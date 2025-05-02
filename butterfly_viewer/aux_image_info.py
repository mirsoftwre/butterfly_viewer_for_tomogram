#!/usr/bin/env python3

"""Dialog for displaying image file information.

Not intended as a script.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from PyQt5 import QtCore, QtWidgets
from PIL import Image
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
            with Image.open(filepath) as img:
                # Basic information
                form_layout.addRow("File:", QtWidgets.QLabel(filepath))
                form_layout.addRow("Format:", QtWidgets.QLabel(img.format))
                form_layout.addRow("Size:", QtWidgets.QLabel(f"{img.width} x {img.height} pixels"))
                
                # Mode information with description
                mode_label = QtWidgets.QLabel(img.mode)
                mode_label.setToolTip(self.MODE_DESCRIPTIONS.get(img.mode, ""))
                form_layout.addRow("Mode:", mode_label)
                
                # Add mode description if available
                if img.mode in self.MODE_DESCRIPTIONS:
                    desc_label = QtWidgets.QLabel(self.MODE_DESCRIPTIONS[img.mode])
                    desc_label.setWordWrap(True)
                    desc_label.setStyleSheet("color: gray; font-size: 9pt;")
                    form_layout.addRow("", desc_label)
                
                # Get number of channels
                if img.mode == 'RGB':
                    channels = 3
                elif img.mode == 'RGBA':
                    channels = 4
                elif img.mode == 'L':
                    channels = 1
                elif img.mode == 'CMYK':
                    channels = 4
                elif img.mode == 'YCbCr':
                    channels = 3
                elif img.mode == 'LAB':
                    channels = 3
                elif img.mode == 'HSV':
                    channels = 3
                elif img.mode == 'LA':
                    channels = 2
                else:
                    channels = None
                    
                if channels is not None:
                    form_layout.addRow("Channels:", QtWidgets.QLabel(str(channels)))
                
                # Get bit depth
                if img.mode == '1':
                    bit_depth = 1
                elif img.mode in ['RGB', 'RGBA', 'L', 'P', 'CMYK', 'YCbCr', 'LAB', 'HSV']:
                    bit_depth = 8
                elif img.mode == 'I':
                    bit_depth = 32
                elif img.mode == 'F':
                    bit_depth = 32
                elif img.mode.startswith('I;16'):
                    bit_depth = 16
                else:
                    bit_depth = None
                    
                if bit_depth is not None:
                    form_layout.addRow("Bit Depth:", QtWidgets.QLabel(f"{bit_depth} bits"))
                
                # Check if multi-page
                try:
                    img.seek(1)
                    # Count total pages
                    n_frames = 1
                    while True:
                        try:
                            img.seek(img.tell() + 1)
                            n_frames += 1
                        except EOFError:
                            break
                    form_layout.addRow("Number of Images:", QtWidgets.QLabel(str(n_frames)))
                except EOFError:
                    # Not a multi-page image
                    pass
                
        except Exception as e:
            error_label = QtWidgets.QLabel(f"Error reading image information: {str(e)}")
            error_label.setWordWrap(True)
            layout.addWidget(error_label)
        
        # Add close button
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box) 