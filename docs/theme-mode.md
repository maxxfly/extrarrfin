# 🎵 Theme Music Mode

← [Back to README](../README.md)

The `theme` command automatically downloads the musical theme of each series and movie as a `theme.mp3` file, saved directly in the root folder of each title.

---

## How it works

1. For each series (from Sonarr) and movie (from Radarr, if configured):
   - Check whether `theme.mp3` already exists → **skip if found**
   - Search YouTube for `Theme <title>` (e.g. `Theme Breaking Bad`)
   - Download the first result as `theme.mp3` (MP3, 192 kbps) via yt-dlp + FFmpeg

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
- The search query is always `Theme <exact title>` — the first YouTube result is used.
- Audio quality: MP3 at 192 kbps.
- Re-running `theme` is safe: existing `theme.mp3` files are skipped automatically.  
  Use `--force` to overwrite them.
