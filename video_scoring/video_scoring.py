__version__ = "0.1.2"

import inspect
import json
import logging
import os
import sys
import traceback as tb
from typing import Any, Dict, Literal, Optional

import qdarktheme
import requests
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QThread, QUrl, Signal
from qtpy.QtWidgets import QMainWindow

from video_scoring.command_stack import CommandStack
from video_scoring.settings import ProjectSettings, TDTData
from video_scoring.widgets.loaders import TDTLoader
from video_scoring.widgets.progress import ProgressBar, ProgressSignals
from video_scoring.widgets.settings import SettingsDockWidget
from video_scoring.widgets.timeline import TimelineDockWidget
from video_scoring.widgets.timestamps import TimeStampsDockwidget
from video_scoring.widgets.update import UpdateCheck, UpdateDialog, Updater
from video_scoring.widgets.video.frontend import VideoPlayerDockWidget

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
        self.project_settings = ProjectSettings()
        self.icons_dir = os.path.join(os.path.dirname(__file__), "resources")
        self.set_icons()
        self.logging_level = logging_level
        self.command_stack = CommandStack()
        self.check_for_update()
        self.create_main_widget()
        self.create_status_bar()
        self.load_settings_file()
        self.create_menu()
        self.init_doc_widgets()
        self.init_key_shortcuts()
        self.loaded.emit()

    def check_for_update(self):
        self.update_checker_thread = QThread()
        # we pass in the version of the current to get around circular imports
        self.update_check = UpdateCheck(version=__version__, parent=self)
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
        if self.project_settings.theme == "dark":
            icon_path = os.path.join(self.icons_dir, "dark", icon_name)
        elif self.project_settings.theme == "light":
            icon_path = os.path.join(self.icons_dir, icon_name)
        elif self.project_settings.theme == "auto":
            icon_path = os.path.join(self.icons_dir, "dark", icon_name)
        else:
            raise Exception(f"Theme {self.project_settings.theme} not recognized")
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
        if self.menu is None:
            raise Exception("Failed to create menu bar")
        self.file_menu = self.menu.addMenu("File")
        if self.file_menu is None:
            raise Exception("Failed to create file menu")
        self.file_menu.addAction("New Project", self.new_project)
        self.file_menu.addAction("Open Project", self.open_project)
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

        self.help_menu = self.menu.addMenu("Help")
        if self.help_menu is None:
            raise Exception("Failed to create help menu")
        self.help_menu.addAction("Help Site", self.help)
        self.report_bug_action = self.help_menu.addAction("Report Bug", self.report_bug)
        self.help_menu.addSeparator()
        self.help_menu.addAction("About", self.about)

    def create_main_widget(self):
        self.main_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

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
        file_dialog.setDirectory(self.project_settings.settings_file_location)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # try save current project
            self.save_settings()
            # open project
            file = file_dialog.selectedFiles()[0]
            if file is None:
                return
            self.project_settings.video_file_location = file
            self.update_status(
                f"Imported video at {self.project_settings.video_file_location}"
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
        file_dialog.setDirectory(self.project_settings.settings_file_location)
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
        file_dialog.setDirectory(self.project_settings.settings_file_location)
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
            self.project_settings.video_file_location = file
            self.update_status(
                f"Imported video at {self.project_settings.video_file_location}"
            )
            self.save_settings()
            self.video_player_dw.load(str(file))
        except:
            self.update_status(
                f"Failed to import video at {self.project_settings.video_file_location}"
            )

    def export_timestamps(self):
        self.timestamps_dw.save()

    def undo(self):
        self.command_stack.undo()

    def redo(self):
        self.command_stack.redo()

    def init_doc_widgets(self):
        self.settings_dock_widget = SettingsDockWidget(self)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.settings_dock_widget
        )
        self.dock_widgets_menu.addAction(self.settings_dock_widget.toggleViewAction())
        self.settings_dock_widget.hide()

        self.video_player_dw = VideoPlayerDockWidget(self, self)
        # add as central widget
        self.setCentralWidget(self.video_player_dw)
        self.dock_widgets_menu.addAction(self.video_player_dw.toggleViewAction())
        if os.path.exists(str(self.project_settings.video_file_location)):
            self.video_player_dw.start(self.project_settings.video_file_location)

        # from video_scoring.widgets.projects.projects import ProjectsDock
        # self.projects_dw = ProjectsDock(self, self)
        # self.addDockWidget(
        #     QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.projects_dw
        # )
        # self.dock_widgets_menu.addAction(self.projects_dw.toggleViewAction())

        self.timestamps_dw = TimeStampsDockwidget(self, self)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.timestamps_dw
        )
        self.dock_widgets_menu.addAction(self.timestamps_dw.toggleViewAction())

        self.timeline_dw = TimelineDockWidget(self, self)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.timeline_dw
        )
        self.dock_widgets_menu.addAction(self.timeline_dw.toggleViewAction())
        # from video_scoring.widgets.analysis import VideoAnalysisDock

        # self.analysis_dw = VideoAnalysisDock(self)
        # self.addDockWidget(
        #     QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.analysis_dw
        # )
        # self.dock_widgets_menu.addAction(self.analysis_dw.toggleViewAction())

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
        self.project_settings.theme = theme

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

    def load_settings_file(self, file_location: Optional[str] = None):
        if file_location is None:
            latest_project_location = self.qt_settings.value("latest_project_location")
        else:
            latest_project_location = file_location
        if latest_project_location is not None:
            try:
                self.project_settings.load(latest_project_location)
                self.project_settings.settings_file_location = latest_project_location
                self.update_status(
                    f"Loaded the latest project settings for {self.project_settings.video_file_name}"
                )
            except Exception as e:
                desktop = QtWidgets.QApplication.screens()[0].geometry()
                self.project_settings.window_size = (
                    desktop.width() / 2,
                    desktop.height() / 2,
                )
                self.project_settings.window_position = (
                    desktop.width() / 4,
                    desktop.height() / 4,
                )
                self.update_status(
                    "Failed to load the latest project settings" + str(e),
                    log_level=logging.ERROR,
                )
        else:
            # resize ourselves to half the screen and center ourselves
            desktop = QtWidgets.QApplication.screens()[0].geometry()
            self.project_settings.window_size = (
                desktop.width() / 2,
                desktop.height() / 2,
            )
            self.project_settings.window_position = (
                desktop.width() / 4,
                desktop.height() / 4,
            )
            self.update_status(
                "No latest project settings found", log_level=logging.INFO
            )

        self.update_log_file()
        self.init_logging()
        self.load_settings()

    def _loaders(self):
        if os.path.exists(self.project_settings.video_file_location):
            self.video_player_dw.load(self.project_settings.video_file_location)
        self.timeline_dw.load()

    def new_project(self):
        # file dialog to select save location
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("JSON (*.json)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("json")
        file_dialog.setDirectory(self.project_settings.settings_file_location)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # try save current project
            self.save_settings()
            # create new project
            self.project_settings = ProjectSettings()
            self.project_settings.settings_file_location = file_dialog.selectedFiles()[
                0
            ]
            self.project_settings.save()
            self.update_status(
                f"Created new project at {self.project_settings.settings_file_location}"
            )
            self.load_settings_file(file_location=file_dialog.selectedFiles()[0])
            self.settings_dock_widget.refresh()
            self._loaders()

    def open_project(self, location: Optional[str] = None):
        # file dialog to select project location
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("JSON (*.json)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setDefaultSuffix("json")
        # set cwd to the current project location
        if self.project_settings.settings_file_location is not None:
            file_dialog.setDirectory(
                os.path.dirname(self.project_settings.settings_file_location)
                if location is None
                else os.path.dirname(location)
            )

        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # try save current project
            self.save_settings()
            # open project
            self.project_settings = ProjectSettings()
            self.project_settings.load(file_dialog.selectedFiles()[0])
            self.update_status(
                f"Opened project at {self.project_settings.settings_file_location}"
            )
            self.load_settings_file(file_location=file_dialog.selectedFiles()[0])
            self.settings_dock_widget.refresh()
            self._loaders()

    def init_logging(self):
        self.log = logging.getLogger()
        self.update_log_file()

    def load_settings(self):
        self.resize(
            int(self.project_settings.window_size[0]),
            int(self.project_settings.window_size[1]),
        )
        self.move(
            int(self.project_settings.window_position[0]),
            int(self.project_settings.window_position[1]),
        )
        self.change_theme(self.project_settings.theme)
        self.loaded.connect(self._loaders)
        # BACKWARDS COMPATIBILITY
        if self.project_settings.scoring_data.timestamp_data != {}:
            self.loaded.connect(self.migrate_timestamp_data)

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
        self.qt_settings.setValue(
            "latest_project_location", self.project_settings.settings_file_location
        )
        self.project_settings.window_size = (self.width(), self.height())
        self.project_settings.window_position = (self.x(), self.y())
        self.project_settings.scoring_data.behavior_tracks = self.timeline_dw.save()
        self.update_log_file()
        self.project_settings.save(file_location)

    def save_settings_as(self):
        # file dialog to select project location
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("JSON (*.json)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        file_dialog.setDefaultSuffix("json")
        file_dialog.setDirectory(self.project_settings.settings_file_location)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.project_settings.settings_file_location = file_dialog.selectedFiles()[
                0
            ]
            self.update_log_file()
            self.save_settings(file_dialog.selectedFiles()[0])

    def update_log_file(self):
        if self.project_settings is None:
            return
        save_dir = os.path.abspath(
            os.path.dirname(self.project_settings.settings_file_location)
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

    def help(self):
        # open browser to github
        help_url = QUrl("https://github.com/DannyAlas/qt-vid-score")
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
            QtGui.QPixmap(os.path.join(self.icons_dir, "icon_bg.png")).scaled(64, 64)
        )
        about_dialog.setWindowIcon(
            QtGui.QIcon(os.path.join(self.icons_dir, "icon.png"))
        )
        joke_thread = QThread()
        joke = JokeThread(self.project_settings.joke_type)
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
        <h2>{self.project_settings.joke_type.capitalize()} Joke</h2>
        <p style="color: grey">Loading...</p>
        <br>

        <div style="color: grey">
        <p><a href="{['https://icanhazdadjoke.com/' if self.project_settings.joke_type == "dad" else "https://backend-omega-seven.vercel.app/api/getjoke"][0]}">source</a></p>
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
        <h2>{self.project_settings.joke_type.capitalize()} Joke</h2>
        <p>{joke['question']}</p>
        <p>{joke['punchline']}</p>
        <br>

        <div style="color: grey">
        <p><a href="{['https://icanhazdadjoke.com/' if self.project_settings.joke_type == "dad" else "https://backend-omega-seven.vercel.app/api/getjoke"][0]}">source</a></p>
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
