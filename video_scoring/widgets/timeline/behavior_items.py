from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, QRectF, Qt, QTimer, Signal, QPointF
from qtpy.QtGui import QBrush, QColor, QPainter, QPen, QMouseEvent
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from video_scoring.command_stack import Command

if TYPE_CHECKING:
    from qtpy.QtCore import QPointF

    from video_scoring import MainWindow
    from video_scoring.widgets.timeline.timeline import TimelineView
    from video_scoring.widgets.timeline.track import BehaviorTrack


class OnsetOffsetMoveCommand(Command):
    """
    Implements a command for undo/redo functionality of onset/offset changes. The command will store the onset and offset for the undo and redo actions.

    Parameters
    ----------
    undo_onset : int
        The onset frame for the undo action
    undo_offset : int
        The offset frame for the undo action
    redo_onset : int
        The onset frame for the redo action
    redo_offset : int
        The offset frame for the redo action
    item : OnsetOffsetItem
        The item that the command is associated with
    """

    def __init__(
        self, undo_onset, undo_offset, redo_onset, redo_offset, item: "OnsetOffsetItem"
    ):
        self.undo_onset = undo_onset
        self.undo_offset = undo_offset
        self.redo_onset = redo_onset
        self.redo_offset = redo_offset
        self.item = item

    def undo(self):
        self.item.set_onset_offset(self.undo_onset, self.undo_offset)
        self.item.update()
        self.item.scene().update()

    def redo(self):
        self.item.set_onset_offset(self.redo_onset, self.redo_offset)
        self.item.update()
        self.item.scene().update()


class OnsetOffsetItemSignals(QObject):
    unhighlight_sig = Signal()


class OnsetOffsetItem(QGraphicsRectItem):
    """
    This will be a behavior item that has onset and offset times
    It's edges will be draggable to change the onset and offset times
    Grabbing the middle will move the whole thing
    """

    def __init__(
        self, onset, offset, view: "TimelineView", parent: "BehaviorTrack" = None
    ):
        super().__init__(parent)
        self.parent = parent
        self.view = view

        # DO NOT MODIFY THESE DIRECTLY
        self._onset: int = onset
        self._offset: int = offset

        self.signals = OnsetOffsetItemSignals()
        self.pressed = False
        self.last_mouse_pos = None
        self.left_edge_grabbed = False
        self.right_edge_grabbed = False
        self.hovered = False
        self.hover_left_edge = False
        self.hover_right_edge = False
        self.edge_grab_boundary = 8
        self.extend_edge_grab_boundary = 8
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setAcceptHoverEvents(True)
        self.signals.unhighlight_sig.connect(self.unhighlight)
        # set geometry
        self.base_color = QColor("#6aa1f5")
        self.setBrush(QBrush(self.base_color))
        self.highlight_color = QColor("#8cbdfa")

    @property
    def onset(self):
        """
        WARNING DO NOT MODIFY THIS DIRECTLY. Use the `set_onset` method to update this value
        """
        return self._onset

    @property
    def offset(self):
        """
        WARNING DO NOT MODIFY THIS DIRECTLY. Use the `set_offset` method to update this value
        """
        return self._offset

    def _drag_left_edge(self, event: QGraphicsSceneMouseEvent) -> None:
        scene_x: QPointF = self.mapToScene(
            QPointF(event.pos()) - self.last_mouse_pos
        ).x()
        nearest_frame = self.view.get_frame_of_x_pos(scene_x)

        # Ensure the onset is not before the beginning of the video
        if scene_x < 0:
            return

        # Ensure onset frame does not exceed offset frame
        if nearest_frame >= self.offset:
            return

        # Get the x position of the nearest frame in local coordinates (by subtracting the current x position)
        snapped_x_local = (
            round(scene_x / self.view.frame_width) * self.view.frame_width
        ) - self.pos().x()
        new_width = self.rect().right() - snapped_x_local  # Calculate the new width

        # save the old position
        old_x_local = self.rect().left()
        old_width = self.rect().width()

        # Set the new position and size of the rectangle, and update the n_onset frame
        self.setRect(
            snapped_x_local, self.rect().top(), new_width, self.rect().height()
        )
        n_onset = self.view.get_frame_of_x_pos(
            self.mapToScene(self.rect().left(), 0).x()
        )

        # if we overlap with another item, revert the change
        if self.parent.overlap_with_item_check(self, onset=n_onset):
            self.setRect(
                old_x_local, self.rect().top(), old_width, self.rect().height()
            )
        # otherwise, update the behavior
        else:
            self.set_onset(new_onset=n_onset)

    def _drag_right_edge(self, event: QGraphicsSceneMouseEvent) -> None:
        new_width = (
            round(
                # get the x position of the mouse in the scene, but don't let it exceed the right edge of the scene
                min(
                    self.mapToScene(QPointF(event.pos())).x(),
                    self.view.sceneRect().right(),
                )
                # Snap the x position to the nearest frame by dividing by the frame width,
                # rounding to the nearest frame, then multiplying by the frame width
                / self.view.frame_width
            )
            * self.view.frame_width
            # subtract the current x position to get convert to local x position
            - self.pos().x()
        )

        # Finally, subtract the left edge of the rectangle to get the new width in local coordinates
        -self.rect().left()

        if new_width < 1:
            return

        old_width = self.rect().width()

        self.setRect(
            self.rect().left(), self.rect().top(), new_width, self.rect().height()
        )
        n_offset = (
            int(self.mapToScene(QPointF(event.pos())).x() / self.view.frame_width) + 1
        )

        if self.parent.overlap_with_item_check(self, offset=n_offset):
            self.setRect(
                self.rect().left(), self.rect().top(), old_width, self.rect().height()
            )
        else:
            self.set_offset(new_offset=n_offset)

    def _drag_item(self, event: QGraphicsSceneMouseEvent) -> None:
        scene_x: QPointF = self.mapToScene(
            QPointF(event.pos()) - self.last_mouse_pos
        ).x()
        new_x = self.view.get_x_pos_of_frame(self.view.get_frame_of_x_pos(scene_x))

        if new_x < 0:
            new_x = 0

        old_x = self.pos().x()

        self.setPos(new_x, self.pos().y())
        n_onset = self.view.get_frame_of_x_pos(
            self.mapToScene(self.rect().left(), 0).x()
        )
        n_offset = self.view.get_frame_of_x_pos(
            self.mapToScene(self.rect().right(), 0).x()
        )

        if self.parent.overlap_with_item_check(self, onset=n_onset, offset=n_offset):
            self.setPos(old_x, self.pos().y())
        else:
            self.set_onset(new_onset=n_onset)
            self.set_offset(new_offset=n_offset)

    def set_onset(self, new_onset: int):
        """
        Set the onset of the behavior item. This will manage syncing the onset with the parent track

        Parameters
        ----------
        new_onset : int
            The new onset value
        """
        self.parent.update_behavior_onset(self, new_onset)
        self._onset = new_onset
        self.parent.parent.parent.main_win.timestamps_dw.update()

    def set_offset(self, new_offset: int):
        """
        Set the offset of the behavior item.

        Parameters
        ----------
        new_offset : int
            The new offset value
        """
        self._offset = new_offset
        self.parent.parent.parent.main_win.timestamps_dw.update()

    def set_onset_offset(self, new_onset: int, new_offset: int):
        """
        Set the onset and offset of the behavior item.

        Parameters
        ----------
        new_onset : int
            The new onset value
        new_offset : int
            The new offset value
        """
        self.set_onset(new_onset)
        self.set_offset(new_offset)

    def highlight(self):
        self.setBrush(QBrush(self.highlight_color))

    def unhighlight(self):
        self.setBrush(QBrush(self.base_color))

    def errorHighlight(self):
        self.setBrush(QBrush(QColor("#ff0000")))

    def setErrored(self):
        # will set the error highlight for a short time
        self.errorHighlight()
        QTimer.singleShot(300, self.unhighlight)

    def mousePressEvent(self, event):
        # Handle mouse press events
        self.pressed = True
        self.setSelected(True)
        self.last_mouse_pos = event.pos()
        cur_onset = self.onset
        cur_offset = self.offset
        self.cur_move_command = OnsetOffsetMoveCommand(
            cur_onset, cur_offset, cur_onset, cur_offset, self
        )
        # if its we're smaller than 10 pixels, determine which edge we're closest to by dividing the width by 2
        if self.rect().width() < 10:
            if event.pos().x() <= self.rect().width() / 2:
                self.left_edge_grabbed = True
                self.right_edge_grabbed = False
            else:
                self.left_edge_grabbed = False
                self.right_edge_grabbed = True
        elif (
            event.pos().x() <= self.edge_grab_boundary + self.extend_edge_grab_boundary
        ):
            self.left_edge_grabbed = True
            self.right_edge_grabbed = False
        elif (
            event.pos().x()
            >= self.rect().width()
            - self.edge_grab_boundary
            - self.extend_edge_grab_boundary
        ):
            self.left_edge_grabbed = False
            self.right_edge_grabbed = True
        else:
            self.left_edge_grabbed = False
            self.right_edge_grabbed = False

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        if (
            self.cur_move_command.undo_offset != self.onset
            or self.cur_move_command.undo_offset != self.offset
        ):
            self.cur_move_command.redo_onset = self.onset
            self.cur_move_command.redo_offset = self.offset
            self.parent.parent.parent.main_win.command_stack.add_command(
                self.cur_move_command
            )
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.pressed:
            # set our z value to be on top of everything except the playhead
            self.setZValue(999)
            if self.left_edge_grabbed:
                self._drag_left_edge(event)
            elif self.right_edge_grabbed:
                self._drag_right_edge(event)
            else:
                self._drag_item(event)

        self.setZValue(10)
        self.scene().update()

    def hoverEnterEvent(self, event):
        # lighten the color fill of the rectangle
        self.highlight()
        self.hovered = True
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
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
        elif (
            event.pos().x()
            >= self.rect().width()
            - self.edge_grab_boundary
            - self.extend_edge_grab_boundary
        ):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.hover_right_edge = True
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.hover_left_edge = False
            self.hover_right_edge = False
        return super().hoverMoveEvent(event)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        # make a light gray pen with rounded edges
        if self.hovered:
            pen = QPen(Qt.GlobalColor.lightGray, 1)
            painter.setPen(pen)
            # add a border around the rectangle with no fill
            border = QRectF(
                self.rect().left(),
                self.rect().top(),
                self.rect().width(),
                self.rect().height(),
            )
            painter.drawRect(border)
        if self.hover_left_edge:
            pen = QPen(Qt.GlobalColor.lightGray, 3)
            painter.setPen(pen)
            # plce the line on the left edge but offset by 1 pixel so that it doesn't get cut off
            painter.drawLine(
                int(self.rect().left()) - 1,
                2,
                int(self.rect().left()) - 1,
                int(self.rect().height()) - 2,
            )
        elif self.hover_right_edge:
            pen = QPen(Qt.GlobalColor.lightGray, 3)
            painter.setPen(pen)
            painter.drawLine(
                int(self.rect().width()),
                2,
                int(self.rect().width()),
                int(self.rect().height()) - 2,
            )
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
