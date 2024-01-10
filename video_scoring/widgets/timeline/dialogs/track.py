from typing import TYPE_CHECKING

from qtpy import QtWidgets
from qtpy.QtCore import Qt

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineDockWidget
    from video_scoring.widgets.timeline.track import BehaviorTrack


class AddTrackDialog(QtWidgets.QDialog):
    def __init__(self, parent: "TimelineDockWidget"):
        super().__init__()
        self._parent = parent
        self.setWindowTitle("Add Track")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.WindowTitleHint, False)
        self.setFixedSize(300, 100)
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Track Name")
        self.layout.addWidget(self.name_input)
        self.button_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.add_button = QtWidgets.QPushButton("Add")
        self.add_button.clicked.connect(self.add_track)
        self.add_button.setDefault(True)
        self.button_layout.addWidget(self.add_button)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.cancel_button)

    def add_track(self):
        name = self.name_input.text()
        if name:
            try:
                self._parent.timeline_view.add_behavior_track(name)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
            self.close()


class RenameTrackDialog(QtWidgets.QDialog):
    def __init__(self, parent: "TimelineDockWidget", track: "BehaviorTrack"):
        super().__init__()
        self.parent = parent
        self.track = track
        self.setWindowTitle("Rename Track")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.WindowTitleHint, False)
        self.setFixedSize(300, 100)
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText(self.track.name)
        self.layout.addWidget(self.name_input)
        self.button_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.add_button = QtWidgets.QPushButton("Rename")
        self.add_button.clicked.connect(self.rename_track)
        self.add_button.setDefault(True)
        self.button_layout.addWidget(self.add_button)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.cancel_button)

    def rename_track(self):
        name = self.name_input.text()
        if name:
            self.track.name = name
            self.track.update_name(name)
            self.close()
