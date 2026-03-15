# 🚀 Installation

← [Back to README](../README.md)

## Prerequisites

- Python 3.8+
- An operational **Sonarr** instance with API access (required)
- An operational **Radarr** instance with API access (optional, for movies)
- **FFmpeg** (required by yt-dlp for audio/video conversion)

### Installing FFmpeg

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

---

## Option 1: Standard Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/extrarrfin.git
cd extrarrfin

# (Recommended) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Verify the installation:

```bash
python extrarrfin.py test
```

---

## Option 2: Docker Installation

See the full [Docker documentation](docker.md) for all options.

```bash
# Pull the image
docker pull jeanmary/extrarrfin:latest

# Quick test
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  jeanmary/extrarrfin:latest --config /config/config.yaml test
```

---

## Next step

→ [Configure ExtrarrFin](configuration.md)
