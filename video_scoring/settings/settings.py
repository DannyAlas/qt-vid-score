import datetime
import json
import logging
import sys
from typing import Optional
from uuid import UUID, uuid4

from PyQt6.QtCore import QMimeData, Qt
from PyQt6.QtGui import QDropEvent, QPaintEvent
from PyQt6.QtWidgets import QTreeWidgetItem
from qtpy import QtCore, QtGui, QtWidgets
import sentry_sdk

from video_scoring.settings import ApplicationSettings, ProjectSettings

log = logging.getLogger()


class Settings:
    def __init__(self):
        self.app_settings = ApplicationSettings()
        self.qt_settings = QtCore.QSettings("Root Lab", "Video Scoring")
        self.load_settings_file()
        sentry_sdk.set_context(
            "application_settings", self.app_settings.model_dump()
        )
    def get_project(self, uid: uuid4):
        for project_t in self.app_settings.projects:
            if str(project_t[0]) == str(uid):
                project = ProjectSettings()
                project.load_from_file(project_t[1])
                return project

    def load_settings_file(self, file_location: Optional[str] = None):
        if file_location is None:
            latest_app_settings_location = self.qt_settings.value(
                "application_settings_location"
            )
        else:
            latest_app_settings_location = file_location

        if latest_app_settings_location is not None:
            try:
                self.app_settings.load(latest_app_settings_location)
            except Exception as e:
                log.error(f"Error loading settings file: {e}")
                self.app_settings = ApplicationSettings()

            self.qt_settings.setValue(
                "application_settings_location", latest_app_settings_location
            )
        sentry_sdk.add_breadcrumb(
            category="application_settings", message="loaded application_settings file", level="info"
        )

    def save_app_settings_file(self):
        save_loc = self.app_settings.save()
        self.qt_settings.setValue("application_settings_location", save_loc)

    def migrate_from_old_settings(
        self, old_settings: dict, new_name: str, new_location: str
    ):
        from video_scoring.settings.base_settings import (
            BehaviorTrackSetting, OOBehaviorItemSetting)

        # a new project will be created for the old monolithic settings
        project = ProjectSettings()
        project.name = new_name
        project.scoring_data.video_file_location = old_settings.get(
            "video_file_location", ""
        )
        project.file_location = old_settings.get("file_location", new_location)
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
        project.save()
        return project