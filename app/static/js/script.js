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
let lastVolume = 1.0;
let currentPage = 1;
let hasNextPage = false;
let hasPrevPage = false;
let totalResults = 0;
let totalPages = 1;
let currentSearchQuery = '';
const pageSize = 10;
let loadingAudio = null; // 当前加载中的audio实例

// 歌词相关变量
let currentLyrics = [];
let currentLyricIndex = -1;
let lyricsInterval = null;

// 新增：播放队列控制
let pendingPlayRequests = new Map(); // 存储待处理的播放请求
let currentPlayToken = null; // 当前播放令牌

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

// 歌词相关DOM元素
const albumCover = document.getElementById('album-cover');
const lyricsDisplay = document.getElementById('lyrics-display');
const lyricsContent = document.getElementById('lyrics-content');
const closeLyricsBtn = document.getElementById('close-lyrics');

// 生成唯一令牌
function generatePlayToken() {
    return Date.now() + '-' + Math.random().toString(36).substr(2, 9);
}

// 清理所有待处理的播放请求
function cleanupPendingRequests() {
    for (let [token, controller] of pendingPlayRequests) {
        if (controller) {
            controller.abort();
        }
    }
    pendingPlayRequests.clear();
}

// 歌词切换函数
function toggleLyrics() {
    console.log('toggleLyrics called');

    if (lyricsDisplay.style.display === 'none' || !lyricsDisplay.style.display) {
        // 显示歌词，隐藏整个封面区域
        lyricsDisplay.style.display = 'flex';
        albumCover.style.display = 'none';

        // 如果正在播放，确保歌词滚动到正确位置
        if (isPlaying && currentAudio) {
            updateLyricsDisplay(currentAudio.currentTime);
        }
    } else {
        // 显示封面，隐藏歌词
        lyricsDisplay.style.display = 'none';
        albumCover.style.display = 'block';
    }
}

// 智能封面获取函数
function getSmartCoverUrl(songData) {
    if (!songData) {
        return 'https://y.gtimg.cn/music/photo_new/T002R800x800M000003y8dsH2wBHlo_1.jpg';
    }
    const albumMid = songData.album_mid || songData.album?.mid;
    if (albumMid) {
        return `https://y.gtimg.cn/music/photo_new/T002R800x800M000${albumMid}.jpg`;
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
        return `https://y.qq.com/music/photo_new/T062R800x800M000${candidate.value}.jpg`;
    }
    return 'https://y.gtimg.cn/music/photo_new/T002R800x800M000003y8dsH2wBHlo_1.jpg';
}

// 初始化播放器
function initPlayer() {
    console.log('初始化播放器');

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

    // 添加封面点击事件（切换歌词显示）
    if (albumCover) {
        albumCover.addEventListener('click', toggleLyrics);
        console.log('已添加封面点击事件监听器');
    } else {
        console.error('未找到专辑封面元素');
    }

    // 添加歌词显示区域点击事件
    if (lyricsDisplay) {
        lyricsDisplay.addEventListener('click', toggleLyrics);
        console.log('已添加歌词显示区域点击事件');
    }

    // 添加关闭按钮点击事件
    if (closeLyricsBtn) {
        closeLyricsBtn.addEventListener('click', function(e) {
            e.stopPropagation(); // 阻止事件冒泡
            toggleLyrics();
        });
        console.log('已添加关闭按钮点击事件');
    }

    checkBackendStatus();
    setVolumeInitial();
    console.log('播放器初始化完成');
}

// 获取歌词的函数
async function fetchLyrics(songMid) {
    try {
        console.log('获取歌词，歌曲MID:', songMid);
        const response = await fetch(`/api/lyric/${songMid}`);
        if (!response.ok) throw new Error('获取歌词失败');
        const data = await response.json();
        console.log('歌词数据:', data);
        return data;
    } catch (error) {
        console.error('获取歌词失败:', error);
        return null;
    }
}

// 解析LRC歌词的函数
function parseLrc(lrcText) {
    if (!lrcText) return [];

    const lines = lrcText.split('\n');
    const lyrics = [];

    const timePattern = /\[(\d+):(\d+)\.(\d+)\]/g;

    lines.forEach(line => {
        const matches = [...line.matchAll(timePattern)];
        const text = line.replace(timePattern, '').trim();

        if (matches.length > 0 && text) {
            matches.forEach(match => {
                const minutes = parseInt(match[1]);
                const seconds = parseInt(match[2]);
                const milliseconds = parseInt(match[3]);
                const time = minutes * 60 + seconds + milliseconds / 100;

                lyrics.push({
                    time: time,
                    text: text
                });
            });
        }
    });

    // 按时间排序
    lyrics.sort((a, b) => a.time - b.time);
    return lyrics;
}

// 显示歌词的函数
function displayLyrics(lyricsData) {
    currentLyrics = [];

    if (!lyricsData || (!lyricsData.lyric && !lyricsData.trans)) {
        lyricsContent.innerHTML = `
            <div class="empty-lyrics">
                <i class="fas fa-music"></i>
                <p>暂无歌词</p>
            </div>
        `;
        return;
    }

    let lyricsHTML = '';

    // 解析主歌词
    if (lyricsData.lyric) {
        const mainLyrics = parseLrc(lyricsData.lyric);
        currentLyrics = mainLyrics;

        if (mainLyrics.length > 0) {
            mainLyrics.forEach((lyric, index) => {
                lyricsHTML += `<div class="lyrics-line" data-index="${index}">${lyric.text}</div>`;
            });
        } else {
            // 如果不是LRC格式，直接显示文本
            lyricsHTML += `<div class="lyrics-line">${lyricsData.lyric}</div>`;
        }
    }

    // 解析翻译歌词（如果有）
    if (lyricsData.trans && currentLyrics.length > 0) {
        const transLyrics = parseLrc(lyricsData.trans);
        transLyrics.forEach(transLyric => {
            // 找到对应时间的主歌词，添加翻译
            const mainIndex = currentLyrics.findIndex(l => Math.abs(l.time - transLyric.time) < 0.1);
            if (mainIndex !== -1) {
                const lineElement = lyricsContent.querySelector(`[data-index="${mainIndex}"]`);
                if (lineElement) {
                    lineElement.innerHTML += `<br><small style="opacity:0.7">${transLyric.text}</small>`;
                }
            }
        });
    }

    lyricsContent.innerHTML = lyricsHTML || `
        <div class="empty-lyrics">
            <i class="fas fa-music"></i>
            <p>暂无歌词</p>
        </div>
    `;
}

// 更新歌词显示的函数
function updateLyricsDisplay(currentTime) {
    if (currentLyrics.length === 0) return;

    // 找到当前应该显示的歌词
    let newIndex = -1;
    for (let i = currentLyrics.length - 1; i >= 0; i--) {
        if (currentTime >= currentLyrics[i].time) {
            newIndex = i;
            break;
        }
    }

    if (newIndex !== currentLyricIndex) {
        // 移除之前的高亮
        const oldActive = document.querySelector('.lyrics-line.active');
        if (oldActive) {
            oldActive.classList.remove('active');
        }

        // 添加新的高亮
        if (newIndex !== -1) {
            const newActive = document.querySelector(`.lyrics-line[data-index="${newIndex}"]`);
            if (newActive) {
                newActive.classList.add('active');

                // 滚动到当前歌词位置
                const containerHeight = lyricsContent.clientHeight;
                const lineHeight = newActive.offsetHeight;
                const scrollTop = newActive.offsetTop - containerHeight / 2 + lineHeight / 2;

                lyricsContent.scrollTo({
                    top: scrollTop,
                    behavior: 'smooth'
                });
            }
        }

        currentLyricIndex = newIndex;
    }
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
    volumeLevel.style.width = '100%';
    if (currentAudio) currentAudio.volume = 1.0;
    lastVolume = 1.0;
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
            <img src="${coverUrl}" alt="${song.name}" onerror="this.src='https://y.gtimg.cn/music/photo_new/T002R800x800M000003y8dsH2wBHlo_1.jpg'">
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

// 严格的音频清理函数
function cleanupAudio() {
    if (currentRequestController) {
        currentRequestController.abort();
        currentRequestController = null;
    }

    // 清理所有待处理的播放请求
    cleanupPendingRequests();

    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        // 移除所有事件监听器
        currentAudio.onloadedmetadata = null;
        currentAudio.ontimeupdate = null;
        currentAudio.onended = null;
        currentAudio.onplay = null;
        currentAudio.onpause = null;
        currentAudio.onerror = null;
        // 断开音频源
        currentAudio.src = '';
        currentAudio.load();
        currentAudio = null;
    }

    if (loadingAudio) {
        loadingAudio.pause();
        loadingAudio.currentTime = 0;
        loadingAudio.onloadedmetadata = null;
        loadingAudio.ontimeupdate = null;
        loadingAudio.onended = null;
        loadingAudio.onplay = null;
        loadingAudio.onpause = null;
        loadingAudio.onerror = null;
        loadingAudio.src = '';
        loadingAudio.load();
        loadingAudio = null;
    }

    // 清除歌词更新间隔
    if (lyricsInterval) {
        clearInterval(lyricsInterval);
        lyricsInterval = null;
    }
}

// 修复核心播放逻辑 - 只播放最后一曲
async function playSong(index) {
    if (index < 0 || index >= searchResults.length) {
        showNotification('无效的歌曲索引', 'error');
        return;
    }

    // 生成新的播放令牌
    const playToken = generatePlayToken();
    currentPlayToken = playToken;

    // 立即清理之前的播放请求和音频
    cleanupAudio();

    const song = searchResults[index];
    currentSongIndex = index;
    currentTitle.textContent = song.name;
    currentArtist.textContent = song.singers;
    currentCover.src = getSmartCoverUrl(song);
    updateActiveResultItem(index);

    // 重置歌词
    currentLyrics = [];
    currentLyricIndex = -1;
    lyricsContent.innerHTML = `
        <div class="empty-lyrics">
            <i class="fas fa-spinner fa-spin"></i>
            <p>加载歌词中...</p>
        </div>
    `;

    // 获取歌词
    if (song.mid) {
        try {
            const lyricsData = await fetchLyrics(song.mid);
            // 检查是否还是当前播放请求
            if (currentPlayToken !== playToken) return;
            displayLyrics(lyricsData);
        } catch (error) {
            console.error('歌词加载失败:', error);
            // 检查是否还是当前播放请求
            if (currentPlayToken !== playToken) return;
            lyricsContent.innerHTML = `
                <div class="empty-lyrics">
                    <i class="fas fa-music"></i>
                    <p>暂无歌词</p>
                </div>
            `;
        }
    } else {
        // 检查是否还是当前播放请求
        if (currentPlayToken !== playToken) return;
        lyricsContent.innerHTML = `
            <div class="empty-lyrics">
                <i class="fas fa-music"></i>
                <p>暂无歌词</p>
            </div>
        `;
    }

    progress.style.width = '0%';
    currentTimeEl.textContent = '0:00';
    totalTimeEl.textContent = formatDuration(song.interval);

    playPauseBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    playPauseBtn.disabled = true;
    isPlaying = false;

    try {
        currentRequestController = new AbortController();
        const signal = currentRequestController.signal;
        const preferFlac = currentSongQuality === 'flac';

        // 将当前控制器存入待处理列表
        pendingPlayRequests.set(playToken, currentRequestController);

        // 1. 调用 /api/play_url 端点
        const response = await fetch('/api/play_url', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                song_data: song,
                prefer_flac: preferFlac
            }),
            signal: signal
        });

        // 检查是否还是当前播放请求
        if (currentPlayToken !== playToken) {
            console.log('播放请求已被取消，跳过播放');
            return;
        }

        const data = await response.json();
        if (!response.ok) throw new Error(data.error || '获取播放URL失败');

        // 检查是否被取消
        if (signal.aborted) {
            return;
        }

        const playUrl = data.url;

        // 创建新的音频实例
        const newAudio = new Audio();

        // 设置事件处理器
        const handleLoadedMetadata = () => {
            // 检查是否还是当前播放请求
            if (currentPlayToken !== playToken) {
                newAudio.pause();
                return;
            }
            totalTimeEl.textContent = formatDuration(newAudio.duration);
        };

        const handleTimeUpdate = () => {
            // 检查是否还是当前播放请求
            if (currentPlayToken !== playToken) {
                newAudio.pause();
                return;
            }
            updateProgress();
            if (lyricsDisplay.style.display !== 'none') {
                updateLyricsDisplay(newAudio.currentTime);
            }
        };

        const handleEnded = () => {
            // 检查是否还是当前播放请求
            if (currentPlayToken !== playToken) return;
            nextSong();
        };

        const handlePlay = () => {
            // 检查是否还是当前播放请求
            if (currentPlayToken !== playToken) {
                newAudio.pause();
                return;
            }
            if (lyricsInterval) clearInterval(lyricsInterval);
            lyricsInterval = setInterval(() => {
                if (lyricsDisplay.style.display !== 'none') {
                    updateLyricsDisplay(newAudio.currentTime);
                }
            }, 100);
        };

        const handlePause = () => {
            if (lyricsInterval) {
                clearInterval(lyricsInterval);
                lyricsInterval = null;
            }
        };

        // 绑定事件
        newAudio.addEventListener('loadedmetadata', handleLoadedMetadata);
        newAudio.addEventListener('timeupdate', handleTimeUpdate);
        newAudio.addEventListener('ended', handleEnded);
        newAudio.addEventListener('play', handlePlay);
        newAudio.addEventListener('pause', handlePause);

        newAudio.volume = lastVolume;
        updateVolumeIcon();

        // 设置音频源并播放
        newAudio.src = playUrl;
        loadingAudio = newAudio;

        await newAudio.play();

        // 再次检查是否被取消
        if (signal.aborted || currentPlayToken !== playToken) {
            newAudio.pause();
            return;
        }

        isPlaying = true;
        playPauseBtn.innerHTML = '<i class="fas fa-pause"></i>';

        // 成功播放，更新当前音频引用
        currentAudio = newAudio;
        loadingAudio = null;

        // 从待处理列表中移除当前令牌
        pendingPlayRequests.delete(playToken);

        showNotification(`正在播放: ${song.name} (${data.quality})`, 'success');

    } catch (error) {
        // 从待处理列表中移除当前令牌
        pendingPlayRequests.delete(playToken);

        if (error.name === 'AbortError') {
            return;
        }

        console.error('播放错误:', error);

        // 检查是否还是当前播放请求
        if (currentPlayToken !== playToken) return;

        showNotification(`播放失败: ${error.message}`, 'error');

        if (error.message.includes('VIP')) {
            showNotification('这首歌是VIP歌曲，需要登录才能播放', 'error');
        } else if (currentSongQuality === 'flac' && !error.message.includes('VIP')) {
            showNotification('FLAC音质不可用，自动尝试MP3格式', 'warning');
            currentSongQuality = 'mp3';
            document.querySelector('input[name="quality"][value="mp3"]').checked = true;
            setTimeout(() => playSong(index), 500);
        }

        playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
        isPlaying = false;
    } finally {
        // 检查是否还是当前播放请求
        if (currentPlayToken === playToken) {
            playPauseBtn.disabled = false;
            currentRequestController = null;
        }
        // 确保清理loadingAudio（如果未被采用）
        if (loadingAudio && loadingAudio !== currentAudio) {
            loadingAudio.pause();
            loadingAudio = null;
        }
    }
}

// 播放/暂停切换
function togglePlay() {
    if (!currentAudio) {
        if (searchResults.length > 0) {
            playSong(currentSongIndex);
        } else {
            showNotification('请先搜索并选择一首歌曲', 'error');
        }
        return;
    }

    // 检查音频是否有效
    if (currentAudio.readyState === 0) {
        showNotification('音频仍在加载中，请稍候', 'warning');
        return;
    }

    if (isPlaying) {
        currentAudio.pause();
        playPauseBtn.innerHTML = '<i class="fas fa-play"></i>';
        isPlaying = false;
    } else {
        currentAudio.play().catch(error => {
            console.error('播放失败:', error);
            showNotification('播放失败，请重试', 'error');
        });
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