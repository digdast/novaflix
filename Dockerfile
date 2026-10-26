FROM python:3.12-slim

LABEL maintainer="NovaFlix Team <admin@novaflix.io>"
LABEL description="Sovereign Open-Source Media Platform - The Ultimate Alternative to Plex, Jellyfin & Emby"

WORKDIR /app

# Install system dependencies including curl and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8096
EXPOSE 8097

ENV PYTHONPATH=/app
ENV NOVAFLIX_HOST=0.0.0.0
ENV NOVAFLIX_PORT=8096
ENV NOVAFLIX_PORTAL_PORT=8097
ENV NOVAFLIX_REMOTE_ENABLED=true

CMD ["python", "-m", "novaflix.main"]
