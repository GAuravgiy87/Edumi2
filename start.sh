#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Try both bin and Scripts (for cross-platform compatibility)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
else
    echo "WARNING: Could not find venv activation script."
fi

echo "venv activated: $(python --version)"

# ── Python dependencies ───────────────────────────────────────────────────────
echo "Installing Python requirements..."
pip install -r requirements.txt --quiet

# ── Node.js / SFU dependencies ────────────────────────────────────────────────
if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found. Install it first."
    exit 1
fi

echo "Installing SFU dependencies..."
cd "$ROOT/sfu"
npm install --omit=dev --silent
cd "$ROOT"

# ── Django setup ──────────────────────────────────────────────────────────────
echo "Running migrations..."
python manage.py migrate --run-syncdb

# Create logs dir
mkdir -p "$ROOT/logs"

# ── Start Redis in background ─────────────────────────────────────────────────
if command -v redis-server &>/dev/null; then
    echo "Starting Redis server..."
    redis-server > "$ROOT/logs/redis.log" 2>&1 &
    REDIS_PID=$!
else
    echo "WARNING: redis-server not found. Assuming Redis is already running."
    REDIS_PID=""
fi

# ── Start Celery Worker in background ─────────────────────────────────────────
if command -v celery &>/dev/null || [ -f "venv/bin/celery" ] || [ -f "venv/Scripts/celery.exe" ]; then
    echo "Starting Celery worker..."
    celery -A school_project worker --loglevel=info > "$ROOT/logs/celery.log" 2>&1 &
    CELERY_PID=$!
else
    echo "WARNING: Celery not found. Worker will not start."
    CELERY_PID=""
fi

# ── Start Celery Beat in background ───────────────────────────────────────────
if command -v celery &>/dev/null || [ -f "venv/bin/celery" ] || [ -f "venv/Scripts/celery.exe" ]; then
    echo "Starting Celery beat..."
    celery -A school_project beat --loglevel=info > "$ROOT/logs/celery_beat.log" 2>&1 &
    BEAT_PID=$!
else
    CELERY_BEAT_PID=""
fi

# ── Start SFU in background ───────────────────────────────────────────────────
echo "Starting SFU media server..."
cd "$ROOT/sfu"
node src/server.js > "$ROOT/logs/sfu.log" 2>&1 &
SFU_PID=$!
cd "$ROOT"
sleep 2

if kill -0 $SFU_PID 2>/dev/null; then
    echo "SFU running (pid $SFU_PID) on port 3000"
else
    echo "ERROR: SFU failed to start. Check logs/sfu.log"
    exit 1
fi

# ── Cleanup on exit ───────────────────────────────────────────────────────────
trap "echo 'Stopping...'; kill $SFU_PID $REDIS_PID $CELERY_PID $BEAT_PID 2>/dev/null; exit" INT TERM EXIT

# ── Start Django ──────────────────────────────────────────────────────────────
echo "Starting Django at http://0.0.0.0:8000"
python manage.py runserver 0.0.0.0:8000
