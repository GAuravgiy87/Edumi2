FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=school_project.settings
# pip cache dir — Docker BuildKit will cache this between builds
ENV PIP_CACHE_DIR=/root/.cache/pip
ENV PIP_NO_COMPILE=1

WORKDIR /app

# System deps in one layer — ffmpeg for RTSP audio, libpq for postgres
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev gcc \
        libgl1 libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — this layer is cached until requirements.txt changes
COPY requirements.txt .

# Single pip install — all packages in one RUN = one cache layer
# opencv-python-headless is identical to opencv-python but without Qt/GUI libs
# It's ~30MB smaller and installs faster in a headless server environment
RUN pip install --upgrade pip --quiet && \
    grep -v '^opencv-python==' requirements.txt > /tmp/req_no_cv.txt && \
    pip install --quiet opencv-python-headless==4.8.1.78 && \
    pip install --quiet -r /tmp/req_no_cv.txt && \
    pip install --quiet psycopg2-binary django-redis channels-redis dj-database-url whitenoise

# Copy source — separate layer so code changes don't re-run pip
COPY . .

RUN mkdir -p /app/media/temp /app/staticfiles && \
    chmod -R 755 /app/media /app/staticfiles && \
    chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
