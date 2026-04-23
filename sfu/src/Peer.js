'use strict';

/**
 * Peer — represents one connected browser client in a Room.
 * Holds all mediasoup objects owned by this peer.
 */

class Peer {
    /**
     * @param {string} peerId
     * @param {string} displayName
     * @param {import('socket.io').Socket} socket
     */
    constructor(peerId, displayName, socket) {
        this.id          = peerId;
        this.displayName = displayName;
        this.socket      = socket;

        // mediasoup objects
        this.sendTransport = null;  // browser → SFU
        this.recvTransport = null;  // SFU → browser

        // Map of kind → Producer  (audio, video, screen)
        this.producers = new Map();

        // Map of producerId → Consumer
        this.consumers = new Map();
    }

    // ── Transport ─────────────────────────────────────────────────────────────

    setSendTransport(transport) {
        this.sendTransport = transport;
        transport.on('routerclose', () => {
            if (this.sendTransport) {
                this.sendTransport.close();
                this.sendTransport = null;
            }
        });
    }

    setRecvTransport(transport) {
        this.recvTransport = transport;
        transport.on('routerclose', () => {
            if (this.recvTransport) {
                this.recvTransport.close();
                this.recvTransport = null;
            }
        });
    }

    // ── Producers ─────────────────────────────────────────────────────────────

    addProducer(producer) {
        this.producers.set(producer.id, producer);
        producer.on('transportclose', () => this.producers.delete(producer.id));
    }

    getProducer(producerId) {
        return this.producers.get(producerId);
    }

    removeProducer(producerId) {
        const p = this.producers.get(producerId);
        if (p && !p.closed) p.close();
        this.producers.delete(producerId);
    }

    // ── Consumers ─────────────────────────────────────────────────────────────

    addConsumer(consumer) {
        this.consumers.set(consumer.id, consumer);
        consumer.on('transportclose', () => this.consumers.delete(consumer.id));
        consumer.on('producerclose', () => {
            this.consumers.delete(consumer.id);
            // Notify browser that this consumer is gone
            this.socket.emit('consumerClosed', { consumerId: consumer.id });
        });
    }

    getConsumer(consumerId) {
        return this.consumers.get(consumerId);
    }

    // ── Cleanup ───────────────────────────────────────────────────────────────

    close() {
        for (const c of this.consumers.values()) { if (!c.closed) c.close(); }
        for (const p of this.producers.values()) { if (!p.closed) p.close(); }
        if (this.sendTransport && !this.sendTransport.closed) this.sendTransport.close();
        if (this.recvTransport && !this.recvTransport.closed) this.recvTransport.close();
        this.consumers.clear();
        this.producers.clear();
    }
}

module.exports = Peer;
