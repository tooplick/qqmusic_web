from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class SongInfo:
    """歌曲信息数据类"""
    mid: str
    name: str
    singers: str
    vip: bool
    album: str
    album_mid: str
    interval: int
    raw_data: Optional[Dict[str, Any]] = None