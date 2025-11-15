from dataclasses import dataclass

@dataclass
class DownloadResult:
    """下载结果数据类"""
    filename: str
    quality: str
    filepath: str
    cached: bool = False
    metadata_added: bool = False