import datetime
import json
import logging
import os
import sys
import zipfile
from typing import Any, Dict, List, Literal, Tuple, TypeVar, Union
from uuid import UUID, uuid4
import subprocess
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator
from qtpy.QtCore import QByteArray
import sentry_sdk
log = logging.getLogger()

uidT = TypeVar("uidT", str, UUID)
project_file_locationT = TypeVar("project_file_locationT", str, os.PathLike)
dtT = TypeVar("dtT", datetime.datetime, str)

VERSION = os.environ.get("VERSION", "")
if VERSION == "":
    raise ValueError("VERSION environment variable not set")


def user_data_dir(file_name: Union[str, None] = None):
    r"""
    Get OS specific data directory path for a file in the Video Scoring application data directory. Will be version specific.

    Parameters
    ----------
    file_name: Union[str, None]
        The name of the file to join with the data directory path, if None will return the data directory path

    Returns
    -------
    `str`
        Path to the data directory or the file in the data directory

    Notes
    -----
    Typical user data directories are:
        macOS:    ~/Library/Application Support/Video Scoring/<version>
        Unix:     ~/.local/share/Video Scoring/<version>
        Unix XDG:      $XDG_DATA_HOME/Video Scoring/<version>
        Win 10:   C:\Users\<username>\AppData\Local\Video Scoring\<version>

    For Unix, we follow the XDG spec and support $XDG_DATA_HOME if defined.
    """
    # get os specific path
    if sys.platform.startswith("win") or sys.platform == 'cygwin' or sys.platform == 'msys':
        os_path = os.getenv("LOCALAPPDATA")
    elif sys.platform.startswith("darwin"):
        os_path = "~/Library/Application Support"
    else:
        # linux if $XDG_DATA_HOME is defined, use it
        os_path = os.getenv("XDG_DATA_HOME", "~/.local/share")

    # join with Video Scoring dir and version
    path = os.path.join(str(os_path), "Video Scoring", VERSION)
    if file_name is None:
        return path
    else:
        return os.path.join(path, file_name)

def cmd_run(cmd):
  try:
    return subprocess.run(cmd, shell=True, capture_output=True, check=True, encoding="utf-8") \
                     .stdout \
                     .strip()
  except:
    return ""

def get_device_id():

    if sys.platform.startswith('linux'):
        return cmd_run('cat /var/lib/dbus/machine-id') or cmd_run('cat /etc/machine-id')

    if sys.platform == 'darwin':
        return cmd_run("ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'")

    if sys.platform.startswith('openbsd') or sys.platform.startswith('freebsd'):
        return cmd_run('cat /etc/hostid') or cmd_run('kenv -q smbios.system.uuid')

    if sys.platform == 'win32' or sys.platform == 'cygwin' or sys.platform == 'msys':
        return cmd_run('wmic csproduct get uuid').split('\n')[2].strip()


class SettingsEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return obj.__str__()
        if isinstance(obj, datetime.datetime):
            return obj.__str__()
        if isinstance(obj, QByteArray):
            return obj.data().decode()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


class CustomDecoder(json.JSONDecoder):
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(
            self, object_hook=self.dict_to_object, *args, **kwargs
        )

    def dict_to_object(self, d):
        if "uid" in d:
            d["uid"] = UUID(d["uid"])
        if "created" in d:
            d["created"] = datetime.datetime.fromisoformat(d["created"])
        if "modified" in d:
            d["modified"] = datetime.datetime.fromisoformat(d["modified"])
        if "layouts" in d:
            for layout in d["layouts"]:
                d["layouts"][layout] = Layout(**d["layouts"][layout])
        if "mask" in d:
            d["mask"] = np.array(d["mask"])
        if "reference" in d:
            d["reference"] = np.array(d["reference"])
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
    save_unsure_timestamp: str = "Shift+S"
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
    set_marker_in: str = "U"
    set_marker_out: str = "I"

    @staticmethod
    def help_text():
        return {
            "exit": "Quit the program and save all timestamps to file",
            "help": "Display the help menu",
            "save_timestamp": "Save timestamp of current frame",
            "save_unsure_timestamp": "Save timestamp of current frame as unsure",
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


class TDTData(BaseModel):
    """
    A class to serialize the data of a TDT block.

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
    video_path : Union[None, str, List[str]]
        The path to the video file(s)
    frame_ts_dict : Union[None, Dict[int, float]]
        A dictionary of the TDT timestamps for each video frame
    """

    tankpath: str = ""
    blockname: str = ""
    blockpath: str = ""
    start_date: str = ""
    utc_start_time: str = ""
    stop_date: str = ""
    utc_stop_time: str = ""
    duration: str = ""
    video_path: Union[None, str, List[str]] = None
    frame_ts_dict: Union[None, Dict[int, float]] = None

    def get_video_path(self):
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

    def get_frame_ts(
        self,
        block: dict,
        epoch_type: Union[Literal["onset"], Literal["offset"]] = "onset",
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

        if epoch_type == "onset":
            for i in range(len(block.epocs.Cam1.onset)):
                t = block.epocs.Cam1.onset[i]
                frame_ts[i] = t
        elif epoch_type == "offset":
            for i in range(len(block.epocs.Cam1.offset)):
                t = block.epocs.Cam1.offset[i]
                frame_ts[i] = t
        else:
            raise ValueError('epoch_type must be either "onset" or "offset"')

        return frame_ts

    def load_from_dict(self, data: dict):
        self.tankpath = data.get("tankpath", None)
        self.blockname = data.get("blockname", None)
        self.blockpath = data.get("blockpath", None)
        self.video_path = data.get("video_path", None)
        self.start_date = data.get("start_date", None)
        self.utc_start_time = data.get("utc_start_time", None)
        self.stop_date = data.get("stop_date", None)
        self.utc_stop_time = data.get("utc_stop_time", None)
        self.duration = data.get("duration", None)
        self.video_path = data.get("video_path", None)
        self.frame_ts_dict = data.get("frame_ts_dict", None)

    def load_from_block(self, block: dict):
        # the block is a `TDStruct` type which is just a python dict with an overloaded __repr__
        # the block contains a list of keys which are the names of the different data types
        # each data type is itself another TDTStruct till we get to the data itself

        # for now we will NOT convert the TDStruct to an object (we may change this later)
        # we will simply provide methods to access the data in the TDStruct through this class
        self.tankpath = str(block.info.tankpath)
        self.blockname = str(block.info.blockname)
        self.blockpath = os.path.join(self.tankpath, self.blockname)
        self.start_date = str(block.info.start_date)
        self.utc_start_time = str(block.info.utc_start_time)
        self.stop_date = str(block.info.stop_date)
        self.utc_stop_time = str(block.info.utc_stop_time)
        self.duration = str(block.info.duration)
        self.video_path = self.get_video_path()
        self.frame_ts_dict = self.get_frame_ts(block=block)


class OOBehaviorItemSetting(BaseModel):
    onset: int = 0
    offset: int = 0
    unsure: bool = False


class BehaviorTrackSetting(BaseModel):
    name: str = ""
    color: str = "#FFFFFF"
    behavior_items: List[OOBehaviorItemSetting] = []


class ScoringData(AbstSettings):
    """Represents the data associated with a scoring session"""

    uid: uidT = Field(default_factory=uuid4)
    video_file_location: str = ""
    timestamp_file_location: str = ""
    timestamp_data: dict = {}
    tdt_data: Union[TDTData, None] = None
    scoring_type: Literal["onset/offset", "single"] = "onset/offset"
    behavior_tracks: List[BehaviorTrackSetting] = []

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)


class ROI(BaseModel):
    uid: str = ""
    mask: Union[None, np.ndarray] = None

    class Config:
        arbitrary_types_allowed = True


class Crop(BaseModel):
    x1: int = 0
    x2: int = 0
    y1: int = 0
    y2: int = 0


class ROI_Analysis(BaseModel):
    threshold: float = 170.0
    method: Literal["Absolute", "Light", "Dark"] = "Absolute"
    roi: Union[None, ROI] = None
    crop: Union[None, Crop] = None
    reference: Union[None, np.ndarray] = None
    diff_dict: Union[None, dict[int, bool]] = None

    class Config:
        arbitrary_types_allowed = True


class LocationAnalysis(BaseModel):
    """Represents the data associated with a analysis session"""

    region_names: Union[None, List[str]] = None
    loc_thresh: float = 99.5
    use_window: bool = True
    window_size: int = 100
    window_weight: float = 0.9
    method: Literal["dark", "abs", "light"] = "dark"
    rmv_wire: bool = False
    wire_krn: int = 5
    location_df: Union[None, pd.DataFrame] = None
    rois: List[ROI] = []
    crop: Union[None, Crop] = None

    class Config:
        arbitrary_types_allowed = True


class AnalysisSettings(BaseModel):
    """Represents the data associated with a analysis session"""

    video_file_location: str = ""
    start: int = 0
    end: Union[None, int] = None
    dsmpl: float = 1.0
    roi_analysis: ROI_Analysis = ROI_Analysis()
    location_analysis: LocationAnalysis = LocationAnalysis()

    class Config:
        arbitrary_types_allowed = True

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)

    def help_text(self):
        return {
            "file": "Path to the video file",
            "start": "Start frame",
            "end": "End frame",
            "region_names": "List of region names",
            "dsmpl": "Downsample factor",
            "stretch": "Stretch factor",
            "scale": "Scale factor",
            "reference": "Reference frame",
            "loc_thresh": "Represents a percentile threshold and can take on values between 0-100.  Each frame is compared to the reference frame.  Then, to remove the influence of small fluctuations, any differences below a given percentile (relative to the maximum difference) are set to 0.  We use a value of 99.5 with good success.",
            "use_window": "This parameter is incredibly helpful if objects other than the animal temporarily enter the field of view during tracking (such as an experimenter’s hand manually delivering a stimulus or reward).  When use_window is set to True, a square window with the animal's position on the prior frame at its center is given more weight when searching for the animal’s location (because an animal presumably can't move far from one frame to the next).  In this way, the influence of objects entering the field of view can be avoided.  If use_window is set to True, the user should consider window_size and window_weight.",
            "window_size": "This parameter only impacts tracking when use_window is set to True.  This defines the size of the square window surrounding the animal that will be more heavily weighted in pixel units.  We typically set this to 2-3 times the animal’s size (if an animal is 100 pixels at its longest, we will set window_size to 200).  Note that to determine the size of the animal in pixels, the user can reference any image of the arena presented in ezTrack, which has the pixel coordinate scale on its axes.",
            "window_weight": "This parameter only impacts tracking when use_window is set to True.  When window_weight is set to 1, pixels outside of the window are not considered at all; at 0, they are given equal weight. Notably, setting a high value that is still not equal to 1 (e.g., 0.9) should allow ezTrack to more rapidly find the animal if, by chance, it moves out of the window.",
            "method": "This parameter determines the luminosity of the object to search for relative to the background and accepts values of 'abs', 'light', and 'dark'. Option 'abs' does not take into consideration whether the animal is lighter or darker than the background and will therefore track the animal across a wide range of backgrounds. 'light' assumes the animal is lighter than the background, and 'dark' assumes the animal is darker than the background. Option 'abs' generally works well, but there are situations in which you may wish to use the others.  For example, if a tether is being used that is opposite in color to the animal (a white wire and a black mouse), the ‘abs’ method is much more likely to be biased by the wire, whereas option ‘dark’ will look for the darker mouse.",
            "rmv_wire": "Ifset to True, an algorithm is used to attempt to remove wires from the field of view.  If rmv_wire is set to True, the user should consider wire_krn.",
            "wire_krn": "This parameter only impacts tracking when rmv_wire is set to True. This value should be set between the width of the wire and the width of the animal, in pixel units. We typically set this to 5-10.  Note that to determine the size of the animal in pixels, the user can reference any image which has the pixel coordinate scale on its axes.",
        }


class DockWidgetState(BaseModel):
    geometry: str = ""
    visible: bool = True


class Layout(BaseModel):
    geometry: str = ""
    dock_state: str = ""
    dock_widgets: dict[str, DockWidgetState] = {}


class ProjectSettings(AbstSettings):
    """This will be an individual project within the application settings. Each project will have its own settings file."""

    uid: uidT = Field(default_factory=uuid4)
    name: str = ""
    scorer: str = ""
    created: dtT = Field(default_factory=datetime.datetime.now)
    modified: dtT = Field(default_factory=datetime.datetime.now)
    file_location: str = ""
    layouts: dict[str, Layout] = {}
    playback: Playback = Playback()
    key_bindings: KeyBindings = KeyBindings()
    scoring_data: ScoringData = ScoringData()
    analysis_settings: AnalysisSettings = AnalysisSettings()
    last_layout: Union[Layout, None] = None

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
                project_settings = json.load(f, cls=CustomDecoder)

        if project_settings is None:
            log.error(f"File {file} is empty")
            raise ValueError(f"File {file} is empty")
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
        if project_settings.get("analysis_settings", None) is not None:
            self.analysis_settings = AnalysisSettings(
                **project_settings["analysis_settings"]
            )
        else:
            self.analysis_settings = AnalysisSettings()
        if project_settings["last_layout"] is not None:
            self.last_layout = Layout(**project_settings["last_layout"])
        self.load_default_layouts()
        sentry_sdk.add_breadcrumb(
            category="project_settings", message=f"loaded project_settings file: {str(self.uid)} - {self.name}", level="info"
        )
        
    def load_default_layouts(self):
        if "Main" not in self.layouts:
            self.layouts["Main"] = Layout(
                geometry="AdnQywADAAAAAAHEAAABMQAACCoAAATXAAABxAAAAVAAAAgqAAAE1wAAAAAAAAAACgAAAAHEAAABUAAACCoAAATX",
                dock_state="AAAA/wAAAAH9AAAAAwAAAAAAAAAAAAAAAPwCAAAAAvsAAAAWAHMAZQB0AHQAaQBuAGcAcwBfAGQAdwAAAAAA/////wAAAcMA////+wAAAB4AdgBpAGQAZQBvAF8AcABsAGEAeQBlAHIAXwBkAHcBAAAAAP////8AAAAAAAAAAAAAAAEAAAI0AAACCPwCAAAAAfsAAAAaAHQAaQBtAGUAcwB0AGEAbQBwAHMAXwBkAHcBAAAAHQAAAggAAACmAP///wAAAAMAAAZnAAABSvwBAAAAAfsAAAAWAHQAaQBtAGUAbABpAG4AZQBfAGQAdwEAAAAAAAAGZwAAAIYA////AAAELwAAAggAAAAEAAAABAAAAAgAAAAI/AAAAAA=",
                dock_widgets={
                    "video_player_dw": DockWidgetState(
                        geometry="AdnQywADAAAAAAAAAAAAHQAABC4AAAIkAAAAAAAAAAD//////////wAAAAAAAAAACgAAAAAAAAAAHQAABC4AAAIk",
                        visible=True,
                    ),
                    "timestamps_dw": DockWidgetState(
                        geometry="AdnQywADAAAAAAQzAAAAHQAABmYAAAIkAAAAAAAAAAD//////////wAAAAAAAAAACgAAAAQzAAAAHQAABmYAAAIk",
                        visible=True,
                    ),
                    "timeline_dw": DockWidgetState(
                        geometry="AdnQywADAAAAAAAAAAACKQAABmYAAANyAAAAAAAAAAD//////////wAAAAAAAAAACgAAAAAAAAACKQAABmYAAANy",
                        visible=True,
                    ),
                    "settings_dw": DockWidgetState(
                        geometry="AdnQywADAAAAAAABAAAAHAAAAoAAAAH7AAAAAAAAAAD//////////wAAAAAAAAAACgAAAAABAAAAHAAAAoAAAAH7",
                        visible=False,
                    ),
                },
            )

    def save(self, file=None):
        if file is None:
            file = self.file_location
        if not os.path.exists(os.path.dirname(file)):
            os.makedirs(os.path.dirname(file))
        try:
            # set the modified date
            self.modified = datetime.datetime.now()
            dump = json.dumps(self.model_dump(), indent=4, cls=SettingsEncoder)
        except Exception as e:
            log.error(f"Error dumping project settings: {e}")
            # propagate the error
            raise e
        with zipfile.ZipFile(file, "w") as zipf:
            zipf.writestr("settings.json", dump)
        sentry_sdk.add_breadcrumb(
            category="project_settings", message=f"saved project_settings file: {str(self.uid)} - {self.name}", level="info"
        )


class ApplicationSettings(AbstSettings):
    """These compose the overall settings of the application. There can be multiple projects within the application settings"""

    version: str = VERSION
    device_id: str = Field(default_factory=get_device_id)
    file_location: str = user_data_dir("settings.json")
    theme: Literal["dark", "light"] = "dark"
    joke_type: Literal["programming", "dad"] = "programming"
    window_size: Tuple[int, int] = (1280, 720)
    window_position: Tuple[int, int] = (0, 0)
    projects: List[
        Tuple[uidT, project_file_locationT]
    ] = []  # list of tuples with "uid" and "file_location"

    def load(self, file_location):
        with open(file_location, "r") as f:
            project_settings = json.load(f)
        if project_settings is None:
            return

        self.version = project_settings.get("version", "")
        self.device_id = get_device_id()
        self.file_location = project_settings.get("file_location", "")
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
            json.dump(self.model_dump(), f, indent=4, cls=SettingsEncoder)
        sentry_sdk.add_breadcrumb(
            category="application_settings", message=f"saved application_settings file: {file_location}", level="info"
        )
        return file_location

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
