/**
 * EduMi SFU Client — mediasoup-client + Socket.IO
 * Optimised for full HD video, stereo audio, low latency.
 */

'use strict';

const SFU_URL = window.SFU_URL || window.location.origin;

// ─── Media constraints ────────────────────────────────────────────────────────

// Desktop: full 1080p60
const VIDEO_CONSTRAINTS_DESKTOP = {
    width:      { ideal: 1920, min: 1280 },
    height:     { ideal: 1080, min: 720  },
    frameRate:  { ideal: 60,   min: 30   },
    facingMode: 'user',
};

// Mobile: 720p30 — balanced quality vs battery
const VIDEO_CONSTRAINTS_MOBILE = {
    width:      { ideal: 1280, min: 640 },
    height:     { ideal: 720,  min: 480 },
    frameRate:  { ideal: 30,   min: 15  },
    facingMode: 'user',
};

// High-quality stereo audio
const AUDIO_CONSTRAINTS = {
    echoCancellation:    true,
    noiseSuppression:    true,
    autoGainControl:     true,
    channelCount:        2,       // stereo
    sampleRate:          48000,
    sampleSize:          16,
    latency:             0.01,    // 10 ms target
};

const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

// ─── Simulcast layers ─────────────────────────────────────────────────────────
// Three layers: thumbnail → HD → Full HD
// SFU picks the right layer per receiver based on bandwidth.
const VIDEO_ENCODINGS = [
    { rid: 'r0', maxBitrate: 300000, scaleResolutionDownBy: 4 },
    { rid: 'r1', maxBitrate: 1000000, scaleResolutionDownBy: 2 },
    { rid: 'r2', maxBitrate: 3000000, scaleResolutionDownBy: 1 },
];

const VIDEO_ENCODINGS_MOBILE = [
    { rid: 'r0', maxBitrate: 200000, scaleResolutionDownBy: 4 },
    { rid: 'r1', maxBitrate: 600000, scaleResolutionDownBy: 2 },
    { rid: 'r2', maxBitrate: 1500000, scaleResolutionDownBy: 1 },
];

// Screen share: single high-bitrate layer — crisp text matters more than motion
const SCREEN_ENCODINGS = [
    { maxBitrate: 5000000, scaleResolutionDownBy: 1 },
];

// ─── State ────────────────────────────────────────────────────────────────────

let socket         = null;
let device         = null;
let sendTransport  = null;
let recvTransport  = null;
let audioProducer  = null;
let videoProducer  = null;
let screenProducer = null;

const consumers   = new Map();  // consumerId → { consumer, peerId, displayName, kind, appData }
const remotePeers = new Map();  // peerId     → { displayName, audioConsumerId, videoConsumerId }

let localStream    = null;
let screenStream   = null;
let isMicOn        = true;
let isCameraOn     = true;
let isScreenSharing = false;

const _cb = {
    onLocalStream:        null,
    onRemoteStream:       null,
    onRemoteStreamClosed: null,
    onPeerJoined:         null,
    onPeerLeft:           null,
    onProducerPaused:     null,
    onProducerResumed:    null,
    onConnected:          null,
    onDisconnected:       null,
    onError:              null,
};

// ─── Public API ───────────────────────────────────────────────────────────────

const SFUClient = {

    on(event, fn) { _cb[event] = fn; return this; },

    async join(roomId, peerId, displayName) {
        await _acquireMedia();

        socket = io(SFU_URL, {
            transports:           ['websocket'],   // websocket-only — no polling overhead
            reconnection:         true,
            reconnectionDelay:    500,
            reconnectionAttempts: 20,
            timeout:              8000,
        });

        await new Promise((resolve, reject) => {
            socket.on('connect',       resolve);
            socket.on('connect_error', reject);
            setTimeout(() => reject(new Error('SFU connection timeout')), 10000);
        });

        const { rtpCapabilities, existingProducers, error } = await _emit('join', { roomId, peerId, displayName });
        if (error) throw new Error(`join failed: ${error}`);

        device = new mediasoupClient.Device();
        await device.load({ routerRtpCapabilities: rtpCapabilities });

        // Create both transports in parallel — saves ~100 ms
        await Promise.all([_createSendTransport(), _createRecvTransport()]);

        await _produceLocalTracks();

        // Consume all existing producers in parallel
        await Promise.all(existingProducers.map(p => _consumeProducer(p)));

        _registerServerEvents();
        _cb.onConnected?.();
    },

    async toggleMic() {
        if (!audioProducer) return isMicOn;
        isMicOn = !isMicOn;
        if (isMicOn) {
            await audioProducer.resume();
            _emit('resumeProducer', { producerId: audioProducer.id });
        } else {
            await audioProducer.pause();
            _emit('pauseProducer', { producerId: audioProducer.id });
        }
        localStream?.getAudioTracks().forEach(t => { t.enabled = isMicOn; });
        return isMicOn;
    },

    async toggleCamera() {
        if (!videoProducer) return isCameraOn;
        isCameraOn = !isCameraOn;
        if (isCameraOn) {
            await videoProducer.resume();
            _emit('resumeProducer', { producerId: videoProducer.id });
        } else {
            await videoProducer.pause();
            _emit('pauseProducer', { producerId: videoProducer.id });
        }
        localStream?.getVideoTracks().forEach(t => { t.enabled = isCameraOn; });
        return isCameraOn;
    },

    async startScreenShare() {
        if (isScreenSharing) return;
        screenStream = await navigator.mediaDevices.getDisplayMedia({
            video: {
                width:     { ideal: 1920 },
                height:    { ideal: 1080 },
                frameRate: { ideal: 30   },
                cursor:    'always',
            },
            audio: false,
        });

        const track = screenStream.getVideoTracks()[0];
        track.contentHint = 'detail';   // hint browser: optimise for text/detail not motion

        screenProducer = await sendTransport.produce({
            track,
            encodings:    SCREEN_ENCODINGS,
            codecOptions: { videoGoogleStartBitrate: 4000 },
            appData:      { source: 'screen' },
        });

        isScreenSharing = true;
        track.onended = () => this.stopScreenShare();
        return screenProducer.id;
    },

    async stopScreenShare() {
        if (!isScreenSharing || !screenProducer) return;
        _emit('closeProducer', { producerId: screenProducer.id });
        screenProducer.close();
        screenProducer = null;
        screenStream?.getTracks().forEach(t => t.stop());
        screenStream   = null;
        isScreenSharing = false;
    },

    leave() {
        audioProducer?.close();
        videoProducer?.close();
        screenProducer?.close();
        for (const { consumer } of consumers.values()) consumer.close();
        consumers.clear();
        remotePeers.clear();
        sendTransport?.close();
        recvTransport?.close();
        localStream?.getTracks().forEach(t => t.stop());
        screenStream?.getTracks().forEach(t => t.stop());
        socket?.disconnect();
        socket = device = sendTransport = recvTransport = null;
        audioProducer = videoProducer = screenProducer = null;
        localStream = screenStream = null;
        isMicOn = isCameraOn = true;
        isScreenSharing = false;
    },

    get localStream()     { return localStream; },
    get isMicOn()         { return isMicOn; },
    get isCameraOn()      { return isCameraOn; },
    get isScreenSharing() { return isScreenSharing; },
    get remotePeers()     { return remotePeers; },
};

// ─── Internals ────────────────────────────────────────────────────────────────

function _emit(event, data = {}) {
    return new Promise(resolve => socket.emit(event, data, resolve));
}

async function _acquireMedia() {
    const videoConstraints = isMobile ? VIDEO_CONSTRAINTS_MOBILE : VIDEO_CONSTRAINTS_DESKTOP;

    try {
        localStream = await navigator.mediaDevices.getUserMedia({
            video: videoConstraints,
            audio: AUDIO_CONSTRAINTS,
        });
        _cb.onLocalStream?.(localStream);
        return;
    } catch (_) {}

    // Fallback: try each track independently
    let vStream = null, aStream = null;
    try { vStream = await navigator.mediaDevices.getUserMedia({ video: videoConstraints }); } catch (_) {}
    try { aStream = await navigator.mediaDevices.getUserMedia({ audio: AUDIO_CONSTRAINTS }); } catch (_) {}

    if (vStream || aStream) {
        localStream = new MediaStream([
            ...(vStream ? vStream.getVideoTracks() : []),
            ...(aStream ? aStream.getAudioTracks() : []),
        ]);
        if (!vStream) isCameraOn = false;
        if (!aStream) isMicOn    = false;
        _cb.onLocalStream?.(localStream);
        return;
    }

    // No media at all — silent canvas placeholder
    localStream = _placeholder();
    isCameraOn  = false;
    isMicOn     = false;
    _cb.onLocalStream?.(localStream);
}

function _placeholder() {
    const c = document.createElement('canvas');
    c.width = 1280; c.height = 720;
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#111827';
    ctx.fillRect(0, 0, c.width, c.height);
    const s = c.captureStream(1);
    try {
        const ac  = new AudioContext();
        const dst = ac.createMediaStreamDestination();
        s.addTrack(dst.stream.getAudioTracks()[0]);
    } catch (_) {}
    return s;
}

async function _createSendTransport() {
    const params = await _emit('createTransport', { direction: 'send' });
    if (params.error) throw new Error(params.error);

    sendTransport = device.createSendTransport(params);

    sendTransport.on('connect', async ({ dtlsParameters }, cb, eb) => {
        try { await _emit('connectTransport', { transportId: sendTransport.id, dtlsParameters }); cb(); }
        catch (e) { eb(e); }
    });

    sendTransport.on('produce', async ({ kind, rtpParameters, appData }, cb, eb) => {
        try {
            const { id, error } = await _emit('produce', { kind, rtpParameters, appData });
            if (error) throw new Error(error);
            cb({ id });
        } catch (e) { eb(e); }
    });

    sendTransport.on('connectionstatechange', state => {
        if (state === 'failed') sendTransport.restartIce();
    });
}

async function _createRecvTransport() {
    const params = await _emit('createTransport', { direction: 'recv' });
    if (params.error) throw new Error(params.error);

    recvTransport = device.createRecvTransport(params);

    recvTransport.on('connect', async ({ dtlsParameters }, cb, eb) => {
        try { await _emit('connectTransport', { transportId: recvTransport.id, dtlsParameters }); cb(); }
        catch (e) { eb(e); }
    });

    recvTransport.on('connectionstatechange', state => {
        if (state === 'failed') recvTransport.restartIce();
    });
}

async function _produceLocalTracks() {
    const audioTrack = localStream?.getAudioTracks()[0];
    if (audioTrack) {
        audioTrack.contentHint = 'speech';
        audioProducer = await sendTransport.produce({
            track: audioTrack,
            codecOptions: {
                opusStereo:      true,   // stereo audio
                opusDtx:         true,   // silence suppression — saves bandwidth
                opusFec:         true,   // forward error correction — reduces glitches
                opusNack:        true,   // retransmission
                opusMaxPlaybackRate: 48000,
            },
            appData: { source: 'mic' },
        });
        if (!isMicOn) await audioProducer.pause();
    }

    const videoTrack = localStream?.getVideoTracks()[0];
    if (videoTrack) {
        videoTrack.contentHint = 'motion';
        const encodings = isMobile ? VIDEO_ENCODINGS_MOBILE : VIDEO_ENCODINGS;
        videoProducer = await sendTransport.produce({
            track: videoTrack,
            encodings,
            codecOptions: {
                videoGoogleStartBitrate:  2000,   // start at 2 Mbps — ramps up fast
                videoGoogleMinBitrate:     500,
                videoGoogleMaxBitrate:    8000,
            },
            appData: { source: 'camera' },
        });
        if (!isCameraOn) await videoProducer.pause();
    }
}

async function _consumeProducer({ producerId, peerId, displayName, kind, appData }) {
    const params = await _emit('consume', {
        producerId,
        rtpCapabilities: device.rtpCapabilities,
    });

    if (params.error) { console.warn('[SFU] consume error:', params.error); return; }

    const consumer = await recvTransport.consume({
        id:            params.id,
        producerId:    params.producerId,
        kind:          params.kind,
        rtpParameters: params.rtpParameters,
    });

    consumers.set(consumer.id, { consumer, peerId, displayName, kind: consumer.kind, appData });

    if (!remotePeers.has(peerId)) {
        remotePeers.set(peerId, { displayName, audioConsumerId: null, videoConsumerId: null });
    }
    const info = remotePeers.get(peerId);
    if (consumer.kind === 'audio') info.audioConsumerId = consumer.id;
    else                           info.videoConsumerId = consumer.id;

    // Content hints for browser decoder optimisation
    if (consumer.kind === 'video') consumer.track.contentHint = appData?.source === 'screen' ? 'detail' : 'motion';
    if (consumer.kind === 'audio') consumer.track.contentHint = 'speech';

    _cb.onRemoteStream?.(peerId, displayName, new MediaStream([consumer.track]), consumer.kind, appData);

    // Resume — server starts consumers paused
    await _emit('resumeConsumer', { consumerId: consumer.id });
}

function _registerServerEvents() {
    socket.on('peerJoined', ({ peerId, displayName }) => {
        _cb.onPeerJoined?.(peerId, displayName);
    });

    socket.on('peerLeft', ({ peerId, displayName }) => {
        remotePeers.delete(peerId);
        _cb.onPeerLeft?.(peerId, displayName);
    });

    socket.on('newProducer', async data => {
        await _consumeProducer(data);
    });

    socket.on('producerPaused', ({ producerId, peerId }) => {
        const e = _byProducerId(producerId);
        if (e) _cb.onProducerPaused?.(peerId, e.kind);
    });

    socket.on('producerResumed', ({ producerId, peerId }) => {
        const e = _byProducerId(producerId);
        if (e) _cb.onProducerResumed?.(peerId, e.kind);
    });

    socket.on('producerClosed', ({ producerId, peerId }) => {
        const e = _byProducerId(producerId);
        if (e) {
            e.consumer.close();
            consumers.delete(e.consumer.id);
            _cb.onRemoteStreamClosed?.(peerId, e.kind);
        }
    });

    socket.on('consumerClosed', ({ consumerId }) => {
        const e = consumers.get(consumerId);
        if (e) {
            e.consumer.close();
            consumers.delete(consumerId);
            _cb.onRemoteStreamClosed?.(e.peerId, e.kind);
        }
    });

    socket.on('disconnect', reason => {
        _cb.onDisconnected?.();
    });
}

function _byProducerId(producerId) {
    for (const e of consumers.values()) {
        if (e.consumer.producerId === producerId) return e;
    }
    return null;
}

window.SFUClient = SFUClient;
