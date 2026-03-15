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
| 1 | **[ThemerrDB](https://app.lizardbyte.dev/ThemerrDB/)** | Direct JSON lookup by TVDB ID (series) or TMDB ID (movies). Returns a curated YouTube URL. |
| 2 | **[TelevisionTunes](https://www.televisiontunes.com/)** | Search by title, pick the best match, download the MP3 directly or via yt-dlp. |
| 3 | **YouTube** (fallback) | Scored search for `main theme "<title>"` via yt-dlp + the internal `VideoScorer`. |

3. Download the audio and convert to **MP3 at 192 kbps** using yt-dlp + FFmpeg.

> **Note:** ThemerrDB requires a valid TVDB ID (series) or TMDB ID (movie) to be set in Sonarr/Radarr. If the ID is missing, this source is skipped automatically.

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

# Verbose mode
python extrarrfin.py theme --verbose
```

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
- **ThemerrDB** provides the most accurate results as themes are curated manually. It requires a TVDB ID (series) or TMDB ID (movie) to be present in Sonarr/Radarr.
- **TelevisionTunes** SSL certificate may be expired; certificate verification is intentionally disabled for this source.
- **YouTube** is the last-resort fallback. The search query is `main theme "<exact title>"` and results are scored by the internal `VideoScorer` (see [SCORING.md](../SCORING.md)).
- Audio quality: MP3 at 192 kbps.
- Re-running `theme` is safe: existing `theme.mp3` files are skipped automatically.  
  Use `--force` to overwrite them.
