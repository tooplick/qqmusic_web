from flask import Blueprint, render_template, jsonify, request
import os
import base64
import pickle
import shutil
import threading
import time
from pathlib import Path
from qqmusic_api.login import get_qrcode, check_qrcode, QRLoginType, QRCodeLoginEvents, check_expired
from ..utils.thread_utils import run_async
from ..config import CONFIG
import logging

logger = logging.getLogger("qqmusic_web")

bp = Blueprint('admin', __name__, url_prefix='/admin')

# 用于存储活跃的二维码会话
qr_sessions = {}

@bp.route('/')
def admin_index():
    """管理员页面"""
    return render_template('admin.html')

@bp.route('/api/get_qrcode/<qr_type>')
def get_qrcode_api(qr_type):
    """获取登录二维码"""
    try:
        logger.info(f"收到二维码生成请求，类型: {qr_type}")
        
        # 使用 run_async 来运行异步函数
        if qr_type == 'wx':
            qr = run_async(get_qrcode(QRLoginType.WX))
        elif qr_type == 'qq':
            qr = run_async(get_qrcode(QRLoginType.QQ))
        else:
            return jsonify({'error': '无效的登录类型，仅支持 "wx" 或 "qq"'}), 400
        
        logger.info(f"二维码生成成功，数据长度: {len(qr.data)}")
        
        # 生成会话ID
        session_id = str(int(time.time()))
        qr_sessions[session_id] = {
            'qr': qr,
            'status': 'waiting',
            'created_at': time.time()
        }
        
        # 启动后台线程检查二维码状态
        thread = threading.Thread(target=check_qr_status, args=(session_id,))
        thread.daemon = True
        thread.start()
        
        qr_base64 = base64.b64encode(qr.data).decode()
        return jsonify({
            'session_id': session_id,
            'qrcode': qr_base64
        })
        
    except Exception as e:
        logger.error(f"获取二维码失败: {e}", exc_info=True)
        return jsonify({'error': f'获取二维码失败: {str(e)}'}), 500

def check_qr_status(session_id):
    """后台线程：检查二维码状态"""
    try:
        if session_id not in qr_sessions:
            return
            
        qr_data = qr_sessions[session_id]
        qr = qr_data['qr']
        max_attempts = 30  # 最多尝试30次，每次间隔2秒，总计60秒超时
        attempts = 0
        
        while attempts < max_attempts and session_id in qr_sessions:
            try:
                # 使用 run_async 在后台线程中运行异步函数
                event, credential = run_async(check_qrcode(qr))
                logger.info(f"二维码状态: {event.name}")
                
                if event == QRCodeLoginEvents.DONE:
                    logger.info(f"登录成功!")
                    # 保存凭证
                    credential_file = Path(CONFIG["CREDENTIAL_FILE"])
                    credential_file.parent.mkdir(parents=True, exist_ok=True)
                    with credential_file.open("wb") as f:
                        pickle.dump(credential, f)
                    logger.info("凭证已保存")
                    qr_sessions[session_id]['status'] = 'success'
                    qr_sessions[session_id]['credential'] = credential
                    return
                elif event == QRCodeLoginEvents.TIMEOUT:
                    logger.info("二维码过期，请重新获取")
                    qr_sessions[session_id]['status'] = 'timeout'
                    return
                elif event == QRCodeLoginEvents.REFUSE:
                    logger.info("拒绝登录，请重新扫码")
                    qr_sessions[session_id]['status'] = 'refused'
                    return
                elif event == QRCodeLoginEvents.WAITING:
                    qr_sessions[session_id]['status'] = 'waiting'
                    
            except Exception as e:
                logger.error(f"检查二维码状态时发生错误: {e}")
                
            attempts += 1
            time.sleep(2)
            
        if session_id in qr_sessions:
            qr_sessions[session_id]['status'] = 'timeout'
        logger.info("二维码验证超时，请重新获取")
        
    except Exception as e:
        logger.error(f"二维码状态检查线程错误: {e}", exc_info=True)

@bp.route('/api/qr_status/<session_id>')
def get_qr_status(session_id):
    """获取二维码状态"""
    try:
        if session_id not in qr_sessions:
            return jsonify({'error': '会话不存在或已过期'}), 404
            
        status_data = qr_sessions[session_id]
        return jsonify({
            'status': status_data['status'],
            'valid': status_data['status'] == 'success'
        })
    except Exception as e:
        logger.error(f"获取二维码状态失败: {e}")
        return jsonify({'error': f'获取二维码状态失败: {str(e)}'}), 500

@bp.route('/api/credential/status')
def check_credential_status():
    """检查凭证状态"""
    try:
        manager = CredentialManager()
        is_valid = run_async(manager.check_status())
        return jsonify({"valid": is_valid})
    except Exception as e:
        logger.error(f"检查凭证状态失败: {e}", exc_info=True)
        return jsonify({"valid": False, "error": str(e)}), 500

@bp.route('/api/credential/refresh', methods=['POST'])
def refresh_credential():
    """刷新凭证"""
    try:
        manager = CredentialManager()
        if not manager.load_credential():
            return jsonify({'error': '未找到凭证文件'}), 404
            
        # 确保凭证已加载
        if manager.credential is None:
            return jsonify({'error': '凭证加载失败'}), 400
            
        is_expired = run_async(check_expired(manager.credential))
        can_refresh = run_async(manager.credential.can_refresh())
        
        if not can_refresh:
            return jsonify({'error': '此凭证不支持刷新'}), 400
            
        run_async(manager.credential.refresh())
        if manager.save_credential():
            return jsonify({'success': True, 'message': '凭证刷新成功'})
        else:
            return jsonify({'error': '凭证刷新成功但保存失败'}), 500
    except Exception as e:
        logger.error(f"刷新凭证失败: {e}", exc_info=True)
        return jsonify({'error': f'刷新凭证失败: {str(e)}'}), 500

@bp.route('/api/credential/info')
def get_credential_info():
    """获取凭证信息"""
    try:
        manager = CredentialManager()
        if not manager.load_credential() or manager.credential is None:
            return jsonify({'error': '未找到凭证文件'}), 404
        
        # 返回凭证的基本信息，隐藏敏感信息
        cred_dict = manager.credential.__dict__
        info = {}
        for key, value in cred_dict.items():
            if key.lower() in ['token', 'refresh_token', 'cookie']:
                # 敏感信息，只显示部分
                if value and len(str(value)) > 10:
                    info[key] = f"{str(value)[:10]}..."
                else:
                    info[key] = str(value)
            else:
                info[key] = str(value)
        
        return jsonify(info)
    except Exception as e:
        logger.error(f"获取凭证信息失败: {e}", exc_info=True)
        return jsonify({'error': f'获取凭证信息失败: {str(e)}'}), 500

@bp.route('/api/clear_music', methods=['POST'])
def clear_music_folder():
    """清空音乐文件夹"""
    try:
        music_dir = Path(CONFIG["MUSIC_DIR"])
        
        # 检查音乐目录是否存在
        if not music_dir.exists():
            return jsonify({'success': False, 'message': '音乐文件夹不存在'})
        
        # 获取文件夹中的文件数量
        files = list(music_dir.glob("*"))
        file_count = len(files)
        
        if file_count == 0:
            return jsonify({'success': True, 'message': '音乐文件夹已经是空的', 'deleted_count': 0})
        
        # 删除所有文件
        deleted_count = 0
        for file_path in files:
            try:
                if file_path.is_file():
                    file_path.unlink()
                    deleted_count += 1
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
                    deleted_count += 1
            except Exception as e:
                logger.error(f"删除文件失败 {file_path}: {e}")
        
        return jsonify({
            'success': True, 
            'message': f'已清空音乐文件夹，删除了 {deleted_count} 个文件/文件夹',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"清空音乐文件夹失败: {e}", exc_info=True)
        return jsonify({'error': f'清空音乐文件夹失败: {str(e)}'}), 500

class CredentialManager:
    """凭证管理器"""

    def __init__(self):
        self.credential_file = Path(CONFIG["CREDENTIAL_FILE"])
        self.credential = None

    def load_credential(self):
        """加载本地凭证"""
        if not self.credential_file.exists():
            logger.info("未找到凭证文件，请先运行登录程序")
            return None

        try:
            with self.credential_file.open("rb") as f:
                cred = pickle.load(f)
            self.credential = cred
            return cred
        except Exception as e:
            logger.error(f"加载凭证失败: {e}")
            return None

    def save_credential(self):
        """保存凭证到文件"""
        if not self.credential:
            logger.info("没有可保存的凭证")
            return False

        try:
            with self.credential_file.open("wb") as f:
                pickle.dump(self.credential, f)
            logger.info("凭证已保存")
            return True
        except Exception as e:
            logger.error(f"保存凭证失败: {e}")
            return False

    async def check_status(self):
        """检查凭证状态"""
        if not self.load_credential() or self.credential is None:
            return False

        try:
            # 检查是否过期
            is_expired = await check_expired(self.credential)
            
            # 检查是否可以刷新
            can_refresh = await self.credential.can_refresh()
            
            logger.info(f"凭证状态 - 是否过期: {is_expired}, 可刷新: {can_refresh}")
            
            if hasattr(self.credential, 'musicid'):
                logger.info(f"用户ID: {self.credential.musicid}")

            return not is_expired
        except Exception as e:
            logger.error(f"检查凭证状态时发生错误: {e}")
            return False