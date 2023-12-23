from typing import TYPE_CHECKING, Literal, Optional

from qtpy.QtGui import QBrush, QColor
from qtpy.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
)

from video_scoring.widgets.timeline.behavior_items import OnsetOffsetItem

if TYPE_CHECKING:
    from video_scoring.widgets.timeline.timeline import TimelineView


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
        self.track_name_item = QGraphicsTextItem(self.name)
        self.y_position = y_position
        self.track_height = track_height
        self.behavior_type = behavior_type
        # TODO: Maybe radomize this across tracks from a palette? 
        self.item_color = "#6aa1f5" # default color
        self.setToolTip(name)
        self.setBrush(QBrush(QColor("#545454")))

        # a dict of behavior items where the key is the onset frame and the value is the item
        self.behavior_items: dict[int, OnsetOffsetItem] = {}

        self.curr_behavior_item: Optional[OnsetOffsetItem] = None

    def add_behavior(self, onset):
        # add a new behavior item
        # if offset is none we're we will be changing the offset based on the playheads position
        self.curr_behavior_item = OnsetOffsetItem(onset, onset + 1, self.parent, self)
        self.behavior_items[onset] = self.curr_behavior_item
        return self.curr_behavior_item

    def remove_behavior(self, item: "OnsetOffsetItem"):
        # remove the given behavior item
        self.behavior_items.pop(item.onset)
        self.parent.scene().removeItem(item)

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
                # if we encompass another item
                if onset <= other_onset and item.offset >= other_item.offset:
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
                if item.onset <= other_onset and offset >= other_item.offset:
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
        self.track_name_item.setPlainText(name)

    def update_item_colors(self, color: str):
        self.item_color = color
        _color = QColor(color)
        for item in self.behavior_items.values():
            item.base_color = _color
            item.highlight_color = _color.lighter(150)
            item.setBrush(QBrush(_color))

    def load(self, data: dict):
        self.name = data["name"]
        self.y_position = data["y_position"]
        self.track_height = data["track_height"]
        self.behavior_type = data["behavior_type"]
        for item_data in data["behavior_items"]:
            i = self.add_behavior(item_data["onset"])
            i.set_offset(item_data["offset"])

    def save(self):
        return {
            "name": self.name,
            "y_position": self.y_position,
            "track_height": self.track_height,
            "behavior_type": self.behavior_type,
            "behavior_items": [item.save() for item in self.behavior_items.values()],
        }
