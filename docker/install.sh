#!/bin/bash

set -e  # 遇到错误立即退出

echo "🚀 开始部署 QQMusic Web..."

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 sudo 运行此脚本: sudo -E bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/tooplick/qqmusic-web/docker/install.sh)\""
    exit 1
fi

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "📦 安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "📦 安装 Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# 创建项目目录
PROJECT_DIR="/opt/qqmusic-web"
echo "📁 创建项目目录: $PROJECT_DIR"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 下载项目文件
echo "📥 下载项目文件..."
if command -v git &> /dev/null; then
    git clone https://github.com/tooplick/qqmusic_web.git .
else
    # 如果没有 git，使用 curl 下载主要文件
    curl -fsSL https://github.com/tooplick/qqmusic_web/archive/main.tar.gz | tar -xz --strip-components=1
fi

# 创建 Dockerfile（如果不存在）
if [ ! -f "Dockerfile" ]; then
    cat > Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用文件
COPY . .

# 暴露端口
EXPOSE 6022

# 启动应用
CMD ["python", "app.py"]
EOF
fi

# 创建 docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  qqmusic-web:
    build: .
    ports:
      - "6022:6022"
    volumes:
      - .:/app  
    environment:
      - FLASK_ENV=production
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6022"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF

# 设置权限
chown -R $(logname):$(logname) $PROJECT_DIR
chmod -R 755 $PROJECT_DIR

# 构建并启动容器
echo "🔨 构建 Docker 容器..."
docker-compose up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "✅ QQMusic Web 部署成功！"
    echo "🌐 访问地址: http://$(curl -s ifconfig.me):6022"
    echo "📁 项目目录: $PROJECT_DIR"
    echo "🔧 管理命令:"
    echo "   查看日志: cd $PROJECT_DIR && docker-compose logs -f"
    echo "   停止服务: cd $PROJECT_DIR && docker-compose down"
    echo "   重启服务: cd $PROJECT_DIR && docker-compose restart"
else
    echo "❌ 服务启动失败，请检查日志: cd $PROJECT_DIR && docker-compose logs"
    exit 1
fi