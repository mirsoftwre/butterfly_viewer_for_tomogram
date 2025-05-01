#!/usr/bin/env python3

"""Profile tool for analyzing pixel values along a line in images.

Not intended as a script.

Creates a line selection tool and profile graph display for the Butterfly Viewer.
"""
# SPDX-License-Identifier: GPL-3.0-or-later

from PyQt5 import QtCore, QtGui, QtWidgets
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class ProfileLine(QtWidgets.QGraphicsLineItem):
    """Interactive line item for profile selection."""
    
    def __init__(self, x1, y1, x2, y2, parent=None):
        super().__init__(x1, y1, x2, y2, parent)
        
        self._moving = False
        self._updating = False  # Flag to prevent recursive updates
        
        # Set line appearance
        pen = QtGui.QPen(QtGui.QColor(255, 255, 0))  # Yellow color
        pen.setWidth(2)
        self.setPen(pen)
        
        # Create handles
        self.handle1 = ProfileHandle(self, 0)
        self.handle2 = ProfileHandle(self, 1)
        
        # Make line movable
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        
        # Add close button - after parent initialization is complete
        self.close_button = CloseButton(self)
        
        # Update positions
        self.updateHandles()
    
    def updateHandles(self):
        """Update handle positions based on line endpoints."""
        if not hasattr(self, 'handle1') or not hasattr(self, 'handle2'):
            return
            
        line = self.line()
        self.handle1.setPos(line.p1())
        self.handle2.setPos(line.p2())
        
        if hasattr(self, 'close_button'):
            self.updateCloseButtonPosition()
    
    def updateCloseButtonPosition(self):
        """Update close button position to be near the line center."""
        if not hasattr(self, 'close_button'):
            return
            
        line = self.line()
        center = line.center()
        # Position the button slightly above the line center
        offset = 15
        normal = line.normalVector().unitVector().translated(-line.p1())
        normal_point = normal.p2()
        
        # Calculate the position above the line center
        button_x = center.x() + (normal_point.x() * offset)
        button_y = center.y() + (normal_point.y() * offset)
        
        self.close_button.setPos(button_x - self.close_button.boundingRect().width()/2,
                                button_y - self.close_button.boundingRect().height()/2)
    
    def itemChange(self, change, value):
        """Handle position changes."""
        if change == QtWidgets.QGraphicsItem.ItemPositionChange and not self._updating:
            try:
                self._updating = True  # Set flag to prevent recursion
                
                if self._moving:
                    # Update handle positions when line is moved
                    self.updateHandles()
                    # Synchronize with other views
                    scene = self.scene()
                    if scene:
                        scene.sync_profile_line_position(self)
            finally:
                self._updating = False  # Always reset flag
                
        return super().itemChange(change, value)
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        self._moving = True
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        self._moving = False
        super().mouseReleaseEvent(event)
        # Emit signal to update profile
        scene = self.scene()
        if scene:
            scene.profile_line_changed.emit()

class CloseButton(QtWidgets.QGraphicsPixmapItem):
    """Close button for removing the profile line."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Load close icon
        close_icon = QtGui.QPixmap(":/icons/close.svg")
        # Scale icon to appropriate size
        scaled_icon = close_icon.scaled(16, 16, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.setPixmap(scaled_icon)
        
        # Make clickable
        self.setAcceptHoverEvents(True)
        
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == QtCore.Qt.LeftButton:
            # Remove the profile line and its associated items
            scene = self.scene()
            if scene:
                scene.cleanup_profile_tool()
        super().mousePressEvent(event)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        # Change cursor to pointing hand
        self.setCursor(QtCore.Qt.PointingHandCursor)
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        # Restore cursor
        self.unsetCursor()
        super().hoverLeaveEvent(event)

class ProfileHandle(QtWidgets.QGraphicsEllipseItem):
    """Handle for adjusting profile line endpoints."""
    
    def __init__(self, parent, handle_num):
        super().__init__(-4, -4, 8, 8, parent)
        self.handle_num = handle_num
        self.parent_line = parent
        self._updating = False  # Flag to prevent recursive updates
        
        # Set handle appearance
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0)))
        self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        
        # Make handle movable
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
    
    def itemChange(self, change, value):
        """Handle position changes."""
        if change == QtWidgets.QGraphicsItem.ItemPositionChange and not self._updating:
            try:
                self._updating = True  # Set flag to prevent recursion
                
                # Update line endpoint when handle is moved
                line = self.parent_line.line()
                if self.handle_num == 0:
                    self.parent_line.setLine(value.x(), value.y(), line.p2().x(), line.p2().y())
                else:
                    self.parent_line.setLine(line.p1().x(), line.p1().y(), value.x(), value.y())
                
                # Update close button position
                self.parent_line.updateCloseButtonPosition()
                
                # Synchronize with other views
                scene = self.scene()
                if scene:
                    scene.sync_profile_line_position(self.parent_line)
                    scene.profile_line_changed.emit()
            finally:
                self._updating = False  # Always reset flag
                
        return super().itemChange(change, value)

class ProfileDialog(QtWidgets.QDialog):
    """Dialog for displaying profile graph."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Intensity Profile")
        self.setModal(False)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        
        # Initialize plot
        self.ax.set_xlabel('Position along line (pixels)')
        self.ax.set_ylabel('Pixel value')
        self.ax.grid(True)
        
        # Set window size
        self.resize(600, 400)
    
    def update_profile(self, profiles, labels):
        """Update the profile plot with new data.
        
        Args:
            profiles: List of (positions, values) tuples for each profile
            labels: List of labels for each profile
        """
        self.ax.clear()
        
        if not profiles:  # No data to plot
            self.ax.set_xlabel('Position along line (pixels)')
            self.ax.set_ylabel('Pixel value')
            self.ax.grid(True)
            self.canvas.draw()
            return
            
        colors = plt.cm.tab10(np.linspace(0, 1, len(profiles)))
        
        for (positions, values), label, color in zip(profiles, labels, colors):
            self.ax.plot(positions, values, label=label, color=color)
        
        self.ax.set_xlabel('Position along line (pixels)')
        self.ax.set_ylabel('Pixel value')
        self.ax.grid(True)
        
        # Only show legend if there are plots
        if len(profiles) > 0:
            self.ax.legend()
        
        self.canvas.draw()

def get_profile_values(image, start_point, end_point, num_samples=1000):
    """Get pixel values along a line in an image.
    
    Args:
        image: numpy array containing image data
        start_point: (x, y) tuple of line start point
        end_point: (x, y) tuple of line end point
        num_samples: Number of points to sample along the line
    
    Returns:
        Tuple of (positions, values) where positions are distances along the line
        and values are the corresponding pixel values
    """
    # Create points along the line
    x = np.linspace(start_point[0], end_point[0], num_samples)
    y = np.linspace(start_point[1], end_point[1], num_samples)
    
    # Calculate positions along the line
    positions = np.sqrt((x - start_point[0])**2 + (y - start_point[1])**2)
    
    # Get pixel values using bilinear interpolation
    if len(image.shape) == 3:  # Color image
        values = []
        for channel in range(image.shape[2]):
            values.append(get_interpolated_values(image[:,:,channel], x, y))
        values = np.mean(values, axis=0)  # Average across channels
    else:  # Grayscale image
        values = get_interpolated_values(image, x, y)
    
    return positions, values

def get_interpolated_values(image, x, y):
    """Get interpolated pixel values at floating point coordinates.
    
    Args:
        image: 2D numpy array
        x: array of x coordinates
        y: array of y coordinates
    
    Returns:
        Array of interpolated pixel values
    """
    x0 = np.floor(x).astype(int)
    x1 = x0 + 1
    y0 = np.floor(y).astype(int)
    y1 = y0 + 1
    
    # Clip to image boundaries
    x0 = np.clip(x0, 0, image.shape[1]-1)
    x1 = np.clip(x1, 0, image.shape[1]-1)
    y0 = np.clip(y0, 0, image.shape[0]-1)
    y1 = np.clip(y1, 0, image.shape[0]-1)
    
    # Get pixel values at corners
    Ia = image[y0, x0]
    Ib = image[y0, x1]
    Ic = image[y1, x0]
    Id = image[y1, x1]
    
    # Calculate weights
    wa = (x1-x) * (y1-y)
    wb = (x-x0) * (y1-y)
    wc = (x1-x) * (y-y0)
    wd = (x-x0) * (y-y0)
    
    # Calculate interpolated values
    return wa*Ia + wb*Ib + wc*Ic + wd*Id 