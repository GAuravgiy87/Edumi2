#!/bin/bash

# Run database migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Celery worker in background
celery -A school_project worker -l warning --concurrency=1 &

# Start Daphne server
daphne -b 0.0.0.0 -p 10000 school_project.asgi:application
