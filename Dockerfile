# Dockerfile – builds the EduMi2 Django application
FROM python:3.11-slim AS base

# OS‑level dependencies (psycopg2, cryptography, ffmpeg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libffi-dev python3-dev \
    ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Expose service ports (will be overridden per container in docker‑compose)
EXPOSE 8002 8003 8004 8005 8006 8007 7880 7881

# Install Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Collect static files at build time (WhiteNoise will serve them)
RUN python manage.py collectstatic --noinput

# Default command – overridden per service in docker‑compose.yml
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
