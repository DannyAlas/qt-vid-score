from pydantic import BaseModel
from typing import Any, Literal, List, Tuple, Union
import json
import os
import sys
import logging

log = logging.getLogger()


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


class AbstSettings(BaseModel):
    @staticmethod
    def help_text() -> dict:
        raise NotImplementedError


class Scoring(AbstSettings):
    scoring_type: Literal["onset/offset", "single"] = "onset/offset"
    save_frame_or_time: Literal["frame", "timestamp"] = "frame"
    text_color: str = "255,0,0"

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
    undo_last_timestamp_save: str = "Ctrl+Z"
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
    select_onset_timestamp: str = "left"
    select_offset_timestamp: str = "right"
    set_player_to_selected_timestamp: str = "enter"
    delete_selected_timestamp: str = "delete"

    @staticmethod
    def help_text():
        return {
            "exit": "Quit the program and save all timestamps to file",
            "help": "Display the help menu",
            "save_timestamp": "Save timestamp of current frame",
            "show_stats": "Display the current stats",
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
            "select_onset_timestamp": "Select the onset timestamp",
            "select_offset_timestamp": "Select the offset timestamp",
            "set_player_to_selected_timestamp": "Set the player to the selected timestamp",
            "delete_selected_timestamp": "Delete the selected timestamp",
        }

    def __setattr__(self, name: str, value: Any) -> None:
        log.debug(f"Setting\t{name}\tto\t{value}")
        return super().__setattr__(name, value)

    def items(self):
        return self.__dict__.items()


class ProjectSettings(AbstSettings):
    project_name: str = ""
    settings_file_location: str = user_data_dir("settings.json")
    video_file_location: str = ""
    video_file_name: str = ""
    timestamp_file_location: str = ""
    scoring: Scoring = Scoring()
    playback: Playback = Playback()
    key_bindings: KeyBindings = KeyBindings()
    timestamps: Union[List[Tuple[float, float]], List[float]] = []
    window_size: Tuple[int, int] = (1280, 720)
    window_position: Tuple[int, int] = (0, 0)

    def load(self, file_location):
        with open(file_location, "r") as f:
            project_settings = json.load(f)
            self.project_name = project_settings["project_name"]
            self.settings_file_location = project_settings["settings_file_location"]
            self.video_file_location = project_settings["video_file_location"]
            self.video_file_name = project_settings["video_file_name"]
            self.scoring = Scoring(**project_settings["scoring"])
            self.playback = Playback(**project_settings["playback"])
            self.key_bindings = KeyBindings(**project_settings["key_bindings"])
            self.timestamps = project_settings["timestamps"]
            self.window_size = project_settings["window_size"]
            self.window_position = project_settings["window_position"]

    def save(self, file_location=None):
        if file_location is None:
            file_location = self.settings_file_location
        if not os.path.exists(os.path.dirname(file_location)):
            os.makedirs(os.path.dirname(file_location))
        with open(file_location, "w") as f:
            json.dump(self.model_dump(), f, indent=4)

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
            "window_size": "Size of the main window",
            "window_position": "Position of the main window",
        }
