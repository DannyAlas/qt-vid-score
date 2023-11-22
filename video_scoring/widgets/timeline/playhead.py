from qtpy.QtCore import Qt, QPointF, QObject, Signal
from qtpy.QtGui import QBrush, QColor, QPen, QPolygonF
from qtpy.QtWidgets import QGraphicsLineItem, QGraphicsPolygonItem
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineView

class playheadSignals(QObject):
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
