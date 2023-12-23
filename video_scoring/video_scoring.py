__version__ = "0.1.2"

import base64
import inspect
import json
import logging
from math import e
import os
import re
import sys
import traceback as tb
from typing import Any, Dict, Literal, Optional, Union, Tuple
from numpy import delete

import qdarktheme
import requests
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QThread, QUrl, Signal
from qtpy.QtWidgets import QMainWindow

from video_scoring.command_stack import CommandStack
from video_scoring.settings import ProjectSettings, TDTData, ApplicationSettings, Settings
from video_scoring.widgets import update
from video_scoring.widgets.loaders import TDTLoader
from video_scoring.widgets.progress import ProgressBar, ProgressSignals
from video_scoring.widgets.settings import SettingsDockWidget
from video_scoring.widgets.timeline import TimelineDockWidget
from video_scoring.widgets.timestamps import TimeStampsDockwidget
from video_scoring.widgets.update import UpdateCheck, UpdateDialog, Updater
from video_scoring.widgets.video.frontend import VideoPlayerDockWidget
from video_scoring.widgets.projects import ProjectsWidget

log = logging.getLogger()


def logging_exept_hook(exctype, value, trace):
    log.critical(f"{str(exctype).upper()}: {value}\n\t{tb.format_exc()}")
    sys.__excepthook__(exctype, value, trace)


sys.excepthook = logging_exept_hook


class MainWindow(QMainWindow):
    loaded = Signal()

    def __init__(self, logging_level=logging.INFO):
        super().__init__()
        self.setWindowTitle("Video Scoring Thing")
        self.qt_settings = QtCore.QSettings("Root Lab", "Video Scoring")
        self.settings = Settings()
        self.main_widget = QtWidgets.QWidget()
        self.command_stack = CommandStack()
        self.app_settings = self.settings.app_settings
        self.app_settings.version = __version__
        self.project_settings = None
        self.menu = None
        self.logging_level = logging_level
        self.icons_dir = os.path.join(os.path.dirname(__file__), "resources")
        self.setDockNestingEnabled(True)
        self.init_logging()
        self.set_icons()
        self.check_for_update()
        self.create_status_bar()
        self.create_menu()
        self.open_projects_window()
        self.init_doc_widgets()

    def open_projects_window(self):
        self.projects_w = ProjectsWidget(self)
        self.set_central_widget(self.projects_w)

    def set_window_sp(self, size: Union[Tuple[int, int], None]=None, position: Union[Tuple[int, int], None]=None):
        """
        Set the window size and position. If no size or position is passed, the window will be centered and take up half the screen. If the size or position is larger than the screen, the window will be centered and take up half the screen.

        Parameters
        ----------
        size : Union[Tuple[int, int], None]
            The size of the window in pixels. If None, the window will be centered on the primary display.
        position : Union[Tuple[int, int], None]
            The position of the window in pixels. If None, the window will be resized to half the size of the primary display.
        """
        desktop = QtWidgets.QApplication.screens()[0].geometry()
        # set the window size and position if passed
        if size is not None:
            self.app_settings.window_size = size
        if position is not None:
            self.app_settings.window_position = position
        # ensure that the window size and position are within the visible screen, if not adjust them
        if (
            self.app_settings.window_size[0] > desktop.width()
            or self.app_settings.window_size[1] > desktop.height()
        ):
            self.app_settings.window_size = (
                desktop.width() / 2,
                desktop.height() / 2,
            )
        if (
            self.app_settings.window_position[0] > desktop.width()
            or self.app_settings.window_position[1] > desktop.height()
        ):
            self.app_settings.window_position = (
                desktop.width() / 4,
                desktop.height() / 4,
            )
        
        self.resize(
            int(self.app_settings.window_size[0]),
            int(self.app_settings.window_size[1]),
        )
        self.move(
            int(self.app_settings.window_position[0]),
            int(self.app_settings.window_position[1]),
        )

    def load_project(self, project: ProjectSettings):
        self.save_settings()
        self.loaded.connect(self._loaders)
        self.project_settings = project
        self.update_status(f"Loading project {project.name}")
        self.set_window_sp()
        self.update_log_file()
        self.init_logging()
        self.set_central_widget()
        self.projects_w.close()
        self.load_doc_widgets()
        self.init_key_shortcuts()
        # TODO: abstract this to a function
        for layout_name in self.project_settings.layouts.keys():
            if layout_name not in [action.text() for action in self.layouts_menu.actions()]:
                self.layouts_menu.addAction(layout_name, lambda: self.load_layout(layout_name))
        for layout_name in [action.text() for action in self.layouts_menu.actions()]:
            if layout_name not in self.project_settings.layouts.keys() and layout_name != "New Layout" and layout_name != "Delete Layout" and layout_name != "":
                self.delete_layout(layout_name)
        self.loaded.emit()

    def set_central_widget(self, widget: QtWidgets.QWidget = None):
        """Set the central widget of the main window, if no widget is passed, the main_widget is set as the central widget"""
        if widget is None:
            if hasattr(self, "video_player_dw"):
                widget = self.video_player_dw
            else:
                widget = self.main_widget
        self.setCentralWidget(widget)
        self.update_menu()

    def import_project_file(self):
        # file dialog to select save location
        self.close_doc_widgets()
        self.project_settings = None
        self.projects_w = ProjectsWidget(self)
        self.set_central_widget(self.projects_w)
        self.projects_w.import_project()

    def open_project_file(self, file_path: str):
        self.save_settings()
        if not file_path.endswith(".vsap"):
            self.update_status(f"File is not a valid project file: {file_path}", logging.ERROR)
            return
        project = ProjectSettings()
        try:
            project.load_from_file(file_path)
        except Exception as e:
            self.update_status(e, logging.ERROR)
            return
        self.load_project(project)
        

    def check_for_update(self):
        self.update_checker_thread = QThread()
        # we pass in the version of the current to get around circular imports
        self.update_check = UpdateCheck(version=__version__)
        self.update_check.moveToThread(self.update_checker_thread)
        self.update_checker_thread.started.connect(self.update_check.run)
        self.update_check.update_available.connect(self.update_available)
        self.update_check.no_update.connect(self.no_update_available)
        self.update_check.update_error.connect(
            lambda e: self.update_status(e, logging.ERROR)
        )
        self.update_check.no_update.connect(
            lambda: self.update_status(
                f"You are running the latest version! ({__version__})"
            )
        )
        self.update_checker_thread.finished.connect(self.update_checker_thread.quit)
        self.update_checker_thread.start()

    def update_available(self, data: Dict[str, Any]):
        self.update_dialog = UpdateDialog(data)
        self.update_dialog.accepted.connect(self.download_update)
        self.update_dialog.exec()

    def no_update_available(self):
        # check the installer folder in the appdata Video Scoring folder
        # if it exists, check if the version is the same as the current version, if so delete it
        # if it doesn't exist, do nothing
        installer_dir = os.path.join(
            os.getenv("LOCALAPPDATA"), "Video Scoring", "installer"
        )
        if os.path.exists(installer_dir):
            for file in os.listdir(installer_dir):
                # the installer name is setup_Video.Scoring_0.0.1.exe
                if file.endswith(".exe"):
                    if file.split("_")[-1].strip(".exe") == __version__:
                        # delete the file
                        os.remove(os.path.join(installer_dir, file))
                        # show a message box saying that the we have successfully updated to the latest version
                        self.update_status(
                            f"Successfully updated to the latest version {__version__}"
                        )
                        msg = QtWidgets.QMessageBox()
                        msg.setWindowTitle("Update")
                        msg.setText(
                            f"Successfully updated to the latest version {__version__}"
                        )
                        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
                        msg.exec()
                        return

    def download_update(self):
        self.update_thread = QThread()
        self.updater = Updater(self.update_dialog.data)
        self.updater.moveToThread(self.update_thread)
        self.updater.progress_signals.started.connect(
            lambda: self.start_pbar(
                self.updater.progress_signals, "Downloading Update", "Downloaded Update"
            )
        )
        self.updater.progress_signals.complete.connect(
            lambda: self.update_status(
                f"Downloaded update to {self.updater.data['tag_name']}"
            )
        )
        self.updater.progress_signals.complete.connect(self._run_installer)
        self.updater.progress_signals.complete.connect(self.update_thread.quit)
        self.update_thread.started.connect(self.updater.run)
        self.update_thread.start()

    def _run_installer(self):
        # run the installer
        installer_dir = os.path.join(
            os.getenv("LOCALAPPDATA"), "Video Scoring", "installer"
        )
        installer_file = [
            os.path.join(installer_dir, file)
            for file in os.listdir(installer_dir)
            if file.endswith(".exe")
        ][0]
        import subprocess

        subprocess.Popen(installer_file, shell=True)
        self.close()

    def _get_icon(self, icon_name, as_string=False, svg=False):
        if self.app_settings.theme == "dark":
            icon_path = os.path.join(self.icons_dir, "dark", icon_name)
        elif self.app_settings.theme == "light":
            icon_path = os.path.join(self.icons_dir, icon_name)
        elif self.app_settings.theme == "auto":
            icon_path = os.path.join(self.icons_dir, "dark", icon_name)
        else:
            raise Exception(f"Theme {self.app_settings.theme} not recognized")
        if not as_string:
            return QtGui.QIcon(icon_path)
        else:
            return icon_path.replace("\\", "/")

    def set_icons(self):
        self.setWindowIcon(QtGui.QIcon(os.path.join(self.icons_dir, "icon.png")))
        # set the tray icon
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.set_tray_icon()

    def set_tray_icon(self):
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon_menu = QtWidgets.QMenu(self)
        self.tray_icon_menu.addAction("Show", self.show)
        self.tray_icon_menu.addAction("Exit", self.close)
        self.tray_icon.setContextMenu(self.tray_icon_menu)
        self.tray_icon.setIcon(self._get_icon("icon.ico"))
        self.tray_icon.setToolTip("Video Scoring Thing")
        self.tray_icon.show()

    def update_status(self, message, log_level=logging.DEBUG, do_log=True):
        if self.status_bar is not None:
            self.status_bar.showMessage(message)
        if not do_log:
            return
        if log_level == logging.INFO:
            log.info(message)
        elif log_level == logging.WARNING:
            log.warning(message)
        elif log_level == logging.ERROR:
            log.error(message)
        elif log_level == logging.CRITICAL:
            log.critical(message)
        elif log_level == logging.DEBUG:
            log.debug(message)

    def start_pbar(
        self,
        signals: ProgressSignals,
        title: str = "Progress Bar",
        completed_msg: str = "Completed",
    ):
        # clear the status bar
        self.status_bar.clearMessage()
        self.pbar = ProgressBar(signals, title, completed_msg, self)
        self.pbar.start_progress()

    def create_menu(self):
        self.menu = self.menuBar()
        self.menu.setObjectName("app menu")
        if self.menu is None:
            raise Exception("Failed to create menu bar")
        self.file_menu = self.menu.addMenu("File")
        if self.file_menu is None:
            raise Exception("Failed to create file menu")
        self.file_menu.addAction("New Project", self.new_project)
        self.file_menu.addAction("Open Project", self.open_project)
        self.file_menu.addAction("Import Project", self.import_project_file)
        self.file_menu.addAction("Save Project", self.save_settings)
        self.file_menu.addAction("Save Project As", self.save_settings_as)
        self.file_menu.addSeparator()
        self.import_menu = self.file_menu.addMenu("Import")
        if self.import_menu is None:
            raise Exception("Failed to create import menu")
        self.import_menu.addAction("Import Video", self.import_video)
        self.import_menu.addAction("Import Timestamps", self.import_timestamps)
        self.import_menu.addAction("Import TDT Tank", self.import_tdt_tank)
        self.file_menu.addAction("Export Timestamps", self.export_timestamps)
        self.file_menu.addSeparator()
        self.file_menu.addAction("Exit", self.close)

        self.edit_menu = self.menu.addMenu("Edit")
        if self.edit_menu is None:
            raise Exception("Failed to create edit menu")
        self.edit_menu.addAction("Undo", self.undo)
        self.edit_menu.addAction("Redo", self.redo)
        self.edit_menu.addAction("Settings", self.open_settings_widget)

        self.view_menu = self.menu.addMenu("View")
        if self.view_menu is None:
            raise Exception("Failed to create view menu")
        self.dock_widgets_menu = self.view_menu.addMenu("Dock Widgets")
        if self.dock_widgets_menu is None:
            raise Exception("Failed to create dock widgets menu")
        self.theme_menu = self.view_menu.addMenu("Theme")
        if self.theme_menu is None:
            raise Exception("Failed to create theme menu")
        self.theme_menu.addAction("Dark", lambda: self.change_theme("dark"))
        self.theme_menu.addAction("Light", lambda: self.change_theme("light"))
        self.view_menu.addSeparator()
        self.toggle_screen_action = self.view_menu.addAction("Full Screen", self.toggle_screen)
        self.layouts_menu = self.view_menu.addMenu("Layouts")
        if self.layouts_menu is None:
            raise Exception("Failed to create layout menu")
        self.layouts_menu.addAction("New Layout", self.new_layout)
        self.layouts_menu.addAction("Delete Layout", self.delete_layout_dialog)
        self.layouts_menu.addSeparator()
        
        self.help_menu = self.menu.addMenu("Help")
        if self.help_menu is None:
            raise Exception("Failed to create help menu")
        self.help_menu.addAction("Help Site", self.help)
        self.report_bug_action = self.help_menu.addAction("Report Bug", self.report_bug)
        self.help_menu.addSeparator()
        self.help_menu.addAction("About", self.about)

    def update_menu(self):
        """Depending on the current central widget, update the menu"""
        # if its the projects widget, disable all menu actions except for the file menu
        if self.centralWidget() is self.projects_w:
            for action in self.menu.actions():
                if action.text() == "Help":
                    continue
                elif action.text() == "File":
                    for sub_action in action.menu().actions():
                        if sub_action.text() in ["New Project", "Open Project", "Import Project", "Exit"]:
                            sub_action.setEnabled(True)
                        else:
                            sub_action.setEnabled(False)
                elif action.text() == "View":
                    for sub_action in action.menu().actions():
                        if sub_action.text() in ["Full Screen", "Normal Screen", "Theme"]:
                            sub_action.setEnabled(True)
                        else:
                            sub_action.setEnabled(False)
                else:
                    for sub_action in action.menu().actions():
                        sub_action.setEnabled(False)
        else:
            # enable all menu actions
            for action in self.menu.actions():
                for sub_action in action.menu().actions():
                    sub_action.setEnabled(True)

    def new_layout(self):
        if self.project_settings is None:
            return
        # open dialog to ask for layout name
        layout_name, ok = QtWidgets.QInputDialog.getText(
            self, "Layout Name", "Enter a name for the layout"
        )
        if not ok:
            return
        if layout_name is None or layout_name == "" or layout_name in [
            name for name in self.project_settings.layouts.keys()
            ]:
            # msg box to error
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Layout Name Error")
            msg.setText(
                f"Layout name {layout_name} is invalid. Please enter a unique name"
            )
            msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # make a dict of the dock widgets and their states
        dock_widgets = {}
        for dock_widget in self.findChildren(QtWidgets.QDockWidget):
            dock_widgets[dock_widget.objectName()] = {
                "geometry": dock_widget.saveGeometry().toBase64(),
                "visible": dock_widget.isVisible(),
            }
        self.project_settings.layouts[layout_name] = {
            "geometry": self.saveGeometry().toBase64(),
            "dock_state": self.saveState(1).toBase64(),
            "dock_widgets": dock_widgets,
        }
        # add this layout to the layouts menu
        self.layouts_menu.addAction(layout_name, lambda: self.load_layout(layout_name))

    def load_layout(self, layout_name: str):
        # load the saved state of the dock widgets
        if layout_name not in self.project_settings.layouts.keys():
            self.update_status(f"Layout {layout_name} not found", logging.ERROR)
            return
        # encoded as base64 strings, so we need to convert them back to bytes
        # self.restoreGeometry(
        #     base64.b64decode(self.project_settings.layouts[layout_name]["geometry"])
        # )
        self.restoreState(
            base64.b64decode(self.project_settings.layouts[layout_name]["dock_state"]), 1
        )
        dock_widgets = self.project_settings.layouts[layout_name]["dock_widgets"]
        for dock_widget in self.findChildren(QtWidgets.QDockWidget):
            if dock_widget.objectName() in dock_widgets.keys():
                # they're stored as hex strings, so we need to convert them back to bytes
                dock_widget.restoreGeometry(base64.b64decode(dock_widgets[dock_widget.objectName()]["geometry"]))
                dock_widget.setVisible(bool(dock_widgets[dock_widget.objectName()]["visible"]))
            else:
                dock_widget.setVisible(False)

    def delete_layout_dialog(self):
        # open a list of layouts to delete
        layout_name, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Delete Layout",
            "Select a layout to delete",
            [name for name in self.project_settings.layouts.keys()],
            editable=False,
        )
        if layout_name is None or layout_name == "":
            return
        if not ok:
            return
        self.delete_layout(layout_name)

    def delete_layout(self, layout_name: str):
        if layout_name not in self.project_settings.layouts.keys():
            self.update_status(f"Layout {layout_name} not found", logging.ERROR)
            return
        del self.project_settings.layouts[layout_name]
        # remove the action from the layouts menu
        for action in self.layouts_menu.actions():
            if action.text() == layout_name:
                self.layouts_menu.removeAction(action)
                break

    def create_status_bar(self):
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)

    def import_video(self):
        # file dialog to select video
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("Videos (*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setDefaultSuffix("mp4")
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # try save current project
            self.save_settings()
            # open project
            file = file_dialog.selectedFiles()[0]
            if file is None:
                return
            self.project_settings.scoring_data.video_file_location = file
            self.update_status(
                f"Imported video at {self.project_settings.scoring_data.video_file_location}"
            )
            self.save_settings()
            self._loaders()

    def import_timestamps(self):
        # file dialog to open csv
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("CSV (*.csv)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setDefaultSuffix("csv")
        file_dialog.setDirectory(self.app_settings.file_location)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # try save current project
            self.save_settings()
            # open project
            file = file_dialog.selectedFiles()[0]
            self.project_settings.scoring_data.timestamp_file_location = file
            self.save_settings()
            self.timeline_dw.import_ts_file(file)

    def import_tdt_tank(self):
        # file dialog to select a folder
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        file_dialog.setDirectory(self.app_settings.file_location)
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptOpen)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            try:
                self.tdt_loader_thread = QThread()
                self.tdt_loader = TDTLoader(file_dialog.selectedFiles()[0])
                self.tdt_loader.moveToThread(self.tdt_loader_thread)
                self.tdt_loader_thread.started.connect(self.tdt_loader.run)
                self.tdt_loader.signals.complete.connect(self.tdt_loader_thread.quit)
                self.tdt_loader.signals.complete.connect(
                    self.settings_dock_widget.refresh
                )
                self.tdt_loader.signals.complete.connect(
                    lambda: self.load_block(self.tdt_loader)
                )
                self.tdt_loader_thread.start()
                self.start_pbar(
                    self.tdt_loader.signals,
                    f"Importing TDT Tank {file_dialog.selectedFiles()[0]}",
                    "Imported TDT Tank",
                )
                self.settings_dock_widget.refresh()
            except:
                self.update_status(
                    f"Failed to import TDT Tank {file_dialog.selectedFiles()[0]}"
                )

    def load_block(self, loader: TDTLoader):
        """We assume that a tdt_loader object has loaded its block property"""
        try:
            self.save_settings()
            self.tdt_data = TDTData(loader.block)
            # open project
            file = self.tdt_data.video_path
            self.project_settings.scoring_data.video_file_location = file
            self.update_status(
                f"Imported video at {self.project_settings.scoring_data.video_file_location}"
            )
            self.save_settings()
            self.video_player_dw.load(str(file))
        except:
            self.update_status(
                f"Failed to import video at {self.project_settings.scoring_data.video_file_location}"
            )

    def export_timestamps(self):
        self.timestamps_dw.save()

    def undo(self):
        self.command_stack.undo()

    def redo(self):
        self.command_stack.redo()

    def init_doc_widgets(self):
        self.settings_dock_widget = SettingsDockWidget(self)
        self.dock_widgets_menu.addAction(self.settings_dock_widget.toggleViewAction())
        self.settings_dock_widget.hide()
        self.video_player_dw = VideoPlayerDockWidget(self, self)
        self.dock_widgets_menu.addAction(self.video_player_dw.toggleViewAction())
        self.video_player_dw.setObjectName("video_player_dw")
        self.video_player_dw.hide()
        self.timestamps_dw = TimeStampsDockwidget(self, self)
        self.dock_widgets_menu.addAction(self.timestamps_dw.toggleViewAction())
        self.timestamps_dw.setObjectName("timestamps_dw")
        self.timestamps_dw.hide()
        self.timeline_dw = TimelineDockWidget(self, self)
        self.dock_widgets_menu.addAction(self.timeline_dw.toggleViewAction())
        self.timeline_dw.setObjectName("timeline_dw")
        self.timeline_dw.hide()
        # from video_scoring.widgets.analysis import VideoAnalysisDock

        # self.analysis_dw = VideoAnalysisDock(self)
        # self.addDockWidget(
        #     QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.analysis_dw
        # )
        # self.dock_widgets_menu.addAction(self.analysis_dw.toggleViewAction())

    def load_doc_widgets(self):
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.settings_dock_widget
        )
        self.settings_dock_widget.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas
        )
        self.settings_dock_widget.hide()
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.video_player_dw
        )
        self.video_player_dw.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas
        )
        self.set_central_widget(self.video_player_dw)
        self.video_player_dw.show()
        if os.path.exists(str(self.project_settings.scoring_data.video_file_location)):
            self.video_player_dw.start(self.project_settings.scoring_data.video_file_location)
        else:
            self.video_player_dw.video_widget.stopPlayer()

        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.timestamps_dw
        )
        self.timestamps_dw.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas
        )
        self.timestamps_dw.show()
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_dw
        )
        self.timeline_dw.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas
        )
        self.timeline_dw.show()
        self.timeline_dw.load()

    def close_doc_widgets(self):
        for dock_widget in self.findChildren(QtWidgets.QDockWidget):
            dock_widget.close()
            self.removeDockWidget(dock_widget)

    def open_settings_widget(self):
        self.settings_dock_widget.show()

    def init_handlers(self):
        """
        Get all methods
        """
        self.shortcut_handlers = dict(
            inspect.getmembers(self, predicate=inspect.ismethod)
        )
        for child in self.children():
            self.shortcut_handlers.update(
                dict(inspect.getmembers(child, predicate=inspect.ismethod))
            )

    def init_key_shortcuts(self):
        self.init_handlers()
        for action, key_sequence in self.project_settings.key_bindings.items():
            self.register_shortcut(action, key_sequence)

    def register_shortcut(self, action, key_sequence):
        if key_sequence is None:
            return
        if not hasattr(self, "shortcut_handlers"):
            self.init_handlers()

        if action not in self.shortcut_handlers.keys():
            # self.update_status(f"Action {action} not found in shortcut handlers")
            return
        # if the action is already registered, update the key sequence
        if action in [
            shortcut.objectName() for shortcut in self.findChildren(QtWidgets.QShortcut)
        ]:
            shortcut = self.findChild(QtWidgets.QShortcut, action)
            shortcut.setKey(QtGui.QKeySequence(key_sequence))
        else:
            # create a new shortcut
            shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(key_sequence), self)
            shortcut.setObjectName(action)
            shortcut.activated.connect(self.shortcut_handlers[action])

    def change_theme(self, theme: Literal["dark", "light"]):
        self.app_settings.theme = theme

        qdarktheme.setup_theme(theme)
        # get the current app
        app = QtWidgets.QApplication.instance()
        # deep search for all widgets
        for widget in app.allWidgets():
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
            widget.setStyleSheet(qdarktheme.load_stylesheet(theme=theme))

    ############################# TimeStamp Actions #############################

    def get_frame_num(self):
        try:
            return self.video_player_dw.get_frame_num()
        except:
            return None

    ############################# File Menu Actions #############################

    def _loaders(self):
        if self.project_settings is None:
            return
        if os.path.exists(self.project_settings.scoring_data.video_file_location):
            self.video_player_dw.load(self.project_settings.scoring_data.video_file_location)
        self.timeline_dw.load()

    def new_project(self):
        # file dialog to select save location
        self.close_doc_widgets()
        self.project_settings = None
        self.projects_w = ProjectsWidget(self)
        self.set_central_widget(self.projects_w)
        self.projects_w.create_project()

    def open_project(self):
        self.save_settings()
        self.close_doc_widgets()
        self.projects_w = ProjectsWidget(self)
        self.set_central_widget(self.projects_w)

    def init_logging(self):
        self.log = logging.getLogger()
        self.update_log_file()

    def migrate_timestamp_data(self):
        self.timeline_dw.timeline_view.add_behavior_track("OLD TIMESTAMP")
        for onset, offset in self.project_settings.scoring_data.timestamp_data.items():
            self.timeline_dw.timeline_view.add_oo_behavior(
                onset=int(onset),
                offset=int(offset),
                track_idx=self.timeline_dw.timeline_view.get_track_idx_from_name(
                    "OLD TIMESTAMP"
                ),
            )
        # msg box to tell the user that the timestamp data has been moved to the timeline
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle("Migrated Timestamp Data")
        msg.setText(
            "Your timestamp data has been migrated to the timeline named `OLD TIMESTAMPS` for compatibility"
        )
        msg.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msg.exec()
        self.project_settings.scoring_data.timestamp_data = {}

    def save_settings(self, file_location=None):
        if self.centralWidget() is self.projects_w:
            return
        # set window size and position if the central widget in not the projects widget
        self.app_settings.window_size = (
            self.width(),
            self.height(),
        )
        self.app_settings.window_position = (
            self.x(),
            self.y(),
        )
        if self.project_settings is None:
            return
        self.project_settings.scoring_data.behavior_tracks = self.timeline_dw.save()
        self.settings.save_settings_file()
        self.update_log_file()
        try:
            self.project_settings.save(file_location)
        except:
            self.update_status(
                f"Failed to save project file to {file_location}", logging.ERROR
            )
            # msg box to error
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Save Project Error")
            msg.setText(f"Failed to save project file to {file_location}")
            msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg.exec()
            return            

    def save_settings_as(self):
        # file dialog to select project location
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("Video Scoring Archive (*.vsap)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("vsap")
        file_dialog.setDirectory(self.app_settings.file_location)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.app_settings.file_location = file_dialog.selectedFiles()[
                0
            ]
            self.update_log_file()
            self.save_settings(file_dialog.selectedFiles()[0])

    def update_log_file(self):
        if self.app_settings is None:
            return
        save_dir = os.path.abspath(
            os.path.dirname(self.app_settings.file_location)
        )
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        if not os.path.exists(os.path.join(save_dir, "log.txt")):
            # create a new log file
            with open(os.path.join(save_dir, "log.txt"), "w") as file:
                file.write("")
        log = logging.getLogger()
        fileHandler = logging.FileHandler(f"{os.path.join(save_dir, 'log.txt')}")
        fileHandler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s \n",
                datefmt="%m/%d/%Y %I:%M:%S %p",
            )
        )
        for handler in log.handlers:
            if isinstance(handler, logging.FileHandler):
                log.removeHandler(handler)
        log.addHandler(fileHandler)
        log.setLevel(self.logging_level)
        self.log = log

    def toggle_screen(self):
        """Toggle between full screen and normal screen"""
        if self.isFullScreen():
            self.toggle_screen_action.setText("Full Screen")
            self.showNormal()
        else:
            self.showFullScreen()
            self.toggle_screen_action.setText("Normal Screen")

    def help(self):
        # open browser to github
        help_url = QUrl("https://github.com/DannyAlas/qt-vid-score/wiki")
        QtGui.QDesktopServices.openUrl(help_url)

    def report_bug(self):
        # open browser to github issues
        help_url = QUrl("https://github.com/DannyAlas/qt-vid-score/issues")
        QtGui.QDesktopServices.openUrl(help_url)

    def about(self):
        class JokeSignals(QtCore.QObject):
            complete = Signal(dict)
            finished = Signal()

        class JokeThread(QtCore.QObject):
            def __init__(self, type: Literal["programming", "general"] = "programming"):
                super().__init__()
                self.type = type
                self.signals = JokeSignals()

            def get_joke(self, type: Literal["programming", "dad"] = "programming"):
                if type == "programming":
                    url = r"https://backend-omega-seven.vercel.app/api/getjoke"
                    response = requests.get(url)
                    if response.status_code == 200:
                        res = json.loads(response.content)[0]
                        return res
                    else:
                        return {
                            "question": "What's the best thing about a Boolean?",
                            "punchline": "Even if you're wrong, you're only off by a bit.",
                        }
                elif type == "dad":
                    url = r"https://icanhazdadjoke.com/"
                    response = requests.get(url, headers={"Accept": "text/plain"})
                    if response.status_code == 200:
                        return {
                            "question": "",
                            "punchline": response.content.decode("utf-8"),
                        }
                    else:
                        return {
                            "question": "What's the best thing about a Boolean?",
                            "punchline": "Even if you're wrong, you're only off by a bit.",
                        }

            def run(self):
                joke = self.get_joke(self.type)
                self.signals.complete.emit(joke)
                self.signals.finished.emit()

        about_dialog = QtWidgets.QMessageBox()
        about_dialog.setWindowTitle("About")
        # set custom icon scaled
        about_dialog.setIconPixmap(
            QtGui.QPixmap(os.path.join(self.icons_dir, "icon_gray.png")).scaled(64, 64)
        )
        about_dialog.setWindowIcon(
            QtGui.QIcon(os.path.join(self.icons_dir, "icon.png"))
        )
        joke_thread = QThread()
        joke = JokeThread(self.app_settings.joke_type)
        joke.moveToThread(joke_thread)
        about_dialog.setText(
            f"""
        <h1>Video Scoring Thing</h1>
        <div style="color: grey">
        <p>Version: {__version__}</p>
        <p>Author: Daniel Alas</p>
        <p>License: MIT</p>
        </div>
        <br>
        <h2>{self.app_settings.joke_type.capitalize()} Joke</h2>
        <p style="color: grey">Loading...</p>
        <br>

        <div style="color: grey">
        <p><a href="{['https://icanhazdadjoke.com/' if self.app_settings.joke_type == "dad" else "https://backend-omega-seven.vercel.app/api/getjoke"][0]}">source</a></p>
        </div>

        """
        )
        joke_thread.started.connect(joke.run)
        joke_thread.finished.connect(joke_thread.quit)
        joke.signals.finished.connect(joke_thread.quit)
        joke.signals.complete.connect(
            lambda joke: about_dialog.setText(
                f"""
        <h1>Video Scoring Thing</h1>
        <div style="color: grey">
        <p>Version: {__version__}</p>
        <p>Author: Daniel Alas</p>
        <p>License: MIT</p>
        </div>
        <br>
        <h2>{self.app_settings.joke_type.capitalize()} Joke</h2>
        <p>{joke['question']}</p>
        <p>{joke['punchline']}</p>
        <br>

        <div style="color: grey">
        <p><a href="{['https://icanhazdadjoke.com/' if self.app_settings.joke_type == "dad" else "https://backend-omega-seven.vercel.app/api/getjoke"][0]}">source</a></p>
        </div>
        
        """
            )
        )

        # add small grey text at bottom
        joke_thread.start()

        about_dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        about_dialog.exec()

    def exit(self):
        self.save_settings()
        self.close()

    def closeEvent(self, event):
        self.save_settings()
        # close all threads
        for thread in self.findChildren(QThread):
            thread.quit()
        event.accept()
