# QQ音乐下载

一个基于Flask和QQ音乐API的在线音乐下载工具，支持搜索、下载和音质选择功能。

## 功能特性

###  核心功能
- **音乐搜索**: 支持按歌曲名、歌手、专辑搜索
- **多音质下载**: 支持标准音质(MP3)和高品质音质(FLAC)
- **自动清理**: 自动清理下载文件，节省存储空间

###  凭证管理
- **自动刷新**: 支持凭证自动刷新功能
- **状态监控**: 实时监控凭证状态

## 项目结构

```
qqmusic_web/
├── app.py                       # Flask Web服务器
├── requirements.txt             # Python 依赖项
├── poetry.lock                  
├── pyproject.toml               
├── qqmusic_cred.pkl             # 凭证文件
├── music/                       # 音乐文件存储目录
├── static/             
│   ├── css/
│   │    └── style.css           # 样式文件
│   ├── js/
│   │    └── script.js           # 前端交互脚本
│   └── images/ 
├── templates/         
│   └── index.html               # 主页
└── docker/             
    ├── dockerfile               # Docker 镜像构建文件
    ├── docker-compose.yml       # 容器编排配置
    ├── giteeinstall.sh 
    └── install.sh               # 安装脚本
```

## 安装部署

### Docker 一键部署(推荐)
```
#（Github）
sudo -E bash -c "$(curl -fsSL https://raw.githubusercontent.com/tooplick/qqmusic_web/refs/heads/main/docker/install.sh)"
```
**如果从 Github 下载脚本遇到网络问题，可以使用Gitee仓库**
```
#（Gitee）
sudo -E bash -c "$(curl -fsSL https://gitee.com/tooplick/qqmusic_web/raw/main/docker/giteeinstall.sh)"
```
**Gitee仓库版本更新可能不及时，请谅解！**
### Python 3.11+

1. **克隆项目**
   ```bash
   git clone https://github.com/tooplick/qqmusic_web
   cd qqmusic_web
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **启动应用**
   ```bash
   python app.py
   ```

4. **访问应用**
   打开浏览器访问 `http://localhost:6022`

### 示例网站：[qq.ygking.top](https://qq.ygking.top/)

## API接口

### 搜索接口
- **端点**: `POST /api/search`
- **参数**: `{ "keyword": "歌曲名" }`
- **返回**: 搜索结果列表

### 下载接口
- **端点**: `POST /api/download`
- **参数**: `{ "song_data": {...}, "prefer_flac": true }`
- **返回**: 下载文件信息

### 文件接口
- **端点**: `GET /api/file/<filename>`
- **功能**: 提供文件下载

### 状态接口
- **端点**: `GET /api/credential/status`
- **功能**: 获取凭证状态

- **端点**: `GET /api/cleanup/status`
- **功能**: 获取清理任务状态

## 配置说明

### 主要配置项
```python
# 清理间隔(秒)
CLEANUP_INTERVAL = 10

# 凭证检查间隔(秒)
CREDENTIAL_CHECK_INTERVAL = 10

# 最大文件名长度
MAX_FILENAME_LENGTH = 100

#封面尺寸[150, 300, 500, 800]
cover_size = 800

# 音乐文件存储目录
MUSIC_DIR = Path("./music")
```

## 注意事项

### 法律声明
- 本工具仅供学习和研究使用
- 请尊重音乐版权，下载后请在24小时内删除
- 不得用于商业用途

## 更新日志
### v2.0.3
- 解决获取封面问题

### v2.0.2
- 优化线程处理

### v2.0.1
- 优化docker网络问题

### v2.0.0
- Docker构建支持

### v1.0.1
- 自动添加封面歌词

### v1.0.0
- 基础搜索和下载功能
- 多音质支持
- 自动清理机制

## 作者信息

- **作者**:GeQian
- **GitHub**：[https://github.com/tooplick](https://github.com/tooplick)

## 许可证

本项目仅用于学习和研究目的，请遵守相关法律法规。

---

**温馨提示**: 享受音乐的同时，请支持正版音乐！