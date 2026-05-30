# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY camera_service/requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project context into the container at /app
# This allows camera_service to access main project apps
COPY . /app/

# Expose port 8001
EXPOSE 8001

# Start the application from the camera_service subdirectory
WORKDIR /app/camera_service
CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]
