/**
 * EduMi Meeting Room — UI orchestration layer
 * Depends on: sfu-client.js (loaded before this file)
 */
'use strict';

const _d = document.getElementById('meeting-data').dataset;
const meetingId = _d.meetingId;
const meetingCode = _d.meetingCode;
const currentUserId = _d.userId;
const currentUsername = _d.username;
const isHost = _d.isHost === 'true';

const wsProto = location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${wsProto}//${location.host}/ws/meeting/${meetingCode.toUpperCase()}/`;
let ws = null, wsTimer = null;

function connectPresenceWS() {
    if (ws && ws.readyState === WebSocket.OPEN) return;
    ws = new WebSocket(wsUrl);
    ws.onopen = () => clearTimeout(wsTimer);
    ws.onclose = () => { wsTimer = setTimeout(connectPresenceWS, 3000); };
    ws.onerror = () => {};
    ws.onmessage = ({ data }) => {
        const msg = JSON.parse(data);
        switch (msg.type) {
            case 'participant_list': (msg.participants || []).forEach(p => addParticipant(p.user_id, p.username, p.is_host, p.is_admin)); break;
            case 'user_joined': addParticipant(msg.user_id, msg.username, msg.is_host, msg.is_admin); break;
            case 'user_left': removeParticipant(msg.user_id); break;
            case 'chat': appendChatMessage(msg.username, msg.message, msg.user_id == currentUserId, msg.timestamp); break;
            case 'screen_share_started': if (String(msg.user_id) !== String(currentUserId)) showNotification(`${msg.username} started sharing screen`, 'info'); break;
            case 'screen_share_stopped': showNotification(`${msg.username} stopped sharing screen`, 'info'); break;
            case 'meeting_sleeping': showNotification('Meeting put to sleep by host', 'warning'); enterSleepMode(); break;
            case 'meeting_unfrozen': showNotification('Meeting is now active', 'success'); exitSleepMode(); break;
        }
    };
}

function addVideoElement(userId, username, stream, isLocal) {
    let box = document.getElementById(`video-${userId}`);
    if (!box) {
        box = document.createElement('div');
        box.id = `video-${userId}`;
        box.className = `video-box${isLocal ? ' local' : ''}`;
        box.dataset.userId = userId;
        const vid = document.createElement('video');
        vid.autoplay = true; vid.playsInline = true; vid.muted = isLocal;
        if (isLocal) vid.style.transform = 'scaleX(-1)';
        const tag = document.createElement('div');
        tag.className = 'video-nametag';
        tag.textContent = isLocal ? 'You' : username;
        box.appendChild(vid); box.appendChild(tag);
        document.getElementById('sidebarVideoArea').appendChild(box);
        vid.srcObject = stream;
        vid.onloadedmetadata = () => vid.play().catch(() => {});
        if (!isLocal) setupAudioDetection(stream, userId);
    } else {
        const vid = box.querySelector('video');
        if (vid && vid.srcObject !== stream) { vid.srcObject = stream; vid.onloadedmetadata = () => vid.play().catch(() => {}); }
    }
    debouncedLayout();
}

function attachAudio(peerId, displayName, stream) {
    let box = document.getElementById(`video-${peerId}`);
    if (!box) {
        box = document.createElement('div');
        box.id = `video-${peerId}`; box.className = 'video-box'; box.dataset.userId = peerId;
        const tag = document.createElement('div'); tag.className = 'video-nametag'; tag.textContent = displayName;
        box.appendChild(tag); document.getElementById('sidebarVideoArea').appendChild(box);
    }
    let aud = box.querySelector('audio');
    if (!aud) { aud = document.createElement('audio'); aud.autoplay = true; aud.style.display = 'none'; box.appendChild(aud); }
    aud.srcObject = stream; aud.play().catch(() => {});
    setupAudioDetection(stream, peerId);
}

function setupAudioDetection(stream, userId) {
    try {
        const ac = new AudioContext(), an = ac.createAnalyser();
        an.fftSize = 256; an.smoothingTimeConstant = 0.8;
        ac.createMediaStreamSource(stream).connect(an);
        const buf = new Uint8Array(an.frequencyBinCount);
        let t = null;
        function tick() {
            an.getByteFrequencyData(buf);
            const avg = buf.reduce((a, b) => a + b, 0) / buf.length;
            const box = document.getElementById(`video-${userId}`);
            if (!box) return;
            if (avg > 15) { box.classList.add('speaking'); clearTimeout(t); t = setTimeout(() => box.classList.remove('speaking'), 500); }
            if (SFUClient.remotePeers.has(userId)) requestAnimationFrame(tick);
        }
        tick();
    } catch (_) {}
}

const _peers = {};

function addParticipant(userId, username, isHostFlag, isAdmin) {
    _peers[userId] = { username, isHost: !!isHostFlag, isAdmin: !!isAdmin };
    renderParticipants();
}

function removeParticipant(userId) {
    delete _peers[userId];
    document.getElementById(`video-${userId}`)?.remove();
    renderParticipants(); debouncedLayout();
}

function renderParticipants() {
    const count = Object.keys(_peers).length + 1;
    document.getElementById('participantCount').textContent = count;
    const list = document.getElementById('participantsList');
    list.querySelectorAll('.participant-item:not(:first-child)').forEach(i => i.remove());
    Object.values(_peers).forEach(d => {
        const item = document.createElement('div');
        item.className = 'participant-item';
        item.innerHTML = `<div class="participant-avatar"><img src="https://ui-avatars.com/api/?name=${encodeURIComponent(d.username)}&background=1877f2&color=fff" alt="${d.username}"></div>
            <div class="participant-info"><div class="participant-name">${d.username}</div>
            <div style="display:flex;gap:4px;margin-top:2px;">
                ${d.isAdmin ? '<span class="host-label" style="background:#ef4444;font-size:10px;padding:1px 6px;">Admin</span>' : ''}
                ${d.isHost  ? '<span class="host-label" style="font-size:10px;padding:1px 6px;">Host</span>' : ''}
            </div></div>`;
        list.appendChild(item);
    });
}

function updateVideoLayout() {
    const container = document.getElementById('videoGridContainer');
    const mainArea = document.getElementById('mainVideoArea');
    const sidebar = document.getElementById('sidebarVideoArea');
    if (!container) return;
    const boxes = Array.from(document.querySelectorAll('.video-box'));
    const count = boxes.length;
    requestAnimationFrame(() => {
        container.className = 'video-grid-container';
        boxes.forEach(b => b.classList.remove('main-presents'));
        const screenId = SFUClient.isScreenSharing ? String(currentUserId) : null;
        let highlight = screenId;
        if (!highlight && count > 1) {
            const speaker = boxes.find(b => b.classList.contains('speaking'));
            highlight = speaker ? String(speaker.dataset.userId)
                : String(boxes.find(b => String(b.dataset.userId) !== String(currentUserId))?.dataset.userId || '');
        }
        if (highlight) {
            container.classList.add('sidebar-view');
            if (screenId === String(currentUserId)) {
                mainArea.innerHTML = '<div class="presenter-dashboard"><h2>You\'re presenting</h2><button class="stop-present-btn" onclick="stopScreenShare()">Stop Presenting</button></div>';
            } else {
                const hBox = document.getElementById(`video-${highlight}`);
                if (hBox) { mainArea.appendChild(hBox); hBox.classList.add('main-presents'); hBox.querySelector('video')?.play().catch(() => {}); }
            }
            boxes.forEach(b => {
                if (String(b.dataset.userId) !== highlight && b.parentElement !== sidebar) { sidebar.appendChild(b); b.querySelector('video')?.play().catch(() => {}); }
            });
        } else {
            container.classList.add('grid-view', `count-${Math.min(count, 25)}`);
            boxes.forEach(b => { if (b.parentElement !== sidebar) sidebar.appendChild(b); b.querySelector('video')?.play().catch(() => {}); });
            mainArea.innerHTML = '';
        }
        document.getElementById('participantCount').textContent = count;
    });
}

function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; }
const debouncedLayout = debounce(updateVideoLayout, 50);

setInterval(() => {
    document.querySelectorAll('.video-box:not(.local) video').forEach(v => {
        if (v.paused && v.readyState >= 2) v.play().catch(() => {});
        if (v.buffered.length) { const d = v.buffered.end(v.buffered.length - 1) - v.currentTime; if (d > 0.5) v.currentTime = v.buffered.end(v.buffered.length - 1) - 0.05; }
    });
}, 3000);

async function toggleMic() { const on = await SFUClient.toggleMic(); document.getElementById('micBtn')?.classList.toggle('off', !on); }
async function toggleCamera() { const on = await SFUClient.toggleCamera(); document.getElementById('camBtn')?.classList.toggle('off', !on); document.getElementById(`video-${currentUserId}`)?.classList.toggle('muted', !on); }

async function toggleScreenShare() {
    if (SFUClient.isScreenSharing) { await stopScreenShare(); return; }
    try { await SFUClient.startScreenShare(); document.getElementById('screenBtn')?.classList.add('active'); ws?.send(JSON.stringify({ type: 'screen_share_started' })); updateVideoLayout(); }
    catch (e) { if (e.name !== 'NotAllowedError') showNotification('Screen share failed: ' + e.message, 'error'); }
}

async function stopScreenShare() {
    await SFUClient.stopScreenShare();
    document.getElementById('screenBtn')?.classList.remove('active');
    ws?.send(JSON.stringify({ type: 'screen_share_stopped' }));
    updateVideoLayout();
}

function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg || !ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'chat', message: msg, timestamp: new Date().toISOString() }));
    appendChatMessage('You', msg, true);
    input.value = '';
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('chatInput')?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); } });
});

function appendChatMessage(username, message, isOwn, timestamp) {
    const box = document.getElementById('chatMessages');
    if (!box) return;
    const div = document.createElement('div');
    div.className = `chat-msg${isOwn ? ' own' : ''}`;
    const time = timestamp ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    div.innerHTML = `<div class="chat-msg-header"><strong>${username}</strong><span class="chat-msg-time">${time}</span></div><div class="chat-msg-text">${message}</div>`;
    box.appendChild(div); box.scrollTop = box.scrollHeight;
    const panel = document.getElementById('chatPanel');
    if (!panel?.classList.contains('active')) { const b = document.getElementById('chatBadge'); if (b) { b.style.display = 'inline'; b.textContent = (parseInt(b.textContent) || 0) + 1; } }
}

function openSidebar(tab) { document.getElementById('meetSidebar').style.display = 'flex'; document.querySelector('.meet-main')?.classList.add('sidebar-open'); switchSidebarTab(tab); }
function toggleSidebar() { const s = document.getElementById('meetSidebar'); const open = s.style.display !== 'none'; s.style.display = open ? 'none' : 'flex'; document.querySelector('.meet-main')?.classList.toggle('sidebar-open', !open); }
function switchSidebarTab(tab) {
    document.querySelectorAll('.sidebar-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.sidebar-panel').forEach(p => p.classList.remove('active'));
    document.querySelector(`.sidebar-tab[onclick*="${tab}"]`)?.classList.add('active');
    document.getElementById(`${tab}Panel`)?.classList.add('active');
    if (tab === 'chat') { const b = document.getElementById('chatBadge'); if (b) { b.style.display = 'none'; b.textContent = '0'; } }
}

function toggleTheme() { const dark = document.body.classList.toggle('dark-mode'); localStorage.setItem('theme', dark ? 'dark' : 'light'); }
function loadTheme() { if (localStorage.getItem('theme') === 'dark') document.body.classList.add('dark-mode'); }

function startTimer() {
    const start = Date.now();
    setInterval(() => {
        const s = Math.floor((Date.now() - start) / 1000);
        document.getElementById('meetTimer').textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    }, 1000);
}

let isSleeping = false;
function toggleSleepMode() {
    if (!isHost) return;
    const url = isSleeping ? `/meetings/unfreeze/${meetingCode}/` : `/meetings/sleep/${meetingCode}/`;
    fetch(url, { method: 'GET', headers: { 'X-CSRFToken': getCookie('csrftoken') } }).then(r => r.json()).then(d => { if (d.status === 'success') { isSleeping = !isSleeping; document.getElementById('sleepBtn')?.classList.toggle('active', isSleeping); } }).catch(() => {});
}
function enterSleepMode() { isSleeping = true; document.getElementById('sleepBtn')?.classList.add('active'); }
function exitSleepMode()  { isSleeping = false; document.getElementById('sleepBtn')?.classList.remove('active'); }

function leaveMeeting() {
    if (!confirm(isHost ? 'End meeting for everyone?' : 'Leave this meeting?')) return;
    SFUClient.leave(); ws?.close();
    fetch(`/meetings/leave/${meetingId}/`, { method: 'POST', headers: { 'X-CSRFToken': getCookie('csrftoken') } })
        .finally(() => { location.href = isHost ? '/meetings/teacher/' : '/meetings/student/'; });
}

let isRecording = false, mediaRecorder = null, recordedChunks = [], recStart = null, recTimer = null;

async function toggleRecording() { isRecording ? stopRecording() : await startRecording(); }

async function startRecording() {
    const canvas = document.createElement('canvas'); canvas.width = 1920; canvas.height = 1080;
    const ctx = canvas.getContext('2d'); const stream = canvas.captureStream(30);
    SFUClient.localStream?.getAudioTracks().forEach(t => stream.addTrack(t));
    const draw = () => {
        if (!isRecording) return;
        ctx.fillStyle = '#111'; ctx.fillRect(0, 0, 1920, 1080);
        const vids = [...document.querySelectorAll('.video-box video')];
        const cols = Math.ceil(Math.sqrt(vids.length)) || 1;
        const w = 1920 / cols, h = 1080 / Math.ceil(vids.length / cols);
        vids.forEach((v, i) => { if (v.readyState >= 2) ctx.drawImage(v, (i % cols) * w, Math.floor(i / cols) * h, w, h); });
        requestAnimationFrame(draw);
    };
    draw();
    const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp9,opus') ? 'video/webm;codecs=vp9,opus' : 'video/webm';
    mediaRecorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 4000000 });
    recordedChunks = [];
    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) recordedChunks.push(e.data); };
    mediaRecorder.onstop = () => {
        const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob(recordedChunks, { type: 'video/webm' })), download: `meeting-${meetingCode}-${new Date().toISOString().slice(0,19).replace(/:/g,'-')}.webm`, style: 'display:none' });
        document.body.appendChild(a); a.click(); a.remove();
    };
    mediaRecorder.start(1000); isRecording = true; recStart = Date.now();
    document.getElementById('recordingIndicator').style.display = 'flex';
    document.getElementById('recordBtn')?.classList.add('recording');
    recTimer = setInterval(() => { const s = Math.floor((Date.now() - recStart) / 1000); document.getElementById('recordingTimer').textContent = `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`; }, 1000);
}

function stopRecording() {
    if (!mediaRecorder) return;
    mediaRecorder.stop(); mediaRecorder = null; isRecording = false; clearInterval(recTimer);
    document.getElementById('recordingIndicator').style.display = 'none';
    document.getElementById('recordBtn')?.classList.remove('recording');
}

function showNotification(message, type) {
    const n = document.createElement('div');
    const bg = type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : type === 'success' ? '#10b981' : '#3b82f6';
    n.style.cssText = `position:fixed;top:80px;left:50%;transform:translateX(-50%);background:${bg};color:white;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,.3);pointer-events:none;`;
    n.textContent = message; document.body.appendChild(n); setTimeout(() => n.remove(), 4000);
}

function getCookie(name) { return document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith(name + '='))?.split('=')[1] ?? null; }
function syncParticipants() { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'request_participants' })); }

// Error boundary
function showErrorBoundary(message, canRetry) {
    document.getElementById('error-boundary')?.remove();
    const el = document.createElement('div');
    el.id = 'error-boundary';
    el.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.95);z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:white;padding:2rem;text-align:center;';
    el.innerHTML = `<div style="font-size:3.5rem;margin-bottom:1rem;">⚠️</div>
        <h2 style="font-size:1.4rem;margin-bottom:.5rem;">Connection Failed</h2>
        <p style="color:rgba(255,255,255,.7);max-width:400px;margin-bottom:2rem;">${message}</p>
        <button style="padding:12px 28px;background:#6366f1;color:white;border:none;border-radius:8px;font-weight:600;cursor:pointer;font-size:1rem;">${canRetry ? 'Rejoin Meeting' : 'Back to Dashboard'}</button>`;
    el.querySelector('button').onclick = canRetry ? () => location.reload() : () => { location.href = isHost ? '/meetings/teacher/' : '/meetings/student/'; };
    document.body.appendChild(el);
}

// Auto-reconnect
let _reconnectAttempts = 0;
const _MAX_RECONNECT = 5;

async function _reconnect() {
    if (_reconnectAttempts >= _MAX_RECONNECT) { showErrorBoundary('Lost connection to the meeting. Please rejoin.', true); return; }
    _reconnectAttempts++;
    showNotification(`Reconnecting... (${_reconnectAttempts}/${_MAX_RECONNECT})`, 'warning');
    try {
        await SFUClient.join(meetingCode, String(currentUserId), currentUsername);
        _reconnectAttempts = 0; showNotification('Reconnected!', 'success');
    } catch (_) { setTimeout(_reconnect, 3000); }
}

// Init
async function init() {
    loadTheme();
    connectPresenceWS();

    SFUClient
        .on('onLocalStream', stream => addVideoElement(currentUserId, currentUsername, stream, true))
        .on('onRemoteStream', (peerId, name, stream, kind) => {
            if (kind === 'video') addVideoElement(peerId, name, stream, false);
            else attachAudio(peerId, name, stream);
        })
        .on('onRemoteStreamClosed', (peerId, kind) => { if (kind === 'video') { const v = document.querySelector(`#video-${peerId} video`); if (v) v.srcObject = null; } })
        .on('onPeerJoined',     (id, name) => { addParticipant(id, name); showNotification(`${name} joined`, 'info'); })
        .on('onPeerLeft',       (id, name) => { removeParticipant(id); showNotification(`${name} left`, 'info'); })
        .on('onProducerPaused', (id, kind) => { if (kind === 'video') document.getElementById(`video-${id}`)?.classList.add('muted'); })
        .on('onProducerResumed',(id, kind) => { if (kind === 'video') document.getElementById(`video-${id}`)?.classList.remove('muted'); })
        .on('onDisconnected',   () => { showNotification('Connection lost — reconnecting...', 'warning'); setTimeout(_reconnect, 2000); });

    try {
        await SFUClient.join(meetingCode, String(currentUserId), currentUsername);
        _reconnectAttempts = 0;
    } catch (err) {
        console.error('[SFU] join failed:', err);
        showErrorBoundary(
            window.SFU_AVAILABLE === false
                ? 'The media server (SFU) is not running. Start it with: cd sfu && node src/server.js'
                : `Could not connect to the media server. ${err.message || 'Check your connection and try again.'}`,
            true
        );
        return;
    }

    startTimer();
    setInterval(syncParticipants, 60000);
}

window.addEventListener('load', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();
    init().catch(e => { console.error('[Init] fatal:', e); showErrorBoundary('Failed to initialize meeting room. Please refresh.', true); });
});
window.addEventListener('beforeunload', () => { SFUClient.leave(); ws?.close(); });

window.addEventListener('load', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();
    init().catch(e => { console.error('[Init] fatal:', e); showErrorBoundary('Failed to initialize meeting room. Please refresh.', true); });
});
window.addEventListener('beforeunload', () => { SFUClient.leave(); ws?.close(); });
