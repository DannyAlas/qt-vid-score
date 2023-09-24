
__version__ = "0.0.1"

from calendar import c
import logging
from pydantic import BaseModel
import sys
import os
from typing import List, Literal, Optional, Any, Dict, Union, Tuple
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QSlider, QWidget
from qtpy.QtMultimedia import QMediaPlayer, QMediaMetaData, QAudioOutput
from qtpy.QtMultimediaWidgets import QVideoWidget
from qtpy.QtCore import QUrl, Qt
from qtpy import QtGui, QtCore
from video_scoring.settings import ProjectSettings
from video_scoring.widgets.settings import SettingsDockWidget
import json
import traceback as tb
import qdarktheme

log = logging.getLogger()

def logging_exept_hook(exctype, value, trace):
    log.critical(f"{str(exctype).upper()}: {value}\n\t{trace}")
    sys.__excepthook__(exctype, value, trace)

sys.excepthook = logging_exept_hook

class MainWindow(QMainWindow):
    def __init__(self, logging_level=logging.INFO):
        super().__init__()
        self.setWindowTitle("Video Scoring Thing")
        self.qt_settings = QtCore.QSettings("Root Lab", "Video Scoring")
        self.project_settings = ProjectSettings()
        self.logging_level = logging_level
        self.create_main_widget()
        self.create_status_bar()
        self.load_settings_file()
        self.create_menu()
        self.init_doc_widgets()

    def update_status(self, message, log_level=logging.INFO, do_log=True):
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
        self.help_menu.addAction("Help", self.help)
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
            self.project_settings.video_file_location = file
            self.update_status(f"Imported video at {self.project_settings.video_file_location}")
            self.save_settings()
            self.video_player.start(file)

    def import_timestamps(self):
        pass

    def import_tdt_tank(self):
        pass

    def export_timestamps(self):
        pass

    def undo(self):
        pass

    def redo(self):
        pass

    def init_doc_widgets(self):
        self.open_settings_widget()
        self.settings_dock_widget.hide()
        from video_scoring.widgets.video.frontend import VideoPlayerDockWidget
        self.video_player = VideoPlayerDockWidget(self)
        # add as central widget
        self.setCentralWidget(self.video_player)
        self.dock_widgets_menu.addAction(self.video_player.toggleViewAction())
        if self.project_settings.video_file_location is not None:
            self.video_player.start(self.project_settings.video_file_location)

    def open_settings_widget(self):
        if not hasattr(self, "settings_dock_widget"):
            self.settings_dock_widget = SettingsDockWidget(self)
            self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.settings_dock_widget)
            self.dock_widgets_menu.addAction(self.settings_dock_widget.toggleViewAction())
        else:
            self.settings_dock_widget.toggleViewAction()
        self.update_log_file()
        
        pass

    ############################# File Menu Actions #############################

    def load_settings_file(self):
        latest_project_location = self.qt_settings.value("latest_project_location")
        if latest_project_location is not None:
            try:
                self.project_settings.load(latest_project_location)
                self.update_status(
                    f"Loaded the latest project settings for {self.project_settings.video_file_name}"
                )
            except:
                self.update_status("Failed to load the latest project settings")
        self.update_log_file()
        self.init_logging()
        self.load_settings()

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
            self.project_settings.settings_file_location = file_dialog.selectedFiles()[0]
            self.project_settings.save()
            self.update_status(f"Created new project at {self.project_settings.settings_file_location}")
            self.load_settings_file()

    def open_project(self):
        # file dialog to select project location
        file_dialog = QtWidgets.QFileDialog()
        file_dialog.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
        file_dialog.setNameFilter("JSON (*.json)")
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptOpen)
        file_dialog.setDefaultSuffix("json")
        file_dialog.setDirectory(self.project_settings.settings_file_location)
        if file_dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            # try save current project
            self.save_settings()
            # open project
            self.project_settings = ProjectSettings()
            self.project_settings.load(file_dialog.selectedFiles()[0])
            self.update_status(f"Opened project at {self.project_settings.settings_file_location}")
            self.load_settings_file()    

        for widget in self.findChildren(QtWidgets.QWidget):
            try:
                widget.refresh()
            except:
                pass

    def init_logging(self):
        self.log = logging.getLogger()
        self.update_log_file()

    def load_settings(self):
        self.resize(self.project_settings.window_size[0], self.project_settings.window_size[1])
        self.move(self.project_settings.window_position[0], self.project_settings.window_position[1])

    def save_settings(self, file_location=None):
        self.qt_settings.setValue("latest_project_location", self.project_settings.settings_file_location)
        self.project_settings.window_size = (self.width(), self.height())
        self.project_settings.window_position = (self.x(), self.y())
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
            self.project_settings.settings_file_location = file_dialog.selectedFiles()[0]
            self.update_log_file()
            self.save_settings(file_dialog.selectedFiles()[0])

    def update_log_file(self):
            if self.project_settings is None:
                return
            save_dir = os.path.abspath(os.path.dirname(self.project_settings.settings_file_location))
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            if not os.path.exists(
                os.path.join(save_dir, "log.txt")
            ):
                # create a new log file
                with open(
                    os.path.join(save_dir, "log.txt"), "w"
                ) as file:
                    file.write("")
            log = logging.getLogger()
            fileHandler = logging.FileHandler(
                f"{os.path.join(save_dir, 'log.txt')}"
            )
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

    def help(self):
        pass

    def about(self):
        about_dialog = QtWidgets.QMessageBox()
        about_dialog.setWindowTitle("About")
        about_dialog.setText("Video Scoring Thing")
        about_dialog.setInformativeText("Version: " + __version__)
        about_dialog.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        about_dialog.exec()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

if __name__ == "__main__":

    app = QApplication(sys.argv)
    main_window = MainWindow()

    qss = """
    * {
        font-size: 12px;
    }
    QToolTip {
        font-size: 12px;
        color: #000000;
    }
    QTreeWidget {
        font-size: 15px;
        font-weight: 400;
    }
    QTreeWidget::item {
        height: 30px;
    }
    QListWidget {
        font-size: 15px;
        font-weight: 400;
    }
    QLabel {
        font-size: 15px;
        font-weight: 600;
    }
    QSpinBox {
        height: 30px;
        font-size: 15;
        font-weight: 400;
    }
    QLineEdit {
        height: 30px;
        font-size: 15px;
        font-weight: 400;
    }
    QComboBox {
        height: 30px;
        font-size: 15;
        font-weight: 400;
    }
    QRangeSlider {
        height: 30px;
        spacing: 10px;
        color: #FFFFFF; 
    }
    QSlider {
        padding: 2px 0;
    }
    QSlider::groove {
        border-radius: 2px;
    }
    QSlider::groove:horizontal {
        height: 4px;
    }
    QSlider::groove:vertical {
        width: 4px;
    }
    QSlider::sub-page:horizontal,
    QSlider::add-page:vertical,
    QSlider::handle {
        background: #D0BCFF;
    }
    QSlider::sub-page:horizontal:disabled,
    QSlider::add-page:vertical:disabled,
    QSlider::handle:disabled {
        background: #D0BCFF;
    }
    QSlider::add-page:horizontal,
    QSlider::handle:hover,
    QSlider::handle:pressed {
        background: #D0BCFF;
    }
    QSlider::handle:horizontal {
        width: 16px;
        height: 8px;
        margin: -6px 0;
        border-radius: 8px;
    }
    QSlider::handle:vertical {
        width: 8px;
        height: 16px;
        margin: 0 -6px;
        border-radius: 8px;
    }


    """
    def load_stylesheet():
        # get the dark theme stylesheet
        stylesheet = qdarktheme.load_stylesheet()
        # a simple qss parser
        # the stylesheet is one string with no newlines
        # remove anything contained within { and }
        d = {}
        opened_curly = 0
        selector_txt = ''
        out = ''
        add_lb = False
        for i, char in enumerate(stylesheet):

            if char == '{':
                opened_curly += 1
                # back track to find the start of the selector if we are at the start of a selector
                if opened_curly == 1:
                    j = i
                    while stylesheet[j] != '}':
                        j -= 1
                    selector_txt = stylesheet[j+1:i]
            if char == '}':
                opened_curly -= 1
                if opened_curly == 0: 
                    add_lb = True
                else: 
                    add_lb = False


            if selector_txt.__contains__('QSlider'):
                out += ""
            else:
                out += char
                if add_lb: 
                    out += '\n'
                    add_lb = False
        return out.replace("""{\nborder:1px solid rgba(63, 64, 66, 1.000);border-radius:4px}""", "").replace("QSlider ", "")
    app.setStyleSheet(load_stylesheet())
    # qdarktheme.setup_theme(theme='auto', corner_shape='rounded', custom_colors={"primary": "#D0BCFF"}, additional_qss=qss)
    main_window.show()
    sys.exit(app.exec())