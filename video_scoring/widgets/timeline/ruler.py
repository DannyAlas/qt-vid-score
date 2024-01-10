import datetime
import math
from email.charset import QP
from typing import TYPE_CHECKING, List, Optional, Tuple

from PyQt6.QtGui import QMouseEvent, QPaintEvent
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import QLineF, QMarginsF, QPointF, QRect, QRectF, Qt
from qtpy.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF

from video_scoring.widgets.timeline.marker import MarkerItem
from video_scoring.widgets.timeline.playhead import Playhead

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineView


class TimelineRulerView(QtWidgets.QGraphicsView):
    """
    The ruler view is a QGraphicsView that displays the ruler for the timeline.
    It is a separate view so that it can be resized independently of the timeline
    view.
    """

    def __init__(self, view: "TimelineView"):
        super().__init__(view)
        self._timeline_view = view
        self._scene = QtWidgets.QGraphicsScene(self)
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.NoDrag)
        # custom context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        # no selection
        self.setScene(self._scene)
        self.setFixedHeight(50)
        # no selection rectangle
        self._timeline_view.frame_width_changed.connect(self.frame_width_changed)
        self._timeline_view.scrolled.connect(self.scroll_changed)
        self.base_frame_width = 50
        self.frame_width = 50
        self.lmb_holding = False
        self.tick_size = 25
        self.tick_bottom = self.height()
        self.tick_top = self.tick_bottom - self.tick_size
        self.dragging_playhead = False
        self._init_playhead()
        self._init_hover_line()
        self._init_marker()
        self._timeline_view.scene_rect_changed.connect(self.update_scene_rect)

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if isinstance(item, MarkerItem):
            # select the item
            context_menu = item.get_context_menu()
            context_menu.exec(self.mapToGlobal(pos))

    def update_scene_rect(self, rect: QRectF):
        self.setSceneRect(rect)
        self.update()

    def _init_playhead(self):
        self.playhead = Playhead(10, 0, 60, self.frame_width, self)
        self.scene().addItem(self.playhead)
        self.playhead.triangle.setY(self.tick_bottom - 5)
        self.playhead.triangle.signals.valueChanged.connect(
            self._timeline_view.valueChanged.emit
        )

    def _init_hover_line(self):
        self.hover_line = QtWidgets.QGraphicsLineItem(0, 0, 0, 0)
        self.scene().addItem(self.hover_line)
        self.hover_line.hide()

    def _init_marker(self):
        self.marker = MarkerItem(0, 0, self._timeline_view, self)
        self.marker.setVisible(False)
        self.scene().addItem(self.marker)

    def get_visible_frames_with_x(self, dynamic_interval):
        """
        Calculate and return a generator of tuples with frame numbers and their corresponding x positions.
        """
        l, r = self._timeline_view.get_visable_frames()
        frame_index = max(0, l - l % dynamic_interval)
        major_tick_start = l - l % dynamic_interval
        minor_tick_start = l - l % self.inter_tick_skip_factor
        while frame_index <= r:
            x = int(frame_index * self.frame_width)
            yield (frame_index, x)
            # Increment to the next relevant frame index
            next_major_tick = major_tick_start + dynamic_interval
            next_minor_tick = minor_tick_start + self.inter_tick_skip_factor
            frame_index = min(next_major_tick, next_minor_tick)
            # Update start values for major and minor ticks
            if frame_index == next_major_tick:
                major_tick_start = frame_index
            if frame_index == next_minor_tick:
                minor_tick_start = frame_index

    def get_dynamic_interval(self, visible_frames):
        total_visible_frames = visible_frames[1] - visible_frames[0]
        # Use a periodic function to oscillate max_major_ticks
        # Adjust the frequency as needed to control how quickly it cycles
        oscillation = (
            math.sin(total_visible_frames / 10000) + 1
        ) / 2  # Normalizes between 0 and 1
        max_major_ticks = 7 + (oscillation * 7)  # Osciilates between 7 and 14

        # Calculate the desired interval in frames between major ticks
        desired_interval = max(total_visible_frames / max_major_ticks, 1)
        # Round to the nearest power of 4 ensuring that the interval is at least 1
        desired_interval = max(5, 5 ** round(math.log(desired_interval, 5)))
        return int(desired_interval)

    def drawBackground(self, painter: QPainter, rect):
        """
        Draws the background of a timeline, including ticks for frames or time.
        """
        pen = QPen(
            Qt.GlobalColor.gray, 1
        )  # Set the pen color and width for the drawing
        painter.setPen(pen)
        # Determine skip factors for major and minor ticks
        self.skip_factor = max(1, int(self.base_frame_width / self.frame_width))
        self.inter_tick_skip_factor = max(
            1, int(self.skip_factor / 10)
        )  # for minor ticks
        dynamic_interval = self.get_dynamic_interval(
            (
                self._timeline_view.visible_left_frame,
                self._timeline_view.visible_right_frame,
            )
        )
        frames_gen = self.get_visible_frames_with_x(dynamic_interval)
        for frame_index, x in frames_gen:
            # Draw a unique tick for the first frame
            if frame_index == 1:
                painter.drawLine(x, self.tick_top + 5, x, self.tick_bottom - 5)
            if self._timeline_view.show_time:
                self.draw_time_ticks(painter, frame_index, dynamic_interval, x)
            else:
                self.draw_frame_ticks(painter, frame_index, dynamic_interval, x)

        frames_gen.close()
        super().drawBackground(painter, rect)

    def get_time_from_frame(self, frame: int) -> float:
        seconds = (
            frame
            / self._timeline_view.main_window.video_player_dw.video_widget.play_worker.vc.video.fps
        )
        # convert seconds to a datetime object
        datetime_object = datetime.datetime(1, 1, 1) + datetime.timedelta(
            seconds=seconds
        )
        # if we're in the hours format to HH:MM:SS
        if seconds >= 3600:
            datetime_object = datetime_object.strftime("%H:%M:%S")
        # if we're in the minutes format to MM:SS
        elif seconds >= 60:
            datetime_object = datetime_object.strftime("%M:%S")
        # if we're in the seconds format to seconds:milliseconds but only show 3 decimal places
        else:
            datetime_object = datetime_object.strftime("%S.%f")[:-4]
        return datetime_object

    def draw_frame_ticks(self, painter: QPainter, frame_index, dynamic_interval, x):
        if frame_index % dynamic_interval == 0:
            # Draw major tick for frames
            painter.drawLine(x, self.tick_top, x, self.tick_bottom)
            painter.drawText(
                QRectF(x - 20, self.tick_top - 20, 40, 20),
                Qt.AlignmentFlag.AlignCenter,
                str(frame_index),
            )
        elif frame_index % self.inter_tick_skip_factor == 0:
            # Draw minor tick for frames
            painter.drawLine(x, self.tick_top + 5, x, self.tick_bottom - 5)

    def draw_time_ticks(self, painter: QPainter, frame_index, dynamic_interval, x):
        if frame_index % dynamic_interval == 0:
            # Draw major tick for whole subdivisions of time
            painter.drawLine(x, self.tick_top, x, self.tick_bottom)
            # determine length of text to draw
            text = self.get_time_from_frame(frame_index)
            # create text object
            text_obj = QtGui.QTextDocument()
            # set the text
            text_obj.setHtml(text)
            # get the width of the text
            text_width = text_obj.size().width()
            # draw the text
            painter.drawText(
                QRectF(x - 20, self.tick_top - 20, text_width, 20),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
        elif frame_index % self.inter_tick_skip_factor == 0:
            # Draw minor tick
            painter.drawLine(x, self.tick_top + 5, x, self.tick_bottom - 5)

    def frame_width_changed(self, width: float):
        self.frame_width = width
        self.update()

    def get_x_pos_of_frame(self, frame: int) -> int:
        return round(frame * self.frame_width)

    def get_frame_of_x_pos(self, x_pos: float) -> int:
        snapped_x = round(x_pos / self.frame_width) * self.frame_width
        return round(snapped_x / self.frame_width)

    def move_playhead_to_frame(self, frame: int):
        self.playhead.setPos(self.get_x_pos_of_frame(frame), 0)
        self.playhead.current_frame = frame
        self._timeline_view.move_playline_to_frame(frame)
        track = self._timeline_view.get_track_from_name(
            self._timeline_view.track_name_to_save_on
        )
        if track is not None:
            self._timeline_view.move_curr_behavior_item(track=track, offset=frame)
            if track.curr_behavior_item is not None:
                self.playhead.triangle.setBrush(
                    QBrush(self.playhead.triangle.active_behavior_color)
                )
            else:
                self.playhead.triangle.setBrush(
                    QBrush(self.playhead.triangle.base_color)
                )
        self.scene().update()

    def move_playhead_to_x(self, x: int):
        snapped_x = round(x / self.frame_width) * self.frame_width
        self.move_playhead_to_frame(round(snapped_x / self.frame_width))

    def set_marker_in(self, frame: int):
        if not self.marker.isVisible():
            self.marker.setVisible(True)
        self.marker.set_onset(frame)
        self.marker.signals.updated.emit()
        self.scene().update()

    def set_marker_out(self, frame: int):
        if not self.marker.isVisible():
            self.marker.setVisible(True)
        self.marker.set_offset(frame)
        self.marker.signals.updated.emit()
        self.scene().update()

    def set_hover_line(self, frame: int):
        self.hover_line.show()
        pen = QPen(Qt.GlobalColor.lightGray, 0.3)
        self.hover_line.setPen(pen)
        self.hover_line.setLine(
            self.get_x_pos_of_frame(frame),
            self.mapToScene(0, 0).y(),
            self.get_x_pos_of_frame(frame),
            self.mapToScene(0, 0).y() + 30,
        )

    def set_hover_line_from_x(self, x: int):
        self.hover_line.show()
        pen = QPen(Qt.GlobalColor.lightGray, 0.3)
        self.hover_line.setPen(pen)
        snapped_x = round(x / self.frame_width) * self.frame_width
        self.hover_line.setLine(
            snapped_x,
            self.mapToScene(0, 0).y(),
            snapped_x,
            self.mapToScene(0, 0).y() + 30,
        )

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        super().mousePressEvent(event)
        if not self.marker.pressed and event.button() == Qt.MouseButton.LeftButton:
            self.playhead.triangle.pressed = True
            new_x = self.mapToScene(event.pos()).x()
            self.move_playhead_to_x(new_x)
            self.playhead.triangle.pressed = False
            self.lmb_holding = True

    def mouseReleaseEvent(self, event):
        self.scene().update()
        self.lmb_holding = False
        self.dragging_playhead = False
        self.marker.pressed = False
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        mouse_pos = self.mapToScene(event.pos()).x()
        # get the current position of the view
        view_pos = self.horizontalScrollBar().value()
        # get the width of the view
        view_width = self.rect().width()
        if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
            self.set_hover_line_from_x(mouse_pos)
        else:
            self.hover_line.hide()
        # if we're in the top 50 pixels and holding the left mouse button, move the playhead to the current mouse position
        if self.lmb_holding and not self.marker.pressed:
            self.dragging_playhead = True
        if self.dragging_playhead:
            # get the current position of the mouse
            mouse_pos = self.mapToScene(event.pos()).x()
            # get the current position of the view
            view_pos = self.horizontalScrollBar().value()
            # get the width of the view
            view_width = self.rect().width()
            if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
                # if we're holding shift, snap to the nearest behavior onset or offset if it's within 20 pixels
                # snapped_x = round(new_x / self.frame_width) * self.frame_width
                frame = self.get_frame_of_x_pos(mouse_pos)
                # if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                #     # get the nearest behavior onset
                #     for track, onset_list in self.item_keys_to_render.items():
                #         for key in onset_list:
                #             behavior = track.behavior_items[key]

                #             if (
                #                 abs(mouse_pos - self.get_x_pos_of_frame(behavior.onset))
                #                 < 20
                #             ):
                #                 frame = behavior.onset
                #                 break
                #             if (
                #                 abs(
                #                     mouse_pos - self.get_x_pos_of_frame(behavior.offset)
                #                 )
                #                 < 20
                #             ):
                #                 frame = behavior.offset
                #                 break

                self.playhead.triangle.pressed = True
                self.move_playhead_to_frame(frame)
                self.playhead.triangle.pressed = False

        self.scene().update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.scene().update()
        self.lmb_holding = False
        self.dragging_playhead = False
        self.marker.pressed = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        self._timeline_view.wheelEvent(event)
        self.update()

    def update(self):
        self.move_playhead_to_frame(self.playhead.current_frame)
        self.scene().update()
        self.repaint()
        super().update()

    def scroll_changed(self):
        self.horizontalScrollBar().setValue(
            self._timeline_view.horizontalScrollBar().value()
        )
        self.repaint()

    def paintEvent(self, event: QPaintEvent | None) -> None:
        super().paintEvent(event)
        # TODO: the below might be unnecessary
        if self.marker.isVisible():
            self.marker.setZValue(10000)
            y_pos = self.mapToScene(0, 0).y() + 20
            self.marker.setPos(self.get_x_pos_of_frame(self.marker.onset), y_pos)
            self.marker.setRect(
                0,
                0,
                self.get_x_pos_of_frame(self.marker.offset)
                - self.get_x_pos_of_frame(self.marker.onset),
                50,
            )


class TimelineRuler(QtWidgets.QWidget):
    """The timeline ruler is a widget that displays the ruler for the timeline."""

    def __init__(self, view: "TimelineView"):
        super().__init__()
        self._view = TimelineRulerView(view)
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.addWidget(self._view)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._view.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setFixedHeight(50)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setMouseTracking(True)
        self._view.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.TextAntialiasing
        )
        self._view.setTransformationAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self._view.setResizeAnchor(
            QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
