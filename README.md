# QQ Music 网页播放器

一个基于Flask和QQ音乐API的在线音乐下载工具，支持搜索、播放、下载和音质选择功能。

## 功能特性

###  核心功能
- **在线播放**：搜索播放歌曲
- **多音质下载**: 支持标准音质(MP3)和高品质音质(FLAC)

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

5。 **配置文件夹**
 - `/root/qqmusic_web/credential` #凭证文件夹
 - `/root/qqmusic_web/music` #下载音乐本地目录

### 示例网站：[qq.ygking.top](https://qq.ygking.top/)

## API接口

### 搜索接口
- **端点**: `POST /api/search`
- **参数**: `{ "keyword": "歌曲名" }`
- **返回**: 搜索结果列表

### 播放接口 (流式播放)

- **端点**: `POST /api/play_url`
- **参数**: `{ "song_data": {...}, "prefer_flac": true }` 
- **返回**: 歌曲的直接媒体 URL 及音质信息。

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

- **端点**: `GET /api/health`
- **功能**: 检查后端服务的健康状态和关键目录信息。

## 更新日志

### v2.1.1
- 播放改为流式传输
- 添加显示歌词
- 修复播放Bug
### v2.1.0
- 重构整个前端
- 支持在线播放搜索下载
- docker挂载配置文件夹

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

## 免责声明
- 本代码遵循 [GPL-3.0 License](https://github.com/tooplick/qqmusic_web/blob/main/LICENSE) 协议
   - 允许**开源/免费使用和引用/修改/衍生代码的开源/免费使用**
   - 不允许**修改和衍生的代码作为闭源的商业软件发布和销售**
   - 禁止**使用本代码盈利**
- 以此代码为基础的程序**必须**同样遵守 [GPL-3.0 License](https://github.com/tooplick/qqmusic_web/blob/main/LICENSE) 协议
- 本代码仅用于**学习讨论**，禁止**用于盈利**,下载的音乐请于**24小时内删除**,支持**正版音乐**
- 他人或组织使用本代码进行的任何**违法行为**与本人无关