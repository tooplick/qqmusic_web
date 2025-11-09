# QQ音乐下载

一个基于Flask和QQ音乐API的在线音乐下载工具，支持搜索、下载和音质选择功能。

## 功能特性

###  核心功能
- **音乐搜索**: 支持按歌曲名、歌手、专辑搜索
- **多音质下载**: 支持标准音质(MP3)和高品质音质(FLAC)
- **自动清理**: 定期清理下载文件，节省存储空间

###  凭证管理
- **自动刷新**: 支持凭证自动刷新功能
- **状态监控**: 实时监控凭证状态


## 项目结构

```
qqmusic_web/
├── app.py                 # Flask主应用
├── requirements.txt       # Python依赖项
├── qqmusic_cred.pkl       # QQ音乐凭证文件
├── music/                 # 音乐文件存储目录
├── static/
│   ├── css/
│   │   └── style.css      # 样式文件
│   ├── js/
│   │   └── script.js      # 前端交互
│   └── images/            # 图片资源
└── templates/
    └── index.html         # 主页
```

## 安装部署

### 环境要求
- Python 3.7+
- pip 包管理工具

### 安装步骤

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
   打开浏览器访问 `http://localhost:5000`

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

# 音乐文件存储目录
MUSIC_DIR = Path("./music")
```

### 凭证文件
- 文件路径: `qqmusic_cred.pkl`
- 格式: pickle序列化文件
- 包含QQ音乐登录凭证信息

## 注意事项

### 法律声明
- 本工具仅供学习和研究使用
- 请尊重音乐版权，下载后请在24小时内删除
- 不得用于商业用途

### 使用限制
- VIP歌曲下载需要有效凭证
- 音质可用性受歌曲版权限制
- 下载速度受网络环境影响

## 警告
- 这是一个开发服务器。请勿将其用于生产环境部署。请改用生产环境的 WSGI 服务器。

## 更新日志
### v1.0.1
- 为FLAC格式自动添加封面歌词
### v1.0.0
- 基础搜索和下载功能
- 多音质支持
- 凭证管理功能
- 自动清理机制

## 作者信息

- **作者**:GeQian
- **GitHub**：[https://github.com/tooplick](https://github.com/tooplick)

## 许可证

本项目仅用于学习和研究目的，请遵守相关法律法规。

---

**温馨提示**: 享受音乐的同时，请支持正版音乐！