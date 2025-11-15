import aiohttp
import logging
from typing import Optional, Dict, Any, Literal
from pathlib import Path

logger = logging.getLogger("qqmusic_web")

class CoverManager:
    """封面管理器"""

    def __init__(self, config):
        self.config = config

    def get_cover_url_by_album_mid(self, mid: str, size: Literal[150, 300, 500, 800] = None) -> Optional[str]:
        """通过专辑MID获取封面URL"""
        if not mid:
            return None
        if size is None:
            size = self.config["COVER_SIZE"]
        if size not in [150, 300, 500, 800]:
            raise ValueError("不支持的封面尺寸")
        return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{mid}.jpg"

    def get_cover_url_by_vs(self, vs: str, size: Literal[150, 300, 500, 800] = None) -> Optional[str]:
        """通过VS值获取封面URL"""
        if not vs:
            return None
        if size is None:
            size = self.config["COVER_SIZE"]
        if size not in [150, 300, 500, 800]:
            raise ValueError("不支持的封面尺寸")
        return f"https://y.qq.com/music/photo_new/T062R{size}x{size}M000{vs}.jpg"

    async def get_valid_cover_url(self, song_data: Dict[str, Any], size: Literal[150, 300, 500, 800] = None) -> Optional[str]:
        """获取并验证有效的封面URL（按优先级尝试所有可能的VS值）"""
        if size is None:
            size = self.config["COVER_SIZE"]

        # 1. 优先尝试专辑MID
        album_mid = song_data.get('album', {}).get('mid', '')
        if album_mid:
            url = self.get_cover_url_by_album_mid(album_mid, size)
            logger.debug(f"尝试专辑MID封面: {url}")
            cover_data = await self.download_cover(url)
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
            url = self.get_cover_url_by_vs(candidate['value'], size)
            logger.debug(f"尝试VS值封面 [{candidate['source']}]: {url}")
            cover_data = await self.download_cover(url)
            if cover_data:
                logger.info(f"使用VS值封面 [{candidate['source']}]: {url}")
                return url

        logger.warning("未找到任何有效的封面URL")
        return None

    async def download_cover(self, url: str) -> Optional[bytes]:
        """下载封面图片"""
        if not url:
            return None

        try:
            async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.config["DOWNLOAD_TIMEOUT"])
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