#!/usr/bin/env python3

"""Multi-image viewer for comparing images with synchronized zooming, panning, and sliding overlays.

Intended to be run as a script:
    $ python butterfly_viewer.py

Features:
    Image windows have synchronized zoom and pan by default, but can be optionally unsynced.
    Image windows will auto-arrange and can be set as a grid, column, or row. 
    Users can create sliding overlays up to 2x2 and adjust their transparencies.

Credits:
    PyQt MDI Image Viewer by tpgit (http://tpgit.github.io/MDIImageViewer/) for sync pan and zoom.
"""
# SPDX-License-Identifier: GPL-3.0-or-later



import argparse
from PyQt5 import sip
import time
import os
from datetime import datetime
import math

from PyQt5 import QtCore, QtGui, QtWidgets

from aux_splitview import SplitView
from aux_functions import strippedName, toBool, determineSyncSenderDimension, determineSyncAdjustmentFactor
from aux_trackers import EventTrackerSplitBypassInterface
from aux_interfaces import SplitViewCreator, SlidersOpacitySplitViews, SplitViewManager
from aux_mdi import QMdiAreaWithCustomSignals
from aux_layouts import GridLayoutFloatingShadow
from aux_exif import get_exif_rotation_angle
from aux_buttons import ViewerButton
import icons_rc



os.environ["QT_ENABLE_HIGHDPI_SCALING"]   = "1"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
os.environ["QT_SCALE_FACTOR"]             = "1"

COMPANY = "Mir Software"
DOMAIN = "https://github.com/mirsoftwre/butterfly_viewer_for_tomogram"
APPNAME = "Butterfly Viewer for Volumetric Images"
VERSION = "1.1.1"

SETTING_RECENTFILELIST = "recentfilelist"
SETTING_LAST_DIRECTORY = "lastdirectory"
SETTING_FILEOPEN = "fileOpenDialog"
SETTING_SCROLLBARS = "scrollbars"
SETTING_STATUSBAR = "statusbar"
SETTING_SYNCHZOOM = "synchzoom"
SETTING_SYNCHPAN = "synchpan"



class SplitViewMdiChild(SplitView):
    """Extends SplitView for use in Butterfly Viewer.

    Extends SplitView with keyboard shortcut to lock the position of the split 
    in the Butterfly Viewer.

    Overrides SplitView by checking split lock status before updating split.
    
    Args:
        See parent method for full documentation.
    """

    shortcut_shift_x_was_activated = QtCore.pyqtSignal()
    # Signal when z-slice changed in volumetric data
    slice_changed = QtCore.pyqtSignal(int)
    # Signal when display range changed in volumetric data
    display_range_changed = QtCore.pyqtSignal(float, float)

    def __init__(self, pixmap, filename_main_topleft, name, pixmap_topright, pixmap_bottomleft, pixmap_bottomright, transform_mode_smooth):
        super().__init__(pixmap, filename_main_topleft, name, pixmap_topright, pixmap_bottomleft, pixmap_bottomright, transform_mode_smooth)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self._isUntitled = True
        
        self.toggle_lock_split_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Shift+X"), self)
        self.toggle_lock_split_shortcut.activated.connect(self.toggle_lock_split)

        self._sync_this_zoom = True
        self._sync_this_pan = True
        self._sync_this_slice = True
        self._sync_this_range = True
        
        # Volumetric data handling
        self.is_volumetric = False
        self.volumetric_handler = None
        self.current_slice = 0
        self.total_slices = 0
        self._handling_slice_sync = False  # Flag to prevent infinite recursion
        self._handling_range_sync = False  # Flag to prevent infinite recursion for display range
        
        # Create Z-slice controls (hidden by default)
        self.z_slice_controls = QtWidgets.QWidget(self)
        self.z_slice_controls.setVisible(False)
        layout = QtWidgets.QVBoxLayout(self.z_slice_controls)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        
        # Slice label
        self.slice_label = QtWidgets.QLabel("0/0", self.z_slice_controls)
        self.slice_label.setAlignment(QtCore.Qt.AlignCenter)
        self.slice_label.setMinimumWidth(60)
        layout.addWidget(self.slice_label)
        
        # Previous slice button
        self.prev_slice_button = QtWidgets.QPushButton("▲", self.z_slice_controls)
        self.prev_slice_button.setToolTip("Previous slice")
        self.prev_slice_button.clicked.connect(self.goto_previous_slice)
        layout.addWidget(self.prev_slice_button)
        
        # Slice slider (vertical orientation)
        self.slice_slider = QtWidgets.QSlider(QtCore.Qt.Vertical, self.z_slice_controls)
        self.slice_slider.setToolTip("Navigate through slices")
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.setInvertedAppearance(True)  # Invert so that top is first slice
        self.slice_slider.valueChanged.connect(self.on_slice_slider_changed)
        self.slice_slider.setMinimumHeight(150)
        layout.addWidget(self.slice_slider, 1)
        
        # Next slice button
        self.next_slice_button = QtWidgets.QPushButton("▼", self.z_slice_controls)
        self.next_slice_button.setToolTip("Next slice")
        self.next_slice_button.clicked.connect(self.goto_next_slice)
        layout.addWidget(self.next_slice_button)
        
        # Add slice controls to layout
        self.z_slice_controls.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 120);
                border-radius: 5px;
                padding: 2px;
            }
            QPushButton {
                min-width: 30px;
                max-width: 60px;
                min-height: 25px;
                max-height: 25px;
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border-radius: 3px;
                border: 1px solid rgba(100, 100, 100, 120);
            }
            QLabel {
                color: white;
                font-size: 9pt;
            }
            QSlider {
                min-width: 20px;
            }
        """)
        
        # Position at left of the view, staying away from topleft and bottomleft controls
        self.z_slice_controls.setFixedWidth(50)
        self.z_slice_controls.setFixedHeight(250)
        
        # Add keyboard shortcuts for slice navigation
        self.shortcut_next_slice = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down), self)
        self.shortcut_next_slice.activated.connect(self.goto_next_slice)
        
        self.shortcut_prev_slice = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up), self)
        self.shortcut_prev_slice.activated.connect(self.goto_previous_slice)
        
        # Create data range controls (hidden by default)
        self.data_range_controls = QtWidgets.QWidget(self)
        self.data_range_controls.setVisible(False)
        data_range_layout = QtWidgets.QVBoxLayout(self.data_range_controls)
        data_range_layout.setContentsMargins(5, 5, 5, 5)
        data_range_layout.setSpacing(4)
        
        # Title label
        self.data_range_title = QtWidgets.QLabel("Data Range", self.data_range_controls)
        self.data_range_title.setAlignment(QtCore.Qt.AlignCenter)
        data_range_layout.addWidget(self.data_range_title)
        
        # Original data range label
        self.original_range_label = QtWidgets.QLabel("Original: [0, 255]", self.data_range_controls)
        self.original_range_label.setAlignment(QtCore.Qt.AlignCenter)
        data_range_layout.addWidget(self.original_range_label)
        
        # Current range label
        self.current_range_label = QtWidgets.QLabel("Current: [0, 255]", self.data_range_controls)
        self.current_range_label.setAlignment(QtCore.Qt.AlignCenter)
        data_range_layout.addWidget(self.current_range_label)
        
        # Min value slider and label
        min_layout = QtWidgets.QHBoxLayout()
        self.min_label = QtWidgets.QLabel("Min:", self.data_range_controls)
        min_layout.addWidget(self.min_label)
        
        self.min_value_label = QtWidgets.QLabel("0", self.data_range_controls)
        self.min_value_label.setMinimumWidth(40)
        min_layout.addWidget(self.min_value_label)
        data_range_layout.addLayout(min_layout)
        
        self.min_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self.data_range_controls)
        self.min_slider.setToolTip("Adjust minimum value")
        self.min_slider.valueChanged.connect(self.on_min_slider_changed)
        data_range_layout.addWidget(self.min_slider)
        
        # Max value slider and label
        max_layout = QtWidgets.QHBoxLayout()
        self.max_label = QtWidgets.QLabel("Max:", self.data_range_controls)
        max_layout.addWidget(self.max_label)
        
        self.max_value_label = QtWidgets.QLabel("255", self.data_range_controls)
        self.max_value_label.setMinimumWidth(40)
        max_layout.addWidget(self.max_value_label)
        data_range_layout.addLayout(max_layout)
        
        self.max_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self.data_range_controls)
        self.max_slider.setToolTip("Adjust maximum value")
        self.max_slider.valueChanged.connect(self.on_max_slider_changed)
        data_range_layout.addWidget(self.max_slider)
        
        # Reset button
        self.reset_range_button = QtWidgets.QPushButton("Reset Range", self.data_range_controls)
        self.reset_range_button.clicked.connect(self.reset_display_range)
        data_range_layout.addWidget(self.reset_range_button)
        
        # Apply the same stylesheet as slice controls
        self.data_range_controls.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 120);
                border-radius: 5px;
                padding: 2px;
            }
            QPushButton {
                min-height: 25px;
                max-height: 25px;
                background-color: rgba(60, 60, 60, 180);
                color: white;
                border-radius: 3px;
                border: 1px solid rgba(100, 100, 100, 120);
            }
            QLabel {
                color: white;
                font-size: 9pt;
            }
            QSlider {
                min-height: 20px;
            }
        """)
        
        # Position at bottom of the view
        self.data_range_controls.setFixedWidth(200)
        self.data_range_controls.setFixedHeight(220)
    
    def resizeEvent(self, event):
        """Handle resize events to reposition the Z-slice controls and data range controls."""
        super().resizeEvent(event)
        if hasattr(self, 'z_slice_controls'):
            # Position the z-slice controls at the middle-left, away from top and bottom controls
            middle_y = (self.height() - self.z_slice_controls.height()) // 2
            # Ensure it doesn't overlap with topleft or bottomleft controls
            self.z_slice_controls.move(10, middle_y)
            
        if hasattr(self, 'data_range_controls'):
            # Position the data range controls at the bottom-center
            bottom_y = self.height() - self.data_range_controls.height() - 10
            center_x = (self.width() - self.data_range_controls.width()) // 2
            self.data_range_controls.move(center_x, bottom_y)
    
    def setup_volumetric_mode(self, volumetric_handler, current_slice):
        """Set up the widget to handle volumetric data.
        
        Args:
            volumetric_handler: VolumetricImageHandler instance for the file
            current_slice: Initial slice to display
        """
        self.is_volumetric = True
        self.volumetric_handler = volumetric_handler
        self.current_slice = current_slice
        self.total_slices = volumetric_handler.total_slices
        
        # Configure slider
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(self.total_slices - 1)
        self.slice_slider.setValue(current_slice)
        
        # Update label
        self.update_slice_label()
        
        # Configure data range controls
        self.setup_data_range_controls()
        
        # Show controls and position them
        self.z_slice_controls.setVisible(True)
        self.data_range_controls.setVisible(True)
        
        # Position at the middle-left of the view for slice controls
        middle_y = (self.height() - self.z_slice_controls.height()) // 2
        self.z_slice_controls.move(10, middle_y)
        
        # Position at the bottom-center for data range controls
        bottom_y = self.height() - self.data_range_controls.height() - 10
        center_x = (self.width() - self.data_range_controls.width()) // 2
        self.data_range_controls.move(center_x, bottom_y)
    
    def setup_data_range_controls(self):
        """Configure data range controls based on the current volumetric handler."""
        if not self.is_volumetric or not self.volumetric_handler:
            return
            
        # Get original data range
        orig_min, orig_max = self.volumetric_handler.original_data_range
        curr_min, curr_max = self.volumetric_handler.data_range
        
        # Update labels with actual values
        self.original_range_label.setText(f"Original: [{orig_min:.1f}, {orig_max:.1f}]")
        self.current_range_label.setText(f"Current: [{curr_min:.1f}, {curr_max:.1f}]")
        
        # Configure sliders
        # Use a precision factor for float values
        precision = 100 if self.volumetric_handler.is_float else 1
        
        # Set slider ranges based on original min/max
        range_span = orig_max - orig_min
        self.min_slider.setMinimum(int(orig_min * precision))
        self.min_slider.setMaximum(int(orig_max * precision))
        self.min_slider.setValue(int(curr_min * precision))
        
        self.max_slider.setMinimum(int(orig_min * precision))
        self.max_slider.setMaximum(int(orig_max * precision))
        self.max_slider.setValue(int(curr_max * precision))
        
        # Update value labels
        self.min_value_label.setText(f"{curr_min:.1f}")
        self.max_value_label.setText(f"{curr_max:.1f}")
        
    def on_min_slider_changed(self, value):
        """Handle changes to the minimum value slider.
        
        Args:
            value: New slider value
        """
        if not self.is_volumetric or not self.volumetric_handler:
            return
            
        # Convert slider value back to actual value
        precision = 100 if self.volumetric_handler.is_float else 1
        min_value = value / precision
        
        # Ensure min value doesn't exceed max value
        _, curr_max = self.volumetric_handler.data_range
        if min_value >= curr_max:
            min_value = curr_max - (1/precision)  # Keep at least a small gap
            self.min_slider.blockSignals(True)
            self.min_slider.setValue(int(min_value * precision))
            self.min_slider.blockSignals(False)
            
        # Update display and label
        self.min_value_label.setText(f"{min_value:.1f}")
        self.update_display_range(min_value=min_value)
        
    def on_max_slider_changed(self, value):
        """Handle changes to the maximum value slider.
        
        Args:
            value: New slider value
        """
        if not self.is_volumetric or not self.volumetric_handler:
            return
            
        # Convert slider value back to actual value
        precision = 100 if self.volumetric_handler.is_float else 1
        max_value = value / precision
        
        # Ensure max value doesn't fall below min value
        curr_min, _ = self.volumetric_handler.data_range
        if max_value <= curr_min:
            max_value = curr_min + (1/precision)  # Keep at least a small gap
            self.max_slider.blockSignals(True)
            self.max_slider.setValue(int(max_value * precision))
            self.max_slider.blockSignals(False)
            
        # Update display and label
        self.max_value_label.setText(f"{max_value:.1f}")
        self.update_display_range(max_value=max_value)
        
    def update_display_range(self, min_value=None, max_value=None):
        """Update the display range in the volumetric handler and refresh the view.
        
        Args:
            min_value: New minimum value (or None to keep current)
            max_value: New maximum value (or None to keep current)
        """
        if not self.is_volumetric or not self.volumetric_handler:
            return
            
        # Prevent recursion when syncing display range
        if self._handling_range_sync:
            return
            
        # Update the display range
        updated = self.volumetric_handler.update_display_range(min_value, max_value)
        
        if updated:
            # Refresh the current range label
            curr_min, curr_max = self.volumetric_handler.data_range
            self.current_range_label.setText(f"Current: [{curr_min:.1f}, {curr_max:.1f}]")
            
            # Emit signal for synchronization
            self.display_range_changed.emit(curr_min, curr_max)
            
            # Reload the current slice to apply the new range
            self.load_slice(self.current_slice)
            
            # If range synchronization is enabled, synchronize all other windows
            window = self.window()
            if isinstance(window, MultiViewMainWindow) and self.sync_this_range:
                self._handling_range_sync = True
                window.synchDisplayRange(self, curr_min, curr_max)
                self._handling_range_sync = False
        
    def reset_display_range(self):
        """Reset the display range to the original detected values."""
        if not self.is_volumetric or not self.volumetric_handler:
            return
            
        # Prevent recursion when syncing display range
        if self._handling_range_sync:
            return
            
        # Reset the display range
        reset = self.volumetric_handler.reset_display_range()
        
        if reset:
            # Update the sliders to match the original range
            orig_min, orig_max = self.volumetric_handler.original_data_range
            precision = 100 if self.volumetric_handler.is_float else 1
            
            self.min_slider.blockSignals(True)
            self.min_slider.setValue(int(orig_min * precision))
            self.min_slider.blockSignals(False)
            
            self.max_slider.blockSignals(True)
            self.max_slider.setValue(int(orig_max * precision))
            self.max_slider.blockSignals(False)
            
            # Update the labels
            self.min_value_label.setText(f"{orig_min:.1f}")
            self.max_value_label.setText(f"{orig_max:.1f}")
            self.current_range_label.setText(f"Current: [{orig_min:.1f}, {orig_max:.1f}]")
            
            # Emit signal for synchronization
            self.display_range_changed.emit(orig_min, orig_max)
            
            # Reload the current slice to apply the reset range
            self.load_slice(self.current_slice)
            
            # If range synchronization is enabled, synchronize all other windows
            window = self.window()
            if isinstance(window, MultiViewMainWindow) and self.sync_this_range:
                self._handling_range_sync = True
                window.synchDisplayRange(self, orig_min, orig_max)
                self._handling_range_sync = False
    
    def set_slice_controls_visible(self, visible):
        """Set visibility of slice controls.
        
        Args:
            visible (bool): True to show slice controls, False to hide them
        """
        if hasattr(self, 'z_slice_controls'):
            self.z_slice_controls.setVisible(visible)
            
        # Also handle data range controls
        if hasattr(self, 'data_range_controls') and self.is_volumetric:
            self.data_range_controls.setVisible(visible)
    
    def load_slice(self, slice_index):
        """Load a specific slice of volumetric data.
        
        Args:
            slice_index: Index of the slice to load
        """
        if not self.is_volumetric or not self.volumetric_handler:
            return
        
        # Prevent recursion when syncing slices
        if self._handling_slice_sync:
            return
            
        # Ensure valid slice index
        if slice_index < 0:
            slice_index = 0
        elif slice_index >= self.total_slices:
            slice_index = self.total_slices - 1
        
        # Get pixmap for selected slice
        pixmap = self.volumetric_handler.get_slice_pixmap(slice_index)
        if pixmap:
            # Update pixmap in view
            self.pixmap_main_topleft = pixmap
            
            # Update current slice
            self.current_slice = slice_index
            
            # Update UI
            self.slice_slider.setValue(slice_index)
            self.update_slice_label()
            
            # Emit signal for UI updates
            self.slice_changed.emit(slice_index)
            
            # If slice synchronization is enabled, synchronize all other windows
            window = self.window()
            if isinstance(window, MultiViewMainWindow) and self._sync_this_slice:
                self._handling_slice_sync = True
                window.synchSlice(self)
                self._handling_slice_sync = False
    
    def goto_next_slice(self):
        """Navigate to the next slice in volumetric data."""
        if self.is_volumetric and self.current_slice < self.total_slices - 1:
            self.load_slice(self.current_slice + 1)
    
    def goto_previous_slice(self):
        """Navigate to the previous slice in volumetric data."""
        if self.is_volumetric and self.current_slice > 0:
            self.load_slice(self.current_slice - 1)
    
    def on_slice_slider_changed(self, value):
        """Handle slice slider value change.
        
        Args:
            value: New slider value representing slice index
        """
        if self.is_volumetric and value != self.current_slice:
            self.load_slice(value)
            
    @property
    def sync_this_zoom(self):
        """bool: Setting of whether to sync this by zoom (or not)."""
        return self._sync_this_zoom
    
    @sync_this_zoom.setter
    def sync_this_zoom(self, bool: bool):
        """bool: Set whether to sync this by zoom (or not)."""
        self._sync_this_zoom = bool

    @property
    def sync_this_pan(self):
        """bool: Setting of whether to sync this by pan (or not)."""
        return self._sync_this_pan
    
    @sync_this_pan.setter
    def sync_this_pan(self, bool: bool):
        """bool: Set whether to sync this by pan (or not)."""
        self._sync_this_pan = bool
        
    @property
    def sync_this_slice(self):
        """bool: Setting of whether to sync this by slice (or not)."""
        return self._sync_this_slice
    
    @sync_this_slice.setter
    def sync_this_slice(self, bool: bool):
        """bool: Set whether to sync this by slice (or not)."""
        self._sync_this_slice = bool
        
    @property
    def sync_this_range(self):
        """bool: Setting of whether to sync this by display range (or not)."""
        return self._sync_this_range
    
    @sync_this_range.setter
    def sync_this_range(self, bool: bool):
        """bool: Set whether to sync this by display range (or not)."""
        self._sync_this_range = bool

    # Control the split of the sliding overlay

    def toggle_lock_split(self):
        """Toggle the split lock.
        
        Toggles the status of the split lock (e.g., if locked, it will become unlocked; vice versa).
        """
        self.split_locked = not self.split_locked
        self.shortcut_shift_x_was_activated.emit()
    
    def update_split(self, pos = None, pos_is_global=False, ignore_lock=False):
        """Update the position of the split while considering the status of the split lock.
        
        See parent method for full documentation.
        """
        if not self.split_locked or ignore_lock:
            super().update_split(pos,pos_is_global,ignore_lock=ignore_lock)

    
    # Events

    def enterEvent(self, event):
        """Pass along enter event to parent method."""
        super().enterEvent(event)

    def update_slice_label(self):
        """Update the slice label with current slice information."""
        self.slice_label.setText(f"{self.current_slice + 1}/{self.total_slices}")

    def apply_display_range_sync(self, min_value, max_value):
        """Apply display range from synchronization.
        
        Args:
            min_value: Minimum value for display range
            max_value: Maximum value for display range
        """
        if not self.is_volumetric or not self.volumetric_handler:
            return
            
        # Set the flag to prevent recursion
        self._handling_range_sync = True
        
        # Update sliders
        precision = 100 if self.volumetric_handler.is_float else 1
        
        self.min_slider.blockSignals(True)
        self.min_slider.setValue(int(min_value * precision))
        self.min_slider.blockSignals(False)
        
        self.max_slider.blockSignals(True)
        self.max_slider.setValue(int(max_value * precision))
        self.max_slider.blockSignals(False)
        
        # Update the labels
        self.min_value_label.setText(f"{min_value:.1f}")
        self.max_value_label.setText(f"{max_value:.1f}")
        
        # Update the display range directly
        updated = self.volumetric_handler.update_display_range(min_value, max_value)
        
        if updated:
            # Refresh the current range label
            self.current_range_label.setText(f"Current: [{min_value:.1f}, {max_value:.1f}]")
            
            # Reload the current slice to apply the updated range
            self.load_slice(self.current_slice)
        
        # Clear the flag
        self._handling_range_sync = False

    def set_z_slice_controls_visible(self, visible):
        """Set visibility of z-slice controls.
        
        Args:
            visible (bool): True to show z-slice controls, False to hide them
        """
        if hasattr(self, 'z_slice_controls'):
            self.z_slice_controls.setVisible(visible)
    
    def set_data_range_controls_visible(self, visible):
        """Set visibility of data range controls.
        
        Args:
            visible (bool): True to show data range controls, False to hide them
        """
        if hasattr(self, 'data_range_controls'):
            self.data_range_controls.setVisible(visible)
            


class MultiViewMainWindow(QtWidgets.QMainWindow):
    """View multiple images with split-effect and synchronized panning and zooming.

    Extends QMainWindow as main window of Butterfly Viewer with user interface:

    - Create sliding overlays.
    - Adjust sliding overlay transparencies.
    - Change viewer settings.
    """
    
    MaxRecentFiles = 10

    def __init__(self):
        super(MultiViewMainWindow, self).__init__()

        self._recentFileActions = []
        self._handlingScrollChangedSignal = False
        self._last_accessed_fullpath = None

        self._mdiArea = QMdiAreaWithCustomSignals()
        self._mdiArea.file_path_dragged.connect(self.display_dragged_grayout)
        self._mdiArea.file_path_dragged_and_dropped.connect(self.load_from_dragged_and_dropped_file)
        self._mdiArea.shortcut_escape_was_activated.connect(self.set_fullscreen_off)
        self._mdiArea.shortcut_f_was_activated.connect(self.toggle_fullscreen)
        self._mdiArea.shortcut_h_was_activated.connect(self.toggle_interface)
        self._mdiArea.shortcut_ctrl_c_was_activated.connect(self.copy_view)
        self._mdiArea.first_subwindow_was_opened.connect(self.on_first_subwindow_was_opened)
        self._mdiArea.last_remaining_subwindow_was_closed.connect(self.on_last_remaining_subwindow_was_closed)

        self._mdiArea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._mdiArea.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._mdiArea.subWindowActivated.connect(self.subWindowActivated)

        self._mdiArea.setBackground(QtGui.QColor(32,32,32))

        self._label_mouse = QtWidgets.QLabel() # Pixel coordinates of mouse in a view
        self._label_mouse.setText("")
        self._label_mouse.adjustSize()
        self._label_mouse.setVisible(False)
        self._label_mouse.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)
        self._label_mouse.setStyleSheet("QLabel {color: white; background-color: rgba(0, 0, 0, 191); border: 0px solid black; margin-left: 0.09em; margin-top: 0.09em; margin-right: 0.09em; margin-bottom: 0.09em; font-size: 7.5pt; border-radius: 0.09em; }")

        self._splitview_creator = SplitViewCreator()
        self._splitview_creator.clicked_create_splitview_pushbutton.connect(self.on_create_splitview)
        tracker_creator = EventTrackerSplitBypassInterface(self._splitview_creator)
        tracker_creator.mouse_position_changed.connect(self.update_split)
        layout_mdiarea_topleft = GridLayoutFloatingShadow()
        layout_mdiarea_topleft.addWidget(self._label_mouse, 1, 0, alignment=QtCore.Qt.AlignLeft|QtCore.Qt.AlignBottom)
        layout_mdiarea_topleft.addWidget(self._splitview_creator, 0, 0, alignment=QtCore.Qt.AlignLeft)
        self.interface_mdiarea_topleft = QtWidgets.QWidget()
        self.interface_mdiarea_topleft.setLayout(layout_mdiarea_topleft)

        self._mdiArea.subWindowActivated.connect(self.update_sliders)
        self._mdiArea.subWindowActivated.connect(self.update_window_highlight)
        self._mdiArea.subWindowActivated.connect(self.update_window_labels)
        self._mdiArea.subWindowActivated.connect(self.updateMenus)
        self._mdiArea.subWindowActivated.connect(self.auto_tile_subwindows_on_close)
        self._mdiArea.subWindowActivated.connect(self.update_mdi_buttons)

        self._sliders_opacity_splitviews = SlidersOpacitySplitViews()
        self._sliders_opacity_splitviews.was_changed_slider_base_value.connect(self.on_slider_opacity_base_changed)
        self._sliders_opacity_splitviews.was_changed_slider_topright_value.connect(self.on_slider_opacity_topright_changed)
        self._sliders_opacity_splitviews.was_changed_slider_bottomright_value.connect(self.on_slider_opacity_bottomright_changed)
        self._sliders_opacity_splitviews.was_changed_slider_bottomleft_value.connect(self.on_slider_opacity_bottomleft_changed)
        tracker_sliders = EventTrackerSplitBypassInterface(self._sliders_opacity_splitviews)
        tracker_sliders.mouse_position_changed.connect(self.update_split)

        self._splitview_manager = SplitViewManager()
        self._splitview_manager.hovered_xy.connect(self.set_split_from_manager)
        self._splitview_manager.clicked_xy.connect(self.set_and_lock_split_from_manager)
        self._splitview_manager.lock_split_locked.connect(self.lock_split)
        self._splitview_manager.lock_split_unlocked.connect(self.unlock_split)

        layout_mdiarea_bottomleft = GridLayoutFloatingShadow()
        layout_mdiarea_bottomleft.addWidget(self._sliders_opacity_splitviews, 0, 0, alignment=QtCore.Qt.AlignBottom)
        layout_mdiarea_bottomleft.addWidget(self._splitview_manager, 0, 1, alignment=QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        self.interface_mdiarea_bottomleft = QtWidgets.QWidget()
        self.interface_mdiarea_bottomleft.setLayout(layout_mdiarea_bottomleft)
        
        
        self.centralwidget_during_fullscreen_pushbutton = QtWidgets.QToolButton() # Needed for users to return the image viewer to the main window if the window of the viewer is lost during fullscreen
        self.centralwidget_during_fullscreen_pushbutton.setText("Close Fullscreen") # Needed for users to return the image viewer to the main window if the window of the viewer is lost during fullscreen
        self.centralwidget_during_fullscreen_pushbutton.clicked.connect(self.set_fullscreen_off)
        self.centralwidget_during_fullscreen_layout = QtWidgets.QVBoxLayout()
        self.centralwidget_during_fullscreen_layout.setAlignment(QtCore.Qt.AlignCenter)
        self.centralwidget_during_fullscreen_layout.addWidget(self.centralwidget_during_fullscreen_pushbutton, alignment=QtCore.Qt.AlignCenter)
        self.centralwidget_during_fullscreen = QtWidgets.QWidget()
        self.centralwidget_during_fullscreen.setLayout(self.centralwidget_during_fullscreen_layout)

        self.fullscreen_pushbutton = ViewerButton()
        self.fullscreen_pushbutton.setIcon(":/icons/full-screen.svg")
        self.fullscreen_pushbutton.setCheckedIcon(":/icons/full-screen-exit.svg")
        self.fullscreen_pushbutton.setToolTip("Fullscreen on/off (F)")
        self.fullscreen_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.fullscreen_pushbutton.setMouseTracking(True)
        self.fullscreen_pushbutton.setCheckable(True)
        self.fullscreen_pushbutton.toggled.connect(self.set_fullscreen)
        self.is_fullscreen = False

        self.interface_toggle_pushbutton = ViewerButton()
        self.interface_toggle_pushbutton.setCheckedIcon(":/icons/eye.svg")
        self.interface_toggle_pushbutton.setIcon(":/icons/eye-cancelled.svg")
        self.interface_toggle_pushbutton.setToolTip("Hide interface (H)")
        self.interface_toggle_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.interface_toggle_pushbutton.setMouseTracking(True)
        self.interface_toggle_pushbutton.setCheckable(True)
        self.interface_toggle_pushbutton.setChecked(True)
        self.interface_toggle_pushbutton.clicked.connect(self.show_interface)

        self.is_interface_showing = True
        self.is_quiet_mode = False
        self.is_global_transform_mode_smooth = False
        self.scene_background_color = None
        self.sync_zoom_by = "box"

        self.close_all_pushbutton = ViewerButton(style="trigger-severe")
        self.close_all_pushbutton.setIcon(":/icons/clear.svg")
        self.close_all_pushbutton.setToolTip("Close all image windows")
        self.close_all_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.close_all_pushbutton.setMouseTracking(True)
        self.close_all_pushbutton.clicked.connect(self._mdiArea.closeAllSubWindows)

        self.tile_default_pushbutton = ViewerButton(style="trigger")
        self.tile_default_pushbutton.setIcon(":/icons/capacity.svg")
        self.tile_default_pushbutton.setToolTip("Grid arrange windows")
        self.tile_default_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.tile_default_pushbutton.setMouseTracking(True)
        self.tile_default_pushbutton.clicked.connect(self._mdiArea.tileSubWindows)
        self.tile_default_pushbutton.clicked.connect(self.fit_to_window)
        self.tile_default_pushbutton.clicked.connect(self.refreshPan)

        self.tile_horizontally_pushbutton = ViewerButton(style="trigger")
        self.tile_horizontally_pushbutton.setIcon(":/icons/split-vertically.svg")
        self.tile_horizontally_pushbutton.setToolTip("Horizontally arrange windows in a single row")
        self.tile_horizontally_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.tile_horizontally_pushbutton.setMouseTracking(True)
        self.tile_horizontally_pushbutton.clicked.connect(self._mdiArea.tile_subwindows_horizontally)
        self.tile_horizontally_pushbutton.clicked.connect(self.fit_to_window)
        self.tile_horizontally_pushbutton.clicked.connect(self.refreshPan)

        self.tile_vertically_pushbutton = ViewerButton(style="trigger")
        self.tile_vertically_pushbutton.setIcon(":/icons/split-horizontally.svg")
        self.tile_vertically_pushbutton.setToolTip("Vertically arrange windows in a single column")
        self.tile_vertically_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.tile_vertically_pushbutton.setMouseTracking(True)
        self.tile_vertically_pushbutton.clicked.connect(self._mdiArea.tile_subwindows_vertically)
        self.tile_vertically_pushbutton.clicked.connect(self.fit_to_window)
        self.tile_vertically_pushbutton.clicked.connect(self.refreshPan)

        self.fit_to_window_pushbutton = ViewerButton(style="trigger")
        self.fit_to_window_pushbutton.setIcon(":/icons/pan.svg")
        self.fit_to_window_pushbutton.setToolTip("Fit and center image in active window (affects all if synced)")
        self.fit_to_window_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.fit_to_window_pushbutton.setMouseTracking(True)
        self.fit_to_window_pushbutton.clicked.connect(self.fit_to_window)

        self.info_pushbutton = ViewerButton(style="trigger-transparent")
        self.info_pushbutton.setIcon(":/icons/about.svg")
        self.info_pushbutton.setToolTip("About...")
        self.info_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.info_pushbutton.setMouseTracking(True)
        self.info_pushbutton.clicked.connect(self.info_button_clicked)

        self.stopsync_toggle_pushbutton = ViewerButton(style="green-yellow")
        self.stopsync_toggle_pushbutton.setIcon(":/icons/refresh.svg")
        self.stopsync_toggle_pushbutton.setCheckedIcon(":/icons/refresh-cancelled.svg")
        self.stopsync_toggle_pushbutton.setToolTip("Unsynchronize zoom and pan (currently synced)")
        self.stopsync_toggle_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.stopsync_toggle_pushbutton.setMouseTracking(True)
        self.stopsync_toggle_pushbutton.setCheckable(True)
        self.stopsync_toggle_pushbutton.toggled.connect(self.set_stopsync_pushbutton)

        self.save_view_pushbutton = ViewerButton()
        self.save_view_pushbutton.setIcon(":/icons/download.svg")
        self.save_view_pushbutton.setToolTip("Save a screenshot of the viewer... | Copy screenshot to clipboard (Ctrl·C)")
        self.save_view_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.save_view_pushbutton.setMouseTracking(True)
        self.save_view_pushbutton.clicked.connect(self.save_view)

        self.open_new_pushbutton = ViewerButton()
        self.open_new_pushbutton.setIcon(":/icons/open-file.svg")
        self.open_new_pushbutton.setToolTip("Open image(s) as single windows...")
        self.open_new_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.open_new_pushbutton.setMouseTracking(True)
        self.open_new_pushbutton.clicked.connect(self.open_multiple)

        self.overlay_toggle_pushbutton = ViewerButton(style="blue-red")
        self.overlay_toggle_pushbutton.setIcon(":/icons/layers.svg")
        self.overlay_toggle_pushbutton.setCheckedIcon(":/icons/layers.svg")
        self.overlay_toggle_pushbutton.setToolTip("Show Overlay Controls")
        self.overlay_toggle_pushbutton.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.overlay_toggle_pushbutton.setMouseTracking(True)
        self.overlay_toggle_pushbutton.setCheckable(True)
        self.overlay_toggle_pushbutton.setChecked(False)
        self.overlay_toggle_pushbutton.clicked.connect(self.toggle_overlay_panels)

        self.buffer_label = ViewerButton(style="invisible")
        self.buffer_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.buffer_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.buffer_label.setMouseTracking(True)

        self.label_mdiarea = QtWidgets.QLabel()
        self.label_mdiarea.setText("Drag images directly to create individual image windows\n\n—\n\nCreate sliding overlays to compare images directly over each other\n\n—\n\nRight-click image windows to change settings and add tools")
        self.label_mdiarea.setStyleSheet("""
            QLabel { 
                color: white;
                border: 0.13em dashed gray;
                border-radius: 0.25em;
                background-color: transparent;
                padding: 1em;
                font-size: 10pt;
                } 
            """)
        self.label_mdiarea.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.label_mdiarea.setAlignment(QtCore.Qt.AlignCenter)

        layout_mdiarea_bottomright_vertical = GridLayoutFloatingShadow()
        layout_mdiarea_bottomright_vertical.addWidget(self.fullscreen_pushbutton, 5, 0)
        layout_mdiarea_bottomright_vertical.addWidget(self.tile_default_pushbutton, 4, 0)
        layout_mdiarea_bottomright_vertical.addWidget(self.tile_horizontally_pushbutton, 3, 0)
        layout_mdiarea_bottomright_vertical.addWidget(self.tile_vertically_pushbutton, 2, 0)
        layout_mdiarea_bottomright_vertical.addWidget(self.fit_to_window_pushbutton, 1, 0)
        layout_mdiarea_bottomright_vertical.addWidget(self.info_pushbutton, 0, 0)
        layout_mdiarea_bottomright_vertical.setContentsMargins(0,0,0,16)
        self.interface_mdiarea_bottomright_vertical = QtWidgets.QWidget()
        self.interface_mdiarea_bottomright_vertical.setLayout(layout_mdiarea_bottomright_vertical)
        tracker_interface_mdiarea_bottomright_vertical = EventTrackerSplitBypassInterface(self.interface_mdiarea_bottomright_vertical)
        tracker_interface_mdiarea_bottomright_vertical.mouse_position_changed.connect(self.update_split)

        layout_mdiarea_bottomright_horizontal = GridLayoutFloatingShadow()
        layout_mdiarea_bottomright_horizontal.addWidget(self.buffer_label, 0, 6)
        layout_mdiarea_bottomright_horizontal.addWidget(self.interface_toggle_pushbutton, 0, 5)
        layout_mdiarea_bottomright_horizontal.addWidget(self.overlay_toggle_pushbutton, 0, 4)
        layout_mdiarea_bottomright_horizontal.addWidget(self.close_all_pushbutton, 0, 3)
        layout_mdiarea_bottomright_horizontal.addWidget(self.stopsync_toggle_pushbutton, 0, 2)
        layout_mdiarea_bottomright_horizontal.addWidget(self.save_view_pushbutton, 0, 1)
        layout_mdiarea_bottomright_horizontal.addWidget(self.open_new_pushbutton, 0, 0)
        layout_mdiarea_bottomright_horizontal.setContentsMargins(0,0,0,16)
        self.interface_mdiarea_bottomright_horizontal = QtWidgets.QWidget()
        self.interface_mdiarea_bottomright_horizontal.setLayout(layout_mdiarea_bottomright_horizontal)
        tracker_interface_mdiarea_bottomright_horizontal = EventTrackerSplitBypassInterface(self.interface_mdiarea_bottomright_horizontal)
        tracker_interface_mdiarea_bottomright_horizontal.mouse_position_changed.connect(self.update_split)

        self.loading_grayout_label = QtWidgets.QLabel("Loading...") # Needed to give users feedback when loading views
        self.loading_grayout_label.setWordWrap(True)
        self.loading_grayout_label.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.loading_grayout_label.setVisible(False)
        self.loading_grayout_label.setStyleSheet("""
            QLabel { 
                color: white;
                background-color: rgba(0,0,0,223);
                font-size: 10pt;
                } 
            """)

        self.dragged_grayout_label = QtWidgets.QLabel("Drop to create single view(s)...") # Needed to give users feedback when dragging in images
        self.dragged_grayout_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.dragged_grayout_label.setWordWrap(True)
        self.dragged_grayout_label.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.dragged_grayout_label.setVisible(False)
        self.dragged_grayout_label.setStyleSheet("""
            QLabel { 
                color: white;
                background-color: rgba(63,63,63,223);
                border: 0.13em dashed gray;
                border-radius: 0.25em;
                margin-left: 0.25em;
                margin-top: 0.25em;
                margin-right: 0.25em;
                margin-bottom: 0.25em;
                font-size: 10pt;
                } 
            """)    


        layout_mdiarea = QtWidgets.QGridLayout()
        layout_mdiarea.setContentsMargins(0, 0, 0, 0)
        layout_mdiarea.setSpacing(0)
        layout_mdiarea.addWidget(self._mdiArea, 0, 0)
        layout_mdiarea.addWidget(self.label_mdiarea, 0, 0, QtCore.Qt.AlignCenter)
        layout_mdiarea.addWidget(self.dragged_grayout_label, 0, 0)
        layout_mdiarea.addWidget(self.loading_grayout_label, 0, 0)
        layout_mdiarea.addWidget(self.interface_mdiarea_topleft, 0, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        layout_mdiarea.addWidget(self.interface_mdiarea_bottomleft, 0, 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignLeft)
        layout_mdiarea.addWidget(self.interface_mdiarea_bottomright_horizontal, 0, 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)
        layout_mdiarea.addWidget(self.interface_mdiarea_bottomright_vertical, 0, 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)

        self.mdiarea_plus_buttons = QtWidgets.QWidget()
        self.mdiarea_plus_buttons.setLayout(layout_mdiarea)

        self.setCentralWidget(self.mdiarea_plus_buttons)

        self.subwindow_was_just_closed = False

        self._windowMapper = QtCore.QSignalMapper(self)

        self._actionMapper = QtCore.QSignalMapper(self)
        self._actionMapper.mapped[str].connect(self.mappedImageViewerAction)
        self._recentFileMapper = QtCore.QSignalMapper(self)
        self._recentFileMapper.mapped[str].connect(self.openRecentFile)

        self.createActions()
        self.addAction(self._activateSubWindowSystemMenuAct)

        self.createMenus()
        self.updateMenus()
        self.createStatusBar()

        self.readSettings()
        self.updateStatusBar()

        self.setUnifiedTitleAndToolBarOnMac(True)
        
        self.showNormal()
        self.menuBar().hide()

        self.setStyleSheet("QWidget{font-size: 9pt}")


    # Screenshot window

    def copy_view(self):
        """Screenshot MultiViewMainWindow and copy to clipboard as image."""
        
        self.display_loading_grayout(True, "Screenshot copied to clipboard.")

        interface_was_already_set_hidden = not self.is_interface_showing # Needed to hide the interface temporarily while grabbing a screenshot (makes sure the screenshot only shows the views)
        if not interface_was_already_set_hidden:
            self.show_interface_off()

        # Hide slice controls in all subwindows
        slice_controls_states = {}
        mouse_rect_states = {}
        windows = self._mdiArea.subWindowList()
        for window in windows:
            child = window.widget()
            # 볼륨 데이터의 슬라이스 컨트롤 상태 저장 및 숨김
            if hasattr(child, 'is_volumetric') and child.is_volumetric:
                slice_controls_states[window] = child.z_slice_controls.isVisible()
                child.set_slice_controls_visible(False)
            
            # mouse_rect 및 픽셀값 문자열 상태 저장 및 숨김
            if hasattr(child, 'mouse_rect_scene_main_topleft') and child.mouse_rect_scene_main_topleft:
                mouse_rect_states[window] = {
                    'rect_visible': child.mouse_rect_scene_main_topleft.isVisible(),
                    'text_visible': child.mouse_rect_text.isVisible()
                }
                child.mouse_rect_scene_main_topleft.setVisible(False)
                child.mouse_rect_text.setVisible(False)

        pixmap = self._mdiArea.grab()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setPixmap(pixmap)

        # Restore slice controls visibility
        for window, was_visible in slice_controls_states.items():
            window.widget().set_slice_controls_visible(was_visible)
            
        # Restore mouse_rect and text visibility
        for window, states in mouse_rect_states.items():
            child = window.widget()
            child.mouse_rect_scene_main_topleft.setVisible(states['rect_visible'])
            child.mouse_rect_text.setVisible(states['text_visible'])

        if not interface_was_already_set_hidden:
            self.show_interface_on()

        self.display_loading_grayout(False, pseudo_load_time=1)


    def save_view(self):
        """Screenshot MultiViewMainWindow and open Save dialog to save screenshot as image.""" 

        self.display_loading_grayout(True, "Saving viewer screenshot...")

        folderpath = None

        if self.activeMdiChild:
            folderpath = self.activeMdiChild.currentFile
            folderpath = os.path.dirname(folderpath)
            folderpath = folderpath + "\\"
        else:
            self.display_loading_grayout(False, pseudo_load_time=0)
            return

        interface_was_already_set_hidden = not self.is_interface_showing # Needed to hide the interface temporarily while grabbing a screenshot (makes sure the screenshot only shows the views)
        if not interface_was_already_set_hidden:
            self.show_interface_off()

        # Hide slice controls in all subwindows
        slice_controls_states = {}
        mouse_rect_states = {}
        windows = self._mdiArea.subWindowList()
        for window in windows:
            child = window.widget()
            # 볼륨 데이터의 슬라이스 컨트롤 상태 저장 및 숨김
            if hasattr(child, 'is_volumetric') and child.is_volumetric:
                slice_controls_states[window] = child.z_slice_controls.isVisible()
                child.set_slice_controls_visible(False)
                
            # mouse_rect 및 픽셀값 문자열 상태 저장 및 숨김
            if hasattr(child, 'mouse_rect_scene_main_topleft') and child.mouse_rect_scene_main_topleft:
                mouse_rect_states[window] = {
                    'rect_visible': child.mouse_rect_scene_main_topleft.isVisible(),
                    'text_visible': child.mouse_rect_text.isVisible()
                }
                child.mouse_rect_scene_main_topleft.setVisible(False)
                child.mouse_rect_text.setVisible(False)

        pixmap = self._mdiArea.grab()

        # Restore slice controls visibility
        for window, was_visible in slice_controls_states.items():
            window.widget().set_slice_controls_visible(was_visible)
            
        # Restore mouse_rect and text visibility
        for window, states in mouse_rect_states.items():
            child = window.widget()
            child.mouse_rect_scene_main_topleft.setVisible(states['rect_visible'])
            child.mouse_rect_text.setVisible(states['text_visible'])

        date_and_time = datetime.now().strftime('%Y-%m-%d %H%M%S') # Sets the default filename with date and time 
        filename = "Viewer screenshot " + date_and_time + ".png"
        name_filters = "PNG (*.png);; JPEG (*.jpeg);; TIFF (*.tiff);; JPG (*.jpg);; TIF (*.tif)" # Allows users to select filetype of screenshot

        self.display_loading_grayout(True, "Selecting folder and name for the viewer screenshot...", pseudo_load_time=0)
        
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save a screenshot of the viewer", folderpath+filename, name_filters)
        _, fileextension = os.path.splitext(filepath)
        fileextension = fileextension.replace('.','')
        if filepath:
            pixmap.save(filepath, fileextension)
        
        if not interface_was_already_set_hidden:
            self.show_interface_on()

        self.display_loading_grayout(False)

    
    # Interface and appearance

    def display_loading_grayout(self, boolean, text="Loading...", pseudo_load_time=0.2):
        """Show/hide grayout screen for loading sequences.

        Args:
            boolean (bool): True to show grayout; False to hide.
            text (str): The text to show on the grayout.
            pseudo_load_time (float): The delay (in seconds) to hide the grayout to give users a feeling of action.
        """ 
        if not boolean:
            text = "Loading..."
        self.loading_grayout_label.setText(text)
        self.loading_grayout_label.setVisible(boolean)
        if boolean:
            self.loading_grayout_label.repaint()
        if not boolean:
            time.sleep(pseudo_load_time)

    def display_dragged_grayout(self, boolean):
        """Show/hide grayout screen for drag-and-drop sequences.

        Args:
            boolean (bool): True to show grayout; False to hide.
        """ 
        self.dragged_grayout_label.setVisible(boolean)
        if boolean:
            self.dragged_grayout_label.repaint()

    def on_last_remaining_subwindow_was_closed(self):
        """Show instructions label of MDIArea."""
        self.label_mdiarea.setVisible(True)

    def on_first_subwindow_was_opened(self):
        """Hide instructions label of MDIArea."""
        self.label_mdiarea.setVisible(False)

    def show_interface(self, boolean):
        """Show/hide interface elements for sliding overlay creator and transparencies.

        Args:
            boolean (bool): True to show interface; False to hide.
        """ 
        if boolean:
            self.show_interface_on()
        elif not boolean:
            self.show_interface_off()

    def show_interface_on(self):
        """Show interface elements for sliding overlay creator and transparencies.""" 
        if self.is_interface_showing:
            return
        
        self.is_interface_showing = True
        self.is_quiet_mode = False

        self.update_window_highlight(self._mdiArea.activeSubWindow())
        self.update_window_labels(self._mdiArea.activeSubWindow())
        self.set_window_close_pushbuttons_always_visible(self._mdiArea.activeSubWindow(), True)
        self.set_window_mouse_rect_visible(self._mdiArea.activeSubWindow(), True)
        self.interface_mdiarea_topleft.setVisible(True)
        self.interface_mdiarea_bottomleft.setVisible(True)
        
        # Show z_slice_controls and data_range_controls for all views
        windows = self._mdiArea.subWindowList()
        for window in windows:
            if isinstance(window.widget(), SplitViewMdiChild):
                window.widget().set_z_slice_controls_visible(True)
                window.widget().set_data_range_controls_visible(True)

        self.interface_toggle_pushbutton.setToolTip("Hide interface (studio mode)")

        if self.interface_toggle_pushbutton:
            self.interface_toggle_pushbutton.setChecked(True)

    def show_interface_off(self):
        """Hide interface elements for sliding overlay creator and transparencies.""" 
        if not self.is_interface_showing:
            return

        self.is_interface_showing = False
        self.is_quiet_mode = True

        self.update_window_highlight(self._mdiArea.activeSubWindow())
        self.update_window_labels(self._mdiArea.activeSubWindow())
        self.set_window_close_pushbuttons_always_visible(self._mdiArea.activeSubWindow(), False)
        self.set_window_mouse_rect_visible(self._mdiArea.activeSubWindow(), False)
        self.interface_mdiarea_topleft.setVisible(False)
        self.interface_mdiarea_bottomleft.setVisible(False)
        
        # Hide z_slice_controls and data_range_controls for all views
        windows = self._mdiArea.subWindowList()
        for window in windows:
            if isinstance(window.widget(), SplitViewMdiChild):
                window.widget().set_z_slice_controls_visible(False)
                window.widget().set_data_range_controls_visible(False)

        self.interface_toggle_pushbutton.setToolTip("Show interface (H)")

        if self.interface_toggle_pushbutton:
            self.interface_toggle_pushbutton.setChecked(False)
            self.interface_toggle_pushbutton.setAttribute(QtCore.Qt.WA_UnderMouse, False)

    def toggle_interface(self):
        """Toggle visibilty of interface elements for sliding overlay creator and transparencies.""" 
        if self.is_interface_showing: # If interface is showing, then toggle it off; if not, then toggle it on
            self.show_interface_off()
        else:
            self.show_interface_on()

    def set_stopsync_pushbutton(self, boolean):
        """Set state of synchronous zoom/pan and appearance of corresponding interface button.

        Args:
            boolean (bool): True to enable synchronized zoom/pan; False to disable.
        """ 
        self._synchZoomAct.setChecked(not boolean)
        self._synchPanAct.setChecked(not boolean)
        
        if self._synchZoomAct.isChecked():
            if self.activeMdiChild:
                self.activeMdiChild.fitToWindow()

        if boolean:
            self.stopsync_toggle_pushbutton.setToolTip("Synchronize zoom and pan (currently unsynced)")
        else:
            self.stopsync_toggle_pushbutton.setToolTip("Unsynchronize zoom and pan (currently synced)")

    def toggle_fullscreen(self):
        """Toggle fullscreen state of app."""
        if self.is_fullscreen:
            self.set_fullscreen_off()
        else:
            self.set_fullscreen_on()
    
    def set_fullscreen_on(self):
        """Enable fullscreen of MultiViewMainWindow.
        
        Moves MDIArea to secondary window and makes it fullscreen.
        Shows interim widget in main window.  
        """
        if self.is_fullscreen:
            return

        position_of_window = self.pos()

        centralwidget_to_be_made_fullscreen = self.mdiarea_plus_buttons
        widget_to_replace_central = self.centralwidget_during_fullscreen

        centralwidget_to_be_made_fullscreen.setParent(None)

        # move() is needed when using multiple monitors because when the widget loses its parent, its position moves to the primary screen origin (0,0) instead of retaining the app's screen
        # The solution is to move the widget to the position of the app window and then make the widget fullscreen
        # A timer is needed for showFullScreen() to apply on the app's screen (otherwise the command is made before the widget's move is established)
        centralwidget_to_be_made_fullscreen.move(position_of_window)
        QtCore.QTimer.singleShot(50, centralwidget_to_be_made_fullscreen.showFullScreen)

        self.showMinimized()

        self.setCentralWidget(widget_to_replace_central)
        widget_to_replace_central.show()
        
        self._mdiArea.tile_what_was_done_last_time()
        self._mdiArea.activateWindow()

        self.is_fullscreen = True
        if self.fullscreen_pushbutton:
            self.fullscreen_pushbutton.setChecked(True)

        if self.activeMdiChild:
            self.synchPan(self.activeMdiChild)

    def set_fullscreen_off(self):
        """Disable fullscreen of MultiViewMainWindow.
        
        Removes interim widget in main window. 
        Returns MDIArea to normal (non-fullscreen) view on main window. 
        """
        if not self.is_fullscreen:
            return
        
        self.showNormal()

        fullscreenwidget_to_be_made_central = self.mdiarea_plus_buttons
        centralwidget_to_be_hidden = self.centralwidget_during_fullscreen

        centralwidget_to_be_hidden.setParent(None)
        centralwidget_to_be_hidden.hide()

        self.setCentralWidget(fullscreenwidget_to_be_made_central)

        self._mdiArea.tile_what_was_done_last_time()
        self._mdiArea.activateWindow()

        self.is_fullscreen = False
        if self.fullscreen_pushbutton:
            self.fullscreen_pushbutton.setChecked(False)
            self.fullscreen_pushbutton.setAttribute(QtCore.Qt.WA_UnderMouse, False)

        self.refreshPanDelayed(100)

    def set_fullscreen(self, boolean):
        """Enable/disable fullscreen of MultiViewMainWindow.
        
        Args:
            boolean (bool): True to enable fullscreen; False to disable.
        """
        if boolean:
            self.set_fullscreen_on()
        elif not boolean:
            self.set_fullscreen_off()
    
    def update_window_highlight(self, window):
        """Update highlight of subwindows in MDIArea.

        Input window should be the subwindow which is active.
        All other subwindow(s) will be shown no highlight.
        
        Args:
            window (QMdiSubWindow): The active subwindow to show highlight and indicate as active.
        """
        if window is None:
            return
        changed_window = window
        if self.is_quiet_mode:
            changed_window.widget().frame_hud.setStyleSheet("QFrame {border: 0px solid transparent}")
        elif self.activeMdiChild.split_locked:
            changed_window.widget().frame_hud.setStyleSheet("QFrame {border: 0.2em orange; border-left-style: outset; border-top-style: inset; border-right-style: inset; border-bottom-style: inset}")
        else:
            changed_window.widget().frame_hud.setStyleSheet("QFrame {border: 0.2em blue; border-left-style: outset; border-top-style: inset; border-right-style: inset; border-bottom-style: inset}")

        windows = self._mdiArea.subWindowList()
        for window in windows:
            if window != changed_window:
                window.widget().frame_hud.setStyleSheet("QFrame {border: 0px solid transparent}")

    def update_window_labels(self, window):
        """Update labels of subwindows in MDIArea.

        Input window should be the subwindow which is active.
        All other subwindow(s) will be shown no labels.
        
        Args:
            window (QMdiSubWindow): The active subwindow to show label(s) of image(s) and indicate as active.
        """
        if window is None:
            return
        changed_window = window
        label_visible = True
        if self.is_quiet_mode:
            label_visible = False
        changed_window.widget().label_main_topleft.set_visible_based_on_text(label_visible)
        changed_window.widget().label_topright.set_visible_based_on_text(label_visible)
        changed_window.widget().label_bottomright.set_visible_based_on_text(label_visible)
        changed_window.widget().label_bottomleft.set_visible_based_on_text(label_visible)

        windows = self._mdiArea.subWindowList()
        for window in windows:
            if window != changed_window:
                window.widget().label_main_topleft.set_visible_based_on_text(False)
                window.widget().label_topright.set_visible_based_on_text(False)
                window.widget().label_bottomright.set_visible_based_on_text(False)
                window.widget().label_bottomleft.set_visible_based_on_text(False)

    def set_window_close_pushbuttons_always_visible(self, window, boolean):
        """Enable/disable the always-on visiblilty of the close X on each subwindow.
        
        Args:
            window (QMdiSubWindow): The active subwindow.
            boolean (bool): True to show the close X always; False to hide unless mouse hovers over.
        """
        if window is None:
            return
        changed_window = window
        always_visible = boolean
        changed_window.widget().set_close_pushbutton_always_visible(always_visible)
        windows = self._mdiArea.subWindowList()
        for window in windows:
            if window != changed_window:
                window.widget().set_close_pushbutton_always_visible(always_visible)

    def set_window_mouse_rect_visible(self, window, boolean):
        """Enable/disable the visiblilty of the red 1x1 outline at the pointer
        
        Outline shows the relative size of a pixel in the active subwindow.
        
        Args:
            window (QMdiSubWindow): The active subwindow.
            boolean (bool): True to show 1x1 outline; False to hide.
        """
        if window is None:
            return
        changed_window = window
        visible = boolean
        changed_window.widget().set_mouse_rect_visible(visible)
        windows = self._mdiArea.subWindowList()
        for window in windows:
            if window != changed_window:
                window.widget().set_mouse_rect_visible(visible)

    def auto_tile_subwindows_on_close(self):
        """Tile the subwindows of MDIArea using previously used tile method."""
        if self.subwindow_was_just_closed:
            self.subwindow_was_just_closed = False
            QtCore.QTimer.singleShot(50, self._mdiArea.tile_what_was_done_last_time)
            self.refreshPanDelayed(50)

    def update_mdi_buttons(self, window):
        """Update the interface button 'Split Lock' based on the status of the split (locked/unlocked) in the given window.
        
        Args:
            window (QMdiSubWindow): The active subwindow.
        """
        if window is None:
            self._splitview_manager.lock_split_pushbutton.setChecked(False)
            return
        
        child = self.activeMdiChild

        self._splitview_manager.lock_split_pushbutton.setChecked(child.split_locked)


    def set_single_window_transform_mode_smooth(self, window, boolean):
        """Set the transform mode of a given subwindow.
        
        Args:
            window (QMdiSubWindow): The subwindow.
            boolean (bool): True to smooth (interpolate); False to fast (not interpolate).
        """
        if window is None:
            return
        changed_window = window
        changed_window.widget().set_transform_mode_smooth(boolean)
        

    def set_all_window_transform_mode_smooth(self, boolean):
        """Set the transform mode of all subwindows. 
        
        Args:
            boolean (bool): True to smooth (interpolate); False to fast (not interpolate).
        """
        if self._mdiArea.activeSubWindow() is None:
            return
        windows = self._mdiArea.subWindowList()
        for window in windows:
            window.widget().set_transform_mode_smooth(boolean)

    def set_all_background_color(self, color):
        """Set the background color of all subwindows. 
        
        Args:
            color (list): Descriptor string and RGB int values. Example: ["White", 255, 255, 255].
        """
        if self._mdiArea.activeSubWindow() is None:
            return
        windows = self._mdiArea.subWindowList()
        for window in windows:
            window.widget().set_scene_background_color(color)
        self.scene_background_color = color

    def set_all_sync_zoom_by(self, by: str):
        """[str] Set the method by which to sync zoom all windows."""
        if self._mdiArea.activeSubWindow() is None:
            return
        windows = self._mdiArea.subWindowList()
        for window in windows:
            window.widget().update_sync_zoom_by(by)
        self.sync_zoom_by = by
        self.refreshZoom()

    def info_button_clicked(self):
        """Trigger when info button is clicked."""
        self.show_about()
        return
    
    def show_about(self):
        """Show about box."""
        sp = "<br>"
        title = "Butterfly Viewer for Volumetric Images"
        text = "Butterfly Viewer for Volumetric Images"
        text = text + sp + "Taehong Kim"
        text = text + sp + "Version: " + VERSION
        text = text + sp + "Source: <a href='https://github.com/mirsoftwre/butterfly_viewer_for_tomogram'>github.com/mirsoftwre/butterfly_viewer_for_tomogram</a>"
        text = text + sp + "License: <a href='https://www.gnu.org/licenses/gpl-3.0.en.html'>GNU GPL v3</a> or later"
        text = text + sp
        text = text + sp + "Original Software: Butterfly Viewer"
        text = text + sp + "Original Author: Lars Maxfield"
        text = text + sp + "Based on version: 1.1"
        text = text + sp + "Source: <a href='https://github.com/olive-groves/butterfly_viewer'>github.com/olive-groves/butterfly_viewer</a>"
        text = text + sp + "Tutorial: <a href='https://olive-groves.github.io/butterfly_viewer'>olive-groves.github.io/butterfly_viewer</a>"
        box = QtWidgets.QMessageBox.about(self, title, text)

    # View loading methods

    def loadFile(self, filename_main_topleft, filename_topright=None, filename_bottomleft=None, filename_bottomright=None):
        """Load an individual image or sliding overlay into new subwindow.

        Args:
            filename_main_topleft (str): The image filepath of the main image to be viewed; the basis of the sliding overlay (main; topleft)
            filename_topright (str): The image filepath for top-right of the sliding overlay (set None to exclude)
            filename_bottomleft (str): The image filepath for bottom-left of the sliding overlay (set None to exclude)
            filename_bottomright (str): The image filepath for bottom-right of the sliding overlay (set None to exclude)
        """
        
        self.display_loading_grayout(True, "Loading viewer with main image '" + filename_main_topleft.split("/")[-1] + "'...")

        activeMdiChild = self.activeMdiChild
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)

        transform_mode_smooth = self.is_global_transform_mode_smooth
        
        # Save the directory to registry for future use
        settings = QtCore.QSettings(COMPANY, APPNAME)
        dir_path = os.path.dirname(filename_main_topleft)
        settings.setValue(SETTING_LAST_DIRECTORY, dir_path)
        
        # Check if the file is a volumetric image
        try:
            # Import locally to avoid circular imports
            from aux_volumetric import VolumetricImageHandler
            is_volumetric = VolumetricImageHandler.is_volumetric_file(filename_main_topleft)
            
            if is_volumetric:
                # Handle volumetric image - load the middle slice
                try:
                    volumetric_handler = VolumetricImageHandler(filename_main_topleft)
                    center_slice_index = volumetric_handler.get_center_slice_index()
                    pixmap = volumetric_handler.get_slice_pixmap(center_slice_index)
                    
                    if pixmap is None:
                        raise ValueError("Failed to load middle slice of volumetric image")
                        
                    # For volumetric images, we don't support overlays
                    pixmap_topright = None
                    pixmap_bottomleft = None
                    pixmap_bottomright = None
                    
                    QtWidgets.QApplication.restoreOverrideCursor()
                    
                    child = self.createMdiChild(pixmap, filename_main_topleft, pixmap_topright, pixmap_bottomleft, pixmap_bottomright, transform_mode_smooth)
                    
                    # Setup volumetric mode in the child
                    child.setup_volumetric_mode(volumetric_handler, center_slice_index)
                    
                    # Connect slice changed signal to update the label
                    child.slice_changed.connect(lambda slice_idx: 
                        child.label_main_topleft.setText(f"{filename_main_topleft} (Volumetric - Slice {slice_idx+1}/{volumetric_handler.total_slices})"))
                    
                    # Show filename with indication it's a volumetric image
                    child.label_main_topleft.setText(f"{filename_main_topleft} (Volumetric - Slice {center_slice_index+1}/{volumetric_handler.total_slices})")
                    child.label_topright.setText("")
                    child.label_bottomright.setText("")
                    child.label_bottomleft.setText("")
                    
                    child.show()
                    
                    if activeMdiChild:
                        if self._synchPanAct.isChecked():
                            self.synchPan(activeMdiChild)
                        if self._synchZoomAct.isChecked():
                            self.synchZoom(activeMdiChild)
                            
                    self._mdiArea.tile_what_was_done_last_time()
                    
                    child.set_close_pushbutton_always_visible(self.is_interface_showing)
                    if self.scene_background_color is not None:
                        child.set_scene_background_color(self.scene_background_color)
                    
                    self.updateRecentFileSettings(filename_main_topleft)
                    self.updateRecentFileActions()
                    
                    self._last_accessed_fullpath = filename_main_topleft
                    
                    self.display_loading_grayout(False)
                    
                    sync_by = self.sync_zoom_by
                    child.update_sync_zoom_by(sync_by)
                    
                    child.fitToWindow()
                    
                    self.statusBar().showMessage("Volumetric file loaded - showing center slice. Use slider to navigate through slices.", 4000)
                    return
                    
                except Exception as e:
                    QtWidgets.QApplication.restoreOverrideCursor()
                    self.display_loading_grayout(True, "Waiting on dialog box...")
                    QtWidgets.QMessageBox.warning(self, APPNAME,
                                             f"Error loading volumetric image: {str(e)}")
                    self.display_loading_grayout(False)
                    return
        except ImportError:
            # If aux_volumetric can't be imported, continue with normal image loading
            pass
                
        # Handle regular 2D image - use existing code
        pixmap = QtGui.QPixmap(filename_main_topleft)
        pixmap_topright = QtGui.QPixmap(filename_topright) if filename_topright else None
        pixmap_bottomleft = QtGui.QPixmap(filename_bottomleft) if filename_bottomleft else None
        pixmap_bottomright = QtGui.QPixmap(filename_bottomright) if filename_bottomright else None
        
        QtWidgets.QApplication.restoreOverrideCursor()
        
        if (not pixmap or
            pixmap.width()==0 or pixmap.height==0):
            self.display_loading_grayout(True, "Waiting on dialog box...")
            QtWidgets.QMessageBox.warning(self, APPNAME,
                                      "Cannot read file %s." % (filename_main_topleft,))
            self.updateRecentFileSettings(filename_main_topleft, delete=True)
            self.updateRecentFileActions()
            self.display_loading_grayout(False)
            return
        
        angle = get_exif_rotation_angle(filename_main_topleft)
        if angle:
            pixmap = pixmap.transformed(QtGui.QTransform().rotate(angle))
        
        if filename_topright:
            angle = get_exif_rotation_angle(filename_topright)
            if angle:
                pixmap_topright = pixmap_topright.transformed(QtGui.QTransform().rotate(angle))
        
        if filename_bottomright:
            angle = get_exif_rotation_angle(filename_bottomright)
            if angle:
                pixmap_bottomright = pixmap_bottomright.transformed(QtGui.QTransform().rotate(angle))
        
        if filename_bottomleft:
            angle = get_exif_rotation_angle(filename_bottomleft)
            if angle:
                pixmap_bottomleft = pixmap_bottomleft.transformed(QtGui.QTransform().rotate(angle))
        
        child = self.createMdiChild(pixmap, filename_main_topleft, pixmap_topright, pixmap_bottomleft, pixmap_bottomright, transform_mode_smooth)
        
        # Show filenames
        child.label_main_topleft.setText(filename_main_topleft)
        child.label_topright.setText(filename_topright)
        child.label_bottomright.setText(filename_bottomright)
        child.label_bottomleft.setText(filename_bottomleft)
        
        child.show()
        
        if activeMdiChild:
            if self._synchPanAct.isChecked():
                self.synchPan(activeMdiChild)
            if self._synchZoomAct.isChecked():
                self.synchZoom(activeMdiChild)
                
        self._mdiArea.tile_what_was_done_last_time()
        
        child.set_close_pushbutton_always_visible(self.is_interface_showing)
        if self.scene_background_color is not None:
            child.set_scene_background_color(self.scene_background_color)
        
        self.updateRecentFileSettings(filename_main_topleft)
        self.updateRecentFileActions()
        
        self._last_accessed_fullpath = filename_main_topleft
        
        self.display_loading_grayout(False)
        
        sync_by = self.sync_zoom_by
        child.update_sync_zoom_by(sync_by)
        
        child.fitToWindow()
        
        self.statusBar().showMessage("File loaded", 2000)

    def load_from_dragged_and_dropped_file(self, filename_main_topleft):
        """Load an individual image (convenience function — e.g., from a single emitted single filename)."""
        self.loadFile(filename_main_topleft)
    
    def createMdiChild(self, pixmap, filename_main_topleft, pixmap_topright, pixmap_bottomleft, pixmap_bottomright, transform_mode_smooth):
        """Create new viewing widget for an individual image or sliding overlay to be placed in a new subwindow.

        Args:
            pixmap (QPixmap): The main image to be viewed; the basis of the sliding overlay (main; topleft)
            filename_main_topleft (str): The image filepath of the main image.
            pixmap_topright (QPixmap): The top-right image of the sliding overlay (set None to exclude).
            pixmap_bottomleft (QPixmap): The bottom-left image of the sliding overlay (set None to exclude).
            pixmap_bottomright (QPixmap): The bottom-right image of the sliding overlay (set None to exclude).

        Returns:
            child (SplitViewMdiChild): The viewing widget instance.
        """
        
        child = SplitViewMdiChild(pixmap,
                         filename_main_topleft,
                         "Window %d" % (len(self._mdiArea.subWindowList())+1),
                         pixmap_topright, pixmap_bottomleft, pixmap_bottomright, 
                         transform_mode_smooth)

        child.enableScrollBars(self._showScrollbarsAct.isChecked())

        child.sync_this_zoom = True
        child.sync_this_pan = True
        
        self._mdiArea.addSubWindow(child, QtCore.Qt.FramelessWindowHint) # LVM: No frame, starts fitted

        child.scrollChanged.connect(self.panChanged)
        child.transformChanged.connect(self.zoomChanged)
        
        child.positionChanged.connect(self.on_positionChanged)
        child.tracker.mouse_leaved.connect(self.on_mouse_leaved)
        
        child.scrollChanged.connect(self.on_scrollChanged)

        child.became_closed.connect(self.on_subwindow_closed)
        child.was_clicked_close_pushbutton.connect(self._mdiArea.closeActiveSubWindow)
        child.shortcut_shift_x_was_activated.connect(self.shortcut_shift_x_was_activated_on_mdichild)
        child.signal_display_loading_grayout.connect(self.display_loading_grayout)
        child.was_set_global_transform_mode.connect(self.set_all_window_transform_mode_smooth)
        child.was_set_scene_background_color.connect(self.set_all_background_color)
        child.was_set_sync_zoom_by.connect(self.set_all_sync_zoom_by)
        child.display_range_changed.connect(lambda min_val, max_val: self.synchDisplayRange(child, min_val, max_val))

        return child


    # View and split methods

    @QtCore.pyqtSlot()
    def on_create_splitview(self):
        """Load a sliding overlay using the filepaths of the current images in the sliding overlay creator."""
        # Get filenames
        file_path_main_topleft = self._splitview_creator.drag_drop_area.app_main_topleft.file_path
        file_path_topright = self._splitview_creator.drag_drop_area.app_topright.file_path
        file_path_bottomleft = self._splitview_creator.drag_drop_area.app_bottomleft.file_path
        file_path_bottomright = self._splitview_creator.drag_drop_area.app_bottomright.file_path

        # loadFile with those filenames
        self.loadFile(file_path_main_topleft, file_path_topright, file_path_bottomleft, file_path_bottomright)

    def fit_to_window(self):
        """Fit the view of the active subwindow (if it exists)."""
        if self.activeMdiChild:
            self.activeMdiChild.fitToWindow()

    def update_split(self):
        """Update the position of the split of the active subwindow (if it exists) relying on the global mouse coordinates."""
        if self.activeMdiChild:
            self.activeMdiChild.update_split() # No input = Rely on global mouse position calculation

    def lock_split(self):
        """Lock the position of the overlay split of active subwindow and set relevant interface elements."""
        if self.activeMdiChild:
            self.activeMdiChild.split_locked = True
        self._splitview_manager.lock_split_pushbutton.setChecked(True)
        self.update_window_highlight(self._mdiArea.activeSubWindow())

    def unlock_split(self):
        """Unlock the position of the overlay split of active subwindow and set relevant interface elements."""
        if self.activeMdiChild:
            self.activeMdiChild.split_locked = False
        self._splitview_manager.lock_split_pushbutton.setChecked(False)
        self.update_window_highlight(self._mdiArea.activeSubWindow())

    def set_split(self, x_percent=0.5, y_percent=0.5, apply_to_all=True, ignore_lock=False, percent_of_visible=False):
        """Set the position of the split of the active subwindow as percent of base image's resolution.
        
        Args:
            x_percent (float): The position of the split as a proportion (0-1) of the base image's horizontal resolution.
            y_percent (float): The position of the split as a proportion (0-1) of the base image's vertical resolution.
            apply_to_all (bool): True to set all subwindow splits; False to set only the active subwindow.
            ignore_lock (bool): True to ignore the lock status of the split; False to adhere.
            percent_of_visible (bool): True to set split as proportion of visible area; False as proportion of the full image resolution.
        """
        if self.activeMdiChild:
            self.activeMdiChild.set_split(x_percent, y_percent, ignore_lock=ignore_lock, percent_of_visible=percent_of_visible)
        if apply_to_all:
            windows = self._mdiArea.subWindowList()
            for window in windows:
                window.widget().set_split(x_percent, y_percent, ignore_lock=ignore_lock, percent_of_visible=percent_of_visible)
        self.update_window_highlight(self._mdiArea.activeSubWindow())

    def set_split_from_slider(self):
        """Set the position of the split of the active subwindow to the center of the visible area of the sliding overlay (convenience function)."""
        self.set_split(x_percent=0.5, y_percent=0.5, apply_to_all=False, ignore_lock=False, percent_of_visible=True)
    
    def set_split_from_manager(self, x_percent, y_percent):
        """Set the position of the split of the active subwindow as percent of base image's resolution (convenience function).
        
        Args:
            x_percent (float): The position of the split as a proportion of the base image's horizontal resolution (0-1).
            y_percent (float): The position of the split as a proportion of the base image's vertical resolution (0-1).
        """
        self.set_split(x_percent, y_percent, apply_to_all=False, ignore_lock=False)

    def set_and_lock_split_from_manager(self, x_percent, y_percent):
        """Set and lock the position of the split of the active subwindow as percent of base image's resolution (convenience function).
        
        Args:
            x_percent (float): The position of the split as a proportion of the base image's horizontal resolution (0-1).
            y_percent (float): The position of the split as a proportion of the base image's vertical resolution (0-1).
        """
        self.set_split(x_percent, y_percent, apply_to_all=False, ignore_lock=True)
        self.lock_split()

    def shortcut_shift_x_was_activated_on_mdichild(self):
        """Update interface button for split lock based on lock status of active subwindow."""
        self._splitview_manager.lock_split_pushbutton.setChecked(self.activeMdiChild.split_locked)

    @QtCore.pyqtSlot()
    def on_scrollChanged(self):
        """Refresh position of split of all subwindows based on their respective last position."""
        windows = self._mdiArea.subWindowList()
        for window in windows:
            window.widget().refresh_split_based_on_last_updated_point_of_split_on_scene_main()

    def on_subwindow_closed(self):
        """Record that a subwindow was closed upon the closing of a subwindow."""
        self.subwindow_was_just_closed = True
    
    @QtCore.pyqtSlot()
    def on_mouse_leaved(self):
        """Update displayed coordinates of mouse as N/A upon the mouse leaving the subwindow area."""
        self._label_mouse.setText("View pixel coordinates: ( N/A , N/A )")
        self._label_mouse.adjustSize()
        
    @QtCore.pyqtSlot(QtCore.QPoint)
    def on_positionChanged(self, pos):
        """Update displayed coordinates of mouse on the active subwindow using global coordinates."""
    
        point_of_mouse_on_viewport = QtCore.QPointF(pos.x(), pos.y())
        pos_qcursor_global = QtGui.QCursor.pos()
        
        if self.activeMdiChild:
        
            # Use mouse position to grab scene coordinates (activeMdiChild?)
            active_view = self.activeMdiChild._view_main_topleft
            # convert to int
            mapX = int(point_of_mouse_on_viewport.x());
            mapY = int(point_of_mouse_on_viewport.y());
            point_of_mouse_on_scene = active_view.mapToScene(mapX, mapY)

            if not self._label_mouse.isVisible():
                self._label_mouse.show()
            self._label_mouse.setText("View pixel coordinates: ( x = %d , y = %d )" % (point_of_mouse_on_scene.x(), point_of_mouse_on_scene.y()))
            
            pos_qcursor_view = active_view.mapFromGlobal(pos_qcursor_global)
            pos_qcursor_scene = active_view.mapToScene(pos_qcursor_view)
            
            # 모든 자식 창에 현재 scene 좌표를 전달하여 동일한 위치에 mouse_rect 표시
            scene_x = point_of_mouse_on_scene.x()
            scene_y = point_of_mouse_on_scene.y()
            
            # 활성 창에서 픽셀 값 가져오기
            pixel_value = "N/A"
            
            # 볼륨 데이터인 경우 원본 데이터 값을 가져옴
            if hasattr(self.activeMdiChild, 'is_volumetric') and self.activeMdiChild.is_volumetric:
                volumetric_handler = self.activeMdiChild.volumetric_handler
                if volumetric_handler:
                    int_scene_x = int(scene_x)
                    int_scene_y = int(scene_y)
                    current_slice = self.activeMdiChild.current_slice
                    
                    # 볼륨 이미지에서 원본 데이터 값 가져오기
                    try:
                        from PIL import Image
                        import numpy as np
                        
                        # 이미지 파일 열기
                        with Image.open(volumetric_handler.filepath) as img:
                            img.seek(current_slice)  # 현재 슬라이스로 이동
                            
                            # 이미지 범위 확인
                            if 0 <= int_scene_x < img.width and 0 <= int_scene_y < img.height:
                                # 이미지를 배열로 변환
                                img_array = np.array(img)
                                
                                # 픽셀 값 가져오기
                                if img.mode == 'L':  # 8비트 그레이스케일
                                    pixel_value = f"{img_array[int_scene_y, int_scene_x]}"
                                elif img.mode == 'I':  # 32비트 정수
                                    pixel_value = f"{img_array[int_scene_y, int_scene_x]}"
                                elif img.mode == 'F':  # 32비트 실수
                                    value = img_array[int_scene_y, int_scene_x]
                                    pixel_value = f"{value:.3f}"
                                else:
                                    # RGB, RGBA 등 다른 이미지 모드 처리
                                    if img.mode == 'RGB':
                                        r, g, b = img_array[int_scene_y, int_scene_x]
                                        pixel_value = f"({r}, {g}, {b})"
                                    elif img.mode == 'RGBA':
                                        r, g, b, a = img_array[int_scene_y, int_scene_x]
                                        pixel_value = f"({r}, {g}, {b}, {a})"
                                    else:
                                        pixel_value = f"{img_array[int_scene_y, int_scene_x]}"
                    except Exception as e:
                        pixel_value = f"Error: {str(e)}"
            else:
                # 볼륨 데이터가 아닌 경우 기존 처리 방식 사용
                active_pixmap = self.activeMdiChild._pixmapItem_main_topleft.pixmap()
                if not active_pixmap.isNull() and 0 <= int(scene_x) < active_pixmap.width() and 0 <= int(scene_y) < active_pixmap.height():
                    image = active_pixmap.toImage()
                    pixel = image.pixel(int(scene_x), int(scene_y))
                    color = QtGui.QColor(pixel)
                    if active_pixmap.depth() <= 8:  # 그레이스케일 이미지
                        pixel_value = f"{color.red()}"  # 그레이스케일은 RGB 값이 모두 동일
                    else:  # 컬러 이미지
                        pixel_value = f"({color.red()}, {color.green()}, {color.blue()})"
            
            # 모든 MDI 자식 창에 좌표 전달
            windows = self._mdiArea.subWindowList()
            for window in windows:
                child = window.widget()
                child_view = child._view_main_topleft
                
                # scene 좌표를 각 뷰의 view 좌표로 변환하여 해당 위치에 표시
                child_view_point = child_view.mapFromScene(scene_x, scene_y)
                
                # 뷰의 경계 내에 있는지 확인
                if (0 <= child_view_point.x() < child_view.width() and 
                    0 <= child_view_point.y() < child_view.height()):
                    
                    # mouse_rect 위치 계산 및 설정
                    mouse_rect_pos_origin_x = math.floor(scene_x - child.mouse_rect_width + 1)
                    mouse_rect_pos_origin_y = math.floor(scene_y - child.mouse_rect_height + 1)
                    child.mouse_rect_scene_main_topleft.setPos(mouse_rect_pos_origin_x, mouse_rect_pos_origin_y)
                    
                    # 동일한 픽셀 값으로 텍스트 설정 (활성 창의 픽셀 값 사용)
                    child.mouse_rect_text.setPlainText(f"({int(scene_x)}, {int(scene_y)}): {pixel_value}")
                    child.mouse_rect_text.setPos(mouse_rect_pos_origin_x, mouse_rect_pos_origin_y + child.mouse_rect_height + 1)
            
        else:
            
            self._label_mouse.setText("View pixel coordinates: ( N/A , N/A )")
            
        self._label_mouse.adjustSize()

    
    # Transparency methods


    @QtCore.pyqtSlot(int)
    def on_slider_opacity_base_changed(self, value):
        """Set transparency of base of sliding overlay of active subwindow.
        
        Triggered upon change in interface transparency slider.
        Temporarily sets position of split to the center of the visible area to give user a preview of the transparency effect.

        Args:
            value (float,int): The transparency as percent opacity, where 100 is opaque (not transparent) and 0 is transparent (0-100).
        """
        if not self.activeMdiChild:
            return
        if not self.activeMdiChild.split_locked:
            self.set_split_from_slider()
        self.activeMdiChild.set_opacity_base(value)

    @QtCore.pyqtSlot(int)
    def on_slider_opacity_topright_changed(self, value):
        """Set transparency of top-right of sliding overlay of active subwindow.
        
        Triggered upon change in interface transparency slider.
        Temporarily sets position of split to the center of the visible area to give user a preview of the transparency effect.

        Args:
            value (float,int): The transparency as percent opacity, where 100 is opaque (not transparent) and 0 is transparent (0-100).
        """
        if not self.activeMdiChild:
            return
        if not self.activeMdiChild.split_locked:
            self.set_split_from_slider()
        self.activeMdiChild.set_opacity_topright(value)

    @QtCore.pyqtSlot(int)
    def on_slider_opacity_bottomright_changed(self, value):
        """Set transparency of bottom-right of sliding overlay of active subwindow.
        
        Triggered upon change in interface transparency slider.
        Temporarily sets position of split to the center of the visible area to give user a preview of the transparency effect.

        Args:
            value (float,int): The transparency as percent opacity, where 100 is opaque (not transparent) and 0 is transparent (0-100).
        """
        if not self.activeMdiChild:
            return
        if not self.activeMdiChild.split_locked:
            self.set_split_from_slider()    
        self.activeMdiChild.set_opacity_bottomright(value)

    @QtCore.pyqtSlot(int)
    def on_slider_opacity_bottomleft_changed(self, value):
        """Set transparency of bottom-left of sliding overlay of active subwindow.
        
        Triggered upon change in interface transparency slider.
        Temporarily sets position of split to the center of the visible area to give user a preview of the transparency effect.

        Args:
            value (float,int): The transparency as percent opacity, where 100 is opaque (not transparent) and 0 is transparent (0-100).
        """
        if not self.activeMdiChild:
            return
        if not self.activeMdiChild.split_locked:
            self.set_split_from_slider()
        self.activeMdiChild.set_opacity_bottomleft(value)

    def update_sliders(self, window):
        """Update interface transparency sliders upon subwindow activating using the subwindow transparency values.
        
        Args:
            window (QMdiSubWindow): The active subwindow.
        """
        if window is None:
            self._sliders_opacity_splitviews.reset_sliders()
            return

        child = self.activeMdiChild
        
        self._sliders_opacity_splitviews.set_enabled(True, child.pixmap_topright_exists, child.pixmap_bottomright_exists, child.pixmap_bottomleft_exists)

        opacity_base_of_activeMdiChild = child._opacity_base
        opacity_topright_of_activeMdiChild = child._opacity_topright
        opacity_bottomright_of_activeMdiChild = child._opacity_bottomright
        opacity_bottomleft_of_activeMdiChild = child._opacity_bottomleft

        self._sliders_opacity_splitviews.update_sliders(opacity_base_of_activeMdiChild, opacity_topright_of_activeMdiChild, opacity_bottomright_of_activeMdiChild, opacity_bottomleft_of_activeMdiChild)


    # [Legacy methods from derived MDI Image Viewer]

    def createMappedAction(self, icon, text, parent, shortcut, methodName):
        """Create |QAction| that is mapped via methodName to call.

        :param icon: icon associated with |QAction|
        :type icon: |QIcon| or None
        :param str text: the |QAction| descriptive text
        :param QObject parent: the parent |QObject|
        :param QKeySequence shortcut: the shortcut |QKeySequence|
        :param str methodName: name of method to call when |QAction| is
                               triggered
        :rtype: |QAction|"""

        if icon is not None:
            action = QtWidgets.QAction(icon, text, parent,
                                   shortcut=shortcut,
                                   triggered=self._actionMapper.map)
        else:
            action = QtWidgets.QAction(text, parent,
                                   shortcut=shortcut,
                                   triggered=self._actionMapper.map)
        self._actionMapper.setMapping(action, methodName)
        return action

    def createActions(self):
        """Create actions used in menus."""
        #File menu actions
        self._openAct = QtWidgets.QAction(
            "&Open...", self,
            shortcut=QtGui.QKeySequence.Open,
            statusTip="Open an existing file",
            triggered=self.open)

        self._switchLayoutDirectionAct = QtWidgets.QAction(
            "Switch &layout direction", self,
            triggered=self.switchLayoutDirection)

        #create dummy recent file actions
        for i in range(MultiViewMainWindow.MaxRecentFiles):
            self._recentFileActions.append(
                QtWidgets.QAction(self, visible=False,
                              triggered=self._recentFileMapper.map))

        self._exitAct = QtWidgets.QAction(
            "E&xit", self,
            shortcut=QtGui.QKeySequence.Quit,
            statusTip="Exit the application",
            triggered=QtWidgets.QApplication.closeAllWindows)

        #View menu actions
        self._showScrollbarsAct = QtWidgets.QAction(
            "&Scrollbars", self,
            checkable=True,
            statusTip="Toggle display of subwindow scrollbars",
            triggered=self.toggleScrollbars)

        self._showStatusbarAct = QtWidgets.QAction(
            "S&tatusbar", self,
            checkable=True,
            statusTip="Toggle display of statusbar",
            triggered=self.toggleStatusbar)

        self._synchZoomAct = QtWidgets.QAction(
            "Synch &Zoom", self,
            checkable=True,
            statusTip="Synch zooming of subwindows",
            triggered=self.toggleSynchZoom)

        self._synchPanAct = QtWidgets.QAction(
            "Synch &Pan", self,
            checkable=True,
            statusTip="Synch panning of subwindows",
            triggered=self.toggleSynchPan)

        #Scroll menu actions
        self._scrollActions = [
            self.createMappedAction(
                None,
                "&Top", self,
                QtGui.QKeySequence.MoveToStartOfDocument,
                "scrollToTop"),

            self.createMappedAction(
                None,
                "&Bottom", self,
                QtGui.QKeySequence.MoveToEndOfDocument,
                "scrollToBottom"),

            self.createMappedAction(
                None,
                "&Left Edge", self,
                QtGui.QKeySequence.MoveToStartOfLine,
                "scrollToBegin"),

            self.createMappedAction(
                None,
                "&Right Edge", self,
                QtGui.QKeySequence.MoveToEndOfLine,
                "scrollToEnd"),

            self.createMappedAction(
                None,
                "&Center", self,
                "5",
                "centerView"),
            ]

        #zoom menu actions
        separatorAct = QtWidgets.QAction(self)
        separatorAct.setSeparator(True)

        self._zoomActions = [
            self.createMappedAction(
                None,
                "Zoo&m In (25%)", self,
                QtGui.QKeySequence.ZoomIn,
                "zoomIn"),

            self.createMappedAction(
                None,
                "Zoom &Out (25%)", self,
                QtGui.QKeySequence.ZoomOut,
                "zoomOut"),

            #self.createMappedAction(
                #None,
                #"&Zoom To...", self,
                #"Z",
                #"zoomTo"),

            separatorAct,

            self.createMappedAction(
                None,
                "Actual &Size", self,
                "/",
                "actualSize"),

            self.createMappedAction(
                None,
                "Fit &Image", self,
                "*",
                "fitToWindow"),

            self.createMappedAction(
                None,
                "Fit &Width", self,
                "Alt+Right",
                "fitWidth"),

            self.createMappedAction(
                None,
                "Fit &Height", self,
                "Alt+Down",
                "fitHeight"),
           ]

        #Window menu actions
        self._activateSubWindowSystemMenuAct = QtWidgets.QAction(
            "Activate &System Menu", self,
            shortcut="Ctrl+ ",
            statusTip="Activate subwindow System Menu",
            triggered=self.activateSubwindowSystemMenu)

        self._closeAct = QtWidgets.QAction(
            "Cl&ose", self,
            shortcut=QtGui.QKeySequence.Close,
            shortcutContext=QtCore.Qt.WidgetShortcut,
            #shortcut="Ctrl+Alt+F4",
            statusTip="Close the active window",
            triggered=self._mdiArea.closeActiveSubWindow)

        self._closeAllAct = QtWidgets.QAction(
            "Close &All", self,
            statusTip="Close all the windows",
            triggered=self._mdiArea.closeAllSubWindows)

        self._tileAct = QtWidgets.QAction(
            "&Tile", self,
            statusTip="Tile the windows",
            triggered=self._mdiArea.tileSubWindows)

        self._tileAct.triggered.connect(self.tile_and_fit_mdiArea)

        self._cascadeAct = QtWidgets.QAction(
            "&Cascade", self,
            statusTip="Cascade the windows",
            triggered=self._mdiArea.cascadeSubWindows)

        self._nextAct = QtWidgets.QAction(
            "Ne&xt", self,
            shortcut=QtGui.QKeySequence.NextChild,
            statusTip="Move the focus to the next window",
            triggered=self._mdiArea.activateNextSubWindow)

        self._previousAct = QtWidgets.QAction(
            "Pre&vious", self,
            shortcut=QtGui.QKeySequence.PreviousChild,
            statusTip="Move the focus to the previous window",
            triggered=self._mdiArea.activatePreviousSubWindow)

        self._separatorAct = QtWidgets.QAction(self)
        self._separatorAct.setSeparator(True)

        self._aboutAct = QtWidgets.QAction(
            "&About", self,
            statusTip="Show the application's About box",
            triggered=self.about)

        self._aboutQtAct = QtWidgets.QAction(
            "About &Qt", self,
            statusTip="Show the Qt library's About box",
            triggered=QtWidgets.QApplication.aboutQt)

    def createMenus(self):
        """Create menus."""
        self._fileMenu = self.menuBar().addMenu("&File")
        self._fileMenu.addAction(self._openAct)
        self._fileMenu.addAction(self._switchLayoutDirectionAct)

        self._fileSeparatorAct = self._fileMenu.addSeparator()
        for action in self._recentFileActions:
            self._fileMenu.addAction(action)
        self.updateRecentFileActions()
        self._fileMenu.addSeparator()
        self._fileMenu.addAction(self._exitAct)

        self._viewMenu = self.menuBar().addMenu("&View")
        self._viewMenu.addAction(self._showScrollbarsAct)
        self._viewMenu.addAction(self._showStatusbarAct)
        self._viewMenu.addSeparator()
        self._viewMenu.addAction(self._synchZoomAct)
        self._viewMenu.addAction(self._synchPanAct)

        self._scrollMenu = self.menuBar().addMenu("&Scroll")
        [self._scrollMenu.addAction(action) for action in self._scrollActions]

        self._zoomMenu = self.menuBar().addMenu("&Zoom")
        [self._zoomMenu.addAction(action) for action in self._zoomActions]

        self._windowMenu = self.menuBar().addMenu("&Window")
        self.updateWindowMenu()
        self._windowMenu.aboutToShow.connect(self.updateWindowMenu)

        self.menuBar().addSeparator()

        self._helpMenu = self.menuBar().addMenu("&Help")
        self._helpMenu.addAction(self._aboutAct)
        self._helpMenu.addAction(self._aboutQtAct)

    def updateMenus(self):
        """Update menus."""
        hasMdiChild = (self.activeMdiChild is not None)

        self._scrollMenu.setEnabled(hasMdiChild)
        self._zoomMenu.setEnabled(hasMdiChild)

        self._closeAct.setEnabled(hasMdiChild)
        self._closeAllAct.setEnabled(hasMdiChild)

        self._tileAct.setEnabled(hasMdiChild)
        self._cascadeAct.setEnabled(hasMdiChild)
        self._nextAct.setEnabled(hasMdiChild)
        self._previousAct.setEnabled(hasMdiChild)
        self._separatorAct.setVisible(hasMdiChild)

    def updateRecentFileActions(self):
        """Update recent file menu items."""
        settings = QtCore.QSettings()
        files = settings.value(SETTING_RECENTFILELIST)
        numRecentFiles = min(len(files) if files else 0,
                             MultiViewMainWindow.MaxRecentFiles)

        for i in range(numRecentFiles):
            text = "&%d %s" % (i + 1, strippedName(files[i]))
            self._recentFileActions[i].setText(text)
            self._recentFileActions[i].setData(files[i])
            self._recentFileActions[i].setVisible(True)
            self._recentFileMapper.setMapping(self._recentFileActions[i],
                                              files[i])

        for j in range(numRecentFiles, MultiViewMainWindow.MaxRecentFiles):
            self._recentFileActions[j].setVisible(False)

        self._fileSeparatorAct.setVisible((numRecentFiles > 0))

    def updateWindowMenu(self):
        """Update the Window menu."""
        self._windowMenu.clear()
        self._windowMenu.addAction(self._closeAct)
        self._windowMenu.addAction(self._closeAllAct)
        self._windowMenu.addSeparator()
        self._windowMenu.addAction(self._tileAct)
        self._windowMenu.addAction(self._cascadeAct)
        self._windowMenu.addSeparator()
        self._windowMenu.addAction(self._nextAct)
        self._windowMenu.addAction(self._previousAct)
        self._windowMenu.addAction(self._separatorAct)

        windows = self._mdiArea.subWindowList()
        self._separatorAct.setVisible(len(windows) != 0)

        for i, window in enumerate(windows):
            child = window.widget()

            text = "%d %s" % (i + 1, child.userFriendlyCurrentFile)
            if i < 9:
                text = '&' + text

            action = self._windowMenu.addAction(text)
            action.setCheckable(True)
            action.setChecked(child == self.activeMdiChild)
            action.triggered.connect(self._windowMapper.map)
            self._windowMapper.setMapping(action, window)

    def createStatusBarLabel(self, stretch=0):
        """Create status bar label.

        :param int stretch: stretch factor
        :rtype: |QLabel|"""
        label = QtWidgets.QLabel()
        label.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
        label.setLineWidth(2)
        self.statusBar().addWidget(label, stretch)
        return label

    def createStatusBar(self):
        """Create status bar."""
        statusBar = self.statusBar()

        self._sbLabelName = self.createStatusBarLabel(1)
        self._sbLabelSize = self.createStatusBarLabel()
        self._sbLabelDimensions = self.createStatusBarLabel()
        self._sbLabelDate = self.createStatusBarLabel()
        self._sbLabelZoom = self.createStatusBarLabel()

        statusBar.showMessage("Ready")


    @property
    def activeMdiChild(self):
        """Get active MDI child (:class:`SplitViewMdiChild` or *None*)."""
        activeSubWindow = self._mdiArea.activeSubWindow()
        if activeSubWindow:
            return activeSubWindow.widget()
        return None


    def closeEvent(self, event):
        """Overrides close event to save application settings.

        :param QEvent event: instance of |QEvent|"""

        if self.is_fullscreen: # Needed to properly close the image viewer if the main window is closed while the viewer is fullscreen
            self.is_fullscreen = False
            self.setCentralWidget(self.mdiarea_plus_buttons)

        self._mdiArea.closeAllSubWindows()
        if self.activeMdiChild:
            event.ignore()
        else:
            self.writeSettings()
            event.accept()
            
    
    def tile_and_fit_mdiArea(self):
        self._mdiArea.tileSubWindows()

    
    # Synchronized pan and zoom methods
    
    @QtCore.pyqtSlot(str)
    def mappedImageViewerAction(self, methodName):
        """Perform action mapped to :class:`aux_splitview.SplitView`
        methodName.

        :param str methodName: method to call"""
        activeViewer = self.activeMdiChild
        if hasattr(activeViewer, str(methodName)):
            getattr(activeViewer, str(methodName))()

    @QtCore.pyqtSlot()
    def toggleSynchPan(self):
        """Toggle synchronized subwindow panning."""
        if self._synchPanAct.isChecked():
            self.synchPan(self.activeMdiChild)

    @QtCore.pyqtSlot()
    def panChanged(self):
        """Synchronize subwindow pans."""
        mdiChild = self.sender()
        while mdiChild is not None and type(mdiChild) != SplitViewMdiChild:
            mdiChild = mdiChild.parent()
        if mdiChild and self._synchPanAct.isChecked():
            self.synchPan(mdiChild)

    @QtCore.pyqtSlot()
    def toggleSynchZoom(self):
        """Toggle synchronized subwindow zooming."""
        if self._synchZoomAct.isChecked():
            self.synchZoom(self.activeMdiChild)

    @QtCore.pyqtSlot()
    def zoomChanged(self):
        """Synchronize subwindow zooms."""
        mdiChild = self.sender()
        if self._synchZoomAct.isChecked():
            self.synchZoom(mdiChild)
        self.updateStatusBar()

    def synchPan(self, fromViewer):
        """Synch panning of all subwindowws to the same as *fromViewer*.

        :param fromViewer: :class:`SplitViewMdiChild` that initiated synching"""

        assert isinstance(fromViewer, SplitViewMdiChild)
        if not fromViewer:
            return
        if self._handlingScrollChangedSignal:
            return
        if fromViewer.parent() != self._mdiArea.activeSubWindow(): # Prevent circular scroll state change signals from propagating
            if fromViewer.parent() != self:
                return
        self._handlingScrollChangedSignal = True

        newState = fromViewer.scrollState
        changedWindow = fromViewer.parent()
        windows = self._mdiArea.subWindowList()
        for window in windows:
            if window != changedWindow:
                if window.widget().sync_this_pan:
                    window.widget().scrollState = newState
                    window.widget().resize_scene()

        self._handlingScrollChangedSignal = False

    def synchZoom(self, fromViewer):
        """Synch zoom of all subwindowws to the same as *fromViewer*.
        
        :param fromViewer: :class:`SplitViewMdiChild` that initiated synching"""
        if not fromViewer:
            return

        newZoomFactor = fromViewer.zoomFactor

        sync_by = self.sync_zoom_by

        sender_dimension = determineSyncSenderDimension(fromViewer.imageWidth,
                                                       fromViewer.imageHeight,
                                                       sync_by)

        changedWindow = fromViewer.parent()
        windows = self._mdiArea.subWindowList()
        for window in windows:
            if window != changedWindow:
                receiver = window.widget()
                if receiver.sync_this_zoom:
                    adjustment_factor = determineSyncAdjustmentFactor(sync_by,
                                                                     sender_dimension,
                                                                     receiver.imageWidth,
                                                                     receiver.imageHeight)

                    receiver.zoomFactor = newZoomFactor*adjustment_factor
                    receiver.resize_scene()
        self.refreshPan()
        
    def synchSlice(self, fromViewer):
        """Synchronize slice with all other image windows (except the one that caused the event).
        
        Args:
            fromViewer (SplitViewMdiChild): The viewer/subwindow which triggered the slice change.
        """
        if not fromViewer or not fromViewer.is_volumetric:
            return

        windows = self._mdiArea.subWindowList()
        for window in windows:
            toViewer = window.widget()
            if (toViewer and isinstance(toViewer, SplitViewMdiChild) and 
                toViewer != fromViewer and toViewer.sync_this_slice):
                
                if toViewer.is_volumetric:
                    # If target has volumetric data and the slice exists, load it
                    if fromViewer.current_slice < toViewer.total_slices:
                        toViewer.load_slice(fromViewer.current_slice)
                    else:
                        # If the target doesn't have this slice, load the last available slice
                        toViewer.load_slice(toViewer.total_slices - 1)
                else:
                    # If target is not volumetric but fromViewer is,
                    # create a black pixmap of the same size as the current pixmap
                    if hasattr(toViewer, '_pixmapItem_main_topleft') and toViewer._pixmapItem_main_topleft:
                        current_pixmap = toViewer._pixmapItem_main_topleft.pixmap()
                        if current_pixmap and not current_pixmap.isNull():
                            width = current_pixmap.width()
                            height = current_pixmap.height()
                            
                            # Create a black pixmap of the same size
                            black_pixmap = QtGui.QPixmap(width, height)
                            black_pixmap.fill(QtCore.Qt.black)
                            
                            # Remove existing pixmap item
                            if hasattr(toViewer, '_pixmap_item_main_topleft') and toViewer._pixmap_item_main_topleft:
                                toViewer._scene_main_topleft.removeItem(toViewer._pixmap_item_main_topleft)
                            
                            # Add black pixmap
                            toViewer._pixmap_item_main_topleft = toViewer._scene_main_topleft.addPixmap(black_pixmap)

    def synchDisplayRange(self, fromViewer, min_value, max_value):
        """Synchronize display range with all other image windows (except the one that caused the event).
        
        Args:
            fromViewer (SplitViewMdiChild): The viewer/subwindow which triggered the display range change.
            min_value (float): The minimum value of the display range.
            max_value (float): The maximum value of the display range.
        """
        if not fromViewer or not fromViewer.is_volumetric:
            return

        windows = self._mdiArea.subWindowList()
        for window in windows:
            toViewer = window.widget()
            if (toViewer and isinstance(toViewer, SplitViewMdiChild) and 
                toViewer != fromViewer and toViewer.sync_this_range):
                
                if toViewer.is_volumetric:
                    # Apply the display range to other volumetric viewers
                    toViewer.apply_display_range_sync(min_value, max_value)

    def refreshPan(self):
        if self.activeMdiChild:
            self.synchPan(self.activeMdiChild)

    def refreshPanDelayed(self, ms=0):
        QtCore.QTimer.singleShot(ms, self.refreshPan)

    def refreshZoom(self):
        if self.activeMdiChild:
            self.synchZoom(self.activeMdiChild)


    # Methods from PyQt MDI Image Viewer left unaltered

    @QtCore.pyqtSlot()
    def activateSubwindowSystemMenu(self):
        """Activate current subwindow's System Menu."""
        activeSubWindow = self._mdiArea.activeSubWindow()
        if activeSubWindow:
            activeSubWindow.showSystemMenu()

    @QtCore.pyqtSlot(str)
    def openRecentFile(self, filename_main_topleft):
        """Open a recent file.

        :param str filename_main_topleft: filename_main_topleft to view"""
        self.loadFile(filename_main_topleft, None, None, None)

    @QtCore.pyqtSlot()
    def open(self):
        """Handle the open action."""
        fileDialog = QtWidgets.QFileDialog(self)
        settings = QtCore.QSettings(COMPANY, APPNAME)
        fileDialog.setNameFilters([
            "Common image files (*.jpeg *.jpg  *.png *.tiff *.tif *.bmp *.gif *.webp *.svg)",
            "JPEG image files (*.jpeg *.jpg)", 
            "PNG image files (*.png)", 
            "TIFF image files (*.tiff *.tif)",
            "BMP (*.bmp)",
            "All files (*)",])
        
        # Use the last directory if available in registry
        if settings.contains(SETTING_LAST_DIRECTORY):
            last_dir = settings.value(SETTING_LAST_DIRECTORY)
            fileDialog.setDirectory(last_dir)
        elif not settings.contains(SETTING_FILEOPEN + "/state"):
            fileDialog.setDirectory(".")
        else:
            self.restoreDialogState(fileDialog, SETTING_FILEOPEN)
            
        fileDialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        if not fileDialog.exec_():
            return
        self.saveDialogState(fileDialog, SETTING_FILEOPEN)

        filename_main_topleft = fileDialog.selectedFiles()[0]
        
        # Save the directory path to registry
        dir_path = os.path.dirname(filename_main_topleft)
        settings.setValue(SETTING_LAST_DIRECTORY, dir_path)
        
        self.loadFile(filename_main_topleft, None, None, None)

    def open_multiple(self):
        """Handle the open multiple action."""
        # Get the last directory from the registry if available
        settings = QtCore.QSettings(COMPANY, APPNAME)
        start_dir = settings.value(SETTING_LAST_DIRECTORY, "")
        
        if not start_dir and self._last_accessed_fullpath:
            start_dir = self._last_accessed_fullpath
            
        filters = "\
            Common image files (*.jpeg *.jpg  *.png *.tiff *.tif *.bmp *.gif *.webp *.svg);;\
            JPEG image files (*.jpeg *.jpg);;\
            PNG image files (*.png);;\
            TIFF image files (*.tiff *.tif);;\
            BMP (*.bmp);;\
            All files (*)"
        fullpaths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select image(s) to open", start_dir, filters)

        if fullpaths:
            # Save the directory path to registry
            dir_path = os.path.dirname(fullpaths[0])
            settings.setValue(SETTING_LAST_DIRECTORY, dir_path)
            
            for fullpath in fullpaths:
                self.loadFile(fullpath, None, None, None)



    @QtCore.pyqtSlot()
    def toggleScrollbars(self):
        """Toggle subwindow scrollbar visibility."""
        checked = self._showScrollbarsAct.isChecked()

        windows = self._mdiArea.subWindowList()
        for window in windows:
            child = window.widget()
            child.enableScrollBars(checked)

    @QtCore.pyqtSlot()
    def toggleStatusbar(self):
        """Toggle status bar visibility."""
        self.statusBar().setVisible(self._showStatusbarAct.isChecked())


    @QtCore.pyqtSlot()
    def about(self):
        """Display About dialog box."""
        QtWidgets.QMessageBox.about(self, "About MDI",
                "<b>MDI Image Viewer</b> demonstrates how to"
                "synchronize the panning and zooming of multiple image"
                "viewer windows using Qt.")
    @QtCore.pyqtSlot(QtWidgets.QMdiSubWindow)
    def subWindowActivated(self, window):
        """Handle |QMdiSubWindow| activated signal.

        :param |QMdiSubWindow| window: |QMdiSubWindow| that was just
                                       activated"""
        self.updateStatusBar()

    @QtCore.pyqtSlot(QtWidgets.QMdiSubWindow)
    def setActiveSubWindow(self, window):
        """Set active |QMdiSubWindow|.

        :param |QMdiSubWindow| window: |QMdiSubWindow| to activate """
        if window:
            self._mdiArea.setActiveSubWindow(window)


    def updateStatusBar(self):
        """Update status bar."""
        self.statusBar().setVisible(self._showStatusbarAct.isChecked())
        imageViewer = self.activeMdiChild
        if not imageViewer:
            self._sbLabelName.setText("")
            self._sbLabelSize.setText("")
            self._sbLabelDimensions.setText("")
            self._sbLabelDate.setText("")
            self._sbLabelZoom.setText("")

            self._sbLabelSize.hide()
            self._sbLabelDimensions.hide()
            self._sbLabelDate.hide()
            self._sbLabelZoom.hide()
            return

        filename_main_topleft = imageViewer.currentFile
        self._sbLabelName.setText(" %s " % filename_main_topleft)

        fi = QtCore.QFileInfo(filename_main_topleft)
        size = fi.size()
        fmt = " %.1f %s "
        if size > 1024*1024*1024:
            unit = "MB"
            size /= 1024*1024*1024
        elif size > 1024*1024:
            unit = "MB"
            size /= 1024*1024
        elif size > 1024:
            unit = "KB"
            size /= 1024
        else:
            unit = "Bytes"
            fmt = " %d %s "
        self._sbLabelSize.setText(fmt % (size, unit))

        pixmap = imageViewer.pixmap_main_topleft
        self._sbLabelDimensions.setText(" %dx%dx%d " %
                                        (pixmap.width(),
                                         pixmap.height(),
                                         pixmap.depth()))

        self._sbLabelDate.setText(
            " %s " %
            fi.lastModified().toString(QtCore.Qt.SystemLocaleShortDate))
        self._sbLabelZoom.setText(" %0.f%% " % (imageViewer.zoomFactor*100,))

        self._sbLabelSize.show()
        self._sbLabelDimensions.show()
        self._sbLabelDate.show()
        self._sbLabelZoom.show()
        
    def switchLayoutDirection(self):
        """Switch MDI subwindow layout direction."""
        if self.layoutDirection() == QtCore.Qt.LeftToRight:
            QtWidgets.QApplication.setLayoutDirection(QtCore.Qt.RightToLeft)
        else:
            QtWidgets.QApplication.setLayoutDirection(QtCore.Qt.LeftToRight)

    def saveDialogState(self, dialog, groupName):
        """Save dialog state, position & size.

        :param str groupName: |QSettings| group name"""
        assert isinstance(dialog, QtWidgets.QDialog)

        settings = QtCore.QSettings(COMPANY, APPNAME)
        settings.beginGroup(groupName)

        settings.setValue('state', dialog.saveState() if hasattr(dialog, "saveState") else QtCore.QByteArray())
        settings.setValue('geometry', dialog.saveGeometry())
        settings.setValue('filter', dialog.selectedNameFilter())

        settings.endGroup()

    def restoreDialogState(self, dialog, groupName):
        """Restore dialog state, position & size.

        :param str groupName: |QSettings| group name"""
        assert isinstance(dialog, QtWidgets.QDialog)

        settings = QtCore.QSettings(COMPANY, APPNAME)
        settings.beginGroup(groupName)

        dialog.restoreState(settings.value('state'))
        dialog.restoreGeometry(settings.value('geometry'))
        dialog.selectNameFilter(settings.value('filter', ""))

        settings.endGroup()

    def writeSettings(self):
        """Write application settings."""
        settings = QtCore.QSettings(COMPANY, APPNAME)
        settings.setValue('pos', self.pos())
        settings.setValue('size', self.size())
        settings.setValue('windowgeometry', self.saveGeometry())
        settings.setValue('windowstate', self.saveState())

        settings.setValue(SETTING_SCROLLBARS,
                          self._showScrollbarsAct.isChecked())
        settings.setValue(SETTING_STATUSBAR,
                          self._showStatusbarAct.isChecked())
        settings.setValue(SETTING_SYNCHZOOM,
                          self._synchZoomAct.isChecked())
        settings.setValue(SETTING_SYNCHPAN,
                          self._synchPanAct.isChecked())

    def readSettings(self):
        """Read application settings."""
        
        scrollbars_always_checked_off_at_startup = True
        statusbar_always_checked_off_at_startup = True
        sync_always_checked_on_at_startup = True

        settings = QtCore.QSettings(COMPANY, APPNAME)

        pos = settings.value('pos', QtCore.QPoint(100, 100))
        size = settings.value('size', QtCore.QSize(1100, 600))
        self.move(pos)
        self.resize(size)

        if settings.contains('windowgeometry'):
            self.restoreGeometry(settings.value('windowgeometry'))
        if settings.contains('windowstate'):
            self.restoreState(settings.value('windowstate'))

        
        if scrollbars_always_checked_off_at_startup:
            self._showScrollbarsAct.setChecked(False)
        else:
            self._showScrollbarsAct.setChecked(
                toBool(settings.value(SETTING_SCROLLBARS, False)))

        if statusbar_always_checked_off_at_startup:
            self._showStatusbarAct.setChecked(False)
        else:
            self._showStatusbarAct.setChecked(
                toBool(settings.value(SETTING_STATUSBAR, False)))

        if sync_always_checked_on_at_startup:
            self._synchZoomAct.setChecked(True)
            self._synchPanAct.setChecked(True)
        else:
            self._synchZoomAct.setChecked(
                toBool(settings.value(SETTING_SYNCHZOOM, False)))
            self._synchPanAct.setChecked(
                toBool(settings.value(SETTING_SYNCHPAN, False)))

    def updateRecentFileSettings(self, filename_main_topleft, delete=False):
        """Update recent file list setting.

        :param str filename_main_topleft: filename_main_topleft to add or remove from recent file
                             list
        :param bool delete: if True then filename_main_topleft removed, otherwise added"""
        settings = QtCore.QSettings(COMPANY, APPNAME)
        
        try:
            files = list(settings.value(SETTING_RECENTFILELIST, []))
        except TypeError:
            files = []

        try:
            files.remove(filename_main_topleft)
        except ValueError:
            pass

        if not delete:
            files.insert(0, filename_main_topleft)
        del files[MultiViewMainWindow.MaxRecentFiles:]

        settings.setValue(SETTING_RECENTFILELIST, files)

    def toggle_overlay_panels(self, boolean=None):
        """Toggle visibility of Overlay panels.
        
        Args:
            boolean (bool, optional): True to show overlay panels; False to hide. 
                                     If None, toggle based on current button state.
        """
        if boolean is None:
            boolean = self.overlay_toggle_pushbutton.isChecked()
        
        # Ensure the interface is visible to show overlay panels
        if boolean and not self.is_interface_showing:
            self.show_interface_on()
            self.interface_toggle_pushbutton.setChecked(True)
        
        # Set visibility of the overlay-related panels
        self._splitview_creator.setVisible(boolean)
        self._sliders_opacity_splitviews.setVisible(boolean)
        self._splitview_manager.setVisible(boolean)
        
        # Update button state and tooltip
        self.overlay_toggle_pushbutton.setChecked(boolean)
        if boolean:
            self.overlay_toggle_pushbutton.setToolTip("Hide Overlay Controls")
        else:
            self.overlay_toggle_pushbutton.setToolTip("Show Overlay Controls")
        
        # If interface is off, ensure overlay panels are also hidden
        if not self.is_interface_showing:
            self._splitview_creator.setVisible(False)
            self._sliders_opacity_splitviews.setVisible(False)
            self._splitview_manager.setVisible(False)



def main():
    """Run MultiViewMainWindow as main app.
    
    Attributes:
        app (QApplication): Starts and holds the main event loop of application.
        mainWin (MultiViewMainWindow): The main window.
    """
    import sys
    import os  # os 모듈 명시적으로 임포트
    
    # 파일을 더블 클릭해서 실행할 때 sys.stderr가 None일 수 있음
    # 이 경우 argparse 오류 발생 방지를 위해 커스텀 ArgumentParser 사용
    class ArgumentParserWithoutExit(argparse.ArgumentParser):
        def error(self, message):
            if sys.stderr is None:
                # 더블 클릭 실행 시 stderr가 없는 경우 조용히 넘어감
                pass
            else:
                # 일반적인 명령줄 실행 시 표준 에러 메시지 출력
                super().error(message)
    
    parser = ArgumentParserWithoutExit(
                prog='Butterfly Viewer',
                description='Side-by-side image viewer with synchronized zoom and sliding overlays. Further info: https://olive-groves.github.io/butterfly_viewer/'
            )

    # Note that despite using argparse, we still forward argv to QApplication further below, so that users can optionally
    # provide QT-specific arguments. Be sure to choose specific names for custom arguments that won't clash with QT.
    parser.add_argument('--hide', help='If provided, hides the interface on start.', action='store_true')
    parser.add_argument('--fullscreen', help='If provided, fullscreens the app on start.', action='store_true')
    parser.add_argument('--show-overlay-controls', help='If provided, shows the overlay controls on start.', action='store_true')
    parser.add_argument('--suppress-warnings', help='If provided, suppresses Qt warning messages.', action='store_true')
    parser.add_argument('--paths', nargs="*", help='If provided, automatically starts with individual (side by side) image windows supplied by these paths.')
    parser.add_argument('--overlay_path_main_topleft', help='If provided, automatically starts with the main image (top left) supplied by this path.')
    parser.add_argument('--overlay_path_topright', help='If provided, automatically starts with the top right image supplied by this path.')
    parser.add_argument('--overlay_path_bottomleft', help='If provided, automatically starts with the bottom left image supplied by this path.')
    parser.add_argument('--overlay_path_bottomright', help='If provided, automatically starts with the bottom right image supplied by this path.')
    
    try:
        args = parser.parse_args()
    except SystemExit:
        # 파일을 더블 클릭하여 실행한 경우, 또는 잘못된 인수가 전달된 경우
        # 기본 값으로 진행
        class DefaultArgs:
            hide = False
            fullscreen = False
            show_overlay_controls = False
            suppress_warnings = False
            paths = []
            overlay_path_main_topleft = None
            overlay_path_topright = None
            overlay_path_bottomleft = None
            overlay_path_bottomright = None
        args = DefaultArgs()
        
    # 더블 클릭한 파일 경로가 있으면 추가
    if len(sys.argv) > 1:
        file_path = sys.argv[1].replace('\\', '/').strip('"')  # 경로 정규화 및 따옴표 제거
        if os.path.isfile(file_path):
            args.paths = [file_path]
            print(f"Loading file: {file_path}")  # 디버깅용 출력

    # 경고 메시지 억제 옵션
    if args.suppress_warnings:
        import os
        os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"
        # stderr 리디렉션
        class NullWriter:
            def write(self, text):
                pass
            def flush(self):
                pass
        
        if sys.stderr is None:
            sys.stderr = NullWriter()

    app = QtWidgets.QApplication(sys.argv)
    QtCore.QSettings.setDefaultFormat(QtCore.QSettings.IniFormat)
    app.setOrganizationName(COMPANY)
    app.setOrganizationDomain(DOMAIN)
    app.setApplicationName(APPNAME)
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(QtGui.QIcon(":/icons/icon.png"))

    mainWin = MultiViewMainWindow()
    mainWin.setWindowTitle(APPNAME)

    # Load any predefined images:
    if args.paths:
        for path in args.paths:
            mainWin.loadFile(path)

    dda = mainWin._splitview_creator.drag_drop_area
    preloadedImageCount = 0
    if args.overlay_path_main_topleft:
        dda.app_main_topleft.load_image(args.overlay_path_main_topleft)
        preloadedImageCount+=1
    if args.overlay_path_bottomleft:
        dda.app_bottomleft.load_image(args.overlay_path_bottomleft)
        preloadedImageCount+=1
    if args.overlay_path_topright:
        dda.app_topright.load_image(args.overlay_path_topright)
        preloadedImageCount+=1
    if args.overlay_path_bottomright:
        dda.app_bottomright.load_image(args.overlay_path_bottomright)
        preloadedImageCount+=1

    if preloadedImageCount >= 2:
        mainWin.on_create_splitview()

    # Settings:
    # 기본적으로 Overlay 관련 컨트롤 숨기기 (명령줄 매개변수로 재정의 가능)
    if not args.show_overlay_controls:
        # Sliding overlay creator, Overlay 컨트롤, Lock overlay 패널을 숨깁니다
        mainWin.toggle_overlay_panels(False)
    
    if args.hide:
        mainWin.show_interface_off()
    if args.fullscreen:
        mainWin.set_fullscreen_on()

    mainWin.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
