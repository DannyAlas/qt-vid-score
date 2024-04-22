from typing import TYPE_CHECKING, List, Optional, Union

from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QEnterEvent, QMouseEvent, QMoveEvent, QPaintEvent, QResizeEvent
from PyQt6.sip import voidptr
from qtpy import QtCore, QtGui, QtWidgets
from video_scoring.widgets.ui.confimLineEdit import ConfirmLineEdit

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineView
    from video_scoring.widgets.timeline.track import BehaviorTrack

from video_scoring.widgets.timeline.dialogs import TrackSettingsDialog


class TrackHeadersOptionsToolBar(QtWidgets.QToolBar):
    def __init__(self, parent: "TrackHeadersWidget"):
        super().__init__(parent)
        self._parent = parent
        self.setMovable(False)
        self.setFloatable(False)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setContentsMargins(0, 0, 0, 0)
        self.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setStyleSheet(
            """QToolBar { 
            background-color: #2c2c2c; 
            padding: 5px; 
            border: 2px solid #3f4042;
            border-radius: 5px;
            }"""
        )
        self.lock_sizes_action = QtWidgets.QAction(self)
        self.lock_sizes_action.setCheckable(True)
        self.lock_sizes_action.setChecked(False)
        self.lock_sizes_action.setToolTip("Lock Track Sizes")
        self.lock_sizes_action.setIcon(
            self._parent.timeline.main_window.get_icon(
                "resize_unlocked.png", self.lock_sizes_action
            )
        )
        self.lock_sizes_action.triggered.connect(self.on_lock_sizes_action_triggered)
        self.addAction(self.lock_sizes_action)

        self.fit_track_heights_action = QtWidgets.QAction(self)
        self.fit_track_heights_action.setToolTip("Fit Track Heights")
        self.fit_track_heights_action.setIcon(
            self._parent.timeline.main_window.get_icon(
                "scalability.png", self.fit_track_heights_action
            )
        )
        self.fit_track_heights_action.triggered.connect(self.fit_track_heights)
        self.addAction(self.fit_track_heights_action)

        self.add_track_action = QtWidgets.QAction(self)
        self.add_track_action.setToolTip("Add Track")
        self.add_track_action.setIcon(
            self._parent.timeline.main_window.get_icon(
                "plus.svg", self.add_track_action
            )
        )
        self.add_track_action.triggered.connect(
            self._parent.timeline.parent.add_behavior_track
        )
        self.addAction(self.add_track_action)

        self.open_flags_action = QtWidgets.QAction(self)
        self.open_flags_action.setToolTip("Open Flags Dialog")
        self.open_flags_action.setIcon(
            self._parent.timeline.main_window.get_icon(
                "flag.png", self.open_flags_action
            )
        )
        self.open_flags_action.triggered.connect(
            self._parent.timeline.parent.open_flags_dialog
        )

        self.addAction(self.open_flags_action)

    def fit_track_heights(self):
        """When the fit track heights button is clicked fit the track heights"""
        self.lock_sizes_action.setChecked(False)
        # -35 not sure why though
        height_to_fit = self._parent.splitter.rect().height() - 35
        num_tracks = len(self._parent.track_headers)
        if num_tracks == 0:
            return
        track_height = height_to_fit / num_tracks
        for track_header in self._parent.track_headers:
            # position the track header
            track_header.move(
                0, int(track_height * self._parent.track_headers.index(track_header))
            )
            track_header.resize(
                QtCore.QSize(int(track_header.size().width()), int(track_height))
            )
            track_header.update()
        self.lock_sizes_action.setChecked(True)
        self.on_lock_sizes_action_triggered()

    def on_lock_sizes_action_triggered(self):
        """When the lock sizes button is clicked lock the sizes of all track headers"""
        if self.lock_sizes_action.isChecked():
            for track_header in self._parent.track_headers:
                track_header.setFixedHeight(track_header.height())
            self.lock_sizes_action.setIcon(
                self._parent.timeline.main_window.get_icon(
                    "resize_locked.png", self.lock_sizes_action
                )
            )
        else:
            for track_header in self._parent.track_headers:
                track_header.setMaximumHeight(16777215)
                track_header.setMinimumHeight(
                    track_header.label.sizeHint().height() + 7
                )
                track_header.resize(
                    QtCore.QSize(
                        int(track_header.size().width()), int(track_header.height())
                    )
                )
            self.lock_sizes_action.setIcon(
                self._parent.timeline.main_window.get_icon(
                    "resize_unlocked.png", self.lock_sizes_action
                )
            )


class RecordToggle(QtWidgets.QCheckBox):
    """A QPushButton that is used to record a behavior"""

    def __init__(self, parent: "TrackHeader", timeline: "TimelineView"):
        super().__init__(parent)
        self._parent = parent
        self.timeline = timeline
        self.setCheckable(True)
        self.setChecked(False)
        self.setToolTip("Save on this track")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.hovered = False
        self.circle_rect = QtCore.QRect(self.rect().right() - 15, 5, 10, 10)

    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        # if we're hovering over the circle set the cursor to a pointing hand
        if self.circle_rect.contains(a0.pos()):
            self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.hovered = True
        else:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.hovered = False
        self.update()
        return super().mouseMoveEvent(a0)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        self.hovered = False
        self.update()
        return super().leaveEvent(a0)

    def mousePressEvent(self, e: QMouseEvent | None) -> None:
        if self.circle_rect.contains(e.pos()):
            self.toggle()
            self._parent.on_record_button_clicked()

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        # update the circle_rect position
        self.circle_rect = QtCore.QRect(self.rect().right() - 15, 5, 10, 10)
        return super().resizeEvent(a0)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the record button"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.transparent))
        # if checked draw a red circle else draw a gray circle
        if self.isChecked():
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#ff0000")))
        else:
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#545454")))
        # draw on right edge
        painter.drawEllipse(self.circle_rect)
        if self.hovered:
            painter.setPen(QtGui.QPen(QtGui.QColor("#9c9c9c"), 1))
            painter.drawEllipse(self.circle_rect)


class TrackLineEdit(ConfirmLineEdit):

    def __init__(self, parent: "TrackHeader", timeline: "TimelineView"):
        super().__init__(parent=parent, main_win=timeline.main_window, text=parent.track.name)
        self.timeline = timeline
        self._parent = parent
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.edit.setText(self._parent.track.name)

    def save_func(self, text: str):
        self._parent.track.update_name(text)

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(200, self.edit.sizeHint().height() + 10) # 10 is padding

class TrackSettingsButton(QtWidgets.QPushButton):
    def __init__(self, parent: "TrackHeader"):
        super().__init__(parent)
        self._parent = parent
        self.setToolTip("Settings")
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setIcon(self._parent.timeline.main_window.get_icon("settings.svg", self))
        self.clicked.connect(self.open_settings)

    def open_settings(self):
        dialog = TrackSettingsDialog(self._parent, self._parent.track)
        dialog.exec_()
        self._parent.update()


class TrackHeader(QtWidgets.QWidget):
    """This is a widget that represents a track header in the timeline view."""

    def __init__(
        self,
        parent: "TrackHeadersWidget",
        track: "BehaviorTrack",
        timeline: "TimelineView",
    ):
        super().__init__(parent)
        self._parent = parent
        self.track = track
        self.track.set_track_header(self)
        self.timeline = timeline
        self.tldw = self.timeline._parent
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_custom_context_menu_requested)
        self.layout = QtWidgets.QGridLayout(self)

        self.settings_button = TrackSettingsButton(self)

        self.label = TrackLineEdit(self, self.timeline)
        self.label.setToolTip("Rename Track")

        # the top right corner of the track header is an elipse that can be clicked to set this as the track_name_to_save_on for the timeline
        self.record_button = RecordToggle(self, self.timeline)
        self.record_button.setToolTip("Set track name to save on")
        # move record button to the right edge

        # label takes up the first column fully
        self.layout.addWidget(self.settings_button, 0, 0, 1, 1)
        self.layout.addWidget(self.label, 0, 1, 1, 1)
        self.layout.addWidget(self.record_button, 0, 2, 1, 1)
        self.setLayout(self.layout)
        self.setMinimumHeight(self.label.sizeHint().height() + 7)
        self.resize(
            QtCore.QSize(int(self.track.rect().width()), self.track.track_height)
        )
        self.tldw.loaded.connect(
            lambda: self.tldw.timeline_view.track_name_to_save_on_changed.connect(
                self.on_track_name_to_save_on_changed
            )
        )

    def on_track_name_to_save_on_changed(self, track_name: str):
        """When the track_name_to_save_on changes update the record button"""
        if track_name == self.track.name:
            self.record_button.setChecked(True)
            for track_header in self._parent.track_headers:
                if track_header is not self:
                    track_header.record_button.setChecked(False)
                    track_header.update()
        else:
            self.record_button.setChecked(False)

    def check_record_button(self):
        self.record_button.setChecked(True)
        self.on_record_button_clicked()

    def get_context_menu(self):
        menu = QtWidgets.QMenu(self)
        delete_action = QtWidgets.QAction("Delete", self)
        delete_action.triggered.connect(
            lambda: self.timeline.parent.delete_behavior_track(self.track)
        )
        return menu

    def on_custom_context_menu_requested(self, pos: QtCore.QPoint):
        """When the track header is right clicked show a context menu"""
        menu = self.get_context_menu()
        menu.exec_(self.mapToGlobal(pos))

    def on_record_button_clicked(self):
        """When the record button is clicked set the track_name_to_save_on for the timeline"""
        if self.record_button.isChecked():
            self.timeline.parent.set_track_to_save_on(self.track.name)
            # uncheck all other record buttons
            for track_header in self._parent.track_headers:
                if track_header is not self:
                    track_header.record_button.setChecked(False)
        if not any(
            [
                track_header.record_button.isChecked()
                for track_header in self._parent.track_headers
            ]
        ):
            self.timeline.parent.set_track_to_save_on(None)

    def update_track_size_pos(self):
        curr_size = self.size()
        curr_pos = self.pos()
        # convert the position to the timeline view coordinates
        # # set the track size and position
        self.track.y_position = int(curr_pos.y() + 10)
        self.track.track_height = curr_size.height()
        self.timeline.scene().update()
        self.timeline.update()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        """When the widget is resized update the track size in the timeline"""
        super().resizeEvent(event)
        self.update_track_size_pos()

    def moveEvent(self, a0: QMoveEvent | None) -> None:
        super().moveEvent(a0)
        self.update_track_size_pos()

    def update_track_name(self, name: str):
        """Update the track name"""
        self.track.name = name
        self.label.setText(name)
        self.label.setToolTip(name)
        self.update_track_size_pos()

    def update(self):
        """Update the track header"""
        super().update()
        self.update_track_size_pos()


class TrackHeadersWidget(QtWidgets.QWidget):
    """A QWidget that holds a list of TrackHeader in a QSplitter"""

    def __init__(self, parent: QtWidgets.QWidget, timeline: "TimelineView"):
        super().__init__(parent)
        self.timeline = timeline
        self.layout = QtWidgets.QVBoxLayout(self)
        self.setFixedWidth(200)

        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(5)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #2c2c2c }")
        self.splitter.setOpaqueResize(True)
        self.splitter.splitterMoved.connect(self.on_splitter_moved)
        self.options_widget = TrackHeadersOptionsToolBar(self)
        # self.layout.addWidget(self.options_widget)
        self.options_widget.setFixedHeight(self.timeline.parent.timeline_ruler.height())

        self.top_spacer = QtWidgets.QWidget()
        self.bottom_spacer = QtWidgets.QWidget()
        self.splitter.addWidget(self.top_spacer)
        self.splitter.addWidget(self.bottom_spacer)
        self.layout.addWidget(self.options_widget)
        self.layout.addWidget(self.splitter)
        self.setLayout(self.layout)
        self.track_headers: List[TrackHeader] = []

    def add_track_header(self, track: "BehaviorTrack"):
        """Add a TrackHeader to the TrackHeaderWidget"""
        track_header = TrackHeader(self, track, self.timeline)
        self.track_headers.append(track_header)
        # remove the bottom spacer and add the track header
        self.bottom_spacer.setParent(None)
        self.splitter.addWidget(track_header)
        # add the bottom spacer back
        self.splitter.addWidget(self.bottom_spacer)
        track_header.update()
        self.timeline.main_window.timestamps_dw.refresh()

    def on_splitter_moved(self):
        """When the splitter is moved update the width of the TrackHeader"""
        for track_header in self.track_headers:
            track_header.setFixedWidth(self.splitter.width())

    def set_track_headers(self, track_headers: List["TrackHeader"]):
        """Set the track headers"""
        self.track_headers = track_headers
        for track_header in self.track_headers:
            self.splitter.addWidget(track_header)

    def get_track_header(self, track: "BehaviorTrack") -> Optional["TrackHeader"]:
        """Get the TrackHeader for a given track"""
        for track_header in self.track_headers:
            if track_header.track == track:
                return track_header
        return None

    def remove_track_header(self, track: "BehaviorTrack"):
        """Remove the TrackHeader for a given track"""
        track_header = self.get_track_header(track)
        if track_header is not None:
            self.track_headers.remove(track_header)
            track_header.setParent(None)
            track_header.deleteLater()
            self.splitter.update()
            self.update()

    def update(self):
        """Update the TrackHeaderWidget"""
        super().update()
        for track_header in self.track_headers:
            track_header.update()
