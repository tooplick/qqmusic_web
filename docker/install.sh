#!/bin/bash
# QQMusic Web 一键安装脚本

set -e

echo "开始安装 QQMusic Web..."

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker 安装完成"
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "安装 Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose 安装完成"
fi

# 创建项目目录
PROJECT_DIR="/opt/qqmusic-web"
echo "创建项目目录: $PROJECT_DIR"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 下载项目文件
echo "下载项目文件..."
if [ -d ".git" ]; then
    echo "项目已存在，更新到最新版本..."
    git pull origin main
else
    git clone https://github.com/tooplick/qqmusic_web.git .
fi

echo "项目文件下载完成"

# 检查 Docker 配置文件是否存在
if [ ! -f "docker/dockerfile" ]; then
    echo "错误: 未找到 docker/dockerfile"
    exit 1
fi

if [ ! -f "docker/docker-compose.yml" ]; then
    echo "错误: 未找到 docker/docker-compose.yml"
    exit 1
fi

echo "使用项目自带的 Docker 配置..."

# 进入 docker 目录并启动服务
cd docker
echo "构建并启动 Docker 容器..."
docker-compose up -d --build

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "QQMusic Web 安装成功！"
    echo ""
    echo "访问地址: http://localhost:6022"
    echo "项目目录: $PROJECT_DIR"
    echo ""
    echo "管理命令:"
    echo "   查看日志: cd $PROJECT_DIR/docker && docker-compose logs -f"
    echo "   停止服务: cd $PROJECT_DIR/docker && docker-compose down"
    echo "   重启服务: cd $PROJECT_DIR/docker && docker-compose restart"
    echo "   更新服务: cd $PROJECT_DIR && git pull && cd docker && docker-compose up -d --build"
else
    echo "服务启动失败，请检查日志:"
    docker-compose logs
    exit 1
fi