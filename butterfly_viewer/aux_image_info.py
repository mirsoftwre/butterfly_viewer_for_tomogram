#!/usr/bin/env python3

"""Dialog for displaying image file information.

Not intended as a script.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from PyQt5 import QtCore, QtWidgets
import tifffile
import numpy as np

class ImageInfoDialog(QtWidgets.QDialog):
    """Dialog for displaying detailed image file information.
    
    Shows metadata such as dimensions, number of images (for multi-page files),
    pixel type, and number of channels.
    """
    
    # Mode descriptions based on Pillow documentation
    MODE_DESCRIPTIONS = {
        '1': "1-bit pixels, black and white, stored with one pixel per byte",
        'L': "8-bit pixels, grayscale",
        'P': "8-bit pixels, mapped to any other mode using a color palette",
        'RGB': "3x8-bit pixels, true color",
        'RGBA': "4x8-bit pixels, true color with transparency mask",
        'CMYK': "4x8-bit pixels, color separation",
        'YCbCr': "3x8-bit pixels, color video format (JPEG standard)",
        'LAB': "3x8-bit pixels, the L*a*b color space",
        'HSV': "3x8-bit pixels, Hue, Saturation, Value color space",
        'I': "32-bit signed integer pixels",
        'F': "32-bit floating point pixels",
        'LA': "L with alpha",
        'PA': "P with alpha",
        'RGBX': "true color with padding",
        'RGBa': "true color with premultiplied alpha",
        'La': "L with premultiplied alpha",
        'I;16': "16-bit unsigned integer pixels",
        'I;16L': "16-bit little endian unsigned integer pixels",
        'I;16B': "16-bit big endian unsigned integer pixels",
        'I;16N': "16-bit native endian unsigned integer pixels"
    }
    
    def __init__(self, filepath, parent=None):
        """Initialize the dialog with image file information.
        
        Args:
            filepath (str): Path to the image file
            parent (QWidget, optional): Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("Image Information")
        self.setModal(True)
        self.setMinimumWidth(400)  # Increased width to accommodate mode descriptions
        
        # Create layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Create form layout for info
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)
        
        try:
            # Open image file
            with tifffile.TiffFile(filepath) as tif:
                # Basic information
                form_layout.addRow("File:", QtWidgets.QLabel(filepath))
                form_layout.addRow("Format:", QtWidgets.QLabel("TIFF"))
                
                # Get image data
                img = tif.series[0].pages[0].asarray()
                
                # Size information
                if len(img.shape) == 2:  # Grayscale
                    height, width = img.shape
                    channels = 1
                elif len(img.shape) == 3:  # Color
                    height, width = img.shape[:2]
                    channels = img.shape[2]
                else:
                    height, width = img.shape[:2]
                    channels = 1
                
                form_layout.addRow("Size:", QtWidgets.QLabel(f"{width} x {height} pixels"))
                
                # Mode information
                if len(img.shape) == 2:  # Grayscale
                    mode = 'L'
                elif len(img.shape) == 3:
                    if channels == 3:
                        mode = 'RGB'
                    elif channels == 4:
                        mode = 'RGBA'
                    else:
                        mode = f'Unknown ({channels} channels)'
                else:
                    mode = 'Unknown'
                
                mode_label = QtWidgets.QLabel(mode)
                mode_label.setToolTip(self.MODE_DESCRIPTIONS.get(mode, ""))
                form_layout.addRow("Mode:", mode_label)
                
                # Add mode description if available
                if mode in self.MODE_DESCRIPTIONS:
                    desc_label = QtWidgets.QLabel(self.MODE_DESCRIPTIONS[mode])
                    desc_label.setWordWrap(True)
                    desc_label.setStyleSheet("color: gray; font-size: 9pt;")
                    form_layout.addRow("", desc_label)
                
                # Channels information
                form_layout.addRow("Channels:", QtWidgets.QLabel(str(channels)))
                
                # Bit depth information
                if img.dtype == np.uint8:
                    bit_depth = 8
                elif img.dtype == np.uint16:
                    bit_depth = 16
                elif img.dtype == np.uint32:
                    bit_depth = 32
                elif img.dtype == np.float32:
                    bit_depth = 32
                elif img.dtype == np.float64:
                    bit_depth = 64
                else:
                    bit_depth = None
                
                if bit_depth is not None:
                    form_layout.addRow("Bit Depth:", QtWidgets.QLabel(f"{bit_depth} bits"))
                
                # Check if multi-page
                n_frames = len(tif.series[0].pages)
                if n_frames > 1:
                    form_layout.addRow("Number of Images:", QtWidgets.QLabel(str(n_frames)))
                
        except Exception as e:
            error_label = QtWidgets.QLabel(f"Error reading image information: {str(e)}")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
        
        # Add close button
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box) 