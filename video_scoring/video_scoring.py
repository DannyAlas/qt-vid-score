import base64
import inspect
import json
import logging
import os
from typing import Any, Dict, Literal, Optional, Tuple, Union

import qdarktheme
import requests
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QThread, QUrl, Signal
from qtpy.QtWidgets import QMainWindow

from video_scoring import settings
from video_scoring.command_stack import CommandStack
from video_scoring.settings import (DockWidgetState, Layout, ProjectSettings,
                                    Settings, TDTData)
from video_scoring.widgets.reporting import FeedbackDialog
from video_scoring.widgets.analysis import VideoAnalysisDock
from video_scoring.widgets.loaders import TDTLoader
from video_scoring.widgets.progress import ProgressBar, ProgressSignals
from video_scoring.widgets.projects import ProjectsWidget
from video_scoring.widgets.settings import SettingsDockWidget
from video_scoring.widgets.timeline import TimelineDockWidget
from video_scoring.widgets.timestamps import TimeStampsDockwidget
from video_scoring.widgets.update import (UpdateCheck, UpdatedDialog,
                                          UpdateDialog, Updater)
from video_scoring.widgets.video.frontend import VideoPlayerDockWidget

log = logging.getLogger()
class MainWindow(QMainWindow):
    loaded = Signal()
    project_loaded = Signal()

    def __init__(self, logging_level=logging.INFO):
        super().__init__()
        self.setWindowTitle("Video Scoring Thing")
        self.qt_settings = QtCore.QSettings("Root Lab", "Video Scoring")
        self.settings = Settings()
        self.main_widget = QtWidgets.QWidget()
        self.command_stack = CommandStack()
        self.app_settings = self.settings.app_settings
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
        self.project_loaded.connect(self._loaders)
        self.loaded.emit()

    def open_projects_window(self):
        self.save_settings()
        self.close_doc_widgets()
        self.projects_w = ProjectsWidget(self)
        self.set_central_widget(self.projects_w)

    def set_window_sp(
        self,
        size: Union[Tuple[int, int], None] = None,
        position: Union[Tuple[int, int], None] = None,
        use_default: bool = False,
    ):
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
        if use_default:
            size, position = self.get_default_sp()
        if size is not None:
            self.app_settings.window_size = size
        if position is not None:
            self.app_settings.window_position = position
        d_size, d_position = self.get_default_sp()
        # ensure that the window size and position are within the visible screen, if not adjust them
        if (
            self.app_settings.window_size[0] > desktop.width()
            or self.app_settings.window_size[1] > desktop.height()
        ):
            self.app_settings.window_size = d_size
        if (
            self.app_settings.window_position[0] > desktop.width()
            or self.app_settings.window_position[1] > desktop.height()
        ):
            self.app_settings.window_position = d_position

        self.resize(
            int(self.app_settings.window_size[0]),
            int(self.app_settings.window_size[1]),
        )
        self.move(
            int(self.app_settings.window_position[0]),
            int(self.app_settings.window_position[1]),
        )

    def get_default_sp(self):
        """
        Get the default window size and position. The default size is half the size of the primary display and the default position is centered on the primary display.

        Returns
        -------
        size : Tuple[int, int]
            The default window size
        position : Tuple[int, int]
            The default window position
        """
        desktop = QtWidgets.QApplication.screens()[0].geometry()
        size = (desktop.width() / 2, desktop.height() / 2)
        position = (desktop.width() / 4, desktop.height() / 4)
        return size, position

    def load_project(self, project: ProjectSettings):
        log.info(f"Loading project {project.name}")
        self.save_settings()
        self.project_settings = project
        self.update_status(f"Loading project {project.name}")
        self.set_window_sp()
        self.update_log_file()
        self.init_logging()
        self.set_central_widget()
        self.projects_w.close()
        self.load_doc_widgets()
        self.init_key_shortcuts()
        self.init_layouts_menu()
        self.load_last_project_layout()

        self.project_loaded.emit()

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
            self.update_status(
                f"File is not a valid project file: {file_path}", logging.ERROR
            )
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
        self.update_check = UpdateCheck(version=self.app_settings.version)
        self.update_check.moveToThread(self.update_checker_thread)
        self.update_checker_thread.started.connect(self.update_check.run)
        self.update_check.update_available.connect(self.update_available)
        self.update_check.no_update.connect(self.no_update_available)
        self.update_check.update_error.connect(
            lambda e: self.update_status(e, logging.ERROR)
        )
        self.update_check.no_update.connect(
            lambda: self.update_status(
                f"You are running the latest version! ({self.app_settings.version})"
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
        from video_scoring.settings.base_settings import user_data_dir

        installer_dir = os.path.join(os.path.dirname(user_data_dir()), "installer")
        if os.path.exists(installer_dir):
            for file in os.listdir(installer_dir):
                if file.endswith(".exe"):
                    if file.split("_")[-1].strip(".exe") == self.app_settings.version:
                        # delete the file
                        os.remove(os.path.join(installer_dir, file))
                    self.update_status(
                        f"Successfully updated to the latest version {self.app_settings.version}"
                    )
            self.updated_dialog = UpdatedDialog(
                version=self.app_settings.version, main_win=self, parent=self
            )
            self.updated_dialog.exec()
            os.rmdir(installer_dir)
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

    def update_status(
        self, message, log_level=logging.DEBUG, do_log=True, display_error=True
    ):
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
            if display_error:
                msg = QtWidgets.QMessageBox()
                msg.setWindowTitle("Error")
                msg.setText(f"{message}")
                msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
                msg.exec()
        elif log_level == logging.CRITICAL:
            log.critical(message)
        elif log_level == logging.DEBUG:
            log.debug(message)

    def start_pbar(
        self,
        signals: ProgressSignals,
        title: str = "Progress Bar",
        completed_msg: str = "Completed",
        popup: bool = False,
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
        self.dock_widgets_menu = self.view_menu.addMenu("Panels")
        if self.dock_widgets_menu is None:
            raise Exception("Failed to create dock widgets menu")
        self.theme_menu = self.view_menu.addMenu("Theme")
        if self.theme_menu is None:
            raise Exception("Failed to create theme menu")
        self.theme_menu.addAction("Dark", lambda: self.change_theme("dark"))
        self.theme_menu.addAction("Light", lambda: self.change_theme("light"))
        self.view_menu.addSeparator()
        self.toggle_screen_action = self.view_menu.addAction(
            "Full Screen", self.toggle_screen
        )
        self.layouts_menu = self.view_menu.addMenu("Layouts")
        if self.layouts_menu is None:
            raise Exception("Failed to create layout menu")
        self.layouts_menu.addAction("New Layout", self.new_layout)
        self.layouts_menu.addAction("Delete Layout", self.delete_layout_dialog)
        self.layouts_menu.addSeparator()

        self.help_menu = self.menu.addMenu("Help")
        if self.help_menu is None:
            raise Exception("Failed to create help menu")
        self.help_menu.addAction("Help", self.help)
        self.feedback_action = self.help_menu.addAction("Feedback", self.feedback)
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
                        if sub_action.text() in [
                            "New Project",
                            "Open Project",
                            "Import Project",
                            "Exit",
                        ]:
                            sub_action.setEnabled(True)
                        else:
                            sub_action.setEnabled(False)
                elif action.text() == "View":
                    for sub_action in action.menu().actions():
                        if sub_action.text() in [
                            "Full Screen",
                            "Normal Screen",
                            "Theme",
                        ]:
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

    def is_pos_visible(self, pos: Tuple[int, int]):
        """
        Check if a position is visible on any screen,

        Parameters
        ----------
        pos : Tuple[int, int]
            The position to check
        """
        for screen in QtWidgets.QApplication.screens():
            if screen.geometry().contains(QtCore.QPoint(*pos)):
                return True
        return False

    def init_layouts_menu(self):
        for layout_name in self.project_settings.layouts.keys():
            if layout_name not in [
                action.text() for action in self.layouts_menu.actions()
            ]:
                self.layouts_menu.addAction(
                    layout_name, lambda: self.load_layout(layout_name=layout_name)
                )
        for layout_name in [action.text() for action in self.layouts_menu.actions()]:
            if (
                layout_name not in self.project_settings.layouts.keys()
                and layout_name != "New Layout"
                and layout_name != "Delete Layout"
                and layout_name != ""
            ):
                self.delete_layout(layout_name)

    def get_layout(self):
        """Return the current layout of the application"""
        # make a dict of the dock widgets and their states
        dock_widgets = {}
        for dock_widget in self.findChildren(QtWidgets.QDockWidget):
            d = DockWidgetState()
            d.geometry = base64.b64encode(dock_widget.saveGeometry()).decode("utf-8")
            d.visible = dock_widget.isVisible()
            dock_widgets[dock_widget.objectName()] = d

        layout = Layout()
        layout.geometry = base64.b64encode(self.saveGeometry()).decode("utf-8")
        layout.dock_state = base64.b64encode(self.saveState(1)).decode("utf-8")
        layout.dock_widgets = dock_widgets
        return layout

    def new_layout(self):
        if self.project_settings is None:
            return
        # open dialog to ask for layout name
        layout_name, ok = QtWidgets.QInputDialog.getText(
            self, "Layout Name", "Enter a name for the layout"
        )
        if not ok:
            return
        if (
            layout_name is None
            or layout_name == ""
            or layout_name in [name for name in self.project_settings.layouts.keys()]
        ):
            # msg box to error
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("Layout Name Error")
            msg.setText(
                f"Layout name {layout_name} is invalid. Please enter a unique name"
            )
            msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg.exec()
            return

        self.project_settings.layouts[layout_name] = self.get_layout()
        # add this layout to the layouts menu
        self.layouts_menu.addAction(
            layout_name, lambda: self.load_layout(layout_name=layout_name)
        )

    def load_layout(self, layout_name: str = None, layout: Layout = None):
        """
        Loads a layout from either name or `Layout` object. If both are passed, the Layout object is used.

        Parameters
        ----------
        layout_name : str, optional
            The name of the layout to load, by default None
        layout : Layout, optional
            The Layout object to load, by default None
        """
        # if both are None, return
        if layout is None and layout_name is None:
            return
        # if layout_name is passed but the layout object, get the object from name
        if layout is None and layout_name is not None:
            layout = self.project_settings.layouts.get(layout_name)
        # if the layout is still None, it doesn't exist
        if layout is None:
            self.update_status(f"Layout {layout_name} not found", logging.ERROR)
            return

        self.restoreGeometry(base64.b64decode(layout.geometry))
        # if the main window is outside of the visible screen, move it to the center
        if not self.is_pos_visible((self.x(), self.y())):
            self.move(
                QtWidgets.QApplication.screens()[0].geometry().width() / 2
                - self.width() / 2,
                QtWidgets.QApplication.screens()[0].geometry().height() / 2
                - self.height() / 2,
            )

        self.restoreState(base64.b64decode(layout.dock_state), 1)
        layout_dock_widgets = layout.dock_widgets
        for name, state in layout_dock_widgets.items():
            # get the dock widget in the main window by name
            window_dock_widget = self.findChild(QtWidgets.QDockWidget, name)
            if window_dock_widget is None:
                continue
            # restore the dock widget geometry by converting the base64 string to bytes
            window_dock_widget.restoreGeometry(base64.b64decode(state.geometry))
            window_dock_widget.setVisible(bool(state.visible))

            # if the dock widget is outside of the visible screen, move it to the center
            if not self.is_pos_visible(
                (window_dock_widget.pos().x(), window_dock_widget.pos().y())
            ):
                window_dock_widget.move(
                    self.width() / 2 - window_dock_widget.width() / 2,
                    self.height() / 2 - window_dock_widget.height() / 2,
                )

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
        # try save current project
        self.save_settings()
        from video_scoring.widgets.timestamps.importer import \
            TimestampsImporter

        self.ts_importer = TimestampsImporter(self)
        self.ts_importer.imported.connect(
            lambda name, data: self.timeline_dw.import_timestamps(name, data)
        )
        self.ts_importer.show()

    def import_tdt_tank(self):
        # file dialog to select a folder
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        file_dialog.setDirectory(self.project_settings.file_location)
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
        # FIXME: proper loading please :)
        try:
            self.save_settings()
            self.project_settings.scoring_data.tdt_data = TDTData()
            self.project_settings.scoring_data.tdt_data.load_from_block(loader.block)
            self.project_settings.scoring_data.video_file_location = (
                self.project_settings.scoring_data.tdt_data.video_path
            )
            self.update_status(
                f"Imported video at {self.project_settings.scoring_data.video_file_location}"
            )
            self.save_settings()
            self._loaders()
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
        self.timeline_dw.timeline_view.valueChanged.connect(
            self.video_player_dw.timelineChanged
        )
        self.dock_widgets_menu.addAction(self.timeline_dw.toggleViewAction())
        self.timeline_dw.setObjectName("timeline_dw")
        self.timeline_dw.hide()
        # self.analysis_dw = VideoAnalysisDock(self)
        # self.analysis_dw.setObjectName("analysis_dw")
        # self.addDockWidget(
        #     QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.analysis_dw
        # )
        # self.dock_widgets_menu.addAction(self.analysis_dw.toggleViewAction())
        # self.analysis_dw.hide()

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
            self.video_player_dw.start(
                self.project_settings.scoring_data.video_file_location
            )
        else:
            self.video_player_dw.video_widget.stopPlayer()

        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.timestamps_dw
        )
        self.timestamps_dw.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        self.timestamps_dw.show()
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_dw
        )
        self.timeline_dw.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        self.timeline_dw.show()

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
        # deep search for all widgets
        for widget in self.findChildren(QtWidgets.QWidget):
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
            self.video_player_dw.load(
                self.project_settings.scoring_data.video_file_location
            )
        self.timeline_dw.load()
        # self.analysis_dw.refresh()

    def new_project(self):
        self.save_settings()
        self.close_doc_widgets()
        self.project_settings = None
        self.projects_w = ProjectsWidget(self)
        self.set_central_widget(self.projects_w)
        self.projects_w.create_project()

    def open_project(self):
        self.save_settings()
        self.project_settings = None
        self.close_doc_widgets()
        self.projects_w = ProjectsWidget(self)
        self.set_central_widget(self.projects_w)

    def init_logging(self):
        self.log = logging.getLogger()
        self.update_log_file()

    def load_last_project_layout(self):
        if self.project_settings is None:
            self.set_window_sp()
        # get the projects last layout
        if self.project_settings.last_layout is None:
            self.set_window_sp(use_default=True)
        else:
            self.load_layout(layout=self.project_settings.last_layout)

    def save_settings(self, file_location=None):
        # set window size and position if the central widget in not the projects widget
        self.app_settings.window_size = (
            self.width(),
            self.height(),
        )
        self.app_settings.window_position = (
            self.x(),
            self.y(),
        )
        self.settings.save_app_settings_file()
        self.update_log_file()
        if self.project_settings is None:
            return
        try:
            self.project_settings.scoring_data.behavior_tracks = (
                self.timeline_dw.serialize_tracks()
            )
            self.project_settings.last_layout = self.get_layout()
            self.project_settings.save(file_location)
        except Exception as e:
            self.update_status(e, logging.ERROR)
            raise Exception(f"Failed to save project file to {file_location}")

    def save_settings_as(self):
        # file dialog to select project location
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("Video Scoring Archive (*.vsap)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("vsap")
        file_dialog.setDirectory(self.project_settings.file_location)
        # set the file name to the current project name
        file_dialog.selectFile(
            self.project_settings.name + self.project_settings.scorer
        )
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            if file_dialog.selectedFiles()[0] is None:
                return
            if not file_dialog.selectedFiles()[0].endswith(".vsap"):
                file_dialog.selectedFiles()[0] += ".vsap"
            self.project_settings.file_location = file_dialog.selectedFiles()[0]
            self.update_log_file()
            self.save_settings(file_dialog.selectedFiles()[0])

    def update_log_file(self):
        if self.app_settings is None:
            return
        save_dir = os.path.abspath(os.path.dirname(self.app_settings.file_location))
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

    def feedback(self):
        # open browser to github issues
        self.feedback_dialog = FeedbackDialog(self)
        self.feedback_dialog.exec()

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
        <p>Version: {self.app_settings.version}</p>
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
        <p>Version: {self.app_settings.version}</p>
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
        try:
            self.save_settings()
            self.close()
        except:
            # TODO: recovery state, if the project file fails to save, we should save the timestamp data to a csv file in either the project folder and/or the appdata folder, then set a flag in the app settings for recovery that will load the timestamp data from the csv file for the project
            # for now have the user save the timestamp data manually
            msg = QtWidgets.QMessageBox()
            msg.setWindowTitle("CRITICAL! Failed to save project file")
            msg.setWindowIcon(QtGui.QIcon(os.path.join(self.icons_dir, "icon.png")))
            msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg.setText(
                f"""CRITICAL FAILURE! 

Failed to save project file to {self.app_settings.file_location}                

PLEASE SAVE ALL TIMESTAMP DATA BEFORE EXITING!"""
            )
            msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            # add button for saving timestamp data, and for ignoring the error
            save_button = msg.addButton(
                "Save Timestamp Data", QtWidgets.QMessageBox.ButtonRole.ActionRole
            )
            ignore_button = msg.addButton(
                "Ignore", QtWidgets.QMessageBox.ButtonRole.ActionRole
            )
            # connect the buttons to save the timestamp data or ignore the error
            save_button.clicked.connect(self.timeline_dw._save_all_to_csv)
            ignore_button.clicked.connect(lambda: self.close())
            msg.exec()

    def closeEvent(self, event):
        self.exit()
        # close all threads
        for thread in self.findChildren(QThread):
            thread.quit()
        event.accept()
