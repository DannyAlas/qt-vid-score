from typing import TYPE_CHECKING, List

from video_scoring.command_stack import Command

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.behavior_items import OnsetOffsetItem
    from video_scoring.widgets.timeline.flag import FlagItem
    from video_scoring.widgets.timeline.marker import MarkerItem
    from video_scoring.widgets.timeline.timeline import TimelineDockWidget, TimelineView
    from video_scoring.widgets.timeline.track import BehaviorTrack


class AddBehaviorCommand(Command):
    def __init__(
        self,
        timeline_view: "TimelineView",
        track: "BehaviorTrack",
        item: "OnsetOffsetItem",
    ):
        super().__init__()
        self.timeline_view = timeline_view
        self.track = track
        self.item = item

    def redo(self):
        self.track.behavior_items[self.item.onset] = self.item
        self.timeline_view.scene().addItem(self.item)
        self.timeline_view.scene().update()
        self.timeline_view.main_window.timestamps_dw.refresh()

    def undo(self):
        self.track.behavior_items.pop(self.item.onset)
        self.timeline_view.scene().removeItem(self.item)
        self.timeline_view.scene().update()
        self.timeline_view.main_window.timestamps_dw.refresh()


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


class DeleteBehaviorCommand(Command):
    def __init__(
        self,
        timeline_view: "TimelineView",
        track: "BehaviorTrack",
        item: "OnsetOffsetItem",
    ):
        super().__init__()
        self.timeline_view = timeline_view
        self.track = track
        self.item = item

    def undo(self):
        self.track.behavior_items[self.item.onset] = self.item
        self.timeline_view.scene().addItem(self.item)
        self.timeline_view.scene().update()
        self.timeline_view.main_window.timestamps_dw.refresh()

    def redo(self):
        self.track.behavior_items.pop(self.item.onset)
        self.timeline_view.scene().removeItem(self.item)
        self.timeline_view.scene().update()
        self.timeline_view.main_window.timestamps_dw.refresh()


class BatchDeleteBehaviorCommand(Command):
    def __init__(
        self,
        timeline_view: "TimelineView",
        items: List["OnsetOffsetItem"],
    ):
        super().__init__()
        self.timeline_view = timeline_view
        self.items = items

    def undo(self):
        for item in self.items:
            track = item.parent
            track.behavior_items[item.onset] = item
            self.timeline_view.scene().addItem(item)
        self.timeline_view.scene().update()
        self.timeline_view.main_window.timestamps_dw.refresh()

    def redo(self):
        for item in self.items:
            track = item.parent
            track.behavior_items.pop(item.onset)
            self.timeline_view.scene().removeItem(item)
        self.timeline_view.scene().update()
        self.timeline_view.main_window.timestamps_dw.refresh()


class AddTrackCommand(Command):
    def __init__(
        self,
        timeline_view: "TimelineView",
        track: "BehaviorTrack",
    ):
        super().__init__()
        self.timeline_view = timeline_view
        self.track = track

    def redo(self):
        self.timeline_view.behavior_tracks.append(self.track)
        self.timeline_view.scene().addItem(self.track)
        self.timeline_view.scene().update()

    def undo(self):
        self.timeline_view.behavior_tracks.pop(
            self.timeline_view.behavior_tracks.index(self.track)
        )
        self.timeline_view.scene().removeItem(self.track)
        self.timeline_view.scene().update()


class DeleteTrackCommand(Command):
    def __init__(
        self,
        timeline_view: "TimelineView",
        track: "BehaviorTrack",
    ):
        super().__init__()
        self.timeline_view = timeline_view
        self.track = track

    def redo(self):
        self.timeline_view.behavior_tracks.pop(
            self.timeline_view.behavior_tracks.index(self.track)
        )
        self.timeline_view.scene().removeItem(self.track)
        self.timeline_view._parent.track_header.remove_track_header(self.track)
        self.timeline_view.scene().update()

    def undo(self):
        self.timeline_view.behavior_tracks.append(self.track)
        self.timeline_view.scene().addItem(self.track)
        self.timeline_view._parent.track_header.add_track_header(self.track)
        # reset the y position of the tracks
        self.timeline_view.scene().update()


class MarkerMoveCommand(Command):
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
        self, undo_onset, undo_offset, redo_onset, redo_offset, item: "MarkerItem"
    ):
        self.undo_onset = undo_onset
        self.undo_offset = undo_offset
        self.redo_onset = redo_onset
        self.redo_offset = redo_offset
        self.item = item

    def undo(self):
        self.item.set_onset_offset(self.undo_onset, self.undo_offset)
        self.item.update()
        self.item.signals.updated.emit()
        self.item.scene().update()

    def redo(self):
        self.item.set_onset_offset(self.redo_onset, self.redo_offset)
        self.item.update()
        self.item.signals.updated.emit()
        self.item.scene().update()


class FlagMoveCommand(Command):
    """
    Implements a command for undo/redo functionality of flag moves.

    Parameters
    ----------
    undo_frame : int
        The to be set when undoing the command
    redo_frame : int
        The to be set when redoing the command
    flag : FlagItem
        The flag that the command is associated with
    """

    def __init__(self, undo_frame, redo_frame, item: "FlagItem"):
        self.undo_frame = undo_frame
        self.redo_frame = redo_frame
        self.item = item

    def undo(self):
        self.item.set_frame(self.undo_frame)
        self.item.update()
        self.item.scene().update()

    def redo(self):
        self.item.set_frame(self.redo_frame)
        self.item.update()
        self.item.scene().update()
