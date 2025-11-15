import logging
from pathlib import Path
from typing import Optional, Dict, Any
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT
from mutagen.mp3 import MP3

logger = logging.getLogger("qqmusic_web")

class MetadataManager:
    """元数据管理器"""

    def __init__(self, config, cover_manager):
        self.config = config
        self.cover_manager = cover_manager

    async def add_metadata_to_flac(self, file_path: Path, song_info, 
                                   lyrics_data: dict = None, song_data: Dict[str, Any] = None) -> bool:
        """为FLAC文件添加封面和歌词"""
        try:
            audio = FLAC(file_path)

            # 添加基本元数据
            audio['title'] = song_info.name
            audio['artist'] = song_info.singers
            audio['album'] = song_info.album

            # 添加封面
            if song_data:
                cover_url = await self.cover_manager.get_valid_cover_url(song_data)
                if cover_url:
                    cover_data = await self.cover_manager.download_cover(cover_url)
                    if cover_data:
                        image = Picture()
                        image.type = 3  # 封面图片
                        image.mime = 'image/png' if cover_url.lower().endswith('.png') else 'image/jpeg'
                        image.desc = 'Cover'
                        image.data = cover_data

                        audio.clear_pictures()
                        audio.add_picture(image)
                        logger.info(f"已添加封面到 {file_path.name}")

            # 添加歌词
            if lyrics_data:
                lyric_text = lyrics_data.get('lyric', '')
                if lyric_text:
                    audio['lyrics'] = lyric_text
                    logger.info(f"已添加歌词到 {file_path.name}")

                trans_text = lyrics_data.get('trans', '')
                if trans_text:
                    audio['translyrics'] = trans_text

            audio.save()
            logger.info(f"已为 {file_path.name} 添加元数据")
            return True

        except Exception as e:
            logger.error(f"添加FLAC元数据失败: {e}")
            return False

    async def add_metadata_to_mp3(self, file_path: Path, song_info,
                                  lyrics_data: dict = None, song_data: Dict[str, Any] = None) -> bool:
        """为MP3文件添加封面和歌词"""
        try:
            # 尝试读取现有ID3标签，如果没有则创建新的
            try:
                audio = ID3(file_path)
            except:
                audio = ID3()

            # 添加基本元数据
            audio.add(TIT2(encoding=3, text=song_info.name))  # 标题
            audio.add(TPE1(encoding=3, text=song_info.singers))  # 艺术家
            audio.add(TALB(encoding=3, text=song_info.album))  # 专辑

            # 添加封面
            if song_data:
                cover_url = await self.cover_manager.get_valid_cover_url(song_data)
                if cover_url:
                    cover_data = await self.cover_manager.download_cover(cover_url)
                    if cover_data:
                        mime_type = 'image/png' if cover_url.lower().endswith('.png') else 'image/jpeg'

                        # 删除现有的封面
                        audio.delall('APIC')

                        # 添加新封面
                        audio.add(APIC(
                            encoding=3,
                            mime=mime_type,
                            type=3,
                            desc='Cover',
                            data=cover_data
                        ))
                        logger.info(f"已添加封面到 {file_path.name}")

            # 添加歌词
            if lyrics_data:
                lyric_text = lyrics_data.get('lyric', '')
                if lyric_text:
                    audio.delall('USLT')
                    audio.add(USLT(
                        encoding=3,
                        lang='eng',
                        desc='Lyrics',
                        text=lyric_text
                    ))
                    logger.info(f"已添加歌词到 {file_path.name}")

                trans_text = lyrics_data.get('trans', '')
                if trans_text:
                    audio.add(USLT(
                        encoding=3,
                        lang='eng',
                        desc='Translation',
                        text=trans_text
                    ))

            audio.save(file_path, v2_version=3)
            logger.info(f"已为 {file_path.name} 添加元数据")
            return True

        except Exception as e:
            logger.error(f"为MP3添加元数据失败: {e}")
            return False

    async def add_metadata_to_file(self, file_path: Path, song_info,
                                   lyrics_data: dict = None, song_data: Dict[str, Any] = None) -> bool:
        """根据文件类型为音频文件添加元数据"""
        file_extension = file_path.suffix.lower()

        if file_extension == '.flac':
            return await self.add_metadata_to_flac(file_path, song_info, lyrics_data, song_data)
        elif file_extension in ['.mp3', '.mpga']:
            return await self.add_metadata_to_mp3(file_path, song_info, lyrics_data, song_data)
        else:
            logger.warning(f"不支持为 {file_extension} 格式添加元数据")
            return False