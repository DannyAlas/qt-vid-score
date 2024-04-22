from email.charset import QP
from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QBrush, QColor, QMouseEvent, QPainter, QPen, QPolygonF
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsPolygonItem,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QMenu,
    QStyleOptionGraphicsItem,
    QWidget,
)

from video_scoring.widgets.timeline.commands import FlagMoveCommand

if TYPE_CHECKING:
    from qtpy.QtCore import QPointF

    from video_scoring import MainWindow
    from video_scoring.widgets.timeline.ruler import TimelineRulerView
    from video_scoring.widgets.timeline.timeline import TimelineView


class FlagItem(QGraphicsPolygonItem):
    """
    Represents a flag on the ruler that has an
    """

    def __init__(
        self,
        frame: int,
        name: str,
        color: QColor,
        tview: "TimelineView",
        rview: "TimelineRulerView",
        parent=None,
    ):
        super().__init__()
        self.timeline_view = tview
        self.ruler_view = rview
        self.main_win = self.timeline_view.main_window

        # DO NOT MODIFY THESE DIRECTLY
        self._frame: int = frame
        self.name: str = name
        if self.name is None:
            self.name = "Flag"
        self.hovered = False
        self.edge_grab_boundary = 8
        self.extend_edge_grab_boundary = 8
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.setAcceptHoverEvents(True)
        self.setOpacity(0.1)
        # set geometry to be a triangle pointing down
        self.height = 10
        self.width = 10
        self.setPolygon(
            QPolygonF(
                [
                    QPointF(0, 0),
                    QPointF(self.width, 0),
                    QPointF(self.width / 2, self.height),
                ]
            )
        )

        self.base_color = color
        self.setBrush(QBrush(self.base_color))
        self.highlight_color = self.base_color.lighter(123)

    # TODO: is there a reason we don't use the built in setters/getters? Fix this if not
    @property
    def frame(self):
        """
        WARNING DO NOT MODIFY THIS DIRECTLY. Use the `set_onset` method to update this value
        """
        return self._frame

    def get_context_menu(self) -> QMenu:
        """
        Returns a context menu for the behavior item

        Parameters
        ----------
        event : QMouseEvent
            The mouse event that triggered the context menu
        """
        menu = QMenu()
        delete_action = menu.addAction("Delete Flag")
        delete_action.triggered.connect(lambda: self.ruler_view.remove_flag(self.frame))
        return menu

    def hoverEnterEvent(self, event):
        self.hovered = True
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.hovered = False
        super().hoverLeaveEvent(event)

    def update_tooltip(self):
        self.setToolTip(f"Frame: {self.frame}")

    def set_frame(self, new_frame: int):
        """
        Set the frame position of the flag.

        Parameters
        ----------
        new_onset : int
            The new onset value
        """

        self._frame = new_frame
        self.update_tooltip()
        self.ruler_view.scene().update()

    def highlight(self):
        self.setBrush(QBrush(self.highlight_color))

    def unhighlight(self):
        self.setBrush(QBrush(self.base_color))

    def errorHighlight(self):
        self.setBrush(QBrush(QColor("#ff0000")))

    def hoverEnterEvent(self, event):
        self.hovered = True
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.hovered = False
        super().hoverLeaveEvent(event)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        # draw us with a border if we are selected
        super().paint(painter, option, widget)
        self.setOpacity(1)
        if self.hovered:
            # lighten the color
            brush = QBrush(self.highlight_color)
            painter.setBrush(brush)
            painter.drawPolygon(self.polygon())
        else:
            brush = QBrush(self.base_color)
            painter.setBrush(brush)
            painter.drawPolygon(self.polygon())

    def setVisible(self, visible: bool):
        super().setVisible(visible)
