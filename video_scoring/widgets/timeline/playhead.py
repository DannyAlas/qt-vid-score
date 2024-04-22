from typing import TYPE_CHECKING

from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QStyleOptionGraphicsItem, QWidget
from qtpy.QtCore import QObject, QPointF, Qt, Signal
from qtpy.QtGui import QBrush, QColor, QPen, QPolygonF
from qtpy.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsPolygonItem

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineView


class playheadSignals(QObject):
    valueChanged = Signal(int)


class DraggableTriangle(QGraphicsPolygonItem):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = playheadSignals()
        # Define the shape as a pentagon
        self.setPolygon(
            QPolygonF(
                [
                    QPointF(-7, -15),
                    QPointF(7, -15),
                    QPointF(7, -5),
                    QPointF(0, 0),
                    QPointF(-7, -5),
                ]
            )
        )
        self.base_color = QColor("#6aa1f5")
        self.hovered_color = QColor("#a7c8f2")
        self.active_behavior_color = QColor("#f56a6a")
        self.setBrush(QBrush(self.base_color))
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._current_frame = 0
        self.pressed = False

    @property
    def current_frame(self):
        return self._current_frame

    @current_frame.setter
    def current_frame(self, value):
        self._current_frame = value

    def mousePressEvent(self, event):
        self.pressed = True
        super().mousePressEvent(event)

    def hoverEnterEvent(self, event):
        # lighten the color of the playhead
        self.setBrush(QBrush(self.hovered_color))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        # restore the color of the playhead
        self.setBrush(QBrush(self.base_color))
        super().hoverLeaveEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        super().mouseReleaseEvent(event)


class Playhead(QGraphicsLineItem):
    def __init__(self, x, y, height, frame_width, tl: "TimelineView"):
        super().__init__(0, y, 0, y + height + 10)
        self.frame_width = frame_width
        self.tl = tl
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setZValue(1000)
        # Create the triangle and set it as a child of the line
        self.current_frame = 0
        self.triangle = DraggableTriangle(self)
        self.triangle.setPos(0, y + height + 10)
        # don't draw the line
        pen = QPen(Qt.GlobalColor.transparent, 2)
        self.setPen(pen)

    def updateFrameWidth(self, new_width):
        self.frame_width = new_width


class PlayheadLine(QGraphicsLineItem):
    def __init__(self, x, y, height, frame_width, tl: "TimelineView"):
        super().__init__(0, y, 0, y + height + 10)
        self.frame_width = frame_width
        self.tl = tl
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable, False)
        # set color
        pen = QPen(Qt.GlobalColor.black, 2)
        self.setPen(pen)
        self.setZValue(1000)
        self._current_frame = 0

    @property
    def current_frame(self):
        return self._current_frame

    @current_frame.setter
    def current_frame(self, value):
        self._current_frame = value
