'use strict';

/**
 * Room — one mediasoup Router per meeting room.
 *
 * Lifecycle:
 *   - Created when first peer joins a meeting
 *   - Destroyed when last peer leaves (after a grace period)
 *
 * Each peer has:
 *   - One send transport  (browser → SFU)
 *   - One recv transport  (SFU → browser)
 *   - One producer per track (audio + video)
 *   - One consumer per remote producer
 */

const config = require('./config');

const CLOSE_TIMEOUT_MS = 10_000; // destroy room 10 s after last peer leaves

class Room {
    /**
     * @param {string} roomId  — meeting code
     * @param {import('mediasoup').types.Router} router
     */
    constructor(roomId, router) {
        this.id      = roomId;
        this._router = router;
        this._peers  = new Map(); // peerId → Peer
        this._closeTimer = null;
    }

    // ── Static factory ────────────────────────────────────────────────────────

    static async create(roomId, worker) {
        const router = await worker.createRouter({ mediaCodecs: config.router.mediaCodecs });
        console.log(`[Room ${roomId}] created on worker ${worker.pid}`);
        return new Room(roomId, router);
    }

    // ── Peer management ───────────────────────────────────────────────────────

    hasPeer(peerId) {
        return this._peers.has(peerId);
    }

    getPeer(peerId) {
        return this._peers.get(peerId);
    }

    addPeer(peer) {
        this._peers.set(peer.id, peer);
        if (this._closeTimer) {
            clearTimeout(this._closeTimer);
            this._closeTimer = null;
        }
    }

    removePeer(peerId) {
        const peer = this._peers.get(peerId);
        if (peer) {
            peer.close();
            this._peers.delete(peerId);
        }

        if (this._peers.size === 0) {
            this._closeTimer = setTimeout(() => {
                console.log(`[Room ${this.id}] empty — closing`);
                this._router.close();
            }, CLOSE_TIMEOUT_MS);
        }
    }

    getPeers() {
        return Array.from(this._peers.values());
    }

    get peerCount() {
        return this._peers.size;
    }

    // ── Transport / Producer / Consumer creation ──────────────────────────────

    async createWebRtcTransport() {
        const transport = await this._router.createWebRtcTransport(
            config.webRtcTransport
        );

        // Enforce max incoming bitrate
        if (config.webRtcTransport.maxIncomingBitrate) {
            try {
                await transport.setMaxIncomingBitrate(
                    config.webRtcTransport.maxIncomingBitrate
                );
            } catch (_) {}
        }

        return transport;
    }

    /** Returns RTP capabilities of this router (sent to clients for device loading) */
    get rtpCapabilities() {
        return this._router.rtpCapabilities;
    }

    /** Check if the router can consume a given producer */
    canConsume({ producerId, rtpCapabilities }) {
        return this._router.canConsume({ producerId, rtpCapabilities });
    }

    /** Pipe a producer to a consumer transport */
    async createConsumer({ consumerTransport, producerId, rtpCapabilities }) {
        if (!this._router.canConsume({ producerId, rtpCapabilities })) {
            throw new Error(`Cannot consume producer ${producerId}`);
        }

        const consumer = await consumerTransport.consume({
            producerId,
            rtpCapabilities,
            paused: true, // start paused — client resumes after recv transport connected
        });

        return consumer;
    }

    close() {
        if (this._closeTimer) clearTimeout(this._closeTimer);
        for (const peer of this._peers.values()) peer.close();
        this._peers.clear();
        if (!this._router.closed) this._router.close();
    }
}

module.exports = Room;
