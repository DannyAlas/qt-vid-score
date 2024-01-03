import datetime
import logging
import math
from typing import TYPE_CHECKING, List, Union

from PyQt6 import QtGui
from qtpy import QtGui, QtWidgets
from qtpy.QtCore import QPointF, QRectF, Qt, Signal, Slot
from qtpy.QtGui import QPainter, QPen
from qtpy.QtWidgets import (QDockWidget, QFrame, QGraphicsLineItem,
                            QGraphicsScene, QGraphicsTextItem, QGraphicsView,
                            QMenu)

from video_scoring.command_stack import Command
from video_scoring.settings.base_settings import BehaviorTrackSetting
from video_scoring.widgets.timeline.behavior_items import OnsetOffsetItem
from video_scoring.widgets.timeline.commands import (
    AddBehaviorCommand, BatchDeleteBehaviorCommand, DeleteBehaviorCommand,
    DeleteTrackCommand)
from video_scoring.widgets.timeline.marker import MarkerItem
from video_scoring.widgets.timeline.playhead import Playhead
from video_scoring.widgets.timeline.track import BehaviorTrack

if TYPE_CHECKING:
    from video_scoring import MainWindow


class AddTrackDialog(QtWidgets.QDialog):
    def __init__(self, parent: "TimelineDockWidget"):
        super().__init__()
        self.parent = parent
        self.setWindowTitle("Add Track")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.WindowTitleHint, False)
        self.setFixedSize(300, 100)
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Track Name")
        self.layout.addWidget(self.name_input)
        self.button_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.add_button = QtWidgets.QPushButton("Add")
        self.add_button.clicked.connect(self.add_track)
        self.add_button.setDefault(True)
        self.button_layout.addWidget(self.add_button)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.cancel_button)

    def add_track(self):
        name = self.name_input.text()
        if name:
            try:
                self.parent.timeline_view.add_behavior_track(name)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
            self.close()


class RenameTrackDialog(QtWidgets.QDialog):
    def __init__(self, parent: "TimelineDockWidget", track: "BehaviorTrack"):
        super().__init__()
        self.parent = parent
        self.track = track
        self.setWindowTitle("Rename Track")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.WindowTitleHint, False)
        self.setFixedSize(300, 100)
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText(self.track.name)
        self.layout.addWidget(self.name_input)
        self.button_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.button_layout)
        self.add_button = QtWidgets.QPushButton("Rename")
        self.add_button.clicked.connect(self.rename_track)
        self.add_button.setDefault(True)
        self.button_layout.addWidget(self.add_button)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        self.button_layout.addWidget(self.cancel_button)

    def rename_track(self):
        name = self.name_input.text()
        if name:
            self.track.name = name
            self.track.update_name(name)
            self.close()


class TimelineView(QGraphicsView):
    valueChanged = Signal(int)
    behavior_tracks_changed = Signal()
    base_frame_width = 50

    def __init__(
        self,
        parent: "TimelineDockWidget" = None,
        main_window: "MainWindow" = None,
    ):
        super().__init__()
        self.main_window = main_window
        self.parent = parent

        self._init_props()
        self._init_scene()
        self._init_view()
        self._init_interaction()
        self._init_playhead()
        self._init_hover_line()
        self._init_track_props()
        self._init_marker()

    @property
    def frame_width(self):
        """The width of each frame in pixels"""
        return self._frame_width

    @frame_width.setter
    def frame_width(self, value: float):
        if value == 0:
            raise ValueError("Frame width must be greater than 0")
        if type(value) != float:
            raise TypeError("Frame width must be an integer")
        self._frame_width = value
        self.playhead.updateFrameWidth(value)

    @property
    def num_frames(self):
        """The total number of frames in the timeline"""
        return self._num_frames

    @num_frames.setter
    def num_frames(self, value):
        if value < 1:
            raise ValueError("Number of frames must be greater than 0")
        if type(value) != int:
            raise TypeError("Number of frames must be an integer")
        self._num_frames = value

    @property
    def zoom_factor(self):
        return self._zoom_factor

    @zoom_factor.setter
    def zoom_factor(self, value):
        self._zoom_factor = value

    def _init_props(self):
        self.show_time = False
        self.visible_left_frame = 0
        self.visible_right_frame = 0
        self._num_frames = 1  # Total number of frames in the timeline
        self._frame_width = self.base_frame_width  # Current width for each frame
        self._zoom_factor = 1.1  # Factor for zooming in and out
        self.playing = False  # Whether the mouse wheel is being used
        self.lmb_holding = False  # Whether the left mouse button is being held
        self.dragging_playhead = False  # Whether the playhead is being dragged
        self.item_keys_to_hide: dict[
            int, "BehaviorTrack"
        ] = (
            {}
        )  # A dict of key for the item to hide and the corresponding behavior track
        self.item_keys_to_render: dict[
            "BehaviorTrack", List[int]
        ] = {}  # A dict of tracks with item onset or offset in the visible range

    def _init_view(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(QPainter.RenderHint.Antialiasing)

    def _init_scene(self):
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, self.num_frames * self.frame_width, 60)

    def _init_interaction(self):
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        self.setInteractive(True)

    def _init_playhead(self):
        self.playhead = Playhead(10, 0, 60, self.frame_width, self)
        self.scene().addItem(self.playhead)
        self.playhead.triangle.signals.valueChanged.connect(self.valueChanged.emit)

    def _init_hover_line(self):
        self.hover_line = QGraphicsLineItem(0, 0, 0, 0)
        self.scene().addItem(self.hover_line)
        self.hover_line.hide()

    def _init_marker(self):
        self.marker = MarkerItem(0, 0, self, self)
        self.marker.setVisible(False)
        self.scene().addItem(self.marker)

    def _init_track_props(self):
        self.track_height = 50
        self.track_y_start = 50
        self.behavior_tracks: List[BehaviorTrack] = []
        self.track_name_to_save_on = None

    def set_track_to_save_on(self, track_idx: int):
        if track_idx is not None and len(self.behavior_tracks) > 0:
            self.track_name_to_save_on = self.behavior_tracks[track_idx].name

    def get_track_from_name(self, name: str) -> Union[BehaviorTrack, None]:
        for track in self.behavior_tracks:
            if track.name == name:
                return track
        return None

    def get_track_idx_from_name(self, name: str) -> Union[int, None]:
        for idx, track in enumerate(self.behavior_tracks):
            if track.name == name:
                return idx
        return None

    def add_behavior_track(self, name: str):
        # check if the track already exists, raise an error if it does
        for track in self.behavior_tracks:
            if track.name == name:
                raise ValueError("Track with name {} already exists".format(name))

        # get the y position of the new track
        y_pos = len(self.behavior_tracks) * self.track_height + self.track_y_start
        # create the new track
        track = BehaviorTrack(name, y_pos + 30, self.track_height, "OnsetOffset", self)
        self.behavior_tracks.append(track)
        self.scene().addItem(track)
        # resize the view so that the track we can see the track
        # self.resize(self.rect().width(), y_pos + self.track_height + 10)
        self.behavior_tracks_changed.emit()
        self.scene().update()
        self.main_window.project_settings.scoring_data.behavior_tracks = (
            self.parent.serialize_tracks()
        )
        return track

    def silent_add_oo_behavior(self, onset, offset=None, track_idx=None, unsure=False):
        if track_idx is None:
            track_idx = self.get_track_idx_from_name(self.track_name_to_save_on)
        if track_idx is None:
            track_idx = 0
        if self.behavior_tracks[track_idx].curr_behavior_item is None:
            x = self.behavior_tracks[track_idx].check_for_overlap(onset)
            if x is None:
                i = self.behavior_tracks[track_idx].add_behavior(onset, unsure=unsure)
                if offset is not None:
                    i.set_offset(offset)
                    self.behavior_tracks[track_idx].curr_behavior_item = None
                self.scene().update()
            else:
                x.setErrored()
        else:
            self.behavior_tracks[track_idx].curr_behavior_item = None
        self.main_window.timestamps_dw.refresh()

    # def add_ts(self, ts, track_idx=None):
    #     if track_idx is None:
    #         track_idx = self.get_track_idx_from_name(self.track_name_to_save_on)
    #     if track_idx is None:
    #         track_idx = 0
    #     # if the tracks curr_behavior_item is None then the ts is an onset
    #     cur_itm = self.behavior_tracks[track_idx].curr_behavior_item
    #     if cur_itm is None:
    #         self.add_oo_behavior(onset=ts, track_idx=track_idx)
    #     # otherwise it's an offset
    #     else:
    #         ovlp = self.behavior_tracks[track_idx].check_for_overlap(cur_itm.onset, ts)
    #         if ovlp is None:
    #             cur_itm.set_offset(ts)
    #             self.behavior_tracks[track_idx].curr_behavior_item = None
    #             self.scene().update()
    #         else:
    #             ovlp.setErrored()

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

    def add_oo_behavior(
        self, onset, offset=None, track_idx=None, unsure=False
    ) -> Union[None, OnsetOffsetItem]:
        # FIXME: this is overly convoluted and needs to be simplified,
        # use add_ts to add an unknown ts to the timeline,
        # this function should only be used to add an onset or offset
        ret = None
        if track_idx is None:
            track_idx = self.get_track_idx_from_name(self.track_name_to_save_on)
        if track_idx is None:
            track_idx = 0
        if self.behavior_tracks[track_idx].curr_behavior_item is None:
            ovlp = self.behavior_tracks[track_idx].check_for_overlap(onset, offset)
            if ovlp is None:
                i = self.behavior_tracks[track_idx].add_behavior(onset, unsure=unsure)
                if offset is not None:
                    i.set_offset(offset)
                    self.behavior_tracks[track_idx].curr_behavior_item = None
                self.scene().update()
                ret = i
            else:
                ovlp.setErrored()
                return None
        else:
            self.behavior_tracks[track_idx].curr_behavior_item = None
        self.main_window.timestamps_dw.refresh()
        return ret

    def delete_oo_behavior(self, onset: int, track: "BehaviorTrack"):
        item = track.remove_behavior(track.behavior_items[onset])
        self.scene().update()
        self.main_window.timestamps_dw.refresh()
        self.main_window.command_stack.add_command(
            DeleteBehaviorCommand(self, track, item)
        )

    def batch_delete_oo_behavior(self, items: List["OnsetOffsetItem"]):
        for item in items:
            track = item.parent
            track.remove_behavior(item)
        self.scene().update()
        self.main_window.timestamps_dw.refresh()
        self.main_window.command_stack.add_command(
            BatchDeleteBehaviorCommand(self, items)
        )

    def get_item_at_frame(self, frame: int):
        # get the item at a specific frame
        for track in self.behavior_tracks:
            for onset, item in track.behavior_items.items():
                if frame >= onset and frame <= item.offset:
                    return item
        return None

    def set_length(self, length: int):
        if length < 1:
            raise ValueError("Length must be greater than 0")
        self.num_frames = length
        self.setSceneRect(0, 0, length * self.frame_width, 60)
        self.playhead.setLine(
            0,
            self.mapToScene(0, 10).y(),
            0,
            self.mapToScene(0, 0).y() + self.rect().height(),
        )
        self.playhead.triangle.setPos(
            self.playhead.triangle.boundingRect().width() / 2 - 11,
            self.mapToScene(0, 0).y() + 20,
        )
        if self.num_frames > 100:
            self.base_frame_width = 50
            self.frame_width = 5.0
        self.move_playhead_to_frame(1)
        self.scene().update()

    def get_time_from_frame(self, frame: int) -> float:
        seconds = (
            frame
            / self.main_window.video_player_dw.video_widget.play_worker.vc.video.fps
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

    def get_time_from_second(self, second: int) -> str:
        # convert seconds to a datetime object
        datetime_object = datetime.datetime(1, 1, 1) + datetime.timedelta(
            seconds=second
        )
        # if we're in the hours format to HH:MM:SS
        if second >= 3600:
            datetime_object = datetime_object.strftime("%H:%M:%S")
        # if we're in the minutes format to MM:SS
        elif second >= 60:
            datetime_object = datetime_object.strftime("%M:%S")
        # if we're in the seconds format to seconds:milliseconds but only show 3 decimal places
        else:
            datetime_object = datetime_object.strftime("%S.%f")[:-4]
        return datetime_object

    def get_visible_frames_with_x(self, dynamic_interval):
        """
        Calculate and return a generator of tuples with frame numbers and their corresponding x positions.
        """
        frame_index = max(
            0, self.visible_left_frame - self.visible_left_frame % dynamic_interval
        )
        major_tick_start = (
            self.visible_left_frame - self.visible_left_frame % dynamic_interval
        )
        minor_tick_start = (
            self.visible_left_frame
            - self.visible_left_frame % self.inter_tick_skip_factor
        )
        while frame_index <= self.visible_right_frame:
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

    def get_playhead_frame(self):
        # get the current frame the playhead is on
        return int(self.playhead.pos().x() / self.frame_width)

    def get_x_pos_of_frame(self, frame: int) -> int:
        # given a frame, get the x position of that frame in the scene
        return int(frame * self.frame_width)

    def get_frame_of_x_pos(self, x_pos: float) -> int:
        # get the frame of a position
        snapped_x = round(x_pos / self.frame_width) * self.frame_width
        return int(snapped_x / self.frame_width)

    def get_visable_frames(self):
        # returns a tuple of the left and right visible frames
        left = int(self.mapToScene(0, 0).x() / self.frame_width)
        right = int(
            (self.mapToScene(self.rect().width(), 0).x() / self.frame_width) + 1
        )
        return left, right

    def move_playhead_to_frame(self, frame: int):
        # move the playhead to a specific frame
        self.playhead.setPos(abs(self.get_x_pos_of_frame(frame)), 0)
        self.playhead.triangle.current_frame = frame
        # TODO: add a setting for weather playhead should update
        # the curr_behavior_item offset
        track = self.get_track_from_name(self.track_name_to_save_on)
        if track is not None:
            if track.curr_behavior_item is not None:
                x = track.check_for_overlap(
                    track.curr_behavior_item.onset,
                    frame,
                )
                if x is None:
                    track.curr_behavior_item.set_offset(frame)
                else:
                    x.setErrored()
        self.valueChanged.emit(frame)
        self.scene().update()

    def scroll_to_playhead(self):
        """Scroll the view to the playhead if it is outside the view"""
        if (
            self.playhead.pos().x() < self.horizontalScrollBar().value()
            or self.playhead.pos().x()
            > self.horizontalScrollBar().value() + self.rect().width()
        ):
            if not self.playhead.triangle.pressed:
                # get the current position of the playhead
                playhead_pos = self.playhead.pos().x()
                # get the current position of the view
                view_pos = self.horizontalScrollBar().value()
                # get the width of the view
                view_width = self.rect().width()
                # if the playhead is to the left of the view, scroll left
                if playhead_pos <= view_pos:
                    # if we can scroll left by the width of the view, do so
                    self.horizontalScrollBar().setValue(int(view_width))
                    # otherwise, just scroll to the beginning
                    if self.horizontalScrollBar().value() == view_pos:
                        self.horizontalScrollBar().setValue(0)
                # if the playhead is to the right of the view, scroll right so that the playhead is all way to the left
                elif playhead_pos > view_pos + view_width:
                    self.horizontalScrollBar().setValue(int(playhead_pos))

    def draw_frame_ticks(self, painter, frame_index, dynamic_interval, x):
        if frame_index % dynamic_interval == 0:
            # Draw major tick for frames
            painter.drawLine(x, self.tick_top, x, self.tick_bottom)
            painter.drawText(
                QRectF(x - 20, self.tick_bottom, 40, 20),
                Qt.AlignmentFlag.AlignCenter,
                str(frame_index),
            )
        elif frame_index % self.inter_tick_skip_factor == 0:
            # Draw minor tick for frames
            painter.drawLine(x, self.tick_top + 5, x, self.tick_bottom - 5)

    def draw_time_ticks(self, painter, frame_index, dynamic_interval, x):
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
                QRectF(x - 20, self.tick_bottom, text_width, 20),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
        elif frame_index % self.inter_tick_skip_factor == 0:
            # Draw minor tick
            painter.drawLine(x, self.tick_top + 5, x, self.tick_bottom - 5)

    def wheelEvent(self, event):
        # if we're holding ctrl, zoom in or out
        if event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.zoomEvent(event)
        # otherwise, scroll left or right
        else:
            self.scrollEvent(event)

    def zoomEvent(self, event):
        og_frame_at_mouse = self.get_frame_of_x_pos(self.mapToScene(event.pos()).x())
        # Zoom in or out by changing the frame width
        # alt switches the angle delta to horizontal, so we use x() instead of y()
        if event.angleDelta().x() > 0:
            # Zoom in (increase frame width)
            # but if we're zoomed in too far, don't zoom in
            if self.frame_width < self.base_frame_width * 10:
                self.frame_width *= self.zoom_factor
        elif event.angleDelta().x() < 0:
            # Zoom out (decrease frame width)
            # but if we're all the frames can't fit in the view, don't zoom out
            if self.num_frames * self.frame_width > self.rect().width():
                self.frame_width /= self.zoom_factor
        # Update the frame width of the playhead
        self.playhead.updateFrameWidth(self.frame_width)
        # Update the scene rect to reflect the new total width of the timeline
        total_width = self.num_frames * self.frame_width
        self.setSceneRect(0, 0, total_width, 60)
        # move the playhead to the current frame
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        # scroll such that the frame under the mouse is in the same position
        # get the new position of the mouse
        new_frame_at_mouse = self.get_frame_of_x_pos(self.mapToScene(event.pos()).x())
        # get the difference in x position between the old and new mouse position
        delta_x = self.get_x_pos_of_frame(og_frame_at_mouse) - self.get_x_pos_of_frame(
            new_frame_at_mouse
        )
        # scroll the view by the difference in x position
        self.horizontalScrollBar().setValue(
            int(self.horizontalScrollBar().value() + delta_x)
        )

        self.update()
        self.scene().update()

    def scrollEvent(self, event):
        # Scroll left or right by changing the scene position
        if event.angleDelta().y() > 0:
            # Scroll left
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 10)
        elif event.angleDelta().y() < 0:
            # Scroll right
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 10)
        self.update()
        self.scene().update()

    def mouseMoveEvent(self, event):
        mouse_pos = self.mapToScene(event.pos()).x()
        # get the current position of the view
        view_pos = self.horizontalScrollBar().value()
        # get the width of the view
        view_width = self.rect().width()
        if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
            # if the mouse is within the view, draw a vertical line
            # Snap to the nearest frame
            new_x = self.mapToScene(event.pos()).x()
            snapped_x = round(new_x / self.frame_width) * self.frame_width
            self.hover_line.setLine(
                snapped_x,
                self.mapToScene(0, 0).y(),
                snapped_x,
                self.mapToScene(0, 0).y() + 30,
            )
            # set pen color to light gray
            pen = QPen(Qt.GlobalColor.lightGray, 0.3)
            self.hover_line.setPen(pen)
            self.hover_line.show()
        else:
            self.hover_line.hide()
        # if we're in the top 50 pixels and holding the left mouse button, move the playhead to the current mouse position
        if self.lmb_holding and event.pos().y() < 50 and not self.marker.pressed:
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
                snapped_x = round(new_x / self.frame_width) * self.frame_width
                if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                    # get the nearest behavior onset
                    for track, onset_list in self.item_keys_to_render.items():
                        for key in onset_list:
                            behavior = track.behavior_items[key]

                            if (
                                abs(mouse_pos - self.get_x_pos_of_frame(behavior.onset))
                                < 20
                            ):
                                frame = behavior.onset
                                break
                            if (
                                abs(
                                    mouse_pos - self.get_x_pos_of_frame(behavior.offset)
                                )
                                < 20
                            ):
                                frame = behavior.offset
                                break

                self.playhead.triangle.pressed = True
                self.move_playhead_to_frame(self.get_frame_of_x_pos(snapped_x))
                self.playhead.triangle.pressed = False

        self.scene().update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        # if we're in the top 50 pixels, get the frame at the current mouse position and move the playhead to that frame
        super().mousePressEvent(
            event
        )  # call first so that items intercept the events first (i.e. the marker setting pressed)
        if event.button() == Qt.MouseButton.LeftButton:
            if (
                event.pos().y() < 50
                and not self.lmb_holding
                and not self.marker.pressed
            ):
                # turn off the rubber band selection
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
                # get the current position of the mouse
                mouse_pos = self.mapToScene(event.pos()).x()
                # get the current position of the view
                view_pos = self.horizontalScrollBar().value()
                # get the width of the view
                view_width = self.rect().width()
                # if the mouse is within the view, draw a vertical line
                if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
                    frame = int(mouse_pos / self.frame_width) + 1
                    self.playhead.triangle.pressed = True
                    self.move_playhead_to_frame(frame)
                    self.playhead.triangle.pressed = False
            self.lmb_holding = True

    def mouseReleaseEvent(self, event):
        self.scene().update()
        self.lmb_holding = False
        self.dragging_playhead = False
        self.marker.pressed = False
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        self.playhead.triangle.setPos(
            self.playhead.triangle.boundingRect().width() / 2 - 11,
            self.mapToScene(0, 0).y() + 20,
        )
        self.playhead.setLine(
            0,
            self.mapToScene(0, 10).y(),
            0,
            self.mapToScene(0, 0).y() + self.rect().height(),
        )
        self.hover_line.setLine(
            1, self.mapToScene(0, 0).y(), 1, self.mapToScene(0, 0).y() + 30
        )
        return super().resizeEvent(event)

    def drawBackground(self, painter: QPainter, rect):
        """
        Draws the background of a timeline, including ticks for frames or time.
        """
        pen = QPen(
            Qt.GlobalColor.gray, 1
        )  # Set the pen color and width for the drawing
        painter.setPen(pen)

        self.visible_left_frame, self.visible_right_frame = self.get_visable_frames()
        # Determine skip factors for major and minor ticks
        self.skip_factor = max(1, int(self.base_frame_width / self.frame_width))
        self.inter_tick_skip_factor = max(
            1, int(self.skip_factor / 20)
        )  # for minor ticks
        dynamic_interval = self.get_dynamic_interval(
            (self.visible_left_frame, self.visible_right_frame)
        )
        # Define tick dimensions and positions
        self.tick_size = 20
        self.top_margin = 25
        self.tick_top = int(self.mapToScene(0, 0).y() + self.top_margin)
        self.tick_bottom = self.tick_top + self.tick_size

        for frame_index, x in self.get_visible_frames_with_x(dynamic_interval):
            # Draw a unique tick for the first frame
            if frame_index == 1:
                painter.drawLine(x, self.tick_top + 5, x, self.tick_bottom - 5)
            if self.show_time:
                self.draw_time_ticks(painter, frame_index, dynamic_interval, x)
            else:
                self.draw_frame_ticks(painter, frame_index, dynamic_interval, x)
        super().drawBackground(painter, rect)

    def paintEvent(self, event) -> None:
        self.playhead.triangle.setPos(
            self.playhead.triangle.boundingRect().width() / 2 - 11,
            self.mapToScene(0, 0).y() + 20,
        )
        self.playhead.setLine(
            0,
            self.mapToScene(0, 10).y(),
            0,
            self.mapToScene(0, 0).y() + self.rect().height(),
        )

        for track in self.behavior_tracks:
            if track.curr_behavior_item is not None:
                track.curr_behavior_item.highlight()

        # get the range of visible frames in the view
        l, r = self.get_visable_frames()
        for track in self.behavior_tracks:
            # at top z index, draw the track name in light gray
            track.track_name_item.setPos(
                self.mapToScene(0, track.y_position).x() + 5,
                self.mapToScene(0, track.y_position).y(),
            )
            if track.track_name_item not in self.scene().items():
                self.scene().addItem(track.track_name_item)
            track.track_name_item.setZValue(100)
            track.track_name_item.setDefaultTextColor(Qt.GlobalColor.lightGray)
            track.track_name_item.setFont(QtGui.QFont("Arial", 10))
            # draw the track rect
            track.setRect(
                0,
                self.mapToScene(0, track.y_position).y(),
                self.mapToScene(0, 0).x() + self.rect().width(),
                track.track_height,
            )
            ################################ LOD RENDERING ################################

            # get the list of items whos onset and item.offset fall outside the visible range
            self.item_keys_to_hide[track] = [
                key for key in track.behavior_items.keys() if key < l or key > r
            ]
            self.item_keys_to_render[track] = [
                key for key in track.behavior_items.keys() if key >= l and key <= r
            ]
            for item in track.behavior_items.values():
                if not item.pressed:
                    item.setPos(
                        self.get_x_pos_of_frame(item.onset),
                        self.mapToScene(0, track.y_position).y() + 2,
                    )
                    item.setRect(
                        0,
                        0,
                        self.get_x_pos_of_frame(item.offset)
                        - self.get_x_pos_of_frame(item.onset),
                        track.track_height - 4,
                    )
                    t = self.get_track_from_name(self.track_name_to_save_on)
                    if t is not None:
                        if not item != t.curr_behavior_item:
                            item.unhighlight()

        # if the marker is visible, draw it in the top
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

        return super().paintEvent(event)

    def update_track_view(self):
        for idx, track in enumerate(self.behavior_tracks):
            track.y_position = idx * self.track_height + 70
        self.setMinimumHeight(10)

    def update(self):
        track = self.get_track_from_name(self.track_name_to_save_on)
        if track is not None:
            if track.curr_behavior_item is not None:
                it = self.get_track_from_name(
                    self.track_name_to_save_on
                ).curr_behavior_item
                if self.get_track_from_name(
                    self.track_name_to_save_on
                ).overlap_with_item_check(it, onset=self.get_playhead_frame()):
                    it.setErrored()
                else:
                    self.get_track_from_name(
                        self.track_name_to_save_on
                    ).curr_behavior_item.set_offset(self.get_playhead_frame())

        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        super().update()


class TimelineDockWidget(QDockWidget):
    """A dock widget that contains the timeline view"""

    valueChanged = Signal(int)
    loaded = Signal()

    def __init__(self, main_win: "MainWindow", parent=None):
        super(TimelineDockWidget, self).__init__(parent)
        self.setWindowTitle("Timeline")
        self.main_win = main_win
        self.timeline_view = TimelineView(self, self.main_win)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFloating(False)

        # custom context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # add combo box to select which track to save on
        self.track_to_save_on = QtWidgets.QComboBox()
        self.track_to_save_on.addItems(
            [track.name for track in self.timeline_view.behavior_tracks]
        )
        self.track_to_save_on.currentIndexChanged.connect(
            self.timeline_view.set_track_to_save_on
        )
        self.show_time_or_frame = QtWidgets.QComboBox()
        self.show_time_or_frame.addItems(["Frame", "Time"])
        if self.timeline_view.show_time:
            self.show_time_or_frame.setCurrentIndex(1)
        else:
            self.show_time_or_frame.setCurrentIndex(0)
        self.show_time_or_frame.currentIndexChanged.connect(
            self.toggle_show_time_or_frame
        )
        self.update_track_to_save()

        self.tool_bar = QtWidgets.QToolBar()
        self.tool_bar.addWidget(QtWidgets.QLabel("Track to Save On:"))
        self.tool_bar.addWidget(self.track_to_save_on)
        # spacer
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        self.tool_bar.addWidget(spacer)
        self.tool_bar.addWidget(QtWidgets.QLabel("Show:"))
        self.tool_bar.addWidget(self.show_time_or_frame)
        self.tool_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.timeline_view)
        self.layout.addWidget(self.tool_bar)

        self.widget = QtWidgets.QWidget()
        self.widget.setLayout(self.layout)
        self.setWidget(self.widget)

    def toggle_show_time_or_frame(self):
        if self.show_time_or_frame.currentText() == "Frame":
            self.timeline_view.show_time = False
        else:
            self.timeline_view.show_time = True
        self.timeline_view.scene().update()

    def show_context_menu(self, pos):
        # get the item at the current mouse position
        scene_pos = self.timeline_view.mapToScene(pos)
        # not sure why, but we need to offset the y position by  to get the correct item
        scene_pos.setY(scene_pos.y() - 30)
        item = self.timeline_view.scene().itemAt(
            QPointF(scene_pos), self.timeline_view.transform()
        )
        context_menu = QMenu()
        if isinstance(item, OnsetOffsetItem):
            # select the item
            item.setSelected(True)
            # add info
            context_menu = item.get_context_menu()
            context_menu.exec(self.mapToGlobal(pos))
        elif isinstance(item, MarkerItem):
            # select the item
            context_menu = item.get_context_menu()
            context_menu.exec(self.mapToGlobal(pos))
        elif isinstance(item, BehaviorTrack):
            rename_action = context_menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.rename_track(item))
            info_action = context_menu.addAction("Info")
            info_action.triggered.connect(lambda: self.show_info(item))
            delete_track_action = context_menu.addAction("Delete Track")
            delete_track_action.triggered.connect(
                lambda: self.delete_behavior_track(item)
            )
            # show the context menu
            context_menu.exec(self.mapToGlobal(pos))
        else:
            # add the add action
            add_action = context_menu.addAction("Add Track")
            # connect the add action to the add_behavior_track function
            add_action.triggered.connect(self.add_behavior_track)
            # show the context menu
            context_menu.exec(self.mapToGlobal(pos))

    def set_marker_in(self):
        self.timeline_view.set_marker_in(self.timeline_view.get_playhead_frame())

    def set_marker_out(self):
        self.timeline_view.set_marker_out(self.timeline_view.get_playhead_frame())

    def add_oo_behavior(self, onset, offset=None, track_idx=None, unsure=False):
        item = self.timeline_view.add_oo_behavior(onset, offset, track_idx, unsure)
        if item is not None:
            self.main_win.command_stack.add_command(
                AddBehaviorCommand(self.timeline_view, item.parent, item)
            )

    def save_timestamp(self, unsure=False):
        if self.main_win.video_player_dw.video_widget.play_worker is None:
            return
        # get the current frame number
        self.add_oo_behavior(
            onset=self.timeline_view.get_playhead_frame(), unsure=unsure
        )
        self.main_win.timestamps_dw.table_widget.update()

    def save_unsure_timestamp(self):
        self.save_timestamp(unsure=True)

    def delete_selected_timestamp(self):
        # if we have one onset or offset selected, delete it, it it's multiple batch delete
        selected_items = self.timeline_view.scene().selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            if isinstance(item, OnsetOffsetItem):
                self.timeline_view.delete_oo_behavior(item.onset, item.parent)
                self.main_win.timestamps_dw.table_widget.update()
        elif len(selected_items) > 1:
            items: list[OnsetOffsetItem] = []
            for item in selected_items:
                if isinstance(item, OnsetOffsetItem):
                    items.append(item)
            self.timeline_view.batch_delete_oo_behavior(items)
            self.main_win.timestamps_dw.table_widget.update()

    def add_behavior_track(self):
        # open a msg box to get the name of the new track
        dialog = AddTrackDialog(self)
        dialog.exec()
        self.update_track_to_save()

    def delete_behavior_track(self, item):
        if isinstance(item, BehaviorTrack):
            # msg box to confirm deletion
            msg_box = QtWidgets.QMessageBox()
            # warning icon
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Delete Track")
            msg_box.setText(f"Are you sure you want to delete Track: {item.name}?")
            msg_box.setStandardButtons(
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
            )
            msg_box.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
            ret = msg_box.exec()
            if ret == QtWidgets.QMessageBox.StandardButton.No:
                return
            # create the delete track command
            self.main_win.command_stack.add_command(
                DeleteTrackCommand(self.timeline_view, item)
            )
            # remove the track from the timeline view
            self.timeline_view.behavior_tracks.pop(
                self.timeline_view.behavior_tracks.index(item)
            )
            # remove the track from the scene
            self.timeline_view.scene().removeItem(item)
            self.timeline_view.scene().removeItem(item.track_name_item)
            # update the scene
            self.timeline_view.scene().update()
            self.main_win.timestamps_dw.update_tracks()
            # reset the y position of the tracks
            self.timeline_view.update_track_view()
            self.update_track_to_save()

    def rename_track(self, item):
        if isinstance(item, BehaviorTrack):
            # open a msg box to get the name of the new track
            dialog = RenameTrackDialog(self, item)
            dialog.exec()
            self.update_track_to_save()
            self.timeline_view.scene().update()
            self.main_win.timestamps_dw.update_tracks()
            return item.name

    def update_track_color(self, track_name: str, color: str):
        track = self.timeline_view.get_track_from_name(track_name)
        if track is not None:
            track.update_item_colors(color)
            track.update()

    def update_track_name(self, track_name: str, new_name: str):
        track = self.timeline_view.get_track_from_name(track_name)
        if track is not None:
            track.name = new_name
            track.update_name(new_name)
            track.update()
            return track.name
        else:
            return None

    def update_track_to_save(self):
        self.track_to_save_on.clear()
        self.track_to_save_on.addItems(
            [track.name for track in self.timeline_view.behavior_tracks]
        )
        self.timeline_view.set_track_to_save_on(self.track_to_save_on.currentIndex())

    def show_info(self, item):
        if isinstance(item, OnsetOffsetItem):
            # open a msg box and show the onset and offset of the item
            msg_box = QtWidgets.QMessageBox()
            msg_box.setWindowTitle("Info")
            msg_box.setText(
                f"Onset: {item.onset}\nOffset: {item.offset}\nUnsure: {item.unsure}"
            )
            msg_box.exec()
        if isinstance(item, BehaviorTrack):
            # open a msg box and show the onset and offset of the item
            msg_box = QtWidgets.QMessageBox()
            msg_box.setWindowTitle("Info")
            msg_box.setText(
                f"Track Name: {item.name}\nY Position: {item.y_position}\nTrack Height: {item.track_height}"
            )
            msg_box.exec()

    def load_tracks(self):
        if len(self.main_win.project_settings.scoring_data.behavior_tracks) == 0:
            try:
                self.timeline_view.add_behavior_track("Track 1")
            except Exception as e:
                self.main_win.update_status(
                    f"Error loading tracks: {str(e)}", logging.ERROR
                )
        self.update_track_to_save()

    def set_length(self, length: int):
        self.timeline_view.set_length(length)

    def move_to_last_onset_offset(self):
        curr_frame = self.timeline_view.get_playhead_frame()
        # get all onset and offset frames for the current track to save on
        onset_offsets = [
            (item.offset, item.onset)
            for item in self.timeline_view.get_track_from_name(
                self.timeline_view.track_name_to_save_on
            ).behavior_items.values()
        ]
        # sort the onset and offset frames
        onset_offsets.sort(key=lambda x: x[0])
        # reverse the list
        onset_offsets.reverse()
        # get the last onset or offset from the current frame
        last_onset_offset = None
        for onset, offset in onset_offsets:
            if onset < curr_frame:
                last_onset_offset = onset
                break
            elif offset < curr_frame:
                last_onset_offset = offset
                break
        # if we found a last onset or offset, move to it
        if last_onset_offset is not None:
            self.timeline_view.move_playhead_to_frame(last_onset_offset)

    def move_to_next_onset_offset(self):
        curr_frame = self.timeline_view.get_playhead_frame()
        # get all onset and offset frames for the current track to save on
        onset_offsets = [
            (item.onset, item.offset)
            for item in self.timeline_view.get_track_from_name(
                self.timeline_view.track_name_to_save_on
            ).behavior_items.values()
        ]
        # sort the onset and offset frames
        onset_offsets.sort(key=lambda x: x[0])

        # get the next onset or offset from the current frame
        next_onset_offset = None
        for onset, offset in onset_offsets:
            if onset > curr_frame:
                next_onset_offset = onset
                break
            elif offset > curr_frame:
                next_onset_offset = offset
                break
        # if we found a next onset or offset, move to it
        if next_onset_offset is not None:
            self.timeline_view.move_playhead_to_frame(next_onset_offset)

    def move_to_last_timestamp(self):
        pass

    def move_to_next_timestamp(self):
        pass

    def select_current_timestamp(self):
        # get the timestamp at the current frame of the playhead
        # get the item at the current frame
        self.timeline_view.behavior_tracks[
            0
        ].curr_behavior_item = self.timeline_view.get_item_at_frame(
            self.timeline_view.get_playhead_frame()
        )

    def load(self):
        self.layout.removeWidget(self.timeline_view)
        self.timeline_view.deleteLater()
        self.timeline_view = TimelineView(self, self.main_win)
        self.timeline_view.valueChanged.connect(self.valueChanged.emit)
        self.layout.removeWidget(self.tool_bar)
        self.layout.addWidget(self.timeline_view)
        self.layout.addWidget(self.tool_bar)

        self.main_win.timestamps_dw.update_tracks()
        self.toggle_show_time_or_frame()
        if self.main_win.video_player_dw.video_widget.play_worker is not None:
            self.set_length(
                self.main_win.video_player_dw.video_widget.play_worker.vc.len
            )

            for track_s in self.main_win.project_settings.scoring_data.behavior_tracks:
                try:
                    track_item = self.timeline_view.add_behavior_track(track_s.name)
                except Exception as e:
                    from uuid import uuid4

                    new_track_name = track_s.name + "_" + str(uuid4())
                    try:
                        track_item = self.timeline_view.add_behavior_track(
                            new_track_name
                        )
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Track Name Error",
                            f"CRIITICAL ERROR LOADING TRACK {track_s.name}:\n{str(e)}",
                        )
                        return

                track_item.update_item_colors(track_s.color)
                for item in track_s.behavior_items:
                    self.timeline_view.silent_add_oo_behavior(
                        onset=item.onset,
                        offset=item.offset,
                        track_idx=self.timeline_view.get_track_idx_from_name(
                            track_item.name
                        ),
                        unsure=item.unsure,
                    )

            self.load_tracks()
            self.main_win.timestamps_dw.update_tracks()
            self.update_track_to_save()
        else:
            self.set_length(100)
        self.loaded.emit()

    def import_timestamps(
        self, name: str, onset_offset_unsure: list[tuple[int, int, bool]]
    ):
        if len(onset_offset_unsure) == 0:
            self.main_win.update_status("No timestamps passed", logging.ERROR)
            return
        try:
            track = self.timeline_view.add_behavior_track(name)
        except Exception as e:
            from uuid import uuid4

            new_track_name = name + "_" + str(uuid4())
            try:
                track = self.timeline_view.add_behavior_track(new_track_name)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Track Name Error",
                    f"Error loading track {name}:\n{str(e)}\nPLEASE RENAME THE FILE",
                )
                return
        for onset, offset, unsure in onset_offset_unsure:
            self.timeline_view.silent_add_oo_behavior(
                int(onset),
                int(offset),
                track_idx=self.timeline_view.get_track_idx_from_name(track.name),
                unsure=unsure,
            )

        self.main_win.timestamps_dw.update_tracks()
        self.update_track_to_save()

    def serialize_tracks(self) -> list[BehaviorTrackSetting]:
        from video_scoring.settings import (BehaviorTrackSetting,
                                            OOBehaviorItemSetting)

        behavior_tracks = []
        for track in self.timeline_view.behavior_tracks:
            behavior_items = []
            for item in track.behavior_items.values():
                behavior_items.append(
                    OOBehaviorItemSetting(
                        onset=item.onset,
                        offset=item.offset,
                        unsure=item.unsure,
                    )
                )
            behavior_tracks.append(
                BehaviorTrackSetting(
                    name=track.name,
                    color=track.item_color,
                    y_position=track.y_position,
                    track_height=track.track_height,
                    behavior_type=track.behavior_type,
                    behavior_items=behavior_items,
                )
            )
        return behavior_tracks

    def _save_all_to_csv(self):
        # will prompt the user to select a directory to save a csv file for each track
        import os

        tracks_settings_list = self.serialize_tracks()
        # get the directory to save the csv files to
        for track in tracks_settings_list:
            # prompt the user to select the save file location
            save_file = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save CSV File",
                f"{os.getcwd()}/{track.name}.csv",
                "CSV Files (*.csv)",
            )
            # if the user selected a directory
            if save_file[0] != "":
                # create a csv file
                with open(f"{save_file[0]}", "w") as f:
                    # write the header
                    f.write("Onset,Offset\n")
                    # write the onset and offset of each behavior
                    for item in track.behavior_items:
                        f.write(f"{item.onset},{item.offset}\n")

    def refresh(self):
        self.load()
        # reset the y position of the tracks
        self.timeline_view.scene().update()
        self.timeline_view.update()
