# ── SFU — mediasoup Node.js server ───────────────────────────────────────────
FROM node:20-slim AS base

# mediasoup requires build tools for its C++ native addon
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer cache)
COPY package.json ./
RUN npm install --omit=dev

# Copy source
COPY src/ ./src/
COPY .env.example ./.env.example

EXPOSE 3000

CMD ["node", "src/server.js"]
