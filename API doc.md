# API接口文档

## 搜索接口
- **端点**: `POST /api/search`
- **参数**: 
  ```json
  {
    "keyword": "歌曲名",
    "page": 1
  }
  ```
- **返回**:
  ```json
  {
    "results": [
      {
        "mid": "歌曲MID",
        "name": "歌曲名",
        "singers": "歌手",
        "vip": false,
        "album": "专辑名",
        "album_mid": "专辑MID",
        "interval": 240,
        "raw_data": {}
      }
    ],
    "pagination": {
      "current_page": 1,
      "has_prev": false,
      "has_next": true,
      "total_pages": 6,
      "total_results": 60
    },
    "all_results": 60
  }
  ```

## 播放接口 (流式播放)
- **端点**: `POST /api/play_url`
- **参数**: 
  ```json
  {
    "song_data": {
      "mid": "歌曲MID",
      "name": "歌曲名",
      "singers": "歌手",
      "vip": false,
      "album": "专辑名"
    },
    "prefer_flac": true
  }
  ```
- **返回**:
  ```json
  {
    "url": "https://stream.url/audio.mp3",
    "quality": "FLAC",
    "song_mid": "歌曲MID"
  }
  ```

## 下载接口
- **端点**: `POST /api/download`
- **参数**: 
  ```json
  {
    "song_data": {
      "mid": "歌曲MID",
      "name": "歌曲名",
      "singers": "歌手",
      "vip": false,
      "album": "专辑名",
      "raw_data": {}
    },
    "prefer_flac": true,
    "add_metadata": true
  }
  ```
- **返回**:
  ```json
  {
    "filename": "歌曲名 - 歌手.flac",
    "quality": "FLAC",
    "filepath": "/music/歌曲名 - 歌手.flac",
    "cached": false,
    "metadata_added": true
  }
  ```

## 文件接口
- **端点**: `GET /api/file/<filename>`
- **功能**: 提供文件下载
- **返回**: 文件流

## 状态接口
- **端点**: `GET /api/credential/status`
- **功能**: 获取凭证状态
- **返回**:
  ```json
  {
    "enabled": true,
    "last_check": "2025-11-15T21:44:48",
    "status": "使用本地凭证登录成功!",
    "expired": false
  }
  ```

- **端点**: `GET /api/cleanup/status`
- **功能**: 获取清理任务状态
- **返回**:
  ```json
  {
    "success": true,
    "message": "音乐文件夹已经是空的",
    "deleted_count": 0
  }
  ```

- **端点**: `GET /api/health`
- **功能**: 检查后端服务的健康状态和关键目录信息
- **返回**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2025-11-15T21:44:48.123456",
    "music_dir_exists": true,
    "music_files_count": 15,
    "environment": "native"
  }
  ```