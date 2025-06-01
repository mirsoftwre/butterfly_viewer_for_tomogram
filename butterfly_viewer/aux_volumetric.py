#!/usr/bin/env python3

"""Volumetric image handling for multi-page TIFF files.

Not intended as a script. Used in Butterfly Viewer for handling volumetric images.

This module provides functionality for:
1. Detecting multi-page TIFF files
2. Extracting slice information
3. Loading individual slices
4. Managing volumetric image state

Supported formats:
- Single channel (grayscale) multi-page TIFF files with pixel types:
  * 8-bit unsigned integer
  * 16-bit unsigned integer
  * 32-bit signed integer
  * 32-bit floating point
"""
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import numpy as np
from PIL import Image
import tifffile
from PyQt5 import QtCore, QtGui


class VolumetricImageHandler:
    """Handler for volumetric images (multi-page TIFF files).
    
    Provides functionality to detect, analyze and load slices from multi-page TIFF files.
    Only supports single-channel (grayscale) TIFF files with various bit depths.
    
    Attributes:
        filepath (str): Path to the volumetric image file
        total_slices (int): Total number of slices in the volumetric image
        current_slice (int): Currently displayed slice index
        bit_depth (int): Bit depth of the image (8, 16, 32)
        is_float (bool): True if the image contains floating point data
        data_range (tuple): Min and max values in data for normalization
        original_data_range (tuple): Original min and max values from full data analysis
        use_forced_range (bool): Whether to use a forced range instead of the detected range
    """
    
    def __init__(self, filepath):
        """Initialize the volumetric image handler.
        
        Args:
            filepath (str): Path to the multi-page TIFF file
        """
        self.filepath = filepath
        self.total_slices = 0
        self.current_slice = 0
        self.bit_depth = 8
        self.is_float = False
        self.data_range = (0, 255)  # Default for 8-bit data
        self.original_data_range = (0, 255)  # Store original range
        self.use_forced_range = False  # Flag to indicate if range is forced
        self.use_tifffile = False  # Flag for using tifffile backend
        self._memmap = None  # Optional memory-mapped array for tifffile
        self._cached_slices = {}  # Dictionary to cache loaded slices
        self._analyze_file()
        
    def _analyze_file(self):
        """Analyze the file to determine if it's a multi-page TIFF and count slices.
        Also determines bit depth and data type, and analyzes all slices to find global min/max.
        """
        try:
            mm = tifffile.memmap(self.filepath)
            self.use_tifffile = True
            self._memmap = mm

            dtype = mm.dtype
            self.bit_depth = dtype.itemsize * 8
            self.is_float = np.issubdtype(dtype, np.floating)

            if mm.ndim > 2:
                self.total_slices = mm.shape[0]
            else:
                self.total_slices = len(mm)

            global_min = float(np.min(mm))
            global_max = float(np.max(mm))
            if global_min < global_max:
                self.original_data_range = (global_min, global_max)
                if not self.use_forced_range:
                    self.data_range = self.original_data_range
            self.current_slice = self.total_slices // 2
            return
        except Exception as e:
            print(f"tifffile analysis failed: {e}")

        try:
            with Image.open(self.filepath) as img:
                if img.mode not in ('L', 'I', 'F', 'I;16', 'I;16L', 'I;16B', 'I;16N'):
                    raise ValueError(f"Unsupported image mode: {img.mode}. Only single-channel images are supported.")

                if img.mode == 'L':
                    self.bit_depth = 8
                    self.is_float = False
                    global_min, global_max = 0, 255
                elif img.mode.startswith('I;16'):
                    self.bit_depth = 16
                    self.is_float = False
                    global_min, global_max = np.iinfo(np.uint16).max, np.iinfo(np.uint16).min
                elif img.mode == 'I':
                    self.bit_depth = 32
                    self.is_float = False
                    global_min, global_max = np.iinfo(np.int32).max, np.iinfo(np.int32).min
                elif img.mode == 'F':
                    self.bit_depth = 32
                    self.is_float = True
                    global_min, global_max = float('inf'), float('-inf')

                self.total_slices = 0
                try:
                    while True:
                        if img.mode != 'L':
                            img_array = np.array(img)
                            if img.mode.startswith('I;16'):
                                img_array = img_array.astype(np.uint16)
                            slice_min = np.min(img_array)
                            slice_max = np.max(img_array)
                            global_min = min(global_min, slice_min)
                            global_max = max(global_max, slice_max)

                        self.total_slices += 1
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass

                if global_min < global_max:
                    self.original_data_range = (float(global_min), float(global_max))
                    if not self.use_forced_range:
                        self.data_range = self.original_data_range

                self.current_slice = self.total_slices // 2
        except Exception as e:
            print(f"Error analyzing volumetric file: {e}")
            self.total_slices = 0
    
    @staticmethod
    def is_volumetric_file(filepath):
        """Check if the given file is a multi-page TIFF (volumetric image).
        
        Args:
            filepath (str): Path to the file to check
            
        Returns:
            bool: True if the file is a single-channel multi-page TIFF with more than 1 slice, False otherwise
        """
        try:
            if not os.path.exists(filepath) or not filepath.lower().endswith((".tif", ".tiff")):
                return False

            with tifffile.TiffFile(filepath) as tif:
                if tif.pages[0].samples != 1:
                    return False

                if len(tif.pages) > 1:
                    return True

            mm = tifffile.memmap(filepath)
            if mm.ndim > 2 and mm.shape[0] > 1:
                return True
            return False
        except Exception:
            try:
                with Image.open(filepath) as img:
                    if img.mode not in ("L", "I", "F", "I;16", "I;16L", "I;16B", "I;16N"):
                        return False
                    try:
                        img.seek(1)
                        return True
                    except EOFError:
                        return False
            except Exception:
                return False
    
    def _normalize_image(self, img):
        """Normalize image data to 8-bit range for display.
        
        Args:
            img (PIL.Image): The original image
            
        Returns:
            PIL.Image: Normalized 8-bit grayscale image
        """
        if img.mode == 'L':
            return img  # Already 8-bit, no normalization needed
        
        # For 16-bit, 32-bit integer, or float data, normalize to 8-bit range
        img_array = np.array(img)
        
        # Handle 16-bit images
        if img.mode.startswith('I;16'):
            img_array = img_array.astype(np.uint16)
        
        # Check if we need to update the data range
        min_val, max_val = self.data_range
        if min_val == max_val:  # Handle edge case of constant value
            normalized = np.zeros_like(img_array, dtype=np.uint8)
            return Image.fromarray(normalized)
        
        # Normalize to [0, 255] range
        normalized = np.clip(img_array, min_val, max_val)  # Clip to min/max range
        normalized = ((normalized - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        
        return Image.fromarray(normalized)
    
    def get_slice_pixmap(self, slice_index=None):
        """Get a QPixmap for the specified slice.
        
        Args:
            slice_index (int, optional): Index of the slice to load. If None, uses current_slice.
            
        Returns:
            QPixmap: The pixmap for the requested slice, or None if loading fails
        """
        if slice_index is None:
            slice_index = self.current_slice
            
        # Validate index
        if slice_index < 0 or slice_index >= self.total_slices:
            return None
            
        # Check if slice is already cached
        if slice_index in self._cached_slices:
            return self._cached_slices[slice_index]
            
        # Load the slice
        try:
            if self.use_tifffile and self._memmap is not None:
                arr = np.array(self._memmap[slice_index])
                img = Image.fromarray(arr)
            elif self.use_tifffile:
                arr = tifffile.imread(self.filepath, key=slice_index)
                img = Image.fromarray(arr)
            else:
                with Image.open(self.filepath) as im:
                    im.seek(slice_index)
                    img = im.copy()

            normalized_img = self._normalize_image(img)

            data = normalized_img.tobytes("raw", "L")
            qimage = QtGui.QImage(
                data,
                normalized_img.width,
                normalized_img.height,
                normalized_img.width,
                QtGui.QImage.Format_Grayscale8,
            )
            pixmap = QtGui.QPixmap.fromImage(qimage)

            # Cache the slice (limit cache to 10 slices to manage memory)
            if len(self._cached_slices) > 10:
                oldest_key = next(iter(self._cached_slices))
                del self._cached_slices[oldest_key]

            self._cached_slices[slice_index] = pixmap
            return pixmap
        except Exception as e:
            print(f"Error loading slice {slice_index}: {e}")
            return None

    def get_slice_array(self, slice_index=None):
        """Get the raw numpy array for the specified slice."""
        if slice_index is None:
            slice_index = self.current_slice
        if slice_index < 0 or slice_index >= self.total_slices:
            return None
        try:
            if self.use_tifffile and self._memmap is not None:
                return np.array(self._memmap[slice_index])
            if self.use_tifffile:
                return tifffile.imread(self.filepath, key=slice_index)
            with Image.open(self.filepath) as im:
                im.seek(slice_index)
                arr = np.array(im)
                if im.mode.startswith('I;16'):
                    arr = arr.astype(np.uint16)
                return arr
        except Exception as e:
            print(f"Error loading slice array {slice_index}: {e}")
            return None
    
    def set_current_slice(self, slice_index):
        """Set the current slice index.
        
        Args:
            slice_index (int): Index of the slice to set as current
            
        Returns:
            bool: True if successful, False if the index is invalid
        """
        if 0 <= slice_index < self.total_slices:
            self.current_slice = slice_index
            return True
        return False
        
    def get_center_slice_index(self):
        """Get the index of the center slice.
        
        Returns:
            int: Index of the center slice
        """
        return self.total_slices // 2
    
    def get_info(self):
        """Get information about the volumetric image.
        
        Returns:
            dict: Dictionary containing information about the image
        """
        return {
            "filepath": self.filepath,
            "total_slices": self.total_slices,
            "current_slice": self.current_slice,
            "bit_depth": self.bit_depth,
            "is_float": self.is_float,
            "data_range": self.data_range
        }
    
    def update_display_range(self, min_value=None, max_value=None, force=False):
        """Update the display range for normalization of high bit-depth images.
        
        Args:
            min_value (float, optional): Minimum value for display range. If None, use detected min.
            max_value (float, optional): Maximum value for display range. If None, use detected max.
            force (bool, optional): If True, force the range even when new data is loaded.
            
        Returns:
            bool: True if successful
        """
        if min_value is not None and max_value is not None and force:
            # Force the range and set the flag
            self.use_forced_range = True
            current_min, current_max = min_value, max_value
        else:
            # Use the current range as a starting point
            current_min, current_max = self.data_range
            
            if min_value is not None:
                current_min = min_value
            
            if max_value is not None:
                current_max = max_value
        
        # Update the range if valid
        if current_min < current_max:
            self.data_range = (current_min, current_max)
            # Clear cache to force re-normalization
            self._cached_slices = {}
            return True
        
        return False
        
    def reset_display_range(self):
        """Reset the display range to the original detected values.
        
        Returns:
            bool: True if successful
        """
        self.use_forced_range = False
        self.data_range = self.original_data_range
        # Clear cache to force re-normalization
        self._cached_slices = {}
        return True
