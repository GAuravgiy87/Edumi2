'use strict';

/**
 * WorkerPool — manages a pool of mediasoup workers.
 * Distributes rooms across workers in round-robin to balance CPU load.
 */

const mediasoup = require('mediasoup');
const config    = require('./config');

class WorkerPool {
    constructor() {
        this._workers = [];
        this._nextIdx = 0;
    }

    async init() {
        for (let i = 0; i < config.numWorkers; i++) {
            const worker = await mediasoup.createWorker({
                rtcMinPort: config.worker.rtcMinPort,
                rtcMaxPort: config.worker.rtcMaxPort,
                logLevel:   config.worker.logLevel,
                logTags:    config.worker.logTags,
            });

            worker.on('died', (error) => {
                console.error(`[Worker ${worker.pid}] died — restarting in 2s`, error);
                setTimeout(() => this._replaceWorker(i), 2000);
            });

            this._workers.push(worker);
            console.log(`[WorkerPool] Worker ${worker.pid} created (${i + 1}/${config.numWorkers})`);
        }
    }

    async _replaceWorker(idx) {
        try {
            const worker = await mediasoup.createWorker({
                rtcMinPort: config.worker.rtcMinPort,
                rtcMaxPort: config.worker.rtcMaxPort,
                logLevel:   config.worker.logLevel,
                logTags:    config.worker.logTags,
            });
            worker.on('died', (error) => {
                console.error(`[Worker ${worker.pid}] died — restarting in 2s`, error);
                setTimeout(() => this._replaceWorker(idx), 2000);
            });
            this._workers[idx] = worker;
            console.log(`[WorkerPool] Worker ${worker.pid} replaced at index ${idx}`);
        } catch (err) {
            console.error('[WorkerPool] Failed to replace worker:', err);
        }
    }

    /** Get next worker in round-robin */
    next() {
        const worker = this._workers[this._nextIdx];
        this._nextIdx = (this._nextIdx + 1) % this._workers.length;
        return worker;
    }

    get size() {
        return this._workers.length;
    }
}

module.exports = new WorkerPool();
