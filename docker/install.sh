#!/bin/bash
# QQMusic Web 一键安装脚本

set -e

echo "开始安装 QQMusic Web..."

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 创建配置目录
echo "创建配置目录..."
mkdir -p /root/qqmusic_web
mkdir -p /root/qqmusic_web/music

# 设置目录权限
chmod 755 /root/qqmusic_web
chmod 755 /root/qqmusic_web/music

echo "配置目录已创建: /root/qqmusic_web/"

# 创建项目目录
PROJECT_DIR="/opt/qqmusic-web"
echo "创建项目目录: $PROJECT_DIR"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# 下载项目文件
echo "下载项目文件..."
# 检查 git 命令是否存在
if command -v git &> /dev/null; then
    if [ -d ".git" ]; then
        echo "项目已存在,更新到最新版本..."
        # 检查当前远程仓库地址
        CURRENT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
        GITEE_REMOTE="https://github.com/tooplick/qqmusic_web.git"
        
        if [ "$CURRENT_REMOTE" != "$GITEE_REMOTE" ]; then
            echo "修正远程仓库地址为 GitHub..."
            git remote set-url origin "$GITEE_REMOTE"
        fi
        
        git pull origin main
    else
        git clone https://github.com/tooplick/qqmusic_web.git .
    fi
    echo "项目文件下载完成"
else
    echo "git 命令不存在，使用 wget 下载项目文件..."
    
    # 检查 wget 命令是否存在
    if ! command -v wget &> /dev/null; then
        echo "安装 wget..."
        if command -v apt-get &> /dev/null; then
            apt-get update
            apt-get install -y wget
        elif command -v yum &> /dev/null; then
            yum install -y wget
        else
            echo "错误: 无法安装 wget，请手动安装后重试"
            exit 1
        fi
    fi
    
    # 删除原有项目文件
    echo "删除原有项目文件..."
    rm -rf ./*
    rm -rf ./.* 2>/dev/null || true
    
    # 下载项目zip文件
    echo "wget项目文件..."
    wget -O qqmusic_web.zip https://github.com/tooplick/qqmusic_web/archive/main.zip
    
    # 检查unzip命令是否存在
    if ! command -v unzip &> /dev/null; then
        echo "安装 unzip..."
        if command -v apt-get &> /dev/null; then
            apt-get install -y unzip
        elif command -v yum &> /dev/null; then
            yum install -y unzip
        else
            echo "错误: 无法安装 unzip，请手动安装后重试"
            exit 1
        fi
    fi
    
    # 解压文件
    echo "解压项目文件..."
    unzip -q qqmusic_web.zip
    
    # 移动文件到当前目录
    echo "移动文件到项目目录..."
    mv qqmusic_web-main/* ./
    mv qqmusic_web-main/.* ./ 2>/dev/null || true
    
    # 清理临时文件
    echo "清理临时文件..."
    rm -rf qqmusic_web-main
    rm -f qqmusic_web.zip
    
    echo "项目文件下载完成"
fi

# 迁移步骤：放在下载项目文件之后，确保两种方式都会执行
echo "检查并迁移旧的凭证文件..."
if [ -f "$PROJECT_DIR/qqmusic_cred.pkl" ]; then
    echo "检测到旧的凭证文件，正在迁移到新位置..."
    cp $PROJECT_DIR/qqmusic_cred.pkl /root/qqmusic_web/qqmusic_cred.pkl
    echo "凭证文件已迁移到 /root/qqmusic_web/qqmusic_cred.pkl"
    
    # 可选：备份后删除旧文件
    # echo "删除旧的凭证文件..."
    # rm -f $PROJECT_DIR/qqmusic_cred.pkl
else
    echo "未找到旧的凭证文件，跳过迁移"
fi

# 检测是否在中国地区
echo "检测网络环境..."
# 检查IP地理位置
IP_INFO=$(curl -s --max-time 5 "http://ip-api.com/json/" || echo "")
if echo "$IP_INFO" | grep -q "\"country\":\"China\""; then
    IS_CHINA=true
else
    # 检查特定中国网站的可访问性
    if curl -s --connect-timeout 5 "https://www.baidu.com" > /dev/null && \
       ! curl -s --connect-timeout 5 "https://www.google.com" > /dev/null 2>&1; then
        IS_CHINA=true
    else
        IS_CHINA=false
    fi
fi

if [ "$IS_CHINA" = true ]; then
    echo "检测到中国地区网络环境，修改 Dockerfile 使用国内镜像源"
    
    # 备份原始 Dockerfile
    if [ -f "docker/dockerfile" ]; then
        cp docker/dockerfile docker/dockerfile.backup
    fi
    
    # 修改 Dockerfile 使用国内镜像
    sed -i 's|FROM python:3.11-slim|FROM docker.1ms.run/library/python:3.11-slim|' docker/dockerfile
    
    echo "Dockerfile 已修改为使用国内镜像源"
else
    echo "使用默认官方镜像源"
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
sleep 2

# 检查服务状态
if docker-compose ps | grep -q "Up"; then
    echo "QQMusic Web 安装成功！"
    echo ""
    
    # 获取本地IP地址
    
    # 使用hostname命令
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    
    # 使用ip命令
    if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" = "" ]; then
        LOCAL_IP=$(ip route get 1 2>/dev/null | awk '{print $7}' | head -1)
    fi
    
    # 如果前两种方法都失败，尝试从网络接口获取
    if [ -z "$LOCAL_IP" ] || [ "$LOCAL_IP" = "" ]; then
        LOCAL_IP=$(ip addr show 2>/dev/null | grep -oP 'inet \K[\d.]+' | grep -v '127.0.0.1' | head -1)
    fi
    
    # 如果仍然无法获取IP，使用默认值
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
    
    echo "管理命令:"
    echo "   查看日志: cd $PROJECT_DIR/docker && sudo docker-compose logs -f"
    echo "   停止服务: cd $PROJECT_DIR/docker && sudo docker-compose down"
    echo "   重启服务: cd $PROJECT_DIR/docker && sudo docker-compose restart"
    echo "   更新服务: cd $PROJECT_DIR/docker && sudo docker-compose up -d --build --force-recreate"
    
    echo ""
else
    echo "服务启动失败，请检查日志:"
    cd $PROJECT_DIR/docker && docker-compose logs
    exit 1
fi