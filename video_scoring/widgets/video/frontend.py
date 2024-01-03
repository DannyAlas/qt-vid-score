import logging
from typing import TYPE_CHECKING

import numpy as np
from PyQt6 import QtGui
from PyQt6.QtGui import QMouseEvent, QPaintEvent, QResizeEvent
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QObject, Qt, QThread, Signal, Slot
from qtpy.QtGui import QImage, QPixmap
from qtpy.QtWidgets import (QDockWidget, QLabel, QPushButton, QSizePolicy,
                            QVBoxLayout, QWidget)

from video_scoring.widgets.video.backend import VideoPlayer

if TYPE_CHECKING:
    from video_scoring import MainWindow


class VideoDisplay(QLabel):
    """A QLabel where we always repaint the most recent frame"""

    def __init__(self, parent: "VideoWidget"):
        super(VideoDisplay, self).__init__(parent)
        self.parent = parent
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


class BouncingAnimation(QtWidgets.QWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super().__init__(parent)
        self.parent = parent
        self.main_win = main_win
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.img = QtGui.QImage(self.main_win._get_icon("icon.png", as_string=True))
        self.img = self.img.scaled(
            int(self.main_win.width() / 8),
            int(self.main_win.height() / 8),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        )
        self.text = QtGui.QTextDocument(self)
        self.text.setHtml("<font color='white'>D133 = Bestes Boi</font>")
        font = QtGui.QFont("Freestyle Script", 20, QtGui.QFont.Weight.Bold)
        font.setStyleStrategy(QtGui.QFont.StyleStrategy.PreferAntialias)
        self.text.setDefaultFont(font)
        self.show_text = False
        self.x = 0
        self.y = 0
        self.dx = 1
        self.dy = 1
        self.timer = self.startTimer(int(1000 / 50))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.drawImage(self.x, self.y, self.img)
        if self.show_text:
            # draw the text with the font
            painter.translate(self.x - 20, self.y + self.img.height() + 10)
            self.text.drawContents(painter)
            painter.translate(-self.x + 20, -self.y - self.img.height() - 10)

    def timerEvent(self, event):
        self.x += self.dx
        self.y += self.dy
        if self.x < 0 or self.x > self.width() - self.img.width():
            self.dx *= -1
        if self.y < 0 or self.y > self.height() - self.img.height():
            self.dy *= -1
        self.update()

    def resizeEvent(self, event):
        self.x = 0
        self.y = 0

    def mousePressEvent(self, event):
        # if we click on the image
        image_rect = QtCore.QRect(self.x, self.y, self.img.width(), self.img.height())
        if image_rect.contains(event.pos()):
            self.show_text = not self.show_text

        super(BouncingAnimation, self).mousePressEvent(event)


# a window with a VideoDisplay label for displaying the video
class VideoWidget(QWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(VideoWidget, self).__init__(parent)
        self.video_display = VideoDisplay(self)
        self.static_animation = BouncingAnimation(main_win, self)
        self.signals = VideoWidgetSignals()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.static_animation)
        self.layout.addWidget(self.video_display)
        self.video_display.hide()
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.setSpacing(0)

        self.preserve_aspect_ratio = True
        self.video_file = None
        self.frame_num = 0
        self.running = False
        self.play_thread = None
        self.play_worker = None
        self.lastFrame = None
        self.framesSincePrev = 0

    def updatePrevWindow(self, frame: np.ndarray) -> None:
        """Update the display with the new pixmap"""
        if self.play_worker.vc.im_format == "mjpg":
            image = QImage(
                frame,
                frame.shape[1],
                frame.shape[0],
                frame.strides[0],
                QImage.Format.Format_RGB888,
            )
        elif self.play_worker.vc.im_format == "mp4v":
            image = QImage(
                frame,
                frame.shape[1],
                frame.shape[0],
                frame.strides[0],
                QImage.Format.Format_BGR888,
            )
        elif self.play_worker.vc.im_format == "avc1":
            image = QImage(
                frame,
                frame.shape[1],
                frame.shape[0],
                frame.strides[0],
                QImage.Format.Format_RGB888,
            )
        elif self.play_worker.vc.im_format == "h264":
            image = QImage(
                frame,
                frame.shape[1],
                frame.shape[0],
                frame.strides[0],
                QImage.Format.Format_RGB888,
            ).rgbSwapped()
        else:
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
        """receives a frame from the play_worker thread."""
        if frame.shape[0] == 0:
            self.play_worker.pause()
            return
        self.lastFrame = [frame]
        self.updatePrevFrame(frame)  # update the preview window
        self.frame_num = frame_num
        self.signals.frame.emit(int(frame_num))  # update the timeline

    def startPlayer(self, video_file) -> None:
        """start updating preview"""
        self.static_animation.hide()
        self.video_display.show()

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

    def stopPlayer(self) -> None:
        """stop updating preview"""
        if self.video_display.isVisible():
            self.video_display.hide()
        if not self.static_animation.isVisible():
            self.static_animation.show()
            self.static_animation.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            # size the animation to the window size
            self.static_animation.resize(self.size())

        if self.running:
            self.play_worker.pause()
            self.running = False
            self.play_thread.quit()
            self.play_thread.wait()
            self.play_thread.deleteLater()
            self.play_worker.deleteLater()

    def updateStatus(self, err, show):
        self.parent.main_win.update_status(err)

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        if self.play_worker is None:
            super(VideoWidget, self).paintEvent(a0)
            return
        if self.preserve_aspect_ratio:
            h = self.play_worker.vc.imh
            w = self.play_worker.vc.imw
            if h == 0 or w == 0:
                super(VideoWidget, self).paintEvent(a0)
                return
            # get the aspect ratio of the video
            aspect_ratio = w / h
            # get the aspect ratio of the window
            window_aspect_ratio = self.width() / self.height()
            # if the window is wider than the video
            if window_aspect_ratio > aspect_ratio:
                # set the height to the height of the window
                self.video_display.resize(
                    int(self.height() * aspect_ratio), self.height()
                )
                self.video_display.resize(
                    int(self.height() * aspect_ratio), self.height()
                )
            else:
                # set the width to the width of the window
                self.video_display.resize(
                    self.width(), int(self.width() / aspect_ratio)
                )
                self.video_display.resize(
                    self.width(), int(self.width() / aspect_ratio)
                )

            # center the video display
            self.video_display.move(
                int((self.width() - self.video_display.width()) / 2),
                int((self.height() - self.video_display.height()) / 2),
            )
        else:
            self.video_display.resize(self.width(), self.height())
            self.video_display.move(0, 0)
        super(VideoWidget, self).paintEvent(a0)


class PlayerControls(QWidget):
    def __init__(self, vpdw: "VideoPlayerDockWidget", parent=None):
        super(PlayerControls, self).__init__(parent)
        self.vpdw = vpdw
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.frame_label = QLabel("0")
        self.frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._init_ui()

    def _init_ui(self):

        # controls toolbar
        self.controls_toolbar = QtWidgets.QToolBar()
        self.controls_toolbar.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.controls_toolbar.setMovable(False)
        self.controls_toolbar.setFloatable(False)
        # self.frame_label.setSizePolicy(
        #     QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        # )
        # seek back medium frames
        self.seek_back_medium_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-backward-long-button.png"),
            "Seek back medium frames",
            self,
        )
        self.controls_toolbar.addAction(self.seek_back_medium_frames_action)

        # seek back medium frames
        self.seek_back_small_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-backward-button.png"),
            "Seek back medium frames",
            self.controls_toolbar,
        )
        self.controls_toolbar.addAction(self.seek_back_small_frames_action)

        # play/pause button
        self.play_button = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("media_play.png"),
            "Play/Pause",
            self.controls_toolbar,
        )
        self.controls_toolbar.addAction(self.play_button)

        # seek forward medium frames
        self.seek_forward_small_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-forward-button.png"),
            f"Seek forward small frames",
            self.controls_toolbar,
        )
        self.controls_toolbar.addAction(self.seek_forward_small_frames_action)

        # seek forward large frames
        self.seek_forward_medium_frames_action = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("seek-forward-long-button.png"),
            "Seek forward large frames",
            self.controls_toolbar,
        )
        self.controls_toolbar.addAction(self.seek_forward_medium_frames_action)

        self.layout.addWidget(self.controls_toolbar)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.left_spacer = QtWidgets.QWidget()
        self.left_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.controls_toolbar.addWidget(self.left_spacer)
        self.controls_toolbar.addWidget(self.frame_label)
        self.right_spacer = QtWidgets.QWidget()
        self.right_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.controls_toolbar.addWidget(self.right_spacer)
        # aspect ratio button
        self.aspect_ratio_button = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("increase.png"),
            "Fill Window",
            self.controls_toolbar,
        )

        self.play_button.triggered.connect(self.vpdw.toggle_play)
        self.aspect_ratio_button.triggered.connect(self.toggle_aspect_ratio)
        self.seek_back_medium_frames_action.triggered.connect(
            self.vpdw.seek_back_medium_frames
        )
        # update tooltip for seek back medium frames
        self.seek_back_medium_frames_action.setToolTip(f"Seek back medium frames")
        self.seek_back_small_frames_action.triggered.connect(
            self.vpdw.seek_back_small_frames
        )
        self.seek_back_small_frames_action.setToolTip(f"Seek back small frames")
        self.seek_forward_small_frames_action.triggered.connect(
            self.vpdw.seek_forward_small_frames
        )
        self.seek_forward_small_frames_action.setToolTip(f"Seek forward small frames")
        self.seek_forward_medium_frames_action.triggered.connect(
            self.vpdw.seek_forward_medium_frames
        )
        self.seek_forward_medium_frames_action.setToolTip(f"Seek forward medium frames")
        self.set_marker_onset_button = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("open-bracket.png"),
            "Set Marker Onset",
            self.controls_toolbar,
        )
        self.set_marker_onset_button.triggered.connect(self.vpdw.set_loop_start)
        self.controls_toolbar.addAction(self.set_marker_onset_button)
        self.set_marker_offset_button = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("close-bracket.png"),
            "Set Marker Offset",
            self.controls_toolbar,
        )
        self.set_marker_offset_button.triggered.connect(self.vpdw.set_loop_end)

        self.controls_toolbar.addAction(self.set_marker_offset_button)

        # add loop button
        self.loop_button = QtWidgets.QAction(
            self.vpdw.main_win._get_icon("loop.png"), "Loop", self.controls_toolbar
        )
        self.loop_button.setCheckable(True)
        self.loop_button.setChecked(False)
        self.loop_button.triggered.connect(self.vpdw.loop)

        self.controls_toolbar.addAction(self.loop_button)
        self.controls_toolbar.addAction(self.aspect_ratio_button)

    def toggle_aspect_ratio(self):
        self.vpdw.video_widget.preserve_aspect_ratio = (
            not self.vpdw.video_widget.preserve_aspect_ratio
        )
        # update the button text
        if self.vpdw.video_widget.preserve_aspect_ratio:
            self.aspect_ratio_button.setIcon(
                self.vpdw.main_win._get_icon("increase.png")
            )
            self.aspect_ratio_button.setToolTip("Fill Window")
        else:
            self.aspect_ratio_button.setIcon(self.vpdw.main_win._get_icon("reduce.png"))
            self.aspect_ratio_button.setToolTip("Fit Window")

    def set_label(self):
        if self.vpdw.video_widget.play_worker is None:
            return
        self.frame_label.setNum(self.vpdw.video_widget.play_worker.vc.frame_num)


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
        if self.video_widget.play_worker is not None:
            for prop in range(len(cv2_props)):
                val = self.video_widget.play_worker.vc.vc.get(prop)
                if val != 0:
                    row = QLabel(f"{cv2_props[prop]}: {val}")
                    row.setSizePolicy(
                        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                    )
                    self.playback_tab.layout.addRow(row)
                    self.playback_tab.layout.addRow(row)
            # add a button to remove the video file
            remove_video_button = QPushButton("Remove Video")
            self.main_win.project_settings.scoring_data.video_file_location = ""
            remove_video_button.clicked.connect(self.video_widget.stopPlayer)
            remove_video_button.clicked.connect(self.close)
            self.playback_tab.layout.addRow(remove_video_button)
        self.tabs.addTab(self.playback_tab, "Playback")


class ViewerView(QtWidgets.QGraphicsView):
    """A QGraphicsView contining the VideoWidget and allows for zooming and panning"""

    def __init__(self, parent: "VideoPlayerDockWidget"):
        super(ViewerView, self).__init__(parent)
        self.parent = parent
        self.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.SmoothPixmapTransform
        )
        # allow dragging of the scene
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        # allow zooming with the mouse wheel
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter
        )
        self.setMouseTracking(True)
        self.setInteractive(True)

        self._init_ui()

    def _init_ui(self):
        self.video_widget = VideoWidget(self.parent.main_win)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.scene = QtWidgets.QGraphicsScene(self)
        self.scene.addWidget(self.video_widget)
        self.setScene(self.scene)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        return super().mouseReleaseEvent(event)

    # zoom in and out with the mouse wheel
    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            self.scale(1.1, 1.1)
        else:
            self.scale(0.9, 0.9)
        return super().wheelEvent(event)

    def paintEvent(self, event: QPaintEvent | None) -> None:
        # draw a border around the video widget
        painter = QtGui.QPainter(self.viewport())
        painter.setPen(QtGui.QPen(QtGui.QColor("black"), 2))
        painter.drawRect(self.video_widget.geometry())

        return super().paintEvent(event)


class VideoPlayerDockWidget(QDockWidget):
    def __init__(self, main_win: "MainWindow", parent=None):
        super(VideoPlayerDockWidget, self).__init__(parent)
        self.setWindowTitle("Video Player")
        self.main_win = main_win
        self._init_ui()
        self.main_win.project_loaded.connect(self._init_connections)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)

    def setWindowTitle(self, title: str) -> None:
        self.setToolTip(title)  # full title for tooltip
        if len(title) > 25:
            title = title[:25] + "..."
        super(VideoPlayerDockWidget, self).setWindowTitle(title)

    def _init_ui(self):
        self.tool_bar = QtWidgets.QToolBar()
        self.tool_bar.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.tool_bar.setMovable(False)
        self.tool_bar.setFloatable(False)
        self.tool_bar.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.tool_bar.setAllowedAreas(QtCore.Qt.ToolBarArea.TopToolBarArea)
        self.fps_label = QLabel(f"FPS: NaN")
        self.tool_bar.addWidget(self.fps_label)
        center_spacer = QtWidgets.QWidget()
        center_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.tool_bar.addWidget(center_spacer)
        self.info_button = QtWidgets.QAction(
            self.main_win._get_icon("cogs.svg", svg=True), "info", self
        )
        self.info_button.triggered.connect(self.open_info)
        self.tool_bar.addAction(self.info_button)

        # self.viewer_view = ViewerView(self)
        # make the video widget the central widget
        self.video_widget = VideoWidget(self.main_win)
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
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

    # on hide/show set us as the central widget of the main window
    def showEvent(self, event):
        self.main_win.setCentralWidget(self)
        super(VideoPlayerDockWidget, self).showEvent(event)

    def _init_connections(self):
        self.video_widget.signals.frame.connect(self.update_timeline)
        self.timeline = self.main_win.timeline_dw
        self.timeline.valueChanged.connect(self.timelineChanged)
        if self.started:
            self.timeline.set_length(self.video_widget.play_worker.vc.len)
            self.fps_label.setText(f"FPS: {self.video_widget.play_worker.vc.fps}")

        self.timeline.loaded.connect(
            lambda: self.timeline.timeline_view.marker.signals.updated.connect(
                self.update_loop
            )
        )
        self.player_controls.loop_button.toggled.connect(self.loop)
        self.update_loop()

    def open_info(self):
        self.info_widget = VideoPlayerSettingsWidget(self.main_win, self.video_widget)
        self.info_widget.init_tabs()
        self.info_widget.show()

    def start(self, video_file: str):
        if video_file is None:
            self.video_widget.stopPlayer()
        try:
            self.video_widget.startPlayer(video_file)
            self.started = True
            self.setWindowTitle(f"Video Player - {video_file.split('/')[-1]}")
        except Exception as e:
            self.main_win.update_status(f"Error: {e}", True)

    def toggle_play(self):
        if self.video_widget.play_worker is None:
            return
        if self.video_widget.play_worker.paused:
            self.video_widget.play_worker.play()
            self.timeline.timeline_view.playing = True
            self.player_controls.play_button.setIcon(
                self.main_win._get_icon("media_pause.png")
            )
        else:
            self.video_widget.play_worker.pause()
            self.timeline.timeline_view.playing = False
            self.player_controls.play_button.setIcon(
                self.main_win._get_icon("media_play.png")
            )

    def update_loop(self):
        if self.video_widget.play_worker is None:
            return
        # if the marker is not visible, set the disable the loop button in the toolbar
        if not self.timeline.timeline_view.marker.isVisible():
            self.player_controls.loop_button.setIcon(
                self.main_win._get_icon("loop-disabled.png")
            )
            self.player_controls.loop_button.setEnabled(False)
            self.player_controls.loop_button.setChecked(False)
            self.video_widget.play_worker.loop = False
            return
        # if the marker is visible, enable the loop button in the toolbar
        self.player_controls.loop_button.setEnabled(True)
        self.player_controls.loop_button.setIcon(self.main_win._get_icon("loop.png"))
        self.video_widget.play_worker.loop_start = (
            self.main_win.timeline_dw.timeline_view.marker.onset
        )
        self.video_widget.play_worker.loop_end = (
            self.main_win.timeline_dw.timeline_view.marker.offset
        )

    def set_loop_start(self):
        self.timeline.set_marker_in()
        self.video_widget.play_worker.loop_start = (
            self.main_win.timeline_dw.timeline_view.marker.onset
        )

    def set_loop_end(self):
        self.timeline.set_marker_out()
        self.video_widget.play_worker.loop_end = (
            self.main_win.timeline_dw.timeline_view.marker.offset
        )

    def loop(self):
        if self.video_widget.play_worker is None:
            return
        self.video_widget.play_worker.loop = (
            self.player_controls.loop_button.isChecked()
        )
        self.update_loop()

    def seek(self, frame_num: int):
        if self.video_widget.play_worker is None:
            return
        self.video_widget.play_worker.seek(frame_num)
        self.timeline.timeline_view.scroll_to_playhead()

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
        self.main_win.update_status("Seeking to first frame", logging.ERROR)
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

    @Slot(int)
    def timelineChanged(self, value):
        # if the video is not playing, seek to the new position
        if self.video_widget.play_worker is None:
            return
        if self.video_widget.play_worker.vc.frame_num != value:
            self.seek(value)

    def update_timeline(self, frame_num):
        self.player_controls.frame_label.setNum(frame_num)

        if not self.timeline.timeline_view.playhead.triangle.pressed:
            self.timeline.timeline_view.move_playhead_to_frame(frame_num)
            self.timeline.timeline_view.scroll_to_playhead()

    def get_frame_num(self):
        return self.video_widget.play_worker.vc.frame_num

    def load(self, video_file):
        if video_file is None:
            return
        try:
            self.video_widget.startPlayer(video_file)
            self.setWindowTitle(f"Video Player - {video_file.split('/')[-1]}")
            self.started = True
        except Exception as e:
            self.main_win.update_status(f"Error: {e}", True)

    def refresh(self):
        # refresh the video widget
        self.load()
