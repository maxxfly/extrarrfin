# 🎵 Theme Music Mode

← [Back to README](../README.md)

The `theme` command automatically downloads the musical theme of each series and movie as a `theme.mp3` file, saved directly in the root folder of each title.

---

## How it works

For each series (from Sonarr) and movie (from Radarr, if configured), the following steps are performed:

1. Check whether `theme.mp3` already exists → **skip if found**
2. Try **three sources in order** (first success wins):

| Priority | Source | Method |
|----------|--------|--------|
| 1 | **[ThemerrDB](https://app.lizardbyte.dev/ThemerrDB/)** | Curated JSON lookup by TMDB ID (series and movies), with the IMDb ID as an alternate key for movies. Returns a curated YouTube URL. |
| 2 | **[TelevisionTunes](https://www.televisiontunes.com/)** | Search by title, pick the best match, download the MP3 directly or via yt-dlp. |
| 3 | **YouTube** (fallback) | Scored search for `main theme "<title>"` via yt-dlp + the internal `VideoScorer`. |

3. Download the audio and convert to **MP3 at 192 kbps** using yt-dlp + FFmpeg.

> **Note:** ThemerrDB indexes series by **TMDB ID** (not TVDB ID), so a valid TMDB ID must be set in Sonarr/Radarr. If the ID is missing, this source is skipped automatically.
>
> The JSON files are read from the same origin the ThemerrDB web app uses
> (`app.lizardbyte.dev/ThemerrDB/…`), with `raw.githubusercontent.com/LizardByte/ThemerrDB/gh-pages`
> as an automatic fallback.

---

## Storage location

The file is saved in the **root folder** of each series or movie (not in a subfolder):

```
/path/to/series/Breaking Bad/
├── Season 1/
├── Specials/
├── extras/
└── theme.mp3          ← here

/path/to/movies/Inception (2010)/
├── Inception (2010).mp4
├── extras/
└── theme.mp3          ← here
```

---

## Commands

```bash
# Download themes for all series and movies
python extrarrfin.py theme

# Limit to a specific title (by name or ID)
python extrarrfin.py theme --limit "Breaking Bad"
python extrarrfin.py theme --limit "Inception"
python extrarrfin.py theme --limit 42

# Dry-run (show what would be done, no download)
python extrarrfin.py theme --dry-run

# Force re-download even if theme.mp3 already exists
python extrarrfin.py theme --force

# Curated sources only — never fall back to a YouTube search
python extrarrfin.py theme --no-fallback

# Curated sources only, and see which source answered
python extrarrfin.py theme --no-fallback --verbose

# Verbose mode
python extrarrfin.py theme --verbose
```

---

## Skipping the YouTube fallback (`--no-fallback`)

By default a title is resolved from ThemerrDB, then TelevisionTunes, and
finally by a **scored YouTube search**. That last step is a best-effort guess:
the scorer can pick a cover, an orchestral arrangement, or an unrelated video
that shares a keyword (see [SCORING.md](../SCORING.md)).

`--no-fallback` restricts resolution to the two **curated** sources:

```bash
python extrarrfin.py theme --no-fallback
```

| | Default | `--no-fallback` |
|---|---|---|
| Sources used | ThemerrDB → TelevisionTunes → YouTube | ThemerrDB → TelevisionTunes |
| Result quality | curated, or a scored guess | curated only |
| Unknown title | theme downloaded from YouTube | reported as **failed** |
| Speed | YouTube search per miss | fast, no search |

Use it when you prefer no theme over a wrong theme, or to pre-fill a library
with only verified matches and handle the rest manually. Expect a higher
failure count: on a library of 86 series / 343 movies, roughly 40 % of series
and 65 % of movies have no curated theme and will be reported failed.

The flag is also accepted by `download --mode theme` and `schedule-mode`.

> **Note:** TelevisionTunes only covers TV shows, so for **movies** `--no-fallback`
> effectively means ThemerrDB only. A movie without a TMDB/IMDb id therefore has
> no curated source at all and fails immediately.

---

## Listing theme status

Use `list --mode theme` to see which series/movies already have a `theme.mp3`:

```bash
python extrarrfin.py list --mode theme
python extrarrfin.py list --mode theme --limit "Breaking Bad"
```

**Example output:**
```
Theme Music — 4 items (3 series, 1 movies)
┃ Type    ┃ ID ┃ Title        ┃ Path              ┃ theme.mp3 ┃ Size    ┃
│ 📺 TV   │ 42 │ Breaking Bad │ /media/TV Shows/… │ ✓ Yes     │ 3.84 MB │
│ 📺 TV   │ 43 │ The Office   │ /media/TV Shows/… │ ✗ No      │ -       │
│ 📺 TV   │ 88 │ Stranger Thi│ /media/TV Shows/… │ ✓ Yes     │ 4.12 MB │
│ 🎬 Movie│ 12 │ Inception    │ /media/Movies/…   │ ✗ No      │ -       │

Summary: 2 with theme.mp3  2 missing
```

---

## Example download output

```
Downloading theme: Breaking Bad  → /media/TV Shows/Breaking Bad
  ✓ Saved to /media/TV Shows/Breaking Bad/theme.mp3

Downloading theme: The Office  → /media/TV Shows/The Office
  ✓ Saved to /media/TV Shows/The Office/theme.mp3

Theme download summary:
  Total:   2
  Success: 2
  Failed:  0
```

---

## Notes

- Radarr is **optional**. If not configured, only series themes are downloaded.
- Sources are tried in order — the first successful download wins. Errors from earlier sources are reported only if all sources fail.
- **ThemerrDB** provides the most accurate results as themes are curated manually. It looks series up by **TMDB ID** and movies by TMDB ID (IMDb ID as an alternate key). If no TMDB/IMDb ID is present in Sonarr/Radarr, this source is skipped.
- **ThemerrDB coverage** on a real library (measured on 86 series / 343 movies): ~60 % of series and ~35 % of movies have a curated theme. The remaining titles fall through to TelevisionTunes / YouTube.
- **TelevisionTunes** SSL certificate may be expired; certificate verification is intentionally disabled for this source.
- **YouTube** is the last-resort fallback. The search query is `main theme "<exact title>"` and results are scored by the internal `VideoScorer` (see [SCORING.md](../SCORING.md)).
- Audio quality: MP3 at 192 kbps.
- Re-running `theme` is safe: existing `theme.mp3` files are skipped automatically.  
  Use `--force` to overwrite them.

---

## Tests

```bash
# All offline tests (no network needed)
make test-unit

# Offline unit tests for the ThemerrDB client (no network needed)
.venv/bin/pytest tests/test_themerrdb.py -v

# Offline tests for --no-fallback (source chain + CLI wiring)
.venv/bin/pytest tests/test_theme_no_fallback.py tests/test_theme_no_fallback_cli.py -v

# Integration tests: real ThemerrDB lookup, real theme.mp3 download, and the
# curated-only (--no-fallback) behaviour
.venv/bin/pytest tests/test_themerrdb_download.py -v -m integration
```

See the docstring of [tests/test_themerrdb_download.py](../tests/test_themerrdb_download.py) for how to refresh the expected URLs when ThemerrDB curates a different video.
