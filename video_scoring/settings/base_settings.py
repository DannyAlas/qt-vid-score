import datetime
from re import T
from uuid import uuid4

from qtpy.QtCore import QByteArray
import json
import logging
import zipfile
import os
import sys
from typing import Any, List, Literal, Tuple, Union, Dict, TypeVar
from uuid import uuid4, UUID

from pydantic import BaseModel, Field, UUID4, field_validator

log = logging.getLogger()

uidT = TypeVar("uidT", str, UUID)
project_file_locationT = TypeVar("project_file_locationT", str, os.PathLike)
dtT = TypeVar("dtT", datetime.datetime, str)
def user_data_dir(file_name):
    r"""
    Get OS specific data directory path for Video Scoring.

    Typical user data directories are:
        macOS:    ~/Library/Application Support/Video Scoring
        Unix:     ~/.local/share/Video Scoring   # or in $XDG_DATA_HOME, if defined
        Win 10:   C:\Users\<username>\AppData\Local\Video Scoring
    For Unix, we follow the XDG spec and support $XDG_DATA_HOME if defined.
    :param file_name: file to be fetched from the data dir
    :return: full path to the user-specific data dir
    """
    # get os specific path
    if sys.platform.startswith("win"):
        os_path = os.getenv("LOCALAPPDATA")
    elif sys.platform.startswith("darwin"):
        os_path = "~/Library/Application Support"
    else:
        # linux
        os_path = os.getenv("XDG_DATA_HOME", "~/.local/share")

    # join with Video Scoring dir
    path = os.path.join(str(os_path), "Video Scoring")

    return os.path.join(path, file_name)

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return obj.__str__()
        if isinstance(obj, datetime.datetime):
            return obj.__str__()
        if isinstance(obj, QByteArray):
            # will be serialized as base64 encoded string
            return obj.data().decode()
        return json.JSONEncoder.default(self, obj)

class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object, *args, **kwargs)

    def dict_to_object(self, d):
        if "uid" in d:
            d["uid"] = UUID(d["uid"])
        if "created" in d:
            d["created"] = datetime.datetime.fromisoformat(d["created"])
        if "modified" in d:
            d["modified"] = datetime.datetime.fromisoformat(d["modified"])
        return d

class AbstSettings(BaseModel):
    @staticmethod
    def help_text() -> dict:
        raise NotImplementedError


class Scoring(AbstSettings):
    scoring_type: Literal["onset/offset", "single"] = "onset/offset"
    save_frame_or_time: Literal["frame", "timestamp"] = "frame"
    text_color: str = "#FFFFFF"

    @staticmethod
    def help_text():
        return {
            "scoring_type": "Either 'onset/offset' or 'single'. If set to 'onset/offset' will save timestamps as a list of event onset/offset pairs. Useful for scoring the beggining of a behavior and ending, or its length. If set to 'single' will save timestamps as a list of singular timestamps. Useful for scoring the occurence of a behavior.",
            "save_frame_or_time": "Either frame or timestamp. If set to 'frame' will save frame numbers as the timestamp. If set to 'time' will save video position in milliseconds as the timestamp.",
            "text_color": "RGB color of the text to be displayed ontop the video",
            "show_current_frame_number": "Show the current frame number on the video",
        }

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)


class Playback(AbstSettings):
    seek_video_small: int = 1
    seek_video_medium: int = 100
    seek_video_large: int = 1000
    playback_speed_modulator: int = 5
    seek_timestamp_small: int = 1
    seek_timestamp_medium: int = 10
    seek_timestamp_large: int = 100

    @staticmethod
    def help_text():
        return {
            "seek_video_small": "Amount of frames to seek forward/backward when pressing the seek small key binding",
            "seek_video_medium": "Amount of frames to seek forward/backward when pressing the seek medium key binding",
            "seek_video_large": "Amount of frames to seek forward/backward when pressing the seek large key binding",
            "playback_speed_modulator": "Amount to increase/decrease fps when playback speed is changed",
            "seek_timestamp_small": "Amount of timestamps to seek forward/backward when pressing the increment selected timestamp by seek small",
            "seek_timestamp_medium": "Amount of timestamps to seek forward/backward when pressing the increment selected timestamp by seek medium",
            "seek_timestamp_large": "Amount of timestamps to seek forward/backward when pressing the increment selected timestamp by seek large",
        }

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)


class KeyBindings(AbstSettings):
    exit: str = "Q"
    help: str = "H"
    save_timestamp: str = "S"
    show_stats: str = "T"
    undo: str = "Ctrl+Z"
    redo: str = "Ctrl+Shift+Z"
    toggle_play: str = "Space"
    seek_forward_small_frames: str = "D"
    seek_back_small_frames: str = "A"
    seek_forward_medium_frames: str = "Shift+D"
    seek_back_medium_frames: str = "Shift+A"
    seek_forward_large_frames: str = "P"
    seek_back_large_frames: str = "O"
    seek_to_first_frame: str = "1"
    seek_to_last_frame: str = "0"
    increase_playback_speed: str = "X"
    decrease_playback_speed: str = "Z"
    increment_selected_timestamp_by_seek_small: str = "down"
    decrement_selected_timestamp_by_seek_small: str = "up"
    increment_selected_timestamp_by_seek_medium: str = "shift+down"
    decrement_selected_timestamp_by_seek_medium: str = "shift+up"
    increment_selected_timestamp_by_seek_large: str = "ctrl+down"
    decrement_selected_timestamp_by_seek_large: str = "ctrl+up"
    move_to_last_onset_offset: str = "left"
    move_to_next_onset_offset: str = "right"
    move_to_last_timestamp: str = "Shift+left"
    move_to_next_timestamp: str = "Shift+right"
    select_current_timestamp: str = "Enter"
    delete_selected_timestamp: str = "delete"

    @staticmethod
    def help_text():
        return {
            "exit": "Quit the program and save all timestamps to file",
            "help": "Display the help menu",
            "save_timestamp": "Save timestamp of current frame",
            "show_stats": "Display the current stats",
            "undo": "Undo the last action",
            "redo": "Redo the last undo",
            "undo_last_timestamp_save": "Undo last timestamp save",
            "toggle_play": "Pause/play",
            "seek_forward_small_frames": "Seek forward by seek_small frames",
            "seek_back_small_frames": "Seek backward by seek_small frames",
            "seek_forward_medium_frames": "Seek forward by seek_medium frames",
            "seek_back_medium_frames": "Seek backward by seek_medium frames",
            "seek_forward_large_frames": "Seek forward by seek_large frames",
            "seek_back_large_frames": "Seek backward by seek_large frames",
            "seek_to_first_frame": "Seek to the first frame",
            "seek_to_last_frame": "Seek to the last frame",
            "increase_playback_speed": "Increase playback speed by playback_speed_modulator",
            "decrease_playback_speed": "Decrease playback speed by playback_speed_modulator",
            "increment_selected_timestamp_by_seek_small": "Increment the selected timestamp by seek_timestamp_small",
            "decrement_selected_timestamp_by_seek_small": "Decrement the selected timestamp by seek_timestamp_small",
            "increment_selected_timestamp_by_seek_medium": "Increment the selected timestamp by seek_timestamp_medium",
            "decrement_selected_timestamp_by_seek_medium": "Decrement the selected timestamp by seek_timestamp_medium",
            "increment_selected_timestamp_by_seek_large": "Increment the selected timestamp by seek_timestamp_large",
            "decrement_selected_timestamp_by_seek_large": "Decrement the selected timestamp by seek_timestamp_large",
            "move_to_last_onset_offset": "Move to the last onset/offset timestamp",
            "move_to_next_onset_offset": "Move to the next onset/offset timestamp",
            "move_to_last_timestamp": "Move to the last timestamp",
            "move_to_next_timestamp": "Move to the next timestamp",
            "select_current_timestamp": "Select the current timestamp",
            "delete_selected_timestamp": "Delete the selected timestamp",
        }

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)

    def items(self):
        return self.__dict__.items()


class TDTData:
    def __init__(self, block: dict):
        """
        A class to access the data of a TDT block

        Parameters
        ----------
        block : dict
            The TDT block. This is the output of `tdt.read_block()`

        Attributes
        ----------
        tankpath : str
            The path to the tank file
        blockname : str
            The name of the block
        blockpath : str
            The path to the block file
        start_date : str
            The start date of the block
        utc_start_time : str
            The start time of the block in UTC
        stop_date : str
            The stop date of the block
        utc_stop_time : str
            The stop time of the block in UTC
        duration : float
            The duration of the block in seconds
        stream_channel : str
            The channel of the stream
        snip_channel : str
            The channel of the snips
        epocs : dict
            The epocs
        streams : dict
            The streams
        snips : dict
            The snips
        scalars : dict
            The scalars
        video_path : Union[None, str, List[str]]
            The path to the video file(s)
        """

        # the block is a `TDStruct` type which is just a python dict with an overloaded __repr__
        # the block contains a list of keys which are the names of the different data types
        # each data type is itself another TDTStruct till we get to the data itself

        # for now we will NOT convert the TDStruct to an object (we may change this later)
        # we will simply provide methods to access the data in the TDStruct through this class
        self.block = block

    @property
    def tankpath(self):
        try:
            return self.block.info.tankpath
        except:
            return None

    @property
    def blockname(self):
        try:
            return self.block.info.blockname
        except:
            return None

    @property
    def blockpath(self):
        return os.path.join(self.tankpath, self.blockname)

    @property
    def start_date(self):
        try:
            return self.block.info.start_date
        except:
            return None

    @property
    def utc_start_time(self):
        try:
            return self.block.info.utc_start_time
        except:
            return None

    @property
    def stop_date(self):
        try:
            return self.block.info.stop_date
        except:
            return None

    @property
    def utc_stop_time(self):
        try:
            return self.block.info.utc_stop_time
        except:
            return None

    @property
    def duration(self):
        try:
            return self.block.info.duration
        except:
            return None

    @property
    def stream_channel(self):
        try:
            return self.block.info.stream_channel
        except:
            return None

    @property
    def snip_channel(self):
        try:
            return self.block.info.snip_channel
        except:
            return None

    @property
    def epocs(self):
        """epocs are values stored with onset and offset timestamps that can be used to create time-based filters on your data. If Runtime Notes were enabled in Synapse, they will appear in data.epocs.Note. The notes themselves will be in data.epocs.Note.notes."""
        return self.block.epocs

    @property
    def streams(self):
        """streams are continuous single channel or multichannel recordings"""
        return self.block.streams

    @property
    def snips(self):
        """snips are short snippets of data collected on a trigger. For example, action potentials recorded around threshold crossings in the Spike Sorting gizmos, or fixed duration snippets recorded by the Strobe Store gizmo.

        This structure includes the waveforms, channel numbers, sort codes, trigger timestamps, and sampling rate.
        """
        return self.block.snips

    @property
    def scalars(self):
        """scalars are similar to epocs but can be single or multi-channel values and only store an onset timestamp when triggered"""
        return self.block.scalars

    @property
    def video_path(self):
        """
        We will assume that the video file is in the same folder as the tank file.

        Returns
        -------
        str
            The path to the video file

        Raises
        ------
        ValueError
            If there is no video file
        ValueError
            If there are multiple video files
        """
        video_files = [
            f
            for f in os.listdir(self.blockpath)
            if f.endswith(".mp4") or f.endswith(".avi") or f.endswith(".mov")
        ]
        if len(video_files) == 0:
            raise ValueError("There is no video file")
        elif len(video_files) > 1:
            raise ValueError("There are multiple video files")
        else:
            return os.path.join(self.blockpath, video_files[0])

    def create_frame_ts(
        self, epoch_type: Union[Literal["onset"], Literal["offset"]] = "onset"
    ) -> dict:
        """
        Creates a dictionary of the timestamps for each video frame. The keys are the frame numbers and the values are the timestamps. The timestamps are either the onset or offset timestamps of the epoc specified by `epoch_type`.

        Returns
        -------
        Union[None, dict  ]
            A dictionary of the timestamps for each video frame

        Raises
        ------
        ValueError
            If there is no video file
        """
        frame_ts = {}
        if self.video_path is None:
            raise ValueError("There is no video file")
        else:
            if epoch_type == "onset":
                for i in range(len(self.epocs.Cam1.onset)):
                    t = self.epocs.Cam1.onset[i]
                    frame_ts[i] = t
            elif epoch_type == "offset":
                for i in range(len(self.epocs.Cam1.offset)):
                    t = self.epocs.Cam1.offset[i]
                    frame_ts[i] = t
            else:
                raise ValueError('epoch_type must be either "onset" or "offset"')

        return frame_ts


class OOBehaviorItemSetting(BaseModel):
    onset: int = 0
    offset: int = 0


class BehaviorTrackSetting(BaseModel):
    name: str = ""
    color: str = "#FFFFFF"
    behavior_items: List[OOBehaviorItemSetting] = []


class ScoringData(AbstSettings):
    """Represents the data associated with a scoring session"""
    uid: uidT = ""
    video_file_location: str = ""
    video_file_name: str = ""
    timestamp_file_location: str = ""
    timestamp_data: dict = {}
    scoring_type: Literal["onset/offset", "single"] = "onset/offset"
    behavior_tracks: List[BehaviorTrackSetting] = []

class ProjectSettings(AbstSettings):
    """This will be an individual project within the application settings. Each project will have its own settings file."""
    uid: uidT = Field(default_factory=uuid4)
    name: str = ""
    scorer: str = ""
    created: dtT = Field(default_factory=datetime.datetime.now)
    modified: dtT = Field(default_factory=datetime.datetime.now)
    file_location: str = ""
    layouts: Dict[str, Any] = {
        "Main": {
            "geometry": "AdnQywADAAAAAAJTAAABgAAACCQAAAUJAAACUwAAAZ8AAAgkAAAFCQAAAAAAAAAACgAAAAJTAAABnwAACCQAAAUJ",
            "dock_state": "AAAA/wAAAAH9AAAAAwAAAAAAAASSAAACOvwCAAAAAfsAAAAeAHYAaQBkAGUAbwBfAHAAbABhAHkAZQByAF8AZAB3AQAAAB0AAAI6AAAAZgD///8AAAABAAABPAAAAjr8AgAAAAH7AAAAGgB0AGkAbQBlAHMAdABhAG0AcABzAF8AZAB3AQAAAB0AAAI6AAAApgD///8AAAADAAAF0gAAAPv8AQAAAAH7AAAAFgB0AGkAbQBlAGwAaQBuAGUAXwBkAHcBAAAAAAAABdIAAACGAP////////wAAAI6AAAABAAAAAQAAAAIAAAACPwAAAAA",
            "dock_widgets": {
                "timeline_dw": {
                    "geometry": "AdnQywADAAAAAAAAAAACWwAABdEAAANVAAAAAAAAAAD//////////wAAAAAAAAAACgAAAAAAAAACWwAABdEAAANV",
                    "visible": True
                },
                "timestamps_dw": {
                    "geometry": "AdnQywADAAAAAASWAAAAHQAABdEAAAJWAAAAAAAAAAD//////////wAAAAAAAAAACgAAAASWAAAAHQAABdEAAAJW",
                    "visible": True
                },
                "video_player_dw": {
                    "geometry": "AdnQywADAAAAAAAAAAAAHQAABJEAAAJWAAAAAAAAAAD//////////wAAAAAAAAAACgAAAAAAAAAAHQAABJEAAAJW",
                    "visible": True
                }
            }
        }
    },
    playback: Playback = Playback()
    key_bindings: KeyBindings = KeyBindings()
    scoring_data: ScoringData = ScoringData()

    # when the project is loaded from a file the uid and created/modified dates will be strings. Convert them to the correct type
    @field_validator("created", "modified", mode="after")
    def model_validator(cls, values):
        if isinstance(values["created"], str):
            values["created"] = datetime.datetime.fromisoformat(values["created"])
        if isinstance(values["modified"], str):
            values["modified"] = datetime.datetime.fromisoformat(values["modified"])
        if isinstance(values["layouts"], list):
            values["layouts"] = values["layouts"][0]
        return values

    @staticmethod
    def help_text():
        return {
            "uid": "Unique identifier for the project",
            "name": "Name of the project",
            "scorer": "Name of the scorer",
            "created": "Date the project was created",
            "modified": "Date the project was last modified",
            "file_location": "Location of the settings file",
        }
    

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)

    def load_from_file(self, file=None) -> Union[str, None]:
        if file is None:
            file = self.file_location
        if not os.path.exists(file):
            log.error(f"File {file} does not exist")
            raise FileNotFoundError(f"File {file} does not exist")

        with zipfile.ZipFile(file, "r") as zipf:
            with zipf.open("settings.json", "r") as f:
                project_settings = json.load(f)
        
        if project_settings is None:
            log.error(f"File {file} is empty")
            raise ValueError(f"File {file} is empty")
        # FIXME: make this fault tolerant
        self.uid = project_settings.get("uid", "")
        self.name = project_settings.get("name", "")
        self.scorer = project_settings.get("scorer", "")
        self.created = project_settings.get("created", datetime.datetime.now())
        self.modified = project_settings.get("modified", datetime.datetime.now())
        self.file_location = project_settings.get("file_location", "")
        self.layouts = project_settings.get("layouts", {})
        self.playback = Playback(**project_settings["playback"])
        self.key_bindings = KeyBindings(**project_settings["key_bindings"])
        self.scoring_data = ScoringData(**project_settings["scoring_data"])

    def save(self, file=None):
        if file is None:
            file = self.file_location
        if not os.path.exists(os.path.dirname(file)):
            os.makedirs(os.path.dirname(file))
        try:
            dump = json.dumps(self.model_dump(), indent=4, cls=CustomEncoder)
        except Exception as e:
            log.error(f"Error dumping project settings: {e}")
            # propagate the error
            raise e
        with zipfile.ZipFile(file, "w") as zipf:
            zipf.writestr("settings.json", dump)

class ApplicationSettings(AbstSettings):
    """These compose the overall settings of the application. There can be multiple projects within the application settings, though the spplication setting shouldn't change."""
    version: str = ""
    file_location: str = user_data_dir("settings.json")
    theme: Literal["dark", "light"] = "dark"
    joke_type: Literal["programming", "dad"] = "programming"
    window_size: Tuple[int, int] = (1280, 720)
    window_position: Tuple[int, int] = (0, 0)
    projects: List[Tuple[uidT, project_file_locationT]] = [] # list of tuples with "uid" and "file_location"

    def load(self, file_location):
        with open(file_location, "r") as f:
            project_settings = json.load(f)
        if project_settings is None:
            return
        
        self.version = project_settings.get("version", "")
        self.theme = project_settings.get("theme", "dark")
        self.joke_type = project_settings.get("joke_type", "programming")
        self.window_size = tuple(project_settings.get("window_size", (1280, 720)))
        self.window_position = tuple(project_settings.get("window_position", (0, 0)))
        self.projects = [tuple(p) for p in project_settings.get("projects", ())]

    @field_validator("projects", mode="after")
    def model_validator(cls, values):
        for project in values["projects"]:
            if not os.path.exists(project[1]):
                values["projects"].remove(project)
        return values

    def save(self, file_location=None):
        if file_location is None:
            file_location = self.file_location
        if not os.path.exists(os.path.dirname(file_location)):
            os.makedirs(os.path.dirname(file_location))
        with open(file_location, "w") as f:
            json.dump(self.model_dump(), f, indent=4, cls=CustomEncoder)

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)

    def help_text(self):
        return {
            "project_name": "Name of the project",
            "settings_file_location": "Location of the settings file",
            "video_file_location": "Location of the video file",
            "video_file_name": "Name of the video file",
            "timestamp_file_location": "Location of the timestamp file",
            "theme": "Theme of the application",
            "joke_type": "I hope this is self explanatory",
            "window_size": "Size of the main window",
            "window_position": "Position of the main window",
            "scoring_data": "Data associated with the scoring session",
            "behavior_tracks": "Tracks of behaviors",
        }

