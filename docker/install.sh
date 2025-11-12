#!/bin/bash
# QQMusic Web Docker 环境一键安装脚本

set -e

echo "开始安装 QQMusic Web Docker 环境..."

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 创建项目目录
PROJECT_DIR="/opt/qqmusic-web"
echo "创建项目目录: $PROJECT_DIR"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 创建数据目录
DATA_DIR="/root/qqmusic-web"
echo "创建数据目录: $DATA_DIR"
mkdir -p $DATA_DIR
mkdir -p $DATA_DIR/music
mkdir -p $DATA_DIR/logs

# 设置权限
chmod 755 $DATA_DIR
chmod 755 $DATA_DIR/music
chmod 755 $DATA_DIR/logs

# 如果项目中有凭证文件，复制到数据目录
if [ -f "qqmusic_cred.pkl" ]; then
    echo "发现项目中的凭证文件，复制到数据目录..."
    cp qqmusic_cred.pkl $DATA_DIR/qqmusic_cred.pkl
    chmod 644 $DATA_DIR/qqmusic_cred.pkl
fi

# 下载项目文件
echo "下载项目文件..."
# [原有的下载代码保持不变...]

# 检测是否在中国地区
echo "检测网络环境..."
# [原有的网络检测代码保持不变...]

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

# 检查 Docker 配置文件是否存在
if [ ! -f "docker/dockerfile" ]; then
    echo "错误: 未找到 docker/dockerfile"
    exit 1
fi

if [ ! -f "docker/docker-compose.yml" ]; then
    echo "错误: 未找到 docker/docker-compose.yml"
    exit 1
fi

echo "使用docker-compose.yml配置..."

# 进入 docker 目录
cd docker

# 停止并删除现有容器
echo "停止并删除现有容器..."
docker-compose down 2>/dev/null || true

# 获取镜像名称并删除旧镜像
echo "删除旧镜像..."
IMAGE_NAME=$(grep "image:" docker-compose.yml | awk '{print $2}' | head -1)
if [ -n "$IMAGE_NAME" ] && docker image inspect "$IMAGE_NAME" &>/dev/null; then
    echo "删除旧镜像: $IMAGE_NAME"
    docker rmi "$IMAGE_NAME" 2>/dev/null || true
fi

# 构建并启动新容器
echo "构建并启动新的 Docker 容器..."
docker-compose up -d --build --force-recreate

# 等待服务启动
echo "等待服务启动..."
sleep 5

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "QQMusic Web Docker 环境安装成功！"
    echo ""
    
    # 显示数据目录信息
    echo "数据目录: $DATA_DIR"
    echo "凭证文件位置: $DATA_DIR/qqmusic_cred.pkl"
    echo "音乐文件存储位置: $DATA_DIR/music/"
    echo "日志文件位置: $DATA_DIR/logs/"
    echo ""
    
    # 获取本地IP地址
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" = "" ]; then
        LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
    fi
    if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" = "" ]; then
        LOCAL_IP=$(ip addr show 2>/dev/null | grep -oP 'inet \K[\d.]+' | grep -v '127.0.0.1' | head -1)
    fi
    if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" = "" ]; then
        LOCAL_IP="127.0.0.1"
    fi
    
    echo "本地访问地址: http://localhost:6022"
    if [ "$LOCAL_IP" != "127.0.0.1" ]; then
        echo "局域网访问地址: http://${LOCAL_IP}:6022"
    fi
    
    # 获取公网IP地址
    PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me || curl -s --max-time 5 ipinfo.io/ip || curl -s --max-time 5 api.ipify.org || echo "")
    
    if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "" ]; then
        echo "公网访问地址: http://${PUBLIC_IP}:6022"
        echo "注意: 请确保防火墙已开放 6022 端口"
    else
        echo "无法自动获取公网IP，请手动检查网络配置"
        echo "您可以通过以下命令查看公网IP: curl ifconfig.me"
    fi
    
    echo ""
    echo "项目目录: $PROJECT_DIR"
    echo ""
    
    echo "Docker 管理命令:"
    echo "   查看状态: cd $PROJECT_DIR/docker && sudo docker-compose ps"
    echo "   查看日志: cd $PROJECT_DIR/docker && sudo docker-compose logs -f"
    echo "   停止服务: cd $PROJECT_DIR/docker && sudo docker-compose down"
    echo "   重启服务: cd $PROJECT_DIR/docker && sudo docker-compose restart"
    echo "   更新服务: cd $PROJECT_DIR/docker && sudo docker-compose up -d --build --force-recreate"
    
    echo ""
    echo "重要提示:"
    echo "   所有数据都存储在: $DATA_DIR"
    echo "   如需管理凭证文件，请操作: $DATA_DIR/qqmusic_cred.pkl"
    echo "   音乐文件位置: $DATA_DIR/music/"
    echo "   日志文件位置: $DATA_DIR/logs/"
    echo "   如需备份，请备份整个数据目录: $DATA_DIR"
    
    echo ""
else
    echo "服务启动失败，请检查日志:"
    cd $PROJECT_DIR/docker && docker-compose logs
    exit 1
fi