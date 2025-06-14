#!/usr/bin/env python3

"""QGraphicsScene with signals and right-click functionality for SplitView.

Not intended as a script.

Creates the base (main) scene of the SplitView for the Butterfly Viewer and Registrator.
"""
# SPDX-License-Identifier: GPL-3.0-or-later



from PyQt5 import QtCore, QtWidgets
import os
import numpy as np
import tifffile

from aux_comments import CommentItem
from aux_rulers import RulerItem
from aux_dialogs import PixelUnitConversionInputDialog
from aux_profile import ProfileLine, ProfileDialog, get_profile_values
from aux_image_info import ImageInfoDialog



class CustomQGraphicsScene(QtWidgets.QGraphicsScene):
    """QGraphicsScene with signals and right-click functionality for SplitView.

    Recommended to be instantiated without input (for example, my_scene = CustomQGraphicsScene())
    
    Signals for right click menu for comments (create comment, save comments, load comments).
    Signals for right click menu for rulers (create ruler, set origin relative position, set px-per-unit conversion) 
    Signals for right click menu for transform mode (interpolate, non-interpolate)
    Methods for right click menu.

    Args:
        Identical to base class QGraphicsScene.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.px_conversion = 1.0
        self.unit_conversion = 1.0
        self.px_per_unit = 1.0
        self.px_per_unit_conversion_set = False
        self.relative_origin_position = "bottomleft"
        self.single_transform_mode_smooth = False

        # Add profile tool support
        self.profile_line = None
        self.profile_dialog = None
        self.in_profile_mode = False

        # Add statistics tool support
        self.in_statistics_mode = False

        self.background_colors = [["Dark gray (default)", 32, 32, 32],
                                  ["White", 255, 255, 255],
                                  ["Light gray", 223, 223, 223],
                                  ["Black", 0, 0, 0]]
        self._background_color = self.background_colors[0]

        self.sync_zoom_options = [["Fit in a box (default)", 
                                    "Scale images to equally sized square boxes"],
                                   ["Width",
                                    "Scale images to be equally wide"],
                                   ["Height",
                                    "Scale images to be equally tall"],
                                   ["Pixel (relative size)",
                                    "Do not scale images (show with same pixel size)"]]
        self.sync_zoom_bys = ["box", "width", "height", "pixel"]
        self._sync_zoom_by = self.sync_zoom_bys[0]

        self.disable_right_click = False

    right_click_comment = QtCore.pyqtSignal(QtCore.QPointF)
    right_click_ruler = QtCore.pyqtSignal(QtCore.QPointF, str, str, float) # Scene position, relative origin position, unit, px-per-unit
    right_click_save_all_comments = QtCore.pyqtSignal()
    right_click_load_comments = QtCore.pyqtSignal()
    right_click_relative_origin_position = QtCore.pyqtSignal(str)
    changed_px_per_unit = QtCore.pyqtSignal(str, float) # Unit, px-per-unit
    right_click_single_transform_mode_smooth = QtCore.pyqtSignal(bool)
    right_click_all_transform_mode_smooth = QtCore.pyqtSignal(bool)
    right_click_background_color = QtCore.pyqtSignal(list)
    right_click_sync_zoom_by = QtCore.pyqtSignal(str)
    position_changed_qgraphicsitem = QtCore.pyqtSignal()
    right_click_crop = QtCore.pyqtSignal()  # New signal for crop functionality
    right_click_crop3D = QtCore.pyqtSignal()  # New signal for 3D crop functionality
    right_click_crop_sync = QtCore.pyqtSignal()  # 새로운 시그널 추가
    right_click_statistics = QtCore.pyqtSignal()  # New signal for statistics tool
    
    # Add new signal for profile line changes
    profile_line_changed = QtCore.pyqtSignal()

    def contextMenuEvent(self, event):
        """Override the event of the context menu (right-click menu)  to display options.

        Triggered when mouse is right-clicked on scene.

        Args:
            event (PyQt event for contextMenuEvent)
        """
        if self.disable_right_click:
            return
        
        what_menu_type = "View"

        scene_pos = event.scenePos()
        item = self.itemAt(scene_pos, self.views()[0].transform())

        action_delete = None
        menu_set_color = None
        action_set_color_red = None
        action_set_color_white = None
        action_set_color_blue = None
        action_set_color_green = None
        action_set_color_yellow = None
        action_set_color_black = None

        item_parent = item
        if item is not None:
            while item_parent.parentItem(): # Loop "upwards" to find parent item
                item_parent = item_parent.parentItem()
        
        if isinstance(item_parent, CommentItem) or isinstance(item_parent, RulerItem):
            action_delete = QtWidgets.QAction("Delete")

            if isinstance(item_parent, CommentItem):
                menu_set_color = QtWidgets.QMenu("Set comment color...")
                action_set_color_red = menu_set_color.addAction("Red")
                action_set_color_red.triggered.connect(lambda: item_parent.set_color("red"))
                action_set_color_white = menu_set_color.addAction("White")
                action_set_color_white.triggered.connect(lambda: item_parent.set_color("white"))
                action_set_color_blue = menu_set_color.addAction("Blue")
                action_set_color_blue.triggered.connect(lambda: item_parent.set_color("blue"))
                action_set_color_green = menu_set_color.addAction("Green")
                action_set_color_green.triggered.connect(lambda: item_parent.set_color("green"))
                action_set_color_yellow = menu_set_color.addAction("Yellow")
                action_set_color_yellow.triggered.connect(lambda: item_parent.set_color("yellow"))
                action_set_color_black = menu_set_color.addAction("Black")
                action_set_color_black.triggered.connect(lambda: item_parent.set_color("black"))

            action_delete.triggered.connect(lambda: self.removeItem(item_parent))

            what_menu_type = "Edit item(s)"

        menu = QtWidgets.QMenu()

        if what_menu_type == "Edit item(s)":
            if menu_set_color:
                menu.addMenu(menu_set_color)
            if action_delete:
                menu.addAction(action_delete) # action_delete.triggered.connect(lambda: self.removeItem(item.parentItem())) # = menu.addAction("Delete", self.removeItem(item.parentItem()))
        else:
            # Image section - comments and crop tools
            menu_image = QtWidgets.QMenu("Image")
            menu.addMenu(menu_image)
            
            # Add Info action
            action_info = menu_image.addAction("Info")
            action_info.setToolTip("Show image information")
            action_info.triggered.connect(self.show_image_info)
            
            action_comment = menu_image.addAction("Comment")
            action_comment.setToolTip("Add a draggable text comment here")
            action_comment.triggered.connect(lambda: self.right_click_comment.emit(scene_pos))
            
            # Add Tools menu
            menu_tools = QtWidgets.QMenu("Tools")
            menu.addMenu(menu_tools)
            
            # Add Profile action
            action_profile = menu_tools.addAction("Profile")
            action_profile.setToolTip("Draw a line to show pixel value profile")
            action_profile.triggered.connect(lambda: self.start_profile_tool(scene_pos))
            
            # Add Statistics action
            action_statistics = menu_tools.addAction("Statistics")
            action_statistics.setToolTip("Calculate statistics for a selected region")
            action_statistics.triggered.connect(lambda: self.right_click_statistics.emit())
            
            # Add crop action to Image menu
            action_crop = menu_image.addAction("Crop")
            action_crop.setToolTip("Crop the selected area of the image")
            action_crop.triggered.connect(lambda: self.right_click_crop.emit())

            # Add synchronized crop action to Image menu
            action_crop_sync = menu_image.addAction("Crop (Sync)")
            action_crop_sync.setToolTip("Crop the selected area in all open images")
            action_crop_sync.triggered.connect(lambda: self.right_click_crop_sync.emit())

            # Add 3D crop action to Image menu
            action_crop3D = menu_image.addAction("3D Crop")
            action_crop3D.setToolTip("Crop a volumetric selection across Z slices")
            action_crop3D.triggered.connect(lambda: self.right_click_crop3D.emit())

            menu_ruler = QtWidgets.QMenu("Measurement ruler...")
            menu_ruler.setToolTip("Add a ruler to measure distances and angles in this image window...")
            menu_ruler.setToolTipsVisible(True)
            menu.addMenu(menu_ruler)

            action_set_px_per_mm = menu_ruler.addAction("Set the ruler conversion factor for real distances (mm, cm)...")
            action_set_px_per_mm.triggered.connect(lambda: self.dialog_to_set_px_per_mm())

            menu_ruler.addSeparator()

            actions = []

            rulers = [
                ["Pixel", "pixels", "px"],
                ["Micrometer", "micrometers", "μm"],
                ["Millimeter", "millimeters", "mm"],
                ["Centimeter", "centimeters", "cm"],
                ["Meter", "meters", "m"],
                ["Inch", "inch", "in"],
                ["Foot", "feet", "ft"],
                ["Yard", "yards", "yd"],
            ]

            for i, ruler in enumerate(rulers):
                name = ruler[0]
                plural = ruler[1]
                abbv = ruler[2]
                actions.append(menu_ruler.addAction(f"{name} ruler"))
                actions[i].setToolTip(f"Add a ruler to measure distances in {plural}")
                actions[i].triggered.connect(lambda value,
                                             emitting=[scene_pos, self.relative_origin_position, abbv, self.px_per_unit]:
                                             self.right_click_ruler.emit(emitting[0], emitting[1], f"{emitting[2]}", emitting[3])) 
            
                if not self.px_per_unit_conversion_set and abbv != "px":
                    text_disclaimer = "(requires conversion to be set before using)"
                    tooltip_disclaimer = "To use this ruler, first set the ruler conversion factor"

                    actions[i].setEnabled(False)
                    actions[i].setText(actions[i].text() + " " + text_disclaimer)
                    actions[i].setToolTip(tooltip_disclaimer)

            menu_ruler.addSeparator()

            action_set_relative_origin_position_topleft = menu_ruler.addAction("Relative origin at top-left")
            action_set_relative_origin_position_topleft.triggered.connect(lambda: self.right_click_relative_origin_position.emit("topleft"))
            action_set_relative_origin_position_topleft.triggered.connect(lambda: self.set_relative_origin_position("topleft"))
            action_set_relative_origin_position_bottomleft = menu_ruler.addAction("Relative origin at bottom-left")
            action_set_relative_origin_position_bottomleft.triggered.connect(lambda: self.right_click_relative_origin_position.emit("bottomleft"))
            action_set_relative_origin_position_bottomleft.triggered.connect(lambda: self.set_relative_origin_position("bottomleft"))

            if self.relative_origin_position == "bottomleft":
                action_set_relative_origin_position_bottomleft.setCheckable(True)
                action_set_relative_origin_position_bottomleft.setChecked(True)
            elif self.relative_origin_position == "topleft": 
                action_set_relative_origin_position_topleft.setCheckable(True)
                action_set_relative_origin_position_topleft.setChecked(True)
            
            menu.addSeparator()

            action_save_all_comments = menu.addAction("Save all comments of this view (.csv)...")
            action_save_all_comments.triggered.connect(lambda: self.right_click_save_all_comments.emit())
            action_load_comments = menu.addAction("Load comments into this view (.csv)...")
            action_load_comments.triggered.connect(lambda: self.right_click_load_comments.emit())

            menu.addSeparator()

            menu_transform = QtWidgets.QMenu("Upsample when zoomed...")
            menu_transform.setToolTipsVisible(True)
            menu.addMenu(menu_transform)

            transform_on_tooltip_str = "Pixels are interpolated when zoomed in, rendering a smooth appearance"
            transform_off_tooltip_str = "Pixels are unchanged when zoomed in, rendering a true-to-pixel appearance"

            action_set_single_transform_mode_smooth_on = menu_transform.addAction("On")
            action_set_single_transform_mode_smooth_on.setToolTip(transform_on_tooltip_str)
            action_set_single_transform_mode_smooth_on.triggered.connect(lambda: self.right_click_single_transform_mode_smooth.emit(True))
            action_set_single_transform_mode_smooth_on.triggered.connect(lambda: self.set_single_transform_mode_smooth(True))

            action_set_single_transform_mode_smooth_off = menu_transform.addAction("Off")
            action_set_single_transform_mode_smooth_off.setToolTip(transform_off_tooltip_str)
            action_set_single_transform_mode_smooth_off.triggered.connect(lambda: self.right_click_single_transform_mode_smooth.emit(False))
            action_set_single_transform_mode_smooth_off.triggered.connect(lambda: self.set_single_transform_mode_smooth(False))

            if self.single_transform_mode_smooth:
                action_set_single_transform_mode_smooth_on.setCheckable(True)
                action_set_single_transform_mode_smooth_on.setChecked(True)
            else:
                action_set_single_transform_mode_smooth_off.setCheckable(True)
                action_set_single_transform_mode_smooth_off.setChecked(True)

            menu_transform.addSeparator()

            action_set_all_transform_mode_smooth_on = menu_transform.addAction("Switch all on")
            action_set_all_transform_mode_smooth_on.setToolTip(transform_on_tooltip_str+" (applies to all windows)")
            action_set_all_transform_mode_smooth_on.triggered.connect(lambda: self.right_click_all_transform_mode_smooth.emit(True))
    
            action_set_all_transform_mode_smooth_off = menu_transform.addAction("Switch all off")
            action_set_all_transform_mode_smooth_off.setToolTip(transform_off_tooltip_str+" (applies to all windows)")
            action_set_all_transform_mode_smooth_off.triggered.connect(lambda: self.right_click_all_transform_mode_smooth.emit(False))

            menu.addSeparator()

            menu_background = QtWidgets.QMenu("Set background color...")
            menu_background.setToolTipsVisible(True)
            menu.addMenu(menu_background)

            for color in self.background_colors:
                descriptor = color[0]
                rgb = color[1:4]
                action_set_background = menu_background.addAction(descriptor)
                action_set_background.setToolTip("RGB " + ", ".join([str(channel) for channel in rgb]))
                action_set_background.triggered.connect(lambda value, color=color: self.right_click_background_color.emit(color))
                action_set_background.triggered.connect(lambda value, color=color: self.background_color_lambda(color))
                if color == self.background_color:
                    action_set_background.setCheckable(True)
                    action_set_background.setChecked(True)

            menu.addSeparator()

            menu_sync_zoom_by = QtWidgets.QMenu("Sync zoom by...")
            menu_sync_zoom_by.setToolTipsVisible(True)
            menu.addMenu(menu_sync_zoom_by)

            for i, option in enumerate(self.sync_zoom_options):
                descriptor = option[0]
                tooltip = option[1]
                by = self.sync_zoom_bys[i]
                action_sync_zoom_by = menu_sync_zoom_by.addAction(descriptor)
                action_sync_zoom_by.setToolTip(tooltip)
                action_sync_zoom_by.triggered.connect(lambda value, by=by: self.right_click_sync_zoom_by.emit(by))
                action_sync_zoom_by.triggered.connect(lambda value, by=by: self.sync_zoom_by_lambda(by))
                if by == self.sync_zoom_by:
                    action_sync_zoom_by.setCheckable(True)
                    action_sync_zoom_by.setChecked(True)



        menu.exec(event.screenPos())

    def set_relative_origin_position(self, string):
        """Set the descriptor of the position of the relative origin for rulers.

        Describes the coordinate orientation:
            "bottomleft" for Cartesian-style (positive X right, positive Y up)
            "topleft" for image-style (positive X right, positive Y down)
        
        Args:
            string (str): "topleft" or "bottomleft" for position of the origin for coordinate system of rulers.
        """
        self.relative_origin_position = string

    def set_single_transform_mode_smooth(self, boolean):
        """Set the descriptor of the status of smooth transform mode.

        Describes the transform mode of pixels on zoom:
            True for smooth (interpolated)
            False for non-smooth (non-interpolated)
        
        Args:
            boolean (bool): True for smooth; False for non-smooth.
        """
        self.single_transform_mode_smooth = boolean

    def dialog_to_set_px_per_mm(self):
        """Open the dialog for users to set the conversion for pixels to millimeters.
        
        Emits the value of the px-per-mm conversion if user clicks "Ok" on dialog.
        """        
        dialog_window = PixelUnitConversionInputDialog(unit="mm", px_conversion=self.px_conversion, unit_conversion=self.unit_conversion, px_per_unit=self.px_per_unit)
        dialog_window.setWindowModality(QtCore.Qt.ApplicationModal)
        if dialog_window.exec_() == QtWidgets.QDialog.Accepted:
            self.px_per_unit = dialog_window.px_per_unit
            if self.px_per_unit_conversion_set:
                self.changed_px_per_unit.emit("mm", self.px_per_unit)
            self.px_per_unit_conversion_set = True
            self.px_conversion = dialog_window.px_conversion
            self.unit_conversion = dialog_window.unit_conversion

    @property
    def background_color(self):
        """Current background color."""
        return self._background_color
    
    @background_color.setter
    def background_color(self, color):
        """Set color as list with descriptor and RGB values [str, r, g, b]."""
        self._background_color = color

    def background_color_lambda(self, color):
        """Within lambda, set color as list with descriptor and RGB values [str, r, g, b]."""
        self.background_color = color

    @property
    def background_rgb(self):
        """Current background color RGB [int, int, int]."""
        return self._background_color[1:4]
    
    @property
    def sync_zoom_by(self):
        """Current sync zoom by."""
        return self._sync_zoom_by
    
    @sync_zoom_by.setter
    def sync_zoom_by(self, by):
        """Set sync zoom by as str."""
        self._sync_zoom_by = by

    def sync_zoom_by_lambda(self, by):
        """Within lambda, set sync zoom by str."""
        self.sync_zoom_by = by

    def start_profile_tool(self, pos):
        """Start the profile tool at the given position.
        
        Args:
            pos: QPointF with initial position
        """
        if not self.in_profile_mode:
            self.in_profile_mode = True
            
            # Create initial line
            offset = 50  # Initial line length
            self.profile_line = ProfileLine(pos.x(), pos.y(), 
                                         pos.x() + offset, pos.y())
            self.addItem(self.profile_line)
            
            # Create profile dialog if it doesn't exist
            if not self.profile_dialog:
                self.profile_dialog = ProfileDialog()
                self.profile_line_changed.connect(self.update_profile)
            
            # Show dialog
            self.profile_dialog.show()
            
            # Synchronize line in other views
            self.sync_profile_line_to_all_views()
            
            # Update profile
            self.update_profile()
            
            # --- 추가: 모든 창의 그래프를 즉시 갱신 ---
            main_window = self.views()[0].window()
            if hasattr(main_window, '_mdiArea'):
                windows = main_window._mdiArea.subWindowList()
                for window in windows:
                    child = window.widget()
                    if hasattr(child, '_scene_main_topleft'):
                        scene = child._scene_main_topleft
                        if scene.profile_line and hasattr(scene.profile_line, 'handle1'):
                            scene.profile_line.handle1.update_all_profiles_in_views()
    
    def sync_profile_line_to_all_views(self):
        """Create synchronized profile lines in all other views."""
        if not self.profile_line:
            return
            
        # Get main window
        main_window = self.views()[0].window()
        if not hasattr(main_window, '_mdiArea'):
            return
            
        # Get all subwindows
        windows = main_window._mdiArea.subWindowList()
        
        # Get current line geometry
        line = self.profile_line.line()
        start_point = (line.x1(), line.y1())
        end_point = (line.x2(), line.y2())
        
        for window in windows:
            child = window.widget()
            if not child:
                continue
                
            # Get the scene
            if hasattr(child, '_scene_main_topleft'):
                scene = child._scene_main_topleft
                if scene != self and not scene.profile_line:  # Don't create in source scene
                    # Create synchronized line
                    scene.profile_line = ProfileLine(start_point[0], start_point[1],
                                                   end_point[0], end_point[1])
                    scene.addItem(scene.profile_line)
                    scene.in_profile_mode = True
                    
                    # Share the same profile dialog
                    scene.profile_dialog = self.profile_dialog
                    scene.profile_line_changed.connect(scene.update_profile)
    
    def sync_profile_line_position(self, source_line):
        """Synchronize profile line position to all other views.
        
        Args:
            source_line: The ProfileLine that was moved/changed
        """
        # Get main window
        main_window = self.views()[0].window()
        if not hasattr(main_window, '_mdiArea'):
            return
            
        # Get all subwindows
        windows = main_window._mdiArea.subWindowList()
        
        # Get source line geometry
        line = source_line.line()
        
        for window in windows:
            child = window.widget()
            if not child:
                continue
                
            # Get the scene
            if hasattr(child, '_scene_main_topleft'):
                scene = child._scene_main_topleft
                if scene != self and scene.profile_line:  # Update only other scenes with profile lines
                    # Update line position
                    scene.profile_line.setLine(line)
                    scene.profile_line.updateHandles()
    
    def update_profile(self):
        """Update the profile display."""
        if not self.profile_line or not self.profile_dialog:
            return
            
        # Get line endpoints in scene coordinates
        line = self.profile_line.line()
        start_point = (line.x1(), line.y1())
        end_point = (line.x2(), line.y2())
        
        # Get all views
        profiles = []
        labels = []
        
        # Get main window
        main_window = self.views()[0].window()
        if hasattr(main_window, '_mdiArea'):
            # Get all subwindows
            windows = main_window._mdiArea.subWindowList()
            
            for window in windows:
                child = window.widget()
                if not child:
                    continue
                
                # Get the image data
                if hasattr(child, '_pixmapItem_main_topleft'):
                    pixmap_item = child._pixmapItem_main_topleft
                    if not pixmap_item.pixmap().isNull():
                        # For volumetric data, we'll get the values directly in get_profile_values
                        # For regular images, convert QPixmap to numpy array
                        image = None
                        if not (hasattr(child, 'is_volumetric') and child.is_volumetric):
                            image = pixmap_item.pixmap().toImage()
                            width = image.width()
                            height = image.height()
                            ptr = image.bits()
                            ptr.setsize(height * width * 4)
                            image = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
                        elif hasattr(child, 'volumetric_handler'):
                            # Use tifffile for volumetric data
                            try:
                                import tifffile
                                with tifffile.TiffFile(child.volumetric_handler.filepath) as tif:
                                    current_slice = getattr(child, 'current_slice', 0)
                                    image = tif.series[0].pages[current_slice].asarray()
                            except Exception as e:
                                logger.error(f"Error reading volumetric data with tifffile: {e}")
                                image = None
                        
                        # Get profile values with scene and pixmap_item for coordinate transformation
                        profile = get_profile_values(image, start_point, end_point, 
                                                   scene=self, pixmap_item=pixmap_item)
                        
                        if profile[0] is not None:  # Only add if we got valid values
                            profiles.append(profile)
                            labels.append(os.path.basename(child.currentFile))
        
        # Update profile dialog
        if profiles:
            self.profile_dialog.update_profile(profiles, labels)
    
    def cleanup_profile_tool(self):
        """Clean up profile tool resources."""
        # Get main window
        main_window = self.views()[0].window()
        if hasattr(main_window, '_mdiArea'):
            # Clean up profile lines in all views
            windows = main_window._mdiArea.subWindowList()
            for window in windows:
                child = window.widget()
                if not child:
                    continue
                    
                if hasattr(child, '_scene_main_topleft'):
                    scene = child._scene_main_topleft
                    if scene.profile_line:
                        scene.removeItem(scene.profile_line)
                        scene.profile_line = None
                        scene.in_profile_mode = False
        
        # Close profile dialog
        try:
            if self.profile_dialog:
                self.profile_dialog.close()
                self.profile_dialog = None
        except:
            pass

    def show_image_info(self):
        """Show the image information dialog for the current image."""
        # Get the current file path from the view
        view = self.views()[0]
        if view and view.window():
            window = view.window()
            if hasattr(window, 'activeMdiChild') and window.activeMdiChild:
                current_file = window.activeMdiChild.currentFile
                if current_file:
                    dialog = ImageInfoDialog(current_file, window)
                    dialog.exec_()