from flask import Blueprint, render_template, send_file, jsonify
from pathlib import Path

bp = Blueprint('web', __name__)


def get_credential_manager():
    """获取凭证管理器实例"""
    from flask import current_app
    return current_app.config['credential_manager']


@bp.route('/')
def index():
    """提供前端页面"""
    credential_manager = get_credential_manager()
    from ..config import CONFIG
    has_credential = (Path(CONFIG["CREDENTIAL_FILE"]).exists() and
                      credential_manager.credential is not None)
    return render_template('index.html', has_credential=has_credential)


@bp.route('/api/file/<filename>')
def api_file(filename):
    """提供文件下载"""
    from ..config import CONFIG

    # 安全检查
    if '..' in filename or filename.startswith('/'):
        return jsonify({'error': '无效的文件名'}), 400

    filepath = Path(CONFIG["MUSIC_DIR"]) / filename
    if filepath.exists() and filepath.is_file():
        return send_file(filepath, as_attachment=True)
    else:
        return jsonify({'error': '文件不存在'}), 404