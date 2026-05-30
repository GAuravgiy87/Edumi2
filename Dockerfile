# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y libpq-dev gcc libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*
# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install psycopg2-binary django-redis channels-redis dj-database-url whitenoise

# Copy the current directory contents into the container at /app
COPY . /app/

# Run collectstatic
RUN python manage.py collectstatic --noinput --clear

# Expose port 8000
EXPOSE 8000

# Use a production-ready entrypoint
# We use daphne for ASGI (WebSockets) and it also handles HTTP
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "school_project.asgi:application"]
