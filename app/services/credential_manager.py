import pickle
import logging
from pathlib import Path
from typing import Optional
from qqmusic_api.login import Credential, check_expired
from ..utils.thread_utils import run_async

logger = logging.getLogger("qqmusic_web")

class CredentialManager:
    """凭证管理器"""

    def __init__(self, config):
        self.config = config
        self.credential = None
        self.status = {
            "enabled": True,
            "last_check": None,
            "status": "未检测到凭证",
            "expired": True
        }

    def load_credential(self) -> Optional[Credential]:
        """加载凭证"""
        credential_file = Path(self.config["CREDENTIAL_FILE"])
        if not credential_file.exists():
            return None

        try:
            with credential_file.open("rb") as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"加载凭证文件失败: {e}")
            return None

    def save_credential(self, cred: Credential) -> bool:
        """保存凭证"""
        try:
            credential_file = Path(self.config["CREDENTIAL_FILE"])
            with credential_file.open("wb") as f:
                pickle.dump(cred, f)
            return True
        except Exception as e:
            logger.error(f"保存凭证文件失败: {e}")
            return False

    def load_and_refresh_sync(self) -> Optional[Credential]:
        """同步加载和刷新凭证"""
        credential_file = Path(self.config["CREDENTIAL_FILE"])
        if not credential_file.exists():
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
                logger.info("本地凭证已过期，将以未登录方式下载")
                self.status.update({
                    "status": "本地凭证已过期，将以未登录方式下载",
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