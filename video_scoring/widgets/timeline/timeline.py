import logging
from typing import TYPE_CHECKING, List, Union

from cv2 import resize
from qtpy import QtGui, QtWidgets
from qtpy.QtCore import QPoint, QPointF, QRectF, Qt, Signal, Slot
from qtpy.QtGui import QPainter, QPen
from qtpy.QtWidgets import (QDockWidget, QFrame, QGraphicsLineItem,
                            QGraphicsScene, QGraphicsTextItem, QGraphicsView,
                            QMenu)

from video_scoring.settings.base_settings import BehaviorTrackSetting
from video_scoring.widgets.timeline.behavior_items import OnsetOffsetItem
from video_scoring.widgets.timeline.commands import (
    AddBehaviorCommand, BatchDeleteBehaviorCommand, DeleteBehaviorCommand,
    DeleteTrackCommand)
from video_scoring.widgets.timeline.dialogs import (AddTrackDialog,
                                                    RenameTrackDialog)
from video_scoring.widgets.timeline.playhead import PlayheadLine
from video_scoring.widgets.timeline.ruler import TimelineRuler
from video_scoring.widgets.timeline.track import BehaviorTrack
from video_scoring.widgets.timeline.track_header import TrackHeadersWidget

if TYPE_CHECKING:
    from video_scoring import MainWindow


class TimelineView(QGraphicsView):
    valueChanged = Signal(int)
    track_name_to_save_on_changed = Signal(str)
    scene_rect_changed = Signal(QRectF)
    frame_width_changed = Signal(float)
    scrolled = Signal()
    base_frame_width = 50

    def __init__(
        self,
        parent: "TimelineDockWidget" = None,
        main_window: "MainWindow" = None,
    ):
        super().__init__()
        self.main_window = main_window
        self.parent = parent
        self._parent = parent
        self._init_props()
        self._init_scene()
        self._init_view()
        self._init_interaction()
        self._init_playline()
        self._init_track_props()

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
        # update the step size of the scroll bar
        self.setSceneRect(0, 0, self.num_frames * self.frame_width, self.height())
        self.scene_rect_changed.emit(self.sceneRect())
        self.frame_width_changed.emit(value)

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

    @property
    def track_name_to_save_on(self):
        return self._track_name_to_save_on

    @track_name_to_save_on.setter
    def track_name_to_save_on(self, value):
        self._track_name_to_save_on = value
        self.track_name_to_save_on_changed.emit(value)

    def _init_props(self):
        self._track_name_to_save_on = None
        self.show_time = False
        self.visible_left_frame = 0
        self.visible_right_frame = 0
        self._num_frames = 1  # Total number of frames in the timeline
        self._frame_width = self.base_frame_width  # Current width for each frame
        self._zoom_factor = 1.1  # Factor for zooming in and out
        self.playing = False  # Whether the mouse wheel is being used
        self.lmb_holding = False  # Whether the left mouse button is being held
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
        self.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.horizontalScrollBar().valueChanged.connect(self.scrolled.emit)

    def _init_scene(self):
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0, 0, self.num_frames * self.frame_width, 60)
        self.scene_rect_changed.emit(self.sceneRect())
        self.setContentsMargins(0, 0, 0, 0)

    def _init_interaction(self):
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.IntersectsItemShape)
        self.setInteractive(True)

    def _init_playline(self):
        self.playline = PlayheadLine(0, 0, 60, self.frame_width, self)
        self.scene().addItem(self.playline)

    def _init_track_props(self):
        self.track_height = 400
        self.track_y_start = 0
        self.behavior_tracks: List[BehaviorTrack] = []

    def set_track_idx_to_save_on(self, track_idx: int):
        if track_idx is not None and len(self.behavior_tracks) > 0:
            self.track_name_to_save_on = self.behavior_tracks[track_idx].name
            self.track_name_to_save_on_changed.emit(self.track_name_to_save_on)

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
        self.scene().update()
        self.main_window.project_settings.scoring_data.behavior_tracks = (
            self.parent.serialize_tracks()
        )
        self.parent.track_header.add_track_header(track)
        return track

    def silent_add_oo_behavior(self, onset, offset=None, track_idx=None, unsure=False):
        if track_idx is None:
            track_idx = self.get_track_idx_from_name(self.track_name_to_save_on)
        if track_idx is None:
            raise ValueError("No track selected")
        track = self.behavior_tracks[track_idx]
        if track.curr_behavior_item is None:
            if offset is None:
                offset = onset + 1
            not_ovlp, itm = track.add_behavior(onset, unsure=unsure)
            if not_ovlp is True:
                itm.set_offset(offset)
            else:
                itm.setErrored()
        track.curr_behavior_item = None
        self.scene().update()

    def add_ts(self, ts, unsure=False) -> OnsetOffsetItem:
        track = self.get_track_from_name(self.track_name_to_save_on)
        cur_itm = track.curr_behavior_item
        if (
            cur_itm is None
        ):  # if we don't have a current item for this track, add a new item one
            ovlp, itm = track.add_behavior(ts, unsure=unsure)
            if ovlp is False:
                track.curr_behavior_item = itm
                self.scene().update()
                self.main_window.timestamps_dw.refresh()
            else:
                itm.setErrored()
        else:  # if we do have a current item, check if we can set it's offset to the current ts
            ovlp_itm = track.check_for_overlap(cur_itm.onset, ts)
            if ovlp_itm is None:
                cur_itm.set_offset(ts)
                track.curr_behavior_item = None
                self.scene().update()
                self.main_window.timestamps_dw.refresh()
            else:
                ovlp_itm.setErrored()
        return cur_itm

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
        self.scene_rect_changed.emit(self.sceneRect())
        self.playline.setLine(
            0,
            self.mapToScene(0, 0).y(),
            0,
            self.mapToScene(0, 0).y() + self.rect().height(),
        )
        self.playline.current_frame = 1
        if self.num_frames > 100:
            self.base_frame_width = 50
            self.frame_width = 5.0
        self.scene().update()

    def get_playline_frame(self):
        # get the current frame the playline is on
        return round(self.playline.pos().x() / self.frame_width)

    def get_x_pos_of_frame(self, frame: int) -> int:
        # given a frame, get the x position of that frame in the scene
        return round(frame * self.frame_width)

    def get_frame_of_x_pos(self, x_pos: float) -> int:
        # get the frame of a position
        snapped_x = round(x_pos / self.frame_width) * self.frame_width
        return round(snapped_x / self.frame_width)

    def get_visable_frames(self):
        # returns a tuple of the left and right visible frames
        left = int(self.mapToScene(0, 0).x() / self.frame_width)
        right = int(
            (self.mapToScene(self.rect().width(), 0).x() / self.frame_width) + 1
        )
        return left, right

    def move_curr_behavior_item(self, track: "BehaviorTrack", offset: int):
        if track.curr_behavior_item is not None:
            x = track.check_for_overlap(
                track.curr_behavior_item.onset,
                offset,
            )
            if x is None:
                track.curr_behavior_item.set_offset(offset)
            else:
                x.setErrored()

    def move_playline_to_frame(self, frame: int):
        # move the playline to a specific frame
        self.playline.setPos(abs(self.get_x_pos_of_frame(frame)), 0)
        self.playline.current_frame = frame
        self.valueChanged.emit(frame)
        self.scene().update()

    def wheelEvent(self, event: QtGui.QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.zoomEvent(event)
        else:
            self.scrollEvent(event)

    def zoomEvent(self, event: QtGui.QWheelEvent):
        og_frame_at_mouse = self.get_frame_of_x_pos(self.mapToScene(event.pos()).x())
        if event.angleDelta().x() > 0:  # Zoom in (increase frame width)
            if (self.frame_width * self.zoom_factor) < self.base_frame_width:
                self.frame_width *= self.zoom_factor
        elif event.angleDelta().x() < 0:
            if (
                self.num_frames * (self.frame_width / self.zoom_factor)
                > self.rect().width()
            ):
                self.frame_width /= self.zoom_factor
        # move the playline to the current frame
        self.move_playline_to_frame(self.playline.current_frame)
        # scroll such that the frame under the mouse is in the same position
        new_frame_at_mouse = self.get_frame_of_x_pos(self.mapToScene(event.pos()).x())
        delta_x = self.get_x_pos_of_frame(og_frame_at_mouse) - self.get_x_pos_of_frame(
            new_frame_at_mouse
        )
        # scroll the view by the difference in x position
        self.horizontalScrollBar().setValue(
            int(self.horizontalScrollBar().value() + delta_x)
        )
        self.scrolled.emit()
        self.update()
        self.move_playline_to_frame(self.playline.current_frame)
        self.scene().update()

    def scrollEvent(self, event: QtGui.QWheelEvent):
        # Scroll left or right by changing the scene position
        if event.angleDelta().y() > 0:
            # Scroll left
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 10)
        elif event.angleDelta().y() < 0:
            # Scroll right
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 10)
        self.scrolled.emit()
        self.move_playline_to_frame(self.playline.current_frame)
        self.update()
        self.scene().update()

    def mouseMoveEvent(self, event):
        self.parent.timeline_ruler._view.set_hover_line_from_x(
            self.mapToScene(int(event.pos().x()), 0).x()
        )
        self.scene().update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(
            event
        )  # call first so that items intercept the events first (i.e. the marker setting pressed)
        if event.button() == Qt.MouseButton.LeftButton:
            self.lmb_holding = True

    def mouseReleaseEvent(self, event):
        self.scene().update()
        self.lmb_holding = False
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        self.playline.setLine(
            0,
            self.mapToScene(0, 0).y(),
            0,
            self.mapToScene(0, 0).y() + self.rect().height(),
        )
        self._parent.timeline_ruler.repaint()  # ruler seems to miss some updates?
        return super().resizeEvent(event)

    def drawBackground(self, painter: QPainter, rect):
        """
        Draws the background of a timeline, including ticks for frames or time.
        """
        self.parent.timeline_ruler.update()
        super().drawBackground(painter, rect)

    def paintEvent(self, event) -> None:
        # draw the tracks
        for track in self.behavior_tracks:
            if track.curr_behavior_item is not None:
                track.curr_behavior_item.highlight()

        self.visible_left_frame, self.visible_right_frame = self.get_visable_frames()
        for track in self.behavior_tracks:
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
                key
                for key in track.behavior_items.keys()
                if key < self.visible_left_frame or key > self.visible_right_frame
            ]
            self.item_keys_to_render[track] = [
                key
                for key in track.behavior_items.keys()
                if key >= self.visible_left_frame and key <= self.visible_right_frame
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

        return super().paintEvent(event)

    def update_track_view(self):
        for idx, track in enumerate(self.behavior_tracks):
            track.y_position = idx * self.track_height + 70
        self.setMinimumHeight(10)


class TimelineDockWidget(QDockWidget):
    """A dock widget that contains the timeline view"""

    valueChanged = Signal(int)
    loaded = Signal()

    def __init__(self, main_win: "MainWindow", parent=None):
        super(TimelineDockWidget, self).__init__(parent)
        self.setWindowTitle("Timeline")
        self.main_win = main_win
        self.timeline_view = TimelineView(self, self.main_win)
        self.timeline_ruler = TimelineRuler(self.timeline_view)
        self.track_header = TrackHeadersWidget(self, self.timeline_view)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFloating(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.show_time_or_frame = QtWidgets.QComboBox()
        self.show_time_or_frame.addItems(["Frame", "Time"])
        if self.timeline_view.show_time:
            self.show_time_or_frame.setCurrentIndex(1)
        else:
            self.show_time_or_frame.setCurrentIndex(0)
        self.show_time_or_frame.currentIndexChanged.connect(
            self.toggle_show_time_or_frame
        )

        self.tool_bar = QtWidgets.QToolBar()
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

        self.layout = QtWidgets.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(0)

        self.widget = QtWidgets.QWidget()
        self.widget.setContentsMargins(0, 0, 0, 0)
        self.widget.setLayout(self.layout)
        self.setWidget(self.widget)

    def toggle_show_time_or_frame(self):
        if self.show_time_or_frame.currentText() == "Frame":
            self.timeline_view.show_time = False
        else:
            self.timeline_view.show_time = True
        self.timeline_view.scene().update()

    def show_context_menu(self, pos: QPoint):
        scene_pos = self.timeline_view.mapToScene(pos)
        scene_pos.setY(
            scene_pos.y() - self.timeline_ruler.height() - self.tool_bar.height()
        )
        scene_pos.setX(scene_pos.x() - self.track_header.width())
        item = self.timeline_view.scene().itemAt(scene_pos, QtGui.QTransform())
        context_menu = QMenu()
        if isinstance(item, OnsetOffsetItem):
            item.setSelected(True)
            context_menu = item.get_context_menu()
            context_menu.exec(self.mapToGlobal(pos))
        elif isinstance(item, BehaviorTrack):
            context_menu = item.track_header.get_context_menu()
            context_menu.exec(self.mapToGlobal(pos))
        else:
            add_action = context_menu.addAction("Add Track")
            add_action.triggered.connect(self.add_behavior_track)
            context_menu.exec(self.mapToGlobal(pos))

    def set_marker_in(self):
        self.timeline_ruler._view.set_marker_in(self.timeline_view.get_playline_frame())

    def set_marker_out(self):
        self.timeline_ruler._view.set_marker_out(
            self.timeline_view.get_playline_frame()
        )

    def save_timestamp(self, unsure=False):
        if self.main_win.video_player_dw.video_widget.play_worker is None:
            return
        if self.timeline_view.track_name_to_save_on is None:
            return
        item = self.timeline_view.add_ts(
            ts=self.timeline_view.get_playline_frame(), unsure=unsure
        )
        if item is not None:
            self.main_win.command_stack.add_command(
                AddBehaviorCommand(self.timeline_view, item.parent, item)
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
            track = self.timeline_view.behavior_tracks.pop(
                self.timeline_view.behavior_tracks.index(item)
            )
            self.track_header.remove_track_header(track)
            # remove the track from the scene
            self.timeline_view.scene().removeItem(item)
            # update the scene
            self.timeline_view.scene().update()
            self.main_win.timestamps_dw.update_tracks()
            # reset the y position of the tracks
            self.timeline_view.update_track_view()

    def rename_track(self, item):
        if isinstance(item, BehaviorTrack):
            # open a msg box to get the name of the new track
            dialog = RenameTrackDialog(self, item)
            dialog.exec()
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

    def set_track_to_save_on(self, track_name: str):
        self.timeline_view.track_name_to_save_on = track_name

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
                    f"Error loading tracks: {str(e)}", logging.WARN
                )
        else:
            self.timeline_view.behavior_tracks[0].track_header.check_record_button()

    def set_length(self, length: int):
        self.timeline_view.set_length(length)

    def move_to_last_onset_offset(self):
        curr_frame = self.timeline_view.get_playline_frame()
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
            self.timeline_view.move_playline_to_frame(last_onset_offset)

    def move_to_next_onset_offset(self):
        curr_frame = self.timeline_view.get_playline_frame()
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
            self.timeline_view.move_playline_to_frame(next_onset_offset)

    def move_to_last_timestamp(self):
        pass

    def move_to_next_timestamp(self):
        pass

    def select_current_timestamp(self):
        # get the timestamp at the current frame of the playline
        # get the item at the current frame
        self.timeline_view.behavior_tracks[
            0
        ].curr_behavior_item = self.timeline_view.get_item_at_frame(
            self.timeline_view.get_playline_frame()
        )

    def load(self):
        self.layout.removeWidget(self.track_header)
        self.layout.removeWidget(self.timeline_view)
        self.layout.removeWidget(self.timeline_ruler)
        self.layout.removeWidget(self.tool_bar)
        self.timeline_view.deleteLater()
        self.track_header.deleteLater()
        self.timeline_view = TimelineView(self, self.main_win)
        self.timeline_ruler = TimelineRuler(self.timeline_view)
        self.track_header = TrackHeadersWidget(self, self.timeline_view)
        self.timeline_view.valueChanged.connect(self.valueChanged.emit)
        # track header is on the left taking up the first column
        # everything else is in the second column
        self.layout.addWidget(self.track_header, 0, 0, 2, 1)
        self.layout.addWidget(self.timeline_ruler, 0, 1, 1, 1)
        # neagtive spacer to push the timeline view to the top
        self.layout.addWidget(self.timeline_view, 1, 1, 1, 1)
        # tool bar takes up the whol bottom row
        self.layout.addWidget(self.tool_bar, 2, 0, 1, 2)

        self.toggle_show_time_or_frame()
        if self.main_win.video_player_dw.video_widget.play_worker is not None:
            self.set_length(
                self.main_win.video_player_dw.video_widget.play_worker.vc.len
            )
        else:
            self.set_length(100)

        for track_s in self.main_win.project_settings.scoring_data.behavior_tracks:
            try:
                track_item = self.timeline_view.add_behavior_track(track_s.name)
            except ValueError as e:
                from uuid import uuid4

                new_track_name = track_s.name + "_" + str(uuid4())
                try:
                    track_item = self.timeline_view.add_behavior_track(new_track_name)
                except ValueError as e:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Track Name Error",
                        f"CRIITICAL ERROR LOADING TRACK {track_s.name}:\n{str(e)}",
                    )
                    return
            track_item.update_item_colors(track_s.color)
            try:
                track_item.update_shortcut(
                    QtGui.QKeySequence(track_s.save_timestamp_key_sequence),
                )
                track_item.update_unsure_shortcut(
                    QtGui.QKeySequence(track_s.save_unsure_timestamp_key_sequence),
                )
            except Exception as e:
                self.main_win.update_status(
                    f"Error loading track {track_s.name} shortcut: {str(e)}",
                    logging.WARN,
                )
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
        self.main_win.timestamps_dw.refresh()
        self.loaded.emit()

    def import_timestamps(
        self, name: str, onset_offset_unsure: list[tuple[int, int, bool]]
    ):
        if len(onset_offset_unsure) == 0:
            self.main_win.update_status("No timestamps passed", logging.WARN)
            return
        try:
            track = self.timeline_view.add_behavior_track(name)
        except ValueError as e:
            from uuid import uuid4

            new_track_name = name + "_" + str(uuid4())
            try:
                track = self.timeline_view.add_behavior_track(new_track_name)
            except ValueError as e:
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
                    save_timestamp_key_sequence=track.save_ts_ks.toString(),
                    save_unsure_timestamp_key_sequence=track.save_uts_ks.toString(),
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

    def scroll_to_playhead(self):
        """Scroll the view to the playhead if it is outside the view"""
        l, r = self.timeline_view.get_visable_frames()
        if (
            self.timeline_ruler._view.playhead.current_frame < l
            or self.timeline_ruler._view.playhead.current_frame > r
        ):
            if not self.timeline_ruler._view.playhead.triangle.pressed:
                if self.timeline_ruler._view.playhead.current_frame < l:
                    while self.timeline_ruler._view.playhead.current_frame < l:
                        sc = max(
                            0,
                            self.timeline_view.horizontalScrollBar().value()
                            - self.timeline_view.rect().width(),
                        )
                        self.timeline_view.horizontalScrollBar().setValue(sc)
                        l, r = self.timeline_view.get_visable_frames()
                elif self.timeline_ruler._view.playhead.current_frame > r:
                    while self.timeline_ruler._view.playhead.current_frame > r:
                        sc = (
                            self.timeline_view.horizontalScrollBar().value()
                            + self.timeline_view.rect().width()
                        )
                        self.timeline_view.horizontalScrollBar().setValue(sc)
                        l, r = self.timeline_view.get_visable_frames()

    def refresh(self):
        self.load()
        # reset the y position of the tracks
        self.timeline_view.scene().update()
        self.timeline_view.update()
