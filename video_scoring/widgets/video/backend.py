# this the a backend for the video widget, it will provide the functionality for getting video frames.
# we will use the opencv library to get the frames from the video
from typing import Union, TYPE_CHECKING
from PyQt6 import QtGui
import cv2
from PyQt6.QtCore import QMutex, QObject, Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenuBar,
                             QSizePolicy, QSlider, QPushButton, QVBoxLayout,
                             QWidget)
from PyQt6.QtGui import QAction, QIcon, QImage, QPixmap
import numpy as np

if TYPE_CHECKING:
    import numpy as np

class VideoCapture(QMutex):
    """holds the videoCapture object and surrounding functions"""

    def __init__(
        self, file
    ):
        super(VideoCapture, self).__init__()
        self.file = file
        self.frame_num = 0
        self.len = 1
        self.imw = 0
        self.imh = 0
        self.connectVC()
        
    def updateStatus(self, msg: str, _log: bool = False):
        """update the status bar by sending a signal"""
        print(msg)

    def updateFPS(self, fps):
        self.fps = fps
        self.mspf = int(round(1000 / self.fps))

    def connectVC(self):
        try:
            self.vc = cv2.VideoCapture(self.file)
            self.vc.set(
                cv2.CAP_PROP_BUFFERSIZE, 5000
            )  # limit buffer size to one frame
            self.updateFPS(self.getFrameRate())

        except Exception as e:
            self.updateStatus(f"Failed connect open file: {e}")
            self.connected = False
            return
        else:
            self.connected = True
        self.imw = int(self.vc.get(3))  # image width (px)
        self.imh = int(self.vc.get(4))  # image height (px)
        self.len = int(self.vc.get(cv2.CAP_PROP_FRAME_COUNT))  # number of frames
        

    def getFrameRate(self) -> float:
        """Determine the native device frame rate"""
        if self.vc is None:
            self.updateStatus(
                f"Cannot get frame rate from {self.file}: device not connected",
                True,
            )
            return 0
        fps = self.vc.get(cv2.CAP_PROP_FPS)  # frames per second
        if fps > 0:
            return int(fps)
        else:
            self.updateStatus(
                f"Invalid auto frame rate returned from {self.file}: {fps}", True
            )
            return 0

    @pyqtSlot()
    def get_frame(self, frame_num: int = None):
        """Get a frame from the webcam using cv2.VideoCapture.read()"""

        if frame_num is not None:
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
                self.updateStatus(
                    f"Cannot close VC", True
                )
        except:
            self.updateStatus(f"Error closing", True)


class VideoPlayerSignals(QObject):
    status = pyqtSignal(str, bool)
    finished = pyqtSignal()
    error = pyqtSignal(str, bool)
    frame = pyqtSignal(np.ndarray, int)

class VideoPlayer(QObject):
    def __init__(
        self, video_file = None
    ):
        super(VideoPlayer, self).__init__()
        self.signals = VideoPlayerSignals()
        self.play_timer = None
        self.paused = False
        self.started = False
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
        self.vc.lock()
        self.signals.frame.emit(self.vc.get_frame(), self.vc.frame_num)
        self.vc.unlock()

    def seek(self, frame_num: int):
        """Seek to a frame number"""
        if not self.started:
            return
        self.vc.lock()
        self.signals.frame.emit(self.vc.get_frame(frame_num), self.vc.frame_num)
        self.vc.unlock()

    def updateFPS(self, fps):
        # stop timer, destroy timer, update vc fps, play
        if not self.started:
            return
        if fps < 1:
            fps = 1
        print(fps)
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
    frame = pyqtSignal(int)
  
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
        self.prevRunning = False
        self.playThread = None
        self.playWorker = None
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

    @pyqtSlot(np.ndarray, int)
    def receivePrevFrame(self, frame: np.ndarray, frame_num):
        """receive a frame from the vidReader thread. pad indicates whether the frame is a filler frame"""
        self.lastFrame = [frame]
        self.updatePrevFrame(frame)  # update the preview window
        self.signals.frame.emit(int(frame_num))  # update the timeline

    def startPlayer(self) -> None:
        """start updating preview"""
        if not self.prevRunning:
            self.prevRunning = True
            self.playThread = QThread()
            # Step 3: Create a worker object
            self.playWorker = VideoPlayer(self.video_file)
            # Step 4: Move worker to the thread
            self.playWorker.moveToThread(self.playThread)
            # Step 5: Connect signals and slots
            self.playWorker.signals.frame.connect(self.receivePrevFrame)
            self.playWorker.signals.status.connect(self.updateStatus)
            self.playWorker.signals.error.connect(self.updateStatus)
            # Step 6: Start the thread
            self.playThread.start()


    def updateStatus(self, err, show):
        print(err, show)


class MainWin(QMainWindow):

    def __init__(self, video_file, parent=None):
        super(MainWin, self).__init__(parent)
        self.video_widget = VideoWidget(video_file)
        self.video_widget.startPlayer()
        # button to play/pause the video
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_pause)
        # layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.video_widget)
        self.layout.addWidget(self.play_button)
        # timeline
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, self.video_widget.playWorker.vc.len)
        self.timeline.setValue(0)
        self.timeline.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.timeline.setTickInterval(1)
        # update slider position when VideoWidget frame changes
        self.video_widget.signals.frame.connect(self.updateSlider)
        # update VideoWidget frame when slider position changes via user input
        self.timeline.valueChanged.connect(self.sliderChanged)
        
        self.layout.addWidget(self.timeline)
        # central widget        
        self.central_widget = QWidget()
        self.central_widget.setLayout(self.layout)
        self.setCentralWidget(self.central_widget)
        
        self.prevRunning = False
        self.playThread = None
        self.playWorker = None
        self.lastFrame = None
        self.framesSincePrev = 0

        # temp slider vals
        self.last_slider_val = 0

        # ovverride focus policy so that key presses are registered
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        

    def play_pause(self):
        if self.video_widget.playWorker.paused:
            self.video_widget.playWorker.play()
            self.play_button.setText("Pause")
        else:
            self.video_widget.playWorker.pause()
            self.play_button.setText("Play")

    def seek(self, frame_num: int):
        """Seek to a frame number"""
        self.video_widget.playWorker.seek(frame_num)

    def sliderChanged(self, value):
        if self.timeline.isSliderDown():
            self.seek(value)
            
    def updateSlider(self, frame_num):
        """update the slider position"""
        # if the user is not moving the slider, update the slider position
        if not self.timeline.isSliderDown():
            self.timeline.setValue(frame_num)

    # when right arrow is pressed, seek to the next frame
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Right:
            self.seek(self.video_widget.playWorker.vc.frame_num)
        elif event.key() == Qt.Key.Key_Left:
            self.seek(self.video_widget.playWorker.vc.frame_num - 2)
        elif event.key() == Qt.Key.Key_Space:
            self.play_pause()
        # shift + d = increase fps
        elif event.key() == Qt.Key.Key_D:
            self.video_widget.playWorker.updateFPS(self.video_widget.playWorker.vc.fps + 1)
        # shift + a = decrease fps
        elif event.key() == Qt.Key.Key_A:
            self.video_widget.playWorker.updateFPS(self.video_widget.playWorker.vc.fps - 1)
        else:
            super(MainWin, self).keyPressEvent(event)

