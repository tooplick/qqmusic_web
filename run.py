#!/usr/bin/env python3
"""
前端
"""
import sys
import os

# 添加应用目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, init_app, stop_all_threads
import logging
import signal


def signal_handler(signum, frame):
    """信号处理函数"""
    print(f"\n接收到信号 {signum}，正在停止应用...")
    stop_all_threads()
    sys.exit(0)


def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("app/app.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

    # 创建并初始化应用
    app = create_app()
    init_app(app)

    # 启动应用
    try:
        app.run(
            debug=False,
            host=app.config['SERVER_HOST'],
            port=app.config['SERVER_PORT'],
            use_reloader=False
        )
    except Exception as e:
        logging.error(f"应用启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()