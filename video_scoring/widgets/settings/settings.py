import typing
from typing import TYPE_CHECKING, Union

import qdarktheme
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from video_scoring.settings.base_settings import (AbstSettings,
                                                  ApplicationSettings,
                                                  BehaviorTrackSetting,
                                                  Playback, ProjectSettings,
                                                  Scoring, ScoringData)
from video_scoring.widgets.timeline import track

if TYPE_CHECKING:
    from main import MainWindow


class SettingsDockWidget(QtWidgets.QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(SettingsDockWidget, self).__init__(parent)
        self.setWindowTitle("Settings")
        self.setObjectName("settings_dw")
        self.main_win = main_win
        self._init_ui()
        self.search_dict: dict[
            str, dict[QtWidgets.QTabWidget, QtWidgets.QWidget]
        ] = (
            {}
        )  # a dict of the widgets in the settings dock widget where the key is the (human searchable) name and the value is the widget

    def _init_ui(self):
        self.tool_bar = QtWidgets.QToolBar()
        self.tool_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.tool_bar.setFloatable(False)
        self.tool_bar.setMovable(False)
        self.tool_bar.setOrientation(Qt.Orientation.Horizontal)
        self.tool_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.tool_bar.setIconSize(QtCore.QSize(16, 16))
        self.refresh_action = QtWidgets.QAction(
            self.main_win._get_icon("refresh.svg", svg=True), "Refresh", self
        )
        self.refresh_action.triggered.connect(self.refresh)
        self.tool_bar.addAction(self.refresh_action)
        self.search_bar = QtWidgets.QLineEdit()
        self.search_bar.setPlaceholderText("Search")
        self.search_bar.textChanged.connect(self.search)
        self.tool_bar.addWidget(self.search_bar)
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.addAction(self.refresh_action)
        self.tab_widget.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)
        self.create_tabs()
        self.main_win.project_loaded.connect(self.refresh)
        self.setFloating(True)
        self.pre_refresh_tab = None
        self.main_widget = QtWidgets.QWidget()
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.addWidget(self.tool_bar)
        self.main_widget.setLayout(self.main_layout)
        self.main_layout.addWidget(self.tab_widget)
        self.setWidget(self.main_widget)

    def search(self, text: str):
        # search the search_dict for the text
        # if the text is in the key, set the tab to be the current tab, focus the widget, and highlight it
        if text == "":
            # if the text is empty, reset the search
            self.reset_search()
            return
        text = text.lower()
        # search
        for key, value in self.search_dict.items():
            if text in key.lower():
                # set the tab to be the current tab
                self.tab_widget.setCurrentWidget(list(value.keys())[0])
                # highlight the widget
                list(value.values())[0].setStyleSheet("background-color: #9c945d")
                # focus the widget
            else:
                list(value.values())[0].setStyleSheet("")

    def reset_search(self):
        # reset the search
        for value in self.search_dict.values():
            list(value.values())[0].setStyleSheet("")

    def reset_settings(self):
        # open a dialog to confirm
        pass

    def create_tabs(self):
        if self.main_win.project_settings is None:
            return
        self.populate_general_settings()
        self.populate_project_settings()
        # self.populate_tab(tab_widget=self.tab_widget, pyd_model=Playback())
        self.populate_playback_settings()
        self.populate_scoring_settings()
        self.populate_key_bindings()

    def populate_key_bindings(self):
        # for each of the key bindings in the settings create a label and a key sequence edit
        # create a scrollable widget for the tab that contains a form layout
        self.key_binds_tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout()
        self.key_binds_tab.setLayout(tab_layout)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        content_widget = QtWidgets.QWidget()
        scroll_area.setWidget(content_widget)
        form_layout = QtWidgets.QFormLayout()
        content_widget.setLayout(form_layout)
        self.key_binds_tab.layout().addWidget(scroll_area)
        for (
            action_name,
            key_sequence,
        ) in self.main_win.project_settings.key_bindings.__dict__.items():
            # create a label for the field
            label = QtWidgets.QLabel(action_name.replace("_", " ").title())
            widget = QtWidgets.QKeySequenceEdit()
            widget.setKeySequence(QtGui.QKeySequence(key_sequence))
            content_widget.layout().addRow(label, widget)
            self.search_dict[action_name] = {self.key_binds_tab: widget}
            widget.setObjectName(action_name)
            widget.setToolTip(
                self.main_win.project_settings.key_bindings.help_text().get(
                    action_name, ""
                )
            )
            widget.keySequenceChanged.connect(self.key_sequence_changed)
        self.tab_widget.addTab(self.key_binds_tab, "Key Bindings")

    def populate_project_settings(self):
        tab = QtWidgets.QWidget()
        tab.setObjectName("project_settings")
        tab_layout = QtWidgets.QFormLayout()
        tab.setLayout(tab_layout)
        # label for the project uid but it is not editable
        label = QtWidgets.QLabel("UID")
        label.setToolTip("Unique Identifier for the project")
        self.search_dict["uid"] = {tab: label}
        uid = QtWidgets.QLineEdit()
        uid.setText(str(self.main_win.project_settings.uid))
        uid.setReadOnly(True)
        uid.setEnabled(False)
        uid.setObjectName("uid")
        # label for the project name
        label_name = QtWidgets.QLabel("Name")
        label_name.setToolTip(self.get_help_text(ProjectSettings, "name"))
        self.search_dict["project name"] = {tab: label_name}
        name = QtWidgets.QLineEdit()
        name.setText(self.main_win.project_settings.name)
        name.setObjectName("name")
        # label for the project scorer
        label_scorer = QtWidgets.QLabel("Scorer")
        label_scorer.setToolTip(self.get_help_text(ProjectSettings, "scorer"))
        self.search_dict["scorer"] = {tab: label_scorer}
        scorer = QtWidgets.QLineEdit()
        scorer.setText(self.main_win.project_settings.scorer)
        scorer.setObjectName("scorer")
        # label for the project created date
        label_created = QtWidgets.QLabel("Created")
        label_created.setToolTip(self.get_help_text(ProjectSettings, "created"))
        created = QtWidgets.QLineEdit()
        created.setText(str(self.main_win.project_settings.created))
        created.setReadOnly(True)
        created.setEnabled(False)
        self.search_dict["created date"] = {tab: label_created}
        # label for the project modified date not editable
        label_modified = QtWidgets.QLabel("Modified")
        label_modified.setToolTip(self.get_help_text(ProjectSettings, "modified"))
        modified = QtWidgets.QLineEdit()
        modified.setText(str(self.main_win.project_settings.modified))
        modified.setReadOnly(True)
        modified.setEnabled(False)
        self.search_dict["modified date"] = {tab: label_modified}
        # label for the project file location
        label_file_location = QtWidgets.QLabel("File Location")
        label_file_location.setToolTip(
            self.get_help_text(ProjectSettings, "file_location")
        )
        file_location = QtWidgets.QLineEdit()
        file_location.setText(self.main_win.project_settings.file_location)
        file_location.mousePressEvent = (
            lambda event: self.main_win.open_projects_window()
        )
        file_location.setReadOnly(True)
        self.search_dict["project file location"] = {tab: label_file_location}
        # connect the text changed signals to update the settings
        name.textChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings)
        )
        scorer.textChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings)
        )
        # add the widgets to the layout
        tab_layout.addRow(label, uid)
        tab_layout.addRow(label_name, name)
        tab_layout.addRow(label_scorer, scorer)
        tab_layout.addRow(label_file_location, file_location)
        tab_layout.addRow(label_created, created)
        tab_layout.addRow(label_modified, modified)
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)
        self.tab_widget.addTab(tab, "Project Settings")

    def populate_general_settings(self):
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QFormLayout()
        tab.setLayout(tab_layout)
        # label for the project version
        label_version = QtWidgets.QLabel(
            f"Version: {self.main_win.app_settings.version}"
        )
        self.search_dict["version"] = {tab: label_version}
        # label for the file location
        label_file_location = QtWidgets.QLabel("File Location")
        label_file_location.setToolTip(
            self.get_help_text(ProjectSettings, "file_location")
        )
        file_location = QtWidgets.QLineEdit()
        file_location.setText(self.main_win.app_settings.file_location)
        file_location.setReadOnly(True)
        file_location.setEnabled(False)
        self.search_dict["application file location"] = {tab: label_file_location}
        # label for the theme
        label_theme = QtWidgets.QLabel("Theme")
        label_theme.setToolTip(self.get_help_text(ProjectSettings, "theme"))
        theme = QtWidgets.QComboBox()
        theme.addItems(["dark", "light", "auto"])
        theme.setCurrentText(self.main_win.app_settings.theme)
        theme.setObjectName("theme")
        self.search_dict["theme"] = {tab: label_theme}
        # label for the joke type
        label_joke_type = QtWidgets.QLabel("Joke Type")
        label_joke_type.setToolTip(self.get_help_text(ProjectSettings, "joke_type"))
        joke_type = QtWidgets.QComboBox()
        joke_type.addItems(["programming", "dad"])
        joke_type.setCurrentText(self.main_win.app_settings.joke_type)
        joke_type.setObjectName("joke_type")
        self.search_dict["joke type"] = {tab: label_joke_type}

        # connect the text changed signals to update the settings
        theme.currentTextChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.app_settings)
        )
        joke_type.currentTextChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.app_settings)
        )
        # add the widgets to the layout
        tab_layout.addWidget(label_version)
        tab_layout.addRow(label_file_location, file_location)
        tab_layout.addRow(label_theme, theme)
        tab_layout.addRow(label_joke_type, joke_type)
        # add a button to reset the settings to default
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)
        # add the tab to the tab widget
        self.tab_widget.addTab(tab, "General Settings")

    def populate_playback_settings(self):
        tab = QtWidgets.QWidget()
        tab.setObjectName("playback_settings")
        tab_layout = QtWidgets.QFormLayout()
        tab.setLayout(tab_layout)
        # label for the seek video small
        label_seek_video_small = QtWidgets.QLabel("Seek Video Small")
        label_seek_video_small.setToolTip(
            self.get_help_text(Playback, "seek_video_small")
        )
        seek_video_small = QtWidgets.QSpinBox()
        seek_video_small.setValue(
            self.main_win.project_settings.playback.seek_video_small
        )
        seek_video_small.setObjectName("seek_video_small")
        self.search_dict["seek video small"] = {tab: label_seek_video_small}
        # label for the seek video medium
        label_seek_video_medium = QtWidgets.QLabel("Seek Video Medium")
        label_seek_video_medium.setToolTip(
            self.get_help_text(Playback, "seek_video_medium")
        )
        seek_video_medium = QtWidgets.QSpinBox()
        seek_video_medium.setValue(
            self.main_win.project_settings.playback.seek_video_medium
        )
        seek_video_medium.setObjectName("seek_video_medium")
        self.search_dict["seek video medium"] = {tab: label_seek_video_medium}
        # label for the seek video large
        label_seek_video_large = QtWidgets.QLabel("Seek Video Large")
        label_seek_video_large.setToolTip(
            self.get_help_text(Playback, "seek_video_large")
        )
        seek_video_large = QtWidgets.QSpinBox()
        seek_video_large.setValue(
            self.main_win.project_settings.playback.seek_video_large
        )
        seek_video_large.setObjectName("seek_video_large")
        self.search_dict["seek video large"] = {tab: label_seek_video_large}
        # label for the playback speed modulator
        label_playback_speed_modulator = QtWidgets.QLabel("Playback Speed Modulator")
        label_playback_speed_modulator.setToolTip(
            self.get_help_text(Playback, "playback_speed_modulator")
        )
        playback_speed_modulator = QtWidgets.QSpinBox()
        playback_speed_modulator.setValue(
            self.main_win.project_settings.playback.playback_speed_modulator
        )
        playback_speed_modulator.setObjectName("playback_speed_modulator")
        self.search_dict["playback speed modulator"] = {
            tab: label_playback_speed_modulator
        }
        # label for the seek timestamp small
        label_seek_timestamp_small = QtWidgets.QLabel("Seek Timestamp Small")
        label_seek_timestamp_small.setToolTip(
            self.get_help_text(Playback, "seek_timestamp_small")
        )
        seek_timestamp_small = QtWidgets.QSpinBox()
        seek_timestamp_small.setValue(
            self.main_win.project_settings.playback.seek_timestamp_small
        )

        seek_timestamp_small.setObjectName("seek_timestamp_small")
        self.search_dict["seek timestamp small"] = {tab: label_seek_timestamp_small}
        # label for the seek timestamp medium
        label_seek_timestamp_medium = QtWidgets.QLabel("Seek Timestamp Medium")
        label_seek_timestamp_medium.setToolTip(
            self.get_help_text(Playback, "seek_timestamp_medium")
        )
        seek_timestamp_medium = QtWidgets.QSpinBox()
        seek_timestamp_medium.setValue(
            self.main_win.project_settings.playback.seek_timestamp_medium
        )
        seek_timestamp_medium.setObjectName("seek_timestamp_medium")
        self.search_dict["seek timestamp medium"] = {tab: label_seek_timestamp_medium}
        # label for the seek timestamp large
        label_seek_timestamp_large = QtWidgets.QLabel("Seek Timestamp Large")
        label_seek_timestamp_large.setToolTip(
            self.get_help_text(Playback, "seek_timestamp_large")
        )
        seek_timestamp_large = QtWidgets.QSpinBox()
        seek_timestamp_large.setValue(
            self.main_win.project_settings.playback.seek_timestamp_large
        )
        seek_timestamp_large.setObjectName("seek_timestamp_large")
        self.search_dict["seek timestamp large"] = {tab: label_seek_timestamp_large}
        # connect the text changed signals to update the settings
        seek_video_small.valueChanged.connect(
            lambda value: self.settings_changed(
                value, self.main_win.project_settings.playback
            )
        )
        seek_video_medium.valueChanged.connect(
            lambda value: self.settings_changed(
                value, self.main_win.project_settings.playback
            )
        )
        seek_video_large.valueChanged.connect(
            lambda value: self.settings_changed(
                value, self.main_win.project_settings.playback
            )
        )
        playback_speed_modulator.valueChanged.connect(
            lambda value: self.settings_changed(
                value, self.main_win.project_settings.playback
            )
        )
        seek_timestamp_small.valueChanged.connect(
            lambda value: self.settings_changed(
                value, self.main_win.project_settings.playback
            )
        )
        seek_timestamp_medium.valueChanged.connect(
            lambda value: self.settings_changed(
                value, self.main_win.project_settings.playback
            )
        )
        seek_timestamp_large.valueChanged.connect(
            lambda value: self.settings_changed(
                value, self.main_win.project_settings.playback
            )
        )
        # add the widgets to the layout
        tab_layout.addRow(label_seek_video_small, seek_video_small)
        tab_layout.addRow(label_seek_video_medium, seek_video_medium)
        tab_layout.addRow(label_seek_video_large, seek_video_large)
        tab_layout.addRow(label_playback_speed_modulator, playback_speed_modulator)
        tab_layout.addRow(label_seek_timestamp_small, seek_timestamp_small)
        tab_layout.addRow(label_seek_timestamp_medium, seek_timestamp_medium)
        tab_layout.addRow(label_seek_timestamp_large, seek_timestamp_large)
        # add a button to reset the settings to default
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)
        # add the tab to the tab widget
        self.tab_widget.addTab(tab, "Playback Settings")

    def populate_scoring_settings(self):
        tab = QtWidgets.QWidget()
        tab.setObjectName("scoring_settings")
        tab_layout = QtWidgets.QGridLayout()
        tab.setLayout(tab_layout)
        # label for the scoring uid
        label_uid = QtWidgets.QLabel("UID")
        label_uid.setToolTip(self.get_help_text(Scoring, "uid"))
        uid = QtWidgets.QLineEdit()
        uid.setText(str(self.main_win.project_settings.scoring_data.uid))
        uid.setObjectName("uid")
        uid.setEnabled(False)
        uid.setReadOnly(True)
        self.search_dict["scoring uid"] = {tab: label_uid}
        # label for the video file location
        label_video_file_location = QtWidgets.QLabel("Video File Location")
        label_video_file_location.setToolTip(
            self.get_help_text(Scoring, "video_file_location")
        )
        video_file_location = QtWidgets.QLineEdit()
        video_file_location.setText(
            self.main_win.project_settings.scoring_data.video_file_location
        )
        video_file_location.setObjectName("video_file_location")
        video_file_location.mousePressEvent = lambda event: self.main_win.import_video()
        video_file_location.setReadOnly(True)
        self.search_dict["video file location"] = {tab: label_video_file_location}
        # label for the timestamp file location
        label_timestamp_file_location = QtWidgets.QLabel("Timestamp File Location")
        label_timestamp_file_location.setToolTip(
            self.get_help_text(Scoring, "timestamp_file_location")
        )
        timestamp_file_location = QtWidgets.QLineEdit()
        timestamp_file_location.setText(
            self.main_win.project_settings.scoring_data.timestamp_file_location
        )
        timestamp_file_location.setObjectName("timestamp_file_location")
        self.search_dict["timestamp file location"] = {
            tab: label_timestamp_file_location
        }
        tdt_data_info_button = QtWidgets.QPushButton("TDT Data Info")
        if self.main_win.project_settings.scoring_data.tdt_data is None:
            tdt_data_info_button = QtWidgets.QPushButton("Import TDT Data")
            tdt_data_info_button.clicked.connect(
                lambda: self.main_win.import_tdt_tank()
            )
        else:
            tdt_data_info_button = QtWidgets.QPushButton("TDT Data Info")
            tdt_data_info_button.clicked.connect(self.open_tdt_data_info_dialog)
        self.search_dict["tdt data"] = {tab: tdt_data_info_button}
        self.track_list_widget = QtWidgets.QListWidget()
        self.track_list_widget.addItems(
            [
                t.name
                for t in self.main_win.project_settings.scoring_data.behavior_tracks
            ]
        )
        self.track_list_widget.currentTextChanged.connect(
            lambda value: self.update_track_settings_widget(
                track_settings_widget, value
            )
        )
        # shrink track list widget to fit
        self.track_list_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Minimum
        )
        track_settings_widget = QtWidgets.QWidget()
        track_settings_layout = QtWidgets.QFormLayout()
        track_settings_widget.setLayout(track_settings_layout)
        # add the widgets to the layout
        tab_layout.addWidget(label_uid, 0, 0)
        tab_layout.addWidget(uid, 0, 1)
        tab_layout.addWidget(label_video_file_location, 1, 0)
        tab_layout.addWidget(video_file_location, 1, 1)
        tab_layout.addWidget(label_timestamp_file_location, 2, 0)
        tab_layout.addWidget(timestamp_file_location, 2, 1)
        tab_layout.addWidget(tdt_data_info_button, 3, 0)
        # horizontal line
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        # label for the behavior tracks
        label_behavior_tracks = QtWidgets.QLabel("Behavior Tracks")
        label_behavior_tracks.setToolTip(self.get_help_text(Scoring, "behavior_tracks"))
        # track widget to contain the track list and the track label and settings
        track_widget = QtWidgets.QWidget()
        track_layout = QtWidgets.QHBoxLayout()
        track_widget.setLayout(track_layout)
        track_layout.addWidget(self.track_list_widget)
        track_layout.addWidget(track_settings_widget)
        # add the widgets to the layout
        tab_layout.addWidget(line, 5, 0, 1, 2)
        tab_layout.addWidget(label_behavior_tracks, 6, 0)
        tab_layout.addWidget(track_widget, 7, 0, 1, 2)
        # populate the track settings widget with the first track
        if len(self.main_win.project_settings.scoring_data.behavior_tracks) > 0:
            self.update_track_settings_widget(
                track_settings_widget,
                self.main_win.project_settings.scoring_data.behavior_tracks[0].name,
            )
        # add a button to reset the settings to default

        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)
        # add the tab to the tab widget
        self.tab_widget.addTab(tab, "Scoring Settings")

    def open_tdt_data_info_dialog(self):
        # open a dialog with the tdt data info
        if self.main_win.project_settings.scoring_data.tdt_data is None:
            return
        # label and disabeled line edit for the
        # tankpath: str = ""
        # blockname: str = ""
        # blockpath: str = ""
        # start_date: str = ""
        # utc_start_time: str = ""
        # stop_date: str = ""
        # utc_stop_time: str = ""
        # duration: str = ""
        # video_path: Union[None, str, List[str]] = None
        # frame_ts_dict: Union[None, Dict[int, float]] = None

        # label for the tank path
        label_tank_path = QtWidgets.QLabel("Tank Path")
        tank_path_line_edit = QtWidgets.QLineEdit()
        tank_path_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.tankpath
        )
        tank_path_line_edit.setReadOnly(True)
        # label for the block name
        label_block_name = QtWidgets.QLabel("Block Name")
        block_name_line_edit = QtWidgets.QLineEdit()
        block_name_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.blockname
        )
        block_name_line_edit.setReadOnly(True)
        # label for the block path
        label_block_path = QtWidgets.QLabel("Block Path")
        block_path_line_edit = QtWidgets.QLineEdit()
        block_path_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.blockpath
        )
        block_path_line_edit.setReadOnly(True)
        # label for the start date
        label_start_date = QtWidgets.QLabel("Start Date")
        start_date_line_edit = QtWidgets.QLineEdit()
        start_date_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.start_date
        )
        start_date_line_edit.setReadOnly(True)
        # label for the utc start time
        label_utc_start_time = QtWidgets.QLabel("UTC Start Time")
        utc_start_time_line_edit = QtWidgets.QLineEdit()
        utc_start_time_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.utc_start_time
        )
        utc_start_time_line_edit.setReadOnly(True)
        # label for the stop date
        label_stop_date = QtWidgets.QLabel("Stop Date")
        stop_date_line_edit = QtWidgets.QLineEdit()
        stop_date_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.stop_date
        )
        stop_date_line_edit.setReadOnly(True)
        # label for the utc stop time
        label_utc_stop_time = QtWidgets.QLabel("UTC Stop Time")
        utc_stop_time_line_edit = QtWidgets.QLineEdit()
        utc_stop_time_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.utc_stop_time
        )
        utc_stop_time_line_edit.setReadOnly(True)
        # label for the duration
        label_duration = QtWidgets.QLabel("Duration")
        duration_line_edit = QtWidgets.QLineEdit()
        duration_line_edit.setText(
            self.main_win.project_settings.scoring_data.tdt_data.duration
        )
        duration_line_edit.setReadOnly(True)
        # label for the video path
        label_video_path = QtWidgets.QLabel("Video Path")
        video_path_line_edit = QtWidgets.QLineEdit()
        video_path_line_edit.setText(
            str(self.main_win.project_settings.scoring_data.tdt_data.video_path)
        )
        video_path_line_edit.setReadOnly(True)
        # label for the frame timestamp dict
        label_frame_ts_dict = QtWidgets.QLabel("Frame Timestamp Dict")
        frame_ts_dict_line_edit = QtWidgets.QLineEdit()
        # True if the frame timestamp dict is not None
        if (
            self.main_win.project_settings.scoring_data.tdt_data.frame_ts_dict
            is not None
        ):
            frame_ts_dict_line_edit.setText("True")
        else:
            frame_ts_dict_line_edit.setText("False")
        frame_ts_dict_line_edit.setReadOnly(True)
        # create a layout for the dialog
        layout = QtWidgets.QFormLayout()
        layout.addRow(label_tank_path, tank_path_line_edit)
        layout.addRow(label_block_name, block_name_line_edit)
        layout.addRow(label_block_path, block_path_line_edit)
        layout.addRow(label_start_date, start_date_line_edit)
        layout.addRow(label_utc_start_time, utc_start_time_line_edit)
        layout.addRow(label_stop_date, stop_date_line_edit)
        layout.addRow(label_utc_stop_time, utc_stop_time_line_edit)
        layout.addRow(label_duration, duration_line_edit)
        layout.addRow(label_video_path, video_path_line_edit)
        layout.addRow(label_frame_ts_dict, frame_ts_dict_line_edit)
        # create a dialog
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("TDT Data Info")
        dialog.setLayout(layout)
        dialog.exec()

    def update_track_settings_widget(
        self, track_settings_widget: QtWidgets.QWidget, track_name: str
    ):
        # clear the layout
        for i in reversed(range(track_settings_widget.layout().count())):
            track_settings_widget.layout().itemAt(i).widget().setParent(None)
        # add the widgets to the layout
        track_settings = None
        for track in self.main_win.project_settings.scoring_data.behavior_tracks:
            if track.name == track_name:
                track_settings = track
                break
        if track_settings is None:
            return
        # label for the behavior track name
        label_name = QtWidgets.QLabel("Name")
        name = QtWidgets.QLineEdit()
        name.setText(track_settings.name)
        name.setObjectName("name")
        name.mousePressEvent = lambda event: self.track_name_changed(track_settings)
        self.search_dict[f"{track_settings.name} name"] = {
            track_settings_widget: label_name
        }
        # label for the behavior track color
        label_color = QtWidgets.QLabel("Color")
        color = QtWidgets.QLineEdit()
        color.setText(track_settings.color)
        color.setObjectName("color")
        color.mousePressEvent = lambda event: self.track_color_picker(
            color, track_settings
        )
        # add the widgets to the layout
        track_settings_widget.layout().addRow(label_name, name)
        track_settings_widget.layout().addRow(label_color, color)

    def populate_behavior_track(
        self, tab_widget: QtWidgets.QTabWidget, behavior_track: BehaviorTrackSetting
    ):
        # create a widget for the tab
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout()
        tab.setLayout(tab_layout)
        # create a form layout for the widget
        form_layout = QtWidgets.QFormLayout()
        tab_layout.addLayout(form_layout)
        # label for the behavior track name
        label_name = QtWidgets.QLabel("Name")
        name = QtWidgets.QLineEdit()
        name.setText(behavior_track.name)
        name.setObjectName("name")
        # label for the behavior track color
        label_color = QtWidgets.QLabel("Color")
        color = QtWidgets.QLineEdit()
        color.setText(behavior_track.color)
        color.setObjectName("color")
        color_button = QtWidgets.QPushButton("Pick Color")
        color_button.clicked.connect(
            lambda: self.track_color_picker(color, behavior_track)
        )
        # add the widgets to the layout
        form_layout.addRow(label_name, name)
        form_layout.addRow(label_color, color)
        form_layout.addRow(color_button)

        tab_widget.addTab(tab, behavior_track.name)

    def track_color_picker(
        self, line_edit: QtWidgets.QLineEdit, track_settings: BehaviorTrackSetting
    ):
        # open a color picker dialog and update the line edit and settings
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            line_edit.setText(color.name())
            track_settings.color = color.name()
            self.main_win.timeline_dw.update_track_color(
                track_settings.name, track_settings.color
            )

    def reload_track_list(self):
        self.track_list_widget.clear()
        self.track_list_widget.addItems(
            [
                t.name
                for t in self.main_win.project_settings.scoring_data.behavior_tracks
            ]
        )

    def track_name_changed(self, track_settings: BehaviorTrackSetting):
        name = self.main_win.timeline_dw.rename_track(
            self.main_win.timeline_dw.timeline_view.get_track_from_name(
                track_settings.name
            )
        )
        if name is not None:

            track_settings.name = name
            self.reload_track_list()

    def guess_widget(self, field_name: str, f_type: type, settings: AbstSettings):
        """
        Given the name of a field and the type of the field, will return a widget that is appropriate for the field with no hooks

        Parameters
        ----------
        field_name : str
            The name of the field
        f_type : python type
            The type of the field
        settings : AbstSettings
            The settings object containing the field
        """
        widget = None
        # create a widget for the field
        if f_type == bool:
            widget = QtWidgets.QCheckBox()
            widget.setChecked(settings.__getattribute__(field_name))
        elif f_type == int:
            widget = QtWidgets.QSpinBox()
            widget.setValue(settings.__getattribute__(field_name))
        elif f_type == float:
            widget = QtWidgets.QDoubleSpinBox()
            widget.setMaximum(1000000)
            widget.setMinimum(-1000000)
            widget.setValue(settings.__getattribute__(field_name))
        elif f_type == str:
            # if it is a known path, make it open a file dialog when clicked
            if field_name in ["settings_file_location", "video_file_location"]:
                widget = QtWidgets.QLineEdit()
                widget.setText(settings.__getattribute__(field_name))
                widget.setReadOnly(True)
                widget.mousePressEvent = (
                    lambda event: QtWidgets.QFileDialog.getOpenFileName(
                        self,
                        "Open File",
                        "",
                        "All Files (*);;Text Files (*.txt);;JSON Files (*.json)",
                    )
                )
            else:
                widget = QtWidgets.QLineEdit()
                widget.setText(settings.__getattribute__(field_name))
        elif f_type == list:
            widget = QtWidgets.QListWidget()
            widget.addItems(settings.__getattribute__(field_name))

        elif hasattr(f_type, "__origin__") and f_type.__origin__ == typing.Literal:
            widget = QtWidgets.QComboBox()
            widget.addItems([str(x) for x in f_type.__args__])
            widget.setCurrentText(settings.__getattribute__(field_name))

        elif hasattr(f_type, "__origin__") and f_type.__origin__ == typing.Union:
            for arg in f_type.__args__:
                if arg == type(None):
                    continue
                elif arg == bool:
                    widget = QtWidgets.QCheckBox()
                    widget.setChecked(settings.__getattribute__(field_name))
                elif arg == int:
                    widget = QtWidgets.QSpinBox()
                    widget.setValue(settings.__getattribute__(field_name))
                elif arg == float:
                    widget = QtWidgets.QDoubleSpinBox()
                    widget.setMaximum(1000000)
                    widget.setMinimum(-1000000)
                    widget.setValue(settings.__getattribute__(field_name))
                elif arg == str:
                    widget = QtWidgets.QLineEdit()
                    widget.setText(settings.__getattribute__(field_name))
                elif arg == list:
                    widget = QtWidgets.QLineEdit()
                    widget.setText(str(settings.__getattribute__(field_name)))
                elif hasattr(arg, "__origin__") and arg.__origin__ == typing.Literal:
                    widget = QtWidgets.QComboBox()
                    widget.addItems([str(x) for x in arg.__args__])
                    widget.setCurrentText(settings.__getattribute__(field_name))
                break

        return widget

    def settings_changed(
        self,
        value,
        pyd_model: Union[ApplicationSettings, ScoringData, Playback, ProjectSettings],
    ):
        widget = self.sender()
        if not widget:
            return
        if pyd_model.__class__.__name__ == "ProjectSettings":
            self.main_win.project_settings.__setattr__(widget.objectName(), value)
        elif pyd_model.__class__.__name__ == "Playback":
            self.main_win.project_settings.playback.__setattr__(
                widget.objectName(), value
            )
        elif pyd_model.__class__.__name__ == "ScoringData":
            self.main_win.project_settings.scoring_data.__setattr__(
                widget.objectName(), value
            )
        elif pyd_model.__class__.__name__ == "ApplicationSettings":
            self.main_win.app_settings.__setattr__(widget.objectName(), value)
        else:
            raise ValueError(
                f"pyd_model must be one of ProjectSettings, Playback, or Scoring, not {pyd_model.__class__.__name__}"
            )

    def key_sequence_changed(self, value: QtGui.QKeySequence):
        widget = self.sender()
        if not widget:
            return
        self.main_win.project_settings.key_bindings.__setattr__(
            widget.objectName(), value.toString()
        )
        self.main_win.register_shortcut(widget.objectName(), value.toString())

    def get_help_text(
        self,
        pyd_model: Union[Scoring, Playback, ProjectSettings, ScoringData],
        field_name: str,
    ):
        try:
            help_text = str(pyd_model.help_text()[field_name])
            help_text = help_text.split(" ")
            help_text = [
                f"<b>{i.replace('_', ' ').title()}<b>" if i.__contains__("_") else i
                for i in help_text
            ]
            # fix the above line
            help_text = " ".join(help_text)
        except KeyError:
            help_text = ""
        return

    def toggleViewAction(self):
        self.refresh()
        return super().toggleViewAction()

    def refresh(self):
        self.pre_refresh_tab = self.tab_widget.currentIndex()
        self.tab_widget.clear()
        self.create_tabs()
        self.tab_widget.setCurrentIndex(self.pre_refresh_tab)
