# 📖 Usage

← [Back to README](../README.md)

---

## Commands overview

| Command | Description |
|---------|-------------|
| [`test`](#test) | Test connections to Sonarr, Radarr and Jellyfin |
| [`list`](#list) | Display a table of series/movies and their status |
| [`list-themes`](#list-themes) | Show `theme.mp3` status for all series & movies (with Year / Network) |
| [`download`](#download) | Download missing Season 0 episodes or extras |
| [`theme`](#theme) | Download `theme.mp3` for series and movies |
| [`scan`](#scan) | Trigger a manual Sonarr rescan |
| [`schedule-mode`](#schedule-mode) | Run downloads on a periodic schedule |

---

## `test`

Verify connections to Sonarr, Radarr (if configured), and Jellyfin (if configured).

```bash
python extrarrfin.py test

# With specific Jellyfin credentials
python extrarrfin.py test --jellyfin-url http://localhost:8096 --jellyfin-api-key YOUR_KEY
```

**Example output:**
```
Testing Sonarr connection...
  URL: http://localhost:8989
  ✓ Connection successful!
  Series: 42 total, 35 monitored
  With monitored Season 0 episodes: 12
  With want-extras tag: 8

Testing Radarr connection...
  URL: http://localhost:7878
  ✓ Connection successful!
  Movies: 156 total, 145 monitored
  With want-extras tag: 8

Testing Jellyfin connection...
  URL: http://localhost:8096
  ✓ Jellyfin connection successful!
  Server: My Jellyfin Server  v10.8.13
```

---

## `list`

Display a Rich table with status information. Three modes are available:

| `--mode` | Description |
|----------|-------------|
| `season0` | Monitored Season 0 episodes (default) |
| `tag` | Series/movies with the `want-extras` tag |
| `theme` | `theme.mp3` presence for all series and movies |

Modes can be combined.

```bash
# Default: Season 0
python extrarrfin.py list

# Extras (tag mode)
python extrarrfin.py list --mode tag

# Theme music status
python extrarrfin.py list --mode theme

# Combine modes
python extrarrfin.py list --mode season0 --mode tag

# Filter by name or ID
python extrarrfin.py list --limit "Breaking Bad"
python extrarrfin.py list --mode theme --limit 42
```

**Season 0 example:**
```
Series with Monitored Season 0 (2)
┃ Type  ┃ ID ┃ Title        ┃ Path              ┃ Downloaded ┃ Missing ┃ Subtitles  ┃ Size   ┃
│ 📺 TV │ 42 │ Breaking Bad │ /media/TV Shows/… │ 5          │ 2       │ 5 en, 5 fr │ 2.4 GB │
│ 📺 TV │ 43 │ The Office   │ /media/TV Shows/… │ 3          │ 1       │ 3 en       │ 856 MB │
Total size: 3.26 GB
```

**Theme mode example:**
```
Theme Music — 4 items (3 series, 1 movies)
┃ Type    ┃ ID ┃ Title        ┃ Path              ┃ theme.mp3 ┃ Size    ┃
│ 📺 TV   │ 42 │ Breaking Bad │ /media/TV Shows/… │ ✓ Yes     │ 3.84 MB │
│ 📺 TV   │ 43 │ The Office   │ /media/TV Shows/… │ ✗ No      │ -       │
│ 🎬 Movie│ 12 │ Inception    │ /media/Movies/…   │ ✗ No      │ -       │
Summary: 1 with theme.mp3  2 missing
```

---

## `list-themes`

Dedicated shortcut to display `theme.mp3` download status for every series and movie that has at least one downloaded file.

Equivalent to `list --mode theme`.

```bash
# Basic table (Type / ID / Title / Path / theme.mp3 / Size)
python extrarrfin.py list-themes

# Filter by name or Sonarr/Radarr ID
python extrarrfin.py list-themes --limit "Stranger Things"
python extrarrfin.py list-themes -l 42
```

### `--more-info` / `-i`

Add two extra columns — **Year** and **Network / Studio** — which are exactly the fields needed to write a new test case in `tests/test_youtube_search.py`:

```bash
python extrarrfin.py list-themes --more-info
python extrarrfin.py list-themes -i --limit "Stranger"
```

**Example output with `--more-info`:**
```
Theme Music — 3 items (2 series, 1 movies)
┃ Type    ┃ ID ┃ Title          ┃ Year ┃ Network / Studio ┃ Path   ┃ theme.mp3 ┃ Size    ┃
│ 📺 TV   │ 1  │ Stranger Things│ 2016 │ Netflix          │ /…     │ ✓ Yes     │ 3.84 MB │
│ 📺 TV   │ 2  │ The Last of Us │ 2023 │ HBO              │ /…     │ ✗ No      │ -       │
│ 🎬 Movie│ 10 │ Dune           │ 2021 │ Legendary Pictur │ /…     │ ✓ Yes     │ 4.12 MB │

Summary: 2 with theme.mp3  1 missing
```

---

## `download`

Download missing Season 0 episodes and/or extras for tagged series/movies.

> **💡** Incomplete `.part` files are automatically cleaned up after failed downloads.

```bash
# Download all missing Season 0 episodes
python extrarrfin.py download

# Dry-run (simulation, no actual download)
python extrarrfin.py download --dry-run

# Tag mode: behind-the-scenes for tagged series/movies
python extrarrfin.py download --mode tag

# Both Season 0 and extras
python extrarrfin.py download --mode season0 --mode tag

# Limit to one series/movie
python extrarrfin.py download --limit "Breaking Bad"
python extrarrfin.py download --limit 42

# Target a specific episode number
python extrarrfin.py download --limit "Breaking Bad" --episode 5

# Force re-download even if file exists
python extrarrfin.py download --force

# Verbose mode (shows scoring details)
python extrarrfin.py download --verbose

# Don't trigger Sonarr scan after download
python extrarrfin.py download --no-scan

# Trigger Jellyfin refresh after download
python extrarrfin.py download --jellyfin-url http://localhost:8096 --jellyfin-api-key YOUR_KEY
```

> **💡 Tip:** Use `--verbose` to understand why a video was selected or rejected.  
> See [SCORING.md](../SCORING.md) for scoring details.

---

## `theme`

Search YouTube for `Theme <title>` and save the result as `theme.mp3` in the root folder of each series/movie.  
→ See full documentation: [docs/theme-mode.md](theme-mode.md)

```bash
python extrarrfin.py theme
python extrarrfin.py theme --limit "Breaking Bad"
python extrarrfin.py theme --dry-run
python extrarrfin.py theme --force
```

---

## `scan`

Trigger a manual Sonarr rescan for a specific series.

```bash
python extrarrfin.py scan 42
python extrarrfin.py scan 42 --dry-run
```

---

## `schedule-mode`

Run downloads automatically at a configurable interval.

```bash
# Use settings from config.yaml
python extrarrfin.py schedule-mode

# Override interval
python extrarrfin.py schedule-mode --interval 30 --unit minutes
python extrarrfin.py schedule-mode --interval 6 --unit hours

# With other options
python extrarrfin.py schedule-mode --limit "Series" --verbose --dry-run
```

Schedule mode:
- Runs immediately on start
- Executes downloads at the specified interval
- Continues until stopped with `Ctrl+C`

> For long-running setups, see [systemd / cron examples](advanced.md).

---

## Common use cases

### First use
```bash
python extrarrfin.py test
python extrarrfin.py download --dry-run
python extrarrfin.py download
```

### Test with a single series
```bash
python extrarrfin.py list --limit "Breaking Bad"
python extrarrfin.py download --limit "Breaking Bad" --dry-run
python extrarrfin.py download --limit "Breaking Bad"
```

### Download extras for a movie (Radarr)
```bash
# Tag the movie in Radarr with "want-extras", then:
python extrarrfin.py download --mode tag --limit "Inception" --dry-run
python extrarrfin.py download --mode tag --limit "Inception"
```

### Download all themes
```bash
python extrarrfin.py theme --dry-run
python extrarrfin.py theme
```

### Mixed workflow (Season 0 + Extras)
```bash
python extrarrfin.py download --mode season0 --mode tag
```

### Re-download existing files
```bash
python extrarrfin.py download --limit "Series Name" --force
```
