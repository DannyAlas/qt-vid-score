from typing import Union, TYPE_CHECKING
from qtpy import QtGui, QtCore
from PyQt6.QtCore import QObject, Qt, pyqtSignal, pyqtSlot, QThread
from PyQt6.QtWidgets import (
    QStyleOptionSlider,
    QLabel,
    QSizePolicy,
    QSlider,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QDockWidget,
)
from PyQt6.QtGui import QImage, QPixmap
import numpy as np
from video_scoring.widgets.video.backend import VideoPlayer
if TYPE_CHECKING:
    from video_scoring import MainWindow


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
        self.running = False
        self.play_thread = None
        self.play_worker = None
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
        print(err, show)


class CustomSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._secondary_slider_pos = []
        # self.indicator_positions = []

    @property
    def secondary_slider_pos(self):
        return self._secondary_slider_pos

    @property
    def indicator(self):
        try:
            return self._indicator
        except:
            image = QtGui.QPixmap(
                r"C:\dev\projects\qt-vid-scoring\qt-vid-score\video_scoring\Images\dark\tick.png"
            )
            if self.orientation() == QtCore.Qt.Orientation.Horizontal:
                height = self.height() / 2
                if image.height() > height:
                    image = image.scaledToHeight(
                        int(height), QtCore.Qt.TransformationMode.SmoothTransformation
                    )
            else:
                width = self.width() / 2
                if image.height() > width:
                    image = image.scaledToHeight(
                        int(width), QtCore.Qt.TransformationMode.SmoothTransformation
                    )
                rotated = QtGui.QPixmap(image.height(), image.width())
                rotated.fill(QtCore.Qt.GlobalColor.transparent)
                qp = QtGui.QPainter(rotated)
                qp.rotate(-90)
                qp.drawPixmap(-image.width(), 0, image)
                qp.end()
                image = rotated
            self._indicator = image
            return self._indicator

    def add_secondary_slider_pos(self, other_pos):
        self._secondary_slider_pos.append(other_pos)
        self.update()

    def set_secondary_slider_pos(self, other_pos):
        self._secondary_slider_pos = other_pos
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._secondary_slider_pos:
            return
        style = self.style()
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)

        # the available space for the handle
        available = style.pixelMetric(style.PM_SliderSpaceAvailable, opt, self)
        # the extent of the slider handle
        sLen = style.pixelMetric(style.PM_SliderLength, opt, self) / 2

        x = self.width() / 2
        y = self.height() / 2
        horizontal = self.orientation() == QtCore.Qt.Orientation.Horizontal
        if horizontal:
            delta = self.indicator.width() / 2
        else:
            delta = self.indicator.height() / 2

        minimum = self.minimum()
        maximum = self.maximum()
        qp = QtGui.QPainter(self)
        # just in case
        qp.translate(opt.rect.x(), opt.rect.y())
        for value in self._secondary_slider_pos:
            # get the actual position based on the available space and add half
            # the slider handle size for the correct position
            pos = (
                style.sliderPositionFromValue(
                    minimum, maximum, value, available, opt.upsideDown
                )
                + sLen
            )
            # draw the image by removing half of its size in order to center it
            if horizontal:
                qp.drawPixmap(int(pos - delta), int(y), self.indicator)
                # self.indicator_positions.append([int(pos - delta), int(y)])
            else:
                qp.drawPixmap(int(x), int(pos - delta), self.indicator)
                # self.indicator_positions.append([int(x), int(pos - delta)])
            
        # self.indicator_positions = np.unique(self.indicator_positions, axis=0).tolist()
        # # color as pastel red
        # qp.setBrush(QtGui.QColor(255, 0, 0, 100))
        # qp.setPen(QtCore.Qt.GlobalColor.transparent)
        # if len(self.indicator_positions) % 2 != 0:
        #     indicator_positions = self.indicator_positions[:-1]
        # else:
        #     indicator_positions = self.indicator_positions
        # self.grouped_indicator_positions = [
        #     indicator_positions[i : i + 2]
        #     for i in range(0, len(indicator_positions), 2)
        # ]

        # for pos1, pos2 in self.grouped_indicator_positions:
        #     if horizontal:
        #         qp.drawRect(pos1[0] +1, pos1[1], pos2[0] - pos1[0] - 2, 5)
        #     else:
        #         qp.drawRect(pos1[0]+1, pos1[1], pos2[0] - pos1[0] - 2, 5)
            
        qp.end()


    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        if (
            self.orientation() == QtCore.Qt.Orientation.Horizontal
            and event.size().height() != event.oldSize().height()
            or self.orientation() == QtCore.Qt.Orientation.Vertical
            and event.size().width() != event.oldSize().width()
        ):
            try:
                del self._indicator
            except AttributeError:
                pass
        

# a timeline widget with a timeline slider a labl for displaying the current frame number, and a button for playing/pausing the video
class TimelineWidget(QWidget):
    def __init__(self, vpdw: "VideoPlayerDockWidget", parent=None):
        super(TimelineWidget, self).__init__(parent)
        self.vpdw = vpdw
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.slider = CustomSlider(Qt.Orientation.Horizontal)
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
        self.frame_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.slider.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.play_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.slider.valueChanged.connect(self.frame_label.setNum)
        self.slider.valueChanged.connect(self.update_value)

    def update_value(self, value):
        self.slider.setValue(value)


class VideoPlayerDockWidget(QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(VideoPlayerDockWidget, self).__init__(parent)
        self.setWindowTitle("Video Player")
        self.video_widget = VideoWidget()
        self.timeline_widget = TimelineWidget(self)
        self.main_win = main_win

        # set the layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.video_widget)
        self.layout.addWidget(self.timeline_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.widget = QWidget()
        self.widget.setLayout(self.layout)
        self.setWidget(self.widget)

        self._init_connections()

    def _init_connections(self):
        self.video_widget.signals.frame.connect(self.update_timeline)
        self.timeline_widget.slider.valueChanged.connect(self.timelineChanged)

    def start(self, video_file):
        try:
            self.video_widget.startPlayer(video_file)
            self.timeline_widget.slider.setRange(
                0, self.video_widget.play_worker.vc.len
            )
            self.toggle_play()
        except Exception as e:
            self.main_win.update_status(f"Error: {e}", True)

    def toggle_play(self):
        if self.video_widget.play_worker is None:
            return

        if self.video_widget.play_worker.paused:
            self.video_widget.play_worker.play()
            self.timeline_widget.play_button.setText("Pause")
        else:
            self.video_widget.play_worker.pause()
            self.timeline_widget.play_button.setText("Play")

    def seek(self, frame_num: int):
        if self.video_widget.play_worker is None:
            return
        self.video_widget.play_worker.seek(frame_num)

    def seek_forward_small_frames(self):
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            + self.main_win.project_settings.playback.seek_video_small
        )

    def seek_back_small_frames(self):
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            - self.main_win.project_settings.playback.seek_video_small
        )

    def seek_forward_medium_frames(self):
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            + self.main_win.project_settings.playback.seek_video_medium
        )

    def seek_back_medium_frames(self):
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            - self.main_win.project_settings.playback.seek_video_medium
        )

    def seek_forward_large_frames(self):
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            + self.main_win.project_settings.playback.seek_video_large
        )

    def seek_back_large_frames(self):
        self.seek(
            self.video_widget.play_worker.vc.frame_num
            - self.main_win.project_settings.playback.seek_video_large
        )

    def seek_to_first_frame(self):
        self.seek(0)

    def seek_to_last_frame(self):
        self.seek(self.video_widget.play_worker.vc.len - 1)

    def increase_playback_speed(self):
        self.video_widget.play_worker.updateFPS(
            self.video_widget.play_worker.vc.fps
            + self.main_win.project_settings.playback.playback_speed_modulator
        )

    def decrease_playback_speed(self):
        self.video_widget.play_worker.updateFPS(
            self.video_widget.play_worker.vc.fps
            - self.main_win.project_settings.playback.playback_speed_modulator
        )

    def timelineChanged(self, value):

        if self.timeline_widget.slider.isSliderDown():
            self.seek(value)

    def save_timestamp(self):
        # get the current frame number
        frame_num = self.video_widget.play_worker.vc.frame_num
        self.main_win.timestamps_dock_widget.add_vid_time_stamp(frame_num)
        _ts = self.main_win.timestamps_dock_widget.table_widget.timestamps
        # _ts is a dict of onset:{offset:float, sure:bool} 
        # convert to a list containing all the onsets and offsets
        ts = []
        for onset, offset_dict in _ts.items():
            ts.append(onset)
            # if offset is not None:
            if offset_dict["offset"] is not None:
                ts.append(offset_dict["offset"])
            
        
        self.timeline_widget.slider.set_secondary_slider_pos(ts)

    def update_timeline(self, frame_num):
        if not self.timeline_widget.slider.isSliderDown():
            self.timeline_widget.slider.setValue(frame_num)
            self.timeline_widget.slider.update()

    def get_frame_num(self):
        return self.video_widget.play_worker.vc.frame_num
