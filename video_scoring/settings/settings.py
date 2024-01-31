import logging
import os
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

import logtail
import sentry_sdk
from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QDropEvent, QPaintEvent
from PyQt6.QtWidgets import QTreeWidgetItem
from qtpy import QtCore, QtGui, QtWidgets

from video_scoring.settings import ApplicationSettings, ProjectSettings
from video_scoring.utils import user_data_dir

if TYPE_CHECKING:
    from video_scoring import MainWindow

log = logging.getLogger("video_scoring")


class Settings:
    def __init__(self, main_window: "MainWindow"):
        self.main_win = main_window
        self.app_settings = ApplicationSettings()
        self.qt_settings = QtCore.QSettings("Root Lab", "Video Scoring")
        self.load_settings_file()
        sentry_sdk.set_context("application_settings", self.app_settings.model_dump())

    def get_project(self, uid: uuid4):
        for project_t in self.app_settings.projects:
            if str(project_t[0]) == str(uid):
                project = ProjectSettings()
                project.load_from_file(project_t[1])
                return project

    def load_settings_file(self, file_location: Optional[str] = None):
        if file_location is None:
            app_settings_location = user_data_dir("settings.json")
        else:
            app_settings_location = file_location
        if os.path.exists(app_settings_location):
            try:
                self.app_settings.load(app_settings_location)
            except Exception as e:
                log.warn(f"Error loading settings file: {e}")
                self.app_settings = ApplicationSettings()
        else:
            log.info("No app settings file found, creating new settings")
            self.app_settings = ApplicationSettings()
        sentry_sdk.add_breadcrumb(
            category="application_settings",
            message="loaded application_settings file",
            level="info",
        )
        with logtail.context(application_settings=self.app_settings.model_dump()):
            log.info(
                f"Loaded application settings version: {self.app_settings.version}"
            )

    def save_app_settings_file(self):
        save_loc = self.app_settings.save()
        self.qt_settings.setValue("application_settings_location", save_loc)

    def migrate_from_old_settings(
        self, old_settings: dict, new_name: str, new_location: str
    ):
        from video_scoring.settings.base_settings import (
            BehaviorTrackSetting,
            OOBehaviorItemSetting,
        )

        # a new project will be created for the old monolithic settings
        project = ProjectSettings()
        project.name = new_name
        project.file_location = new_location
        old_scoring_data = old_settings.get("scoring_data", [])
        for old_track in old_scoring_data.get("behavior_tracks", []):
            track = BehaviorTrackSetting()
            track.name = old_track.get("name", "OLD TRACK")

            for old_item in old_track.get("behavior_items", []):
                item = OOBehaviorItemSetting()
                item.onset = old_item.get("onset", 0)
                item.offset = old_item.get("offset", 0)
                track.behavior_items.append(item)
            project.scoring_data.behavior_tracks.append(track)
        project.save(main_win=self.main_win)
        return project
