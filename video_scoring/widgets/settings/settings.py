import typing
from typing import TYPE_CHECKING, Union

import qdarktheme
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from video_scoring.settings.base_settings import (
    AbstSettings,
    ApplicationSettings,
    BehaviorTrackSetting,
    Playback,
    ProjectSettings,
    Scoring,
    ScoringData,
)

if TYPE_CHECKING:
    from main import MainWindow


class SettingsDockWidget(QtWidgets.QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(SettingsDockWidget, self).__init__(parent)
        self.setWindowTitle("Settings")
        self.main_win = main_win
        # there will be tabs for each of the settings
        self.tab_widget = QtWidgets.QTabWidget()
        self.setWidget(self.tab_widget)
        self.tab_widget.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)
        self.create_tabs()
        self.main_win.loaded.connect(self.refresh)
        self.setFloating(True)

    def reset_settings(self):
        # open a dialog to confirm
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setText("Reset Settings")
        msg.setInformativeText(
            "Are you sure you want to reset the settings to default?"
        )
        msg.setWindowTitle("Reset Settings")
        msg.setStandardButtons(
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Cancel)
        ret = msg.exec()
        if ret == QtWidgets.QMessageBox.StandardButton.Cancel:
            return
        # reset the settings to default
        self.main_win.project_settings = ProjectSettings()
        self.refresh()

    def create_tabs(self):
        self.populate_general_settings()
        self.populate_project_settings()
        # self.populate_tab(tab_widget=self.tab_widget, pyd_model=Playback())
        self.populate_playback_settings()
        self.populate_scoring_settings()
        self.populate_key_bindings()

    def populate_key_bindings(self):
        if self.main_win.project_settings is None:
            return
        # for each of the key bindings in the settings create a label and a key sequence edit
        # create a widget for the tab
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout()
        tab.setLayout(tab_layout)
        # create a scroll area for the widget
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(tab)

        self.tab_widget.addTab(scroll_area, "Key Bindings")
        # create a form layout for the widget
        form_layout = QtWidgets.QFormLayout()
        tab_layout.addLayout(form_layout)
        # iterate through the fields of the model
        for (
            action_name,
            key_sequence,
        ) in self.main_win.project_settings.key_bindings.__dict__.items():
            # create a label for the field
            label = QtWidgets.QLabel(action_name.replace("_", " ").title())
            widget = QtWidgets.QKeySequenceEdit()
            widget.setKeySequence(QtGui.QKeySequence(key_sequence))
            form_layout.addRow(label, widget)
            widget.setObjectName(action_name)
            widget.setToolTip(
                self.main_win.project_settings.key_bindings.help_text().get(
                    action_name, ""
                )
            )
            widget.keySequenceChanged.connect(self.key_sequence_changed)

        tab_layout.addStretch()
        # add a button to reset the settings to default
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)

    def populate_project_settings(self):
        if self.main_win.project_settings is None:
            return
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QFormLayout()
        tab.setLayout(tab_layout)
        # label for the project uid but it is not editable
        label = QtWidgets.QLabel("UID")
        label.setToolTip("Unique Identifier for the project")
        uid = QtWidgets.QLineEdit()
        uid.setText(str(self.main_win.project_settings.uid))
        uid.setReadOnly(True)
        uid.setEnabled(False)
        uid.setObjectName("uid")
        # label for the project name
        label_name = QtWidgets.QLabel("Name")
        label_name.setToolTip(self.get_help_text(ProjectSettings, "name"))
        name = QtWidgets.QLineEdit()
        name.setText(self.main_win.project_settings.name)
        name.setObjectName("name")
        # label for the project scorer
        label_scorer = QtWidgets.QLabel("Scorer")
        label_scorer.setToolTip(self.get_help_text(ProjectSettings, "scorer"))
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
        # label for the project modified date not editable
        label_modified = QtWidgets.QLabel("Modified")
        label_modified.setToolTip(self.get_help_text(ProjectSettings, "modified"))
        modified = QtWidgets.QLineEdit()
        modified.setText(str(self.main_win.project_settings.modified))
        modified.setReadOnly(True)
        modified.setEnabled(False)
        # label for the project file location
        label_file_location = QtWidgets.QLabel("File Location")
        label_file_location.setToolTip(self.get_help_text(ProjectSettings, "file_location"))
        file_location = QtWidgets.QLineEdit()
        file_location.setText(self.main_win.project_settings.file_location)
        file_location.setReadOnly(True)
        file_location.setEnabled(False)
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
        tab_layout.addRow(label_created, created)
        tab_layout.addRow(label_modified, modified)
        tab_layout.addRow(label_file_location, file_location)
        # add a button to reset the settings to default
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)
        # add the tab to the tab widget
        self.tab_widget.addTab(tab, f"{self.main_win.project_settings.name.capitalize()} Settings")

    def populate_general_settings(self):
        if self.main_win.project_settings is None:
            return
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QFormLayout()
        tab.setLayout(tab_layout)
        # label for the project version
        label_version = QtWidgets.QLabel(f"Version: {self.main_win.app_settings.version}")
        # label for the file location
        label_file_location = QtWidgets.QLabel("File Location")
        label_file_location.setToolTip(self.get_help_text(ProjectSettings, "file_location"))
        file_location = QtWidgets.QLineEdit()   
        file_location.setText(self.main_win.app_settings.file_location)
        file_location.setReadOnly(True)
        file_location.setEnabled(False)
        # label for the theme
        label_theme = QtWidgets.QLabel("Theme")
        label_theme.setToolTip(self.get_help_text(ProjectSettings, "theme"))
        theme = QtWidgets.QComboBox()
        theme.addItems(["dark", "light", "auto"])
        theme.setCurrentText(self.main_win.app_settings.theme)
        theme.setObjectName("theme")
        # label for the joke type
        label_joke_type = QtWidgets.QLabel("Joke Type") 
        label_joke_type.setToolTip(self.get_help_text(ProjectSettings, "joke_type"))
        joke_type = QtWidgets.QComboBox()
        joke_type.addItems(["programming", "dad"])
        joke_type.setCurrentText(self.main_win.app_settings.joke_type)
        joke_type.setObjectName("joke_type")

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
        if self.main_win.project_settings is None:
            return
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QFormLayout()
        tab.setLayout(tab_layout)
        # label for the seek video small
        label_seek_video_small = QtWidgets.QLabel("Seek Video Small")
        label_seek_video_small.setToolTip(self.get_help_text(Playback, "seek_video_small"))
        seek_video_small = QtWidgets.QSpinBox()
        seek_video_small.setValue(self.main_win.project_settings.playback.seek_video_small)
        seek_video_small.setObjectName("seek_video_small")
        # label for the seek video medium
        label_seek_video_medium = QtWidgets.QLabel("Seek Video Medium")
        label_seek_video_medium.setToolTip(self.get_help_text(Playback, "seek_video_medium"))
        seek_video_medium = QtWidgets.QSpinBox()
        seek_video_medium.setValue(self.main_win.project_settings.playback.seek_video_medium)
        seek_video_medium.setObjectName("seek_video_medium")
        # label for the seek video large
        label_seek_video_large = QtWidgets.QLabel("Seek Video Large")
        label_seek_video_large.setToolTip(self.get_help_text(Playback, "seek_video_large"))
        seek_video_large = QtWidgets.QSpinBox()
        seek_video_large.setValue(self.main_win.project_settings.playback.seek_video_large)
        seek_video_large.setObjectName("seek_video_large")
        # label for the playback speed modulator
        label_playback_speed_modulator = QtWidgets.QLabel("Playback Speed Modulator")
        label_playback_speed_modulator.setToolTip(self.get_help_text(Playback, "playback_speed_modulator"))
        playback_speed_modulator = QtWidgets.QSpinBox()
        playback_speed_modulator.setValue(self.main_win.project_settings.playback.playback_speed_modulator)
        playback_speed_modulator.setObjectName("playback_speed_modulator")
        # label for the seek timestamp small
        label_seek_timestamp_small = QtWidgets.QLabel("Seek Timestamp Small")
        label_seek_timestamp_small.setToolTip(self.get_help_text(Playback, "seek_timestamp_small"))
        seek_timestamp_small = QtWidgets.QSpinBox()
        seek_timestamp_small.setValue(self.main_win.project_settings.playback.seek_timestamp_small)

        seek_timestamp_small.setObjectName("seek_timestamp_small")
        # label for the seek timestamp medium
        label_seek_timestamp_medium = QtWidgets.QLabel("Seek Timestamp Medium")
        label_seek_timestamp_medium.setToolTip(self.get_help_text(Playback, "seek_timestamp_medium"))
        seek_timestamp_medium = QtWidgets.QSpinBox()
        seek_timestamp_medium.setValue(self.main_win.project_settings.playback.seek_timestamp_medium)
        seek_timestamp_medium.setObjectName("seek_timestamp_medium")
        # label for the seek timestamp large
        label_seek_timestamp_large = QtWidgets.QLabel("Seek Timestamp Large")
        label_seek_timestamp_large.setToolTip(self.get_help_text(Playback, "seek_timestamp_large"))
        seek_timestamp_large = QtWidgets.QSpinBox()
        seek_timestamp_large.setValue(self.main_win.project_settings.playback.seek_timestamp_large)
        seek_timestamp_large.setObjectName("seek_timestamp_large")

        # connect the text changed signals to update the settings
        seek_video_small.valueChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings.playback)
        )
        seek_video_medium.valueChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings.playback)
        )
        seek_video_large.valueChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings.playback)
        )
        playback_speed_modulator.valueChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings.playback)
        )
        seek_timestamp_small.valueChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings.playback)
        )
        seek_timestamp_medium.valueChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings.playback)
        )
        seek_timestamp_large.valueChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings.playback)
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
        if self.main_win.project_settings is None:
            return
        tab = QtWidgets.QWidget()
        tab_tabs = QtWidgets.QTabWidget()
        tab_tabs.setMovable(False)
        # vertical layout for the tab widget
        tab_tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        tab_tabs.setDocumentMode(True)
        tab_layout = QtWidgets.QFormLayout()
        tab.setLayout(tab_layout)
        tab_layout.addWidget(tab_tabs)
        # label for the scoring uid
        label_uid = QtWidgets.QLabel("UID")
        label_uid.setToolTip(self.get_help_text(Scoring, "uid"))
        uid = QtWidgets.QLineEdit()
        uid.setText(self.main_win.project_settings.scoring_data.uid)
        uid.setObjectName("uid")
        uid.setEnabled(False)
        uid.setReadOnly(True)
        tab_layout.addRow(label_uid, uid)
        # label for the video file location
        label_video_file_location = QtWidgets.QLabel("Video File Location")
        label_video_file_location.setToolTip(self.get_help_text(Scoring, "video_file_location"))
        video_file_location = QtWidgets.QLineEdit()
        video_file_location.setText(self.main_win.project_settings.scoring_data.video_file_location)
        video_file_location.setObjectName("video_file_location")
        # label for the video file name
        label_video_file_name = QtWidgets.QLabel("Video File Name")
        label_video_file_name.setToolTip(self.get_help_text(Scoring, "video_file_name"))
        video_file_name = QtWidgets.QLineEdit()
        video_file_name.setText(self.main_win.project_settings.scoring_data.video_file_name)
        video_file_name.setObjectName("video_file_name")
        # label for the timestamp file location
        label_timestamp_file_location = QtWidgets.QLabel("Timestamp File Location")
        label_timestamp_file_location.setToolTip(self.get_help_text(Scoring, "timestamp_file_location"))
        timestamp_file_location = QtWidgets.QLineEdit()
        timestamp_file_location.setText(self.main_win.project_settings.scoring_data.timestamp_file_location)
        timestamp_file_location.setObjectName("timestamp_file_location")
        # each behavior track will have a tab inside of the scoring settings tab
        # for each behavior track create a tab
        for behavior_track in self.main_win.project_settings.scoring_data.behavior_tracks:
            self.populate_behavior_track(tab_tabs, behavior_track)
        # populate the scoring settings tab
        tab_layout.addRow(label_video_file_location, video_file_location)
        tab_layout.addRow(label_video_file_name, video_file_name)
        tab_layout.addRow(label_timestamp_file_location, timestamp_file_location)
        # add a button to reset the settings to default
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)
        # add the tab to the tab widget
        self.tab_widget.addTab(tab, "Scoring Settings")
        
    def populate_behavior_track(self, tab_widget: QtWidgets.QTabWidget, behavior_track: BehaviorTrackSetting):
        if self.main_win.project_settings is None:
            return

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
        

        
        

    ############ Custom widgets for settings ############
    def _settings_file_location(self):
        # this is a path to the settings file, I want a button next to a line edit which opens a file dialog
        # create a widget for the field
        widget = QtWidgets.QHBoxLayout()
        line_edit = QtWidgets.QLineEdit()
        line_edit.setText(self.main_win.project_settings.settings_file_location)
        line_edit.setReadOnly(True)
        line_edit.mousePressEvent = lambda event: self.main_win.open_project()
        widget.addWidget(line_edit)
        button = QtWidgets.QPushButton("Open")
        button.clicked.connect(lambda: self.main_win.open_project())
        # update the value of the field when the button is clicked
        widget.addWidget(button)
        return widget

    def _theme(self):
        # this is a combo box with the available themes, changing the theme will change the theme of the main window
        widget = QtWidgets.QComboBox()
        widget.addItems(["dark", "light", "auto"])
        widget.setCurrentText(self.main_win.project_settings.theme)
        # change theme with main window method and update settings
        widget.currentTextChanged.connect(
            lambda value: self.main_win.change_theme(value)
        )
        widget.currentTextChanged.connect(
            lambda value: self.settings_changed(value, self.main_win.project_settings)
        )
        return widget

    def _text_color(self):
        # widget is a line edit with a color picker
        widget = QtWidgets.QHBoxLayout()
        line_edit = QtWidgets.QLineEdit()
        line_edit.setText(str(self.main_win.project_settings.scoring.text_color))
        line_edit.setReadOnly(True)
        button = QtWidgets.QPushButton("Pick Color")
        button.clicked.connect(
            lambda: self.color_picker(line_edit, self.main_win.project_settings.scoring)
        )
        widget.addWidget(line_edit)
        widget.addWidget(button)
        return widget

    def track_color_picker(self, line_edit: QtWidgets.QLineEdit, settings: BehaviorTrackSetting):
        # open a color picker dialog and update the line edit and settings
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            line_edit.setText(color.name())
            settings.color = color.name()
            self.main_win.timeline_dw.update_track_color(settings.name, settings.color)
            
    def populate_tab(
        self,
        tab_widget: QtWidgets.QTabWidget,
        pyd_model: Union[Scoring, Playback, ProjectSettings],
    ):
        # create a widget for the tab
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout()
        tab.setLayout(tab_layout)
        # create a scroll area for the widget
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(tab)
        tab_widget.addTab(scroll_area, pyd_model.__class__.__name__)
        # create a form layout for the widget
        form_layout = QtWidgets.QFormLayout()
        tab_layout.addLayout(form_layout)
        # iterate through the fields of the model
        for field_name in pyd_model.model_fields:
            # ignore top level fields
            if field_name in [
                "scoring",
                "playback",
                "key_bindings",
                "projectSettings",
                "timestamps",
            ]:
                continue
            # create a label for the field
            label = QtWidgets.QLabel(field_name.replace("_", " ").title())
            f_type = typing.get_type_hints(pyd_model)[field_name]
            # help text will have the feild name as the_field_name, convert to bolded 'The Field Name'
            help_text = self.get_help_text(pyd_model, field_name)

            if pyd_model.__class__.__name__ == "ProjectSettings":
                settings = self.main_win.project_settings
            elif pyd_model.__class__.__name__ == "Playback":
                settings = self.main_win.project_settings.playback
            elif pyd_model.__class__.__name__ == "Scoring":
                settings = self.main_win.project_settings.scoring_data
            else:
                raise ValueError(
                    f"pyd_model must be one of ProjectSettings, Playback, or Scoring, not {pyd_model.__class__.__name__}"
                )

            # if we have a method for this field, use it
            # the method will be called the name of the field with an underscore in front
            # e.g. _settings_file_location
            if hasattr(self, f"_{field_name}"):
                widget = getattr(self, f"_{field_name}")()
            else:
                widget = self.guess_widget(field_name, f_type, settings)
                if widget is not None:
                    try:
                        widget.valueChanged.connect(
                            lambda value: self.settings_changed(value, pyd_model)
                        )
                    except AttributeError:
                        pass
                    try:
                        widget.currentTextChanged.connect(
                            lambda value: self.settings_changed(value, pyd_model)
                        )
                    except AttributeError:
                        pass
                    try:
                        widget.textChanged.connect(
                            lambda value: self.settings_changed(value, pyd_model)
                        )
                    except AttributeError:
                        pass
            if widget is not None:
                form_layout.addRow(label, widget)
                widget.setObjectName(field_name)
                label.setToolTip(help_text)

        tab_layout.addStretch()
        # add a button to reset the settings to default
        reset_button = QtWidgets.QPushButton("Reset Settings")
        reset_button.clicked.connect(self.reset_settings)
        tab_layout.addWidget(reset_button)

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
        self, value, pyd_model: Union[ApplicationSettings, ScoringData, Playback, ProjectSettings]
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
        self.tab_widget.clear()
        self.create_tabs()
