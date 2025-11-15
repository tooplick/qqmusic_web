// 管理员页面 JavaScript
const BASE_URL = window.location.origin;

console.log('BASE_URL:', BASE_URL);

// DOM 元素缓存
const qqLoginBtn      = document.getElementById('qqLoginBtn');
const wxLoginBtn      = document.getElementById('wxLoginBtn');
const qrcodeContainer = document.getElementById('qrcodeContainer');
const qrcodeImage     = document.getElementById('qrcodeImage');
const qrcodePlaceholder = document.getElementById('qrcodePlaceholder');
const qrcodeStatus    = document.getElementById('qrcodeStatus');
const checkStatusBtn  = document.getElementById('checkStatusBtn');
const statusResult    = document.getElementById('statusResult');
const refreshBtn      = document.getElementById('refreshBtn');
const refreshResult   = document.getElementById('refreshResult');
const infoBtn         = document.getElementById('infoBtn');
const infoResult      = document.getElementById('infoResult');
const clearMusicBtn   = document.getElementById('clearMusicBtn');
const clearMusicResult = document.getElementById('clearMusicResult');

// 事件绑定
qqLoginBtn.addEventListener('click', () => generateQRCode('qq'));
wxLoginBtn.addEventListener('click', () => generateQRCode('wx'));
checkStatusBtn.addEventListener('click', checkCredentialStatus);
refreshBtn.addEventListener('click', refreshCredential);
infoBtn.addEventListener('click', getCredentialInfo);
clearMusicBtn.addEventListener('click', clearMusicFolder);

// 当前活跃的会话ID
let currentSessionId = null;

// 生成二维码
async function generateQRCode(type) {
    try {
        showLoading(qrcodeStatus);
        qrcodeContainer.classList.add('active');
        
        // 隐藏占位符，显示加载状态
        qrcodePlaceholder.innerHTML = '<div class="loading-spinner"></div>生成二维码中...';
        qrcodeImage.style.display = 'none';
        qrcodePlaceholder.style.display = 'flex';
        qrcodePlaceholder.style.flexDirection = 'column';

        const url = `${BASE_URL}/admin/api/get_qrcode/${type}`;
        console.log('请求二维码URL:', url);

        const response = await fetch(url);
        console.log('响应状态:', response.status, response.statusText);
        
        if (!response.ok) {
            // 尝试获取错误详情
            let errorDetail = '';
            try {
                const errorData = await response.json();
                errorDetail = errorData.error || '';
            } catch (e) {
                // 忽略 JSON 解析错误
            }
            
            throw new Error(`HTTP error! status: ${response.status}${errorDetail ? ` - ${errorDetail}` : ''}`);
        }

        const data = await response.json();
        console.log('收到二维码响应:', data);
        
        const qrBase64 = data.qrcode;
        currentSessionId = data.session_id;
        
        console.log('二维码数据长度:', qrBase64.length);
        
        // 设置二维码图片
        qrcodeImage.onload = () => {
            // 图片加载成功后隐藏占位符，显示二维码
            qrcodePlaceholder.style.display = 'none';
            qrcodeImage.style.display = 'block';
            qrcodeStatus.textContent = '二维码已生成，请使用手机扫描';
            qrcodeStatus.className = 'qrcode-status';
        };
        
        qrcodeImage.onerror = () => {
            // 图片加载失败时显示错误占位符
            qrcodePlaceholder.innerHTML = '<i class="fas fa-exclamation-triangle"></i><p>二维码加载失败</p>';
            qrcodePlaceholder.style.display = 'flex';
            qrcodeImage.style.display = 'none';
            qrcodeStatus.textContent = '二维码加载失败，请重试';
            qrcodeStatus.className = 'qrcode-status error';
        };
        
        qrcodeImage.src = `data:image/png;base64,${qrBase64}`;
        qrcodeStatus.textContent = '请使用手机扫描二维码登录';
        qrcodeStatus.className = 'qrcode-status';

        // 开始轮询检查登录状态
        const checkInterval = setInterval(async () => {
            try {
                if (!currentSessionId) {
                    clearInterval(checkInterval);
                    return;
                }
                
                const statusResponse = await fetch(`${BASE_URL}/admin/api/qr_status/${currentSessionId}`);
                if (statusResponse.ok) {
                    const statusData = await statusResponse.json();
                    console.log('轮询二维码状态:', statusData);
                    
                    if (statusData.status === 'success') {
                        clearInterval(checkInterval);
                        qrcodeStatus.textContent = '登录成功！凭证已保存。';
                        qrcodeStatus.classList.add('success');
                        currentSessionId = null;
                    } else if (statusData.status === 'timeout' || statusData.status === 'refused') {
                        clearInterval(checkInterval);
                        qrcodeStatus.textContent = `登录失败: ${statusData.status === 'timeout' ? '二维码已过期' : '用户拒绝登录'}`;
                        qrcodeStatus.classList.add('error');
                        currentSessionId = null;
                    }
                    // 其他状态继续等待
                }
            } catch (e) {
                console.error('轮询登录状态失败:', e);
            }
        }, 2000);
    } catch (error) {
        console.error('生成二维码失败:', error);
        qrcodePlaceholder.innerHTML = '<i class="fas fa-exclamation-triangle"></i><p>二维码生成失败</p>';
        qrcodePlaceholder.style.display = 'flex';
        qrcodeImage.style.display = 'none';
        qrcodeStatus.textContent = `生成二维码失败: ${error.message}`;
        qrcodeStatus.classList.add('error');
    }
}

// 检查凭证状态
async function checkCredentialStatus() {
    try {
        showLoading(statusResult);
        const response = await fetch(`${BASE_URL}/admin/api/credential/status`);
        if (!response.ok) {
            let errorDetail = '';
            try {
                const errorData = await response.json();
                errorDetail = errorData.error || '';
            } catch (e) {
                // 忽略 JSON 解析错误
            }
            throw new Error(`HTTP error! status: ${response.status}${errorDetail ? ` - ${errorDetail}` : ''}`);
        }

        const data = await response.json();
        showResult(statusResult, data.valid ? '凭证有效' : '凭证无效或已过期',
                   data.valid ? 'success' : 'error');
    } catch (error) {
        console.error(error);
        showResult(statusResult, `检查凭证状态失败: ${error.message}`, 'error');
    }
}

// 刷新凭证
async function refreshCredential() {
    try {
        showLoading(refreshResult);
        refreshBtn.disabled = true;

        const response = await fetch(`${BASE_URL}/admin/api/credential/refresh`, { method: 'POST' });
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        showResult(refreshResult, data.message || '刷新成功', 'success');
    } catch (error) {
        showResult(refreshResult, `刷新凭证失败: ${error.message}`, 'error');
    } finally {
        refreshBtn.disabled = false;
    }
}

// 获取凭证信息
async function getCredentialInfo() {
    try {
        showLoading(infoResult);
        const response = await fetch(`${BASE_URL}/admin/api/credential/info`);
        if (!response.ok) {
            if (response.status === 404)
                throw new Error('未找到凭证文件，请先登录生成凭证');
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // 创建一行一行显示的凭证信息
        let infoHTML = '<div class="credential-info">';
        for (const [key, value] of Object.entries(data)) {
            infoHTML += `
                <div class="info-item">
                    <div class="info-label">${key}</div>
                    <div class="info-value">${value}</div>
                </div>
            `;
        }
        infoHTML += '</div>';
        
        showResult(infoResult, infoHTML, 'info');
    } catch (error) {
        showResult(infoResult, `获取凭证信息失败: ${error.message}`, 'error');
    }
}

// 清空音乐文件夹
async function clearMusicFolder() {
    try {
        showLoading(clearMusicResult);
        clearMusicBtn.disabled = true;

        const response = await fetch(`${BASE_URL}/admin/api/clear_music`, { method: 'POST' });
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        showResult(clearMusicResult, data.message, data.success ? 'success' : 'error');
    } catch (error) {
        showResult(clearMusicResult, `清空音乐文件夹失败: ${error.message}`, 'error');
    } finally {
        clearMusicBtn.disabled = false;
    }
}

// 工具函数
function showLoading(el) { 
    el.innerHTML = '<div class="loading-spinner"></div>加载中...'; 
    el.className = 'result loading'; 
}

function showResult(el, msg, type) { 
    el.innerHTML = msg; 
    el.className = `result ${type}`; 
}