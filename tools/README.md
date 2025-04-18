# Butterfly Viewer Tools

This directory contains utility scripts for development, testing, and sample data generation for the Butterfly Viewer application.

## Volumetric Tester Utility

The `volumetric_tester.py` script provides a standalone utility for testing the `VolumetricImageHandler` class and working with multi-page TIFF files. It allows you to:

- Open multi-page TIFF files via a file dialog or command line argument
- View individual slices of the volumetric image
- Navigate through slices using a slider or keyboard shortcuts
- Adjust display range for normalization of high bit-depth images
- Force a specific normalization range for all slices

### Usage

Run the utility with:

```
python tools/volumetric_tester.py [filepath]
```

Where `[filepath]` is an optional path to a multi-page TIFF file to open. If not provided, you can open a file through the application's "Open" menu option.

### Keyboard Shortcuts

- Left/Right Arrows: Navigate to previous/next slice
- Home/End: Jump to first/last slice
- +/- Keys: Adjust maximum display range
- Ctrl++/Ctrl+-: Adjust minimum display range
- R: Reset display range to original detected values
- F: Force current display range for all slices

### Normalization Features

The utility supports two normalization modes:

1. **Auto Range**: Each slice is normalized based on its actual data range (default)
2. **Global Range**: All slices use the same normalization range, detected from analyzing all slices
3. **Forced Range**: Manually set a specific range that will be used for all slices

These options help visualize volumetric data consistently across slices and enhance visibility of features in high bit-depth images.

### Requirements

- Python 3.6+
- PyQt5
- Pillow (PIL)
- NumPy

## Other Tools

### create_sample_volumetric.py

Generates a sample multi-page TIFF file with configurable parameters for testing purposes.

### create_and_view_volumetric.py

Combines both tools above - creates a sample multi-page TIFF file and immediately opens it in the volumetric tester utility. This is useful for quick testing of the volumetric image handling functionality.

Usage:
```
python tools/create_and_view_volumetric.py [--output PATH] [--slices NUM] [--width WIDTH] [--height HEIGHT] [--no-text] [--silent]
```

For more detailed usage information, run any script with the `--help` flag. 