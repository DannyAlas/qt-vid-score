from typing import Union, TYPE_CHECKING
from PyQt6 import QtGui
import cv2
from PyQt6.QtCore import QMutex, QObject, Qt, QTimer, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenuBar,
                             QSizePolicy, QSlider, QPushButton, QVBoxLayout,
                             QWidget, QDockWidget)
from PyQt6.QtGui import QAction, QIcon, QImage, QPixmap
import numpy as np
from video_scoring.widgets.video.backend import VideoPlayer

if TYPE_CHECKING:
    import numpy as np


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

    def __init__(self, parent=None):
        super(VideoWidget, self).__init__(parent)
        self.video_display = VideoDisplay()
        self.signals = VideoWidgetSignals()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.video_display)
        self.setLayout(self.layout)
        self.video_file = None
        self.frame_num = 0
        self.prevRunning = False
        self.playThread = None
        self.playWorker = None
        self.lastFrame = None
        self.framesSincePrev = 0

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
        if frame.shape[0] == 0:
            self.playWorker.pause()
            return
        self.lastFrame = [frame]
        self.updatePrevFrame(frame)  # update the preview window
        self.signals.frame.emit(int(frame_num))  # update the timeline

    def startPlayer(self, video_file) -> None:
        """start updating preview"""
        if self.prevRunning:
            self.playWorker.pause()
            self.prevRunning = False
            self.playThread.quit()
            self.playThread.wait()
            self.playThread.deleteLater()
            self.playWorker.deleteLater()
            
        self.video_file = video_file
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
        self.playWorker.seek(0)
    


    def updateStatus(self, err, show):
        print(err, show)


# a timeline widget with a timeline slider a labl for displaying the current frame number, and a button for playing/pausing the video
class TimelineWidget(QWidget):
    def __init__(self, vpdw:'VideoPlayerDockWidget', parent=None):
        super(TimelineWidget, self).__init__(parent)
        self.vpdw = vpdw
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)
        self.frame_label = QLabel("0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.play_button = QPushButton("Play")
        self.play_button.setCheckable(True)
        self.play_button.clicked.connect(self.vpdw.toggle_play)
        self.layout.addWidget(self.slider)
        self.layout.addWidget(self.frame_label)
        self.layout.addWidget(self.play_button)
        self.frame_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.play_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.slider.valueChanged.connect(self.frame_label.setNum)
        self.slider.valueChanged.connect(self.update_value)


    def update_value(self, value):
        self.slider.setValue(value)



class VideoPlayerDockWidget(QDockWidget):
    def __init__(self, parent=None):
        super(VideoPlayerDockWidget, self).__init__(parent)
        self.setWindowTitle("Video Player")
        self.video_widget = VideoWidget()
        self.timeline_widget = TimelineWidget(self)


        # set the layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.video_widget)
        self.layout.addWidget(self.timeline_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.widget = QWidget()
        self.widget.setLayout(self.layout)
        self.setWidget(self.widget)

        self.video_widget.signals.frame.connect(self.updateTimeline)
        self.timeline_widget.slider.valueChanged.connect(self.timelineChanged)

    def toggle_play(self):
        if self.video_widget.playWorker.paused:
            self.video_widget.playWorker.play()
            self.timeline_widget.play_button.setText("Pause")
        else:
            self.video_widget.playWorker.pause()
            self.timeline_widget.play_button.setText("Play")

    def seek(self, frame_num: int):
        self.video_widget.playWorker.seek(frame_num)

    def timelineChanged(self, value):
        if self.timeline_widget.slider.isSliderDown():
            self.seek(value)

    def updateTimeline(self, frame_num):
        if not self.timeline_widget.slider.isSliderDown():
            self.timeline_widget.slider.setValue(frame_num)
            self.timeline_widget.slider.update()

    def start(self, video_file):
        try:
                self.video_widget.startPlayer(video_file)
                self.timeline_widget.slider.setRange(0, self.video_widget.playWorker.vc.len)
                self.toggle_play()
        except Exception as e:
            print(e)