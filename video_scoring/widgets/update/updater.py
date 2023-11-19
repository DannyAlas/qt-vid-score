# this is a class that is used to update the application
# it will look for the latest release on github and compare it to the current version
# if it finds a newer version, it will ask the user if they want to update
# if they do, it will download the latest release into a temporary directory and run the installer

import logging
import os
import sys
import tempfile
import traceback as tb
from pathlib import Path
from zipfile import ZipFile

import requests
from qtpy.QtCore import Qt, QThread, Signal, Slot
from qtpy.QtWidgets import QApplication, QMessageBox, QProgressDialog

from video_scoring import __version__ as VERSION


class Updater(QThread):
    update_available = Signal(str)
    update_error = Signal(str)
    update_download_progress = Signal(int)
    update_download_complete = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.url = "https://api.github.com/repos/DannyAlas/vid-scoring/releases/latest"

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
                self.update_available.emit(latest_version)
        except Exception as e:
            self.update_error.emit(f"Error checking for update: {e}")

    @Slot(str)
    def download_update(self, version):
        try:
            self.update_download_progress.emit(0)
            # get os
            if sys.platform.startswith("win"):
                _os = "windows"
            elif sys.platform.startswith("darwin"):
                _os = "mac"
            elif sys.platform.startswith("linux"):
                _os = "linux"
            else:
                raise Exception(f"Unsupported OS: {sys.platform}")
            # get arch
            if sys.maxsize > 2**32:
                arch = "64"
            else:
                arch = "32"
            # get download url
            response = requests.get(self.url)
            response.raise_for_status()
            data = response.json()
            for asset in data["assets"]:
                if asset["name"].startswith(f"VideoScoring-{version}-{_os}-{arch}"):
                    download_url = asset["browser_download_url"]
                    break
            else:
                raise Exception(f"Could not find download url for {_os} {arch}")
            # download file
            self.update_download_progress.emit(5)
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            total_length = int(response.headers.get("content-length"))
            downloaded = 0
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = Path(temp_dir) / "VideoScoring.zip"
                with open(temp_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        downloaded += len(chunk)
                        f.write(chunk)
                        self.update_download_progress.emit(
                            int(downloaded / total_length * 90)
                        )
                # extract file
                self.update_download_progress.emit(95)
                with ZipFile(temp_file) as zf:
                    zf.extractall(temp_dir)
                # run installer
                self.update_download_progress.emit(100)
                installer = Path(temp_dir) / "VideoScoring" / "installer.py"
                os.system(f"python {installer}")
            self.update_download_complete.emit()
        except Exception as e:
            self.update_error.emit(f"Error downloading update: {e}")
