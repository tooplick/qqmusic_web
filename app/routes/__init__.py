from .web_routes import bp as web_bp
from .api_routes import bp as api_bp
from .admin_routes import bp as admin_bp  # 新增

__all__ = ['web_bp', 'api_bp', 'admin_bp']  # 更新