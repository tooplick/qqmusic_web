from pathlib import Path
import os

def get_project_root():
    """获取项目根目录（包含 run.py 的目录）"""
    current_file = Path(__file__).resolve()
    
    # 当前文件在 app/config.py，所以项目根目录是祖父目录
    project_root = current_file.parent.parent
    
    # 验证项目根目录是否包含 run.py
    if (project_root / 'run.py').exists():
        return project_root
    
    # 如果找不到 run.py，回退到当前工作目录
    return Path.cwd()

def get_config():
    """获取动态配置，支持容器和非容器环境"""
    # 判断是否在容器中运行（通过检查 /app 目录是否存在）
    is_container = Path("/app").exists()

    if is_container:
        # 容器环境 - 使用挂载路径
        base_dir = Path("/app")
        credential_dir = base_dir / "credential"
        music_dir = base_dir / "music"
    else:
        # 非容器环境 - 使用项目根目录
        base_dir = get_project_root()
        credential_dir = base_dir / "credential"
        music_dir = base_dir / "music"

    # 确保目录存在
    credential_dir.mkdir(exist_ok=True)
    music_dir.mkdir(exist_ok=True)
    
    # 凭证文件路径
    credential_file = credential_dir / "qqmusic_cred.pkl"

    return {
        "CREDENTIAL_FILE": str(credential_file),
        "MUSIC_DIR": str(music_dir),
        "MAX_FILENAME_LENGTH": 100,
        "COVER_SIZE": 800,  # 封面尺寸[150, 300, 500, 800]
        "DOWNLOAD_TIMEOUT": 60,
        "SEARCH_LIMIT": 10,
        "SERVER_HOST": "0.0.0.0",
        "SERVER_PORT": 6022,
        "IS_CONTAINER": is_container  # 环境标识
    }

CONFIG = get_config()