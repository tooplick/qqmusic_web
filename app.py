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
from typing import Optional, Dict, Any, Literal
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT, TPE2, TCOM, TDRC, TCON
from mutagen.mp3 import MP3

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("qqmusic_web")

app = Flask(__name__)
CREDENTIAL_FILE = Path("qqmusic_cred.pkl")
MUSIC_DIR = Path("./music")
MUSIC_DIR.mkdir(exist_ok=True)

# 配置常量
CLEANUP_INTERVAL = 10  # 清理间隔(秒)
CREDENTIAL_CHECK_INTERVAL = 10  # 凭证检查间隔(秒)
MAX_FILENAME_LENGTH = 100  #
cover_size = 800  # 封面尺寸[150, 300, 500, 800]


def get_cover(mid: str, size: Literal[150, 300, 500, 800] = 300) -> str:
    if size not in [150, 300, 500, 800]:
        raise ValueError("not supported size")
    return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{mid}.jpg"


async def add_metadata_to_flac(file_path: Path, song_info: dict, cover_url: str = None, lyrics_data: dict = None):
    """为FLAC文件添加封面和歌词"""
    try:
        audio = FLAC(file_path)

        # 添加基本元数据
        audio['title'] = song_info.get('name', '')
        audio['artist'] = song_info.get('singers', '')
        audio['album'] = song_info.get('album', '')

        # 添加封面
        if cover_url:
            cover_data = await download_file_content(cover_url)
            if cover_data and len(cover_data) > 1024:  # 确保不是空图片
                image = Picture()
                image.type = 3  # 封面图片
                # 根据URL判断MIME类型
                if cover_url.lower().endswith('.png'):
                    image.mime = 'image/png'
                else:
                    image.mime = 'image/jpeg'
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

            # 添加翻译歌词（如果有）
            trans_text = lyrics_data.get('trans', '')
            if trans_text:
                audio['translyrics'] = trans_text

        audio.save()
        logger.info(f"已为 {file_path.name} 添加元数据")
        return True

    except Exception as e:
        logger.error(f"添加元数据失败: {e}")
        return False


async def add_metadata_to_mp3(file_path: Path, song_info: dict, cover_url: str = None, lyrics_data: dict = None):
    """为MP3文件添加封面和歌词"""
    try:
        # 尝试读取现有ID3标签，如果没有则创建新的
        try:
            audio = ID3(file_path)
        except:
            audio = ID3()

        # 添加基本元数据
        audio.add(TIT2(encoding=3, text=song_info.get('name', '')))  # 标题
        audio.add(TPE1(encoding=3, text=song_info.get('singers', '')))  # 艺术家
        audio.add(TALB(encoding=3, text=song_info.get('album', '')))  # 专辑

        # 添加封面
        if cover_url:
            cover_data = await download_file_content(cover_url)
            if cover_data and len(cover_data) > 1024:  # 确保不是空图片
                # 根据URL判断MIME类型
                if cover_url.lower().endswith('.png'):
                    mime_type = 'image/png'
                else:
                    mime_type = 'image/jpeg'

                # 删除现有的封面
                audio.delall('APIC')

                # 添加新封面
                audio.add(APIC(
                    encoding=3,  # UTF-8
                    mime=mime_type,
                    type=3,  # 封面图片
                    desc='Cover',
                    data=cover_data
                ))
                logger.info(f"已添加封面到 {file_path.name}")

        # 添加歌词
        if lyrics_data:
            lyric_text = lyrics_data.get('lyric', '')
            if lyric_text:
                # 删除现有的歌词
                audio.delall('USLT')

                # 添加歌词
                audio.add(USLT(
                    encoding=3,  # UTF-8
                    lang='eng',
                    desc='Lyrics',
                    text=lyric_text
                ))
                logger.info(f"已添加歌词到 {file_path.name}")

            # 添加翻译歌词（如果有）
            trans_text = lyrics_data.get('trans', '')
            if trans_text:
                audio.add(USLT(
                    encoding=3,  # UTF-8
                    lang='eng',
                    desc='Translation',
                    text=trans_text
                ))

        audio.save(file_path, v2_version=3)  # 使用ID3v2.3格式保存，兼容性更好
        logger.info(f"已为 {file_path.name} 添加元数据")
        return True

    except Exception as e:
        logger.error(f"为MP3添加元数据失败: {e}")
        return False


async def add_metadata_to_file(file_path: Path, song_info: dict, cover_url: str = None, lyrics_data: dict = None):
    """根据文件类型为音频文件添加元数据"""
    file_extension = file_path.suffix.lower()

    if file_extension == '.flac':
        return await add_metadata_to_flac(file_path, song_info, cover_url, lyrics_data)
    elif file_extension in ['.mp3', '.mpga']:
        return await add_metadata_to_mp3(file_path, song_info, cover_url, lyrics_data)
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

    def load_and_refresh_sync(self) -> Optional[Credential]:
        """同步加载和刷新凭证"""
        global credential

        if not CREDENTIAL_FILE.exists():
            logger.info("本地无凭证文件，仅能下载免费歌曲")
            self.status.update({
                "status": "本地无凭证文件，仅能下载免费歌曲",
                "expired": True
            })
            return None

        try:
            with CREDENTIAL_FILE.open("rb") as f:
                cred = pickle.load(f)

            # 检查是否过期
            is_expired = run_async(check_expired(cred))

            if is_expired:
                logger.info("本地凭证已过期，尝试自动刷新...")
                self.status["status"] = "本地凭证已过期，尝试自动刷新..."
                can_refresh = run_async(cred.can_refresh())

                if can_refresh:
                    try:
                        run_async(cred.refresh())
                        with CREDENTIAL_FILE.open("wb") as f:
                            pickle.dump(cred, f)
                        logger.info("凭证自动刷新成功!")
                        self.status.update({
                            "status": "凭证自动刷新成功!",
                            "expired": False,
                            "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        self.credential = cred
                        credential = cred
                        return cred
                    except Exception as e:
                        logger.error(f"凭证自动刷新失败: {e}")
                        self.status["status"] = f"凭证自动刷新失败: {e}，将以未登录方式下载"
                        self.status["expired"] = True
                        return None
                else:
                    logger.info("凭证不支持刷新，将以未登录方式下载")
                    self.status.update({
                        "status": "凭证不支持刷新，将以未登录方式下载",
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
                credential = cred
                return cred

        except Exception as e:
            logger.error(f"加载凭证失败: {e}，将以未登录方式下载")
            self.status.update({
                "status": f"加载凭证失败: {e}，将以未登录方式下载",
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

                can_refresh = run_async(self.credential.can_refresh())
                if can_refresh:
                    try:
                        run_async(self.credential.refresh())
                        with CREDENTIAL_FILE.open("wb") as f:
                            pickle.dump(self.credential, f)
                        logger.info("凭证自动刷新成功!")
                        self.status.update({
                            "status": "凭证自动刷新成功!",
                            "expired": False,
                            "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    except Exception as e:
                        logger.error(f"凭证自动刷新失败: {e}")
                        self.status["status"] = f"凭证自动刷新失败: {e}"
                        self.status["expired"] = True
                else:
                    logger.info("凭证不支持刷新")
                    self.status.update({
                        "status": "凭证不支持刷新",
                        "expired": True
                    })
            else:
                self.status["status"] = "凭证状态正常"
                self.status["expired"] = False
                logger.info("凭证状态正常")

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
            "files_cleaned": 0
        }

    def cleanup_music_folder(self):
        """清空music文件夹"""
        try:
            if not MUSIC_DIR.exists():
                MUSIC_DIR.mkdir(exist_ok=True)
                return

            # 获取所有文件
            files = [f for f in MUSIC_DIR.iterdir() if f.is_file()]
            file_count = len(files)

            if file_count > 0:
                # 删除所有文件
                for file_path in files:
                    try:
                        file_path.unlink()
                    except Exception as e:
                        logger.warning(f"删除文件失败 {file_path}: {e}")

                # 更新状态
                self.status.update({
                    "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "files_cleaned": file_count,
                    "next_run": (datetime.now() + timedelta(seconds=CLEANUP_INTERVAL)).strftime("%Y-%m-%d %H:%M:%S")
                })

                logger.info(f"已清理 {file_count} 个文件，下次运行: {self.status['next_run']}")
            else:
                # 没有文件时只更新时间
                self.status.update({
                    "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "next_run": (datetime.now() + timedelta(seconds=CLEANUP_INTERVAL)).strftime("%Y-%m-%d %H:%M:%S")
                })

        except Exception as e:
            logger.error(f"清理任务错误: {e}")


# 全局管理器实例
credential_manager = CredentialManager()
cleanup_manager = CleanupManager()

# 全局凭证（保持向后兼容）
credential = None

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
            time.sleep(CREDENTIAL_CHECK_INTERVAL)

    if credential_thread is None or not credential_thread.is_alive():
        credential_thread = threading.Thread(target=credential_check_loop, daemon=True)
        credential_thread.start()
        logger.info(f"自动凭证检查任务已启动，每{CREDENTIAL_CHECK_INTERVAL}秒检查一次")


def start_cleanup_scheduler():
    """启动定时清理任务"""
    global cleanup_thread, stop_threads

    def cleanup_loop():
        while not stop_threads and cleanup_manager.status["enabled"]:
            cleanup_manager.cleanup_music_folder()
            time.sleep(CLEANUP_INTERVAL)

    if cleanup_thread is None or not cleanup_thread.is_alive():
        cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        cleanup_thread.start()
        logger.info(f"自动清理任务已启动，每{CLEANUP_INTERVAL}秒检查一次")


def sanitize_filename(filename: str) -> str:
    """清理文件名中的非法字符并限制长度"""
    illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in illegal_chars:
        filename = filename.replace(char, '_')

    # 限制文件名长度
    if len(filename) > MAX_FILENAME_LENGTH:
        name, ext = os.path.splitext(filename)
        filename = name[:MAX_FILENAME_LENGTH - len(ext)] + ext

    return filename


async def download_file_content(url: str) -> Optional[bytes]:
    """异步下载文件内容"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
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


@app.route('/')
def index():
    """提供前端页面"""
    has_credential = CREDENTIAL_FILE.exists() and credential_manager.credential is not None
    return render_template('index.html', has_credential=has_credential)


@app.route('/api/search', methods=['POST'])
def api_search():
    """搜索歌曲API"""
    data = request.get_json(silent=True) or {}
    keyword = data.get('keyword', '').strip()

    if not keyword:
        return jsonify({'error': '歌曲名不能为空'}), 400

    try:
        # 搜索前10条结果
        results = run_async(search.search_by_type(keyword, num=10))
        if not results:
            return jsonify({'error': '未找到歌曲'}), 404

        # 格式化结果
        formatted_results = []
        for song in results:
            name = song.get("title", "")
            singers = ", ".join([s.get("name", "") for s in song.get("singer", [])])
            vip_flag = song.get("pay", {}).get("pay_play", 0) != 0
            album_info = song.get("album", {})
            album_name = album_info.get("name", "")
            album_mid = album_info.get("mid", "")

            formatted_results.append({
                'mid': song.get('mid', ''),
                'name': name,
                'singers': singers,
                'vip': vip_flag,
                'album': album_name,
                'album_mid': album_mid,  # 添加专辑mid用于获取封面
                'interval': song.get('interval', 0)
            })

        return jsonify({'results': formatted_results})

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return jsonify({'error': f'搜索失败: {str(e)}'}), 500


@app.route('/api/download', methods=['POST'])
def api_download():
    """下载歌曲API"""
    data = request.get_json(silent=True) or {}
    song_data = data.get('song_data')
    prefer_flac = data.get('prefer_flac', False)
    add_metadata = data.get('add_metadata', True)  # 默认添加元数据

    if not song_data:
        return jsonify({'error': '缺少歌曲数据'}), 400

    try:
        song_info = song_data
        mid = song_info.get('mid')
        vip = song_info.get('vip', False)
        album_mid = song_info.get('album_mid', '')

        if not mid:
            return jsonify({'error': '无效的歌曲ID'}), 400

        if vip and not credential_manager.credential:
            return jsonify({'error': '这首歌是VIP歌曲，需要登录才能下载高音质版本'}), 403

        song_name = song_info.get('name', '未知歌曲')
        singer_name = song_info.get('singers', '未知歌手')

        # 根据音质偏好设置下载策略
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

        safe_filename = sanitize_filename(f"{song_name} - {singer_name}")
        download_info = {}
        downloaded_file_type = None

        # 尝试不同音质
        for file_type, quality_name in quality_order:
            filepath = MUSIC_DIR / f"{safe_filename}{file_type.e}"

            # 如果文件已存在，直接返回
            if filepath.exists():
                download_info = {
                    'filename': f"{safe_filename}{file_type.e}",
                    'quality': quality_name,
                    'filepath': str(filepath),
                    'cached': True
                }
                downloaded_file_type = file_type
                logger.info(f"使用缓存文件: {filepath.name}")
                break

            logger.info(f"尝试下载 {quality_name}: {safe_filename}{file_type.e}{' [VIP]' if vip else ''}")

            # 获取歌曲URL
            urls = run_async(get_song_urls([mid], file_type=file_type, credential=credential_manager.credential))
            url = urls.get(mid)

            if not url:
                logger.warning(f"无法获取歌曲URL ({quality_name})")
                continue

            if isinstance(url, list):
                url = url[0]

            # 下载歌曲
            content = run_async(download_file_content(url))

            if content:
                with open(filepath, "wb") as f:
                    f.write(content)
                logger.info(f"下载成功 ({quality_name}): {filepath.name}")
                download_info = {
                    'filename': f"{safe_filename}{file_type.e}",
                    'quality': quality_name,
                    'filepath': str(filepath),
                    'cached': False
                }
                downloaded_file_type = file_type
                break
            else:
                logger.warning(f"{quality_name} 下载失败")

        # 为文件添加元数据（FLAC和MP3都支持）
        if (download_info and not download_info.get('cached', False) and
                add_metadata and downloaded_file_type in [SongFileType.FLAC, SongFileType.MP3_320,
                                                          SongFileType.MP3_128]):
            try:
                # 获取封面URL
                cover_url = None
                if album_mid:
                    cover_url = get_cover(album_mid, cover_size)  # 使用指定尺寸的封面

                # 获取歌词
                lyrics_data = None
                try:
                    lyrics_data = run_async(get_lyric(mid))
                except Exception as e:
                    logger.warning(f"获取歌词失败: {e}")

                # 添加元数据到文件
                if cover_url or lyrics_data:
                    metadata_success = run_async(add_metadata_to_file(
                        Path(download_info['filepath']),
                        song_info,
                        cover_url,
                        lyrics_data
                    ))
                    download_info['metadata_added'] = metadata_success
                else:
                    download_info['metadata_added'] = False

            except Exception as e:
                logger.error(f"添加元数据失败: {e}")
                download_info['metadata_added'] = False

        if download_info:
            return jsonify(download_info)
        else:
            return jsonify({'error': '所有音质下载失败'}), 500

    except Exception as e:
        logger.error(f"下载失败: {e}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@app.route('/api/file/<filename>')
def api_file(filename):
    """提供文件下载"""
    # 安全检查：防止路径遍历攻击
    if '..' in filename or filename.startswith('/'):
        return jsonify({'error': '无效的文件名'}), 400

    filepath = MUSIC_DIR / filename
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


def stop_all_threads():
    """停止所有后台线程"""
    global stop_threads
    stop_threads = True


def init_app():
    """初始化应用"""
    credential_manager.load_and_refresh_sync()
    start_credential_checker()
    start_cleanup_scheduler()
    logger.info("应用初始化完成")


if __name__ == '__main__':
    try:
        init_app()
        app.run(debug=False, host='0.0.0.0', port=6022, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止...")
    except Exception as e:
        logger.error(f"应用启动失败: {e}")
    finally:
        stop_all_threads()
        logger.info("应用已停止")