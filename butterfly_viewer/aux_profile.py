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
from aux_buttons import ViewerButton
from PIL import Image  # Add PIL import here since we use it for volumetric data

class ProfileLine(QtWidgets.QGraphicsLineItem):
    """Interactive line item for profile selection."""
    
    def __init__(self, x1, y1, x2, y2, parent=None):
        # Set minimum line length (in scene coordinates)
        self.MIN_LINE_LENGTH = 100
        
        # Ensure minimum line length
        dx = x2 - x1
        dy = y2 - y1
        current_length = (dx * dx + dy * dy) ** 0.5
        
        if current_length < self.MIN_LINE_LENGTH:
            # Calculate the scaling factor needed to reach minimum length
            scale = self.MIN_LINE_LENGTH / current_length if current_length > 0 else 1
            # Extend the line while keeping the start point fixed
            x2 = x1 + dx * scale
            y2 = y1 + dy * scale
        
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
        """Update close button position to be near the right handle."""
        if not hasattr(self, 'close_button'):
            return
            
        line = self.line()
        
        # Get the right endpoint (handle2 position)
        right_point = line.p2()
        
        # Calculate unit vector in the direction of the line
        dx = line.dx()
        dy = line.dy()
        length = (dx * dx + dy * dy) ** 0.5
        if length > 0:
            # Use a fixed offset from the right handle
            offset = self.MIN_LINE_LENGTH * 0.4  # 30% of minimum line length
            
            # Position the button to the right of the right handle
            button_x = right_point.x() + offset
            button_y = right_point.y()
            
            self.close_button.setPos(button_x, button_y)
    
    def itemChange(self, change, value):
        """Handle position changes."""
        if change == QtWidgets.QGraphicsItem.ItemPositionChange and not self._updating:
            try:
                self._updating = True  # Set flag to prevent recursion
                
                if self._moving:
                    # Update handle positions when line is moved
                    self.updateHandles()
                    
                    # Get the scene and window
                    scene = self.scene()
                    if scene and scene.views():
                        view = scene.views()[0]
                        window = view.window()
                        
                        # Get all windows and sync profile line position
                        if window and hasattr(window, '_mdiArea'):
                            windows = window._mdiArea.subWindowList()
                            for other_window in windows:
                                other_child = other_window.widget()
                                if other_child and hasattr(other_child, '_scene_main_topleft'):
                                    other_scene = other_child._scene_main_topleft
                                    if other_scene != scene and hasattr(other_scene, 'profile_line'):
                                        # Get the line coordinates in scene coordinates
                                        line = self.line()
                                        pos = self.pos()
                                        # Update the other scene's profile line position
                                        other_scene.profile_line.setPos(pos)
                                        other_scene.profile_line.updateHandles()
                                        
                            # Update profiles in all views
                            profiles = []
                            labels = []
                            for other_window in windows:
                                other_child = other_window.widget()
                                if other_child and hasattr(other_child, '_scene_main_topleft'):
                                    other_scene = other_child._scene_main_topleft
                                    if hasattr(other_scene, 'profile_line'):
                                        # Get profile values for this scene
                                        line = other_scene.profile_line.line()
                                        start_point = (line.x1() + other_scene.profile_line.pos().x(), 
                                                     line.y1() + other_scene.profile_line.pos().y())
                                        end_point = (line.x2() + other_scene.profile_line.pos().x(), 
                                                   line.y2() + other_scene.profile_line.pos().y())
                                        
                                        # Get the image data
                                        pixmap_item = None
                                        for item in other_scene.items():
                                            if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                                                pixmap_item = item
                                                break
                                        
                                        if pixmap_item:
                                            positions, values = get_profile_values(None, start_point, end_point, 
                                                                                scene=other_scene, pixmap_item=pixmap_item)
                                            if positions is not None and values is not None:
                                                profiles.append((positions, values))
                                                labels.append(f"Window {len(profiles)}")
                            
                            # Update the profile dialog with all profiles
                            if profiles:
                                for other_window2 in windows:
                                    other_child2 = other_window2.widget()
                                    if other_child2 and hasattr(other_child2, '_scene_main_topleft'):
                                        other_scene2 = other_child2._scene_main_topleft
                                        if hasattr(other_scene2, 'profile_dialog'):
                                            other_scene2.profile_dialog.update_profile(profiles, labels)
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
        if scene is not None and hasattr(scene, 'profile_line_changed'):
            scene.profile_line_changed.emit()
            
    def setLine(self, x1, y1, x2, y2):
        """Override setLine to enforce minimum length."""
        dx = x2 - x1
        dy = y2 - y1
        current_length = (dx * dx + dy * dy) ** 0.5
        
        if current_length < self.MIN_LINE_LENGTH:
            # Calculate the scaling factor needed to reach minimum length
            scale = self.MIN_LINE_LENGTH / current_length if current_length > 0 else 1
            # Extend the line while keeping the start point fixed
            x2 = x1 + dx * scale
            y2 = y1 + dy * scale
            
        super().setLine(x1, y1, x2, y2)

class CloseButton(QtWidgets.QGraphicsItem):
    """Close button for removing the profile line."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set fixed size for the button
        self.button_size = 30
        
        # Make clickable
        self.setAcceptHoverEvents(True)
        
        # Create ViewerButton for consistent styling
        self.button = ViewerButton(style="trigger-severe")
        self.button.setIcon(":/icons/close.svg")
        self.button.setFixedSize(self.button_size, self.button_size)
        self.button.clicked.connect(self.remove_profile)
        
        # Create proxy widget to display the button in the graphics scene
        self.proxy = QtWidgets.QGraphicsProxyWidget(self)
        self.proxy.setWidget(self.button)
        
        # Center the proxy widget on this item
        self.proxy.setPos(-self.button_size/2, -self.button_size/2)
        
    def boundingRect(self):
        """Return the bounding rectangle of the button."""
        return QtCore.QRectF(-self.button_size/2, -self.button_size/2, 
                            self.button_size, self.button_size)
        
    def paint(self, painter, option, widget):
        """Paint method required by QGraphicsItem."""
        # Scale the proxy widget to maintain consistent size
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            if view:
                scale = 1.0 / view.transform().m11()
                self.proxy.setScale(scale)
        
    def remove_profile(self):
        """Remove the profile line and its associated items."""
        scene = self.scene()
        if scene:
            scene.cleanup_profile_tool()
            
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == QtCore.Qt.LeftButton:
            self.remove_profile()
        super().mousePressEvent(event)
        
    def hoverEnterEvent(self, event):
        """Handle hover enter events."""
        self.setCursor(QtCore.Qt.PointingHandCursor)
        super().hoverEnterEvent(event)
        
    def hoverLeaveEvent(self, event):
        """Handle hover leave events."""
        self.unsetCursor()
        super().hoverLeaveEvent(event)

class ProfileHandle(QtWidgets.QGraphicsItem):
    """Handle for adjusting profile line endpoints."""
    
    def __init__(self, parent, handle_num):
        super().__init__(parent)
        self.handle_num = handle_num
        self.parent_line = parent
        self._updating = False  # Flag to prevent recursive updates
        
        # Set fixed size for the handle
        self.handle_size = 10
        
        # Make handle movable
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        
    def boundingRect(self):
        """Return the bounding rectangle of the handle."""
        return QtCore.QRectF(-self.handle_size/2, -self.handle_size/2, 
                            self.handle_size, self.handle_size)
        
    def paint(self, painter, option, widget):
        """Paint the handle."""
        painter.save()
        
        # Scale transform to maintain consistent size
        view = self.scene().views()[0]
        scale = 1.0 / view.transform().m11()
        painter.scale(scale, scale)
        
        # Draw handle
        rect = QtCore.QRectF(-self.handle_size/2, -self.handle_size/2,
                            self.handle_size, self.handle_size)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 1))
        painter.drawRect(rect)
        
        painter.restore()
    
    def update_all_profiles_in_views(self):
        """모든 윈도우의 profile_dialog에 대해 profiles, labels를 계산하여 update_profile을 호출한다."""
        scene = self.scene()
        if scene and scene.views():
            view = scene.views()[0]
            window = view.window()
            if window and hasattr(window, '_mdiArea'):
                windows = window._mdiArea.subWindowList()
                profiles = []
                labels = []
                for other_window in windows:
                    other_child = other_window.widget()
                    if other_child and hasattr(other_child, '_scene_main_topleft'):
                        other_scene = other_child._scene_main_topleft
                        if hasattr(other_scene, 'profile_line'):
                            line = other_scene.profile_line.line()
                            start_point = (line.x1(), line.y1())
                            end_point = (line.x2(), line.y2())
                            pixmap_item = None
                            for item in other_scene.items():
                                if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                                    pixmap_item = item
                                    break
                            if pixmap_item:
                                positions, values = get_profile_values(None, start_point, end_point, scene=other_scene, pixmap_item=pixmap_item)
                                if positions is not None and values is not None:
                                    profiles.append((positions, values))
                                    labels.append(f"Window {len(profiles)}")
                if profiles:
                    for other_window2 in windows:
                        other_child2 = other_window2.widget()
                        if other_child2 and hasattr(other_child2, '_scene_main_topleft'):
                            other_scene2 = other_child2._scene_main_topleft
                            if hasattr(other_scene2, 'profile_dialog'):
                                other_scene2.profile_dialog.update_profile(profiles, labels)

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
                # --- profile_line 위치/모양 동기화 ---
                scene = self.scene()
                if scene and scene.views():
                    view = scene.views()[0]
                    window = view.window()
                    if window and hasattr(window, '_mdiArea'):
                        windows = window._mdiArea.subWindowList()
                        for other_window in windows:
                            other_child = other_window.widget()
                            if other_child and hasattr(other_child, '_scene_main_topleft'):
                                other_scene = other_child._scene_main_topleft
                                if other_scene != scene and hasattr(other_scene, 'profile_line'):
                                    line = self.parent_line.line()
                                    other_scene.profile_line.setLine(line.x1(), line.y1(), line.x2(), line.y2())
                                    other_scene.profile_line.updateHandles()
                # --- profile 업데이트 (공통 함수) ---
                self.update_all_profiles_in_views()
                # Emit signal to update profile
                scene = self.scene()
                if scene is not None and hasattr(scene, 'profile_line_changed'):
                    scene.profile_line_changed.emit()
            finally:
                self._updating = False  # Always reset flag
        return super().itemChange(change, value)
        
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == QtCore.Qt.LeftButton:
            event.accept()
            super().mousePressEvent(event)
        else:
            event.ignore()
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if event.button() == QtCore.Qt.LeftButton:
            event.accept()
            super().mouseReleaseEvent(event)
            # 프로파일 업데이트 (공통 함수 호출)
            self.update_all_profiles_in_views()
        else:
            event.ignore()

class ProfileDialog(QtWidgets.QDialog):
    """Dialog for displaying profile graph."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Intensity Profile")
        
        # Set window flags to stay on top by default
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        # Create menu bar
        self.menu_bar = QtWidgets.QMenuBar(self)
        
        # File menu
        self.file_menu = self.menu_bar.addMenu("File")
        
        # Save Graph action
        self.save_graph_action = QtWidgets.QAction("Save Graph as Image...", self)
        self.save_graph_action.triggered.connect(self.save_graph)
        self.file_menu.addAction(self.save_graph_action)
        
        # Export Data action
        self.export_data_action = QtWidgets.QAction("Export Profile Data...", self)
        self.export_data_action.triggered.connect(self.export_data)
        self.file_menu.addAction(self.export_data_action)
        
        # View menu
        self.view_menu = self.menu_bar.addMenu("View")
        
        # Always on Top action
        self.always_on_top_action = QtWidgets.QAction("Always on Top", self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.setChecked(True)
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        self.view_menu.addAction(self.always_on_top_action)
        
        # Create layout
        layout = QtWidgets.QVBoxLayout()
        layout.setMenuBar(self.menu_bar)
        layout.addWidget(self.canvas)
        
        self.setLayout(layout)
        self.resize(800, 600)
        
        # Store profile data
        self.current_profiles = None
        self.current_labels = None
        
    def toggle_always_on_top(self, checked):
        """Toggle the window's always-on-top state."""
        flags = self.windowFlags()
        if checked:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        else:
            flags &= ~QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()  # Need to show again after changing flags
        
    def save_graph(self):
        """Save the current graph as an image file."""
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Graph",
            "",
            "PNG Files (*.png);;JPEG Files (*.jpg);;All Files (*)"
        )
        
        if file_path:
            try:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight')
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    "Graph saved successfully!"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to save graph: {str(e)}"
                )
                
    def export_data(self):
        """Export profile data to CSV file."""
        if self.current_profiles is None or self.current_labels is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Warning",
                "No profile data available to export."
            )
            return
            
        file_path, selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Profile Data",
            "",
            "CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            import pandas as pd
            
            # Create DataFrame
            data = {}
            for profile, label in zip(self.current_profiles, self.current_labels):
                x_values = profile[0]
                y_values = profile[1]
                data[f"{label}_X"] = x_values
                data[f"{label}_Y"] = y_values
                
            df = pd.DataFrame(data)
            
            # Save based on file extension
            try:
                if file_path.lower().endswith('.xlsx'):
                    df.to_excel(file_path, index=False)
                else:
                    if not file_path.lower().endswith('.csv'):
                        file_path += '.csv'
                    df.to_csv(file_path, index=False)
            except ImportError as e:
                # If Excel export fails due to missing openpyxl, fallback to CSV
                if 'openpyxl' in str(e):
                    if not file_path.lower().endswith('.csv'):
                        file_path = file_path.rsplit('.', 1)[0] + '.csv'
                    df.to_csv(file_path, index=False)
                    QtWidgets.QMessageBox.information(
                        self,
                        "Notice",
                        "Excel export not available. Data has been saved as CSV instead."
                    )
                else:
                    raise
                
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                "Profile data exported successfully!"
            )
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to export data: {str(e)}"
            )
    
    def update_profile(self, profiles, labels):
        """Update the profile graph with new data."""
        self.current_profiles = profiles
        self.current_labels = labels
        
        self.ax.clear()
        
        for profile, label in zip(profiles, labels):
            x_values = profile[0]
            y_values = profile[1]
            self.ax.plot(x_values, y_values, label=label)
            
        self.ax.set_xlabel('Distance (pixels)')
        self.ax.set_ylabel('Intensity')
        self.ax.legend()
        self.ax.grid(True)
        
        self.figure.tight_layout()
        self.canvas.draw()
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Clean up matplotlib figure to prevent memory leaks
        plt.close(self.figure)
        super().closeEvent(event)

def get_profile_values(image, start_point, end_point, num_samples=1000, scene=None, pixmap_item=None):
    """Get pixel values along a line in an image.
    
    Args:
        image: numpy array containing image data or None if using volumetric data
        start_point: (x, y) tuple of line start point in scene coordinates
        end_point: (x, y) tuple of line end point in scene coordinates
        num_samples: Number of points to sample along the line
        scene: The QGraphicsScene containing the image (needed for coordinate transformation)
        pixmap_item: The QGraphicsPixmapItem containing the image
    
    Returns:
        Tuple of (positions, values) where positions are distances along the line
        and values are the corresponding pixel values
    """
    if scene and pixmap_item:
        # Convert scene coordinates to item coordinates
        start_point_item = pixmap_item.mapFromScene(QtCore.QPointF(*start_point))
        end_point_item = pixmap_item.mapFromScene(QtCore.QPointF(*end_point))
        
        # Get item coordinates
        start_x = start_point_item.x()
        start_y = start_point_item.y()
        end_x = end_point_item.x()
        end_y = end_point_item.y()
        
        # Create points along the line in item coordinates
        x = np.linspace(start_x, end_x, num_samples)
        y = np.linspace(start_y, end_y, num_samples)
        
        # Calculate positions along the line
        positions = np.sqrt((x - start_x)**2 + (y - start_y)**2)
        
        # Check if we're dealing with volumetric data
        if hasattr(scene, 'views') and scene.views():
            view = scene.views()[0]
            mdi_child = view.parent()
            if hasattr(mdi_child, 'is_volumetric') and mdi_child.is_volumetric:
                volumetric_handler = mdi_child.volumetric_handler
                current_slice = mdi_child.current_slice
                try:
                    # Open the image file and get the current slice
                    with Image.open(volumetric_handler.filepath) as img:
                        img.seek(current_slice)
                        # Convert coordinates to integers and clip to image boundaries
                        x_indices = np.clip(x.astype(int), 0, img.width - 1)
                        y_indices = np.clip(y.astype(int), 0, img.height - 1)
                        # Convert image to numpy array
                        img_array = np.array(img)
                        # Get values along the line
                        if img.mode == 'L':  # 8-bit grayscale
                            values = img_array[y_indices, x_indices]
                        elif img.mode == 'I':  # 32-bit integer
                            values = img_array[y_indices, x_indices]
                        elif img.mode == 'F':  # 32-bit float
                            values = img_array[y_indices, x_indices]
                        else:  # RGB or RGBA
                            if len(img_array.shape) == 3:
                                # Average across color channels
                                values = np.mean(img_array[y_indices, x_indices], axis=1)
                            else:
                                values = img_array[y_indices, x_indices]
                        return positions, values
                except Exception as e:
                    print(f"Error reading volumetric data: {str(e)}")
                    return positions, np.zeros_like(positions)
        
        # For regular images, get pixel values using bilinear interpolation
        if image is not None:
            if len(image.shape) == 3:  # Color image
                values = []
                for channel in range(image.shape[2]):
                    values.append(get_interpolated_values(image[:,:,channel], x, y))
                values = np.mean(values, axis=0)  # Average across channels
            else:  # Grayscale image
                values = get_interpolated_values(image, x, y)
            
            return positions, values
    
    return None, None

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