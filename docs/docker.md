# 🐳 Docker

← [Back to README](../README.md)

---

## Quick start

```bash
# Pull the image
docker pull jeanmary/extrarrfin:latest

# Test connection
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  jeanmary/extrarrfin:latest --config /config/config.yaml test

# List series
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  jeanmary/extrarrfin:latest --config /config/config.yaml list

# One-time download
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  -v /path/to/media:/media \
  jeanmary/extrarrfin:latest --config /config/config.yaml download
```

---

## Docker Compose (recommended for schedule mode)

1. Create a config directory:
```bash
mkdir config
cp config.yaml config/
```

2. `docker-compose.yml`:
```yaml
version: '3.8'

services:
  extrarrfin:
    image: jeanmary/extrarrfin:latest
    container_name: extrarrfin
    restart: unless-stopped
    volumes:
      - ./config:/config
      - /path/to/your/media:/media
    environment:
      # Sonarr (required)
      - SONARR_URL=http://sonarr:8989
      - SONARR_API_KEY=your_api_key_here
      - SONARR_DIRECTORY=/media

      # Radarr (optional)
      - RADARR_URL=http://radarr:7878
      - RADARR_API_KEY=your_radarr_api_key_here
      - RADARR_DIRECTORY=/media

      # Jellyfin (optional)
      - JELLYFIN_URL=http://jellyfin:8096
      - JELLYFIN_API_KEY=your_jellyfin_api_key_here

      # Media
      - MEDIA_DIRECTORY=/media

      # Subtitles
      - SUBTITLE_LANGUAGES=fr,en,fr-FR,en-US,en-GB
      - DOWNLOAD_ALL_SUBTITLES=false

      # STRM mode
      - USE_STRM_FILES=false

    command: ["--config", "/config/config.yaml", "schedule-mode"]
    networks:
      - media

networks:
  media:
    external: true
    name: your_existing_network
```

3. Run:
```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
```

---

## Environment variables reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SONARR_URL` | ✅ | Sonarr instance URL |
| `SONARR_API_KEY` | ✅ | Sonarr API key |
| `RADARR_URL` | — | Radarr instance URL |
| `RADARR_API_KEY` | — | Radarr API key |
| `JELLYFIN_URL` | — | Jellyfin server URL |
| `JELLYFIN_API_KEY` | — | Jellyfin API key |
| `MEDIA_DIRECTORY` | — | Path to media directory (host side) |
| `SONARR_DIRECTORY` | — | Sonarr root directory (container side) |
| `RADARR_DIRECTORY` | — | Radarr root directory (container side) |
| `SUBTITLE_LANGUAGES` | — | Comma-separated codes (e.g. `fr,en,de`) |
| `DOWNLOAD_ALL_SUBTITLES` | — | `true` to download all languages |
| `USE_STRM_FILES` | — | `true` to create STRM files |

---

## Connecting to an existing Sonarr/Radarr network

If Sonarr/Radarr already run in Docker:

```bash
# Find their network
docker network ls

# Reference the same network in docker-compose.yml
networks:
  media:
    external: true
    name: sonarr_default   # replace with actual network name
```

---

## One-off commands in Docker

```bash
# Run theme download
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  -v /path/to/media:/media \
  jeanmary/extrarrfin:latest --config /config/config.yaml theme

# Download extras (tag mode)
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  -v /path/to/media:/media \
  jeanmary/extrarrfin:latest --config /config/config.yaml download --mode tag

# Dry-run
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  -v /path/to/media:/media \
  jeanmary/extrarrfin:latest --config /config/config.yaml download --dry-run
```
