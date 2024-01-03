import multiprocessing as mp
import os
from tkinter import N
from typing import TYPE_CHECKING

import cv2
import numpy as np
from qtpy import QtCore, QtGui, QtWidgets

from video_scoring.settings.base_settings import AnalysisSettings, Crop

if TYPE_CHECKING:
    from video_scoring import MainWindow


class QtProgress:
    def __init__(self, iterable):
        self.iterable = iterable
        self.total = len(iterable)
        self.count = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.count < self.total:
            print(f"{self.count}/{self.total}")
            self.count += 1
            return self.iterable[self.count - 1]
        else:
            raise StopIteration

    def update(self):
        print(f"{self.count}/{self.total}")


class ROIDiff:
    def __init__(self, analysis_settings: AnalysisSettings):
        self.anst = analysis_settings
        cap = cv2.VideoCapture(self.anst.video_file_location)
        self.end = (
            int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if self.anst.end is None
            else self.anst.end
        )

    def set_roi(self, frame_num=2):
        cap = cv2.VideoCapture(self.anst.video_file_location)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        roi = cv2.selectROI(frame)
        cv2.destroyAllWindows()
        self.anst.roi_analysis.crop = Crop(
            x1=roi[0], x2=roi[0] + roi[2], y1=roi[1], y2=roi[1] + roi[3]
        )
        cap.release()

    def set_reference(self, num_frames=1000):
        if not os.path.isfile(self.anst.video_file_location):
            raise FileNotFoundError(
                "File not found. Check that directory and file names are correct."
            )
        cap = cv2.VideoCapture(self.anst.video_file_location)
        frames = np.linspace(
            0,
            min(self.end, int(cap.get(cv2.CAP_PROP_FRAME_COUNT))),
            num=num_frames,
            dtype=int,
        )
        collection = []
        for frame_num in frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if ret:
                frame = self.crop_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                collection.append(frame)
        self.anst.roi_analysis.reference = np.median(collection, axis=0)
        cap.release()

    def crop_frame(self, frame: np.ndarray):
        return frame[
            self.anst.roi_analysis.crop.y1 : self.anst.roi_analysis.crop.y2,
            self.anst.roi_analysis.crop.x1 : self.anst.roi_analysis.crop.x2,
        ]

    def get_dif(self, frame: np.ndarray):
        dif = {
            "abs": np.absolute,
            "light": np.subtract,
            "dark": lambda f, r: np.subtract(r, f),
        }.get(self.anst.roi_analysis.method, np.absolute)(
            frame, self.anst.roi_analysis.reference
        )
        return dif.astype("int16")

    def loop_frames(self):
        frames = np.linspace(self.anst.start, self.end, num=self.end, dtype=int)
        with mp.Pool(mp.cpu_count()) as pool:
            chunks = np.array_split(frames, mp.cpu_count())
            tasks = [
                pool.apply_async(
                    self.get_in_roi, args=(chunk, self.anst.roi_analysis.threshold)
                )
                for chunk in chunks
            ]
            results = []
            progress = QtProgress(tasks)
            for task in progress:
                results.append(task.get())
        self.anst.roi_analysis.diff_dict = {
            k: v for result in results for k, v in result.items()
        }

    def get_in_roi(self, chunk, threshold: int = 1):
        in_roi = {}
        cap = cv2.VideoCapture(self.anst.video_file_location)
        for f in chunk:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f)
            ret, frame = cap.read()
            if ret:
                frame = self.crop_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                dif = self.get_dif(frame)
                dif[dif < threshold] = 0
                in_roi[int(f)] = bool(np.any(dif > 0))
        cap.release()
        return in_roi


class ROIDiffThread(QtCore.QThread):
    def __init__(self, analysis_settings: AnalysisSettings):
        super().__init__()
        self.anst = analysis_settings
        self.roi_diff = ROIDiff(self.anst)

    def run(self):
        if self.anst.roi_analysis.crop is None:
            self.roi_diff.set_roi()
        if self.anst.roi_analysis.reference is None:
            self.roi_diff.set_reference()
        self.roi_diff.loop_frames()
        # done


# widget for roi analysis


class ROIAnalysisWidget(QtWidgets.QWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.main_win.project_loaded.connect(self._init_connections)
        self.main_win.project_loaded.connect(self.refresh)
        self._init_ui()

    def _init_ui(self):
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        # refresh button
        # a float spin box for the threshold
        self.start_frame = QtWidgets.QSpinBox()
        self.start_frame.setRange(0, 100000)
        self.start_frame.setSingleStep(1)
        self.start_frame.valueChanged.connect(self.update_start_frame)
        self.end_frame = QtWidgets.QSpinBox()
        self.end_frame.setRange(0, 100000)
        self.end_frame.setSingleStep(1)
        self.end_frame.valueChanged.connect(self.update_end_frame)
        # check box for whether to use selection for start and end or manually set
        self.use_selection = QtWidgets.QCheckBox("Use Selection")
        self.threshold = QtWidgets.QDoubleSpinBox()
        self.threshold.setRange(0, 255)
        self.threshold.setSingleStep(1)
        self.threshold.valueChanged.connect(self.update_threshold)
        self.method = QtWidgets.QComboBox()
        self.method.addItems(["Absolute", "Light", "Dark"])
        self.method.currentTextChanged.connect(self.update_method)
        self.preview_roi = QtWidgets.QPushButton("Preview ROI")
        self.preview_roi.clicked.connect(self.preview_roi_clicked)
        self.set_roi = QtWidgets.QPushButton("Set ROI")
        self.set_roi.clicked.connect(self.set_roi_clicked)
        self.preview_reference = QtWidgets.QPushButton("Preview Reference")
        self.preview_reference.clicked.connect(self.preview_reference_clicked)
        self.set_reference = QtWidgets.QPushButton("Set Reference")
        self.set_reference.clicked.connect(self.set_reference_clicked)
        self.start = QtWidgets.QPushButton("Start")
        self.start.clicked.connect(self.start_clicked)

        # first line is use selection, start, end
        self.layout.addWidget(self.use_selection, 0, 0)
        self.layout.addWidget(QtWidgets.QLabel("Start"), 0, 1)
        self.layout.addWidget(self.start_frame, 0, 2)
        self.layout.addWidget(QtWidgets.QLabel("End"), 0, 3)
        self.layout.addWidget(self.end_frame, 0, 4)
        # second line is threshold, method
        self.layout.addWidget(QtWidgets.QLabel("Threshold"), 1, 0)
        self.layout.addWidget(self.threshold, 1, 1)
        self.layout.addWidget(QtWidgets.QLabel("Method"), 1, 2)
        self.layout.addWidget(self.method, 1, 3)
        # third line is preview roi, set roi, preview reference, set reference
        self.layout.addWidget(self.preview_roi, 2, 0)
        self.layout.addWidget(self.set_roi, 2, 1)
        self.layout.addWidget(self.preview_reference, 3, 0)
        self.layout.addWidget(self.set_reference, 3, 1)
        # fourth line is start
        self.layout.addWidget(self.start, 4, 0)

    def _init_connections(self):
        self.main_win.timeline_dw.timeline_view.marker.signals.updated.connect(
            lambda: self.set_start_end(
                *self.main_win.timeline_dw.timeline_view.marker.get_selection()
            )
        )

    def set_start_end(self, start, end):
        if self.use_selection.isChecked():
            self.start_frame.setValue(start)
            self.end_frame.setValue(end)

    def refresh(self):
        self._init_connections()
        self.anst = self.main_win.project_settings.analysis_settings
        if self.anst.roi_analysis.roi is None:
            self.set_roi.setEnabled(True)
            self.preview_roi.setEnabled(False)
        else:
            self.set_roi.setEnabled(True)
            self.preview_roi.setEnabled(True)
        if self.anst.roi_analysis.reference is None:
            self.set_reference.setEnabled(True)
            self.preview_reference.setEnabled(False)
        else:
            self.set_reference.setEnabled(True)
            self.preview_reference.setEnabled(True)

        self.threshold.setValue(self.anst.roi_analysis.threshold)
        self.method.setCurrentText(self.anst.roi_analysis.method)

    def update_threshold(self, value):
        self.anst.roi_analysis.threshold = value

    def update_start_frame(self, value):
        self.anst.start = value

    def update_end_frame(self, value):
        self.anst.end = value

    def update_method(self, value):
        self.anst.roi_analysis.method = value

    def preview_roi_clicked(self):
        roi_diff = ROIDiff(self.anst)
        cap = cv2.VideoCapture(self.anst.video_file_location)
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return
        frame = roi_diff.crop_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        cv2.imshow("ROI", frame)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        cap.release()

    def set_roi_clicked(self):
        roi_diff = ROIDiff(self.anst)
        roi_diff.set_roi()
        self.preview_roi.setEnabled(True)

    def set_reference_clicked(self):
        roi_diff = ROIDiff(self.anst)
        roi_diff.set_reference()

    def preview_reference_clicked(self):
        roi_diff = ROIDiff(self.anst)
        cv2.imshow("Reference", roi_diff.anst.roi_analysis.reference)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def start_clicked(self):
        self.thread = ROIDiffThread(self.anst)
        self.thread.start()
        self.thread.finished.connect(self.thread_finished)

    def thread_finished(self):
        # the dict is a dictionary of frame numbers and whether the roi is active (bool)
        # convert it to a list of tuples representing the onsets and offsets of the roi activity events
        started_roi = False
        stream = []
        print(self.anst.roi_analysis.diff_dict)
        for frame, active in self.anst.roi_analysis.diff_dict.items():
            if active and not started_roi:
                stream.append((frame, frame))
                started_roi = True
            elif not active and started_roi:
                stream[-1] = (stream[-1][0], frame)
                started_roi = False
        track = self.main_win.timeline_dw.timeline_view.add_behavior_track("ROI")
        for onset, offset in stream:
            track.parent.add_oo_behavior(
                onset,
                offset,
                track_idx=self.main_win.timeline_dw.timeline_view.get_track_idx_from_name(
                    track.name
                ),
            )
