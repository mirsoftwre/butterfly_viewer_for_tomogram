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
import time

class UpdateChecker(QtCore.QObject):
    """Handles checking for software updates."""
    
    update_available = QtCore.pyqtSignal(str, str, list, str)  # version, download_url, update_history, error
    
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
        self.settings = QtCore.QSettings()
        
    def should_check_update(self):
        """Check if enough time has passed since the last update check.
        
        Returns:
            bool: True if should check for updates, False otherwise
        """
        last_check = self.settings.value('last_update_check', 0, type=float)
        current_time = time.time()
        # Check if 6 hours (21600 seconds) have passed
        return (current_time - last_check) >= 21600
        
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
        # Check if we should perform the update check
        if not self.should_check_update():
            print("Skipping update check - less than 6 hours since last check")
            return
            
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
                self.update_available.emit('', '', [], f"Network error: {e}")
                return
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                print(f"Content that failed to parse: {content}")
                self.update_available.emit('', '', [], f"Invalid manifest format: {e}")
                return
                
            latest_version = manifest_data.get('latest_version')
            if not latest_version:
                print("No version found in manifest")
                self.update_available.emit('', '', [], "No version information in manifest")
                return
                
            # Get download URL from the latest version in update_history
            latest_version_info = next(
                (item for item in manifest_data.get('update_history', []) 
                 if item['version'] == latest_version),
                None
            )
            download_url = latest_version_info['download_url'] if latest_version_info else None
            if not download_url:
                print("No download URL found for latest version")
                self.update_available.emit('', '', [], "No download URL for latest version")
                return
                
            update_history = manifest_data.get('update_history', [])
            
            print(f"Current version: {self.current_version}")
            print(f"Latest version: {latest_version}")
            
            # Save the current time as last check time
            self.settings.setValue('last_update_check', time.time())
            
            # Compare versions
            if version.parse(latest_version) > version.parse(self.current_version):
                print("Update available!")
                # Filter update history to only show versions newer than current version
                relevant_updates = [
                    update for update in update_history 
                    if version.parse(update['version']) > version.parse(self.current_version)
                ]
                relevant_updates.sort(key=lambda x: version.parse(x['version']), reverse=True)
                self.update_available.emit(latest_version, download_url, relevant_updates, '')
            else:
                print("No update needed")
                self.update_available.emit('', '', [], '')
                
        except Exception as e:
            print(f"Unexpected error during update check: {e}")
            self.update_available.emit('', '', [], str(e))

class UpdateDialog(QtWidgets.QDialog):
    """Dialog to show update information and options."""
    
    def __init__(self, current_version, new_version, download_url, update_history, parent=None):
        """Initialize the update dialog.
        
        Args:
            current_version (str): Current version of the software
            new_version (str): Available new version
            download_url (str): URL to download the new version
            update_history (list): List of update history entries
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        
        self.download_url = download_url
        
        self.setWindowTitle("Software Update Available")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # Version information
        version_info = QtWidgets.QWidget()
        version_layout = QtWidgets.QGridLayout(version_info)
        
        version_layout.addWidget(QtWidgets.QLabel("Current version:"), 0, 0)
        version_layout.addWidget(QtWidgets.QLabel(current_version), 0, 1)
        version_layout.addWidget(QtWidgets.QLabel("New version:"), 1, 0)
        version_layout.addWidget(QtWidgets.QLabel(new_version), 1, 1)
        
        layout.addWidget(version_info)
        
        # Update history
        if update_history:
            layout.addWidget(QtWidgets.QLabel("Update History:"))
            history_text = QtWidgets.QTextEdit()
            history_content = ""
            
            for update in update_history:
                history_content += f"Version {update['version']} ({update['release_date']})\n"
                for change in update['changes']:
                    history_content += f"• {change}\n"
                history_content += "\n"
            
            history_text.setPlainText(history_content)
            history_text.setReadOnly(True)
            layout.addWidget(history_text)
        
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