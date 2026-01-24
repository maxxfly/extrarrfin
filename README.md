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

## � What Gets Downloaded?

ExtrarrFin targets **Season 0 episodes** (special episodes) from your Sonarr library based on specific criteria:

### Selection Criteria

An episode will be downloaded if **ALL** of the following conditions are met:

1. **✅ Series is monitored** in Sonarr
   - The series must have its "Monitored" flag enabled

2. **✅ Episode is monitored** in Season 0
   - Individual episodes must be marked as monitored
   - The entire season doesn't need to be monitored - only the specific episodes you want
   - This allows fine-grained control: you can monitor only specific specials

3. **✅ Episode has no file**
   - The episode must not already have a file in Sonarr
   - Use `--force` flag to re-download existing files if needed

### What is Season 0?

Season 0 (also called "Specials") typically includes:
- 🎬 **Behind-the-scenes** footage
- 🎤 **Interviews** with cast and crew
- 🎭 **Deleted scenes** and outtakes
- 📺 **Pilot episodes** and unaired pilots
- 🎉 **Holiday specials** and crossover episodes
- 🎥 **Featurettes** and making-of documentaries
- 📰 **Recap episodes** and previews

### YouTube Search Strategy

For each missing episode, ExtrarrFin searches YouTube using:

1. **First attempt**: `"Series Name" + "Episode Title"`
   - Example: "Breaking Bad Behind the Scenes"

2. **Fallback**: `"Episode Title"` only
   - Used if the first search returns no results
   - Example: "Behind the Scenes"

### Download Process

For each matched episode:
1. ⬇️ Downloads video from YouTube (best quality MP4)
2. 📝 Downloads subtitles (configurable languages)
3. 🎬 Converts subtitles to SRT format
4. 💾 Saves as: `Series Name - S00E01 - Episode Title.mp4`
5. 📁 Places in `/path/to/series/Specials/` folder
6. 🔄 Triggers Sonarr rescan (unless `--no-scan` flag is used)

### Example Workflow

```
Monitored series in Sonarr: "Breaking Bad"
├─ Season 0 (Specials)
│  ├─ S00E01 "Pilot" ..................... [monitored, no file] → ✅ Will download
│  ├─ S00E02 "Inside Breaking Bad" ....... [monitored, no file] → ✅ Will download
│  ├─ S00E03 "Making of Season 1" ........ [NOT monitored] ...... → ❌ Will skip
│  └─ S00E04 "Deleted Scenes" ............ [monitored, has file] → ❌ Will skip (already exists)
```

**Result**: Only episodes S00E01 and S00E02 will be downloaded.

## �📋 Prerequisites

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

# Subtitle configuration (optional)
subtitle_languages:
  - "fr"
  - "en"
  - "fr-FR"
  - "en-US"
  - "en-GB"
download_all_subtitles: false
```

### Option 2: Environment variables

You can also use a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
nano .env
```

Or export variables directly:

```bash
export SONARR_URL="http://localhost:8989"
export SONARR_API_KEY="your_api_key_here"
export MEDIA_DIRECTORY="/mnt/media/TV Shows"
export SONARR_DIRECTORY="/tv"
export SUBTITLE_LANGUAGES="fr,en,es"
export DOWNLOAD_ALL_SUBTITLES="false"
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

## � Subtitle Management

ExtrarrFin automatically downloads and manages subtitles from YouTube videos:

### Features

- **Auto-download**: Subtitles are automatically downloaded when available
- **Multiple languages**: Configure priority languages (default: French and English)
- **Smart fallback**: Uses manual subtitles first, then auto-generated if needed
- **Format conversion**: All subtitles are converted to SRT format for maximum compatibility
- **Embedded + External**: Subtitles are both embedded in the video file and saved as separate .srt files

### Configuration

```yaml
# Download specific languages (in priority order)
subtitle_languages:
  - "fr"          # French
  - "en"          # English
  - "fr-FR"       # French (France)
  - "en-US"       # English (US)
  - "en-GB"       # English (UK)
  - "de"          # German
  - "es"          # Spanish
  - "it"          # Italian
  - "pt"          # Portuguese

# Or download ALL available subtitles
download_all_subtitles: false  # Set to true to download all
```

### How it works

1. **Priority mode** (default): Downloads only specified languages
   - Tries manual subtitles first
   - Falls back to auto-generated if manual not available
   - Downloads in the order specified in `subtitle_languages`

2. **All subtitles mode**: When `download_all_subtitles: true`
   - Downloads every available subtitle language
   - Useful for international content
   - May result in larger storage usage

### Language codes

Use ISO 639-1 codes or with regional variants:
- Simple: `fr`, `en`, `de`, `es`, `it`, `pt`, `ja`, `ko`, `zh`
- Regional: `en-US`, `en-GB`, `fr-FR`, `fr-CA`, `es-ES`, `es-MX`, `pt-BR`, `pt-PT`

### Examples

**For French content with English fallback:**
```yaml
subtitle_languages: ["fr", "fr-FR", "en"]
```

**For international viewing:**
```yaml
download_all_subtitles: true
```

**For specific multi-language setup:**
```yaml
subtitle_languages: ["fr", "en", "es", "de", "it"]
download_all_subtitles: false
```

### Output

Subtitles are saved both:
- **Embedded**: Inside the video file (for apps that support it)
- **External**: As separate `.srt` files (e.g., `Series - S00E01.fr.srt`, `Series - S00E01.en.srt`)

This ensures maximum compatibility with Jellyfin, Plex, and other media servers.

## �🔧 Directory mapping

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
      # Subtitle configuration (optional)
      - SUBTITLE_LANGUAGES=fr,en,fr-FR,en-US,en-GB
      - DOWNLOAD_ALL_SUBTITLES=false
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
  -e SUBTITLE_LANGUAGES=fr,en,es \
  -e DOWNLOAD_ALL_SUBTITLES=false \
  -v /path/to/media:/media \
  jeanmary/extrarrfin:latest download
```

Available environment variables:
- `SONARR_URL`: Sonarr instance URL
- `SONARR_API_KEY`: Sonarr API key
- `MEDIA_DIRECTORY`: Path to media directory
- `SONARR_DIRECTORY`: Sonarr root directory path
- `SUBTITLE_LANGUAGES`: Comma-separated language codes (e.g., `fr,en,de,es`)
- `DOWNLOAD_ALL_SUBTITLES`: Set to `true` to download all available subtitles

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
