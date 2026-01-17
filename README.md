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

## 📋 Prerequisites

- Python 3.8+
- An operational Sonarr instance
- Sonarr API access (API key)
- FFmpeg (for yt-dlp)

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/extrarrfin.git
cd extrarrfin

# Install dependencies
pip install -r requirements.txt
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

### Automation with cron

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
