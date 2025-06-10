#!/usr/bin/env python3

"""TIFF File Analyzer

A command-line tool to analyze TIFF files and output their metadata to a text file.
Supports both regular TIFF and BigTIFF formats.

Usage:
    python tiff_analyzer.py <tiff_file> [output_file]

If output_file is not specified, the output will be saved as <tiff_file>_analysis.txt
"""

import os
import sys
import argparse
import logging
from datetime import datetime
import numpy as np
import tifffile
from PIL import Image, TiffTags

def analyze_tiff_file(tiff_path, output_path=None):
    """Analyze a TIFF file and output its metadata to a text file.
    
    Args:
        tiff_path (str): Path to the TIFF file
        output_path (str, optional): Path to save the analysis output
    """
    if not os.path.exists(tiff_path):
        print(f"Error: File not found: {tiff_path}")
        return False
        
    if not tiff_path.lower().endswith(('.tif', '.tiff')):
        print(f"Error: Not a TIFF file: {tiff_path}")
        return False
    
    # Set default output path if not specified
    if output_path is None:
        base_name = os.path.splitext(tiff_path)[0]
        output_path = f"{base_name}_analysis.txt"
    
    try:
        # Open the output file
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header
            f.write("TIFF File Analysis Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"File: {tiff_path}\n")
            f.write(f"File Size: {os.path.getsize(tiff_path):,} bytes\n\n")
            
            # Analyze with tifffile
            with tifffile.TiffFile(tiff_path) as tif:
                # Basic TIFF information
                f.write("Basic TIFF Information\n")
                f.write("-" * 30 + "\n")
                f.write(f"BigTIFF: {'Yes' if tif.is_bigtiff else 'No'}\n")
                f.write(f"Byte Order: {tif.byteorder}\n")
                f.write(f"Number of Series: {len(tif.series)}\n\n")
                
                # Analyze each series
                for i, series in enumerate(tif.series):
                    f.write(f"Series {i+1}\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"Shape: {series.shape}\n")
                    f.write(f"Data Type: {series.dtype}\n")
                    f.write(f"Axes: {series.axes}\n")
                    f.write(f"Number of Pages: {len(series.pages)}\n")
                    
                    # Get page information
                    if len(series.pages) > 0:
                        page = series.pages[0]
                        f.write("\nFirst Page Information:\n")
                        
                        # Get resolution if available
                        try:
                            if hasattr(page, 'resolution'):
                                f.write(f"  Resolution: {page.resolution}\n")
                        except:
                            pass
                            
                        # Get compression if available
                        try:
                            if hasattr(page, 'compression'):
                                f.write(f"  Compression: {page.compression}\n")
                        except:
                            pass
                            
                        # Get photometric if available
                        try:
                            if hasattr(page, 'photometric'):
                                f.write(f"  Photometric: {page.photometric}\n")
                        except:
                            pass
                            
                        # Get planar configuration if available
                        try:
                            if hasattr(page, 'planarconfig'):
                                f.write(f"  Planar Configuration: {page.planarconfig}\n")
                        except:
                            pass
                            
                        # Get bits per sample if available
                        try:
                            if hasattr(page, 'bitspersample'):
                                f.write(f"  Bits Per Sample: {page.bitspersample}\n")
                        except:
                            pass
                            
                        # Get samples per pixel if available
                        try:
                            if hasattr(page, 'samplesperpixel'):
                                f.write(f"  Samples Per Pixel: {page.samplesperpixel}\n")
                        except:
                            pass
                        
                        # Additional TIFF tags
                        f.write("\nAdditional TIFF Tags:\n")
                        for tag in page.tags:
                            try:
                                tag_name = TiffTags.TAGS.get(tag.code, f"Unknown Tag {tag.code}")
                                f.write(f"  {tag_name}: {tag.value}\n")
                            except:
                                continue
                    
                    f.write("\n")
                
                # Memory usage estimation
                if len(tif.series) > 0:
                    series = tif.series[0]
                    dtype_size = np.dtype(series.dtype).itemsize
                    total_size = np.prod(series.shape) * dtype_size
                    f.write("Memory Usage Estimation\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"Data Type Size: {dtype_size} bytes\n")
                    f.write(f"Total Size: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)\n\n")
            
            # Additional analysis with PIL
            try:
                with Image.open(tiff_path) as img:
                    f.write("PIL Image Information\n")
                    f.write("-" * 30 + "\n")
                    f.write(f"Format: {img.format}\n")
                    f.write(f"Mode: {img.mode}\n")
                    f.write(f"Size: {img.size}\n")
                    # EXIF data if available
                    if hasattr(img, '_getexif') and img._getexif():
                        f.write("\nEXIF Data:\n")
                        for tag_id, value in img._getexif().items():
                            try:
                                tag_name = TiffTags.TAGS.get(tag_id, f"Unknown Tag {tag_id}")
                                f.write(f"  {tag_name}: {value}\n")
                            except:
                                continue
            except Exception as pil_error:
                f.write("\n[PIL] Could not open file with Pillow. Reason: {}\n".format(pil_error))
            
            print(f"Analysis complete. Results saved to: {output_path}")
            return True
            
    except Exception as e:
        print(f"Error analyzing TIFF file: {e}")
        return False

def main():
    """Main entry point for the TIFF analyzer."""
    parser = argparse.ArgumentParser(description="Analyze TIFF files and output metadata to a text file.")
    parser.add_argument("tiff_file", help="Path to the TIFF file to analyze")
    parser.add_argument("output_file", nargs="?", help="Path to save the analysis output (optional)")
    
    args = parser.parse_args()
    
    if not analyze_tiff_file(args.tiff_file, args.output_file):
        sys.exit(1)

if __name__ == "__main__":
    main() 