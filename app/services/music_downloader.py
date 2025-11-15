import logging
from pathlib import Path
from typing import Optional
from qqmusic_api.song import get_song_urls, SongFileType
from qqmusic_api.lyric import get_lyric
from ..models import SongInfo, DownloadResult
from .file_manager import FileManager
from .metadata_manager import MetadataManager

logger = logging.getLogger("qqmusic_web")

class MusicDownloader:
    """音乐下载器"""

    def __init__(self, config, credential_manager, file_manager, metadata_manager):
        self.config = config
        self.credential_manager = credential_manager
        self.file_manager = file_manager
        self.metadata_manager = metadata_manager

    async def download_song(self, song_info: SongInfo, prefer_flac: bool = False,
                            add_metadata: bool = True) -> Optional[DownloadResult]:
        """下载歌曲"""
        # 设置下载策略
        if prefer_flac:
            quality_order = [
                (SongFileType.FLAC, "FLAC"),
                (SongFileType.MP3_320, "320kbps"),
                (SongFileType.MP3_128, "128kbps")
            ]
        else:
            quality_order = [
                (SongFileType.MP3_320, "320kbps"),
                (SongFileType.MP3_128, "128kbps")
            ]

        safe_filename = self.file_manager.sanitize_filename(
            f"{song_info.name} - {song_info.singers}"
        )

        # 尝试不同音质
        for file_type, quality_name in quality_order:
            filepath = Path(self.config["MUSIC_DIR"]) / f"{safe_filename}{file_type.e}"

            # 检查缓存
            if filepath.exists():
                return DownloadResult(
                    filename=f"{safe_filename}{file_type.e}",
                    quality=quality_name,
                    filepath=str(filepath),
                    cached=True
                )

            logger.info(f"尝试下载 {quality_name}: {safe_filename}{file_type.e}")

            # 获取歌曲URL并下载
            urls = await get_song_urls(
                [song_info.mid],
                file_type=file_type,
                credential=self.credential_manager.credential
            )
            url = urls.get(song_info.mid)

            if not url:
                continue

            if isinstance(url, list):
                url = url[0]

            content = await self.file_manager.download_file_content(url)
            if content:
                with open(filepath, "wb") as f:
                    f.write(content)

                logger.info(f"下载成功 ({quality_name}): {filepath.name}")
                result = DownloadResult(
                    filename=f"{safe_filename}{file_type.e}",
                    quality=quality_name,
                    filepath=str(filepath),
                    cached=False
                )

                # 添加元数据
                if add_metadata and not result.cached:
                    await self._add_metadata(result, song_info, file_type)

                return result

        return None

    async def _add_metadata(self, result: DownloadResult, song_info: SongInfo,
                            file_type: SongFileType):
        """为下载的文件添加元数据"""
        if file_type not in [SongFileType.FLAC, SongFileType.MP3_320, SongFileType.MP3_128]:
            return

        try:
            lyrics_data = None
            try:
                lyrics_data = await get_lyric(song_info.mid)
            except Exception as e:
                logger.warning(f"获取歌词失败: {e}")

            # 使用智能封面获取方法，传递完整的原始歌曲数据
            metadata_success = await self.metadata_manager.add_metadata_to_file(
                Path(result.filepath),
                song_info,
                lyrics_data,
                song_info.raw_data  # 传递完整的原始歌曲数据用于封面获取
            )
            result.metadata_added = metadata_success

        except Exception as e:
            logger.error(f"添加元数据失败: {e}")
            result.metadata_added = False