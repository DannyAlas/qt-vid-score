from typing import Union, List, Dict, Tuple, Literal, TypeAlias, Any
from dataclasses import dataclass


@dataclass
class BlockInfo:
    tankpath: str
    blockname: str
    blockpath: str
    start_date: str
    utc_start_time: str
    stop_date: str
    utc_stop_time: str
    duration: str
    video_path: str


class Block:
    epocs: Dict[str, Any]
    streams: Dict[str, Any]
    info: BlockInfo