'use strict';

const os = require('os');

module.exports = {
    port:       parseInt(process.env.SFU_PORT || '3000', 10),
    secret:     process.env.SFU_SECRET || 'change-me-in-production',
    numWorkers: parseInt(process.env.NUM_WORKERS || '') || Math.max(1, os.cpus().length),

    worker: {
        rtcMinPort: parseInt(process.env.RTC_MIN_PORT || '40000', 10),
        rtcMaxPort: parseInt(process.env.RTC_MAX_PORT || '40200', 10),
        logLevel:   'warn',
        logTags:    ['info', 'ice', 'dtls', 'rtp', 'srtp', 'rtcp'],
    },

    router: {
        mediaCodecs: [
            {
                kind:      'audio',
                mimeType:  'audio/opus',
                clockRate: 48000,
                channels:  2,
                parameters: {
                    minptime:       10,
                    useinbandfec:   1,
                    usedtx:         1,
                    maxplaybackrate: 48000,
                    'sprop-stereo': 1,
                },
            },
            {
                // VP8 — supports simulcast, widest browser support
                kind:      'video',
                mimeType:  'video/VP8',
                clockRate: 90000,
                parameters: {
                    'x-google-start-bitrate': 1000,
                },
            },
            {
                // H264 — hardware accelerated on most devices, supports simulcast
                kind:      'video',
                mimeType:  'video/h264',
                clockRate: 90000,
                parameters: {
                    'packetization-mode':      1,
                    'profile-level-id':        '42e032',
                    'level-asymmetry-allowed': 1,
                    'x-google-start-bitrate':  1000,
                },
            },
        ],
    },

    webRtcTransport: {
        listenIps: [
            {
                ip:          '0.0.0.0',
                announcedIp: process.env.ANNOUNCED_IP || '127.0.0.1',
            },
        ],
        enableUdp:  true,
        enableTcp:  true,
        preferUdp:  true,

        // High initial bitrate — ramps up fast instead of starting blurry
        initialAvailableOutgoingBitrate: 5_000_000,   // 5 Mbps start
        minimumAvailableOutgoingBitrate:   600_000,   // 600 kbps floor

        // Allow full 1080p60 + overhead
        maxIncomingBitrate: 8_000_000,   // 8 Mbps per sender

        maxSctpMessageSize: 262144,
    },
};
