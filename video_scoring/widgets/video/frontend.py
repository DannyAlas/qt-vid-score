from email.charset import QP
from tkinter import E
from typing import TYPE_CHECKING, Literal

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QObject, Qt, QThread, QUrl, Signal, Slot
from qtpy.QtGui import QBrush, QImage, QPainter, QPixmap
from qtpy.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from video_scoring.widgets.video.backend import VideoPlayer

if TYPE_CHECKING:
    from video_scoring import MainWindow


class VideoDisplay(QLabel):
    """A QLabel where we always repaint the most recent frame"""

    def __init__(self, parent: "VideoWidget"):
        super(VideoDisplay, self).__init__(parent)
        self.parent = parent
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(1, 1)
        self.setScaledContents(True)

    def paintEvent(self, event):
        if self.pixmap() is not None:
            self.setPixmap(self.pixmap())
        super(VideoDisplay, self).paintEvent(event)

    def update(self):
        self.repaint()


class VideoWidgetSignals(QObject):
    frame = Signal(int)


# a window with a VideoDisplay label for displaying the video
class VideoWidget(QWidget):
    def __init__(self, parent: "VideoPlayerDockWidget"):
        super(VideoWidget, self).__init__(parent)
        self.parent = parent
        self.video_display = VideoDisplay(self)
        self.signals = VideoWidgetSignals()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.video_display)
        self.setLayout(self.layout)
        self.video_file = None
        self.frame_num = 0
        self.running = False
        self.play_thread = None
        self.play_worker = None
        self.lastFrame = None
        self.framesSincePrev = 0
        # create a url for the background image
        self.default_image = QPixmap(
            r"C:\dev\projects\qt-vid-scoring\qt-vid-score\video_scoring\Images\icon_gray.png"
        )
        self.default_image = self.default_image.scaledToHeight(
            200, QtCore.Qt.TransformationMode.SmoothTransformation
        )
        self.default_image_widget = None

    def showDefaultImage(self):
        # instead of the video display, show a default image if the video is not playing
        # make a widget to hold the image that will be centered in the window
        self.default_image_widget = QWidget()
        self.default_image_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.default_image_widget.setLayout(QVBoxLayout())
        self.default_image_widget.layout().addWidget(
            QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        )
        self.default_image_widget.layout().itemAt(0).widget().setPixmap(
            self.default_image
        )
        self.layout.addWidget(self.default_image_widget)

    def showVideoDisplay(self):
        if self.default_image_widget in self.layout:
            self.layout.removeWidget(self.default_image_widget)
            self.default_image_widget.deleteLater()

        if self.video_display not in self.layout:
            self.layout.addWidget(self.video_display)

    def updatePrevWindow(self, frame: np.ndarray) -> None:
        """Update the display with the new pixmap"""

        image = QImage(
            frame, frame.shape[1], frame.shape[0], QImage.Format.Format_RGB888
        ).rgbSwapped()
        self.video_display.setPixmap(QPixmap.fromImage(image))
        # fit the window to the image
        self.video_display.update()

    def updatePrevFrame(self, frame: np.ndarray) -> None:
        """Update the live preview window"""
        # update the preview
        if type(frame) == np.ndarray:
            self.framesSincePrev = 1
            # convert frame to pixmap in separate thread and update window when done
            self.updatePrevWindow(frame)
        else:
            self.updateStatus(f"Frame is empty", True)

    @Slot(np.ndarray, int)
    def receivePrevFrame(self, frame: np.ndarray, frame_num):
        """receive a frame from the vidReader thread. pad indicates whether the frame is a filler frame"""
        if frame.shape[0] == 0:
            self.play_worker.pause()
            return
        self.lastFrame = [frame]
        self.updatePrevFrame(frame)  # update the preview window
        self.signals.frame.emit(int(frame_num))  # update the timeline

    def startPlayer(self, video_file) -> None:
        """start updating preview"""
        if self.running:
            self.play_worker.pause()
            self.running = False
            self.play_thread.quit()
            self.play_thread.wait()
            self.play_thread.deleteLater()
            self.play_worker.deleteLater()

        self.video_file = video_file
        self.running = True
        self.play_thread = QThread()
        # Step 3: Create a worker object
        self.play_worker = VideoPlayer(self.video_file)
        # Step 4: Move worker to the thread
        self.play_worker.moveToThread(self.play_thread)
        # Step 5: Connect signals and slots
        self.play_worker.signals.frame.connect(self.receivePrevFrame)
        self.play_worker.signals.status.connect(self.updateStatus)
        self.play_worker.signals.error.connect(self.updateStatus)
        # Step 6: Start the thread
        self.play_thread.start()
        self.play_worker.seek(0)

    def updateStatus(self, err, show):
        self.parent.main_win.update_status(err)


class PlayerControls(QWidget):
    def __init__(self, vpdw: "VideoPlayerDockWidget", parent=None):
        super(PlayerControls, self).__init__(parent)
        self.vpdw = vpdw
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.frame_label = QLabel("0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # controls toolbar
        self.controls_toolbar = QtWidgets.QToolBar()
        self.controls_toolbar.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.controls_toolbar.setMovable(False)
        self.controls_toolbar.setFloatable(False)
        self.controls_toolbar.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.controls_toolbar.setAllowedAreas(QtCore.Qt.ToolBarArea.BottomToolBarArea)
        # center the items in the controls toolbar
        left_spacer = QtWidgets.QWidget()
        left_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.controls_toolbar.addWidget(left_spacer)
        # seek back large frames
        self.seek_back_large_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-backward-long-button.png"),
            f"Seek back large frames ({self.vpdw.main_win.project_settings.playback.seek_video_large})",
            self.controls_toolbar,
        )
        self.seek_back_large_frames_action.triggered.connect(
            self.vpdw.seek_back_medium_frames
        )
        self.controls_toolbar.addAction(self.seek_back_large_frames_action)

        # seek back medium frames
        self.seek_back_small_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-backward-button.png"),
            f"Seek back small frames ({self.vpdw.main_win.project_settings.playback.seek_timestamp_small})",
            self.controls_toolbar,
        )
        self.seek_back_small_frames_action.triggered.connect(
            self.vpdw.seek_back_small_frames
        )
        self.controls_toolbar.addAction(self.seek_back_small_frames_action)

        # play/pause button
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.vpdw.toggle_play)
        self.controls_toolbar.addWidget(self.play_button)

        # seek forward medium frames
        self.seek_forward_small_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-forward-button.png"),
            f"Seek forward small frames ({self.vpdw.main_win.project_settings.playback.seek_video_small})",
            self.controls_toolbar,
        )
        self.seek_forward_small_frames_action.triggered.connect(
            self.vpdw.seek_forward_small_frames
        )
        self.controls_toolbar.addAction(self.seek_forward_small_frames_action)

        # seek forward large frames
        self.seek_forward_medium_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-forward-long-button.png"),
            f"Seek forward medium frames ({self.vpdw.main_win.project_settings.playback.seek_timestamp_small})",
            self.controls_toolbar,
        )
        self.seek_forward_medium_frames_action.triggered.connect(
            self.vpdw.seek_forward_medium_frames
        )
        self.controls_toolbar.addAction(self.seek_forward_medium_frames_action)
        self.layout.addWidget(self.frame_label)
        self.layout.addWidget(self.controls_toolbar)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.frame_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        # center the controls toolbar
        right_spacer = QtWidgets.QWidget()
        right_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.controls_toolbar.addWidget(right_spacer)

    def set_label(self):
        if self.vpdw.video_widget.play_worker is None:
            return
        if self.vpdw.main_win.project_settings.scoring.save_frame_or_time == "frame":
            self.frame_label.setNum(self.vpdw.video_widget.play_worker.vc.frame_num)
        else:
            self.frame_label.setText(
                str(
                    self.vpdw.video_widget.play_worker.vc.video.frame_ts.get(
                        self.vpdw.video_widget.play_worker.vc.frame_num, 0
                    )
                )
            )


class VideoPlayerSettingsWidget(QWidget):
    def __init__(
        self, main_win: "MainWindow", video_widget: "VideoWidget", parent=None
    ):
        super(VideoPlayerSettingsWidget, self).__init__(parent)
        # a series of tab on the right side of this widget
        self.main_win = main_win
        self.video_widget = video_widget
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)
        self.tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.West)

    def init_tabs(self):
        # the playback tab, a form layout with a series of settings taken from the cv2.VideoCapture class
        self.playback_tab = QWidget()
        self.playback_tab.layout = QtWidgets.QFormLayout()
        self.playback_tab.setLayout(self.playback_tab.layout)

        # add row for video file
        row = QLabel(f"Video File: {self.video_widget.video_file}")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.playback_tab.layout.addRow(row)

        cv2_props = [
            "CAP_PROP_POS_MSEC",
            "Current Frame",
            "Relative Position",
            "Frame Width",
            "Frame Height",
            "Frame Rate",
            "4-character code of codec",
            "Number of frames in the video file",
        ]
        for prop in range(len(cv2_props)):
            val = self.video_widget.play_worker.vc.vc.get(prop)
            if val != 0:
                row = QLabel(f"{cv2_props[prop]}: {val}")
                row.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
                self.playback_tab.layout.addRow(row)
                self.playback_tab.layout.addRow(row)
        self.tabs.addTab(self.playback_tab, "Playback")


class VideoPlayerDockWidget(QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(VideoPlayerDockWidget, self).__init__(parent)
        self.setWindowTitle("Video Player")
        self.main_win = main_win
        self.tool_bar = QtWidgets.QToolBar()
        self.tool_bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.tool_bar.setMovable(False)
        self.tool_bar.setFloatable(False)
        self.tool_bar.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.tool_bar.setAllowedAreas(QtCore.Qt.ToolBarArea.TopToolBarArea)
        self.video_widget = VideoWidget(self)
        self.player_controls = PlayerControls(self)
        self.started = False
        # set the layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tool_bar)
        self.layout.addWidget(self.video_widget)
        self.layout.addWidget(self.player_controls)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.widget = QWidget()
        self.widget.setLayout(self.layout)
        self.setWidget(self.widget)
        self.main_win.loaded.connect(self._init_connections)

    def _init_connections(self):
        self.video_widget.signals.frame.connect(self.update_timeline)
        self.timeline = self.main_win.timeline_dw
        self.timeline.timeline_view.valueChanged.connect(self.timelineChanged)
        if self.started:
            self.timeline.set_length(self.video_widget.play_worker.vc.len)
            self.toggle_play()
        self.fps_label = QLabel(f"FPS: {self.video_widget.play_worker.vc.fps}")
        self.tool_bar.addWidget(self.fps_label)
        center_spacer = QtWidgets.QWidget()
        center_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.tool_bar.addWidget(center_spacer)
        self.info_button = QPushButton(
            self.main_win._get_icon("cogs.svg", svg=True), "Info"
        )
        self.info_button.clicked.connect(self.open_info)
        self.tool_bar.addWidget(self.info_button)

    def open_info(self):
        self.info_widget = VideoPlayerSettingsWidget(self.main_win, self.video_widget)
        self.info_widget.init_tabs()
        self.info_widget.show()

    def start(self, video_file):
        try:
            self.video_widget.startPlayer(video_file)
            self.started = True
            self.timeline.set_length(self.video_widget.play_worker.vc.len)
            self.toggle_play()
        except Exception as e:
            self.main_win.update_status(f"Error: {e}", True)

    def toggle_play(self):
        if self.video_widget.play_worker is None:
            return
        if self.video_widget.play_worker.paused:
            self.video_widget.play_worker.play()
            self.timeline.timeline_view.playing = True
            self.player_controls.play_button.setText("Pause")
        else:
            self.video_widget.play_worker.pause()
            self.timeline.timeline_view.playing = False
            self.player_controls.play_button.setText("Play")

    def seek(self, frame_num: int):
        if self.video_widget.play_worker is None:
            return
        self.video_widget.play_worker.seek(frame_num)

    def seek_forward_small_frames(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            + self.main_win.project_settings.playback.seek_video_small
        )

    def seek_back_small_frames(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            - self.main_win.project_settings.playback.seek_video_small
        )

    def seek_forward_medium_frames(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            + self.main_win.project_settings.playback.seek_video_medium
        )

    def seek_back_medium_frames(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            - self.main_win.project_settings.playback.seek_video_medium
        )

    def seek_forward_large_frames(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            + self.main_win.project_settings.playback.seek_video_large
        )

    def seek_back_large_frames(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            - self.main_win.project_settings.playback.seek_video_large
        )

    def seek_to_first_frame(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(0)

    def seek_to_last_frame(self):
        if self.video_widget.play_worker is None:
            return
        self.seek(self.video_widget.play_worker.vc.len - 1)

    def increase_playback_speed(self):
        if self.video_widget.play_worker is None:
            return
        self.toggle_play()
        self.video_widget.play_worker.updateFPS(
            self.video_widget.play_worker.vc.fps
            + self.main_win.project_settings.playback.playback_speed_modulator
        )
        self.fps_label.setText(f"FPS: {self.video_widget.play_worker.vc.fps}")
        self.toggle_play()

    def decrease_playback_speed(self):
        if self.video_widget.play_worker is None:
            return
        self.toggle_play()
        self.video_widget.play_worker.updateFPS(
            self.video_widget.play_worker.vc.fps
            - self.main_win.project_settings.playback.playback_speed_modulator
        )
        self.fps_label.setText(f"FPS: {self.video_widget.play_worker.vc.fps}")
        self.toggle_play()

    def timelineChanged(self, value):
        # if the video is not playing, seek to the new position
        if self.video_widget.play_worker is None:
            return
        if self.video_widget.play_worker.vc.frame_num != value:
            self.seek(value)

    def save_timestamp(self):
        if self.video_widget.play_worker is None:
            return
        # get the current frame number
        frame_num = self.video_widget.play_worker.vc.frame_num
        self.main_win.timeline_dw.timeline_view.add_oo_behavior(frame_num)
        self.main_win.timestamps_dw.table_widget.update()

    def update_timeline(self, frame_num):
        if self.main_win.project_settings.scoring.save_frame_or_time == "frame":
            self.player_controls.frame_label.setNum(frame_num)
        else:
            self.player_controls.frame_label.setText(
                str(self.video_widget.play_worker.vc.video.frame_ts.get(frame_num, 0))
            )
        if not self.timeline.timeline_view.playhead.triangle.pressed:
            self.timeline.timeline_view.setValue(frame_num)

    def get_frame_num(self):
        return self.video_widget.play_worker.vc.frame_num
