
import re
from PyQt6 import QtCore, QtGui
from numpy import cfloat
from qtpy.QtWidgets import QGraphicsRectItem, QGraphicsItemGroup, QGraphicsItem, QGraphicsSceneDragDropEvent, QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent, QGraphicsView, QGraphicsScene, QGraphicsLineItem, QGraphicsPolygonItem, QMainWindow, QStyleOptionGraphicsItem, QWidget, QSizePolicy
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, QRectF, QPointF, Signal
from qtpy.QtGui import QColor, QPen, QBrush, QPolygonF
from typing import TYPE_CHECKING, Union, Optional, List, Literal 

if TYPE_CHECKING:
    from video_scoring import MainWindow


class OnsetOffset(dict):
    """
    Represents a dictionary of onset and offset frames. Provides methods to add a new entry with checks for overlap. Handels sorting.

    Notes
    -----
    The Key is the onset frame and the value is a dict with the keys "offset", "sure", and "notes". The value of "offset" is the offset frame. The value of "sure" is a bool indicating if the onset-offset pair is sure. The value of "notes" is a string.

    We only store frames in the dict. The conversion to a time is handled by the UI. We will always store the onset and offset as frames. 
    
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._onset_offset = {}

    def __setitem__(self, key, value):
        # check if the key is a frame number
        if not isinstance(key, int):
            raise TypeError("The key must be an integer")

        # check if the value is a dict
        if not isinstance(value, dict):
            raise TypeError("The value must be a dict")

        # check if the value has the correct keys
        if not all(
            key in value.keys() for key in ["offset", "sure", "notes"]
        ):
            raise ValueError(
                'The value must have the keys "offset", "sure", and "notes"'
            )

        # check if the offset is a frame number
        if value["offset"] is not None and not isinstance(value["offset"], int):
            raise TypeError("The offset must be an integer or None")

        # check if sure is a bool
        if not isinstance(value["sure"], bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if not isinstance(value["notes"], str):
            raise TypeError("The notes value must be a string")

        # check if the onset is already in the dict
        if key in self._onset_offset.keys():
            raise ValueError("The onset is already in the dict")

    def add_onset(self, onset, offset=None, sure=None, notes=None):
        # check if the onset is already in the dict
        if onset in self._onset_offset.keys():
            raise ValueError("The onset is already in the dict")

        # check if the offset is a frame number
        if offset is not None and not isinstance(offset, int):
            raise TypeError("The offset must be an integer or None")

        # check if sure is a bool
        if sure is not None and not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if notes is not None and not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # check for overlap
        self._check_overlap(onset=onset, offset=offset)

        # add the onset to the dict
        self._onset_offset[onset] = {
            "offset": offset,
            "sure": sure,
            "notes": notes,
        }

        # sort dict by onset
        self._onset_offset = dict(sorted(self._onset_offset.items(), key=lambda x: x[0]))

    def add_offset(self, onset, offset):
        # check if the onset is already in the dict
        if onset not in self._onset_offset.keys():
            raise ValueError("The onset is not in the dict")

        # check if the offset is a frame number
        if not isinstance(offset, int):
            raise TypeError("The offset must be an integer")

        # check for overlap
        self._check_overlap(onset=onset, offset=offset)

        # add the offset to the dict
        self._onset_offset[onset]["offset"] = offset

        # sort dict by onset
        self._onset_offset = dict(sorted(self._onset_offset.items(), key=lambda x: x[0]))

    def add_sure(self, onset, sure):
        # check if the onset is already in the dict
        if onset not in self._onset_offset.keys():
            raise ValueError("The onset is not in the dict")

        # check if sure is a bool
        if not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # add the sure to the dict
        self._onset_offset[onset]["sure"] = sure

    def add_notes(self, onset, notes):
        # check if the onset is already in the dict
        if onset not in self._onset_offset.keys():
            raise ValueError("The onset is not in the dict")

        # check if notes is a string
        if not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # add the notes to the dict
        self._onset_offset[onset]["notes"] = notes
        
    def _check_overlap(self, onset, offset=None):
        """
        Check if the provided onset and offset times overlap with any existing ranges.

        Parameters
        ----------
        onset : int
            The onset frame.
        offset : int, optional
            The offset frame, by default None.

        Raises
        ------
        ValueError
            If there is an overlap.
        """
        
        # If we are adding a new onset, check if it will overlap with any existing onset - offset ranges
        if offset is None:
            for n_onset, entry in self._onset_offset.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if onset >= n_onset and onset <= entry["offset"]:
                    raise ValueError(
                        f"The provided onset time of {onset} overlaps with an existing range: {n_onset} - {entry['offset']}"
                    )

        if offset is not None:
            if offset <= onset:
                raise ValueError(
                    f"The provided offset frame of {offset} is before the onset frame of {onset}"
                )
            for n_onset, entry in self._onset_offset.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if onset >= n_onset and onset <= entry["offset"]:
                    raise ValueError(
                        f"The provided onset/offset range of `{onset} : {offset}` overlaps with an existing range: {n_onset} - {entry['offset']}"
                    )

class Single(dict):
    """Represents a dictionary of onset frames. Handels sorting."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._onset = {}

    def __setitem__(self, key, value):
        # check if the key is a frame number
        if not isinstance(key, int):
            raise TypeError("The key must be an integer")

        # check if the value is a dict
        if not isinstance(value, dict):
            raise TypeError("The value must be a dict")

        # check if the value has the correct keys
        if not all(
            key in value.keys() for key in ["sure", "notes"]
        ):
            raise ValueError(
                'The value must have the keys "sure", and "notes"'
            )

        # check if sure is a bool
        if not isinstance(value["sure"], bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if not isinstance(value["notes"], str):
            raise TypeError("The notes value must be a string")

        # check if the onset is already in the dict
        if key in self._onset.keys():
            raise ValueError("The onset is already in the dict")

    def add_onset(self, onset, sure=None, notes=None):
        # check if the onset is already in the dict
        if onset in self._onset.keys():
            raise ValueError("The onset is already in the dict")

        # check if sure is a bool
        if sure is not None and not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if notes is not None and not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # add the onset to the dict
        self._onset[onset] = {
            "sure": sure,
            "notes": notes,
        }

        # sort dict by onset
        self._onset = dict(sorted(self._onset.items(), key=lambda x: x[0]))

    def add_sure(self, onset, sure):
        # check if the onset is already in the dict
        if onset not in self._onset.keys():
            raise ValueError("The onset is not in the dict")

        # check if sure is a bool
        if not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # add the sure to the dict
        self._onset[onset]["sure"] = sure

    def add_notes(self, onset, notes):
        # check if the onset is already in the dict
        if onset not in self._onset.keys():
            raise ValueError("The onset is not in the dict")

        # check if notes is a string
        if not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # add the notes to the dict
        self._onset[onset]["notes"] = notes

class Behaviors(dict):
    """Represents a dictionary of behaviors. Each behavior has a name as a key and implements the OnsetOffset or Singe class as the value."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._behaviors = {}

    def __setitem__(self, key, value):
        # check if the key is a string
        if not isinstance(key, str):
            raise TypeError("The key must be a string")

        # check if the value is a OnsetOffset or Single object
        if not isinstance(value, (OnsetOffset, Single)):
            raise TypeError("The value must be a OnsetOffset or Single object")

        # check if the onset is already in the dict
        if key in self._behaviors.keys():
            raise ValueError("The behavior is already in the dict")

    def add_behavior(self, name, behavior_type: Union[OnsetOffset, Single]):
        # check if the behavior is already in the dict
        if name in self._behaviors.keys():
            raise ValueError("The behavior is already in the dict")

        # add the behavior to the dict
        self._behaviors[name] = behavior_type

class playheadSignals(QtCore.QObject):
    valueChanged = Signal(int)
class DraggableTriangle(QGraphicsPolygonItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = playheadSignals()
        # Define the shape as a pentagon
        self.setPolygon(QPolygonF([
            QPointF(-10, -12), 
            QPointF(10, -12),
            QPointF(10, -5), 
            QPointF(0, 0),
            QPointF(-10, -5),
            ]))
        self.setBrush(QBrush(QColor("#6aa1f5")))
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable, True)  
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.current_frame = 0
        self.pressed = False

    def mousePressEvent(self, event):
        self.pressed = True
        super().mousePressEvent(event)

    def hoverEnterEvent(self, event):
        # lighten the color of the playhead
        self.setBrush(QBrush(QColor("#a7c8f2")))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # restore the color of the playhead
        self.setBrush(QBrush(QColor("#6aa1f5")))
        super().hoverLeaveEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        super().mouseReleaseEvent(event)

class CustomPlayhead(QGraphicsLineItem):
    def __init__(self, x, y, height, frame_width, tl: 'TimelineView'):
        super().__init__(0, y, 0, y + height + 10)
        self.frame_width = frame_width
        self.tl = tl
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable, False)
        # set color
        pen = QPen(Qt.GlobalColor.black, 2)
        self.setPen(pen)
        self.setZValue(1000)
        # Create the triangle and set it as a child of the line
        self.triangle = DraggableTriangle(self)
        
    def updateFrameWidth(self, new_width):
        self.frame_width = new_width

class OnsetOffsetItemSignals(QtCore.QObject):
    unhighlight_sig = Signal()

class OnsetOffsetItem(QGraphicsRectItem):
    """
    This will be a behavior item that has onset and offset times
    It's edges will be draggable to change the onset and offset times
    Grabbing the middle will move the whole thing
    """
    def __init__(self, onset, offset, view: 'TimelineView', parent: 'BehaviorTrack'=None):
        super().__init__(parent)
        self.parent = parent
        self.view = view
        self.onset = onset
        self.offset = offset
        self.signals = OnsetOffsetItemSignals()
        self.n_onset = None
        self.n_offset = None
        # self.acceptHoverEvents()
        self.pressed = False
        # self.last_mouse_pos = None
        self.left_edge_grabbed = False
        self.right_edge_grabbed = False
        self.hovered = False
        self.hover_left_edge = False
        self.hover_right_edge = False
        self.edge_grab_boundary = 8
        self.extend_edge_grab_boundary = 8
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setAcceptHoverEvents(True)
        self.signals.unhighlight_sig.connect(self.unhighlight)
        # set geometry
        self.base_color = QColor("#6aa1f5")
        self.setBrush(QBrush(self.base_color))
        self.highlight_color = QColor("#9cc5f8")

    def mousePressEvent(self, event):
        # Handle mouse press events
        self.pressed = True
        self.last_mouse_pos = event.pos()
        # if its we're smaller than 10 pixels, determine which edge we're closest to by dividing the width by 2
        if self.rect().width() < 10:
            if event.pos().x() <= self.rect().width() / 2:
                self.left_edge_grabbed = True
                self.right_edge_grabbed = False
            else:
                self.left_edge_grabbed = False
                self.right_edge_grabbed = True
        elif event.pos().x() <= self.edge_grab_boundary + self.extend_edge_grab_boundary:
            self.left_edge_grabbed = True
            self.right_edge_grabbed = False
        elif event.pos().x() >= self.rect().width() - self.edge_grab_boundary - self.extend_edge_grab_boundary:
            self.left_edge_grabbed = False
            self.right_edge_grabbed = True
        else:
            self.left_edge_grabbed = False
            self.right_edge_grabbed = False

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        super().mouseReleaseEvent(event)

    def highlight(self):
        self.setBrush(QBrush(self.highlight_color))

    def unhighlight(self):
        print("unhighlight")
        self.setBrush(QBrush(self.base_color))

    def errorHighlight(self):
        self.setBrush(QBrush(QColor("#ff0000")))

    def setErrored(self):
        # will set the error highlight for a short time
        self.errorHighlight()
        QtCore.QTimer.singleShot(300, self.unhighlight)
        
        

    def mouseMoveEvent(self, event):
        if self.pressed:
            # set our z value to be on top of everything except the playhead
            self.setZValue(999)
            # re implement the mouse move event to move the rect only horizontally
            if self.left_edge_grabbed:
                scene_x  = self.mapToScene(event.pos() - self.last_mouse_pos).x()
                # Ensure the onset is not before the beginning of the video
                if scene_x < 0:
                    return
                nearest_frame = self.view.get_frame_of_x_pos(scene_x)
                # Ensure onset frame does not exceed offset frame
                if nearest_frame >= self.offset:
                    return
                # Get the x position of the nearest frame in scene coordinates
                snapped_x = round(scene_x / self.view.frame_width) * self.view.frame_width
                # Convert snapped x position to local coordinates
                snapped_x_local = snapped_x - self.pos().x()
                # Store the right edge x-coordinate in local coordinates
                right_edge_local = self.rect().right()
                # Calculate the new width
                new_width = right_edge_local - snapped_x_local
                # save the old position
                old_x_local = self.rect().left()
                old_width = self.rect().width()
                # Set the new position and size of the rectangle using local coordinates
                self.setRect(snapped_x_local, self.rect().top(), new_width, self.rect().height())
                self.n_onset = self.view.get_frame_of_x_pos(self.mapToScene(self.rect().left(),0).x())
                try:
                    self.parent.update_behavior(self)
                except ValueError:
                    # If the update fails, revert to the old position and size
                    self.setRect(old_x_local, self.rect().top(), old_width, self.rect().height())
                    self.n_onset = None
            elif self.right_edge_grabbed:
                # Directly use the scene x-coordinate of the mouse for the right edge
                scene_x = min(self.mapToScene(event.pos()).x(), self.view.sceneRect().right())
                snapped_x = round(scene_x / self.view.frame_width) * self.view.frame_width
                snapped_x_local = snapped_x - self.pos().x()
                new_width = snapped_x_local - self.rect().left()
                if new_width < 1:
                    return
                old_width = self.rect().width()
                self.setRect(self.rect().left(), self.rect().top(), new_width, self.rect().height())
                self.n_offset = int(self.mapToScene(event.pos()).x() / self.view.frame_width) + 1
                try:
                    self.parent.update_behavior(self)
                except ValueError:
                    self.setRect(self.rect().left(), self.rect().top(), old_width, self.rect().height())
                    self.n_offset = None
            else:
                scene_pos = self.mapToScene(event.pos() - self.last_mouse_pos)
                # Get the nearest frame based on the mouse x position
                nearest_frame = self.view.get_frame_of_x_pos(scene_pos.x())
                # Get the x position of the nearest frame
                new_x = self.view.get_x_pos_of_frame(nearest_frame)
                if new_x < 0:
                    new_x = 0
                # Get the old width
                old_x = self.pos().x()
                self.setPos(new_x, self.pos().y())
                self.update()
                self.n_onset = self.view.get_frame_of_x_pos(self.mapToScene(self.rect().left(),0).x())
                self.n_offset = self.view.get_frame_of_x_pos(self.mapToScene(self.rect().right(),0).x())
                try:
                    self.parent.update_behavior(self)
                except ValueError:
                    self.setPos(old_x, self.pos().y())
                    self.n_onset = None
                    self.n_offset = None
        self.setZValue(10)
        self.scene().update()

    def hoverEnterEvent(self, event):
        # lighten the color fill of the rectangle
        self.highlight()
        self.hovered = True
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # restore the color of the playhead
        self.unhighlight()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.hovered = False
        self.hover_left_edge = False
        self.hover_right_edge = False
        self.setZValue(10)
        super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        # get our size, if its we're smaller than 10 pixels, determine which edge we're closest to
        if event.pos().x() <= self.edge_grab_boundary + self.extend_edge_grab_boundary:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.hover_left_edge = True
        elif event.pos().x() >= self.rect().width() - self.edge_grab_boundary - self.extend_edge_grab_boundary:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.hover_right_edge = True
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.hover_left_edge = False
            self.hover_right_edge = False
        return super().hoverMoveEvent(event)

    # in our paint event, draw a line on the left and right edges of the rectangle if we're hovered over them
    def paint(self, painter: QtGui.QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        # make a light gray pen with rounded edges
        if self.hovered:
            pen = QPen(Qt.GlobalColor.lightGray, 1)
            painter.setPen(pen)
            # add a border around the rectangle with no fill
            border = QRectF(self.rect().left(), self.rect().top(), self.rect().width(), self.rect().height())
            painter.drawRect(border)
        if self.hover_left_edge:
            pen = QPen(Qt.GlobalColor.lightGray, 3)
            painter.setPen(pen)
            # plce the line on the left edge but offset by 1 pixel so that it doesn't get cut off
            painter.drawLine(int(self.rect().left())-1, 2, int(self.rect().left())-1, int(self.rect().height())-2)
        elif self.hover_right_edge:
            pen = QPen(Qt.GlobalColor.lightGray, 3)
            painter.setPen(pen)
            painter.drawLine(int(self.rect().width()), 2, int(self.rect().width()), int(self.rect().height())-2)
        super().paint(painter, option, widget)
        # This is for debugging
        # painter.setPen(QPen(Qt.GlobalColor.black, 3))
        # painter.setFont(QtGui.QFont("Arial", 10))
        # painter.setBrush(QBrush(Qt.GlobalColor.white))
        # painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        # painter.setRenderHint(QtGui.QPainter.RenderHint.TextAntialiasing)
        # # on the left edge, draw our onset frame
        # painter.drawText(int(self.rect().left()), int(self.rect().top())+10, str(self.onset))        
        # # on the right edge, draw our offset frame
        # painter.drawText(int(self.rect().width())-30, int(self.rect().top())+10, str(self.offset))
class BehaviorTrack(QtWidgets.QGraphicsRectItem):
    def __init__(self, name: str, y_position, track_height, behavior_type: Literal['OnsetOffset', 'Single'], parent:'TimelineView'):
        super().__init__()
        self.parent = parent
        self.name = name
        self.y_position = y_position
        self.track_height = track_height
        self.behavior_type = behavior_type
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
        self.setAcceptHoverEvents(True)
        # dark gray background
        self.setBrush(QBrush(QColor("#545454")))

        # a dict of behavior items where the key is the onset frame and the value is the item
        self.behavior_items: dict[int, OnsetOffsetItem] = {}

    def add_behavior(self, onset):
        # add a new behavior item

        b = OnsetOffsetItem(onset, onset+10, self.parent, self)
        self.behavior_items[onset] = b
        self.update_behavior(b)

    def check_for_overlap(self, onset, offset):
        # check if the provided item overlaps with any existing items
        # if it does, return the item that overlaps
        for other_onset, other_item in self.behavior_items.items():
            # skip the item we're checking
            if other_onset == onset:
                continue
            # if our new onset is between the onset and offset of another item, don't update the onset
            if onset >= other_onset and onset <= other_item.offset:
                return other_item
            # if our new offset is between the onset and offset of another item, don't update the offset
            if offset >= other_onset and offset <= other_item.offset:
                return other_item
        return None
    
    def update_behavior(self, item: OnsetOffsetItem):
        # we've updated the onset
        if item.n_onset is not None and item.n_onset != item.onset:
            # if the new onset is already in the dict, don't update the onset
            if item.n_onset in self.behavior_items.keys():
                item.n_onset = None
                raise ValueError("The onset is already in the dict")
            for other_onset, other_item in self.behavior_items.items():
                # skip the item we're updating
                if other_onset == item.onset:
                    continue
                # if our new onset is between the onset and offset of another item, don't update the onset
                if other_onset <= item.n_onset and other_item.offset >= item.n_onset+1:
                    item.n_onset = None
                    raise ValueError(
                        f"The provided onset time of {item.n_onset} overlaps with an existing range: {other_onset} - {other_item.offset}"
                    )
        # we've updated the offset
        if item.n_offset is not None and item.n_offset != item.offset:
            for other_onset, other_item in self.behavior_items.items():
                # skip the item we're updating
                if other_onset == item.onset:
                    continue
                # if our new offset is between the onset and offset of another item, don't update the offset
                if item.n_offset-1 >= other_onset and item.n_offset <= other_item.offset:
                    item.n_offset = None
                    raise ValueError(
                        f"The provided offset time of {item.n_offset} overlaps with an existing range: {other_onset} - {other_item.offset}"
                    )
        # if we've made it this far, we can update the onset and offset
        if item.n_onset is not None and item.n_onset != item.onset:
        # update our dict
            self.behavior_items[item.n_onset] = self.behavior_items.pop(item.onset)
            # update the onset
            item.onset = item.n_onset
            item.n_onset = None
        if item.n_offset is not None and item.n_offset != item.offset:
            # update the offset
            item.offset = item.n_offset
            item.n_offset = None


class TimelineView(QGraphicsView):
    valueChanged = Signal(int)
    frame_width_changed = Signal(int)
    def __init__(self, num_frames):
        super().__init__()
        # Set up the scene
        self.setScene(QGraphicsScene(self))
        self.setMouseTracking(True)
        self.value = 0 # Current frame
        self.base_frame_width = 50  # Base width for each frame
        self.frame_width = self.base_frame_width  # Current width for each frame
        self.num_frames = num_frames  # Total number of frames
        self.zoom_factor = 1.1  # Factor for zooming in and out
        self.scale_factor = 1.1  # Zoom factor for X-axis
        self.current_scale_x = 1  # Current scale on X-axis
        self.left_hand_margin = 20 # Left hand margin for the view
        
        self.playing = False  # Whether the mouse wheel is being used
        self.lmb_holding = False  # Whether the left mouse button is being held
        self.item_keys_to_hide: dict[int, 'BehaviorTrack'] = {} # A dict of key for the item to hide and the corresponding behavior track
        self.item_keys_to_render: dict[int, 'BehaviorTrack'] = {} # A dict of key for the item to render and the corresponding behavior track
        self.setSceneRect(0, 0, num_frames * self.frame_width, 60)  # Adjust the size as needed
        # Customize the view
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setRenderHints(QtGui.QPainter.RenderHint.Antialiasing)

        # Create and add the playhead
        self.playhead = CustomPlayhead(10, 0, 60, self.frame_width, self)  
        self.scene().addItem(self.playhead)
        self.playhead.triangle.signals.valueChanged.connect(self.valueChanged.emit)

        # add a track
        self.track_height = 50
        self.track_y_start = 50

        self.hover_line = QGraphicsLineItem(0, 0, 0, 0)

        ################ TEMP ################
        self.behavior_tracks: List[BehaviorTrack] = []
        self.add_behavior_track("test")

    def add_behavior_track(self, name: str):
        # add a new behavior track
        # get the y position of the new track
        y_pos = len(self.behavior_tracks) * self.track_height + self.track_y_start
        # create the new track
        track = BehaviorTrack("Test", y_pos+27, self.track_height, OnsetOffset, self)
        self.behavior_tracks.append(track)
        self.scene().addItem(track)
        # resize the view so that the track we can see the track
        self.resize(self.rect().width(), y_pos + self.track_height + 10)
        self.setMinimumSize(self.rect().width(), y_pos + self.track_height + 10)
        self.scene().update()
        
    def add_oo_behavior(self, onset):
        x = self.behavior_tracks[0].check_for_overlap(onset, onset+10)
        if x is None:
            self.behavior_tracks[0].add_behavior(onset)
            self.scene().update()
        else:
            # todo: add some notification that the behavior overlaps, maybe a red border around the offending item
            # x is the offending item
            x.setErrored()

    def set_length(self, length: int):
        self.num_frames = length
        self.setSceneRect(0, 0, length * self.frame_width, 60)
        self.playhead.setLine(0, self.mapToScene(0, 10).y(), 0, self.mapToScene(0, 0).y() + self.rect().height())
        self.playhead.triangle.setPos(self.playhead.triangle.boundingRect().width() / 2-11, self.mapToScene(0, 0).y()+ 20)
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        if self.num_frames > 100:
            self.base_frame_width = 50
            self.frame_width = 5
            self.frame_width_changed.emit(self.frame_width)
        self.scene().update()
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        pen = QPen(Qt.GlobalColor.gray, 1)
        painter.setPen(pen)

        left_start = rect.left()
        
        visible_left_frame = int(left_start / self.frame_width) + 1
        visible_right_frame = int(rect.right() / self.frame_width) + 1

        # Determine skip factor based on frame width
        skip_factor = max(1, int(self.base_frame_width / self.frame_width))
        self.tick_size = 20
        self.top_margin = 25
        self.tick_top = int(self.mapToScene(0, 0).y() + self.top_margin)
        self.tick_bottom = int(self.mapToScene(0, 0).y() + self.tick_size +self.top_margin)

        for i in range(max(0, visible_left_frame), min(visible_right_frame, self.num_frames)):
            if i == 1:
                x = int(i * self.frame_width)
                painter.drawLine(x, self.tick_top+5, x, self.tick_bottom-5)
            if i % skip_factor == 0:
                x = int(i * self.frame_width)
                painter.drawLine(x, self.tick_top, x, self.tick_bottom)
                rect = QRectF(x - 20, self.tick_bottom, 40, 20)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i))
            else:
                x = int(i * self.frame_width)
                painter.drawLine(x, self.tick_top+5, x, self.tick_bottom-5)

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
        right = int((self.mapToScene(self.rect().width(), 0).x() / self.frame_width) + 1)
        return left, right

    def move_playhead_to_frame(self, frame):
        # move the playhead to a specific frame
        self.playhead.setPos(abs(self.get_x_pos_of_frame(frame)), 0)
        self.playhead.triangle.current_frame = frame
        self.valueChanged.emit(frame)

    def wheelEvent(self, event):
        # if we're holding ctrl, zoom in or out
        if event.modifiers() == Qt.KeyboardModifier.AltModifier:
            self.zoomEvent(event)
        # otherwise, scroll left or right
        else:
            self.scrollEvent(event)

    def zoomEvent(self, event):
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
        # get the mouse position in the scene and scroll towards it
        mouse_pos = self.mapToScene(event.pos())
        # center the view on the mouse position but by a factor of the zoom
        self.centerOn(mouse_pos)
        # Redraw the scene to update the frame display
        # move the playhead to the current frame
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        # Redraw the scene to update the frame display
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

    def scroll_to_playhead(self):
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
            self.hover_line.setLine(snapped_x, self.mapToScene(0, 0).y(), snapped_x, self.mapToScene(0, 0).y() + 30)
            # set pen color to light gray
            pen = QPen(Qt.GlobalColor.lightGray, 1)
            self.hover_line.setPen(pen)
            self.hover_line.show()
        # if we're in the top 50 pixels and holding the left mouse button and the playhead triangle is not being hovered over, move the playhead to the current mouse position
        if self.lmb_holding and event.pos().y() < 50:
            # get the current position of the mouse
            mouse_pos = self.mapToScene(event.pos()).x()
            # get the current position of the view
            view_pos = self.horizontalScrollBar().value()
            # get the width of the view
            view_width = self.rect().width()
            if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
                # if we're holding shift, snap to the nearest behavior onset or offset if it's within 20 pixels
                if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                    # get the nearest behavior onset or offset
                    for key, track in self.item_keys_to_render.items():
                        behavior = track.behavior_items[key]
                        if abs(mouse_pos - self.get_x_pos_of_frame(behavior.onset)) < 20:
                            frame = behavior.onset
                            break
                        elif abs(mouse_pos - self.get_x_pos_of_frame(behavior.offset)) < 20:
                            frame = behavior.offset
                            break
                        else:
                            frame = int(mouse_pos / self.frame_width) + 1
                else:
                    frame = int(mouse_pos / self.frame_width) + 1
                self.playhead.triangle.pressed = True
                self.move_playhead_to_frame(frame)
                self.playhead.triangle.pressed = False

        self.scene().update()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        # if we're in the top 50 pixels, get the frame at the current mouse position and move the playhead to that frame
        if event.pos().y() < 50 and not self.lmb_holding:
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

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.scene().update()
        self.lmb_holding = False
        super().mouseReleaseEvent(event)
    
    def resizeEvent(self, event) -> None:
        self.playhead.triangle.setPos(self.playhead.triangle.boundingRect().width() / 2-11, self.mapToScene(0, 0).y()+ 20)
        self.playhead.setLine(0, self.mapToScene(0, 10).y(), 0, self.mapToScene(0, 0).y() + self.rect().height())
        self.hover_line.setLine(1, self.mapToScene(0, 0).y(), 1, self.mapToScene(0, 0).y() + 30)
        return super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        self.playhead.triangle.setPos(self.playhead.triangle.boundingRect().width() / 2-11, self.mapToScene(0, 0).y()+ 20)
        self.playhead.setLine(0, self.mapToScene(0, 10).y(), 0, self.mapToScene(0, 0).y() + self.rect().height())

        # if the playhead outside the view, scroll to it so it's visible
        if self.playhead.pos().x() < self.horizontalScrollBar().value() or self.playhead.pos().x() > self.horizontalScrollBar().value() + self.rect().width():
            if not self.playhead.triangle.pressed and self.playing:
                # scroll to the playhead
                self.scroll_to_playhead()

        # get the range of visible frames in the view
        l,r = self.get_visable_frames()
        for track in self.behavior_tracks:
            track.setRect(0, self.mapToScene(0,track.y_position).y(), self.mapToScene(0,0).x() + self.rect().width(), track.track_height)

            for item in track.behavior_items.values():
                if not item.pressed:
                    item.setPos(self.get_x_pos_of_frame(item.onset), self.mapToScene(0,track.y_position).y()+2)
                    item.setRect(0, 0, self.get_x_pos_of_frame(item.offset) - self.get_x_pos_of_frame(item.onset), track.track_height-4)

            ################################ LOD RENDERING ################################

            # get the list of items whos onset and item.offset fall outside the visible range
            self.item_keys_to_hide = {key:track for key in track.behavior_items.keys() if track.behavior_items[key].onset < l and track.behavior_items[key].offset > r}
            self.item_keys_to_render = {key:track for key in track.behavior_items.keys() if key >= l and key <= r}

            # ISSUE: zooming breaks this - items everywhere. 

            # hide the items that are not in the visible range
            # for item in track.behavior_items.values():
            #     if item in self.item_keys_to_hide.values():
            #         item.hide()
                    
            # # show the items that are in the visible range
            # for key in self.item_keys_to_render.keys():
            #     track.behavior_items[key].show()
            #     item = track.behavior_items[key]
            #     if not item.pressed:
            #         item.setPos(self.get_x_pos_of_frame(item.onset), self.mapToScene(0,track.y_position).y()+2)
            #         item.setRect(0, 0, self.get_x_pos_of_frame(item.offset) - self.get_x_pos_of_frame(item.onset), track.track_height-4)

        return super().paintEvent(event)

    def setValue(self, value):
        self.value = value
        self.update()

    def isPlayheadDown(self):
        return self.playhead.triangle.pressed

    def update(self):
        if self.value:
            self.playhead.triangle.current_frame = self.value
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        super().update()

class TimelineDockWidget(QtWidgets.QDockWidget):
    """This is the widget that contains the timeline, as a dockwidget for resizing. It cannot be closed or floated, only docked and resized"""
    
    def __init__(self, main_win: "MainWindow", parent=None):
            super(TimelineDockWidget, self).__init__(parent)
            self.setWindowTitle("Timeline")
            self.timeline_view = TimelineView(100)
            self.main_win = main_win
            self.setWidget(self.timeline_view)

    def set_length(self, length: int):
        self.timeline_view.set_length(length)
