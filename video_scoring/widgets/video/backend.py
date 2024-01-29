# this the a backend for the video widget, it will provide the functionality for getting video frames.
# we will use the opencv library to get the frames from the video
import logging
from calendar import c
from typing import TYPE_CHECKING, Union

import cv2
import numpy as np
from qtpy import QtGui
from qtpy.QtCore import QMutex, QObject, Qt, QThread, QTimer, Signal, Slot
from qtpy.QtGui import QAction, QIcon, QImage, QPixmap
from qtpy.QtWidgets import (QApplication, QLabel, QMainWindow, QMenuBar,
                            QPushButton, QSizePolicy, QSlider, QVBoxLayout,
                            QWidget)

if TYPE_CHECKING:
    import numpy as np
log = logging.getLogger("video_scoring")


class VideoFile:
    def __init__(self, file_path: str):
        """
        A class to access the data of a video file

        Parameters
        ----------
        file_path : str
            The path to the video file

        Attributes
        ----------
        file_path : str
            The path to the video file
        cap : cv2.VideoCapture
            The video capture object
        fps : float
            The frames per second of the video
        frame_count : int
            The number of frames in the video
        duration : float
            The duration of the video in seconds
        """

        self.file_path = file_path
        self.cap = cv2.VideoCapture(self.file_path, cv2.CAP_FFMPEG)
        # check if the video capture object was created
        if not self.cap.isOpened():
            raise Exception(f"Failed to open video file at path: {self.file_path}")
        # self.cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.frame_count / self.fps
        self.frame_ts = {}
        self.init_frame_ts()

    def init_frame_ts(self):
        """
        Initialize the frame timestamps
        """
        for i in range(self.frame_count):
            self.frame_ts[i] = i * (1000 / self.fps)

    def __del__(self):
        self.cap.release()

    def get_frame(self, frame_num: int) -> np.ndarray:
        """
        Get a frame from the video

        Parameters
        ----------
        frame_num : int
            The frame number to get

        Returns
        -------
        np.ndarray
            The frame
        """
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        if ret:
            return frame
        else:
            return None


class VideoCapture(QMutex):
    """holds the videoCapture object and surrounding functions"""

    def __init__(self, file):
        super(VideoCapture, self).__init__()
        self.video = VideoFile(file)
        self.frame_num = 0
        self.len = 1
        self.imw = 0
        self.imh = 0
        self.connectVC()

    def updateStatus(self, msg: str, _log: bool = False):
        """update the status bar by sending a signal"""
        # TODO: fix this with proper logging and the updateStatus below
        log.info(msg)

    def updateFPS(self, fps):
        self.fps = fps
        self.mspf = int(round(1000 / self.fps))

    def connectVC(self):
        try:
            self.vc = self.video.cap
            self.vc.set(cv2.CAP_PROP_BUFFERSIZE, 5000)
            self.im_format = "".join(
                [
                    chr((int(self.vc.get(cv2.CAP_PROP_FOURCC)) >> 8 * i) & 0xFF)
                    for i in range(4)
                ]
            )
            self.updateFPS(self.getFrameRate())

        except Exception as e:
            self.updateStatus(f"Failed connect open file: {e}")
            self.connected = False
            return
        else:
            self.connected = True
        self.imw = int(self.vc.get(3))  # image width (px)
        self.imh = int(self.vc.get(4))  # image height (px)
        self.len = int(self.vc.get(cv2.CAP_PROP_FRAME_COUNT))

    def getFrameRate(self) -> float:
        """Determine the native device frame rate"""
        if self.vc is None:
            self.updateStatus(
                f"Cannot get frame rate from {self.video.file_path}: device not connected",
                True,
            )
            return 0
        fps = self.vc.get(cv2.CAP_PROP_FPS)  # frames per second
        if fps > 0:
            return int(fps)
        else:
            self.updateStatus(
                f"Invalid auto frame rate returned from {self.video.file_path}: {fps}\n\tAssuming 30fps",
                True,
            )
            return 30

    @Slot()
    def get_frame(self, frame_num: int = None):
        """Get a frame from the webcam using cv2.VideoCapture.read()"""

        if frame_num is not None:
            if frame_num < 0:
                frame_num = 0
            elif frame_num > self.len:
                frame_num = self.len - 1
            self.vc.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            (status, frame) = self.vc.read()
            self.frame_num = int(self.vc.get(cv2.CAP_PROP_POS_FRAMES))
        else:
            (status, frame) = self.vc.read()
            self.frame_num = int(self.vc.get(cv2.CAP_PROP_POS_FRAMES))

        if not status:
            return np.array([])
        else:
            return frame

    def closeVC(self):
        """Close the webcam device"""
        try:
            if self.vc is not None:
                self.vc.release()
            else:
                self.updateStatus(f"Cannot close VC", True)
        except:
            self.updateStatus(f"Error closing", True)


class VideoPlayerSignals(QObject):
    status = Signal(str, bool)
    finished = Signal()
    error = Signal(str, bool)
    frame = Signal(np.ndarray, int)


class VideoPlayer(QObject):
    def __init__(self, video_file=None):
        super(VideoPlayer, self).__init__()
        self.signals = VideoPlayerSignals()
        self.play_timer = None
        self.paused = True
        self.started = False
        self.loop = False
        self.loop_start = 0
        self.loop_end = 0
        if video_file is not None:
            self.startPlayer(video_file)

    def startPlayer(self, video_file) -> None:
        self.vc = VideoCapture(video_file)
        self.started = True

    def play(self):
        if not self.started:
            return
        if self.play_timer is None:
            self.play_timer = QTimer()
            self.play_timer.setInterval(self.vc.mspf)
            self.play_timer.moveToThread(QApplication.instance().thread())
            self.play_timer.timeout.connect(self.get_play_frame)
        if not self.play_timer.isActive():
            self.play_timer.start()
        self.paused = False

    def pause(self):
        if not self.started:
            return
        if self.play_timer is not None:
            self.play_timer.stop()
        else:
            self.play()
            self.play_timer.stop()
        self.paused = True

    def get_play_frame(self):
        if not self.started:
            return
        # if we're looping and we're at the end of the loop, seek to the beginning
        if self.loop and self.vc.frame_num >= self.loop_end:
            self.seek(self.loop_start)
        else:
            self.vc.lock()
            self.signals.frame.emit(self.vc.get_frame(), self.vc.frame_num)
            self.vc.unlock()

    def seek(self, frame_num: int):
        """Seek to a frame number"""
        if not self.started:
            return
        self.vc.lock()
        self.signals.frame.emit(self.vc.get_frame(frame_num - 1), self.vc.frame_num)
        self.vc.unlock()

    def updateFPS(self, fps):
        # stop timer, destroy timer, update vc fps, play
        if not self.started:
            return
        if fps < 1:
            fps = 1
        if self.play_timer is not None:
            self.play_timer.stop()
            self.play_timer.deleteLater()
            self.play_timer = None
        self.vc.updateFPS(fps)


class VideoDisplay(QLabel):
    """A QLabel where we always repaint the most recent frame"""

    def __init__(self, parent=None):
        super(VideoDisplay, self).__init__(parent)
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
    def __init__(self, video_file, parent=None):
        super(VideoWidget, self).__init__(parent)
        self.video_display = VideoDisplay()
        self.video_file = video_file
        self.signals = VideoWidgetSignals()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.video_display)
        self.setLayout(self.layout)
        self.frame_num = 0
        self.running = False
        self.play_thread = None
        self.play_worker = None
        self.lastFrame = None
        self.framesSincePrev = 0

        self.startPlayer()

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
        self.lastFrame = [frame]
        self.updatePrevFrame(frame)  # update the preview window
        self.signals.frame.emit(int(frame_num))  # update the timeline

    def startPlayer(self) -> None:
        """start updating preview"""
        if not self.running:
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

    def updateStatus(self, err, show):
        log.warn(err)
