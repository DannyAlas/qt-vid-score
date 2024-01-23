import dis
import logging
from typing import TYPE_CHECKING, Literal, Optional

from qtpy import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineView
    from video_scoring.widgets.timeline.track import BehaviorTrack
    from video_scoring.widgets.timeline.track_header import TrackHeader


class TrackSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: "TrackHeader", track: "BehaviorTrack"):
        super().__init__(parent)
        self.parent = parent
        self._parent = parent
        self.track = track
        self.setWindowTitle(f"Track Settings: {self.track.name}")
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        self._init_ui()

    def _init_ui(self):
        # a form layout for the track settings
        self.form_layout = QtWidgets.QGridLayout()

        # name line edit, item color picker, shortcut key sequence edit, unsure shortcut key sequence edit
        self.name_label = QtWidgets.QLabel("Name")
        self.name_line_edit = QtWidgets.QLineEdit(self.track.name)
        self.name_line_edit.textChanged.connect(self._on_name_changed)
        self.item_color_label = QtWidgets.QLabel("Item Color")
        self.item_color_picker = QtWidgets.QPushButton()
        self.item_color_picker.clicked.connect(self._on_item_color_clicked)
        self.item_color_picker.setStyleSheet(
            f"background-color: {self.track.item_color}"
        )
        self.shortcut_label = QtWidgets.QLabel("Save Shortcut")
        self.shortcut_edit = QtWidgets.QKeySequenceEdit()
        self.shortcut_edit.setKeySequence(self.track.save_ts_ks)
        self.shortcut_edit.keySequenceChanged.connect(self._on_shortcut_changed)
        self.unsure_shortcut_label = QtWidgets.QLabel("Save Unsure Shortcut")
        self.unsure_shortcut_edit = QtWidgets.QKeySequenceEdit()
        self.unsure_shortcut_edit.setKeySequence(self.track.save_uts_ks)
        self.unsure_shortcut_edit.keySequenceChanged.connect(
            self._on_unsure_shortcut_changed
        )
        self.form_layout.addWidget(self.name_label, 0, 0)
        self.form_layout.addWidget(self.name_line_edit, 0, 1)
        self.form_layout.addWidget(self.item_color_label, 1, 0)
        self.form_layout.addWidget(self.item_color_picker, 1, 1)
        self.form_layout.addWidget(self.shortcut_label, 2, 0)
        self.form_layout.addWidget(self.shortcut_edit, 2, 1)
        self.form_layout.addWidget(self.unsure_shortcut_label, 3, 0)
        self.form_layout.addWidget(self.unsure_shortcut_edit, 3, 1)

        # a button box for the ok and cancel buttons
        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.setStandardButtons(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # a layout for the button box
        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.button_box)

        # a layout for the form layout and button layout
        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.addLayout(self.form_layout)
        self.main_layout.addLayout(self.button_layout)

        # set the main layout
        self.setLayout(self.main_layout)

    def _on_name_changed(self, text: str):
        self._parent.update_track_name(text)
        self.setWindowTitle(f"Track Settings: {self.track.name}")

    def _on_item_color_clicked(self):
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self.track.item_color), self
        )
        if color.isValid():
            self.track.update_item_colors(color.name())
            self.item_color_picker.setStyleSheet(
                f"background-color: {self.track.item_color}"
            )

    def _on_shortcut_changed(self, key_sequence: QtGui.QKeySequence):
        # TODO: check if the shortcut is already taken, notify user if it is
        if key_sequence == self.track.save_ts_ks or key_sequence.toString() == "":
            return
        try:
            self.track.update_shortcut(key_sequence)
            self.shortcut_edit.setStyleSheet("")
        except Exception as e:
            # notify the user that the shortcut is already taken
            self._parent.timeline.main_window.update_status(
                f"{e}", do_log=False, log_level=logging.WARN, display_error=True
            )
            # color the shortcut edit red
            self.shortcut_edit.setKeySequence(self.track.save_ts_ks)
            self.shortcut_edit.setStyleSheet("border: 1px solid red")

    def _on_unsure_shortcut_changed(self, key_sequence: QtGui.QKeySequence):
        if key_sequence == self.track.save_uts_ks or key_sequence.toString() == "":
            return
        try:
            self.track.update_unsure_shortcut(key_sequence)
            self.unsure_shortcut_edit.setStyleSheet("")
        except Exception as e:
            # notify the user that the shortcut is already taken
            self._parent.timeline.main_window.update_status(
                f"{e}", log_level=logging.ERROR, display_error=True, do_log=False
            )
            self.unsure_shortcut_edit.setKeySequence(self.track.save_uts_ks)
            # color the shortcut edit border red
            self.unsure_shortcut_edit.setStyleSheet("border: 1px solid red")

    def accept(self):
        super().accept()
