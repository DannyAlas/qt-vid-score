"""
A simple dock widget that contains tabs for the video analysis widgets 
"""
from typing import TYPE_CHECKING

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from video_scoring.widgets.analysis.roi.roi_analysis import ROIAnalysisWidget

if TYPE_CHECKING:
    from video_scoring import MainWindow


class VideoAnalysisDock(QtWidgets.QDockWidget):
    def __init__(self, main_win: "MainWindow") -> None:
        super().__init__()
        self.main_win = main_win
        self.setWindowTitle("Video Analysis")
        self.main_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QVBoxLayout()
        self.main_widget.setLayout(self.layout)
        self.setWidget(self.main_widget)
        self.roi_analysis_widget = ROIAnalysisWidget(self.main_win)
        self.main_win.loaded.connect(self._init_ui)
        self.main_win.project_loaded.connect(self.refresh)

    def _init_ui(self):
        self.main_widget = QtWidgets.QWidget()
        self.layout = QtWidgets.QGridLayout()
        self.main_widget.setLayout(self.layout)
        self.setWidget(self.main_widget)

        self.tab_widget = QtWidgets.QTabWidget()
        self.file_label = QtWidgets.QLabel("File:")
        self.file_name_line = QtWidgets.QLineEdit()
        self.file_name_line.setReadOnly(True)
        self.file_name_line.mousePressEvent = lambda _: self.main_win.import_video()

        self.layout.addWidget(self.file_label, 0, 0)
        self.layout.addWidget(self.file_name_line, 0, 1)
        self.layout.addWidget(self.tab_widget, 1, 0, 1, 2)

        self.tab_widget.addTab(self.roi_analysis_widget, "ROI Analysis")

    def refresh(self):
        self.file_name_line.setText(
            self.main_win.project_settings.scoring_data.video_file_location
        )
        self.main_win.project_settings.analysis_settings.video_file_location = (
            self.main_win.project_settings.scoring_data.video_file_location
        )
        self.roi_analysis_widget.refresh()
