import json
import os
from typing import TYPE_CHECKING

import markdown2
import requests
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtWidgets import QDialog, QPushButton

from video_scoring.settings.base_settings import user_data_dir
from video_scoring.settings.settings import Settings
from video_scoring.widgets.progress import ProgressSignals

if TYPE_CHECKING:
    from video_scoring import MainWindow


class UpdateCheck(QThread):
    update_available = Signal(dict)
    update_error = Signal(str)
    no_update = Signal()

    def __init__(self, version):
        super().__init__()
        global VERSION
        VERSION = version
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
            # versioning is semantic versioning, check that the latest version is greater than the current version
            latest_version = tuple(map(int, latest_version.split(".")))
            current_version = tuple(map(int, VERSION.split(".")))
            if latest_version > current_version:
                self.update_available.emit(data)
            else:
                self.no_update.emit()
        except Exception as e:
            self.update_error.emit(f"Error checking for update: {e}")


class UpdateDialog(QDialog):
    accepted = Signal()

    def __init__(self, data: dict, parent=None):
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
        self.body.setText(
            f"""<h1>🔔 New Update Available!</h1>
🌟 Version {self.new_ver} Released
"""
        )
        self.body.setContentsMargins(0, 0, 0, 0)
        self.accept_button = QPushButton("Update")
        self.accept_button.setFlat(False)
        self.accept_button.clicked.connect(self.accept)
        self.accept_button.clicked.connect(self.accepted.emit)
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
        self.body.setText(
            f"""<h1>🔔 New Update Available!</h1>
🌟 Version {self.new_ver} Released
<br>
{markdown2.markdown(self.data.get('body'))}
"""
        )
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
        self.body.setText(
            f"""<h1>🔔 New Update Available!</h1>
🌟 Version {self.new_ver} Released
"""
        )
        self.hide_release_notes_button.hide()
        self.resize(QtCore.QSize(200, 200))
        if hasattr(self, "show_release_notes_button"):
            self.show_release_notes_button.show()
        else:
            self.show_release_notes_button = QPushButton("Show Release Notes")
            self.show_release_notes_button.setFlat(True)
            self.button_layout.addWidget(self.show_release_notes_button)
            self.show_release_notes_button.clicked.connect(self.show_release_notes)


class Updater(QThread):
    """
    This class is used to update the application. It will download the latest release from github and extract it into the appropriate directory.
    """

    update_error = Signal(str)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.data = data
        self.url = self.data.get("assets")[0].get(
            "browser_download_url"
        )  # [0] is the windows release
        self.version = self.data.get("tag_name").strip("v")
        self.install_dir = os.path.join(
            (os.environ.get("LOCALAPPDATA")), "Video Scoring", "installer"
        )
        if not os.path.exists(self.install_dir):
            os.makedirs(self.install_dir, exist_ok=True)
        self.installer_file = os.path.join(self.install_dir, self.url.split("/")[-1])
        self.progress_signals = ProgressSignals()

    def run(self):
        try:
            self.update()
        except Exception as e:
            self.update_error.emit(f"Error updating: {e}")
        self.progress_signals.complete.emit()

    def update(self):
        try:
            self.download()
        except Exception as e:
            self.update_error.emit(f"Error updating: {e}")

    def download(self):
        try:
            self.progress_signals.started.emit()
            response = requests.get(self.url, stream=True)
            response.raise_for_status()
            total_length = int(response.headers.get("content-length"))
            with open(self.installer_file, "wb") as f:
                dl = 0
                for data in response.iter_content(chunk_size=4096):
                    dl += len(data)
                    f.write(data)
                    self.progress_signals.progress.emit(int(dl / total_length * 100))
        except Exception as e:
            self.update_error.emit(f"Error downloading update: {e}")


class UpdatedDialog(QDialog):
    def __init__(self, version: str, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Complete")
        self.version = version
        self.main_win = main_win
        old_settings_file = os.path.join(
            os.path.dirname(user_data_dir()), "settings.json"
        )
        if os.path.exists(old_settings_file):
            with open(str(old_settings_file), "r") as file:
                old_settings = json.load(file)
            self._populate_migration_explanation(old_settings)
        else:
            self._populate_updated()

    def _populate_updated(self):
        self.body = QtWidgets.QTextBrowser()
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.body.setOpenExternalLinks(True)
        self.body.setText(
            f"""<h1>🌟 Update Complete!</h1>
<p>
    ✨ You are now running version {self.version}.
</p>
<p>
    <a href="https://github.com/DannyAlas/qt-vid-score/releases/latest">View the changelog</a>
</p>
"""
        )
        self.body.setContentsMargins(0, 0, 0, 0)
        self.accept_button = QPushButton("Ok")
        self.accept_button.setFlat(False)
        self.accept_button.clicked.connect(self.accept)
        self.accept_button.setMinimumSize(QtCore.QSize(60, 20))
        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.addWidget(self.accept_button)
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

    def get_file_location(self, location: str = "~"):
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDirectory(os.path.expanduser("~"))
        file_dialog.setNameFilter("Video Scoring Archive (*.vsap)")
        file_dialog.setDefaultSuffix("vsap")
        file_dialog.setLabelText(QtWidgets.QFileDialog.DialogLabel.Accept, "Import")
        file_dialog.setLabelText(QtWidgets.QFileDialog.DialogLabel.Reject, "Cancel")

        if os.path.exists(location):
            file_dialog.setDirectory(location)

        if file_dialog.exec():
            return file_dialog.selectedFiles()[0]
        else:
            return ""

    def _populate_migration_explanation(self, old_settings: dict):
        self.explanation = QtWidgets.QLabel()
        self.explanation.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.explanation.setText(self.populate_explanation())

        self.project_name_label = QtWidgets.QLabel("Project Name")
        self.project_name = QtWidgets.QLineEdit()
        self.project_name.setPlaceholderText(
            old_settings.get("project_name", "Project Name")
        )

        self.file_location_label = QtWidgets.QLabel("Project File Location")
        self.file_location = QtWidgets.QLineEdit()
        self.file_location.setPlaceholderText(
            old_settings.get("settings_file_location", "Project File Location")
        )
        self.file_location.mousePressEvent = lambda _: self.file_location.setText(
            self.get_file_location(self.file_location.text())
        )

        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.setStandardButtons(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText(
            "Import"
        )
        self.button_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        ).setText("Don't Import")
        self.button_box.accepted.connect(lambda: self.import_old_settings(old_settings))
        self.button_box.rejected.connect(self.reject)

        self.layout = QtWidgets.QGridLayout()
        self.layout.addWidget(self.explanation, 0, 0, 1, 2)
        self.layout.addWidget(self.project_name_label, 1, 0)
        self.layout.addWidget(self.project_name, 1, 1)
        self.layout.addWidget(self.file_location_label, 2, 0)
        self.layout.addWidget(self.file_location, 2, 1)
        self.layout.addWidget(self.button_box, 3, 0, 1, 2)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.layout)

    def import_old_settings(self, old_settings):

        self.project_name.setStyleSheet("")
        self.file_location.setStyleSheet("")
        if self.input_validated():
            new_prj = Settings(self.main_win).migrate_from_old_settings(
                old_settings=old_settings,
                new_name=self.project_name.text(),
                new_location=self.file_location.text(),
            )
            self.main_win.app_settings.projects.append(
                (new_prj.uid, new_prj.file_location)
            )
            self.main_win.projects_w.add_projects()
            self.accept()

    def input_validated(self):
        if self.project_name.text() == "":
            self.project_name.setStyleSheet("border: 1px solid red;")
            return False
        if self.file_location.text() == "":
            self.file_location.setStyleSheet("border: 1px solid red;")
            return False
        if not os.path.exists(os.path.dirname(self.file_location.text())):
            self.file_location.setStyleSheet("border: 1px solid red;")
            return False
        return True

    def populate_explanation(self):
        return f"""<h1>🌟 Update Complete!</h1>
<h2>
    ✨ You are now running version {self.version}.
</h2>
<p>
    <a href="https://github.com/DannyAlas/qt-vid-score/releases/latest">View the changelog</a>
</p>
---
<h3>
    We found a settings file that uses the old projects format. 
</h3>
<h3>
    To import it please give it a name and location
</h3>
</br>
"""
