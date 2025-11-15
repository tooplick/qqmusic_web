from flask import Flask
import logging


def create_app():
    """应用工厂函数"""
    app = Flask(__name__)

    # 加载配置
    from .config import CONFIG
    app.config.update(CONFIG)

    # 初始化服务
    from .services.credential_manager import CredentialManager
    from .services.cover_manager import CoverManager
    from .services.file_manager import FileManager
    from .services.metadata_manager import MetadataManager
    from .services.music_downloader import MusicDownloader

    # 创建服务实例
    credential_manager = CredentialManager(app.config)
    cover_manager = CoverManager(app.config)
    file_manager = FileManager(app.config)
    metadata_manager = MetadataManager(app.config, cover_manager)
    music_downloader = MusicDownloader(
        app.config, credential_manager, file_manager, metadata_manager
    )

    # 将服务实例保存到app配置中以便访问
    app.config['credential_manager'] = credential_manager
    app.config['music_downloader'] = music_downloader
    app.config['cover_manager'] = cover_manager
    app.config['file_manager'] = file_manager
    app.config['metadata_manager'] = metadata_manager

    # 注册蓝图
    from .routes.web_routes import bp as web_bp
    from .routes.api_routes import bp as api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    return app


def init_app(app):
    """初始化应用"""
    credential_manager = app.config['credential_manager']
    credential_manager.load_and_refresh_sync()
    logger = logging.getLogger("qqmusic_web")
    logger.info(f"应用初始化完成 - 运行环境: {'容器' if app.config['IS_CONTAINER'] else '原生'}")
    logger.info(f"凭证文件路径: {app.config['CREDENTIAL_FILE']}")
    logger.info(f"音乐目录路径: {app.config['MUSIC_DIR']}")


def stop_all_threads():
    """停止所有后台线程"""
    from .utils.thread_utils import thread_pool
    thread_pool.shutdown(wait=False)