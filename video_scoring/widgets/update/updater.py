# this is a class that is used to update the application
# it will look for the latest release on github and compare it to the current version
# if it finds a newer version, it will ask the user if they want to update
# if they do, it will download the latest release into a temporary directory and run the installer

import logging
import os
import sys
import markdown2
import traceback as tb
from pathlib import Path
from zipfile import ZipFile

import requests
from qtpy.QtCore import Qt, QThread, Signal, Slot
from qtpy.QtWidgets import QApplication, QMessageBox, QPushButton, QDialog
from qtpy import QtWidgets, QtGui, QtCore
from video_scoring.main import __version__ as VERSION


class UpdateCheck(QThread):
    update_available = Signal(dict)
    update_error = Signal(str)
    no_update = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.url = "https://api.github.com/repos/DannyAlas/qt-vid-score/releases/latest"

    def run(self):
        try:
            self.check_for_update()
        except Exception as e:
            self.update_error.emit(f"Error checking for update: {e}")

    def check_for_update(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            data = response.json()
            latest_version = data["tag_name"].strip("v")
            if latest_version != VERSION:
                self.update_available.emit(data)
            else:
                self.no_update.emit()
        except Exception as e:
            self.update_error.emit(f"Error checking for update: {e}")
class UpdateDialog(QDialog):
    def __init__(self, data:dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        # standart update icon
        self.data = data
        self.new_ver = self.data.get("tag_name").strip("v")

        # set the text of the dialog to ask the user if they want to update

        self.body = QtWidgets.QLabel()
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.body.setOpenExternalLinks(True)
        self.body.setText(f"""<h1>Update Available!!</h1>
Current Version: {VERSION}</h4>
New Version: {self.new_ver}
<br>
<h3>Would you like to update?</h3>
""")
        self.body.setContentsMargins(0, 0, 0, 0)
        self.accept_button = QPushButton("Update")
        self.accept_button.setFlat(False)
        self.accept_button.clicked.connect(self.accept)
        self.accept_button.setMinimumSize(QtCore.QSize(60, 20))
        self.reject_button = QPushButton("Later")
        self.reject_button.setFlat(False)
        self.reject_button.clicked.connect(self.reject)
        self.reject_button.setMinimumSize(QtCore.QSize(60, 20))
        self.show_release_notes_button = QPushButton("Show Release Notes")
        self.show_release_notes_button.clicked.connect(self.show_release_notes)
        self.show_release_notes_button.setFlat(True)
        # make it so when the user clicks the show release notes button, it will show the release notes but not close the dialog     
        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.addWidget(self.accept_button)
        self.button_layout.addWidget(self.reject_button)
        self.button_layout.addWidget(self.show_release_notes_button)
        self.accept_button.setDefault(True)
        self.accept_button.setAutoDefault(True)
        self.button_layout.addStretch()
        self.button_layout.setContentsMargins(10, 10, 10, 10)
        self.button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.body)
        self.scroll_area.setContentsMargins
        self.scroll_area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.scroll_area)
        self.layout.addLayout(self.button_layout)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self.layout)
        
        if hasattr(self, "hide_release_notes_button"):
            self.hide_release_notes_button.hide()
            
    def show_release_notes(self):
        self.show()
        self.body.setText(f"""<h1>Update Available!!</h1>
Current Version: {VERSION}
New Version: {self.new_ver}
<br>
{markdown2.markdown(self.data.get('body'))}
<br>
<h3>Would you like to update?</h3>""")
        self.show_release_notes_button.hide()
        # resize the dialog to fit the release notes
        self.resize(QtCore.QSize(500, 500))
        if hasattr(self, "hide_release_notes_button"):
            self.hide_release_notes_button.show()
        else:
            self.hide_release_notes_button = QPushButton("Hide Release Notes")
            self.hide_release_notes_button.setFlat(True)
            self.button_layout.addWidget(self.hide_release_notes_button)
            self.hide_release_notes_button.clicked.connect(self.hide_release_notes)
        
    def hide_release_notes(self):
        self.show()
        self.body.setText(f"""<h2>Update Available</h2>
<br>
<h3>Current Version: {VERSION}</h3>
<h3>New Version: {self.new_ver}</h3>
<br>
<h3>Would you like to update?</h3>
""")
        self.hide_release_notes_button.hide()
        self.resize(QtCore.QSize(200, 200))
        if hasattr(self, "show_release_notes_button"):
            self.show_release_notes_button.show()
        else:
            self.show_release_notes_button = QPushButton("Show Release Notes")
            self.show_release_notes_button.setFlat(True)
            self.button_layout.addWidget(self.show_release_notes_button)
            self.show_release_notes_button.clicked.connect(self.show_release_notes)


        