from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QMouseEvent, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)
from qtpy import QtCore, QtGui, QtWidgets


# an item that with a left and right circle and a rectangle that encompasses the both
class CustomGraphicsScrollBarHandle(QtWidgets.QGraphicsRectItem):
    def __init__(self, *args, **kwargs):
        super(CustomGraphicsScrollBarHandle, self).__init__(*args, **kwargs)
        # accept hover events
        self.setAcceptHoverEvents(True)
        # allow mouse tracking
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # cursur
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.unhovered_brush = QtGui.QBrush(QtGui.QColor("red"))
        self.hovered_brush = QtGui.QBrush(QtGui.QColor("blue"))
        self.left_hovered = False
        self.right_hovered = False
        self.left_edge = int(self.rect().left())
        self.right_edge = int(self.rect().right())
        self.top_edge = int(self.rect().top())
        self.bottom_edge = int(self.rect().bottom())
        self.v_center = int((self.top_edge + self.bottom_edge) / 2)
        self.last_pos = None

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        pos = event.pos()
        if (
            pos.x() >= self.left_edge
            and pos.x() <= self.left_edge + 10
            and pos.y() >= self.top_edge
            and pos.y() <= self.bottom_edge
        ):
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            self.left_hovered = True
            self.right_hovered = False
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        elif (
            pos.x() >= self.right_edge - 10
            and pos.x() <= self.right_edge
            and pos.y() >= self.top_edge
            and pos.y() <= self.bottom_edge
        ):
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            self.right_hovered = True
            self.left_hovered = False
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
        else:
            self.right_hovered = False
            self.left_hovered = False
            self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        return super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        self.left_hovered = False
        self.right_hovered = False
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        return super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        pos = event.pos()
        print(pos.x(), pos.y())
        if (
            pos.x() >= self.left_edge
            and pos.x() <= self.left_edge + 10
            and pos.y() >= self.top_edge
            and pos.y() <= self.bottom_edge
        ):
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            self.left_hovered = True
            self.right_hovered = False
        elif (
            pos.x() >= self.right_edge - 10
            and pos.x() <= self.right_edge
            and pos.y() >= self.top_edge
            and pos.y() <= self.bottom_edge
        ):
            self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            self.right_hovered = True
            self.left_hovered = False
        else:
            self.right_hovered = False
            self.left_hovered = False
            self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.update()
        return super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.last_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        # if we're hovering over the left edge, move the left edge, keep the right edge in place
        # if we're hovering over the right edge, move the right edge, keep the left edge in place
        if self.left_hovered:
            self.setRect(
                event.pos().x(),
                self.top_edge,
                self.right_edge - event.pos().x(),
                self.bottom_edge - self.top_edge,
            )
        elif self.right_hovered:
            self.setRect(
                self.left_edge,
                self.top_edge,
                event.pos().x() - self.left_edge,
                self.bottom_edge - self.top_edge,
            )
        # else only move horizontally, using the last position as a reference
        else:
            self.setRect(
                self.rect().left() + event.pos().x() - self.last_pos.x(),
                self.top_edge,
                self.right_edge - self.left_edge,
                self.bottom_edge - self.top_edge,
            )
        self.last_pos = event.pos()
        self.update()

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = ...,
    ) -> None:
        # don't draw our rectangle
        painter.setPen(QtGui.QPen(QtGui.QColor("transparent")))
        painter.setBrush(QtGui.QBrush(QtGui.QColor("transparent")))
        painter.drawRect(self.rect())

        # draw the left and right circles and the middle rectangle
        self.left_edge = int(self.rect().left())
        self.right_edge = int(self.rect().right())
        self.top_edge = int(self.rect().top())
        self.bottom_edge = int(self.rect().bottom())
        self.v_center = int((self.top_edge + self.bottom_edge) / 2)
        self.h_center = int((self.left_edge + self.right_edge) / 2)
        self.x_rad = int((self.right_edge - self.left_edge) / 2)
        self.y_rad = int((self.bottom_edge - self.top_edge) / 2)

        painter.setBrush(QtGui.QBrush(QtGui.QColor("red")))
        # draw us a rect with rounded corners
        painter.drawRoundedRect(self.rect(), 15, 15)
        if self.left_hovered:
            painter.setBrush(QtGui.QBrush(QtGui.QColor("blue")))
        else:
            painter.setBrush(QtGui.QBrush(QtGui.QColor("black")))
        # center vertically on the left edge
        painter.drawEllipse(QtCore.QPoint(self.left_edge + 15, self.v_center), 5, 5)
        if self.right_hovered:
            painter.setBrush(QtGui.QBrush(QtGui.QColor("blue")))
        else:
            painter.setBrush(QtGui.QBrush(QtGui.QColor("black")))
        # center vertically on the right edge
        painter.drawEllipse(QtCore.QPoint(self.right_edge - 15, self.v_center), 5, 5)


class CustomGraphicsScrollBar(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super(CustomGraphicsScrollBar, self).__init__(*args, **kwargs)
        self.setScene(QGraphicsScene(self))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setMouseTracking(True)
        # Define the handle
        self.handle = CustomGraphicsScrollBarHandle()
        self.handle.setRect(0, 0, 100, 20)
        self.handle.setBrush(QtGui.QBrush(QtGui.QColor("red")))
        self.scene().addItem(self.handle)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        print("mouse pressed")
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        print("mouse released")
        super().mouseReleaseEvent(event)


if __name__ == "__main__":
    app = QApplication([])
    scrollBar = CustomGraphicsScrollBar()
    scrollBar.show()
    app.exec()
