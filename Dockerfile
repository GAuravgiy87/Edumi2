FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=school_project.settings
ENV PIP_NO_COMPILE=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev gcc \
        libgl1 libglib2.0-0 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip --quiet && \
    grep -v '^opencv-python' requirements.txt | grep -v '^numpy' > /tmp/req.txt && \
    pip install --quiet "numpy==1.26.4" && \
    pip install --quiet "opencv-python-headless==4.8.1.78" && \
    pip install --quiet -r /tmp/req.txt && \
    pip install --quiet psycopg2-binary django-redis channels-redis dj-database-url whitenoise

COPY . .

RUN mkdir -p /app/media/temp /app/staticfiles /app/logs && \
    chmod -R 755 /app/media /app/staticfiles /app/logs

EXPOSE 10000
