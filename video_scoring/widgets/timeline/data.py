from typing import Union


class OnsetOffset(dict):
    """
    Represents a dictionary of onset and offset frames. Provides methods to add a new entry with checks for overlap. Handels sorting.

    Notes
    -----
    The Key is the onset frame and the value is a dict with the keys "offset", "sure", and "notes". The value of "offset" is the offset frame. The value of "sure" is a bool indicating if the onset-offset pair is sure. The value of "notes" is a string.

    We only store frames in the dict. The conversion to a time is handled by the UI. We will always store the onset and offset as frames.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._onset_offset = {}

    def __setitem__(self, key, value):
        # check if the key is a frame number
        if not isinstance(key, int):
            raise TypeError("The key must be an integer")

        # check if the value is a dict
        if not isinstance(value, dict):
            raise TypeError("The value must be a dict")

        # check if the value has the correct keys
        if not all(key in value.keys() for key in ["offset", "sure", "notes"]):
            raise ValueError(
                'The value must have the keys "offset", "sure", and "notes"'
            )

        # check if the offset is a frame number
        if value["offset"] is not None and not isinstance(value["offset"], int):
            raise TypeError("The offset must be an integer or None")

        # check if sure is a bool
        if not isinstance(value["sure"], bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if not isinstance(value["notes"], str):
            raise TypeError("The notes value must be a string")

        # check if the onset is already in the dict
        if key in self._onset_offset.keys():
            raise ValueError("The onset is already in the dict")

    def add_onset(self, onset, offset=None, sure=None, notes=None):
        # check if the onset is already in the dict
        if onset in self._onset_offset.keys():
            raise ValueError("The onset is already in the dict")

        # check if the offset is a frame number
        if offset is not None and not isinstance(offset, int):
            raise TypeError("The offset must be an integer or None")

        # check if sure is a bool
        if sure is not None and not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if notes is not None and not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # check for overlap
        self._check_overlap(onset=onset, offset=offset)

        # add the onset to the dict
        self._onset_offset[onset] = {
            "offset": offset,
            "sure": sure,
            "notes": notes,
        }

        # sort dict by onset
        self._onset_offset = dict(
            sorted(self._onset_offset.items(), key=lambda x: x[0])
        )

    def add_offset(self, onset, offset):
        # check if the onset is already in the dict
        if onset not in self._onset_offset.keys():
            raise ValueError("The onset is not in the dict")

        # check if the offset is a frame number
        if not isinstance(offset, int):
            raise TypeError("The offset must be an integer")

        # check for overlap
        self._check_overlap(onset=onset, offset=offset)

        # add the offset to the dict
        self._onset_offset[onset]["offset"] = offset

        # sort dict by onset
        self._onset_offset = dict(
            sorted(self._onset_offset.items(), key=lambda x: x[0])
        )

    def add_sure(self, onset, sure):
        # check if the onset is already in the dict
        if onset not in self._onset_offset.keys():
            raise ValueError("The onset is not in the dict")

        # check if sure is a bool
        if not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # add the sure to the dict
        self._onset_offset[onset]["sure"] = sure

    def add_notes(self, onset, notes):
        # check if the onset is already in the dict
        if onset not in self._onset_offset.keys():
            raise ValueError("The onset is not in the dict")

        # check if notes is a string
        if not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # add the notes to the dict
        self._onset_offset[onset]["notes"] = notes

    def _check_overlap(self, onset, offset=None):
        """
        Check if the provided onset and offset times overlap with any existing ranges.

        Parameters
        ----------
        onset : int
            The onset frame.
        offset : int, optional
            The offset frame, by default None.

        Raises
        ------
        ValueError
            If there is an overlap.
        """

        # If we are adding a new onset, check if it will overlap with any existing onset - offset ranges
        if offset is None:
            for n_onset, entry in self._onset_offset.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if onset >= n_onset and onset <= entry["offset"]:
                    raise ValueError(
                        f"The provided onset time of {onset} overlaps with an existing range: {n_onset} - {entry['offset']}"
                    )

        if offset is not None:
            if offset <= onset:
                raise ValueError(
                    f"The provided offset frame of {offset} is before the onset frame of {onset}"
                )
            for n_onset, entry in self._onset_offset.items():
                # some entries may not have an offset yet
                if entry["offset"] is None:
                    continue
                if onset >= n_onset and onset <= entry["offset"]:
                    raise ValueError(
                        f"The provided onset/offset range of `{onset} : {offset}` overlaps with an existing range: {n_onset} - {entry['offset']}"
                    )


class Single(dict):
    """Represents a dictionary of onset frames. Handels sorting."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._onset = {}

    def __setitem__(self, key, value):
        # check if the key is a frame number
        if not isinstance(key, int):
            raise TypeError("The key must be an integer")

        # check if the value is a dict
        if not isinstance(value, dict):
            raise TypeError("The value must be a dict")

        # check if the value has the correct keys
        if not all(key in value.keys() for key in ["sure", "notes"]):
            raise ValueError('The value must have the keys "sure", and "notes"')

        # check if sure is a bool
        if not isinstance(value["sure"], bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if not isinstance(value["notes"], str):
            raise TypeError("The notes value must be a string")

        # check if the onset is already in the dict
        if key in self._onset.keys():
            raise ValueError("The onset is already in the dict")

    def add_onset(self, onset, sure=None, notes=None):
        # check if the onset is already in the dict
        if onset in self._onset.keys():
            raise ValueError("The onset is already in the dict")

        # check if sure is a bool
        if sure is not None and not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # check if notes is a string
        if notes is not None and not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # add the onset to the dict
        self._onset[onset] = {
            "sure": sure,
            "notes": notes,
        }

        # sort dict by onset
        self._onset = dict(sorted(self._onset.items(), key=lambda x: x[0]))

    def add_sure(self, onset, sure):
        # check if the onset is already in the dict
        if onset not in self._onset.keys():
            raise ValueError("The onset is not in the dict")

        # check if sure is a bool
        if not isinstance(sure, bool):
            raise TypeError("The sure value must be a bool")

        # add the sure to the dict
        self._onset[onset]["sure"] = sure

    def add_notes(self, onset, notes):
        # check if the onset is already in the dict
        if onset not in self._onset.keys():
            raise ValueError("The onset is not in the dict")

        # check if notes is a string
        if not isinstance(notes, str):
            raise TypeError("The notes value must be a string")

        # add the notes to the dict
        self._onset[onset]["notes"] = notes


class Behaviors(dict):
    """Represents a dictionary of behaviors. Each behavior has a name as a key and implements the OnsetOffset or Singe class as the value."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._behaviors = {}

    def __setitem__(self, key, value):
        # check if the key is a string
        if not isinstance(key, str):
            raise TypeError("The key must be a string")

        # check if the value is a OnsetOffset or Single object
        if not isinstance(value, (OnsetOffset, Single)):
            raise TypeError("The value must be a OnsetOffset or Single object")

        # check if the onset is already in the dict
        if key in self._behaviors.keys():
            raise ValueError("The behavior is already in the dict")

    def add_behavior(self, name, behavior_type: Union[OnsetOffset, Single]):
        # check if the behavior is already in the dict
        if name in self._behaviors.keys():
            raise ValueError("The behavior is already in the dict")

        # add the behavior to the dict
        self._behaviors[name] = behavior_type
