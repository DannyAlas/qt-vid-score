from email.charset import QP
from tkinter import E
from typing import TYPE_CHECKING, Literal

import numpy as np
from qtpy import QtCore
from qtpy.QtCore import QObject, Qt, QThread, QUrl, Signal, Slot
from qtpy.QtGui import QBrush, QImage, QPainter, QPixmap
from qtpy.QtWidgets import (
    QDockWidget,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyleOptionSlider,
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
        self.play_button = QPushButton("Play")
        self.play_button.setCheckable(True)
        self.play_button.clicked.connect(self.vpdw.toggle_play)
        self.layout.addWidget(self.frame_label)
        self.layout.addWidget(self.play_button)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.frame_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.play_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

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


class VideoPlayerDockWidget(QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(VideoPlayerDockWidget, self).__init__(parent)
        self.setWindowTitle("Video Player")
        self.main_win = main_win
        self.video_widget = VideoWidget(self)
        self.player_controls = PlayerControls(self)
        self.started = False
        # set the layout
        self.layout = QVBoxLayout()
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
        self.toggle_play()

    def decrease_playback_speed(self):
        if self.video_widget.play_worker is None:
            return
        self.toggle_play()
        self.video_widget.play_worker.updateFPS(
            self.video_widget.play_worker.vc.fps
            - self.main_win.project_settings.playback.playback_speed_modulator
        )
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
