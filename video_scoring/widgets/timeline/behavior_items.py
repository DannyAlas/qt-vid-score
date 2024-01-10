from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen
from qtpy.QtWidgets import (QGraphicsItem, QGraphicsRectItem,
                            QGraphicsSceneHoverEvent, QGraphicsSceneMouseEvent,
                            QMenu, QStyleOptionGraphicsItem, QWidget)

from video_scoring.widgets.timeline.commands import OnsetOffsetMoveCommand

if TYPE_CHECKING:
    from qtpy.QtCore import QPointF

    from video_scoring import MainWindow
    from video_scoring.widgets.timeline.timeline import TimelineView
    from video_scoring.widgets.timeline.track import BehaviorTrack


class OnsetOffsetItemSignals(QObject):
    unhighlight_sig = Signal()


class OnsetOffsetItem(QGraphicsRectItem):
    """
    This will be a behavior item that has onset and offset times
    It's edges will be draggable to change the onset and offset times
    Grabbing the middle will move the whole thing
    """

    def __init__(
        self,
        onset: int,
        offset: int,
        unsure: bool,
        view: "TimelineView",
        parent: "BehaviorTrack" = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.view = view

        # DO NOT MODIFY THESE DIRECTLY
        self._onset: int = onset
        self._offset: int = offset
        self.unsure: bool = unsure

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
        self.base_color = QColor(self.parent.item_color)
        self.setBrush(QBrush(self.base_color))
        self.highlight_color = self.base_color.lighter(110)
        self.setToolTip(
            f"{self.onset} - {self.offset} - {['Sure', 'Unsure'][self.unsure]}"
        )

    # TODO: is there a reason we don't use the built in setters/getters? Fix this if not
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

    def get_context_menu(self) -> QMenu:
        """
        Returns a context menu for the behavior item

        Parameters
        ----------
        event : QMouseEvent
            The mouse event that triggered the context menu
        """
        menu = QMenu()
        if self.unsure:
            unsure_action = menu.addAction("Set Sure")
            unsure_action.triggered.connect(lambda: self.parent.set_unsure(self, False))
            unsure_action.triggered.connect(menu.close)
        else:
            unsure_action = menu.addAction("Set Unsure")
            unsure_action.triggered.connect(lambda: self.parent.set_unsure(self, True))
            unsure_action.triggered.connect(menu.close)
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(
            lambda: self.view.delete_oo_behavior(onset=self.onset, track=self.parent)
        )
        return menu

    def update_tooltip(self):
        self.setToolTip(
            f"{self.onset} - {self.offset} - {['Sure', 'Unsure'][self.unsure]}"
        )

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
        self.update()

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
            # subtract the current x position to convert to local x position
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
        n_offset = int(
            round(self.mapToScene(QPointF(event.pos())).x() / self.view.frame_width)
        )

        if self.parent.overlap_with_item_check(self, offset=n_offset):
            self.setRect(
                self.rect().left(), self.rect().top(), old_width, self.rect().height()
            )
        else:
            self.set_offset(new_offset=n_offset)
        self.update()

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
        self.view.main_window.timestamps_dw.refresh()
        self.update_tooltip()

    def set_offset(self, new_offset: int):
        """
        Set the offset of the behavior item.

        Parameters
        ----------
        new_offset : int
            The new offset value
        """
        if new_offset < self.onset + 1:
            return
        self._offset = new_offset
        self.view.main_window.timestamps_dw.update()
        self.update_tooltip()

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

    def set_unsure(self, unsure: bool):
        """
        Set the unsure status of the behavior item.

        Parameters
        ----------
        unsure : bool
            The new unsure value
        """
        self.unsure = unsure
        self.update_tooltip()
        self.update()

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
                self.hover_left_edge = True
                self.right_edge_grabbed = False
                self.hover_right_edge = False
                self.update()
            else:
                self.left_edge_grabbed = False
                self.hover_left_edge = False
                self.right_edge_grabbed = True
                self.hover_right_edge = True
                self.update()
        elif (
            event.pos().x() <= self.edge_grab_boundary + self.extend_edge_grab_boundary
            and not event.pos().x()
            >= self.rect().width()
            - self.edge_grab_boundary
            - self.extend_edge_grab_boundary
        ):
            self.left_edge_grabbed = True
            self.hover_left_edge = True
            self.right_edge_grabbed = False
            self.hover_right_edge = False
            self.update()
        elif (
            event.pos().x()
            >= self.rect().width()
            - self.edge_grab_boundary
            - self.extend_edge_grab_boundary
            and not event.pos().x()
            <= self.edge_grab_boundary + self.extend_edge_grab_boundary
        ):
            self.left_edge_grabbed = False
            self.hover_left_edge = False
            self.right_edge_grabbed = True
            self.hover_right_edge = True
            self.update()
        else:
            self.left_edge_grabbed = False
            self.hover_left_edge = False
            self.right_edge_grabbed = False
            self.hover_right_edge = False
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.pressed = False
        if (
            self.cur_move_command.undo_onset != self.onset
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
        if self.rect().width() < 10:
            if event.pos().x() <= self.rect().width() / 2:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.hover_left_edge = True
                self.hover_right_edge = False
                self.update()
            elif event.pos().x() >= self.rect().width() / 2:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                self.hover_left_edge = False
                self.hover_right_edge = True
                self.update()

        elif (
            event.pos().x() <= self.edge_grab_boundary + self.extend_edge_grab_boundary
            and not event.pos().x()
            >= self.rect().width()
            - self.edge_grab_boundary
            - self.extend_edge_grab_boundary
        ):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.hover_left_edge = True
            self.hover_right_edge = False
            self.update()
        elif (
            event.pos().x()
            >= self.rect().width()
            - self.edge_grab_boundary
            - self.extend_edge_grab_boundary
            and not event.pos().x()
            <= self.edge_grab_boundary + self.extend_edge_grab_boundary
        ):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.hover_right_edge = True
            self.hover_left_edge = False
            self.update()
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.hover_left_edge = False
            self.hover_right_edge = False
            self.update()
        return super().hoverMoveEvent(event)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setPen(Qt.GlobalColor.transparent)
        painter.setBrush(QBrush(self.base_color))
        painter.drawRect(self.rect())
        edge_color = self.highlight_color.lighter(150)
        if self.isSelected():
            pen = QPen(Qt.GlobalColor.lightGray, 2)
            painter.setPen(pen)
            painter.drawRect(self.rect())
        if self.hovered or self.hover_left_edge or self.hover_right_edge:
            pen = QPen(Qt.GlobalColor.lightGray, 3)
            painter.setPen(pen)
            painter.drawRect(self.rect())
        if self.hover_left_edge:
            pen = QPen(edge_color, 3)
            painter.setPen(pen)
            painter.setBrush(QBrush(edge_color))
            painter.drawLine(
                int(self.rect().left()) + 1,
                2,
                int(self.rect().left()) - 1,
                int(self.rect().height()) - 2,
            )
        elif self.hover_right_edge:
            pen = QPen(edge_color, 3)
            painter.setPen(pen)
            painter.setBrush(QBrush(edge_color))
            painter.drawLine(
                int(self.rect().width()),
                2,
                int(self.rect().width()),
                int(self.rect().height()) - 2,
            )
        if self.unsure:
            pen = QPen(Qt.GlobalColor.yellow, 3)
            painter.setPen(pen)
            painter.drawRect(self.rect())

    def save(self):
        return {
            "onset": self.onset,
            "offset": self.offset,
        }
