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
- BigTIFF support for files larger than 2GB
"""
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import numpy as np
from PIL import Image, TiffTags, TiffImagePlugin
from PyQt5 import QtCore, QtGui
import logging
import tifffile

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class VolumetricImageHandler:
    """Handler for volumetric images (multi-page TIFF files).
    
    Provides functionality to detect, analyze and load slices from multi-page TIFF files.
    Only supports single-channel (grayscale) TIFF files with various bit depths.
    Supports BigTIFF format for files larger than 2GB.
    
    Attributes:
        filepath (str): Path to the volumetric image file
        total_slices (int): Total number of slices in the volumetric image
        current_slice (int): Currently displayed slice index
        bit_depth (int): Bit depth of the image (8, 16, 32)
        is_float (bool): True if the image contains floating point data
        data_range (tuple): Min and max values in data for normalization
        original_data_range (tuple): Original min and max values from full data analysis
        use_forced_range (bool): Whether to use a forced range instead of the detected range
        is_bigtiff (bool): True if the file is in BigTIFF format
    """
    
    def __init__(self, filepath):
        """Initialize the handler with a file path.
        
        Args:
            filepath (str): Path to the volumetric image file.
        """
        self.filepath = filepath
        self.is_volumetric = False
        self.shape = None
        self.dtype = None
        self.axes = None
        self.n_pages = 0
        self.total_slices = 0  # For backward compatibility
        self.is_bigtiff = False
        self.byte_order = None
        self.compression = None
        self.photometric = None
        self.planar_config = None
        self.bits_per_sample = None
        self.samples_per_pixel = None
        self.rows_per_strip = None
        self.image_width = None
        self.image_length = None
        self.memory_usage = 0
        self.current_slice = 0
        self.data_range = None
        self.original_data_range = None  # For backward compatibility
        self.use_forced_range = False  # For backward compatibility
        self.is_float = False  # For backward compatibility
        self.bit_depth = 8  # For backward compatibility
        self._cached_slices = {}  # For backward compatibility
        
        # Analyze the file
        self._analyze_file()
        
        # Set current slice to middle by default
        if self.n_pages > 0:
            self.current_slice = self.n_pages // 2
            self.total_slices = self.n_pages  # For backward compatibility
        
    def _analyze_file(self):
        """Analyze the file to determine its type and properties."""
        try:
            with tifffile.TiffFile(self.filepath) as tif:
                self.is_volumetric = True
                self.shape = tif.series[0].shape
                self.dtype = tif.series[0].dtype
                self.axes = tif.series[0].axes
                self.n_pages = len(tif.series[0].pages)
                self.is_bigtiff = tif.is_bigtiff
                logger.info(f"File is BigTIFF: {self.is_bigtiff}")
                logger.info(f"File shape: {self.shape}")
                logger.info(f"File dtype: {self.dtype}")
                logger.info(f"File axes: {self.axes}")
                logger.info(f"Number of pages: {self.n_pages}")
                
                # Get metadata from the first page
                page = tif.series[0].pages[0]
                self.byte_order = tif.byteorder
                self.compression = page.compression
                self.photometric = page.photometric
                self.planar_config = page.planarconfig
                self.bits_per_sample = page.bitspersample
                self.samples_per_pixel = page.samplesperpixel
                self.rows_per_strip = page.rowsperstrip
                self.image_width = page.imagewidth
                self.image_length = page.imagelength
                self.memory_usage = np.prod(self.shape) * self.dtype.itemsize
                
                # Set data type specific properties
                if self.dtype == np.float32:
                    self.is_float = True
                    self.bit_depth = 32
                    data = tif.series[0].asarray()
                    min_val = float(np.min(data))
                    max_val = float(np.max(data))
                    self.original_data_range = (min_val, max_val)
                    self.data_range = self.original_data_range
                    logger.info(f"Data range: {self.data_range}")
                elif self.dtype == np.uint8:
                    self.is_float = False
                    self.bit_depth = 8
                    self.original_data_range = (0, 255)
                elif self.dtype == np.uint16:
                    self.is_float = False
                    self.bit_depth = 16
                    self.original_data_range = (0, 65535)
                elif self.dtype == np.int32:
                    self.is_float = False
                    self.bit_depth = 32
                    self.original_data_range = (-2147483648, 2147483647)
                else:
                    raise ValueError(f"Unsupported data type: {self.dtype}")
                
                if not self.is_float:
                    self.data_range = self.original_data_range
        except Exception as e:
            logger.error(f"Error analyzing file with tifffile: {e}")
            raise ValueError(f"Could not read file {self.filepath} with tifffile")
    
    @staticmethod
    def is_volumetric_file(filepath):
        """Check if a file is a volumetric image file (multi-page TIFF).
        
        Args:
            filepath (str): Path to the file to check.
            
        Returns:
            bool: True if the file is a volumetric image file, False otherwise.
        """
        try:
            with tifffile.TiffFile(filepath) as tif:
                # Check if it's a multi-page TIFF
                if len(tif.series) > 0 and len(tif.series[0].shape) >= 3:
                    logger.info(f"File detected as volumetric: {filepath}")
                    logger.info(f"Shape: {tif.series[0].shape}")
                    logger.info(f"Is BigTIFF: {tif.is_bigtiff}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error checking file with tifffile: {e}")
            return False
    
    def _normalize_image(self, img_array):
        """Normalize image data to 8-bit range.
        
        Args:
            img_array (numpy.ndarray): Input image array
            
        Returns:
            numpy.ndarray: Normalized 8-bit image array
        """
        # Handle float32 data
        if img_array.dtype == np.float32:
            min_val, max_val = np.min(img_array), np.max(img_array)
            if min_val == max_val:
                return np.zeros_like(img_array, dtype=np.uint8)
            return ((img_array - min_val) / (max_val - min_val) * 255).astype(np.uint8)
            
        # Handle integer data
        if img_array.dtype == np.uint8:
            return img_array
        elif img_array.dtype == np.uint16:
            return (img_array / 256).astype(np.uint8)
        elif img_array.dtype == np.int32:
            # Normalize to 0-255 range
            min_val, max_val = np.min(img_array), np.max(img_array)
            if min_val == max_val:
                return np.zeros_like(img_array, dtype=np.uint8)
            return ((img_array - min_val) / (max_val - min_val) * 255).astype(np.uint8)
        else:
            raise ValueError(f"Unsupported data type: {img_array.dtype}")
    
    def get_slice_pixmap(self, slice_index=None):
        """Get a QPixmap of the specified slice.
        
        Args:
            slice_index (int, optional): Index of the slice to get. If None, uses current_slice.
            
        Returns:
            QPixmap: The slice as a QPixmap.
        """
        if slice_index is None:
            slice_index = self.current_slice
            
        # Validate index
        if slice_index < 0 or slice_index >= self.n_pages:
            return None
            
        # Check if slice is already cached
        if slice_index in self._cached_slices:
            return self._cached_slices[slice_index]
            
        try:
            with tifffile.TiffFile(self.filepath) as tif:
                # Read the specific slice
                data = tif.series[0].pages[slice_index].asarray()
                
                # Get current data range
                min_val, max_val = self.data_range
                
                # Normalize to 0-255 range using the current data range
                data = np.clip(data, min_val, max_val)
                data = ((data - min_val) / (max_val - min_val) * 255).astype(np.uint8)
                
                # Convert to QImage
                height, width = data.shape
                bytes_per_line = width
                image = QtGui.QImage(data.data, width, height, bytes_per_line, QtGui.QImage.Format_Grayscale8)
                pixmap = QtGui.QPixmap.fromImage(image)
                
                # Cache the slice (limit cache to 10 slices to manage memory)
                if len(self._cached_slices) > 10:
                    # Remove least recently used slice (first key)
                    oldest_key = next(iter(self._cached_slices))
                    del self._cached_slices[oldest_key]
                
                self._cached_slices[slice_index] = pixmap
                return pixmap
                
        except Exception as e:
            logger.error(f"Error reading slice {slice_index} with tifffile: {e}")
            raise ValueError(f"Could not read slice {slice_index} from file {self.filepath}")
    
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
        """Update the display range for the image.
        
        Args:
            min_value (float, optional): New minimum value. If None, uses current minimum.
            max_value (float, optional): New maximum value. If None, uses current maximum.
            force (bool, optional): If True, forces the range even if it's outside original range.
            
        Returns:
            bool: True if the range was updated successfully
        """
        if force:
            self.use_forced_range = True
            self.data_range = (min_value, max_value)
            # Clear cache to force re-normalization
            self._cached_slices = {}
            return True
        else:
            self.use_forced_range = False
            current_min, current_max = self.data_range
            
            # If min_value is None, keep current min value
            new_min = min_value if min_value is not None else current_min
            # If max_value is None, keep current max value
            new_max = max_value if max_value is not None else current_max
            
            # Ensure the new range is within the original range
            min_val = max(new_min, self.original_data_range[0])
            max_val = min(new_max, self.original_data_range[1])
            
            # Only clear cache if the range actually changed
            if (min_val, max_val) != self.data_range:
                self.data_range = (min_val, max_val)
                # Clear cache to force re-normalization
                self._cached_slices = {}
            
            return True
    
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
