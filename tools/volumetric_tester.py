#!/usr/bin/env python3

"""Multi-page TIFF Viewer Utility for Testing VolumetricImageHandler

This utility allows testing the VolumetricImageHandler class by providing an
interface to:
1. Open multi-page TIFF files
2. Navigate through slices
3. View image information (bit depth, data type, etc.)
4. Adjust display range for high bit-depth images

Usage:
    python volumetric_tester.py [filepath]
    
    If filepath is provided, the utility will attempt to open it on startup.

Keyboard shortcuts:
    Left/Right Arrow: Previous/Next slice
    Home/End: First/Last slice
    +/-: Adjust maximum display range
    Ctrl++/Ctrl+-: Adjust minimum display range
    R: Reset display range to detected values
    F: Force current range for all slices
"""

import os
import sys
import argparse
from PyQt5 import QtWidgets, QtGui, QtCore
import inspect

# Add parent directory to path to import from butterfly_viewer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the VolumetricImageHandler class
from butterfly_viewer.aux_volumetric import VolumetricImageHandler

class VolumetricTesterApp(QtWidgets.QMainWindow):
    """Application for testing the VolumetricImageHandler class."""
    
    def __init__(self, filepath=None):
        """Initialize the VolumetricTester application.
        
        Args:
            filepath (str, optional): Path to a multi-page TIFF file to open on startup.
        """
        super().__init__()
        
        self.volumetric_handler = None
        self.filepath = filepath
        
        self._setup_ui()
        
        if filepath:
            self._load_file(filepath)
    
    def _setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Volumetric Image Tester")
        self.resize(800, 600)
        
        # Create central widget and layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        
        # Create image display area
        self.image_label = QtWidgets.QLabel("No image loaded")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setStyleSheet("background-color: #333; color: white;")
        
        # Create scroll area for the image
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        
        # Create file info area
        self.info_label = QtWidgets.QLabel("No file loaded")
        self.info_label.setAlignment(QtCore.Qt.AlignCenter)
        
        # Create slice navigation controls
        nav_layout = QtWidgets.QHBoxLayout()
        
        # Add buttons for navigation
        self.prev_button = QtWidgets.QPushButton("Previous")
        self.prev_button.clicked.connect(self._go_to_previous_slice)
        
        self.next_button = QtWidgets.QPushButton("Next")
        self.next_button.clicked.connect(self._go_to_next_slice)
        
        # Add slice counter label
        self.slice_label = QtWidgets.QLabel("Slice: -/-")
        self.slice_label.setAlignment(QtCore.Qt.AlignCenter)
        
        # Add slice slider
        self.slice_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slice_slider.setEnabled(False)
        self.slice_slider.valueChanged.connect(self._on_slider_changed)
        
        # Add components to navigation layout
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.slice_slider)
        nav_layout.addWidget(self.next_button)
        
        # Create range adjustment controls (for high bit-depth images)
        range_layout = QtWidgets.QHBoxLayout()
        
        range_label = QtWidgets.QLabel("Display Range:")
        self.min_value_label = QtWidgets.QLabel("Min: -")
        self.max_value_label = QtWidgets.QLabel("Max: -")
        
        self.reset_range_button = QtWidgets.QPushButton("Reset Range")
        self.reset_range_button.clicked.connect(self._reset_display_range)
        
        self.force_range_button = QtWidgets.QPushButton("Force Range")
        self.force_range_button.setToolTip("Use current range for all slices")
        self.force_range_button.clicked.connect(self._force_display_range)
        
        range_layout.addWidget(range_label)
        range_layout.addWidget(self.min_value_label)
        range_layout.addWidget(self.max_value_label)
        range_layout.addWidget(self.reset_range_button)
        range_layout.addWidget(self.force_range_button)
        
        # Add controls to main layout
        main_layout.addWidget(scroll_area, 1)
        main_layout.addWidget(self.info_label)
        main_layout.addWidget(self.slice_label)
        main_layout.addLayout(nav_layout)
        main_layout.addLayout(range_layout)
        
        # Create menu bar
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        
        # Create actions
        open_action = QtWidgets.QAction("Open...", self)
        open_action.setShortcut(QtGui.QKeySequence.Open)
        open_action.triggered.connect(self._on_open_file)
        
        exit_action = QtWidgets.QAction("Exit", self)
        exit_action.setShortcut(QtGui.QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        
        # Add actions to menu
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # Create status bar
        self.statusBar().showMessage("Ready")
        self.statusBar().addPermanentWidget(
            QtWidgets.QLabel("Left/Right: Navigate slices, +/-: Adjust range, R: Reset range, F: Force range")
        )
        
        # Set up keyboard shortcuts
        self._setup_shortcuts()
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts for navigation and adjustments."""
        # Previous slice (Left arrow)
        self.shortcut_prev = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), self)
        self.shortcut_prev.activated.connect(self._go_to_previous_slice)
        
        # Next slice (Right arrow)
        self.shortcut_next = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right), self)
        self.shortcut_next.activated.connect(self._go_to_next_slice)
        
        # First slice (Home)
        self.shortcut_first = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Home), self)
        self.shortcut_first.activated.connect(self._go_to_first_slice)
        
        # Last slice (End)
        self.shortcut_last = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_End), self)
        self.shortcut_last.activated.connect(self._go_to_last_slice)
        
        # Increase max display value (+)
        self.shortcut_inc_max = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Plus), self)
        self.shortcut_inc_max.activated.connect(lambda: self._adjust_display_range(max_delta=0.1))
        
        # Decrease max display value (-)
        self.shortcut_dec_max = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Minus), self)
        self.shortcut_dec_max.activated.connect(lambda: self._adjust_display_range(max_delta=-0.1))
        
        # Increase min display value (Ctrl+Plus)
        self.shortcut_inc_min = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl++"), self)
        self.shortcut_inc_min.activated.connect(lambda: self._adjust_display_range(min_delta=0.1))
        
        # Decrease min display value (Ctrl+Minus)
        self.shortcut_dec_min = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+-"), self)
        self.shortcut_dec_min.activated.connect(lambda: self._adjust_display_range(min_delta=-0.1))
        
        # Reset display range (R)
        self.shortcut_reset = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_R), self)
        self.shortcut_reset.activated.connect(self._reset_display_range)
        
        # Force display range (F)
        self.shortcut_force = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F), self)
        self.shortcut_force.activated.connect(self._force_display_range)
    
    def _on_open_file(self):
        """Handle open file action."""
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Multi-page TIFF",
            os.path.dirname(self.filepath) if self.filepath else "",
            "TIFF Files (*.tif *.tiff);;All Files (*)"
        )
        
        if filepath:
            self._load_file(filepath)
    
    def _load_file(self, filepath):
        """Load a multi-page TIFF file.
        
        Args:
            filepath (str): Path to the file to load
        """
        self.statusBar().showMessage(f"Loading {os.path.basename(filepath)}...")
        
        # Check if the file is a volumetric image
        if not VolumetricImageHandler.is_volumetric_file(filepath):
            QtWidgets.QMessageBox.warning(
                self,
                "Not a volumetric image",
                f"The file {os.path.basename(filepath)} is not a multi-page TIFF file or is not a single-channel image."
            )
            self.statusBar().showMessage("File loading failed")
            return
        
        try:
            # Create volumetric handler
            self.volumetric_handler = VolumetricImageHandler(filepath)
            self.filepath = filepath
            
            # Update UI
            self._update_info()
            
            # Set up slider
            self.slice_slider.setMinimum(0)
            self.slice_slider.setMaximum(self.volumetric_handler.total_slices - 1)
            self.slice_slider.setValue(self.volumetric_handler.current_slice)
            self.slice_slider.setEnabled(True)
            
            # Load the current slice
            self._load_slice(self.volumetric_handler.current_slice)
            
            self.statusBar().showMessage(f"Loaded {os.path.basename(filepath)} with {self.volumetric_handler.total_slices} slices")
        
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error loading file",
                f"An error occurred while loading {filepath}:\n{str(e)}"
            )
            self.statusBar().showMessage("File loading failed")
    
    def _update_info(self):
        """Update information display about the current file."""
        if not self.volumetric_handler:
            self.info_label.setText("No file loaded")
            return
        
        info = self.volumetric_handler.get_info()
        
        # Format information for display
        filename = os.path.basename(info["filepath"])
        bit_depth = info["bit_depth"]
        data_type = "Float" if info["is_float"] else "Integer"
        data_range = f"{info['data_range'][0]:.2f} to {info['data_range'][1]:.2f}"
        
        # Add info about original range if different
        if hasattr(self.volumetric_handler, 'original_data_range') and self.volumetric_handler.use_forced_range:
            orig_range = self.volumetric_handler.original_data_range
            data_range += f" (original: {orig_range[0]:.2f} to {orig_range[1]:.2f})"
        
        # Update info label
        info_text = f"File: {filename} | Type: {bit_depth}-bit {data_type} | Range: {data_range} | Slices: {info['total_slices']}"
        self.info_label.setText(info_text)
        
        # Update min/max labels
        self.min_value_label.setText(f"Min: {info['data_range'][0]:.2f}")
        self.max_value_label.setText(f"Max: {info['data_range'][1]:.2f}")
    
    def _on_slider_changed(self, value):
        """Handle slice slider value change.
        
        Args:
            value (int): The new slice index
        """
        if self.volumetric_handler and 0 <= value < self.volumetric_handler.total_slices:
            self._load_slice(value)
    
    def _load_slice(self, slice_index):
        """Load and display a specific slice.
        
        Args:
            slice_index (int): Index of the slice to load
        """
        if not self.volumetric_handler:
            return
        
        # Update current slice in handler
        self.volumetric_handler.set_current_slice(slice_index)
        
        # Get pixmap for the slice
        pixmap = self.volumetric_handler.get_slice_pixmap(slice_index)
        
        if pixmap:
            # Set the pixmap to the image label
            self.image_label.setPixmap(pixmap)
            self.image_label.adjustSize()
            
            # Update slice label
            self.slice_label.setText(f"Slice: {slice_index + 1}/{self.volumetric_handler.total_slices}")
            
            # Update slider (avoid recursive calls)
            if self.slice_slider.value() != slice_index:
                self.slice_slider.blockSignals(True)
                self.slice_slider.setValue(slice_index)
                self.slice_slider.blockSignals(False)
            
            self.statusBar().showMessage(f"Displaying slice {slice_index + 1}/{self.volumetric_handler.total_slices}")
        else:
            self.image_label.setText(f"Failed to load slice {slice_index}")
            self.statusBar().showMessage(f"Failed to load slice {slice_index}")
    
    def _go_to_previous_slice(self):
        """Navigate to the previous slice."""
        if not self.volumetric_handler:
            return
            
        current = self.volumetric_handler.current_slice
        if current > 0:
            self._load_slice(current - 1)
    
    def _go_to_next_slice(self):
        """Navigate to the next slice."""
        if not self.volumetric_handler:
            return
            
        current = self.volumetric_handler.current_slice
        if current < self.volumetric_handler.total_slices - 1:
            self._load_slice(current + 1)
    
    def _go_to_first_slice(self):
        """Navigate to the first slice."""
        if not self.volumetric_handler:
            return
            
        self._load_slice(0)
    
    def _go_to_last_slice(self):
        """Navigate to the last slice."""
        if not self.volumetric_handler:
            return
            
        last_slice = self.volumetric_handler.total_slices - 1
        self._load_slice(last_slice)
    
    def _adjust_display_range(self, min_delta=0, max_delta=0):
        """Adjust the display range for normalization.
        
        Args:
            min_delta (float): Amount to adjust the minimum value
            max_delta (float): Amount to adjust the maximum value
        """
        if not self.volumetric_handler:
            return
        
        # Get current range
        min_val, max_val = self.volumetric_handler.data_range
        
        # Calculate the current range span
        range_span = max_val - min_val
        
        # Convert delta to absolute values based on range span
        absolute_min_delta = range_span * min_delta
        absolute_max_delta = range_span * max_delta
        
        # Calculate new values
        new_min = min_val + absolute_min_delta
        new_max = max_val + absolute_max_delta
        
        # Don't let min exceed max
        if new_min >= new_max:
            if min_delta > 0:  # Min is increasing
                new_min = new_max - (range_span * 0.01)  # Keep a small gap
            elif max_delta < 0:  # Max is decreasing
                new_max = new_min + (range_span * 0.01)  # Keep a small gap
        
        # Update range
        if self.volumetric_handler.update_display_range(new_min, new_max):
            # Update display
            self._update_info()
            self._load_slice(self.volumetric_handler.current_slice)
            
            self.statusBar().showMessage(f"Display range updated: {new_min:.2f} to {new_max:.2f}")
    
    def _reset_display_range(self):
        """Reset the display range to the detected min/max values."""
        if not self.volumetric_handler:
            return
            
        # Use the new reset method if available
        if hasattr(self.volumetric_handler, 'reset_display_range'):
            self.volumetric_handler.reset_display_range()
        else:
            # Fallback for backward compatibility
            self.volumetric_handler._analyze_file()
        
        # Update display
        self._update_info()
        self._load_slice(self.volumetric_handler.current_slice)
        
        self.statusBar().showMessage("Display range reset to original values")
    
    def _force_display_range(self):
        """Force the current display range for all future operations."""
        if not self.volumetric_handler:
            return
            
        min_val, max_val = self.volumetric_handler.data_range
        
        # Only proceed if update_display_range has the force parameter
        if hasattr(self.volumetric_handler, 'update_display_range') and \
           len(inspect.signature(self.volumetric_handler.update_display_range).parameters) >= 3:
            if self.volumetric_handler.update_display_range(min_val, max_val, force=True):
                self._update_info()
                self.statusBar().showMessage(f"Display range forced to: {min_val:.2f} to {max_val:.2f}")


def main():
    """Run the VolumetricTester application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Multi-page TIFF Viewer Utility for testing VolumetricImageHandler")
    parser.add_argument("filepath", nargs="?", help="Path to a multi-page TIFF file to open on startup")
    args = parser.parse_args()
    
    # Create and start application
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for a modern look
    
    # Create main window
    main_window = VolumetricTesterApp(args.filepath)
    main_window.show()
    
    # Execute application
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 