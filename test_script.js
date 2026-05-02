
// ── Config ────────────────────────────────────────────────────────────────────
const _d          = document.getElementById('meeting-data').dataset;
const meetingCode = _d.meetingCode;
const currentUserId   = _d.userId;
const currentUsername = _d.username;
const isHost      = _d.isHost === 'true';
const initialCanSpeak = _d.canSpeak === 'true';
const initialCanVideo = _d.canVideo === 'true';
const initialCanShare = _d.canShare === 'true';
const TOKEN_URL   = _d.tokenUrl;
const LEAVE_URL    = _d.leaveUrl;
const SLEEP_URL    = _d.sleepUrl;
const UNFREEZE_URL = _d.unfreezeUrl;
const AFTER_LEAVE  = _d.afterLeaveUrl;
const CSRF         = _d.csrf;

// LiveKit SDK globals (from UMD bundle)
const { Room, RoomEvent, Track, TrackEvent, LocalTrack,
        createLocalScreenTracks, VideoPresets, ConnectionState } = LivekitClient;

// ── State ─────────────────────────────────────────────────────────────────────
let room = null;
let isMicOn    = true;
let isCameraOn = true;
let isScreenSharing = false;
let screenTrackPub  = null;
let isSleeping = false;
let unreadMessages = 0;
let timerInterval  = null;
let timerSeconds   = 0;
let signalingWs    = null;

// Permission State (Enforced locally for students)
let canSpeak = initialCanSpeak;
let canVideo = initialCanVideo;
let canShare = initialCanShare;

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
    // ── Signaling WebSocket ──────────────────────────────────────────────────
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    signalingWs = new WebSocket(`${proto}//${window.location.host}/ws/meeting/${meetingCode}/`);
    
    signalingWs.onmessage = (e) => {
        const data = JSON.parse(e.data);
        handleSignalingMessage(data);
    };

    // Fetch token from Django
    const res   = await fetch(TOKEN_URL);
    const data  = await res.json();
    if (data.error) { alert('Access denied: ' + data.error); return; }

    const { token, url } = data;

    room = new Room({
        adaptiveStream: true,          // auto-adjust quality per subscriber bandwidth
        dynacast: true,                // only encode layers actually needed
        videoCaptureDefaults: {
            resolution: VideoPresets.h1080.resolution,
        },
        publishDefaults: {
            simulcast: true,           // send 3 quality layers — SFU picks the right one per viewer
            videoCodec: 'h264',
        },
    });

    // ── Room events ───────────────────────────────────────────────────────────
    room
        .on(RoomEvent.ParticipantConnected,    onParticipantConnected)
        .on(RoomEvent.ParticipantDisconnected, onParticipantDisconnected)
        .on(RoomEvent.TrackSubscribed,         onTrackSubscribed)
        .on(RoomEvent.TrackUnsubscribed,       onTrackUnsubscribed)
        .on(RoomEvent.TrackMuted,              onTrackMuted)
        .on(RoomEvent.TrackUnmuted,            onTrackUnmuted)
        .on(RoomEvent.ActiveSpeakersChanged,   onActiveSpeakersChanged)
        .on(RoomEvent.DataReceived,            onDataReceived)
        .on(RoomEvent.Disconnected,            onDisconnected)
        .on(RoomEvent.ConnectionStateChanged,  onConnectionStateChanged);

    await room.connect(url, token);
    console.log('Connected to LiveKit room:', room.name);

    // Publish local camera + mic
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showNotification('Camera/Mic blocked! Please use HTTPS or localhost.', 'error');
            console.warn('mediaDevices API is missing. Usually happens on non-HTTPS connections.');
        } else {
            await room.localParticipant.enableCameraAndMicrophone();
        }
    } catch (e) {
        console.error('Camera/Mic error:', e);
        showNotification('Could not start camera/mic: ' + e.message, 'warning');
    }

    // Render local participant
    renderLocalParticipant();

    // Render any participants already in the room
    room.remoteParticipants.forEach(p => onParticipantConnected(p));

    updateParticipantCount();
    startTimer();
}

// ── Render helpers ────────────────────────────────────────────────────────────
function getOrCreateBox(identity, displayName, isLocal) {
    let box = document.getElementById(`video-box-${identity}`);
    if (box) return box;

    box = document.createElement('div');
    box.id = `video-box-${identity}`;
    box.className = 'video-box';
    box.dataset.identity = identity;
    box.dataset.userId   = identity; // Required for Face Tracking
    box.style.cursor = 'pointer'; // Make it look clickable
    
    // Click to enlarge this video
    box.onclick = () => {
        if (box.parentElement.id !== 'mainVideoArea') {
            const mainArea = document.getElementById('mainVideoArea');
            if (mainArea.children.length > 0) {
                const currentMain = mainArea.children[0];
                currentMain.classList.remove('main-presents');
                const v = currentMain.querySelector('video');
                if (v) { 
                    v.style.objectFit = 'cover'; 
                    v.style.transform = currentMain.dataset.identity === room.localParticipant.identity ? 'scaleX(-1)' : 'none'; 
                }
                document.getElementById('sidebarVideoArea').appendChild(currentMain);
            }
            moveToMain(box, displayName, identity === 'local-screen');
        }
    };

    const nameTag = document.createElement('div');
    nameTag.className = 'video-nametag';
    nameTag.textContent = isLocal ? 'You' : displayName;
    box.appendChild(nameTag);

    document.getElementById('sidebarVideoArea').appendChild(box);
    updateLayout();
    return box;
}

function renderLocalParticipant() {
    const lp  = room.localParticipant;
    const box = getOrCreateBox(lp.identity, currentUsername, true);

    // Attach camera track if already published
    lp.videoTrackPublications.forEach(pub => {
        if (pub.track && pub.source === Track.Source.Camera) {
            attachTrackToBox(pub.track, box, true);
        }
    });

    // Also listen for future local track publications (e.g. screen share)
    lp.on('localTrackPublished', pub => {
        if (pub.source === Track.Source.ScreenShare && pub.track) {
            showLocalScreenShare(pub.track);
        }
    });
    lp.on('localTrackUnpublished', pub => {
        if (pub.source === Track.Source.ScreenShare) {
            hideLocalScreenShare();
        }
    });
}

function attachTrackToBox(track, box, isLocal) {
    // Remove existing element for this track kind
    const existing = box.querySelector(`[data-kind="${track.kind}"]`);
    if (existing) existing.remove();

    const el = track.attach();
    el.dataset.kind = track.kind;
    if (track.kind === Track.Kind.Video) {
        el.style.cssText = 'width:100%;height:100%;object-fit:cover;display:block;';
        if (isLocal) el.style.transform = 'scaleX(-1)';
        el.muted = true;
        el.autoplay = true;
        el.playsInline = true;
        if (isLocal) {
            el.id = 'localVideo';
            el.dataset.local = 'true';
        }
        box.insertBefore(el, box.querySelector('.video-nametag'));
    }
    // Audio elements are invisible — LiveKit attaches them to document automatically
}

function detachTrackFromBox(track, box) {
    track.detach().forEach(el => el.remove());
}

// ── Local screen share preview ────────────────────────────────────────────────
function showLocalScreenShare(track) {
    // Create a dedicated screen-share box for the presenter
    let box = document.getElementById('local-screen-box');
    if (!box) {
        box = document.createElement('div');
        box.id = 'local-screen-box';
        box.className = 'video-box';
        box.dataset.identity = 'local-screen';
        const tag = document.createElement('div');
        tag.className = 'video-nametag';
        tag.textContent = 'Your Screen';
        box.appendChild(tag);
    }
    const el = track.attach();
    el.dataset.kind = 'video';
    el.style.cssText = 'width:100%;height:100%;object-fit:contain;display:block;background:#000;';
    el.muted = true;
    el.autoplay = true;
    el.playsInline = true;
    box.insertBefore(el, box.querySelector('.video-nametag'));

    // Add stop button overlay
    let stopBtn = box.querySelector('.screen-stop-btn');
    if (!stopBtn) {
        stopBtn = document.createElement('button');
        stopBtn.className = 'screen-stop-btn';
        stopBtn.textContent = 'Stop Sharing';
        stopBtn.style.cssText = `position:absolute;bottom:16px;left:50%;transform:translateX(-50%);
            background:rgba(239,68,68,0.9);color:#fff;border:none;border-radius:8px;
            padding:8px 20px;font-size:13px;font-weight:600;cursor:pointer;z-index:10;`;
        stopBtn.onclick = stopScreenShare;
        box.appendChild(stopBtn);
    }

    moveToMain(box, 'Your Screen', true);
}

function hideLocalScreenShare() {
    const box = document.getElementById('local-screen-box');
    if (box) box.remove();
    clearMain();
    // Restore camera box to sidebar
    const camBox = document.getElementById(`video-box-${room.localParticipant.identity}`);
    if (camBox) {
        camBox.classList.remove('main-presents');
        document.getElementById('sidebarVideoArea').appendChild(camBox);
        const v = camBox.querySelector('video');
        if (v) { v.style.objectFit = 'cover'; v.style.transform = 'scaleX(-1)'; }
    }
    updateLayout();
}

// ── Participant events ────────────────────────────────────────────────────────
function onParticipantConnected(participant) {
    console.log('Participant joined:', participant.identity);
    getOrCreateBox(participant.identity, participant.name || participant.identity, false);
    updateParticipantsList();
    updateParticipantCount();

    // Subscribe to any already-published tracks
    participant.trackPublications.forEach(pub => {
        if (pub.isSubscribed && pub.track) {
            onTrackSubscribed(pub.track, pub, participant);
        }
    });
}

function onParticipantDisconnected(participant) {
    console.log('Participant left:', participant.identity);
    const box = document.getElementById(`video-box-${participant.identity}`);
    if (box) box.remove();
    updateParticipantsList();
    updateParticipantCount();
    updateLayout();
}

function onTrackSubscribed(track, publication, participant) {
    // Never process our own tracks here — handled by renderLocalParticipant
    if (participant.identity === room.localParticipant.identity) return;

    const box = getOrCreateBox(participant.identity, participant.name || participant.identity, false);
    if (track.kind === Track.Kind.Video) {
        attachTrackToBox(track, box, false);
        if (publication.source === Track.Source.ScreenShare) {
            moveToMain(box, participant.name || participant.identity, true);
        }
    } else if (track.kind === Track.Kind.Audio) {
        track.attach(); // LiveKit appends audio element to document automatically
    }
}

function onTrackUnsubscribed(track, publication, participant) {
    const box = document.getElementById(`video-box-${participant.identity}`);
    if (box) detachTrackFromBox(track, box);

    if (publication.source === Track.Source.ScreenShare) {
        // Return box to sidebar
        document.getElementById('sidebarVideoArea').appendChild(box);
        clearMain();
        updateLayout();
    }
}

function onTrackMuted(publication, participant) {
    const box = document.getElementById(`video-box-${participant.identity}`);
    if (!box) return;
    if (publication.kind === Track.Kind.Video) box.classList.add('cam-off');
    if (publication.kind === Track.Kind.Audio) box.classList.add('muted');
}

function onTrackUnmuted(publication, participant) {
    const box = document.getElementById(`video-box-${participant.identity}`);
    if (!box) return;
    if (publication.kind === Track.Kind.Video) box.classList.remove('cam-off');
    if (publication.kind === Track.Kind.Audio) box.classList.remove('muted');
}

function onActiveSpeakersChanged(speakers) {
    // Clear all speaking indicators
    document.querySelectorAll('.video-box.speaking').forEach(b => b.classList.remove('speaking'));
    speakers.forEach(p => {
        const box = document.getElementById(`video-box-${p.identity}`);
        if (box) box.classList.add('speaking');
    });
}

function onDataReceived(payload, participant) {
    try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg.type === 'chat') {
            appendChatMessage(msg.username, msg.message, msg.userId === currentUserId);
        } else if (msg.type === 'meeting_sleeping') {
            isSleeping = true;
            showNotification('Meeting has been put to sleep by the host', 'warning');
        } else if (msg.type === 'meeting_unfrozen') {
            isSleeping = false;
            showNotification('Meeting is now active', 'success');
        }
    } catch(e) { console.warn('Data parse error:', e); }
}

function onDisconnected() {
    showNotification('Disconnected from meeting', 'error');
}

function onConnectionStateChanged(state) {
    console.log('Connection state:', state);
}

// ── Signaling Handlers ────────────────────────────────────────────────────────
function handleSignalingMessage(data) {
    switch(data.type) {
        case 'kick_user':
            if (data.user_id == currentUserId) {
                alert(data.message);
                leaveMeeting();
            } else {
                showNotification(`User kicked: ${data.user_id}`, 'info');
            }
            break;
        case 'permission_update':
            if (data.user_id == currentUserId) {
                handleLocalPermissionUpdate(data.permission_type, data.value, data.message);
            }
            break;
        case 'global_control_update':
            handleGlobalControlUpdate(data.control_type, data.value, data.message);
            break;
    }
}

async function handleLocalPermissionUpdate(type, allowed, message) {
    showNotification(message, allowed ? 'success' : 'warning');
    if (type === 'audio') {
        canSpeak = allowed;
        if (!allowed && isMicOn) toggleMic();
    } else if (type === 'video') {
        canVideo = allowed;
        if (!allowed && isCameraOn) toggleCamera();
    } else if (type === 'screenshare') {
        canShare = allowed;
        if (!allowed && isScreenSharing) stopScreenShare();
    }
}

async function handleGlobalControlUpdate(type, value, message) {
    if (isHost) return; // Host isn't affected by global student controls
    
    showNotification(message, value ? 'warning' : 'info');
    if (type === 'mute_all' && value) {
        if (isMicOn) toggleMic();
    } else if (type === 'camera_off_all' && value) {
        if (isCameraOn) toggleCamera();
    } else if (type === 'screenshare_off_all' && value) {
        if (isScreenSharing) stopScreenShare();
    }
}

// ── Layout ────────────────────────────────────────────────────────────────────
function moveToMain(box, label, isScreenShare) {
    const mainArea   = document.getElementById('mainVideoArea');
    const container  = document.getElementById('videoGridContainer');
    container.className = 'video-grid-container sidebar-view';
    box.classList.add('main-presents');
    mainArea.innerHTML = '';
    mainArea.appendChild(box);

    if (isScreenShare) {
        // Fix video to contain (not crop) for screen share
        const v = box.querySelector('video');
        if (v) { v.style.objectFit = 'contain'; v.style.transform = 'none'; }
    }
}

function clearMain() {
    const mainArea  = document.getElementById('mainVideoArea');
    const container = document.getElementById('videoGridContainer');
    mainArea.innerHTML = '';
    container.className = 'video-grid-container grid-view count-' + getAllBoxes().length;
}

function getAllBoxes() {
    return Array.from(document.querySelectorAll('.video-box'));
}

function updateLayout() {
    const boxes = getAllBoxes();
    const container = document.getElementById('videoGridContainer');
    const mainArea = document.getElementById('mainVideoArea');
    
    // Force sidebar view
    container.className = 'video-grid-container sidebar-view';
    
    // If main area is empty, pick a video to enlarge
    if (mainArea.children.length === 0 && boxes.length > 0) {
        // Prioritize remote participants over local camera
        const remoteBox = boxes.find(b => b.dataset.identity !== room.localParticipant.identity && b.dataset.identity !== 'local-screen');
        const targetBox = remoteBox || boxes[0];
        const isScreenShare = targetBox.dataset.identity === 'local-screen';
        const label = targetBox.querySelector('.video-nametag') ? targetBox.querySelector('.video-nametag').textContent : '';
        moveToMain(targetBox, label, isScreenShare);
    }
    
    updateParticipantCount();
}

// ── Controls ──────────────────────────────────────────────────────────────────
async function toggleMic() {
    if (!canSpeak && !isMicOn && !isHost) {
        showNotification('Teacher has blocked your microphone', 'error');
        return;
    }
    isMicOn = !isMicOn;
    await room.localParticipant.setMicrophoneEnabled(isMicOn);
    const btn = document.getElementById('micBtn');
    btn.classList.toggle('off', !isMicOn);
    const micOnIcon  = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>';
    const micOffIcon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>';
    btn.innerHTML = isMicOn ? micOnIcon : micOffIcon;
}

async function toggleCamera() {
    if (!canVideo && !isCameraOn && !isHost) {
        showNotification('Teacher has blocked your camera', 'error');
        return;
    }
    isCameraOn = !isCameraOn;
    await room.localParticipant.setCameraEnabled(isCameraOn);
    const btn = document.getElementById('camBtn');
    btn.classList.toggle('off', !isCameraOn);
    const camOnIcon  = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>';
    const camOffIcon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/></svg>';
    btn.innerHTML = isCameraOn ? camOnIcon : camOffIcon;

    // Force stop track to turn off physical camera light
    if (!isCameraOn) {
        room.localParticipant.videoTrackPublications.forEach(pub => {
            if (pub.source === Track.Source.Camera && pub.track && pub.track.mediaStreamTrack) {
                pub.track.mediaStreamTrack.enabled = false;
                pub.track.mediaStreamTrack.stop();
            }
        });
    }

    // Update UI
    const localBox = document.getElementById(`video-box-${room.localParticipant.identity}`);
    if (localBox) localBox.classList.toggle('cam-off', !isCameraOn);
}

async function toggleScreenShare() {
    if (!canShare && !isScreenSharing && !isHost) {
        showNotification('Teacher has blocked screen sharing', 'error');
        return;
    }
    if (!isScreenSharing) {
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
                throw new Error("Screen sharing is not supported on this browser (or you are not on HTTPS).");
            }
            const [screenTrack] = await createLocalScreenTracks({ audio: false });
            screenTrackPub = await room.localParticipant.publishTrack(screenTrack, {
                screenShareEncoding: { maxBitrate: 3_000_000, maxFramerate: 30 },
            });
            isScreenSharing = true;
            document.getElementById('screenBtn').classList.add('active');
            // Layout is handled by the localTrackPublished event → showLocalScreenShare()
            screenTrack.mediaStreamTrack.addEventListener('ended', stopScreenShare);
            showNotification('Screen sharing started', 'info');
        } catch(e) {
            console.error('Screen share error:', e);
            if (e.name !== 'NotAllowedError') showNotification('Could not share screen: ' + e.message, 'error');
        }
    } else {
        stopScreenShare();
    }
}

async function stopScreenShare() {
    if (!isScreenSharing) return;
    isScreenSharing = false;
    document.getElementById('screenBtn').classList.remove('active');
    if (screenTrackPub) {
        await room.localParticipant.unpublishTrack(screenTrackPub.track);
        screenTrackPub.track.stop();
        screenTrackPub = null;
    }
    // Layout cleanup handled by localTrackUnpublished → hideLocalScreenShare()
    showNotification('Screen sharing stopped', 'info');
}

// ── Chat ──────────────────────────────────────────────────────────────────────
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const text  = input.value.trim();
    if (!text || !room) return;
    input.value = '';

    const payload = JSON.stringify({ type: 'chat', username: currentUsername, userId: currentUserId, message: text });
    await room.localParticipant.publishData(new TextEncoder().encode(payload), { reliable: true });
    appendChatMessage(currentUsername, text, true);
}

function appendChatMessage(username, text, isOwn) {
    const panel = document.getElementById('chatMessages');
    const div   = document.createElement('div');
    div.className = 'chat-msg' + (isOwn ? ' own' : '');
    div.innerHTML = `
        <div class="chat-msg-header"><strong>${username}</strong><span class="chat-msg-time">${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span></div>
        <div class="chat-msg-text">${text}</div>`;
    panel.appendChild(div);
    panel.scrollTop = panel.scrollHeight;

    if (!isOwn && document.getElementById('chatPanel').style.display === 'none') {
        unreadMessages++;
        const badge = document.getElementById('chatBadge');
        badge.textContent = unreadMessages;
        badge.style.display = 'block';
    }
}

// ── Sleep mode (host only) ────────────────────────────────────────────────────
async function toggleSleepMode() {
    const url = isSleeping ? UNFREEZE_URL : SLEEP_URL;
    await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': CSRF } });

    // Broadcast to all via data channel
    const type = isSleeping ? 'meeting_unfrozen' : 'meeting_sleeping';
    const payload = JSON.stringify({ type });
    await room.localParticipant.publishData(new TextEncoder().encode(payload), { reliable: true });

    isSleeping = !isSleeping;
    const btn = document.getElementById('sleepBtn');
    if (btn) btn.classList.toggle('active', isSleeping);
}

// ── Teacher Controls ──────────────────────────────────────────────────────────
async function toggleGlobalControl(type) {
    const btn = type === 'mute_all' ? document.getElementById('muteAllBtn') : document.getElementById('camOffAllBtn');
    const currentState = btn.classList.contains('active');
    const newState = !currentState;
    
    const res = await fetch(_d.globalControlUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, value: newState })
    });
    
    if (res.ok) {
        btn.classList.toggle('active', newState);
        showNotification(`Global ${type.replace('_', ' ')} ${newState ? 'Enabled' : 'Disabled'}`, 'success');
    }
}

async function kickUser(userId) {
    if (!confirm('Are you sure you want to kick this student for 1 hour?')) return;
    
    const url = _d.kickUrl.replace('0', userId);
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF }
    });
    
    if (res.ok) showNotification('Student kicked successfully', 'success');
}

async function updatePermission(userId, type, value) {
    const url = _d.permissionUrl.replace('0', userId);
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF, 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, value })
    });
    
    if (res.ok) {
        showNotification(`Permission updated for student`, 'success');
        updateParticipantsList();
    }
}

async function unbanUser(userId) {
    const url = _d.revokeBanUrl.replace('0', userId);
    const res = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF }
    });
    
    if (res.ok) {
        showNotification('Student unbanned successfully', 'success');
        fetchBannedUsers();
    }
}

async function fetchBannedUsers() {
    if (!isHost) return;
    const res = await fetch(_d.bannedUsersUrl);
    const data = await res.json();
    const list = document.getElementById('bannedList');
    if (!list) return;
    
    list.innerHTML = '';
    if (data.banned && data.banned.length > 0) {
        data.banned.forEach(u => {
            const item = document.createElement('div');
            item.className = 'participant-item';
            item.innerHTML = `
                <div class="participant-avatar"><img src="https://ui-avatars.com/api/?name=${u.username}&background=ef4444&color=fff" alt="${u.username}"></div>
                <div class="participant-info">
                    <div class="participant-name">${u.username}</div>
                    <div style="font-size:10px; color:#ef4444;">Banned until ${new Date(u.banned_until).toLocaleTimeString()}</div>
                </div>
                <div class="participant-actions">
                    <button class="action-btn" onclick="unbanUser('${u.id}')" title="Unban Student">✅</button>
                </div>`;
            list.appendChild(item);
        });
    } else {
        list.innerHTML = '<p style="text-align:center; color:#999; font-size:12px; padding:10px;">No banned students</p>';
    }
}

// ── Leave ─────────────────────────────────────────────────────────────────────
async function leaveMeeting() {
    if (room) await room.disconnect();
    await fetch(LEAVE_URL, { method: 'POST', headers: { 'X-CSRFToken': CSRF } });
    window.location.href = AFTER_LEAVE;
}

// ── Sidebar helpers ───────────────────────────────────────────────────────────
function openSidebar(tab) {
    document.getElementById('meetSidebar').style.display = 'flex';
    document.getElementById('meetMain').classList.add('sidebar-open');
    switchSidebarTab(tab);
}

function toggleSidebar() {
    const s = document.getElementById('meetSidebar');
    const isOpen = s.style.display !== 'none';
    s.style.display = isOpen ? 'none' : 'flex';
    document.getElementById('meetMain').classList.toggle('sidebar-open', !isOpen);
}

function switchSidebarTab(tab) {
    document.querySelectorAll('.sidebar-tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.sidebar-panel').forEach(p => p.style.display = 'none');
    document.querySelector(`.sidebar-tab[onclick*="${tab}"]`).classList.add('active');
    document.getElementById(tab + 'Panel').style.display = 'flex';

    if (tab === 'chat') {
        unreadMessages = 0;
        const badge = document.getElementById('chatBadge');
        badge.style.display = 'none';
    }
}

// ── Participants list ─────────────────────────────────────────────────────────
function updateParticipantsList() {
    const list = document.getElementById('participantsList');
    list.innerHTML = `
        <div class="participant-item">
            <div class="participant-avatar"><img src="https://ui-avatars.com/api/?name=${currentUsername}&background=1877f2&color=fff" alt="${currentUsername}"></div>
            <div class="participant-info">
                <div class="participant-name">${currentUsername} (You)</div>
                ${isHost ? '<span class="host-label">Host</span>' : ''}
            </div>
        </div>`;

    if (room) {
        room.remoteParticipants.forEach(p => {
            const item = document.createElement('div');
            item.className = 'participant-item';
            item.innerHTML = `
                <div class="participant-avatar"><img src="https://ui-avatars.com/api/?name=${p.name||p.identity}&background=6366f1&color=fff" alt="${p.name||p.identity}"></div>
                <div class="participant-info">
                    <div class="participant-name">${p.name || p.identity}</div>
                </div>
                ${isHost ? `
                <div class="participant-actions">
                    <button class="action-btn" onclick="updatePermission('${p.identity}', 'audio', true)" title="Allow Mic">🎤</button>
                    <button class="action-btn" onclick="updatePermission('${p.identity}', 'video', true)" title="Allow Cam">📷</button>
                    <button class="action-btn danger" onclick="kickUser('${p.identity}')" title="Kick Out">🚫</button>
                </div>
                ` : ''}`;
            list.appendChild(item);
        });
    }
    
    if (isHost) fetchBannedUsers();
}

function updateParticipantCount() {
    const count = room ? room.remoteParticipants.size + 1 : 1;
    document.getElementById('participantCount').textContent = count;
}

// ── Timer ─────────────────────────────────────────────────────────────────────
function startTimer() {
    timerInterval = setInterval(() => {
        timerSeconds++;
        const m = String(Math.floor(timerSeconds / 60)).padStart(2, '0');
        const s = String(timerSeconds % 60).padStart(2, '0');
        document.getElementById('meetTimer').textContent = `${m}:${s}`;
    }, 1000);
}

// ── Notification ──────────────────────────────────────────────────────────────
function showNotification(msg, type = 'info') {
    const colors = { info: '#6366f1', success: '#10b981', warning: '#f59e0b', error: '#ef4444' };
    const n = document.createElement('div');
    n.style.cssText = `position:fixed;bottom:100px;left:50%;transform:translateX(-50%);
        background:${colors[type]};color:#fff;padding:10px 20px;border-radius:8px;
        font-size:13px;font-weight:600;z-index:9999;pointer-events:none;
        box-shadow:0 4px 16px rgba(0,0,0,0.3);`;
    n.textContent = msg;
    document.body.appendChild(n);
    setTimeout(() => n.remove(), 3000);
}

// ── Start ─────────────────────────────────────────────────────────────────────
window.addEventListener('beforeunload', () => { if (room) room.disconnect(); });
init().catch(e => { console.error('Init error:', e); showNotification('Failed to connect: ' + e.message, 'error'); });

// ── Face Attendance Module (Students Only) ───────────────────────────────────

(function() {
    let attWs = null;
    let captureTimer = null;
    let marked = false;

    // Create Badge UI
    const badge = document.createElement('div');
    badge.id = 'face-att-badge';
    badge.className = 'state-active';
    badge.innerHTML = `
        <div class="fa-dot"></div>
        <div style="flex:1">
            <div id="face-att-text">Initializing Face Recognition...</div>
            <div id="face-att-prog-wrap" style="display:none">
                <div id="face-att-progress-bar"><div id="face-att-progress-fill"></div></div>
            </div>
        </div>
    `;
    document.body.appendChild(badge);

    const badgeText = badge.querySelector('#face-att-text');
    const progWrap  = badge.querySelector('#face-att-prog-wrap');
    const progFill  = badge.querySelector('#face-att-progress-fill');

    function connect() {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        attWs = new WebSocket(`${proto}//${window.location.host}/ws/attendance/${meetingCode}/`);
        attWs.onmessage = e => {
            const data = JSON.parse(e.data);
            switch(data.type) {
                case 'connected':
                    if (data.has_profile) {
                        badgeText.textContent = 'Face Recognition Active';
                        startCapture(data.interval * 1000);
                    } else {
                        badge.className = 'state-warning';
                        badgeText.innerHTML = 'No profile found. <a href="/attendance/face/setup/" style="color:#f87171">Register Now</a>';
                    }
                    break;
                case 'verification_progress':
                    const pct = Math.round((data.verified_seconds / data.required_seconds) * 100);
                    badge.className = 'state-progress';
                    badgeText.textContent = `Verifying... ${pct}%`;
                    progWrap.style.display = 'block';
                    progFill.style.width = pct + '%';
                    break;
                case 'attendance_marked':
                    marked = true;
                    badge.className = 'state-success';
                    badgeText.textContent = 'Attendance Recorded!';
                    progWrap.style.display = 'none';
                    stopCapture();
                    setTimeout(() => badge.style.opacity = '0', 5000);
                    break;
                case 'verification_failed':
                    badge.className = 'state-warning';
                    badgeText.textContent = data.message || 'Face Not Recognized';
                    break;
            }
        };
        attWs.onclose = () => !marked && setTimeout(connect, 5000);
    }

    function captureAndSend() {
        const video = document.getElementById('localVideo');
        if (!video || video.readyState < 2 || !attWs || attWs.readyState !== 1) return;
        const canvas = document.createElement('canvas');
        canvas.width = 320; canvas.height = 240;
        const ctx = canvas.getContext('2d');
        ctx.save(); ctx.scale(-1, 1); ctx.drawImage(video, -320, 0, 320, 240); ctx.restore();
        attWs.send(JSON.stringify({ type: 'frame', frame: canvas.toDataURL('image/jpeg', 0.8).split(',')[1] }));
    }

    function startCapture(ms) {
        if (captureTimer) clearInterval(captureTimer);
        captureTimer = setInterval(captureAndSend, ms || 15000);
        setTimeout(captureAndSend, 2000);
    }

    function stopCapture() { clearInterval(captureTimer); captureTimer = null; }

    window.addEventListener('load', () => setTimeout(connect, 3000));
})();


// ── Face Tracking Module (Host Only) ─────────────────────────────────────────

(function() {
    let ftWs = null;
    let ftEnabled = false;
    let ftTimer = null;
    const ftCanvas = document.createElement('canvas');

    window.toggleFaceTracking = function() {
        ftEnabled = !ftEnabled;
        const btn = document.getElementById('ftToggleBtn');
        btn.classList.toggle('active', ftEnabled);
        if (ftEnabled) {
            btn.style.background = '#10b981';
            connect();
            showNotification('Face Tracking Enabled', 'success');
        } else {
            btn.style.background = '';
            stop();
            showNotification('Face Tracking Disabled', 'info');
        }
    };

    function connect() {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ftWs = new WebSocket(`${proto}//${window.location.host}/ws/face-tracking/${meetingCode}/`);
        ftWs.onopen = () => { ftTimer = setInterval(captureAll, 5000); captureAll(); };
        ftWs.onmessage = e => {
            const data = JSON.parse(e.data);
            if (data.type === 'bulk_tracking_result') {
                Object.entries(data.results).forEach(([uid, res]) => drawOverlay(uid, res));
            }
        };
        ftWs.onclose = () => ftEnabled && setTimeout(connect, 5000);
    }

    function stop() {
        clearInterval(ftTimer); ftTimer = null;
        if (ftWs) ftWs.close();
        document.querySelectorAll('.ft-canvas-overlay, .ft-emotion-badge').forEach(el => el.remove());
    }

    function captureAll() {
        if (!ftWs || ftWs.readyState !== 1) return;
        const frames = {};
        document.querySelectorAll('.video-box').forEach(box => {
            const uid = box.dataset.userId;
            if (!uid || uid === currentUserId) return;
            const video = box.querySelector('video');
            if (!video || video.readyState < 2) return;
            ftCanvas.width = 320; ftCanvas.height = 240;
            ftCanvas.getContext('2d').drawImage(video, 0, 0, 320, 240);
            frames[uid] = ftCanvas.toDataURL('image/jpeg', 0.7).split(',')[1];
        });
        if (Object.keys(frames).length > 0) ftWs.send(JSON.stringify({ type: 'bulk_frame', frames }));
    }

    function drawOverlay(uid, res) {
        const box = document.getElementById(`video-box-${uid}`);
        if (!box) return;
        let canvas = box.querySelector('.ft-canvas-overlay');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.className = 'ft-canvas-overlay';
            box.appendChild(canvas);
        }
        canvas.width = box.offsetWidth; canvas.height = box.offsetHeight;
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (res.face_visible && res.faces) {
            res.faces.forEach(face => {
                const { x, y, w, h } = face.box;
                ctx.strokeStyle = '#10b981'; ctx.lineWidth = 2;
                ctx.strokeRect(x * canvas.width, y * canvas.height, w * canvas.width, h * canvas.height);
                ctx.fillStyle = '#10b981'; ctx.font = 'bold 12px Inter';
                ctx.fillText(face.name, x * canvas.width, y * canvas.height - 5);
            });
            updateEmotion(box, res.emotion_label);
        } else {
            updateEmotion(box, null);
        }
    }

    function updateEmotion(box, label) {
        let eb = box.querySelector('.ft-emotion-badge');
        if (!label) { eb?.remove(); return; }
        if (!eb) { eb = document.createElement('div'); eb.className = 'ft-emotion-badge'; box.appendChild(eb); }
        eb.textContent = label;
    }
})();

