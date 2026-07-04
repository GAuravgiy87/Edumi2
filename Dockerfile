# ==============================================================================
#  EduMi 2 — Production Dockerfile
#  Multi-stage build: builder → runtime (smaller final image)
# ==============================================================================

# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_COMPILE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ make \
        cmake \
        libpq-dev \
        libgl1 libglib2.0-0 \
        libopenblas-dev liblapack-dev libx11-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python packages into a prefix directory (for copying to runtime)
RUN pip install --upgrade pip setuptools wheel --quiet && \
    # Pin numpy first (face_recognition needs 1.x)
    pip install --quiet "numpy==1.26.4" && \
    # Use headless OpenCV (no GUI libs needed on server)
    grep -v '^opencv-python' requirements.txt | \
        grep -v '^numpy' | \
        grep -v '^dlib-bin' | \
        grep -v '^face_recognition' > /tmp/req_filtered.txt && \
    pip install --quiet "opencv-python-headless==4.8.1.78" && \
    pip install --quiet "dlib-bin==20.0.1" && \
    pip install --quiet --no-deps face_recognition==1.3.0 && \
    pip install --quiet -r /tmp/req_filtered.txt && \
    # Production extras
    pip install --quiet \
        psycopg2-binary \
        dj-database-url \
        django-redis \
        channels-redis \
        whitenoise \
        gunicorn


# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=school_project.settings \
    PATH="/app/venv/bin:$PATH"

# Install only runtime system libraries (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libgl1 libglib2.0-0 \
        libopenblas0 \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r edumi && useradd -r -g edumi -d /app edumi

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=edumi:edumi . .

# Create required directories with correct permissions
RUN mkdir -p \
        /app/database/media/recordings \
        /app/staticfiles \
        /app/logs \
    && chown -R edumi:edumi /app \
    && chmod +x /app/start.sh 2>/dev/null || true

# Switch to non-root user
USER edumi

# Collect static files at build time (faster startup)
RUN python manage.py collectstatic --noinput --clear -v 0 2>/dev/null || true

EXPOSE 8002

# Healthcheck — Daphne responds on /health/
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsk https://localhost:8002/health/ || exit 1

CMD ["python", "run_ssl_server.py"]
