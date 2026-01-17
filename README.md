# ExtrarrFin 🎬

**ExtrarrFin** is a Python tool that automates the download of special episodes (Season 0) for your monitored series in Sonarr, using yt-dlp to search and download content from YouTube.

## ✨ Features

- 🔍 **Automatic detection**: Retrieves all monitored series with monitored Season 0
- 📺 **YouTube download**: Uses yt-dlp to download special episodes from YouTube
- 🎯 **Jellyfin format**: Automatically names files according to Jellyfin-compatible format
- 🏃 **Dry-run mode**: Lists episodes without downloading them
- ♻️ **Duplicate detection**: Avoids re-downloading existing files (`--force` option to override)
- 🔄 **Sonarr integration**: Automatically triggers a scan after download
- 🎚️ **Filtering**: Ability to limit to a specific series with `--limit`
- ⚙️ **Flexible configuration**: YAML file, environment variables or CLI arguments
- 📂 **Directory mapping**: Support for remote execution with path mapping
- ⏰ **Schedule mode**: Automatic periodic downloads with configurable intervals
- 🐳 **Docker support**: Run in a container with Alpine-based image

## 📋 Prerequisites

- Python 3.8+
- An operational Sonarr instance
- Sonarr API access (API key)
- FFmpeg (for yt-dlp)

## 🚀 Installation

### Option 1: Standard Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/extrarrfin.git
cd extrarrfin

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Docker Installation

```bash
# Pull the image from Docker Hub
docker pull jeanmary/extrarrfin:latest

# Or use docker-compose (recommended)
# Create a docker-compose.yml file and run:
docker-compose up -d
```

### Installing system dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

## ⚙️ Configuration

### Option 1: Configuration file (recommended)

Copy the example file and edit it:

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Example `config.yaml`:

```yaml
# Your Sonarr instance URL
sonarr_url: "http://localhost:8989"

# Sonarr API key
sonarr_api_key: "your_api_key_here"

# Directory where your media is located (optional)
media_directory: "/mnt/media/TV Shows"

# Root directory in Sonarr (optional)
sonarr_directory: "/tv"

# yt-dlp download format
yt_dlp_format: "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

# Log level
log_level: "INFO"

# Schedule mode (optional)
schedule_enabled: false
schedule_interval: 6
schedule_unit: "hours"  # seconds, minutes, hours, days, weeks
```

### Option 2: Environment variables

```bash
export SONARR_URL="http://localhost:8989"
export SONARR_API_KEY="your_api_key_here"
export MEDIA_DIRECTORY="/mnt/media/TV Shows"
export SONARR_DIRECTORY="/tv"
```

### Option 3: Command-line arguments

```bash
python extrarrfin.py --sonarr-url http://localhost:8989 --sonarr-api-key YOUR_KEY list
```

## 📖 Usage

### Available commands

#### `test` - Test connection

```bash
python extrarrfin.py test
```

Verifies that the connection to Sonarr is working correctly.

#### `list` - List series and episodes

```bash
# List all series with monitored Season 0
python extrarrfin.py list

# Limit to a specific series (by name)
python extrarrfin.py list --limit "Breaking Bad"

# Limit to a specific series (by ID)
python extrarrfin.py list --limit 42
```

#### `download` - Download episodes

```bash
# Dry-run mode (simulation without downloading)
python extrarrfin.py download --dry-run

# Download all missing episodes
python extrarrfin.py download

# Limit to a specific series
python extrarrfin.py download --limit "Breaking Bad"

# Force re-download even if files exist
python extrarrfin.py download --force

# Don't trigger Sonarr scan after download
python extrarrfin.py download --no-scan
```

#### `scan` - Manual scan

```bash
# Trigger a manual scan for a series
python extrarrfin.py scan 42
```

#### `schedule-mode` - Automatic periodic downloads

```bash
# Run with config file settings
python extrarrfin.py schedule-mode

# Override interval and unit
python extrarrfin.py schedule-mode --interval 30 --unit minutes

# With other options
python extrarrfin.py schedule-mode --interval 6 --unit hours --limit "Series Name"

# Dry-run mode for testing
python extrarrfin.py schedule-mode --dry-run --interval 5 --unit minutes
```

Schedule mode will:
- Run immediately on start
- Execute downloads at the specified interval
- Continue running until stopped with Ctrl+C
- Display clear information about each execution and next run

### Global options

```bash
# Use a specific configuration file
python extrarrfin.py --config /path/to/config.yaml list

# Specify URL and API key directly
python extrarrfin.py --sonarr-url http://localhost:8989 --sonarr-api-key YOUR_KEY list

# Set log level
python extrarrfin.py --log-level DEBUG list

# Specify mapping directories
python extrarrfin.py --media-dir /mnt/media --sonarr-dir /tv download
```

## 🎯 Common use cases

### Scenario 1: First use

```bash
# 1. Test connection
python extrarrfin.py test

# 2. List what would be downloaded
python extrarrfin.py download --dry-run

# 3. Download episodes
python extrarrfin.py download
```

### Scenario 2: Test with a series

```bash
# Limit to one series to test
python extrarrfin.py list --limit "Breaking Bad"
python extrarrfin.py download --limit "Breaking Bad" --dry-run
python extrarrfin.py download --limit "Breaking Bad"
```

### Scenario 3: Remote execution

If you're running the script on a different machine than Sonarr:

```bash
# Configure mapping in config.yaml
# sonarr_directory: "/tv"
# media_directory: "/mnt/nas/media/TV Shows"

python extrarrfin.py download
```

### Scenario 4: Re-download files

```bash
# Force re-download
python extrarrfin.py download --limit "Series Name" --force
```

## 📁 File structure

Downloaded files are organized according to Jellyfin format:

```
/path/to/series/
└── Specials/
    ├── Series Name - S00E01 - Episode Title.mp4
    ├── Series Name - S00E02 - Episode Title.mp4
    └── ...
```

Naming format: `{SeriesName} - S{Season:02d}E{Episode:02d} - {EpisodeTitle}.{ext}`

## 🔧 Directory mapping

If you're running the script on a different machine than Sonarr, you need to configure mapping:

- **`sonarr_directory`**: The path as configured in Sonarr (e.g. `/tv`)
- **`media_directory`**: The actual path on your machine (e.g. `/mnt/nas/media/TV Shows`)

The script will automatically convert paths.

## 🐛 Troubleshooting

### Problem: "Missing configuration"

**Solution**: Create a `config.yaml` file or use environment variables:

```bash
export SONARR_URL="http://localhost:8989"
export SONARR_API_KEY="your_key"
```

### Problem: "No video found on YouTube"

**Solution**: The tool searches YouTube in two steps:
1. First with "series name + episode name"
2. Then with "episode name only" if the first search fails

If videos are still not found, check that:
- Episode names in Sonarr are accurate
- The content exists on YouTube
- Your network can access YouTube

### Problem: Sonarr connection error

**Solution**: Verify that:
- Sonarr URL is correct (with port)
- API key is valid (Settings > General in Sonarr)
- Sonarr is accessible from your machine

```bash
# Test connection
python extrarrfin.py test
```

### Problem: FFmpeg not found

**Solution**: Install FFmpeg:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### Problem: Incorrect file paths

**Solution**: Configure directory mapping:

```yaml
media_directory: "/your/real/path"
sonarr_directory: "/path/in/sonarr"
```

## 📝 Advanced examples

### Schedule mode with systemd

```bash
# Create a systemd service file
sudo nano /etc/systemd/system/extrarrfin.service
```

```ini
[Unit]
Description=ExtrarrFin Schedule Mode
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/home/user/extrarrfin
ExecStart=/usr/bin/python3 /home/user/extrarrfin/extrarrfin.py --config /home/user/extrarrfin/config.yaml schedule-mode
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start the service
sudo systemctl enable extrarrfin
sudo systemctl start extrarrfin
sudo systemctl status extrarrfin
```

### Automation with cron (one-time runs)

```bash
# Run every day at 2 AM
0 2 * * * cd /home/user/extrarrfin && /usr/bin/python3 extrarrfin.py --config config.yaml download >> /var/log/extrarrfin.log 2>&1
```

### Wrapper script

```bash
#!/bin/bash
# extrarrfin-wrapper.sh

cd /home/user/extrarrfin
source venv/bin/activate
python extrarrfin.py download --log-level INFO
deactivate
```

## 🐳 Docker Usage

### Quick start with Docker

```bash
# Pull the image from Docker Hub
docker pull jeanmary/extrarrfin:latest

# Test connection
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  jeanmary/extrarrfin:latest --config /config/config.yaml test

# List series
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  jeanmary/extrarrfin:latest --config /config/config.yaml list

# Download episodes (one-time)
docker run --rm \
  -v $(pwd)/config.yaml:/config/config.yaml \
  -v /path/to/media:/media \
  jeanmary/extrarrfin:latest --config /config/config.yaml download
```

### Docker Compose (recommended for schedule mode)

1. Create a `config` directory and copy your configuration:

```bash
mkdir config
cp config.yaml config/
```

2. Edit `docker-compose.yml` to adjust paths and settings:

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
      - SONARR_URL=http://sonarr:8989
      - SONARR_API_KEY=your_api_key_here
      - MEDIA_DIRECTORY=/media
      - SONARR_DIRECTORY=/media
    command: ["--config", "/config/config.yaml", "schedule-mode"]
    networks:
      - media

networks:
  media:
    external: true
    name: your_existing_network
```

3. Start the container:

```bash
# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Docker environment variables

You can override config with environment variables:

```bash
docker run --rm \
  -e SONARR_URL=http://sonarr:8989 \
  -e SONARR_API_KEY=your_key \
  -e MEDIA_DIRECTORY=/media \
  -v /path/to/media:/media \
  jeanmary/extrarrfin:latest download
```

### Docker with existing Sonarr network

If Sonarr is already running in Docker:

```bash
# Find Sonarr's network
docker network ls

# Use the same network in docker-compose.yml
networks:
  media:
    external: true
    name: sonarr_network_name
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. Fork the project
2. Create a branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for more details.

## ⚠️ Disclaimer

This tool downloads content from YouTube. Make sure to respect:
- YouTube's Terms of Service
- Copyright laws in your country
- Sonarr's Terms of Service

Use this tool responsibly and only for content you have the rights to.

## 🙏 Acknowledgments

- [Sonarr](https://sonarr.tv/) - The TV series manager
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - The YouTube downloader
- [Click](https://click.palletsprojects.com/) - The CLI library
- [Rich](https://github.com/Textualize/rich) - Terminal display

## 📞 Support

For any questions or issues:
- Open an issue on GitHub
- Check Sonarr documentation
- Check logs with `--log-level DEBUG`

---

**Made with ❤️ for the *arr community**
