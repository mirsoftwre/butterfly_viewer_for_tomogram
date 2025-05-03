#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Update checker module for Butterfly Viewer.
Checks for new versions using a manifest file and provides update information.
"""

import json
import urllib.request
import urllib.error
import re
from packaging import version
from PyQt5 import QtCore, QtWidgets, QtGui
import webbrowser

class UpdateChecker(QtCore.QObject):
    """Handles checking for software updates."""
    
    update_available = QtCore.pyqtSignal(str, str, str, str)  # version, download_url, release_notes, error
    
    def __init__(self, current_version, manifest_url, parent=None):
        """Initialize the update checker.
        
        Args:
            current_version (str): Current version of the software
            manifest_url (str): URL to the manifest file
            parent (QObject): Parent object
        """
        super().__init__(parent)
        self.current_version = current_version
        self.manifest_url = manifest_url
        
    def convert_box_shared_link(self, url):
        """Convert Box.com shared link to direct download URL.
        
        Args:
            url (str): Box.com shared link
            
        Returns:
            str: Direct download URL
        """
        # Extract shared ID from URL
        match = re.search(r'/s/([a-zA-Z0-9]+)', url)
        if match:
            shared_id = match.group(1)
            return f"https://tomocube.box.com/shared/static/{shared_id}"
        return url
        
    def check_for_updates(self):
        """Check for updates by fetching and parsing the manifest file."""
        try:
            # Convert Box.com shared link to direct download URL
            download_url = self.convert_box_shared_link(self.manifest_url)
            print(f"Checking for updates at: {download_url}")  # Debug log
            
            # Set up request with headers
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Referer': 'https://tomocube.box.com/'
            }
            request = urllib.request.Request(download_url, headers=headers)
            
            # Fetch manifest file
            try:
                with urllib.request.urlopen(request) as response:
                    content = response.read()
                    print(f"Received content: {content[:200]}...")  # Debug log
                    manifest_data = json.loads(content)
            except urllib.error.URLError as e:
                print(f"Network error: {e}")
                self.update_available.emit('', '', '', f"Network error: {e}")
                return
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                print(f"Content that failed to parse: {content}")
                self.update_available.emit('', '', '', f"Invalid manifest format: {e}")
                return
                
            latest_version = manifest_data.get('version')
            if not latest_version:
                print("No version found in manifest")
                self.update_available.emit('', '', '', "No version information in manifest")
                return
                
            download_url = manifest_data.get('download_url')
            if not download_url:
                print("No download URL found in manifest")
                self.update_available.emit('', '', '', "No download URL in manifest")
                return
                
            release_notes = manifest_data.get('release_notes', '')
            
            print(f"Current version: {self.current_version}")
            print(f"Latest version: {latest_version}")
            
            # Compare versions
            if version.parse(latest_version) > version.parse(self.current_version):
                print("Update available!")
                self.update_available.emit(latest_version, download_url, release_notes, '')
            else:
                print("No update needed")
                self.update_available.emit('', '', '', '')
                
        except Exception as e:
            print(f"Unexpected error during update check: {e}")
            self.update_available.emit('', '', '', str(e))

class UpdateDialog(QtWidgets.QDialog):
    """Dialog to show update information and options."""
    
    def __init__(self, current_version, new_version, download_url, release_notes, parent=None):
        """Initialize the update dialog.
        
        Args:
            current_version (str): Current version of the software
            new_version (str): Available new version
            download_url (str): URL to download the new version
            release_notes (str): Release notes for the new version
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        
        self.download_url = download_url
        
        self.setWindowTitle("Software Update Available")
        self.setMinimumWidth(400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Version information
        version_layout = QtWidgets.QHBoxLayout()
        version_layout.addWidget(QtWidgets.QLabel("Current version:"))
        version_layout.addWidget(QtWidgets.QLabel(current_version))
        layout.addLayout(version_layout)
        
        new_version_layout = QtWidgets.QHBoxLayout()
        new_version_layout.addWidget(QtWidgets.QLabel("New version:"))
        new_version_layout.addWidget(QtWidgets.QLabel(new_version))
        layout.addLayout(new_version_layout)
        
        # Release notes
        if release_notes:
            layout.addWidget(QtWidgets.QLabel("What's New:"))
            notes_text = QtWidgets.QTextEdit()
            notes_text.setPlainText(release_notes)
            notes_text.setReadOnly(True)
            notes_text.setMaximumHeight(150)
            layout.addWidget(notes_text)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        
        self.download_button = QtWidgets.QPushButton("Download Update")
        self.download_button.clicked.connect(self.download_update)
        button_box.addButton(self.download_button, QtWidgets.QDialogButtonBox.ActionRole)
        
        self.remind_button = QtWidgets.QPushButton("Remind Me Later")
        self.remind_button.clicked.connect(self.reject)
        button_box.addButton(self.remind_button, QtWidgets.QDialogButtonBox.RejectRole)
        
        self.skip_button = QtWidgets.QPushButton("Skip This Version")
        self.skip_button.clicked.connect(self.skip_version)
        button_box.addButton(self.skip_button, QtWidgets.QDialogButtonBox.RejectRole)
        
        layout.addWidget(button_box)
        
    def download_update(self):
        """Open the download URL in the default web browser."""
        webbrowser.open(self.download_url)
        self.accept()
        
    def skip_version(self):
        """Save the skipped version and close dialog."""
        # TODO: Implement version skip functionality
        self.reject() 