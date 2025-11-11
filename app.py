import asyncio
import pickle
from pathlib import Path
from qqmusic_api import search
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
import random

# 配置常量
CONFIG = {
    "CREDENTIAL_FILE": Path("qqmusic_cred.pkl"),
    "MUSIC_DIR": Path("./music"),
    "CLEANUP_INTERVAL": 30,  # 延长清理间隔，减少服务器压力
    "CREDENTIAL_CHECK_INTERVAL": 30,  # 延长凭证检查间隔
    "MAX_FILENAME_LENGTH": 100,
    "COVER_SIZE": 800,  # 
    "DOWNLOAD_TIMEOUT": 45,  # 增加下载超时时间
    "SEARCH_LIMIT": 8,  # 减少搜索数量
    "SERVER_HOST": "0.0.0.0",
    "SERVER_PORT": 6022,
    "MAX_RETRY_ATTEMPTS": 2,  # 最大重试次数
    "RETRY_DELAY": 1,  # 重试延迟(秒)
    "REQUEST_DELAY": 0.5,  # 请求延迟，避免过快请求
}

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
CONFIG["MUSIC_DIR"].mkdir(exist_ok=True)

# 线程池用于执行阻塞操作
thread_pool = ThreadPoolExecutor(max_workers=2)  # 减少工作线程数

@dataclass
class SongInfo:
    """歌曲信息数据类"""
    mid: str
    name: str
    singers: str
    vip: bool = False
    album: str = ""
    album_mid: str = ""
    interval: int = 0
    payplay: int = 0  # 付费播放类型

@dataclass
class DownloadResult:
    """下载结果数据类"""
    filename: str
    quality: str
    filepath: str
    cached: bool = False
    metadata_added: bool = False
    error: str = None

class RetryManager:
    """重试管理器"""
    
    @staticmethod
    async def with_retry(async_func, *args, max_attempts=CONFIG["MAX_RETRY_ATTEMPTS"], **kwargs):
        """带重试的异步函数执行"""
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                # 添加随机延迟，避免请求过于频繁
                if attempt > 0:
                    delay = CONFIG["RETRY_DELAY"] * (2 ** attempt) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
                
                result = await async_func(*args, **kwargs)
                if result is not None:  # 如果函数返回None也视为失败
                    return result
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"第 {attempt + 1} 次尝试失败: {e}")
                continue
        
        logger.error(f"所有 {max_attempts} 次尝试都失败了")
        if last_exception:
            raise last_exception
        else:
            raise Exception("操作失败")

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
            # 添加请求延迟
            await asyncio.sleep(CONFIG["REQUEST_DELAY"])
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=CONFIG["DOWNLOAD_TIMEOUT"])
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        # 降低内容大小检查阈值
                        if len(content) > 512:  # 从1KB降低到512B
                            return content
                        else:
                            logger.warning(f"下载内容过小: {len(content)} bytes")
                    else:
                        logger.warning(f"下载失败，状态码: {resp.status}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"下载超时: {url}")
            return None
        except Exception as e:
            logger.error(f"下载文件时出错: {e}")
            return None

class MetadataManager:
    """元数据管理器"""
    
    @staticmethod
    def get_cover_url(mid: str, size: Literal[150, 300, 500, 800] = None) -> str:
        """获取封面URL"""
        if size is None:
            size = CONFIG["COVER_SIZE"]
        if size not in [150, 300, 500, 800]:
            size = 300  # 默认使用300尺寸
        return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{mid}.jpg"
    
    @staticmethod
    async def add_metadata_to_flac(file_path: Path, song_info: SongInfo, 
                                 cover_url: str = None, lyrics_data: dict = None) -> bool:
        """为FLAC文件添加封面和歌词"""
        try:
            audio = FLAC(file_path)
            
            # 添加基本元数据
            audio['title'] = song_info.name
            audio['artist'] = song_info.singers
            audio['album'] = song_info.album
            
            # 添加封面（可选，失败不影响主要功能）
            if cover_url:
                try:
                    cover_data = await FileManager.download_file_content(cover_url)
                    if cover_data:
                        image = Picture()
                        image.type = 3
                        image.mime = 'image/png' if cover_url.lower().endswith('.png') else 'image/jpeg'
                        image.desc = 'Cover'
                        image.data = cover_data
                        
                        audio.clear_pictures()
                        audio.add_picture(image)
                        logger.info(f"已添加封面到 {file_path.name}")
                except Exception as e:
                    logger.warning(f"添加封面失败: {e}")
            
            # 添加歌词（可选）
            if lyrics_data:
                lyric_text = lyrics_data.get('lyric', '')
                if lyric_text:
                    audio['lyrics'] = lyric_text
                
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
                                cover_url: str = None, lyrics_data: dict = None) -> bool:
        """为MP3文件添加封面和歌词"""
        try:
            try:
                audio = ID3(file_path)
            except:
                audio = ID3()
            
            # 添加基本元数据
            audio.add(TIT2(encoding=3, text=song_info.name))
            audio.add(TPE1(encoding=3, text=song_info.singers))
            audio.add(TALB(encoding=3, text=song_info.album))
            
            # 添加封面（可选）
            if cover_url:
                try:
                    cover_data = await FileManager.download_file_content(cover_url)
                    if cover_data:
                        mime_type = 'image/png' if cover_url.lower().endswith('.png') else 'image/jpeg'
                        
                        audio.delall('APIC')
                        audio.add(APIC(
                            encoding=3,
                            mime=mime_type,
                            type=3,
                            desc='Cover',
                            data=cover_data
                        ))
                except Exception as e:
                    logger.warning(f"添加MP3封面失败: {e}")
            
            # 添加歌词（可选）
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
                
                trans_text = lyrics_data.get('trans', '')
                if trans_text:
                    audio.add(USLT(
                        encoding=3,
                        lang='eng',
                        desc='Translation',
                        text=trans_text
                    ))
            
            audio.save(file_path, v2_version=3)
            return True
            
        except Exception as e:
            logger.error(f"为MP3添加元数据失败: {e}")
            return False
    
    @staticmethod
    async def add_metadata_to_file(file_path: Path, song_info: SongInfo,
                                 cover_url: str = None, lyrics_data: dict = None) -> bool:
        """根据文件类型为音频文件添加元数据"""
        try:
            file_extension = file_path.suffix.lower()
            
            if file_extension == '.flac':
                return await MetadataManager.add_metadata_to_flac(file_path, song_info, cover_url, lyrics_data)
            elif file_extension in ['.mp3', '.mpga']:
                return await MetadataManager.add_metadata_to_mp3(file_path, song_info, cover_url, lyrics_data)
            else:
                return False
        except Exception as e:
            logger.error(f"添加元数据失败: {e}")
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
            
            # 只清理超过1小时的文件，避免删除正在下载的文件
            now = time.time()
            files_to_clean = []
            
            for file_path in CONFIG["MUSIC_DIR"].iterdir():
                if file_path.is_file():
                    # 如果文件创建时间超过1小时，则清理
                    if now - file_path.stat().st_ctime > 3600:
                        files_to_clean.append(file_path)
            
            if files_to_clean:
                deleted_count = 0
                for file_path in files_to_clean:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"删除文件失败 {file_path}: {e}")
                
                self.status.update({
                    "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "files_cleaned": deleted_count,
                    "total_cleaned": self.status["total_cleaned"] + deleted_count,
                    "next_run": (datetime.now() + timedelta(
                        seconds=CONFIG["CLEANUP_INTERVAL"]
                    )).strftime("%Y-%m-%d %H:%M:%S")
                })
                
                logger.info(f"已清理 {deleted_count} 个旧文件")
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
        try:
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
                
                try:
                    # 使用重试机制获取歌曲URL
                    urls = await RetryManager.with_retry(
                        get_song_urls,
                        [song_info.mid], 
                        file_type=file_type, 
                        credential=self.credential_manager.credential
                    )
                    
                    if not urls:
                        continue
                    
                    url = urls.get(song_info.mid)
                    if not url:
                        continue
                    
                    if isinstance(url, list):
                        url = url[0]
                    
                    # 使用重试机制下载文件
                    content = await RetryManager.with_retry(
                        FileManager.download_file_content,
                        url
                    )
                    
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
                        
                        # 异步添加元数据（不阻塞主要下载流程）
                        if add_metadata and not result.cached:
                            asyncio.create_task(
                                self._add_metadata(result, song_info, file_type)
                            )
                        
                        return result
                    
                except Exception as e:
                    logger.warning(f"下载 {quality_name} 失败: {e}")
                    continue
            
            return DownloadResult(
                filename="",
                quality="",
                filepath="",
                error="所有音质下载失败"
            )
            
        except Exception as e:
            logger.error(f"下载过程出错: {e}")
            return DownloadResult(
                filename="",
                quality="",
                filepath="",
                error=f"下载失败: {str(e)}"
            )
    
    async def _add_metadata(self, result: DownloadResult, song_info: SongInfo, 
                          file_type: SongFileType):
        """为下载的文件添加元数据"""
        if file_type not in [SongFileType.FLAC, SongFileType.MP3_320, SongFileType.MP3_128]:
            return
        
        try:
            cover_url = None
            if song_info.album_mid:
                cover_url = MetadataManager.get_cover_url(song_info.album_mid)
            
            lyrics_data = None
            try:
                lyrics_data = await RetryManager.with_retry(get_lyric, song_info.mid)
            except Exception as e:
                logger.warning(f"获取歌词失败: {e}")
            
            if cover_url or lyrics_data:
                metadata_success = await MetadataManager.add_metadata_to_file(
                    Path(result.filepath),
                    song_info,
                    cover_url,
                    lyrics_data
                )
                result.metadata_added = metadata_success
                
        except Exception as e:
            logger.error(f"添加元数据失败: {e}")
            result.metadata_added = False

class SearchManager:
    """搜索管理器"""
    
    @staticmethod
    async def search_songs(keyword: str, limit: int = CONFIG["SEARCH_LIMIT"]) -> List[SongInfo]:
        """搜索歌曲"""
        try:
            # 使用重试机制
            results = await RetryManager.with_retry(
                search.search_by_type,
                keyword, 
                num=limit
            )
            
            if not results:
                return []
            
            formatted_results = []
            for song in results:
                try:
                    # 提取歌手信息
                    singers = []
                    for singer in song.get("singer", []):
                        singer_name = singer.get("name", "").strip()
                        if singer_name:
                            singers.append(singer_name)
                    
                    singers_str = ", ".join(singers) if singers else "未知歌手"
                    
                    # 多种方式判断VIP歌曲
                    pay_info = song.get("pay", {})
                    pay_play = pay_info.get("pay_play", 0)
                    
                    # 额外检查歌曲状态
                    status = song.get("status", 0)
                    
                    # VIP判断逻辑：pay_play不为0 或者 status为1
                    is_vip = pay_play != 0 or status == 1
                    
                    album_info = song.get("album", {})
                    
                    song_info = SongInfo(
                        mid=song.get('mid', ''),
                        name=song.get("title", "未知歌曲").strip(),
                        singers=singers_str,
                        vip=is_vip,
                        payplay=pay_play,
                        album=album_info.get("name", "").strip(),
                        album_mid=album_info.get("mid", ""),
                        interval=song.get('interval', 0)
                    )
                    
                    formatted_results.append(song_info)
                    
                except Exception as e:
                    logger.warning(f"处理单条搜索结果失败: {e}")
                    continue
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

# 全局管理器实例
credential_manager = CredentialManager()
cleanup_manager = CleanupManager()
music_downloader = MusicDownloader(credential_manager)
search_manager = SearchManager()

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
            try:
                credential_manager.check_and_refresh()
            except Exception as e:
                logger.error(f"凭证检查任务出错: {e}")
            time.sleep(CONFIG["CREDENTIAL_CHECK_INTERVAL"])
    
    if credential_thread is None or not credential_thread.is_alive():
        credential_thread = threading.Thread(target=credential_check_loop, daemon=True)
        credential_thread.start()
        logger.info(f"自动凭证检查任务已启动")

def start_cleanup_scheduler():
    """启动定时清理任务"""
    global cleanup_thread, stop_threads
    
    def cleanup_loop():
        while not stop_threads and cleanup_manager.status["enabled"]:
            try:
                cleanup_manager.cleanup_music_folder()
            except Exception as e:
                logger.error(f"清理任务出错: {e}")
            time.sleep(CONFIG["CLEANUP_INTERVAL"])
    
    if cleanup_thread is None or not cleanup_thread.is_alive():
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        logger.info(f"自动清理任务已启动")

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
    
    if not keyword:
        return jsonify({'error': '歌曲名不能为空'}), 400
    
    try:
        results = run_async(search_manager.search_songs(keyword))
        if not results:
            return jsonify({'error': '未找到歌曲，请尝试其他关键词'}), 404
        
        # 转换为字典以便JSON序列化
        formatted_results = [song.__dict__ for song in results]
        
        return jsonify({
            'results': formatted_results,
            'count': len(formatted_results)
        })
        
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return jsonify({'error': f'搜索失败，请稍后重试: {str(e)}'}), 500

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
        song_info = SongInfo(**song_data)
        
        # 改进的VIP歌曲权限检查
        if song_info.vip and not credential_manager.credential:
            return jsonify({
                'error': 'VIP歌曲需要登录QQ音乐账号才能下载'
            }), 403
        
        # 下载歌曲
        result = run_async(music_downloader.download_song(
            song_info, prefer_flac, add_metadata
        ))
        
        if result and not result.error:
            return jsonify(result.__dict__)
        else:
            error_msg = result.error if result else "下载失败"
            return jsonify({'error': error_msg}), 500
            
    except Exception as e:
        logger.error(f"下载失败: {e}")
        return jsonify({'error': f'下载失败，请稍后重试: {str(e)}'}), 500

@app.route('/api/file/<filename>')
def api_file(filename):
    """提供文件下载"""
    # 安全检查
    if '..' in filename or filename.startswith('/') or '/' in filename:
        return jsonify({'error': '无效的文件名'}), 400
    
    filepath = CONFIG["MUSIC_DIR"] / filename
    if filepath.exists() and filepath.is_file():
        try:
            return send_file(filepath, as_attachment=True)
        except Exception as e:
            logger.error(f"发送文件失败: {e}")
            return jsonify({'error': '文件发送失败'}), 500
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
        "has_credential": credential_manager.credential is not None
    })

@app.route('/api/system/info')
def api_system_info():
    """系统信息"""
    import psutil
    return jsonify({
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent,
        "active_threads": threading.active_count()
    })

def stop_all_threads():
    """停止所有后台线程"""
    global stop_threads
    stop_threads = True
    thread_pool.shutdown(wait=False)

def init_app():
    """初始化应用"""
    try:
        credential_manager.load_and_refresh_sync()
        start_credential_checker()
        start_cleanup_scheduler()
        logger.info("应用初始化完成")
    except Exception as e:
        logger.error(f"应用初始化失败: {e}")

if __name__ == '__main__':
    try:
        init_app()
        app.run(
            debug=False, 
            host=CONFIG["SERVER_HOST"], 
            port=CONFIG["SERVER_PORT"], 
            use_reloader=False,
            threaded=True  # 启用多线程
        )
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止...")
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
    finally:
        stop_all_threads()
        logger.info("应用已停止")