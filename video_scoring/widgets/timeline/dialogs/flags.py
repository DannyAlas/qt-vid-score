from typing import TYPE_CHECKING, List, Dict

from qtpy import QtWidgets, QtGui, QtCore
from qtpy.QtCore import Qt
from enum import IntEnum

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineDockWidget


class EventCodes(IntEnum):
    Mag_CSe = 47103
    Mag_CSm = 48127
    Mag_CSp_Pump = 48607
    Mag_CSp = 48639
    Mag = 49151
    CSe = 63487
    CSm = 64511
    Pump_CSp = 64991
    CSp = 65023
    Pump = 65503
    Offset = 65535


class FlagsDialog(QtWidgets.QDialog):
    def __init__(self, parent: "TimelineDockWidget"):
        super().__init__()
        self._parent = parent
        self.event_codes: Dict[str, List[int]] = {}
        self.flag_color: QtGui.QColor = QtGui.QColor("blue")
        self.setWindowTitle("Flags")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._init_ui()
        self._init()

    def _init_ui(self):
        # a vertical layout with a 3 sections
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        # header
        self.header_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.header_layout)
        self.header_label = QtWidgets.QLabel("Flag Manager")
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.header_label)
        self.header_layout.addStretch()
        # Center form layout
        self.form_layout = QtWidgets.QFormLayout()
        # two sections one with a combo box and the other with a color picker
        self.flag_combo = QtWidgets.QComboBox()
        self.layout.addLayout(self.form_layout)
        self.form_layout.addRow("Flag Name", self.flag_combo)
        self.color_picker = QtWidgets.QPushButton()
        self.color_picker.clicked.connect(self._on_item_color_clicked)
        self.color_picker.setStyleSheet(f"background-color: {self.flag_color.name()}")
        self.form_layout.addRow("Flag Color", self.color_picker)
        # bottom button layout
        self.button_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.add_button = QtWidgets.QPushButton("Add")
        self.add_button.clicked.connect(self.add_flags)
        self.button_layout.addWidget(self.add_button)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.cancel_button)

    def _on_item_color_clicked(self):
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self.flag_color.name()), self
        )
        if color.isValid():
            self.flag_color = color
            self.color_picker.setStyleSheet(
                f"background-color: {self.flag_color.name()}"
            )

    def _init(self):
        if self._parent.main_win.tdt is None:
            # change header label to "No TDT Data"
            self.header_label.setText("No TDT Data")
            self.header_label.setStyleSheet("color: red")
            # disable the add button
            self.add_button.setEnabled(False)
            # disable the combo box
            self.flag_combo.setEnabled(False)
            # disable the color picker
            self.color_picker.setEnabled(False)
            self.color_picker.setStyleSheet("background-color: gray")
        else:
            # enable the add button
            self.add_button.setEnabled(True)
            # enable the combo box
            self.flag_combo.setEnabled(True)
            # enable the color picker
            self.color_picker.setEnabled(True)
            # populate the combo box
            self.populate_combo()

    def populate_combo(self):
        # FIXME: this is static, we'll need a way to add event codes at runtime
        self.event_codes = {
            "CSp": [48607, 48639, 64991, 65023],
            "CSe": [47103, 63487],
            "CSm": [48127, 64511],
            "Mag Entry": [47103, 48127, 48607, 48639, 49151],
        }
        self.flag_combo.addItems(self.event_codes.keys())

    def add_flags(self):
        if self._parent.main_win.tdt is None:
            self._parent.main_win.update_status(
                "No TDT Data, please load TDT data first.", display_warning=True
            )
            return
        else:
            codes = self.event_codes[self.flag_combo.currentText()]
            frames_dict = self._parent.main_win.tdt.get_event_frames(
                {self.flag_combo.currentText(): codes}
            )
            frames = [f[0] for f in frames_dict[self.flag_combo.currentText()]]
            for f in frames:
                self._parent.timeline_ruler.add_flag(f, self.flag_color)
            self.close()
