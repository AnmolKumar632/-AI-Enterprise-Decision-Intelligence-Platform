# Build stage: Official lightweight Python runtime
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create media dirs
RUN mkdir -p /app/media/datasets /app/media/models /app/media/reports /app/media/predictions

# Run collectstatic for static assets
RUN python manage.py collectstatic --noinput

# Expose server port
EXPOSE 8000

# Start server via Gunicorn WSGI
CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
