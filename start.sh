#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo "venv activated: $(python --version)"

# ── Dependencies ──────────────────────────────────────────────────────────────
echo "Installing requirements..."
pip install -r requirements.txt --quiet

# ── Django setup ──────────────────────────────────────────────────────────────
echo "Running migrations..."
python manage.py migrate --run-syncdb

# ── Run ───────────────────────────────────────────────────────────────────────
echo "Starting server at http://0.0.0.0:8000"
python manage.py runserver 0.0.0.0:8000
