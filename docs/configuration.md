# ⚙️ Configuration

← [Back to README](../README.md)

ExtrarrFin can be configured in three ways (in order of priority: CLI args > env vars > YAML file).

---

## Option 1: YAML file (recommended)

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Full example:

```yaml
# === SONARR (TV Series) - Required ===
sonarr_url: "http://localhost:8989"
sonarr_api_key: "your_api_key_here"

# === RADARR (Movies) - Optional ===
# Leave empty or omit to disable Radarr support
radarr_url: "http://localhost:7878"
radarr_api_key: "your_radarr_api_key_here"

# === JELLYFIN - Optional ===
jellyfin_url: "http://localhost:8096"
jellyfin_api_key: "your_jellyfin_api_key_here"

# === PATH MAPPING - Optional ===
# Use when ExtrarrFin runs on a different machine than Sonarr/Radarr
# See: docs/advanced.md#directory-mapping
media_directory: "/mnt/media/TV Shows"
sonarr_directory: "/tv"
radarr_directory: "/movies"

# === DOWNLOAD FORMAT ===
yt_dlp_format: "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

# === YOUTUBE SCORING ===
# See SCORING.md for details
youtube_search_results: 10  # Number of results to analyze (3-20)
min_score: 50.0             # Minimum score threshold (40-80)

# === LOGGING ===
log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

# === MODE ===
# season0: Download monitored Season 0 episodes from Sonarr
# tag:     Download behind-the-scenes for series/movies with "want-extras" tag
# Both:    mode: ["season0", "tag"]
mode: "season0"

# === SCHEDULE ===
schedule_enabled: false
schedule_interval: 6
schedule_unit: "hours"  # seconds, minutes, hours, days, weeks

# === SUBTITLES ===
subtitle_languages:
  - "fr"
  - "en"
  - "fr-FR"
  - "en-US"
  - "en-GB"
download_all_subtitles: false

# === STRM MODE ===
# Creates .strm files instead of downloading — saves disk space
# See: docs/strm-mode.md
use_strm_files: false

# === MOVIE EXTRAS KEYWORDS (tag mode) ===
movie_extras_keywords:
  - "behind the scenes"
  - "making of"
  - "featurette"
  - "interviews"
  - "deleted scenes"
  - "bloopers"
  - "vfx"
  - "special effects"
  - "visual effects"
  - "SFX"
  - "FX"
```

---

## Option 2: Environment variables

```bash
export SONARR_URL="http://localhost:8989"
export SONARR_API_KEY="your_api_key_here"
export RADARR_URL="http://localhost:7878"
export RADARR_API_KEY="your_radarr_api_key_here"
export JELLYFIN_URL="http://localhost:8096"
export JELLYFIN_API_KEY="your_jellyfin_api_key_here"
export MEDIA_DIRECTORY="/mnt/media/TV Shows"
export SONARR_DIRECTORY="/tv"
export RADARR_DIRECTORY="/movies"
export SUBTITLE_LANGUAGES="fr,en,es"
export DOWNLOAD_ALL_SUBTITLES="false"
export USE_STRM_FILES="false"
```

---

## Option 3: CLI arguments

All options can be passed directly on the command line:

```bash
python extrarrfin.py \
  --sonarr-url http://localhost:8989 \
  --sonarr-api-key YOUR_KEY \
  --radarr-url http://localhost:7878 \
  --radarr-api-key YOUR_RADARR_KEY \
  --media-dir /mnt/media \
  --sonarr-dir /tv \
  --log-level DEBUG \
  download
```

### Available global CLI options

| Option | Env var | Description |
|--------|---------|-------------|
| `--config PATH` | — | Path to YAML config file |
| `--sonarr-url URL` | `SONARR_URL` | Sonarr instance URL (required) |
| `--sonarr-api-key KEY` | `SONARR_API_KEY` | Sonarr API key (required) |
| `--radarr-url URL` | `RADARR_URL` | Radarr instance URL (optional) |
| `--radarr-api-key KEY` | `RADARR_API_KEY` | Radarr API key (optional) |
| `--jellyfin-url URL` | `JELLYFIN_URL` | Jellyfin URL (optional) |
| `--jellyfin-api-key KEY` | `JELLYFIN_API_KEY` | Jellyfin API key (optional) |
| `--media-dir PATH` | `MEDIA_DIRECTORY` | Local media directory |
| `--sonarr-dir PATH` | `SONARR_DIRECTORY` | Sonarr root directory |
| `--radarr-dir PATH` | `RADARR_DIRECTORY` | Radarr root directory |
| `--log-level LEVEL` | — | DEBUG / INFO / WARNING / ERROR |

---

## Getting API keys

### Sonarr
1. Open Sonarr → **Settings** → **General**
2. Copy the **API Key**

### Radarr
1. Open Radarr → **Settings** → **General**
2. Copy the **API Key**

### Jellyfin
1. Open Jellyfin → **Dashboard** → **API Keys**
2. Click **+**, give it a name (e.g. "ExtrarrFin"), copy the key
