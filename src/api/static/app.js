/**
 * 舞台音效控制台 - Web UI
 * 
 * 功能：
 * - WebSocket 实时状态同步
 * - 播放控制（长按确认）
 * - 音量调节
 * - 断点管理
 * - 音效触发
 */

// ==================== 全局状态 ====================
const state = {
    connected: false,
    mode: 'auto',
    isPlaying: false,
    isPaused: false,
    currentAudioId: null,
    currentPosition: 0,
    currentCueIndex: 0,
    bgmVolume: 0.8,
    sfxVolume: 0.8,
    inSilence: false,
    silenceRemaining: 0,
    cues: [],
    audioFiles: [],
    breakpoints: {},
    playingSfx: {}
};

// WebSocket 连接
let ws = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY = 2000;

// 长按配置
const LONG_PRESS_DURATION = 500;
let longPressTimer = null;
let longPressTarget = null;

// ==================== WebSocket 连接管理 ====================
function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    updateConnectionStatus('connecting');
    
    try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = async () => {
            console.log('WebSocket 已连接');
            state.connected = true;
            reconnectAttempts = 0;
            updateConnectionStatus('connected');
            
            // 请求初始状态
            ws.send(JSON.stringify({ type: 'get_state' }));
            
            // 重新加载数据（确保数据是最新的）
            try {
                await loadCues();
                await loadAudioList();
            } catch (e) {
                console.error('重新加载数据失败:', e);
            }
        };
        
        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleMessage(message);
            } catch (e) {
                console.error('解析消息失败:', e);
            }
        };
        
        ws.onclose = () => {
            console.log('WebSocket 已断开');
            state.connected = false;
            updateConnectionStatus('disconnected');
            scheduleReconnect();
        };
        
        ws.onerror = (error) => {
            console.error('WebSocket 错误:', error);
        };
    } catch (e) {
        console.error('WebSocket 连接失败:', e);
        scheduleReconnect();
    }
}

function scheduleReconnect() {
    if (reconnectTimer) return;
    
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        console.log(`${RECONNECT_DELAY/1000}秒后重连 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connect();
        }, RECONNECT_DELAY);
    } else {
        updateConnectionStatus('disconnected', '连接失败，请刷新页面');
    }
}

function updateConnectionStatus(status, text) {
    const indicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    
    indicator.className = 'indicator ' + status;
    
    if (text) {
        statusText.textContent = text;
    } else {
        switch (status) {
            case 'connected':
                statusText.textContent = '已连接';
                break;
            case 'connecting':
                statusText.textContent = '连接中...';
                break;
            case 'disconnected':
                statusText.textContent = '已断开';
                break;
        }
    }
}

// ==================== 消息处理 ====================
function handleMessage(message) {
    switch (message.type) {
        case 'state':
            updateState(message.data);
            break;
        case 'event':
            handleEvent(message.event, message.data);
            if (message.state) {
                updateState(message.state);
            }
            break;
        case 'pong':
            // 心跳响应
            break;
        case 'error':
            console.error('服务器错误:', message.message);
            break;
    }
}

function handleEvent(event, data) {
    console.log('事件:', event, data);
    // 可以在这里添加特定事件的处理逻辑
}

function updateState(newState) {
    if (!newState) {
        console.warn('updateState: 收到空状态');
        return;
    }
    
    console.log('更新状态:', newState);
    
    // 更新本地状态
    if (newState.mode !== undefined) state.mode = newState.mode;
    if (newState.is_playing !== undefined) state.isPlaying = newState.is_playing;
    if (newState.is_paused !== undefined) state.isPaused = newState.is_paused;
    if (newState.current_audio_id !== undefined) state.currentAudioId = newState.current_audio_id;
    if (newState.current_position !== undefined) state.currentPosition = newState.current_position;
    if (newState.current_cue_index !== undefined) state.currentCueIndex = newState.current_cue_index;
    if (newState.bgm_volume !== undefined) state.bgmVolume = newState.bgm_volume;
    if (newState.sfx_volume !== undefined) state.sfxVolume = newState.sfx_volume;
    if (newState.in_silence !== undefined) state.inSilence = newState.in_silence;
    if (newState.silence_remaining !== undefined) state.silenceRemaining = newState.silence_remaining;
    if (newState.duration !== undefined) state.duration = newState.duration;
    
    console.log('本地状态已更新:', state);
    
    // 更新 UI
    updateUI();
}

// ==================== UI 更新 ====================
function updateUI() {
    updateModeUI();
    updateProgressUI();
    updateVolumeUI();
    updateButtonStates();
    updateCueListHighlight();
}

function updateCueListHighlight() {
    // 更新 Cue 列表高亮
    const cueItems = document.querySelectorAll('.cue-item');
    cueItems.forEach((item, index) => {
        item.classList.remove('current', 'next');
        if (index === state.currentCueIndex) {
            item.classList.add('current');
        } else if (index === state.currentCueIndex + 1) {
            item.classList.add('next');
        }
    });
}

function updateModeUI() {
    // 更新模式标签
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === state.mode);
    });
    
    // 显示对应面板
    document.getElementById('panel-auto').classList.toggle('active', state.mode === 'auto');
    document.getElementById('panel-manual').classList.toggle('active', state.mode === 'manual');
}

function updateProgressUI() {
    const duration = state.duration || 0;
    const position = state.currentPosition || 0;
    const progress = duration > 0 ? (position / duration) * 100 : 0;
    
    // 自动模式进度条
    const progressFill = document.getElementById('progress-fill');
    if (progressFill) {
        progressFill.style.width = progress + '%';
    }
    
    // 手动模式进度条
    const manualProgressFill = document.getElementById('manual-progress-fill');
    if (manualProgressFill) {
        manualProgressFill.style.width = progress + '%';
    }
    
    // 时间显示
    document.getElementById('current-time').textContent = formatTime(position);
    document.getElementById('total-time').textContent = formatTime(duration);
    document.getElementById('manual-current-time').textContent = formatTime(position);
    document.getElementById('manual-total-time').textContent = formatTime(duration);
}

function updateVolumeUI() {
    const bgmSlider = document.getElementById('bgm-volume');
    const sfxSlider = document.getElementById('sfx-volume');
    const bgmValue = document.getElementById('bgm-volume-value');
    const sfxValue = document.getElementById('sfx-volume-value');
    
    // 音量范围 0-3.0 对应 0%-300%
    if (bgmSlider && !bgmSlider.matches(':active')) {
        bgmSlider.value = Math.round(state.bgmVolume * 100);
    }
    if (sfxSlider && !sfxSlider.matches(':active')) {
        sfxSlider.value = Math.round(state.sfxVolume * 100);
    }
    
    if (bgmValue) bgmValue.textContent = Math.round(state.bgmVolume * 100) + '%';
    if (sfxValue) sfxValue.textContent = Math.round(state.sfxVolume * 100) + '%';
}

function updateButtonStates() {
    // 根据播放状态更新按钮
    const playBtns = document.querySelectorAll('[data-action="play"]');
    const pauseBtns = document.querySelectorAll('[data-action="pause"]');
    
    playBtns.forEach(btn => {
        btn.disabled = state.isPlaying && !state.isPaused;
    });
    
    pauseBtns.forEach(btn => {
        btn.disabled = !state.isPlaying || state.isPaused;
    });
}

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// ==================== API 调用 ====================
async function apiCall(endpoint, method = 'POST', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }
        
        console.log(`API 调用: ${method} /api/${endpoint}`, data);
        const response = await fetch(`/api/${endpoint}`, options);
        const result = await response.json();
        console.log(`API 响应: ${endpoint}`, result);
        return result;
    } catch (e) {
        console.error('API 调用失败:', endpoint, e);
        return { success: false, error: e.message };
    }
}

// 播放控制
async function play() {
    return apiCall('play');
}

async function pause() {
    return apiCall('pause');
}

async function resume() {
    return apiCall('resume');
}

async function stop() {
    return apiCall('stop');
}

async function nextCue() {
    return apiCall('next');
}

async function replay() {
    return apiCall('replay');
}

async function seek(position) {
    return apiCall('seek', 'POST', { position });
}

// 音量控制
async function setBgmVolume(volume) {
    return apiCall('volume/bgm', 'POST', { volume });
}

async function setSfxVolume(volume) {
    return apiCall('volume/sfx', 'POST', { volume });
}

// 模式切换
async function switchMode(mode) {
    return apiCall('mode', 'POST', { mode });
}

// 断点管理
async function saveBreakpoint(audioId, position, label = '') {
    return apiCall(`breakpoints/${audioId}`, 'POST', { position, label });
}

async function deleteBreakpoint(audioId, bpId) {
    return apiCall(`breakpoints/${audioId}/${bpId}`, 'DELETE');
}

async function clearBreakpoints(audioId) {
    return apiCall(`breakpoints/${audioId}`, 'DELETE');
}

async function getBreakpoints(audioId) {
    return apiCall(`breakpoints/${audioId}`, 'GET');
}

// 音效控制
async function toggleSfx(sfxId) {
    return apiCall(`sfx/toggle/${sfxId}`, 'POST');
}

// 获取数据
async function getCues() {
    return apiCall('cues', 'GET');
}

async function getAudioList() {
    return apiCall('audio', 'GET');
}

async function getState() {
    return apiCall('state', 'GET');
}

// ==================== 长按处理 ====================
function setupLongPress(element, callback) {
    let pressTimer = null;
    let startTime = 0;
    
    const startPress = (e) => {
        e.preventDefault();
        startTime = Date.now();
        element.classList.add('pressing');
        
        pressTimer = setTimeout(() => {
            element.classList.remove('pressing');
            callback();
        }, LONG_PRESS_DURATION);
    };
    
    const endPress = (e) => {
        e.preventDefault();
        element.classList.remove('pressing');
        
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
            
            const elapsed = Date.now() - startTime;
            if (elapsed < LONG_PRESS_DURATION) {
                // 显示提示
                showToast('请长按以确认操作');
            }
        }
    };
    
    const cancelPress = () => {
        element.classList.remove('pressing');
        if (pressTimer) {
            clearTimeout(pressTimer);
            pressTimer = null;
        }
    };
    
    // 触摸事件
    element.addEventListener('touchstart', startPress, { passive: false });
    element.addEventListener('touchend', endPress, { passive: false });
    element.addEventListener('touchcancel', cancelPress);
    
    // 鼠标事件
    element.addEventListener('mousedown', startPress);
    element.addEventListener('mouseup', endPress);
    element.addEventListener('mouseleave', cancelPress);
}

function showToast(message, duration = 2000) {
    // 移除现有的 toast
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0,0,0,0.8);
        color: white;
        padding: 10px 20px;
        border-radius: 20px;
        font-size: 14px;
        z-index: 1000;
        animation: fadeInOut ${duration}ms ease;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), duration);
}

// ==================== Cue 列表渲染 ====================
async function loadCues() {
    const result = await getCues();
    console.log('加载 Cue 列表:', result);
    if (result.cues) {
        state.cues = result.cues;
        state.currentCueIndex = result.current_index || 0;
        renderCueList();
        console.log('Cue 列表已加载:', state.cues.length, '个');
    } else {
        console.warn('Cue 列表为空或加载失败');
    }
}

function renderCueList() {
    const container = document.getElementById('cue-list');
    if (!container) return;
    
    container.innerHTML = '';
    
    state.cues.forEach((cue, index) => {
        const item = document.createElement('div');
        item.className = 'cue-item';
        
        if (index === state.currentCueIndex) {
            item.classList.add('current');
        } else if (index === state.currentCueIndex + 1) {
            item.classList.add('next');
        }
        
        const duration = cue.end_time ? (cue.end_time - cue.start_time) : 0;
        
        item.innerHTML = `
            <div class="cue-index">${index + 1}</div>
            <div class="cue-info">
                <div class="cue-title">${cue.label || cue.audio_id}</div>
                <div class="cue-duration">${formatTime(duration)}</div>
            </div>
        `;
        
        item.addEventListener('click', () => {
            // 可以添加点击跳转到指定 Cue 的功能
        });
        
        container.appendChild(item);
    });
}

// ==================== 音频列表渲染 ====================
async function loadAudioList() {
    const result = await getAudioList();
    console.log('加载音频列表:', result);
    if (result.audio_files) {
        state.audioFiles = result.audio_files;
        renderAudioSelect();
        renderSfxGrid();
        console.log('音频列表已加载:', state.audioFiles.length, '个');
    } else {
        console.warn('音频列表为空或加载失败');
    }
}

function renderAudioSelect() {
    const select = document.getElementById('audio-select');
    if (!select) return;
    
    select.innerHTML = '<option value="">-- 选择音频 --</option>';
    
    state.audioFiles.forEach(audio => {
        if (audio.track_type === 'bgm') {
            const option = document.createElement('option');
            option.value = audio.id;
            option.textContent = audio.title || audio.id;
            select.appendChild(option);
        }
    });
}

function renderSfxGrid() {
    const container = document.getElementById('sfx-grid');
    if (!container) return;
    
    container.innerHTML = '';
    
    state.audioFiles.forEach(audio => {
        if (audio.track_type === 'sfx') {
            const btn = document.createElement('button');
            btn.className = 'sfx-btn';
            btn.dataset.sfxId = audio.id;
            btn.textContent = audio.title || audio.id;
            
            if (state.playingSfx[audio.id]) {
                btn.classList.add('playing');
            }
            
            btn.addEventListener('click', async () => {
                const result = await toggleSfx(audio.id);
                if (result.success) {
                    state.playingSfx[audio.id] = result.is_playing;
                    btn.classList.toggle('playing', result.is_playing);
                }
            });
            
            container.appendChild(btn);
        }
    });
}

// ==================== 断点列表渲染 ====================
async function loadBreakpoints(audioId) {
    if (!audioId) return;
    
    const result = await getBreakpoints(audioId);
    if (result.breakpoints) {
        state.breakpoints[audioId] = result.breakpoints;
        renderBreakpointList(audioId);
    }
}

function renderBreakpointList(audioId) {
    const container = document.getElementById('breakpoint-list');
    if (!container) return;
    
    const breakpoints = state.breakpoints[audioId] || [];
    container.innerHTML = '';
    
    if (breakpoints.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 10px;">暂无断点</div>';
        return;
    }
    
    breakpoints.forEach(bp => {
        const item = document.createElement('div');
        item.className = 'breakpoint-item';
        
        item.innerHTML = `
            <span class="bp-time">${formatTime(bp.position)}</span>
            <span class="bp-label">${bp.label || (bp.auto_saved ? '自动保存' : '')}</span>
            <button class="bp-delete" data-bp-id="${bp.id}">删除</button>
        `;
        
        // 点击断点跳转
        item.addEventListener('click', async (e) => {
            if (e.target.classList.contains('bp-delete')) {
                e.stopPropagation();
                await deleteBreakpoint(audioId, bp.id);
                loadBreakpoints(audioId);
            } else {
                await seek(bp.position);
            }
        });
        
        container.appendChild(item);
    });
}

// ==================== 事件绑定 ====================
function setupEventListeners() {
    // 模式切换
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const mode = btn.dataset.mode;
            await switchMode(mode);
        });
    });
    
    // 自动模式 - 播放控制（长按）
    const btnPlay = document.getElementById('btn-play');
    if (btnPlay) {
        setupLongPress(btnPlay, async () => {
            if (state.isPaused) {
                await resume();
            } else {
                await play();
            }
        });
    }
    
    const btnPause = document.getElementById('btn-pause');
    if (btnPause) {
        setupLongPress(btnPause, pause);
    }
    
    // 停止和下一段（普通点击）
    const btnStop = document.getElementById('btn-stop');
    if (btnStop) {
        btnStop.addEventListener('click', stop);
    }
    
    const btnNext = document.getElementById('btn-next');
    if (btnNext) {
        btnNext.addEventListener('click', nextCue);
    }
    
    // 手动模式 - 播放控制（长按）
    const btnManualPlay = document.getElementById('btn-manual-play');
    if (btnManualPlay) {
        setupLongPress(btnManualPlay, async () => {
            if (state.isPaused) {
                await resume();
            } else {
                await play();
            }
        });
    }
    
    const btnManualPause = document.getElementById('btn-manual-pause');
    if (btnManualPause) {
        setupLongPress(btnManualPause, pause);
    }
    
    const btnManualStop = document.getElementById('btn-manual-stop');
    if (btnManualStop) {
        btnManualStop.addEventListener('click', stop);
    }
    
    const btnReplay = document.getElementById('btn-replay');
    if (btnReplay) {
        btnReplay.addEventListener('click', replay);
    }
    
    // 音频选择
    const audioSelect = document.getElementById('audio-select');
    if (audioSelect) {
        audioSelect.addEventListener('change', (e) => {
            const audioId = e.target.value;
            if (audioId) {
                state.currentAudioId = audioId;
                loadBreakpoints(audioId);
            }
        });
    }
    
    // 断点管理
    const btnSaveBp = document.getElementById('btn-save-bp');
    if (btnSaveBp) {
        btnSaveBp.addEventListener('click', async () => {
            if (state.currentAudioId && state.currentPosition > 0) {
                await saveBreakpoint(state.currentAudioId, state.currentPosition);
                loadBreakpoints(state.currentAudioId);
                showToast('断点已保存');
            }
        });
    }
    
    const btnClearBp = document.getElementById('btn-clear-bp');
    if (btnClearBp) {
        btnClearBp.addEventListener('click', async () => {
            if (state.currentAudioId) {
                await clearBreakpoints(state.currentAudioId);
                loadBreakpoints(state.currentAudioId);
                showToast('断点已清除');
            }
        });
    }
    
    // 音量控制 (0-300% 对应 0-3.0)
    const bgmVolume = document.getElementById('bgm-volume');
    if (bgmVolume) {
        bgmVolume.addEventListener('input', (e) => {
            const volume = parseInt(e.target.value) / 100;  // 转换为 0-3.0
            document.getElementById('bgm-volume-value').textContent = e.target.value + '%';
            setBgmVolume(volume);
        });
    }
    
    const sfxVolume = document.getElementById('sfx-volume');
    if (sfxVolume) {
        sfxVolume.addEventListener('input', (e) => {
            const volume = parseInt(e.target.value) / 100;  // 转换为 0-3.0
            document.getElementById('sfx-volume-value').textContent = e.target.value + '%';
            setSfxVolume(volume);
        });
    }
    
    // 进度条点击跳转
    const progressBar = document.getElementById('progress-bar');
    if (progressBar) {
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            const position = percent * (state.duration || 0);
            seek(position);
        });
    }
    
    const manualProgressBar = document.getElementById('manual-progress-bar');
    if (manualProgressBar) {
        manualProgressBar.addEventListener('click', (e) => {
            const rect = manualProgressBar.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            const position = percent * (state.duration || 0);
            seek(position);
        });
    }
}

// ==================== 初始化 ====================
async function init() {
    console.log('舞台音效控制台 Web UI 初始化...');
    
    // 设置事件监听
    setupEventListeners();
    
    // 连接 WebSocket
    connect();
    
    // 加载初始数据（不等待 WebSocket 连接）
    try {
        await loadCues();
        await loadAudioList();
        
        // 获取初始状态
        const stateResult = await getState();
        if (stateResult) {
            updateState(stateResult);
        }
    } catch (e) {
        console.error('加载初始数据失败:', e);
    }
    
    // 定期发送心跳
    setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
        }
    }, 30000);
    
    // 定期更新进度（每 500ms）
    setInterval(() => {
        if (state.isPlaying && !state.isPaused && state.duration > 0) {
            // 本地估算位置更新
            state.currentPosition += 0.5;
            if (state.currentPosition > state.duration) {
                state.currentPosition = state.duration;
            }
            updateProgressUI();
        }
    }, 500);
    
    console.log('初始化完成');
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);

// 添加 toast 动画样式
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInOut {
        0% { opacity: 0; transform: translateX(-50%) translateY(20px); }
        15% { opacity: 1; transform: translateX(-50%) translateY(0); }
        85% { opacity: 1; transform: translateX(-50%) translateY(0); }
        100% { opacity: 0; transform: translateX(-50%) translateY(-20px); }
    }
`;
document.head.appendChild(style);
