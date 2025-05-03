I'll analyze the current software and create a product requirements document. First, let me explore the codebase to understand the software structure and functionality.

Ran tool
Let me first look at the README to get an overview of the software.

Read file: README.md
Now, let's look at the main code files to understand the software functionality in more detail.

Ran tool
Let's look at the main butterfly_viewer.py file to understand the core functionality:

Read file: butterfly_viewer/butterfly_viewer.py
Let's look at the auxiliary components to understand the split view functionality which seems to be a key feature:

Read file: butterfly_viewer/aux_splitview.py
Let's also look at the environment file to understand the dependencies:

Read file: environment.yml
Let's also take a look at the installer directory to understand the installation process:

Ran tool

Read file: installer/butterfly_viewer.iss
Based on my analysis of the codebase, I'll now create a Product Requirements Document for Butterfly Viewer for Tomogram.

# Butterfly Viewer for Tomogram - Product Requirements Document

## 1. Introduction

### 1.1 Purpose
Butterfly Viewer is a desktop multi-image viewer specifically designed for comparing and analyzing tomogram images with features like sliding overlays, synchronized panning and zooming, and other specialized tools for visual comparison of local image files side by side.

### 1.2 Product Scope
Butterfly Viewer enables researchers and analysts to efficiently compare multiple images with identical resolutions, particularly useful for analyzing tomographic data and other imaging research. The application provides a comprehensive toolset for detailed comparison of images including X-rays, element maps, high-resolution photos, and other research data.

### 1.3 Target Users
- Scientific researchers working with tomographic data
- Art researchers and conservators analyzing paintings and artwork
- Professionals comparing multi-layered imaging data
- Anyone needing to analyze multiple aligned images with precision

## 2. Product Overview

### 2.1 Product Perspective
Butterfly Viewer is a standalone desktop application that works in conjunction with Butterfly Registrator (a separate tool for image alignment). It builds upon previous image viewing technology and extends it with specialized features for scientific and research image comparison.

### 2.2 Product Features
- **Sliding Overlays**: Up to 2x2 image layout with adjustable transparency
- **Synchronized Pan and Zoom**: All loaded images can be navigated simultaneously
- **Multiple Synchronization Modes**: Various ways to synchronize zoom across images
- **Auto-arranging Windows**: Automatic grid, column, or row arrangements
- **Drag and Drop Support**: Easy loading of images via drag and drop
- **Annotation Tools**: Comment and measurement tools with export capabilities
- **Configurable Interface**: Adjustable visibility of UI elements
- **Multiple File Format Support**: Handles PNG, JPEG, and TIFF file formats
- **Volumetric Image Support**: View and navigate through multi-page TIFF files as volumetric data with slice selection controls

### 2.3 User Classes and Characteristics
- **Primary Users**: Researchers and analysts with moderate technical background
- **Secondary Users**: General users interested in comparing multiple images
- **Operating Environment**: Windows and macOS platforms

### 2.4 Operating Environment
- Windows 10+ (executable installer)
- macOS (packaged application)
- Also available as Python source code for cross-platform use

### 2.5 Design and Implementation Constraints
- Developed using Python 3.6 and PyQt5
- Compatible with most types of PNG, JPEG, and TIFF files
- Input images for sliding overlays must have identical resolutions
- Volumetric images must be in multi-page TIFF format

## 3. System Features

### 3.1 Image Loading and Display
- Load multiple images through file dialog or drag-and-drop
- Display up to 2x2 images in a split view configuration
- Support for commonly used image formats (PNG, JPEG, TIFF)
- Support for multi-page TIFF files as volumetric data

### 3.2 Sliding Overlay Functionality
- Create sliding comparisons between up to four images
- Lock/unlock split position with keyboard shortcut (Shift+X)
- Adjust transparency of each overlay quadrant independently
- Set split position manually with sliders or mouse movement

### 3.3 Synchronized Navigation
- Pan and zoom multiple images simultaneously
- Different synchronization modes to accommodate various image sizes
- Optional independent navigation for each image window

### 3.4 Image Window Management
- Auto-arrange windows in grid, column, or row layouts
- Close individual windows or all windows
- Control window highlighting and labels

### 3.5 Annotation and Measurement Tools
- Add comments to specific points in images
- Create and position measurement rulers
- Save and load annotations to/from CSV files
- Configure coordinate system orientation (top-left or bottom-left origin)

### 3.6 User Interface Customization
- Toggle visibility of scrollbars, status bar, and interface elements
- Adjust background color
- Configure image rendering quality (smooth transform mode)

### 3.7 View Options
- Zoom in/out with mouse wheel or keyboard shortcuts
- Fit to window, width, or height
- View at actual size (1:1 pixel mapping)
- Support for fullscreen mode

### 3.8 Volumetric Image Navigation
- Automatic detection of multi-page TIFF files as volumetric data
- Display of slice count information from volumetric files
- Slice selection interface with slider and spinbox controls
- Ability to navigate through slices while maintaining current view state
- Initial loading of center slice for performance optimization
- Handling of mixed 2D and volumetric images in synchronized views

### 3.9 Image Information Display
- Display detailed metadata for the current image file through a dedicated dialog
- Show pixel dimensions (width x height)
- Display number of images for multi-page files (e.g., TIFF)
- Show pixel type information (bit depth, data type)
- Display number of channels
- Access through context menu under Image > Info
- Support for different image formats with varying metadata availability

## 4. External Interface Requirements

### 4.1 User Interfaces
- Main window with menu bar, status bar, and MDI area
- Split view controls for sliding overlay
- Transparency sliders for overlay adjustment
- Support for keyboard shortcuts for common operations
- Slice selection controls (slider and spinbox) for volumetric images

### 4.2 Hardware Interfaces
- Standard display with sufficient resolution for image comparison
- Mouse or trackpad for navigation and control
- Keyboard for shortcuts and commands

### 4.3 Software Interfaces
- Operating system: Windows 10+ or macOS
- Python 3.6+ and dependencies for source code version
- Related tool: Butterfly Registrator for image alignment

### 4.4 Communication Interfaces
- File system access for loading and saving images and annotations
- No network connectivity required

## 5. Non-Functional Requirements

### 5.1 Performance Requirements
- Fast loading and rendering of high-resolution images
- Smooth panning and zooming with synchronized views
- Efficient memory management for multiple large images
- On-demand loading of volumetric image slices for memory optimization

### 5.2 Safety Requirements
- No data loss or corruption during image viewing and annotation
- Confirmation prompts for potentially destructive operations

### 5.3 Security Requirements
- Local processing of all data (no external data transmission)
- Standard file system security for saved annotations

### 5.4 Software Quality Attributes
- Usability: Intuitive interface for image comparison
- Reliability: Stable operation with error handling
- Maintainability: Modular code structure for easier updates

## 6. Installation and Packaging

### 6.1 Windows Installation
- Provided as an executable installer (.exe)
- Uses Inno Setup for installation package
- Desktop shortcut option
- Standard application installation in Program Files

### 6.2 macOS Installation
- Provided as a macOS application bundle
- Standard drag-and-drop installation to Applications folder

### 6.3 Python Source Code Use
- Conda environment configuration provided
- Dependencies specified in environment.yml
- Instructions for running from source included in documentation

## 7. Volumetric Image Feature Specifications

### 7.1 File Support
- Support for multi-page TIFF files as volumetric data
- Automatic detection of volumetric files based on file information
- Specialized image loader for volumetric data files

### 7.2 Slice Information and Controls
- Extraction of slice count information from volumetric file metadata
- Display of slice range information in the user interface
- Slider control for visual selection of slices
- Spinbox control for precise numerical slice selection
- Initial loading of the center slice by default

### 7.3 Slice Navigation
- On-demand loading of slices to optimize performance
- Maintenance of current view state (zoom level, pan position) when changing slices
- UI feedback indicating current slice position within the volumetric data

### 7.4 Multi-View Integration
- Support for simultaneous viewing of multiple volumetric images
- Support for mixed viewing of 2D and volumetric images
- Display of black placeholder for images without corresponding slices at current Z position
- Synchronized slice navigation when possible
- Visual indication of slice mismatch between different volumetric images

### 7.5 Performance Considerations
- Lazy loading of slice data to minimize memory usage
- Caching of recently viewed slices for improved performance
- Progressive loading for large volumetric datasets

## 8. Future Enhancements
- Support for more than 2x2 split view configuration
- Enhanced ruler and measurement tools
- Integration with other imaging analysis tools
- Support for additional volumetric file formats beyond multi-page TIFF
- 3D reconstruction and volume rendering capabilities
- Cross-sectional views along different axes
- Advanced volumetric data visualization options
- Batch processing capabilities
- Remote collaboration features

## 9. Conclusion
Butterfly Viewer for Tomogram is a specialized image viewing application designed for researchers and analysts who need to compare multiple images with high precision. Its key differentiators are the sliding overlay functionality, synchronized navigation, annotation capabilities, and volumetric data support specifically tailored for scientific and research contexts.

# 3D Crop Feature Requirements

## Overview
The 3D Crop feature allows users to extract a specific XY region across multiple Z slices from volumetric data and save it as a multi-page TIFF file.

## Detailed Requirements

### User Interface
1. Add a new menu item "Crop (3D)" to the main menu
2. Implement a selection interface allowing users to:
   - Define a rectangular region in the XY plane
   - Adjust the position and size of the selected region
   - Navigate through Z slices while maintaining the XY selection
   - Specify start and end Z slices for the crop operation

### Functionality
1. When activated, allow users to draw a rectangular selection on the current view
2. Provide handles to resize and reposition the selection rectangle
3. Enable Z slice navigation during the selection process
4. Implement a dialog to:
   - Let users specify Z slice range (all slices or a specific range)
   - Choose output file path and filename
   - Confirm or cancel the crop operation

### Data Processing
1. Extract the selected XY region from each Z slice in the specified range
2. Use original data for extraction, not the displayed/processed view
3. Save the extracted data as a multi-page TIFF file

### Technical Requirements
1. Implement as a separate feature from the existing 2D crop functionality
2. Handle appropriate error conditions (file write errors, memory limitations)
3. Provide visual feedback during the extraction and saving process
4. Maintain UI responsiveness during processing of large datasets

## Success Criteria
1. Users can successfully select a 3D region (XY area across Z slices)
2. The cropped region can be saved as a multi-page TIFF
3. The saved file accurately represents the selected data from the original source

# Profile Tool Requirements

## Overview
The Profile Tool allows users to analyze pixel values along a user-defined line across images, enabling quantitative comparison of intensity profiles across multiple images.

## Detailed Requirements

### User Interface
1. Add a new menu item "Profile" under the Tools menu in the context menu
2. Implement a line drawing interface that allows users to:
   - Draw a line on the image by clicking and dragging
   - Adjust the line position using handles at both endpoints
   - See real-time updates of the profile as the line position changes

### Line Selection Tool
1. Interactive line drawing tool with:
   - Clear visual feedback during line drawing
   - Handles at both endpoints for adjustment
   - Ability to drag the entire line
   - Visual indication of the active line

### Profile Display
1. Graph window showing:
   - X-axis: Position along the line (in pixels)
   - Y-axis: Pixel values
   - Multiple profiles overlaid when multiple images are open
   - Different colors for each image's profile
   - Legend identifying each profile
2. Real-time updates when:
   - Line position is adjusted
   - Line endpoints are moved
   - Image content changes

### Multi-Image Support
1. Synchronized display of profiles from multiple images:
   - Same line position across all synchronized views
   - Overlaid profiles in the same graph for easy comparison
   - Consistent color coding between images and their profiles
2. Support for different image types:
   - Grayscale images
   - Color images (separate profiles for each channel)
   - Volumetric images (profile at current Z-slice)

### Technical Requirements
1. Efficient calculation of pixel values along the line using interpolation
2. Smooth updating of the profile display during line adjustments
3. Proper handling of image boundaries and out-of-bounds conditions
4. Support for high bit-depth images and different data types

### Export Capabilities
1. Ability to export profile data as CSV
2. Option to save profile graph as image
3. Copy profile data to clipboard

## Success Criteria
1. Users can easily draw and adjust profile lines
2. Profile display updates smoothly during line adjustments
3. Multiple profiles can be effectively compared
4. Profile data accurately represents image pixel values

## 10. Auto-Update System

### 10.1 Overview
The software includes an automatic update checking system that verifies the availability of new versions on startup and provides users with download links for updates.

### 10.2 Update Check Process
- Automatically check for updates when the application starts
- Compare current version with latest version from manifest file
- Notify users when a new version is available
- Provide direct download links to the new version

### 10.3 Update Distribution
- Software is distributed through Box.com
- Update checking uses a manifest file (JSON format) hosted online
- No direct Box.com API integration required

### 10.4 Manifest File Structure
The manifest file contains:
- Latest version number
- Download URL for the new version
- Release notes/update content description
- Other relevant metadata

### 10.5 User Interface
- Display update notification when new version is available
- Show current version and available version
- Provide option to:
  - Download the update
  - Skip this version
  - Remind later
- Display release notes/changes in the new version

### 10.6 Technical Requirements
- HTTP/HTTPS capability to fetch manifest file
- JSON parsing functionality
- Proper error handling for network issues
- Version comparison logic
- Non-blocking update check process
