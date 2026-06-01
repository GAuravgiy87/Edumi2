FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_CACHE_DIR=/root/.cache/pip
ENV PIP_NO_COMPILE=1

WORKDIR /app

# ffmpeg for RTSP audio extraction, libgl1/libglib2.0-0 for OpenCV headless
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Requirements first for cache efficiency
COPY camera_service/requirements.txt .
RUN pip install --upgrade pip --quiet && \
    pip install --quiet -r requirements.txt

# Copy full project (camera_service imports models from main project)
COPY . .

RUN mkdir -p /app/media/temp && \
    chmod -R 755 /app/media && \
    chmod +x /app/camera_service/entrypoint.sh

EXPOSE 8001
WORKDIR /app/camera_service
ENTRYPOINT ["/app/camera_service/entrypoint.sh"]
