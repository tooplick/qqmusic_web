// 全局变量
let currentSongIndex = 0;
let isPlaying = false;
let currentAudio = null;
let searchResults = [];
let allSearchResults = [];
let isFullscreen = false;
let currentSongQuality = 'flac';
let currentRequestController = null;
let isMuted = false;
let lastVolume = 0.7;
let currentPage = 1;
let hasNextPage = false;
let hasPrevPage = false;
let totalResults = 0;
let totalPages = 1;
let currentSearchQuery = '';
const pageSize = 10;
let loadingAudio = null; // 新增 - 当前加载中的audio实例

// DOM元素
const playPauseBtn = document.getElementById('play-pause-btn');
const prevBtn = document.getElementById('prev-btn');
const nextBtn = document.getElementById('next-btn');
const progressBar = document.getElementById('progress-bar');
const progress = document.getElementById('progress');
const currentTimeEl = document.getElementById('current-time');
const totalTimeEl = document.getElementById('total-time');
const volumeBar = document.getElementById('volume-bar');
const volumeLevel = document.getElementById('volume-level');
const volumeDownBtn = document.getElementById('volume-down-btn');
const volumeUpBtn = document.getElementById('volume-up-btn');
const currentTitle = document.getElementById('current-title');
const currentArtist = document.getElementById('current-artist');
const currentCover = document.getElementById('current-cover');
const resultsContainer = document.getElementById('results-container');
const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const resultsCount = document.getElementById('results-count');
const loadingSpinner = document.getElementById('loading-spinner');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const notification = document.getElementById('notification');
const flacOption = document.getElementById('flac-option');
const mp3Option = document.getElementById('mp3-option');
const fullscreenBtn = document.getElementById('fullscreen-btn');
const playerSection = document.getElementById('player-section');
const prevPageBtn = document.getElementById('prev-page-btn');
const nextPageBtn = document.getElementById('next-page-btn');
const pageInfo = document.getElementById('page-info');
const paginationControls = document.getElementById('pagination-controls');

// 智能封面获取函数
function getSmartCoverUrl(songData) {
    if (!songData) {
        return 'https://y.gtimg.cn/music/photo_new/T002R300x300M000003y8dsH2wBHlo_1.jpg';
    }
    const albumMid = songData.album_mid || songData.album?.mid;
    if (albumMid) {
        return `https://y.gtimg.cn/music/photo_new/T002R300x300M000${albumMid}.jpg`;
    }

    const vsValues = songData.vs || songData.raw_data?.vs || [];
    const candidateVs = [];

    vsValues.forEach((vs, index) => {
        if (vs && typeof vs === 'string' && vs.length >= 3 && !vs.includes(',')) {
            candidateVs.push({ value: vs, priority: 1 });
        }
    });
    vsValues.forEach((vs, index) => {
        if (vs && vs.includes(',')) {
            const parts = vs.split(',').map(part => part.trim()).filter(part => part);
            parts.forEach(part => {
                if (part.length >= 3) candidateVs.push({ value: part, priority: 2 });
            });
        }
    });
    candidateVs.sort((a, b) => a.priority - b.priority);

    for (const candidate of candidateVs) {
        return `https://y.qq.com/music/photo_new/T062R300x300M000${candidate.value}.jpg`;
    }
    return 'https://y.gtimg.cn/music/photo_new/T002R300x300M000003y8dsH2wBHlo_1.jpg';
}

// 初始化播放器
function initPlayer() {
    playPauseBtn.addEventListener('click', togglePlay);
    prevBtn.addEventListener('click', prevSong);
    nextBtn.addEventListener('click', nextSong);
    progressBar.addEventListener('click', setProgress);
    volumeBar.addEventListener('click', setVolume);
    volumeDownBtn.addEventListener('click', decreaseVolume);
    volumeUpBtn.addEventListener('click', increaseVolume);
    searchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keyup', function(e) {
        if (e.key === 'Enter') handleSearch();
    });
    fullscreenBtn.addEventListener('click', toggleFullscreen);
    prevPageBtn.addEventListener('click', goToPrevPage);
    nextPageBtn.addEventListener('click', goToNextPage);

    document.querySelectorAll('input[name="quality"]').forEach(option => {
        option.addEventListener('change', function() {
            currentSongQuality = this.value;
            if (searchResults.length > 0 && currentSongIndex < searchResults.length && currentAudio) {
                playSong(currentSongIndex);
            }
        });
    });
    checkBackendStatus();
    setVolumeInitial();
    console.log('播放器初始化完成');
}

// 消息提示
function showNotification(message, type = 'info') {
    notification.textContent = message;
    notification.className = 'notification';
    notification.classList.add(type);
    notification.classList.add('show');
    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// 检查后端连接状态
async function checkBackendStatus() {
    try {
        const response = await fetch('/api/health');
        if (response.ok) {
            const data = await response.json();
            statusDot.classList.add('connected');
            statusText.textContent = '已连接';
        } else throw new Error('后端响应异常');
    } catch (error) {
        statusText.textContent = '连接失败';
        showNotification('无法连接到服务器，请检查后端是否运行', 'error');
    }
}

// 音量初始值
function setVolumeInitial() {
    volumeLevel.style.width = '70%';
    if (currentAudio) currentAudio.volume = 0.7;
    lastVolume = 0.7;
    updateVolumeIcon();
}
function increaseVolume() {
    let volume = currentAudio ? currentAudio.volume : lastVolume;
    setVolumeValue(Math.min(1, volume + 0.1));
}
function decreaseVolume() {
    let volume = currentAudio ? currentAudio.volume : lastVolume;
    setVolumeValue(Math.max(0, volume - 0.1));
}
function setVolumeValue(volume) {
    volumeLevel.style.width = `${volume * 100}%`;
    lastVolume = volume;
    if (currentAudio) currentAudio.volume = volume;
    updateVolumeIcon();
}
function updateVolumeIcon() {
    const volume = currentAudio ? currentAudio.volume : lastVolume;
    if (volume === 0) {
        volumeDownBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
        volumeUpBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
    } else if (volume < 0.5) {
        volumeDownBtn.innerHTML = '<i class="fas fa-volume-down"></i>';
        volumeUpBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
    } else {
        volumeDownBtn.innerHTML = '<i class="fas fa-volume-down"></i>';
        volumeUpBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
    }
}

// 搜索逻辑
function handleSearch() {
    const query = searchInput.value.trim();
    currentPage = 1;
    performSearch(query, 1);
}
async function performSearch(query, page = 1) {
    if (!query) {
        showNotification('请输入搜索关键词', 'error');
        return;
    }
    currentSearchQuery = query;
    currentPage = page;
    loadingSpinner.style.display = 'flex';
    resultsContainer.innerHTML = '';
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keyword: query, page: page })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || '搜索失败');
        searchResults = data.results || [];
        if (data.pagination) {
            hasNextPage = data.pagination.has_next;
            hasPrevPage = data.pagination.has_prev;
            totalResults = data.pagination.total_results;
            totalPages = data.pagination.total_pages;
        }
        renderSearchResults();
        showNotification(searchResults.length === 0 ? '未找到相关歌曲' : `第 ${currentPage} 页，显示 ${searchResults.length} 首歌曲`, searchResults.length === 0 ? 'error' : 'success');
    } catch (error) {
        showNotification(error.message, 'error');
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle"></i>
                <p>搜索失败: ${error.message}</p>
            </div>
        `;
    } finally {
        loadingSpinner.style.display = 'none';
        updatePaginationControls();
    }
}
function updatePaginationControls() {
    if (searchResults.length === 0) {
        paginationControls.style.display = 'none';
        return;
    }
    paginationControls.style.display = 'flex';
    prevPageBtn.disabled = !hasPrevPage;
    nextPageBtn.disabled = !hasNextPage;
    pageInfo.textContent = ` ${currentPage}  /  ${totalPages} `;
    resultsCount.textContent = `找到 ${totalResults} 首`;
    resultsCount.style.paddingRight = '12px';
}
function goToPrevPage() {
    if (currentPage > 1) {
        currentPage--;
        performSearch(currentSearchQuery, currentPage);
    }
}
function goToNextPage() {
    if (currentPage < totalPages) {
        currentPage++;
        performSearch(currentSearchQuery, currentPage);
    }
}
function renderSearchResults() {
    resultsContainer.innerHTML = '';
    if (searchResults.length === 0) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-search"></i>
                <p>未找到相关歌曲</p>
            </div>
        `;
        return;
    }
    searchResults.forEach((song, index) => {
        const resultItem = document.createElement('div');
        resultItem.className = `result-item ${index === currentSongIndex ? 'active' : ''}`;
        const coverUrl = getSmartCoverUrl(song);
        const duration = formatDuration(song.interval);
        resultItem.innerHTML = `
            <img src="${coverUrl}" alt="${song.name}" onerror="this.src='https://y.gtimg.cn/music/photo_new/T002R300x300M000003y8dsH2wBHlo_1.jpg'">
            <div class="result-item-info">
                <div class="result-item-title">
                    ${song.name} ${song.vip ? '<span class="vip-badge">VIP</span>' : ''}
                </div>
                <div class="result-item-artist">${song.singers}</div>
            </div>
            <div class="result-item-duration">${duration}</div>
            <div class="result-actions">
                <button class="result-action-btn play-song-btn" data-index="${index}" title="播放">
                    <i class="fas fa-play"></i>
                </button>
                <button class="result-action-btn download-song-btn" data-index="${index}" title="下载">
                    <i class="fas fa-download"></i>
                </button>
            </div>
        `;
        resultsContainer.appendChild(resultItem);
    });
    document.querySelectorAll('.play-song-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            playSong(index);
        });
    });
    document.querySelectorAll('.download-song-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            downloadSongFromResult(index);
        });
    });
}

// 修复核心播放逻辑
async function playSong(index) {
    if (index < 0 || index >= searchResults.length) {
        showNotification('无效的歌曲索引', 'error');
        return;
    }
    // 停止所有旧audio
    // Abort前一个fetch请求
    if (currentRequestController) currentRequestController.abort();
    // 暂停所有旧audio
    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio = null;
    }
    if (loadingAudio) {
        loadingAudio.pause();
        loadingAudio.currentTime = 0;
        loadingAudio = null;
    }

    const song = searchResults[index];
    currentSongIndex = index;
    currentTitle.textContent = song.name;
    currentArtist.textContent = song.singers;
    currentCover.src = getSmartCoverUrl(song);
    updateActiveResultItem(index);

    progress.style.width = '0%';
    currentTimeEl.textContent = '0:00';
    totalTimeEl.textContent = formatDuration(song.interval);

    playPauseBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    playPauseBtn.disabled = true;
    isPlaying = false; // 等待新音频加载

    try {
        currentRequestController = new AbortController();
        const signal = currentRequestController.signal;
        const preferFlac = currentSongQuality === 'flac';
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                song_data: song,
                prefer_flac: preferFlac,
                add_metadata: true
            }),
            signal: signal
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || '下载失败');
        const playUrl = `/api/file/${encodeURIComponent(data.filename)}`;
        loadingAudio = new Audio(playUrl);

        // 事件监听
        loadingAudio.addEventListener('loadedmetadata', () => {
            totalTimeEl.textContent = formatDuration(loadingAudio.duration);
        });
        loadingAudio.addEventListener('timeupdate', updateProgress);
        loadingAudio.addEventListener('ended', nextSong);
        loadingAudio.volume = lastVolume;
        updateVolumeIcon();

        await loadingAudio.play(); // 首次播放
        isPlaying = true; // 标记正在播放
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';

        // 替换全局audio
        if (currentAudio && currentAudio !== loadingAudio) {
            currentAudio.pause();
        }
        currentAudio = loadingAudio;
        loadingAudio = null;
        showNotification(`正在播放: ${song.name}`, 'success');
    } catch (error) {
        if (error.name === 'AbortError') {
            // 加载已取消
            return;
        }
        if (error.message.includes('VIP') && !song.vip) {
            showNotification('这首歌是VIP歌曲，需要登录才能播放', 'error');
        } else {
            showNotification(`播放失败: ${error.message}`, 'error');
            if (currentSongQuality === 'flac') {
                showNotification('FLAC音质不可用，自动尝试MP3格式', 'warning');
                currentSongQuality = 'mp3';
                document.querySelector('input[name="quality"][value="mp3"]').checked = true;
                setTimeout(() => playSong(index), 500);
            }
        }
        playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
        isPlaying = false;
    } finally {
        playPauseBtn.disabled = false;
        currentRequestController = null;
        loadingAudio = null;
    }
}

// 播放/暂停切换
function togglePlay() {
    if (!currentAudio) {
        // 若没音频，尝试播放当前选中的
        if (searchResults.length > 0) {
            playSong(currentSongIndex);
        } else {
            showNotification('请先搜索并选择一首歌曲', 'error');
        }
        return;
    }
    if (isPlaying) {
        currentAudio.pause();
        playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
        isPlaying = false;
    } else {
        currentAudio.play();
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';
        isPlaying = true;
    }
}

// 下一首
function nextSong() {
    if (searchResults.length === 0) return;
    const nextIndex = (currentSongIndex + 1) % searchResults.length;
    playSong(nextIndex);
}

// 上一首
function prevSong() {
    if (searchResults.length === 0) return;
    const prevIndex = (currentSongIndex - 1 + searchResults.length) % searchResults.length;
    playSong(prevIndex);
}

// 更新进度条
function updateProgress() {
    if (!currentAudio) return;
    const progressPercent = (currentAudio.currentTime / currentAudio.duration) * 100;
    progress.style.width = `${progressPercent}%`;
    currentTimeEl.textContent = formatDuration(currentAudio.currentTime);
}

// 设置进度
function setProgress(e) {
    if (!currentAudio) return;
    const width = this.clientWidth;
    const clickX = e.offsetX;
    const duration = currentAudio.duration;
    currentAudio.currentTime = (clickX / width) * duration;
}

// 设置音量
function setVolume(e) {
    const width = this.clientWidth;
    const clickX = e.offsetX;
    const volume = clickX / width;
    setVolumeValue(volume);
}

// 下载逻辑
async function downloadSongFromResult(index) {
    if (index < 0 || index >= searchResults.length) {
        showNotification('无效的歌曲索引', 'error');
        return;
    }
    const song = searchResults[index];
    try {
        const preferFlac = currentSongQuality === 'flac';
        const downloadBtn = document.querySelector(`.download-song-btn[data-index="${index}"]`);
        if (downloadBtn) {
            downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            downloadBtn.disabled = true;
        }
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                song_data: song,
                prefer_flac: preferFlac,
                add_metadata: true
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || '下载失败');
        const downloadUrl = `/api/file/${encodeURIComponent(data.filename)}`;
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showNotification(`已开始下载: ${song.name}`, 'success');
    } catch (error) {
        if (error.message.includes('VIP')) {
            showNotification('这首歌是VIP歌曲，需要登录才能下载', 'error');
        } else {
            showNotification(`下载失败: ${error.message}`, 'error');
            if (currentSongQuality === 'flac') {
                showNotification('FLAC音质不可用，尝试MP3音质', 'warning');
                currentSongQuality = 'mp3';
                document.querySelector('input[name="quality"][value="mp3"]').checked = true;
                setTimeout(() => downloadSongFromResult(index), 500);
            }
        }
    } finally {
        const downloadBtn = document.querySelector(`.download-song-btn[data-index="${index}"]`);
        if (downloadBtn) {
            downloadBtn.innerHTML = '<i class="fas fa-download"></i>';
            downloadBtn.disabled = false;
        }
    }
}

// 全屏
function toggleFullscreen() {
    if (!isFullscreen) {
        playerSection.classList.add('fullscreen');
        fullscreenBtn.innerHTML = '<i class="fas fa-compress"></i>';
        isFullscreen = true;
    } else {
        playerSection.classList.remove('fullscreen');
        fullscreenBtn.innerHTML = '<i class="fas fa-expand"></i>';
        isFullscreen = false;
    }
}

// 高亮当前项
function updateActiveResultItem(index) {
    const resultItems = document.querySelectorAll('.result-item');
    resultItems.forEach((item, i) => {
        if (i === index) item.classList.add('active');
        else item.classList.remove('active');
    });
}

// 格式化时长
function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

// 入口
document.addEventListener('DOMContentLoaded', initPlayer);