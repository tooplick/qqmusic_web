from flask import Blueprint, request, jsonify
from datetime import datetime
from pathlib import Path
from qqmusic_api import search
from qqmusic_api.song import get_song_urls, SongFileType
from qqmusic_api.lyric import get_lyric
import logging
from ..utils.thread_utils import run_async  # 修复这里：run_utils -> run_async

bp = Blueprint('api', __name__)
logger = logging.getLogger("qqmusic_web")


def get_credential_manager():
    """获取凭证管理器实例"""
    from flask import current_app
    return current_app.config['credential_manager']


def get_music_downloader():
    """获取音乐下载器实例"""
    from flask import current_app
    return current_app.config['music_downloader']


@bp.route('/search', methods=['POST'])
def api_search():
    """搜索歌曲API"""
    data = request.get_json(silent=True) or {}
    keyword = data.get('keyword', '').strip()
    page = data.get('page', 1)

    if not keyword:
        return jsonify({'error': '歌曲名不能为空'}), 400

    try:
        # 一次性获取60条结果
        search_limit = 60
        results = run_async(search.search_by_type(keyword, num=search_limit))
        if not results:
            return jsonify({'error': '未找到歌曲'}), 404

        # 计算分页
        from ..config import CONFIG
        page_size = CONFIG["SEARCH_LIMIT"]
        total_results = len(results)
        total_pages = (total_results + page_size - 1) // page_size

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

            formatted_results.append({
                'mid': song.get('mid', ''),
                'name': song.get("title", ""),
                'singers': singers,
                'vip': song.get("pay", {}).get("pay_play", 0) != 0,
                'album': song.get("album", {}).get("name", ""),
                'album_mid': song.get("album", {}).get("mid", ""),
                'interval': song.get('interval', 0),
                'raw_data': song
            })

        return jsonify({
            'results': formatted_results,
            'pagination': {
                'current_page': page,
                'has_prev': page > 1,
                'has_next': page < total_pages,
                'total_pages': total_pages,
                'total_results': total_results
            },
            'all_results': total_results
        })

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return jsonify({'error': f'搜索失败: {str(e)}'}), 500


@bp.route('/play_url', methods=['POST'])
def api_play_url():
    """获取歌曲播放URL API"""
    data = request.get_json(silent=True) or {}
    song_data = data.get('song_data')
    prefer_flac = data.get('prefer_flac', False)

    if not song_data:
        return jsonify({'error': '缺少歌曲数据'}), 400

    try:
        credential_manager = get_credential_manager()

        # 检查VIP歌曲权限
        if song_data.get('vip', False) and not credential_manager.credential:
            return jsonify({
                'error': '这首歌是VIP歌曲，需要登录才能播放'
            }), 403

        # 设置音质获取策略
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

        # 尝试获取URL
        for file_type, quality_name in quality_order:
            logger.info(f"尝试获取 {quality_name} 播放URL: {song_data.get('name', '')}")

            # 异步运行获取URL的函数
            urls = run_async(get_song_urls(
                [song_data.get('mid', '')],
                file_type=file_type,
                credential=credential_manager.credential
            ))
            url = urls.get(song_data.get('mid', ''))

            if not url:
                continue

            # API可能返回列表，取第一个
            if isinstance(url, list):
                url = url[0]

            if url:
                logger.info(f"获取URL成功 ({quality_name}): {song_data.get('name', '')}")
                return jsonify({
                    'url': url,
                    'quality': quality_name,
                    'song_mid': song_data.get('mid', '')
                })

        # 如果所有音质都失败
        return jsonify({'error': '所有音质均无法获取播放URL'}), 500

    except Exception as e:
        logger.error(f"获取播放URL失败: {e}")
        return jsonify({'error': f'获取播放URL失败: {str(e)}'}), 500


@bp.route('/download', methods=['POST'])
def api_download():
    """下载歌曲API"""
    data = request.get_json(silent=True) or {}
    song_data = data.get('song_data')
    prefer_flac = data.get('prefer_flac', False)
    add_metadata = data.get('add_metadata', True)

    if not song_data:
        return jsonify({'error': '缺少歌曲数据'}), 400

    try:
        credential_manager = get_credential_manager()
        music_downloader = get_music_downloader()

        # 检查VIP歌曲权限
        if song_data.get('vip', False) and not credential_manager.credential:
            return jsonify({
                'error': '这首歌是VIP歌曲，需要登录才能下载高音质版本'
            }), 403

        # 创建SongInfo对象
        from ..models import SongInfo
        song_info = SongInfo(
            mid=song_data.get('mid', ''),
            name=song_data.get('name', ''),
            singers=song_data.get('singers', ''),
            vip=song_data.get('vip', False),
            album=song_data.get('album', ''),
            album_mid=song_data.get('album_mid', ''),
            interval=song_data.get('interval', 0),
            raw_data=song_data.get('raw_data')
        )

        # 下载歌曲
        result = run_async(music_downloader.download_song(
            song_info, prefer_flac, add_metadata
        ))

        if result:
            return jsonify({
                'filename': result.filename,
                'quality': result.quality,
                'filepath': result.filepath,
                'cached': result.cached,
                'metadata_added': result.metadata_added
            })
        else:
            return jsonify({'error': '所有音质下载失败'}), 500

    except Exception as e:
        logger.error(f"下载失败: {e}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500


@bp.route('/credential/status')
def api_credential_status():
    """获取凭证状态"""
    credential_manager = get_credential_manager()
    return jsonify(credential_manager.status)


@bp.route('/health')
def api_health():
    """健康检查端点"""
    from ..config import CONFIG
    music_dir = Path(CONFIG["MUSIC_DIR"])
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "music_dir_exists": music_dir.exists(),
        "music_files_count": len(list(music_dir.glob("*"))) if music_dir.exists() else 0,
        "environment": "container" if CONFIG["IS_CONTAINER"] else "native"
    })


@bp.route('/lyric/<song_mid>')
def api_lyric(song_mid):
    """获取歌词API"""
    try:
        lyrics_data = run_async(get_lyric(song_mid))
        return jsonify(lyrics_data)
    except Exception as e:
        logger.error(f"获取歌词失败: {e}")
        return jsonify({'error': f'获取歌词失败: {str(e)}'}), 500