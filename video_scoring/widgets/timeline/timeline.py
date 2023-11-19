from re import T
from PyQt6 import QtCore, QtGui
from qtpy.QtWidgets import QGraphicsRectItem, QGraphicsItemGroup, QGraphicsItem, QGraphicsSceneDragDropEvent, QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent, QGraphicsView, QGraphicsScene, QGraphicsLineItem, QGraphicsPolygonItem, QMainWindow, QStyleOptionGraphicsItem, QWidget, QSizePolicy
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt, QRectF, QPointF, Signal
from qtpy.QtGui import QColor, QPen, QBrush, QPolygonF
from typing import TYPE_CHECKING, Union, Optional

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

class OOBehaviorItem(QGraphicsRectItem):
    """
    This will be a behavior item that has onset and offset times
    It's edges will be draggable to change the onset and offset times
    Grabbing the middle will move the whole thing
    """
    def __init__(self, onset, offset, view: 'TimelineView', parent: 'Track'=None):
        super(QGraphicsRectItem, self).__init__(QRectF(10 + 50, 10, 30, 30))
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable, False)  
        self.parent = parent
        self.view = view
        self.onset = onset
        self.offset = offset
        
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.pressed = False
        self.setBrush(QBrush(QColor("#6aa1f5")))
        self.acceptHoverEvents()
        self.setRect(QRectF(0, self.view.mapToScene(0, self.parent.y_position).y() + 25+2, self.view.get_x_pos_of_frame(self.offset) - self.view.get_x_pos_of_frame(self.onset), self.parent.track_height-4))
        self.left_edge_grabbed = False
        self.right_edge_grabbed = False

    def setPos(self, x, y):
        # Snap to the nearest frame
        snapped_x = round(x / self.view.frame_width) * self.view.frame_width
        super().setPos(snapped_x, y)

    def mousePressEvent(self, event):
        # Handle mouse press events
        self.pressed = True
        if event.pos().x() <= 5:
            self.left_edge_grabbed = True
        elif event.pos().x() >= self.rect().width() - 5:
            self.right_edge_grabbed = True
        else:
            self.left_edge_grabbed = False
            self.right_edge_grabbed = False

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.pressed:
            if self.left_edge_grabbed:
                # get the current position of the mouse
                mouse_pos = self.mapToScene(event.pos())
                # move the left edge of the rectangle to the mouse position
                print(mouse_pos.x())
            elif self.right_edge_grabbed:
                # get the current position of the mouse
                mouse_pos = self.mapToScene(event.pos())
                # move the right edge of the rectangle to the mouse position
                print(mouse_pos.x())
            else:
                # get the current position of the mouse
                mouse_pos = self.mapToScene(event.pos())
                # mouse pos - offset of the item
                self.setPos(mouse_pos.x() - self.rect().width() / 2, 0)
            

        super().mouseMoveEvent(event)

    def hoverEnterEvent(self, event):
        # lighten the color fill of the rectangle
        self.setBrush(QBrush(QColor("#a7c8f2")))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # restore the color of the playhead
        self.setBrush(QBrush(QColor("#6aa1f5")))
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        if event.pos().x() <= 5:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif event.pos().x() >= self.rect().width() - 5:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        return super().hoverMoveEvent(event)
    

    def mouseReleaseEvent(self, event):
        self.pressed = False
        super().mouseReleaseEvent(event)

    def paint(self, painter: QtGui.QPainter, option: 'QStyleOptionGraphicsItem', widget: Optional[QWidget] = ...) -> None:
        # draw a rectangle
        self.setRect(QRectF(0, self.view.mapToScene(0, self.parent.y_position).y() + 25+2, self.view.get_x_pos_of_frame(self.offset) - self.view.get_x_pos_of_frame(self.onset), self.parent.track_height-4))
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())

class Track(QGraphicsItem):
    def __init__(self, y_position, track_height, parent:'TimelineView'=None):
        super(Track, self).__init__()
        self.parent = parent
        self.y_position = y_position
        self.track_height = track_height
        self.acceptHoverEvents()
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.behaviors = []
        
    def boundingRect(self):
        y1 = self.parent.mapToScene(0, self.y_position).y() + 25
        x2 = self.parent.mapToScene(self.parent.rect().width(), 0).x()
        return QRectF(0, y1, x2, self.track_height)

    def paint(self, painter: QtGui.QPainter, option: 'QStyleOptionGraphicsItem', widget: Optional[QWidget] = ...) -> None:
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(QBrush(Qt.GlobalColor.gray))
        painter.drawRect(self.boundingRect())

class TimelineView(QGraphicsView):
    valueChanged = Signal(int)
    frame_width_changed = Signal(int)
    def __init__(self, num_frames):
        super().__init__()
        # Set up the scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.value = 0 # Current frame
        self.base_frame_width = 50  # Base width for each frame
        self.frame_width = self.base_frame_width  # Current width for each frame
        self.num_frames = num_frames  # Total number of frames
        self.zoom_factor = 1.1  # Factor for zooming in and out
        self.scale_factor = 1.1  # Zoom factor for X-axis
        self.current_scale_x = 1  # Current scale on X-axis
        self.playing = False  # Whether the mouse wheel is being used
        self.lmb_holding = False  # Whether the left mouse button is being held
        self.setSceneRect(0, 0, num_frames * self.frame_width, 60)  # Adjust the size as needed

        # Customize the view
        self.setInteractive(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Create and add the playhead
        self.playhead = CustomPlayhead(10, 0, 60, self.frame_width, self)  
        self.scene.addItem(self.playhead)
        self.playhead.triangle.signals.valueChanged.connect(self.valueChanged.emit)

        # add a track
        track_height = 50
        track_y_start = 50
        self.track = Track(track_y_start, track_height, self)
        self.scene.addItem(self.track)
        # resize the view so that the track we can see the track
        self.resize(self.rect().width(), track_y_start + track_height + 10)
        self.setMinimumSize(self.rect().width(), track_y_start + track_height + 10)
        b = OOBehaviorItem(10, 20, self, self.track)
        self.scene.addItem(b)

        self.hover_line = QGraphicsLineItem(1, self.mapToScene(0, 0).y(), 1, self.mapToScene(0, 0).y() + 30)
        self.scene.addItem(self.hover_line)

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
        self.scene.update()
    
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        pen = QPen(Qt.GlobalColor.gray, 1)
        painter.setPen(pen)
        # draw a black border around the view
        visible_left = int(rect.left() / self.frame_width)
        visible_right = int(rect.right() / self.frame_width) + 1

        # Determine skip factor based on frame width
        skip_factor = max(1, int(self.base_frame_width / self.frame_width))
        tick_size = 20
        top_margin = 25
        tick_top = int(self.mapToScene(0, 0).y() + top_margin)
        tick_bottom = int(self.mapToScene(0, 0).y() + tick_size + top_margin)
        for i in range(max(0, visible_left), min(visible_right, self.num_frames)):
            if i % skip_factor == 0:
                x = int(i * self.frame_width)
                painter.drawLine(x, tick_top, x, tick_bottom)
                rect = QRectF(x - 20, tick_bottom, 40, 20)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))
            else:
                x = int(i * self.frame_width)
                painter.drawLine(x, tick_top+5, x, tick_bottom-5)

    def get_playhead_frame(self):
        # get the current frame the playhead is on
        return int(self.playhead.pos().x() / self.frame_width)

    def get_x_pos_of_frame(self, frame):
        # get the position of a frame
        return frame * self.frame_width

    def move_playhead_to_frame(self, frame):
        # move the playhead to a specific frame
        self.playhead.setPos(abs(self.get_x_pos_of_frame(frame-1)), 0)
        self.playhead.triangle.current_frame = frame
        self.valueChanged.emit(frame)

    def wheelEvent(self, event):
        # if we're holding ctrl, zoom in or out
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.zoomEvent(event)
        # otherwise, scroll left or right
        else:
            self.scrollEvent(event)

    def zoomEvent(self, event):
        # Zoom in or out by changing the frame width
        if event.angleDelta().y() > 0:
            # Zoom in (increase frame width)
            # but if we're zoomed in too far, don't zoom in
            if self.frame_width < self.base_frame_width * 10:
                self.frame_width *= self.zoom_factor
        elif event.angleDelta().y() < 0:
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
        self.centerOn(mouse_pos/self.scale_factor)
        # Redraw the scene to update the frame display
        # move the playhead to the current frame
        self.move_playhead_to_frame(self.playhead.triangle.current_frame)
        # Redraw the scene to update the frame display
        self.scene.update()

    def scrollEvent(self, event):
        # Scroll left or right by changing the scene position
        if event.angleDelta().y() > 0:
            # Scroll left
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - 10)
        elif event.angleDelta().y() < 0:
            # Scroll right
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + 10)
        self.scene.update()

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
        # if we're in the top 30 pixels, add a vertical line spanning the top 30 pixels at the current mouse position
        
        mouse_pos = self.mapToScene(event.pos()).x()
        # get the current position of the view
        view_pos = self.horizontalScrollBar().value()
        # get the width of the view
        view_width = self.rect().width()
        if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
            # get the current position of the mouse
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
            # if the mouse is within the view, draw a vertical line
            if mouse_pos >= view_pos and mouse_pos <= view_pos + view_width:
                frame = int(mouse_pos / self.frame_width) + 1
                self.playhead.triangle.pressed = True
                self.move_playhead_to_frame(frame)
                self.playhead.triangle.pressed = False

        self.scene.update()
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
                self.move_playhead_to_frame(frame)
        self.lmb_holding = True

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.scene.update()
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
        for item in self.scene.items():
            item.update()
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
