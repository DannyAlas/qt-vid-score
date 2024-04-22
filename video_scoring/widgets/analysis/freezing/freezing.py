from typing import TYPE_CHECKING

import cv2
import numpy as np
from PyQt6.QtCore import QObject
from qtpy import QtCore, QtGui, QtWidgets

from video_scoring.widgets.progress import ProgressSignals

# a simple app to edit the freezing parameters
if TYPE_CHECKING:
    from video_scoring import MainWindow
    from video_scoring.widgets.analysis.analysis import VideoAnalysisDock


class MotionAnalysis(QtCore.QObject):
    complete = QtCore.Signal(list or None)

    def __init__(
        self,
        file_path,
        start_frame,
        end_frame,
        dsmpl_ratio=1,
        motion_threshold=10,
        gaussian_sigma=1,
        freezing_threshold=200,
        min_duration=15,
    ):
        super().__init__()
        self.file_path = file_path
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.dsmpl_ratio = dsmpl_ratio
        self.motion_threshold = motion_threshold
        self.gaussian_sigma = gaussian_sigma
        self.freezing_threshold = freezing_threshold
        self.min_duration = min_duration
        self.progress_signal = ProgressSignals()

    def run(self):
        self.progress_signal.started.emit()
        print(
            self.file_path,
            self.start_frame,
            self.end_frame,
            self.dsmpl_ratio,
            self.motion_threshold,
            self.gaussian_sigma,
            self.freezing_threshold,
            self.min_duration,
        )
        cap = cv2.VideoCapture(self.file_path)
        cap_max = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap_max = int(self.end_frame) if self.end_frame is not None else cap_max
        cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

        # Initialize first frame and array to store motion values in
        ret, frame_new = cap.read()
        frame_new = cv2.cvtColor(frame_new, cv2.COLOR_BGR2GRAY)

        if self.dsmpl_ratio < 1:
            frame_new = cv2.resize(
                frame_new,
                (
                    int(frame_new.shape[1] * self.dsmpl_ratio),
                    int(frame_new.shape[0] * self.dsmpl_ratio),
                ),
                cv2.INTER_NEAREST,
            )
        frame_new = cv2.GaussianBlur(
            frame_new.astype("float"), (0, 0), self.gaussian_sigma
        )
        self.motion = np.zeros(cap_max - self.start_frame)

        # Loop through frames to detect frame by frame differences
        for x in range(1, len(self.motion)):
            frame_old = frame_new
            ret, frame_new = cap.read()
            if ret == True:
                # Reset new frame and process calculate difference between old/new frames
                frame_new = cv2.cvtColor(frame_new, cv2.COLOR_BGR2GRAY)
                if self.dsmpl_ratio < 1:
                    frame_new = cv2.resize(
                        frame_new,
                        (
                            int(frame_new.shape[1] * self.dsmpl_ratio),
                            int(frame_new.shape[0] * self.dsmpl_ratio),
                        ),
                        cv2.INTER_NEAREST,
                    )
                frame_new = cv2.GaussianBlur(
                    frame_new.astype("float"), (0, 0), self.gaussian_sigma
                )
                frame_dif = np.absolute(frame_new - frame_old)
                frame_cut = (frame_dif > self.motion_threshold).astype("uint8")
                self.motion[x] = np.sum(frame_cut)
            else:
                # if no frame is detected
                x = x - 1  # Reset x to last frame detected
                self.motion = self.motion[:x]  # Amend length of motion vector
                break
            self.progress_signal.progress.emit(int((x / len(self.motion)) * 100))

        BelowThresh = (np.asarray(self.motion) < self.freezing_threshold).astype(int)

        # Perform local cumulative thresh detection
        # For each consecutive frame motion is below threshold count is increased by 1 until motion goes above thresh,
        # at which point coint is set back to 0
        CumThresh = np.zeros(len(self.motion))
        for x in range(1, len(self.motion)):
            if BelowThresh[x] == 1:
                CumThresh[x] = CumThresh[x - 1] + BelowThresh[x]
            # the percentage to be a portion of 50

        # Define periods where motion is below thresh for minduration as freezing
        Freezing = (CumThresh >= self.min_duration).astype(int)
        for x in range(len(Freezing) - 2, -1, -1):
            if (
                Freezing[x] == 0
                and Freezing[x + 1] > 0
                and Freezing[x + 1] < self.min_duration
            ):
                Freezing[x] = Freezing[x + 1] + 1

        Freezing = (Freezing > 0).astype(int)
        Freezing = Freezing * 100  # Convert to Percentage

        cap.release()  # release video
        self.progress_signal.complete.emit()
        self.complete.emit(Freezing)


class FreezingWidget(QtWidgets.QWidget):
    def __init__(
        self, analysis_widget: "VideoAnalysisDock", main_win: "MainWindow", parent=None
    ):
        super().__init__(parent=parent)
        self.analysis_widget = analysis_widget
        self.fpath = analysis_widget.file_name_line.text()
        print(self.fpath)
        self.main_win = main_win
        self.start = 0
        self.vid_len = 10000
        self.dsmpl = 1
        self.main_win = main_win

        # form layout
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        # make a scroll area to hold the widgets
        scroll_area = QtWidgets.QScrollArea()
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setLayout(QtWidgets.QFormLayout())
        self.scroll_widget.layout().addRow(QtWidgets.QLabel("Start Frame", self))

        self.start_frame = QtWidgets.QSpinBox(self)
        self.start_frame.setRange(0, self.vid_len)
        self.start_frame.setValue(0)
        self.start_frame.valueChanged.connect(lambda x: self.set_start(x))
        self.scroll_widget.layout().addRow(self.start_frame)

        self.scroll_widget.layout().addRow(QtWidgets.QLabel("End Frame", self))
        self.end_frame = QtWidgets.QSpinBox(self)
        self.end_frame.setRange(0, self.vid_len)
        self.end_frame.setValue(self.vid_len)
        self.end_frame.valueChanged.connect(lambda x: self.set_end(x))
        self.scroll_widget.layout().addRow(self.end_frame)

        self.scroll_widget.layout().addRow(QtWidgets.QLabel("Motion Threshold", self))
        self.motion_thresh = QtWidgets.QDoubleSpinBox(self)
        self.motion_thresh.setRange(0, 100000)
        self.motion_thresh.setDecimals(2)
        self.motion_thresh.setSingleStep(1)
        self.motion_thresh.setValue(10)
        self.scroll_widget.layout().addRow(self.motion_thresh)

        self.scroll_widget.layout().addRow(QtWidgets.QLabel("Motion Sigma", self))
        self.motion_sigma = QtWidgets.QDoubleSpinBox(self)
        self.motion_sigma.setRange(0, 100)
        self.motion_sigma.setValue(1)
        self.scroll_widget.layout().addRow(self.motion_sigma)

        self.scroll_widget.layout().addRow(QtWidgets.QLabel("Freezing Threshold", self))
        self.freezing_thresh = QtWidgets.QDoubleSpinBox(self)
        self.freezing_thresh.setRange(0, 100000)
        self.freezing_thresh.setDecimals(2)
        self.freezing_thresh.setSingleStep(1)
        self.freezing_thresh.setValue(200)
        self.scroll_widget.layout().addRow(self.freezing_thresh)

        self.scroll_widget.layout().addRow(QtWidgets.QLabel("Minimum Duration", self))
        self.min_duration = QtWidgets.QDoubleSpinBox(self)
        self.min_duration.setRange(0, 100000)
        self.min_duration.setDecimals(2)
        self.min_duration.setSingleStep(1)
        self.min_duration.setValue(15)
        self.scroll_widget.layout().addRow(self.min_duration)

        self.analyze_button = QtWidgets.QPushButton("Analyze", self)
        self.analyze_button.clicked.connect(self.analyze)

        self.scroll_widget.layout().addRow(self.analyze_button)

        scroll_area.setWidget(self.scroll_widget)
        scroll_area.setWidgetResizable(True)
        self.layout.addWidget(scroll_area)
        self.setLayout(self.layout)

    def set_start(self, start):
        self.start = start

    def set_end(self, end):
        self.end = end

    def analyze(self):
        # create new thread
        # change the button to say cancel
        # when the thread is complete, change the button back to analyze
        if hasattr(self, "motion_analyzer"):
            self.motion_analyzer.file_path = self.fpath
            self.motion_analyzer.start_frame = self.start
            self.motion_analyzer.end_frame = self.end
            self.motion_analyzer.dsmpl_ratio = self.dsmpl
            self.motion_analyzer.motion_threshold = self.motion_thresh.value()
            self.motion_analyzer.gaussian_sigma = self.motion_sigma.value()
            self.motion_analyzer.freezing_threshold = self.freezing_thresh.value()
            self.motion_analyzer.min_duration = self.min_duration.value()
        else:
            self.motion_analyzer_thread = QtCore.QThread()
            self.motion_analyzer = MotionAnalysis(
                self.fpath,
                self.start,
                self.end,
                self.dsmpl,
                self.motion_thresh.value(),
                self.motion_sigma.value(),
                self.freezing_thresh.value(),
                self.min_duration.value(),
            )
            self.motion_analyzer.moveToThread(self.motion_analyzer_thread)
            self.motion_analyzer_thread.started.connect(self.motion_analyzer.run)
            self.motion_analyzer.complete.connect(self.motion_analyzer_complete)
            self.motion_analyzer.complete.connect(self.motion_analyzer_thread.quit)
            self.motion_analyzer_thread.started.connect(
                lambda: self.main_win.start_pbar(
                    title="Analyzing Motion",
                    completed_msg="Motion Analysis Complete",
                    signals=self.motion_analyzer.progress_signal,
                )
            )
        # disable the analyze button
        self.analyze_button.setText("Cancel")
        self.analyze_button.setEnabled(False)
        self.motion_analyzer_thread.start()

    def motion_analyzer_complete(self, freezing):
        self.freezing = freezing
        self.freezing_behaviors = []
        for i, freezing in enumerate(self.freezing):
            if freezing == 100:
                if i == 0:
                    self.freezing_behaviors.append([i, i])
                elif self.freezing[i - 1] != 100:
                    self.freezing_behaviors.append([i, i])
                else:
                    self.freezing_behaviors[-1][1] = i

        self.main_win.status_bar.showMessage("Freezing Analysis Complete")
        if (
            self.main_win.timeline_dw.timeline_view.get_track_idx_from_name(
                "Freezing Analysis"
            )
            is None
        ):
            name = "Freezing Analysis"
        else:
            name = f"Freezing Analysis {len(self.main_win.timeline_dw.timeline_view.behavior_tracks)}"
        self.main_win.timeline_dw.timeline_view.add_behavior_track(name)
        for behavior in self.freezing_behaviors:
            self.main_win.timeline_dw.timeline_view.silent_add_oo_behavior(
                onset=behavior[0],
                track_idx=self.main_win.timeline_dw.timeline_view.get_track_idx_from_name(
                    name
                ),
                offset=behavior[1],
            )

        self.analyze_button.setText("Analyze")
        self.analyze_button.setEnabled(True)
        self.analyze_button.clicked.connect(self.analyze)
