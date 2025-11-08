document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const resultsDiv = document.getElementById('results');
    const qualityOptions = document.querySelectorAll('.quality-option');
    const resultsCount = document.getElementById('results-count');
    const btnText = document.querySelector('.btn-text');
    const btnLoading = document.querySelector('.btn-loading');
    const resultsTitle = document.getElementById('results-title');
    const resultsStatus = document.getElementById('results-status');

    // State variables
    let preferFlac = true;
    let currentResults = [];

    // Event Listeners
    qualityOptions.forEach(option => {
        option.addEventListener('click', handleQualityChange);
    });

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // Functions
    function handleQualityChange() {
        qualityOptions.forEach(opt => opt.classList.remove('selected'));
        this.classList.add('selected');

        if (this.dataset.quality === 'high') {
            preferFlac = true;
        } else {
            preferFlac = false;
        }
    }

    function performSearch() {
        const keyword = searchInput.value.trim();

        if (!keyword) {
            showMessage('请输入要搜索的歌曲名', 'error');
            searchInput.focus();
            return;
        }

        showMessage('正在搜索歌曲，请稍候...', 'loading');
        setSearchButtonState(true);

        fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ keyword: keyword })
        })
        .then(response => response.json())
        .then(data => {
            setSearchButtonState(false);

            if (data.error) {
                showMessage(data.error, 'error');
                return;
            }

            currentResults = data.results;
            displayResults(data.results);
            showMessage(`找到 ${data.results.length} 首相关歌曲`, 'success');
        })
        .catch(error => {
            setSearchButtonState(false);
            console.error('搜索失败:', error);
            showMessage('搜索失败，请检查网络连接后重试', 'error');
        });
    }

    function setSearchButtonState(loading) {
        if (loading) {
            searchBtn.disabled = true;
            btnText.style.display = 'none';
            btnLoading.style.display = 'flex';
        } else {
            searchBtn.disabled = false;
            btnText.style.display = 'flex';
            btnLoading.style.display = 'none';
        }
    }

    function displayResults(results) {
        resultsDiv.innerHTML = '';
        resultsCount.textContent = '';
        clearMessage(); // 清除状态信息

        if (results.length === 0) {
            resultsDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">😕</div>
                    <div class="empty-title">未找到相关歌曲</div>
                    <div class="empty-desc">尝试使用其他关键词搜索</div>
                </div>
            `;
            return;
        }

        resultsCount.textContent = `${results.length} 首歌曲`;

        results.forEach((song, index) => {
            const resultItem = document.createElement('div');
            resultItem.className = 'result-item';

            // 格式化时长
            const minutes = Math.floor(song.interval / 60);
            const seconds = song.interval % 60;
            const duration = `${minutes}:${seconds.toString().padStart(2, '0')}`;

            resultItem.innerHTML = `
                <div class="song-info">
                    <div class="song-name">
                        ${song.name}
                        ${song.vip ? '<span class="vip-badge">VIP</span>' : ''}
                    </div>
                    <div class="song-singer">${song.singers}</div>
                    <div class="song-album">${song.album || '未知专辑'} • ${duration}</div>
                </div>
                <button class="download-btn" data-mid="${song.mid}">
                    <span class="btn-icon"></span>
                    <span class="btn-text">下载</span>
                </button>
            `;

            resultsDiv.appendChild(resultItem);
        });

        // 添加下载事件监听
        document.querySelectorAll('.download-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const mid = this.dataset.mid;
                downloadSong(mid, this);
            });
        });
    }

    function downloadSong(mid, button) {
        // 从currentResults中查找完整的歌曲数据
        const song = currentResults.find(item => item.mid === mid);
        if (!song) {
            showMessage('未找到歌曲数据', 'error');
            return;
        }

        const buttonText = button.querySelector('.btn-text');
        const originalText = buttonText.textContent;

        button.disabled = true;
        buttonText.textContent = '下载中...';
        showMessage(`正在下载: ${song.name}`, 'loading');

        fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                song_data: song,
                prefer_flac: preferFlac
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showMessage(data.error, 'error');
                button.disabled = false;
                buttonText.textContent = originalText;
                return;
            }

            showMessage(`成功下载: ${data.filename} (${data.quality})`, 'success');

            // 创建临时下载链接并自动触发下载
            const tempLink = document.createElement('a');
            tempLink.href = `/api/file/${data.filename}`;
            tempLink.download = data.filename;
            tempLink.style.display = 'none';
            document.body.appendChild(tempLink);
            tempLink.click();
            document.body.removeChild(tempLink);

            button.disabled = false;
            buttonText.textContent = originalText;
        })
        .catch(error => {
            console.error('下载失败:', error);
            showMessage('下载失败，请稍后重试', 'error');
            button.disabled = false;
            buttonText.textContent = originalText;
        });
    }

    function showMessage(message, type) {
        resultsStatus.textContent = message;
        resultsStatus.className = 'results-status ' + type;

        // 自动清除成功和加载消息
        if (type === 'success' || type === 'loading') {
            setTimeout(() => {
                clearMessage();
            }, type === 'success' ? 5000 : 10000);
        }
    }

    function clearMessage() {
        resultsStatus.textContent = '';
        resultsStatus.className = 'results-status';
    }
});