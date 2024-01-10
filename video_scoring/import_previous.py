"""
This class holds a dialog that allows the user to import the old monolithic settings file for version 0.1.2 into the new project settings format.

WILL BE DEPRECATED IN FUTURE VERSIONS IN VERSION 0.2.1

WILL BE REMOVED IN VERSION 0.3.0

"""

import sys

from qtpy import QtCore, QtGui, QtWidgets


class ImportPreviousSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, old_settings: dict):
        super().__init__(parent)
        self.old_settings = old_settings
        self.setWindowTitle("Import Previous Settings")
        self.setWindowFlags(
            self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.setFixedWidth(500)
        self.setFixedHeight(300)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().setSpacing(10)

        # a rich text label that explains what is happening
        self.explanation = QtWidgets.QLabel()
        self.explanation.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.explanation.setText(self.populate_explanation())
        self.layout().addWidget(self.explanation)

        self.project_name = QtWidgets.QLineEdit()
        self.project_name.setPlaceholderText(
            old_settings.get("project_name", "Project Name")
        )
        self.layout().addWidget(self.project_name)

        self.file_location = QtWidgets.QLineEdit()
        self.file_location.setPlaceholderText(
            old_settings.get("settings_file_location", "Project File Location")
        )
        self.layout().addWidget(self.file_location)

        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.setStandardButtons(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout().addWidget(self.button_box)

    def input_validated(self):
        import os

        if self.project_name.text() == "":
            self.project_name.setStyleSheet("border: 1px solid red;")
            return False
        if self.file_location.text() == "":
            self.file_location.setStyleSheet("border: 1px solid red;")
            return False
        if not os.path.exists(self.file_location.text()):
            self.file_location.setStyleSheet("border: 1px solid red;")
            return False
        return True

    def accept(self):
        self.project_name.setStyleSheet("")
        self.file_location.setStyleSheet("")
        if self.input_validated():
            super().accept()

    def populate_explanation(self):
        return f"""
<h3>Import Previous Settings</h3>
<p>
    You are importing a previous settings file from version 0.1.2 or earlier.
    This file contains all of the settings for the project including the video file location.
    You will need to select a location for the project file and the video file.
</p>
<p>
    <b>Project Name</b><br>
    The name of the project. This will be used as the name of the project file.
</p>
<p>
    <b>Project File Location</b><br>
    The location to save the project file. This will be used to save the project file.
</p>
"""
