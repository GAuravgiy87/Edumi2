'use strict';

require('dotenv').config();

const express    = require('express');
const http       = require('http');
const { Server } = require('socket.io');
const cors       = require('cors');

const config     = require('./config');
const workerPool = require('./WorkerPool');
const Room       = require('./Room');
const Peer       = require('./Peer');

// ── App setup ─────────────────────────────────────────────────────────────────

const app    = express();
const server = http.createServer(app);

app.use(cors({ origin: '*' }));
app.use(express.json());

// Health check — used by Docker and Django to verify SFU is up
app.get('/health', (_req, res) => res.json({ status: 'ok', rooms: rooms.size }));

// ── State ─────────────────────────────────────────────────────────────────────

/** @type {Map<string, Room>} roomId → Room */
const rooms = new Map();

// ── Socket.IO ─────────────────────────────────────────────────────────────────

const io = new Server(server, {
    cors:       { origin: '*', methods: ['GET', 'POST'] },
    transports: ['websocket', 'polling'],
    // Tight ping — detect dead connections fast, don't hold stale state
    pingTimeout:  8000,
    pingInterval: 5000,
    // Larger buffer for video signaling payloads
    maxHttpBufferSize: 1e7,
});

// ── Helpers ───────────────────────────────────────────────────────────────────

async function getOrCreateRoom(roomId) {
    if (!rooms.has(roomId)) {
        const worker = workerPool.next();
        const room   = await Room.create(roomId, worker);
        rooms.set(roomId, room);
        room._router.on('workerclose', () => {
            console.warn(`[Room ${roomId}] worker closed — removing room`);
            rooms.delete(roomId);
        });
    }
    return rooms.get(roomId);
}

// ── Socket.IO connection handler ──────────────────────────────────────────────

io.on('connection', (socket) => {
    console.log(`[Socket] connected: ${socket.id}`);

    let currentRoom = null;
    let currentPeer = null;

    // ── join ──────────────────────────────────────────────────────────────────
    socket.on('join', async ({ roomId, peerId, displayName }, callback) => {
        try {
            const room = await getOrCreateRoom(roomId);
            currentRoom = room;

            // Remove stale peer if reconnecting
            if (room.hasPeer(peerId)) room.removePeer(peerId);

            const peer = new Peer(peerId, displayName, socket);
            room.addPeer(peer);
            currentPeer = peer;

            socket.join(roomId);

            // Tell the joining peer about existing producers
            const existingProducers = [];
            for (const p of room.getPeers()) {
                if (p.id === peerId) continue;
                for (const producer of p.producers.values()) {
                    existingProducers.push({
                        producerId:  producer.id,
                        peerId:      p.id,
                        displayName: p.displayName,
                        kind:        producer.kind,
                        appData:     producer.appData,
                    });
                }
            }

            // Notify existing peers about the new joiner
            socket.to(roomId).emit('peerJoined', {
                peerId,
                displayName,
            });

            callback({
                rtpCapabilities:   room.rtpCapabilities,
                existingProducers,
            });

            console.log(`[Room ${roomId}] peer ${displayName} (${peerId}) joined — ${room.peerCount} peers`);
        } catch (err) {
            console.error('[join] error:', err);
            callback({ error: err.message });
        }
    });

    // ── createTransport ───────────────────────────────────────────────────────
    socket.on('createTransport', async ({ direction }, callback) => {
        try {
            if (!currentRoom || !currentPeer) throw new Error('Not in a room');

            const transport = await currentRoom.createWebRtcTransport();

            if (direction === 'send') {
                currentPeer.setSendTransport(transport);
            } else {
                currentPeer.setRecvTransport(transport);
            }

            callback({
                id:             transport.id,
                iceParameters:  transport.iceParameters,
                iceCandidates:  transport.iceCandidates,
                dtlsParameters: transport.dtlsParameters,
            });
        } catch (err) {
            console.error('[createTransport] error:', err);
            callback({ error: err.message });
        }
    });

    // ── connectTransport ──────────────────────────────────────────────────────
    socket.on('connectTransport', async ({ transportId, dtlsParameters }, callback) => {
        try {
            if (!currentPeer) throw new Error('Not in a room');

            const transport =
                currentPeer.sendTransport?.id === transportId
                    ? currentPeer.sendTransport
                    : currentPeer.recvTransport;

            if (!transport) throw new Error(`Transport ${transportId} not found`);

            await transport.connect({ dtlsParameters });
            callback({});
        } catch (err) {
            console.error('[connectTransport] error:', err);
            callback({ error: err.message });
        }
    });

    // ── produce ───────────────────────────────────────────────────────────────
    socket.on('produce', async ({ kind, rtpParameters, appData }, callback) => {
        try {
            if (!currentPeer || !currentPeer.sendTransport) {
                throw new Error('No send transport');
            }

            const producer = await currentPeer.sendTransport.produce({
                kind,
                rtpParameters,
                appData: appData || {},
            });

            currentPeer.addProducer(producer);

            producer.on('score', (score) => {
                socket.emit('producerScore', { producerId: producer.id, score });
            });

            // Notify all other peers in the room about the new producer
            socket.to(currentRoom.id).emit('newProducer', {
                producerId:  producer.id,
                peerId:      currentPeer.id,
                displayName: currentPeer.displayName,
                kind:        producer.kind,
                appData:     producer.appData,
            });

            callback({ id: producer.id });

            console.log(`[Room ${currentRoom.id}] ${currentPeer.displayName} produced ${kind} (${producer.id})`);
        } catch (err) {
            console.error('[produce] error:', err);
            callback({ error: err.message });
        }
    });

    // ── consume ───────────────────────────────────────────────────────────────
    socket.on('consume', async ({ producerId, rtpCapabilities }, callback) => {
        try {
            if (!currentPeer || !currentPeer.recvTransport) {
                throw new Error('No recv transport');
            }

            const consumer = await currentRoom.createConsumer({
                consumerTransport: currentPeer.recvTransport,
                producerId,
                rtpCapabilities,
            });

            currentPeer.addConsumer(consumer);

            consumer.on('score', (score) => {
                socket.emit('consumerScore', { consumerId: consumer.id, score });
            });

            // Immediately request the highest simulcast layer
            if (consumer.type === 'simulcast') {
                await consumer.setPreferredLayers({
                    spatialLayer:  2,   // highest resolution layer
                    temporalLayer: 2,   // highest framerate layer
                }).catch(() => {});
            }

            callback({
                id:            consumer.id,
                producerId,
                kind:          consumer.kind,
                rtpParameters: consumer.rtpParameters,
                type:          consumer.type,
                appData:       consumer.appData,
            });
        } catch (err) {
            console.error('[consume] error:', err);
            callback({ error: err.message });
        }
    });

    // ── resumeConsumer ────────────────────────────────────────────────────────
    socket.on('resumeConsumer', async ({ consumerId }, callback) => {
        try {
            const consumer = currentPeer?.getConsumer(consumerId);
            if (!consumer) throw new Error(`Consumer ${consumerId} not found`);
            await consumer.resume();
            callback({});
        } catch (err) {
            console.error('[resumeConsumer] error:', err);
            callback({ error: err.message });
        }
    });

    // ── pauseProducer / resumeProducer ────────────────────────────────────────
    socket.on('pauseProducer', async ({ producerId }, callback) => {
        try {
            const producer = currentPeer?.getProducer(producerId);
            if (!producer) throw new Error(`Producer ${producerId} not found`);
            await producer.pause();
            socket.to(currentRoom.id).emit('producerPaused', { producerId, peerId: currentPeer.id });
            callback({});
        } catch (err) {
            callback({ error: err.message });
        }
    });

    socket.on('resumeProducer', async ({ producerId }, callback) => {
        try {
            const producer = currentPeer?.getProducer(producerId);
            if (!producer) throw new Error(`Producer ${producerId} not found`);
            await producer.resume();
            socket.to(currentRoom.id).emit('producerResumed', { producerId, peerId: currentPeer.id });
            callback({});
        } catch (err) {
            callback({ error: err.message });
        }
    });

    // ── closeProducer ─────────────────────────────────────────────────────────
    socket.on('closeProducer', async ({ producerId }, callback) => {
        try {
            currentPeer?.removeProducer(producerId);
            socket.to(currentRoom?.id).emit('producerClosed', { producerId, peerId: currentPeer?.id });
            callback({});
        } catch (err) {
            callback({ error: err.message });
        }
    });

    // ── getStats ──────────────────────────────────────────────────────────────
    socket.on('getStats', async ({ producerId }, callback) => {
        try {
            const producer = currentPeer?.getProducer(producerId);
            if (!producer) throw new Error('Producer not found');
            const stats = await producer.getStats();
            callback({ stats: Array.from(stats.values()) });
        } catch (err) {
            callback({ error: err.message });
        }
    });

    // ── disconnect ────────────────────────────────────────────────────────────
    socket.on('disconnect', (reason) => {
        console.log(`[Socket] disconnected: ${socket.id} — ${reason}`);
        if (currentRoom && currentPeer) {
            // Notify others
            socket.to(currentRoom.id).emit('peerLeft', {
                peerId:      currentPeer.id,
                displayName: currentPeer.displayName,
            });
            currentRoom.removePeer(currentPeer.id);
            console.log(`[Room ${currentRoom.id}] peer ${currentPeer.displayName} left — ${currentRoom.peerCount} remaining`);
        }
    });
});

// ── Boot ──────────────────────────────────────────────────────────────────────

(async () => {
    await workerPool.init();
    server.listen(config.port, () => {
        console.log(`[SFU] mediasoup server listening on port ${config.port}`);
        console.log(`[SFU] ${workerPool.size} worker(s) ready`);
        console.log(`[SFU] UDP ports ${config.worker.rtcMinPort}–${config.worker.rtcMaxPort}`);
    });
})();
