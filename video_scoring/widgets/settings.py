from qtpy import QtWidgets, QtCore, QtGui
import typing
from typing import TYPE_CHECKING, Union

from video_scoring.settings import (
    Scoring,
    Playback,
    KeyBindings,
    ProjectSettings,
    AbstSettings,
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
        self.tab_widget.setMovable(False)
        self.tab_widget.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        self.tab_widget.setDocumentMode(True)
        self.create_tabs()

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
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(tab)
        tab_widget.addTab(scroll_area, pyd_model.__class__.__name__)
        # create a form layout for the widget
        form_layout = QtWidgets.QFormLayout()
        tab_layout.addLayout(form_layout)
        # iterate through the fields of the model
        for field_name in pyd_model.model_fields:
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
            help_text = str(pyd_model.help_text()[field_name])
            help_text = help_text.split(" ")
            help_text = [
                f"<b>{i.replace('_', ' ').title()}<b>" if i.__contains__("_") else i
                for i in help_text
            ]
            # fix the above line
            help_text = " ".join(help_text)
            label.setToolTip(help_text)
            widget = None

            if pyd_model.__class__.__name__ == "ProjectSettings":
                settings = self.main_win.project_settings
            elif pyd_model.__class__.__name__ == "Playback":
                settings = self.main_win.project_settings.playback
            elif pyd_model.__class__.__name__ == "Scoring":
                settings = self.main_win.project_settings.scoring
            else:
                raise ValueError(
                    f"pyd_model must be one of ProjectSettings, Playback, or Scoring, not {pyd_model.__class__.__name__}"
                )
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
                    elif (
                        hasattr(arg, "__origin__") and arg.__origin__ == typing.Literal
                    ):
                        widget = QtWidgets.QComboBox()
                        widget.addItems([str(x) for x in arg.__args__])
                        widget.setCurrentText(settings.__getattribute__(field_name))
                    break

            if widget is not None:
                form_layout.addRow(label, widget)
                widget.setObjectName(field_name)
                widget.setToolTip(help_text)
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

    def settings_changed(
        self, value, pyd_model: Union[Scoring, Playback, ProjectSettings]
    ):
        widget = self.sender()
        if not widget:
            return
        if pyd_model.__class__.__name__ == "ProjectSettings":
            self.main_win.project_settings.__setattr__(widget.objectName(), value)
            print(self.main_win.project_settings.__dict__)
        elif pyd_model.__class__.__name__ == "Playback":
            self.main_win.project_settings.playback.__setattr__(
                widget.objectName(), value
            )
            print(self.main_win.project_settings.playback.__dict__)
        elif pyd_model.__class__.__name__ == "Scoring":
            self.main_win.project_settings.scoring.__setattr__(
                widget.objectName(), value
            )
            print(self.main_win.project_settings.scoring.__dict__)
        else:
            print(pyd_model.__class__.__name__)

    def key_sequence_changed(self, value: QtGui.QKeySequence):
        widget = self.sender()
        if not widget:
            return
        self.main_win.project_settings.key_bindings.__setattr__(
            widget.objectName(), value.toString()
        )
        self.main_win.register_shortcut(widget.objectName(), value.toString())

    def refresh(self):
        self.tab_widget.clear()
        self.create_tabs()
