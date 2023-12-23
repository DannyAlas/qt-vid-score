import datetime
from uuid import uuid4
from typing import Optional
from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QDropEvent, QPaintEvent
from PyQt6.QtWidgets import QTreeWidgetItem
from qtpy import QtCore, QtGui, QtWidgets
import sys 


import json
import logging
from video_scoring.settings import ProjectSettings, ApplicationSettings
import sys
from uuid import uuid4, UUID

log = logging.getLogger()

class Settings:

    def __init__(self):
        self.app_settings = ApplicationSettings()
        self.qt_settings = QtCore.QSettings("Root Lab", "Video Scoring")
        self.load_settings_file()

    def get_project(self, uid: uuid4):
        # TODO: switch to sacing project files as a tuple of (uid, file_location) so that we don't have to search through all the files to find the one we want
        for project_t in self.app_settings.projects:
            if str(project_t[0]) == str(uid):
                project = ProjectSettings()
                project.load_from_file(project_t[1])
                return project

    def load_settings_file(self, file_location: Optional[str] = None):
        if file_location is None:
            latest_project_location = self.qt_settings.value("application_settings_location")
        else:
            latest_project_location = file_location

        if latest_project_location is not None:
            try:
                self.app_settings.load(latest_project_location)
            except Exception as e:
                log.error(f"Error loading settings file: {e}")
                # create a new settings file
                self.app_settings = ApplicationSettings()
                
            self.qt_settings.setValue("application_settings_location", latest_project_location)

    def save_settings_file(self, file_location: Optional[str] = None):
        if file_location is None:
            latest_project_location = self.qt_settings.value("application_settings_location")
        else:
            latest_project_location = file_location

        if latest_project_location is not None:
            self.app_settings.save(latest_project_location)
            self.qt_settings.setValue("application_settings_location", latest_project_location)


