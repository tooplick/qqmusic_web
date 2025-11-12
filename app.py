import asyncio
import pickle
from pathlib import Path
from qqmusic_api import search
from qqmusic_api.search import general_search
from qqmusic_api.song import get_song_urls, SongFileType
from qqmusic_api.login import Credential, check_expired
from qqmusic_api.lyric import get_lyric
import aiohttp
from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid
import threading
import time
import shutil
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any, Literal, List, Tuple
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT, TPE2, TCOM, TDRC, TCON
from mutagen.mp3 import MP3
import json
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


# 动态配置
def get_config():
    """获取动态配置，支持容器和非容器环境"""
    # 判断是否在容器中运行（通过检查 /app 目录是否存在）
    is_container = Path("/app").exists()

    if is_container:
        # 容器环境 - 使用挂载路径
        base_dir = Path("/app")
        credential_file = base_dir / "credential/qqmusic_cred.pkl"
        music_dir = base_dir / "music"
    else:
        # 非容器环境 - 使用当前工作目录
        base_dir = Path.cwd()
        credential_file = base_dir / "qqmusic_cred.pkl"
        music_dir = base_dir / "music"

    # 确保目录存在
    music_dir.mkdir(exist_ok=True)

    return {
        "CREDENTIAL_FILE": credential_file,
        "MUSIC_DIR": music_dir,
        "CLEANUP_INTERVAL": 20,  # 清理间隔(秒)
        "CREDENTIAL_CHECK_INTERVAL": 60,  # 凭证检查间隔(秒)
        "MAX_FILENAME_LENGTH": 100,
        "COVER_SIZE": 800,  # 封面尺寸[150, 300, 500, 800]
        "DOWNLOAD_TIMEOUT": 60,
        "SEARCH_LIMIT": 10,
        "SERVER_HOST": "0.0.0.0",
        "SERVER_PORT": 6022,
        "IS_CONTAINER": is_container  # 环境标识
    }


# 初始化配置
CONFIG = get_config()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("qqmusic_web")

app = Flask(__name__)

# 线程池用于执行阻塞操作
thread_pool = ThreadPoolExecutor(max_workers=4)


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
    raw_data: Optional[Dict[str, Any]] = None  # 添加原始数据字段


@dataclass
class DownloadResult:
    """下载结果数据类"""
    filename: str
    quality: str
    filepath: str
    cached: bool = False
    metadata_added: bool = False


class CoverManager:
    """封面管理器"""

    @staticmethod
    def get_cover_url_by_album_mid(mid: str, size: Literal[150, 300, 500, 800] = None) -> Optional[str]:
        """通过专辑MID获取封面URL"""
        if not mid:
            return None
        if size is None:
            size = CONFIG["COVER_SIZE"]
        if size not in [150, 300, 500, 800]:
            raise ValueError("不支持的封面尺寸")
        return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{mid}.jpg"

    @staticmethod
    def get_cover_url_by_vs(vs: str, size: Literal[150, 300, 500, 800] = None) -> Optional[str]:
        """通过VS值获取封面URL"""
        if not vs:
            return None
        if size is None:
            size = CONFIG["COVER_SIZE"]
        if size not in [150, 300, 500, 800]:
            raise ValueError("不支持的封面尺寸")
        return f"https://y.qq.com/music/photo_new/T062R{size}x{size}M000{vs}.jpg"

    @staticmethod
    async def get_valid_cover_url(song_data: Dict[str, Any], size: Literal[150, 300, 500, 800] = None) -> Optional[str]:
        """获取并验证有效的封面URL（按优先级尝试所有可能的VS值）"""
        if size is None:
            size = CONFIG["COVER_SIZE"]

        # 1. 优先尝试专辑MID
        album_mid = song_data.get('album', {}).get('mid', '')
        if album_mid:
            url = CoverManager.get_cover_url_by_album_mid(album_mid, size)
            logger.debug(f"尝试专辑MID封面: {url}")
            cover_data = await CoverManager.download_cover(url)
            if cover_data:
                logger.info(f"使用专辑MID封面: {url}")
                return url

        # 2. 尝试所有可用的VS值（按顺序）
        vs_values = song_data.get('vs', [])
        logger.debug(f"分析VS值: {vs_values}")

        # 收集所有候选VS值
        candidate_vs = []

        # 首先收集所有单个有效的VS值
        for i, vs in enumerate(vs_values):
            if vs and isinstance(vs, str) and len(vs) >= 3 and ',' not in vs:
                candidate_vs.append({
                    'value': vs,
                    'source': f'vs_single_{i}',
                    'priority': 1  # 高优先级
                })

        # 然后收集逗号分隔的VS值部分
        for i, vs in enumerate(vs_values):
            if vs and ',' in vs:
                parts = [part.strip() for part in vs.split(',') if part.strip()]
                for j, part in enumerate(parts):
                    if len(part) >= 3:
                        candidate_vs.append({
                            'value': part,
                            'source': f'vs_part_{i}_{j}',
                            'priority': 2  # 中优先级
                        })

        # 按优先级排序
        candidate_vs.sort(key=lambda x: x['priority'])

        logger.debug(f"候选VS值: {[c['value'] for c in candidate_vs]}")

        # 按顺序尝试每个候选VS值
        for candidate in candidate_vs:
            url = CoverManager.get_cover_url_by_vs(candidate['value'], size)
            logger.debug(f"尝试VS值封面 [{candidate['source']}]: {url}")
            cover_data = await CoverManager.download_cover(url)
            if cover_data:
                logger.info(f"使用VS值封面 [{candidate['source']}]: {url}")
                return url

        logger.warning("未找到任何有效的封面URL")
        return None

    @staticmethod
    async def download_cover(url: str) -> Optional[bytes]:
        """下载封面图片"""
        if not url:
            return None

        try:
            async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=CONFIG["DOWNLOAD_TIMEOUT"])
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        # 检查文件大小和内容有效性
                        if len(content) > 1024:
                            # 简单验证图片格式
                            if content.startswith(b'\xff\xd8') or content.startswith(b'\x89PNG'):
                                logger.debug(f"封面下载成功: {len(content)} bytes")
                                return content
                            else:
                                logger.warning(f"封面图片格式无效: {url}")
                        else:
                            logger.warning(f"封面图片过小: {len(content)} bytes, URL: {url}")
                    else:
                        logger.warning(f"封面下载失败: HTTP {resp.status}, URL: {url}")
                    return None
        except Exception as e:
            logger.error(f"封面下载异常: {e}, URL: {url}")
            return None


class FileManager:
    """文件管理器"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """清理文件名中的非法字符并限制长度"""
        illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in illegal_chars:
            filename = filename.replace(char, '_')

        # 限制文件名长度
        if len(filename) > CONFIG["MAX_FILENAME_LENGTH"]:
            name, ext = os.path.splitext(filename)
            filename = name[:CONFIG["MAX_FILENAME_LENGTH"] - len(ext)] + ext

        return filename

    @staticmethod
    async def download_file_content(url: str) -> Optional[bytes]:
        """异步下载文件内容"""
        try:
            async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=CONFIG["DOWNLOAD_TIMEOUT"])
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        # 检查内容是否有效（大于1KB）
                        if len(content) > 1024:
                            return content
                        else:
                            logger.warning(f"下载内容过小: {len(content)} bytes")
                    else:
                        logger.warning(f"下载失败，状态码: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"下载文件时出错: {e}")
            return None


class MetadataManager:
    """元数据管理器"""

    @staticmethod
    async def add_metadata_to_flac(file_path: Path, song_info: SongInfo,
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
                cover_url = await CoverManager.get_valid_cover_url(song_data)
                if cover_url:
                    cover_data = await CoverManager.download_cover(cover_url)
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

    @staticmethod
    async def add_metadata_to_mp3(file_path: Path, song_info: SongInfo,
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
                cover_url = await CoverManager.get_valid_cover_url(song_data)
                if cover_url:
                    cover_data = await CoverManager.download_cover(cover_url)
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

    @staticmethod
    async def add_metadata_to_file(file_path: Path, song_info: SongInfo,
                                   lyrics_data: dict = None, song_data: Dict[str, Any] = None) -> bool:
        """根据文件类型为音频文件添加元数据"""
        file_extension = file_path.suffix.lower()

        if file_extension == '.flac':
            return await MetadataManager.add_metadata_to_flac(file_path, song_info, lyrics_data, song_data)
        elif file_extension in ['.mp3', '.mpga']:
            return await MetadataManager.add_metadata_to_mp3(file_path, song_info, lyrics_data, song_data)
        else:
            logger.warning(f"不支持为 {file_extension} 格式添加元数据")
            return False


class CredentialManager:
    """凭证管理器"""

    def __init__(self):
        self.credential = None
        self.status = {
            "enabled": True,
            "last_check": None,
            "last_refresh": None,
            "status": "未检测到凭证",
            "expired": True
        }

    def load_credential(self) -> Optional[Credential]:
        """加载凭证"""
        if not CONFIG["CREDENTIAL_FILE"].exists():
            return None

        try:
            with CONFIG["CREDENTIAL_FILE"].open("rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"加载凭证文件失败: {e}")
            return None

    def save_credential(self, cred: Credential) -> bool:
        """保存凭证"""
        try:
            with CONFIG["CREDENTIAL_FILE"].open("wb") as f:
                pickle.dump(cred, f)
            return True
        except Exception as e:
            logger.error(f"保存凭证文件失败: {e}")
            return False

    async def refresh_credential(self, cred: Credential) -> bool:
        """刷新凭证"""
        try:
            if await cred.can_refresh():
                await cred.refresh()
                return self.save_credential(cred)
            return False
        except Exception as e:
            logger.error(f"刷新凭证失败: {e}")
            return False

    def load_and_refresh_sync(self) -> Optional[Credential]:
        """同步加载和刷新凭证"""
        if not CONFIG["CREDENTIAL_FILE"].exists():
            logger.info("本地无凭证文件，仅能下载免费歌曲")
            self.status.update({
                "status": "本地无凭证文件，仅能下载免费歌曲",
                "expired": True
            })
            return None

        cred = self.load_credential()
        if not cred:
            self.status.update({
                "status": "加载凭证失败，仅能下载免费歌曲",
                "expired": True
            })
            return None

        try:
            # 检查是否过期
            is_expired = run_async(check_expired(cred))

            if is_expired:
                logger.info("本地凭证已过期，尝试自动刷新...")
                self.status["status"] = "本地凭证已过期，尝试自动刷新..."

                if run_async(self.refresh_credential(cred)):
                    logger.info("凭证自动刷新成功!")
                    self.status.update({
                        "status": "凭证自动刷新成功!",
                        "expired": False,
                        "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    self.credential = cred
                    return cred
                else:
                    logger.info("凭证不支持刷新或刷新失败，将以未登录方式下载")
                    self.status.update({
                        "status": "凭证不支持刷新或刷新失败，将以未登录方式下载",
                        "expired": True
                    })
                    return None
            else:
                logger.info("使用本地凭证登录成功!")
                self.status.update({
                    "status": "使用本地凭证登录成功!",
                    "expired": False
                })
                self.credential = cred
                return cred

        except Exception as e:
            logger.error(f"处理凭证时出错: {e}")
            self.status.update({
                "status": f"处理凭证时出错: {e}，将以未登录方式下载",
                "expired": True
            })
            return None

    def check_and_refresh(self):
        """检查并刷新凭证"""
        if not self.status["enabled"]:
            return

        self.status["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not self.credential:
            self.load_and_refresh_sync()
            return

        try:
            is_expired = run_async(check_expired(self.credential))

            if is_expired:
                logger.info("检测到凭证已过期，尝试自动刷新...")
                self.status.update({
                    "status": "检测到凭证已过期，尝试自动刷新...",
                    "expired": True
                })

                if run_async(self.refresh_credential(self.credential)):
                    logger.info("凭证自动刷新成功!")
                    self.status.update({
                        "status": "凭证自动刷新成功!",
                        "expired": False,
                        "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    logger.info("凭证不支持刷新")
                    self.status.update({
                        "status": "凭证不支持刷新",
                        "expired": True
                    })
            else:
                self.status["status"] = "凭证状态正常"
                self.status["expired"] = False

        except Exception as e:
            logger.error(f"检查凭证时出错: {e}")
            self.status.update({
                "status": f"检查凭证时出错: {e}",
                "expired": True
            })


class CleanupManager:
    """清理管理器"""

    def __init__(self):
        self.status = {
            "enabled": True,
            "last_run": None,
            "next_run": None,
            "files_cleaned": 0,
            "total_cleaned": 0
        }

    def cleanup_music_folder(self):
        """清空music文件夹"""
        try:
            if not CONFIG["MUSIC_DIR"].exists():
                CONFIG["MUSIC_DIR"].mkdir(exist_ok=True)
                return

            files = [f for f in CONFIG["MUSIC_DIR"].iterdir() if f.is_file()]
            file_count = len(files)

            if file_count > 0:
                deleted_count = 0
                for file_path in files:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除文件失败 {file_path}: {e}")

                # 更新状态
                self.status.update({
                    "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "files_cleaned": deleted_count,
                    "total_cleaned": self.status["total_cleaned"] + deleted_count,
                    "next_run": (datetime.now() + timedelta(
                        seconds=CONFIG["CLEANUP_INTERVAL"]
                    )).strftime("%Y-%m-%d %H:%M:%S")
                })

                logger.info(f"已清理 {deleted_count} 个文件，下次运行: {self.status['next_run']}")
            else:
                self.status.update({
                    "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "files_cleaned": 0,
                    "next_run": (datetime.now() + timedelta(
                        seconds=CONFIG["CLEANUP_INTERVAL"]
                    )).strftime("%Y-%m-%d %H:%M:%S")
                })

        except Exception as e:
            logger.error(f"清理任务错误: {e}")


class MusicDownloader:
    """音乐下载器"""

    def __init__(self, credential_manager: CredentialManager):
        self.credential_manager = credential_manager

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

        safe_filename = FileManager.sanitize_filename(
            f"{song_info.name} - {song_info.singers}"
        )

        # 尝试不同音质
        for file_type, quality_name in quality_order:
            filepath = CONFIG["MUSIC_DIR"] / f"{safe_filename}{file_type.e}"

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

            content = await FileManager.download_file_content(url)
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
            metadata_success = await MetadataManager.add_metadata_to_file(
                Path(result.filepath),
                song_info,
                lyrics_data,
                song_info.raw_data  # 传递完整的原始歌曲数据用于封面获取
            )
            result.metadata_added = metadata_success

        except Exception as e:
            logger.error(f"添加元数据失败: {e}")
            result.metadata_added = False


# 全局管理器实例
credential_manager = CredentialManager()
cleanup_manager = CleanupManager()
music_downloader = MusicDownloader(credential_manager)

# 任务控制变量
cleanup_thread = None
credential_thread = None
stop_threads = False


def run_async(coro):
    """运行异步函数"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


def start_credential_checker():
    """启动凭证检查任务"""
    global credential_thread, stop_threads

    def credential_check_loop():
        while not stop_threads and credential_manager.status["enabled"]:
            credential_manager.check_and_refresh()
            time.sleep(CONFIG["CREDENTIAL_CHECK_INTERVAL"])

    if credential_thread is None or not credential_thread.is_alive():
        credential_thread = threading.Thread(target=credential_check_loop, daemon=True)
        credential_thread.start()
        logger.info(f"自动凭证检查任务已启动，每{CONFIG['CREDENTIAL_CHECK_INTERVAL']}秒检查一次")


def start_cleanup_scheduler():
    """启动定时清理任务"""
    global cleanup_thread, stop_threads

    def cleanup_loop():
        while not stop_threads and cleanup_manager.status["enabled"]:
            cleanup_manager.cleanup_music_folder()
            time.sleep(CONFIG["CLEANUP_INTERVAL"])

    if cleanup_thread is None or not cleanup_thread.is_alive():
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        logger.info(f"自动清理任务已启动，每{CONFIG['CLEANUP_INTERVAL']}秒检查一次")


# Flask路由
@app.route('/')
def index():
    """提供前端页面"""
    has_credential = (CONFIG["CREDENTIAL_FILE"].exists() and
                      credential_manager.credential is not None)
    return render_template('index.html', has_credential=has_credential)


@app.route('/api/search', methods=['POST'])
def api_search():
    """搜索歌曲API"""
    data = request.get_json(silent=True) or {}
    keyword = data.get('keyword', '').strip()
    page = data.get('page', 1)  # 添加页码参数，默认为1

    if not keyword:
        return jsonify({'error': '歌曲名不能为空'}), 400

    try:
        # 一次性获取60条结果
        search_limit = 60
        results = run_async(search.search_by_type(keyword, num=search_limit))
        if not results:
            return jsonify({'error': '未找到歌曲'}), 404

        # 计算分页
        page_size = CONFIG["SEARCH_LIMIT"]  # 10
        total_results = len(results)
        total_pages = (total_results + page_size - 1) // page_size  # 向上取整

        # 确保页码在有效范围内
        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        # 计算分页结果
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_results = results[start_index:end_index]

        formatted_results = []
        for song in paginated_results:
            singers = ", ".join([s.get("name", "") for s in song.get("singer", [])])

            formatted_results.append(SongInfo(
                mid=song.get('mid', ''),
                name=song.get("title", ""),
                singers=singers,
                vip=song.get("pay", {}).get("pay_play", 0) != 0,
                album=song.get("album", {}).get("name", ""),
                album_mid=song.get("album", {}).get("mid", ""),
                interval=song.get('interval', 0),
                raw_data=song  # 保存完整的原始数据用于封面获取
            ).__dict__)  # 转换为字典以便JSON序列化

        return jsonify({
            'results': formatted_results,
            'pagination': {
                'current_page': page,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'total_pages': total_pages,
                'total_results': total_results
            },
            'all_results': total_results  # 返回实际获取的总数
        })

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return jsonify({'error': f'搜索失败: {str(e)}'}), 500


@app.route('/api/download', methods=['POST'])
def api_download():
    """下载歌曲API"""
    data = request.get_json(silent=True) or {}
    song_data = data.get('song_data')
    prefer_flac = data.get('prefer_flac', False)
    add_metadata = data.get('add_metadata', True)

    if not song_data:
        return jsonify({'error': '缺少歌曲数据'}), 400

    try:
        # 从字典创建SongInfo对象，包括raw_data
        song_info = SongInfo(
            mid=song_data.get('mid', ''),
            name=song_data.get('name', ''),
            singers=song_data.get('singers', ''),
            vip=song_data.get('vip', False),
            album=song_data.get('album', ''),
            album_mid=song_data.get('album_mid', ''),
            interval=song_data.get('interval', 0),
            raw_data=song_data.get('raw_data')  # 包含原始歌曲数据用于封面获取
        )

        # 检查VIP歌曲权限
        if song_info.vip and not credential_manager.credential:
            return jsonify({
                'error': '这首歌是VIP歌曲，需要登录才能下载高音质版本'
            }), 403

        # 下载歌曲
        result = run_async(music_downloader.download_song(
            song_info, prefer_flac, add_metadata
        ))

        if result:
            return jsonify(result.__dict__)
        else:
            return jsonify({'error': '所有音质下载失败'}), 500

    except Exception as e:
        logger.error(f"下载失败: {e}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@app.route('/api/file/<filename>')
def api_file(filename):
    """提供文件下载"""
    # 安全检查
    if '..' in filename or filename.startswith('/'):
        return jsonify({'error': '无效的文件名'}), 400

    filepath = CONFIG["MUSIC_DIR"] / filename
    if filepath.exists() and filepath.is_file():
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({'error': '文件不存在'}), 404


@app.route('/api/cleanup/status')
def api_cleanup_status():
    """获取清理任务状态"""
    return jsonify(cleanup_manager.status)


@app.route('/api/cleanup/toggle', methods=['POST'])
def api_cleanup_toggle():
    """切换清理任务状态"""
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled', True)
    cleanup_manager.status["enabled"] = enabled
    return jsonify({"enabled": cleanup_manager.status["enabled"]})


@app.route('/api/credential/status')
def api_credential_status():
    """获取凭证状态"""
    return jsonify(credential_manager.status)


@app.route('/api/credential/toggle', methods=['POST'])
def api_credential_toggle():
    """切换凭证检查状态"""
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled', True)
    credential_manager.status["enabled"] = enabled
    return jsonify({"enabled": credential_manager.status["enabled"]})


@app.route('/api/health')
def api_health():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "music_dir_exists": CONFIG["MUSIC_DIR"].exists(),
        "music_files_count": len(list(CONFIG["MUSIC_DIR"].glob("*"))) if CONFIG["MUSIC_DIR"].exists() else 0,
        "environment": "container" if CONFIG["IS_CONTAINER"] else "native"
    })




def stop_all_threads():
    """停止所有后台线程"""
    global stop_threads
    stop_threads = True
    thread_pool.shutdown(wait=False)


def init_app():
    """初始化应用"""
    credential_manager.load_and_refresh_sync()
    start_credential_checker()
    start_cleanup_scheduler()
    logger.info(f"应用初始化完成 - 运行环境: {'容器' if CONFIG['IS_CONTAINER'] else '原生'}")
    logger.info(f"凭证文件路径: {CONFIG['CREDENTIAL_FILE']}")
    logger.info(f"音乐目录路径: {CONFIG['MUSIC_DIR']}")


if __name__ == '__main__':
    try:
        init_app()
        app.run(
            debug=False,
            host=CONFIG["SERVER_HOST"],
            port=CONFIG["SERVER_PORT"],
            use_reloader=False
        )
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止...")
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
    finally:
        stop_all_threads()
        logger.info("应用已停止")