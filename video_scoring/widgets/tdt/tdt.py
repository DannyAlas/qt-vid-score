from video_scoring.settings.base_settings import TDTSettings
import os
from typing import Union, List, Dict, Tuple, Literal, TypeAlias, Any
import numpy as np
from video_scoring.widgets.tdt._types import Block

class TDT:
    """
    A class to handle TDT data.
    THIS NEEDS TO BE REFACTORED!!!!

    Overwrite the tdt methods with our own methods as there are many issues with the tdt library.
    """

    def __init__(self, block: Block, settings: TDTSettings):
        self.block = block
        self.settings = settings
        if block:
            try:
                self.load_settings_from_block(block)
            except:
                pass

    def get_video_path(self):
        """
        We will assume that the video file is in the same folder as the tank file.

        Returns
        -------
        str
            The path to the video file

        """
        print("block", self.block.info.blockpath)
        video_files = [
            f
            for f in os.listdir(self.block.info.blockpath)
            if f.endswith(".mp4") or f.endswith(".avi") or f.endswith(".mov")
        ]
        return os.path.join(self.block.info.blockpath, video_files[0])

    def get_frame_ts(
        self,
        epoch_key: str = "Cam1",
        epoch_type: Union[Literal["onset"], Literal["offset"]] = "onset",
    ) -> dict:
        """
        Creates a dictionary of the timestamps for each video frame.

        Parameters
        ----------
        epoch_key : str, optional
            The key for the epoch to use, by default "Cam1"
        epoch_type : Union[Literal["onset"], Literal["offset"]], optional
            The type of the epoch, by default "onset"

        Returns
        -------
        Union[None, dict  ]
            A dictionary of the timestamps for each video frame

        Raises
        ------
        ValueError
            If the epoch does not exist
        """
        try:
            self.block.epocs[epoch_key][epoch_type]
        except KeyError:
            raise ValueError(f"Epoch {epoch_key} {epoch_type} does not exist")

        frame_ts = {}

        for i in range(len(self.block.epocs[epoch_key][epoch_type])):
            t = self.block.epocs[epoch_key][epoch_type][i]
            frame_ts[i] = t
        return frame_ts

    def get_time_ranges(self, epocs, values: list):
        """
        Given a list of values, find the time ranges (in seconds) of the valid values in the epocs data.

        Parameters
        ----------
        epocs : tdt.StructType
            The epocs struct from the TDT data. example: data.epocs.PtAB
        values : list
            A list of values to find the time ranges of. example: [65023, 65024]

        Returns
        -------
        np.2darray
            A 2d array with 2 rows and n columns where n is the number of valid time ranges. The first row is the onset and the second row is the offset of the time ranges.

        Raises
        ------
        Exception
            If there is an error in the values filter.
        """

        if len(values) == 1:
            # find valid time ranges
            try:
                # use this for numbers
                valid = np.isclose(epocs.data, values)
            except:
                try:
                    # use this for Note strings
                    valid = np.isin(epocs.notes, values)
                except:
                    raise Exception("Filter values are not valid.")
        else:
            # find valid time ranges
            try:
                # use this for numbers
                valid = np.isin(epocs.data, values)
            except:
                try:
                    # use this for Note strings
                    valid = np.isin(epocs.notes, values)
                except:
                    raise Exception("Filter values are not valid.")
        # get time ranges
        time_ranges = np.vstack((epocs.onset[valid], epocs.offset[valid]))
        return time_ranges

    def get_event_frames(
        self, event_codes: Dict[str, List[int]], epoch_key: str = "PtAB"
    ) -> Dict[str, List[Tuple[int, int]]]:
        """
        Given a TDT data struct and a dict of event codes, return a dict of event names and a list of tuples of (onset, o
        Parameters
        ----------
        event_codes : Dict[str, int]
            A dict of event names and their corresponding event codes. Example: {"Mag": [47103,48127]}
        epoch_key : str, optional
            The name of the epoch, by default "PtAB"

        Returns
        -------
        Dict[str, List[Tuple[int, int]]]
            A dict of key: event names value: list of tuples of (onset, offset) in frames.
        """
        frame_dict = (
            self.settings.frame_ts_dict
            if self.settings.frame_ts_dict
            else self.get_frame_ts()
        )

        frame_seconds = list(frame_dict.values())

        event_frames = {}
        for event, codes in event_codes.items():
            # get time ranges in seconds
            time_ranges = self.get_time_ranges(self.block.epocs[epoch_key], codes)

            # get frame_times
            frames = []
            for tr in time_ranges.T:
                # get the frame number of the closest frame to the time range
                # this will be the frame number of the onset
                onset = np.argmin(np.abs(frame_seconds - tr[0]))
                # this will be the frame number of the offset
                offset = np.argmin(np.abs(frame_seconds - tr[1]))
                frames.append((onset, offset + 1))

            event_frames[event] = frames
        return event_frames

    def get_marker_times(self):
        frames = self.get_event_frames({"Mag": [47103, 48127, 48607, 48639, 49151]})[
            "Mag"
        ]
        # convert the list of tuples to a list of only the onset
        return [f[0] for f in frames]

    def load_settings_from_dict(self, data: dict):
        self.settings.tankpath = data.get("tankpath", None)
        self.settings.blockname = data.get("blockname", None)
        self.settings.blockpath = data.get("blockpath", None)
        self.settings.video_path = data.get("video_path", None)
        self.settings.start_date = data.get("start_date", None)
        self.settings.utc_start_time = data.get("utc_start_time", None)
        self.settings.stop_date = data.get("stop_date", None)
        self.settings.utc_stop_time = data.get("utc_stop_time", None)
        self.settings.duration = data.get("duration", None)
        self.settings.video_path = data.get("video_path", None)
        self.settings.frame_ts_dict = data.get("frame_ts_dict", None)

    def load_settings_from_block(self, block: Block):
        self.block = block
        self.settings.tankpath = str(block.info.tankpath)
        self.settings.blockname = str(block.info.blockname)
        self.settings.blockpath = os.path.join(
            self.settings.tankpath, self.settings.blockname
        )
        self.settings.start_date = str(block.info.start_date)
        self.settings.utc_start_time = str(block.info.utc_start_time)
        self.settings.stop_date = str(block.info.stop_date)
        self.settings.utc_stop_time = str(block.info.utc_stop_time)
        self.settings.duration = str(block.info.duration)
        self.settings.video_path = self.get_video_path()
        self.settings.frame_ts_dict = self.get_frame_ts(block=block)
