import re
from typing import TYPE_CHECKING, Literal, Optional
from uuid import uuid4

from qtpy.QtGui import QBrush, QColor, QKeySequence
from qtpy.QtWidgets import (QGraphicsRectItem, QGraphicsSceneMouseEvent,
                            QGraphicsTextItem)

from video_scoring.widgets.timeline.behavior_items import OnsetOffsetItem

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineView
    from video_scoring.widgets.timeline.track_header import TrackHeader


class BehaviorTrack(QGraphicsRectItem):
    def __init__(
        self,
        name: str,
        y_position,
        track_height,
        behavior_type: Literal["OnsetOffset", "Single"],
        parent: "TimelineView",
    ):
        super().__init__()
        self.parent = parent
        self.name = name
        self.y_position = y_position
        self.track_height = track_height
        self.behavior_type = behavior_type
        self.save_ts_ks = QKeySequence()
        self.save_uts_ks = QKeySequence()

        # TODO: Maybe radomize this across tracks from a palette?
        self.item_color = "#6aa1f5"  # default color
        self.track_header = None
        self.setToolTip(name)
        self.setBrush(QBrush(QColor("#545454")))

        # a dict of behavior items where the key is the onset frame and the value is the item
        self.behavior_items: dict[int, OnsetOffsetItem] = {}

        self.curr_behavior_item: Optional[OnsetOffsetItem] = None

    def get_item(self, onset: int) -> Optional[OnsetOffsetItem]:
        return self.behavior_items.get(onset, None)

    def add_behavior(self, onset, unsure=False) -> tuple[bool, OnsetOffsetItem]:
        """Add a new behavior item to the track.

        Parameters
        ----------
        onset : int
            The onset frame of the new behavior item
        unsure : bool, optional
            Whether or not the behavior is unsure, by default False

        Returns
        -------
        tuple[bool, OnsetOffsetItem]
            A tuple containing a bool indicating whether or not the behavior was added. If it was, the second item is the new behavior item. If it wasn't, the second item is the item that overlaps with the new item.
        """
        # add a new behavior item
        ovlp = self.check_for_overlap(onset)
        if ovlp is not None:
            return False, ovlp
        self.curr_behavior_item = OnsetOffsetItem(
            onset, onset + 1, unsure, self.parent, self
        )
        self.behavior_items[onset] = self.curr_behavior_item
        return True, self.curr_behavior_item

    def remove_behavior(self, item: "OnsetOffsetItem"):
        # remove the given behavior item
        item = self.behavior_items.pop(item.onset)
        self.parent.scene().removeItem(item)
        return item

    def set_unsure(self, item: "OnsetOffsetItem", unsure: bool):
        item.set_unsure(unsure)
        self.parent.scene().update()
        self.parent.main_window.timestamps_dw.refresh()

    def check_for_overlap(self, onset, offset=None):
        # check if the provided item overlaps with any existing items
        # if it does, return the item that overlaps
        for other_onset, other_item in self.behavior_items.items():
            # skip the item we're checking
            if other_onset == onset:
                continue
            # if our new onset is between the onset and offset of another item, don't update the onset
            if onset >= other_onset and onset <= other_item.offset:
                return other_item
            if offset is not None:
                # if our new offset is between the onset and offset of another item, don't update the offset
                if offset >= other_onset and offset <= other_item.offset:
                    return other_item
                # if we encompass another item, don't update the onset or offset
                if onset <= other_onset and offset >= other_item.offset:
                    return other_item
        return None

    def overlap_with_item_check(
        self, item: "OnsetOffsetItem", onset: int = None, offset: int = None
    ):
        """
        Check if the given onset or offset overlaps with any other items in the track.

        Parameters
        ----------
        item : OnsetOffsetItem
            The item to check
        onset : int, optional
            the new onset, by default None
        offset : int, optional
            the new offset, by default None

        Returns
        -------
        bool
            True if the onset or offset overlaps with another item, False otherwise
        """
        # we're updating the onset
        if onset is not None and onset != item.onset:
            # if the new onset is already in the dict
            if onset in self.behavior_items.keys():
                return True
            for other_onset, other_item in self.behavior_items.items():
                # skip the item we're updating
                if item == other_item:
                    continue
                # if our new onset is between the onset and offset of another item
                if other_onset <= onset and other_item.offset >= onset + 1:
                    return True
        # we're updating the offset
        if offset is not None and offset != item.offset:
            for other_onset, other_item in self.behavior_items.items():
                # skip the item we're updating
                if other_onset == item.onset:
                    continue
                # if our new offset is between the onset and offset of another item
                if offset - 1 >= other_onset and offset <= other_item.offset:
                    return True
                # if we encompass another item, don't update the onset or offset
                if onset <= other_onset and offset >= other_item.offset:
                    return True
        return False

    def update_behavior_onset(self, item: "OnsetOffsetItem", onset: int):
        """
        Update the onset of a behavior item in the `behavior_items` dict.

        Parameters
        ----------
        item : OnsetOffsetItem
            The item to update
        """
        if onset != item.onset:
            self.behavior_items[onset] = self.behavior_items.pop(item.onset)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        return super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        return super().mouseReleaseEvent(event)

    def update_name(self, name: str):
        self.name = name
        self.track_header.label.setText(name)
        self.setToolTip(name)

    def update_item_colors(self, color_str: str):
        color = QColor(color_str)
        self.item_color = color.name()
        for item in self.behavior_items.values():
            item.base_color = color
            item.highlight_color = color.lighter(150)
            item.setBrush(QBrush(color))

    def update_shortcut(self, key_sequence: QKeySequence):
        if self.save_ts_ks == key_sequence:
            return
        func_name = f"Save Timestamp on {self.name}"
        # create a method for this class with the name of the function
        setattr(
            self,
            func_name,
            lambda: self.save_sure_ts_on_shortcut(),
        )
        try:
            self.parent.main_window.register_shortcut(
                method=getattr(self, func_name),
                key_sequence=key_sequence,
                name=func_name,
            )
        except Exception as e:
            raise Exception(
                f"Could not register shortcut `{key_sequence.toString()}` for track {self.name} because {e}"
            )
        self.save_ts_ks = key_sequence

    def update_unsure_shortcut(self, key_sequence: QKeySequence):
        if self.save_uts_ks == key_sequence:
            return
        func_name = f"Save Unsure Timestamp on {self.name}"
        setattr(
            self,
            func_name,
            lambda: self.save_unsure_ts_on_shortcut(),
        )
        try:
            self.parent.main_window.register_shortcut(
                method=getattr(self, func_name),
                key_sequence=key_sequence,
                name=func_name,
            )
        except Exception as e:
            raise Exception(
                f"Could not register shortcut `{key_sequence.toString()}` for track {self.name} because {e}"
            )
        self.save_uts_ks = key_sequence

    def set_track_header(self, header: "TrackHeader"):
        self.track_header = header

    def save_sure_ts_on_shortcut(self):
        # set the timeline track_name_to_save to this track's name
        self.parent.track_name_to_save_on = self.name
        self.parent._parent.save_timestamp()

    def save_unsure_ts_on_shortcut(self):
        # set the timeline track_name_to_save to this track's name
        self.parent.track_name_to_save_on = self.name
        self.parent._parent.save_timestamp(unsure=True)
