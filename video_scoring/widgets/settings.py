import typing
from typing import TYPE_CHECKING, Union

import qdarktheme
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from video_scoring.settings.base_settings import (AbstSettings, KeyBindings,
                                                  Playback, ProjectSettings,
                                                  Scoring, ScoringData)

if TYPE_CHECKING:
    from main import MainWindow


class SettingsDockWidget(QtWidgets.QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(SettingsDockWidget, self).__init__(parent)
        self.setWindowTitle("Settings")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main_win = main_win
        # there will be tabs for each of the settings
        self.tab_widget = QtWidgets.QTabWidget()
        self.setWidget(self.tab_widget)
        self.tab_widget.setMovable(False)
        self.tab_widget.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)
        self.create_tabs()

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
        self.populate_tab(tab_widget=self.tab_widget, pyd_model=ProjectSettings())
        self.populate_tab(tab_widget=self.tab_widget, pyd_model=Playback())
        self.populate_tab(tab_widget=self.tab_widget, pyd_model=Scoring())
        self.populate_key_bindings()

    def populate_key_bindings(self):
        # for each of the key bindings in the settings create a label and a key sequence edit
        # create a widget for the tab
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout()
        tab.setLayout(tab_layout)
        # create a scroll area for the widget
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll_area.setStyleSheet("background-color: rgb(24,24,25);")
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

    def _video_file_location(self):
        # this is a path to the video file, I want a button next to a line edit which opens a file dialog
        # create a widget for the field
        widget = QtWidgets.QHBoxLayout()
        line_edit = QtWidgets.QLineEdit()
        line_edit.setText(self.main_win.project_settings.video_file_location)
        line_edit.setReadOnly(True)
        line_edit.mousePressEvent = lambda event: self.main_win.import_video()
        widget.addWidget(line_edit)
        button = QtWidgets.QPushButton("Open")
        button.clicked.connect(lambda: self.main_win.import_video())
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

    def color_picker(self, line_edit: QtWidgets.QLineEdit, settings: Scoring):
        # open a color picker dialog and update the line edit and settings
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            line_edit.setText(color.name())
            settings.text_color = color.name()

    def populate_tab(
        self,
        tab_widget: QtWidgets.QTabWidget,
        pyd_model: Union[Scoring, Playback, ProjectSettings],
    ):
        """This is a cluster fuck O_O"""
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
        self, value, pyd_model: Union[Scoring, Playback, ProjectSettings]
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
        elif pyd_model.__class__.__name__ == "Scoring":
            self.main_win.project_settings.scoring.__setattr__(
                widget.objectName(), value
            )
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
        self.main_win.register_shortcut_name(widget.objectName(), value.toString())

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

    def refresh(self):
        self.tab_widget.clear()
        self.create_tabs()
