"""
A simple dock widget that contains tabs for the video analysis widgets 
"""
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from video_scoring.widgets.analysis.freezing.freezing import FreezingWidget

if TYPE_CHECKING:
    from video_scoring import MainWindow


class VideoAnalysisDock(QDockWidget):
    def __init__(self, main_win: "MainWindow") -> None:
        super().__init__()
        self.main_win = main_win
        self.setWindowTitle("Video Analysis")
        self.main_widget = QWidget()
        self.layout = QVBoxLayout()
        self.main_widget.setLayout(self.layout)
        self.setWidget(self.main_widget)
        self.main_win.loaded.connect(self._init_ui)
        self.hide()

    def _init_ui(self):
        # We will then have a tab widget to hold the different analysis widgets
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)
        self.freezing_widget = FreezingWidget(
            file_path=self.main_win.video_player_dw.video_widget.video_file,
            vid_frame_len=self.main_win.video_player_dw.video_widget.play_worker.vc.len,
            main_win=self.main_win,
        )
        self.tab_widget.addTab(self.freezing_widget, "Freezing")
