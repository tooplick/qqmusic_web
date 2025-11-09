#!/bin/bash
# QQMusic Web 一键部署脚本

set -e

echo "🚀 开始部署 QQMusic Web..."
echo "📁 项目地址: https://github.com/tooplick/qqmusic_web"

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 sudo 运行此脚本"
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
if [ -d ".git" ]; then
    echo "🔄 项目已存在，更新到最新版本..."
    git pull origin main
else
    git clone https://github.com/tooplick/qqmusic_web.git .
fi

# 检查必要的文件
if [ ! -f "docker/dockerfile" ]; then
    echo "❌ 错误: 未找到 docker/dockerfile"
    exit 1
fi

if [ ! -f "docker/docker-compose.yml" ]; then
    echo "❌ 错误: 未找到 docker/docker-compose.yml"
    exit 1
fi


# 使用项目自带的 docker-compose 配置
echo "📋 使用项目自带的 Docker 配置..."
cd docker

# 构建并启动服务
echo "🔨 构建并启动容器..."
docker-compose up -d --build

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 15

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "🎉 QQMusic Web 部署成功！"
    echo ""
    echo "🌐 访问地址: http://$(curl -s ifconfig.me):6022"
    echo "📁 项目目录: $PROJECT_DIR"
    echo ""
    echo "🔧 管理命令:"
    echo "   查看日志: cd $PROJECT_DIR/docker && docker-compose logs -f"
    echo "   停止服务: cd $PROJECT_DIR/docker && docker-compose down"
    echo "   重启服务: cd $PROJECT_DIR/docker && docker-compose restart"
    echo "   更新服务: cd $PROJECT_DIR && git pull && cd docker && docker-compose up -d --build"
else
    echo "❌ 服务启动失败，请检查日志:"
    docker-compose logs
    exit 1
fi