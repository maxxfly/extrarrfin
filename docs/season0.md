# 📺 Season 0 Mode

← [Back to README](../README.md)

Season 0 mode is the default download mode. It downloads **special episodes** (Season 0) from your Sonarr library by searching YouTube.

---

## Selection criteria

An episode will be downloaded only if **all** conditions are met:

| Condition | Details |
|-----------|---------|
| ✅ Series is monitored | The series must have the "Monitored" flag enabled in Sonarr |
| ✅ Episode is monitored | The individual Season 0 episode must be marked as monitored |
| ✅ Episode has no file | The episode must not already have a file attached in Sonarr |

Use `--force` to re-download episodes that already have a file.

---

## What is Season 0?

Season 0 (also called "Specials") typically includes:

- 🎬 Behind-the-scenes footage
- 🎤 Interviews with cast and crew
- 🎭 Deleted scenes and outtakes
- 📺 Pilot episodes and unaired pilots
- 🎉 Holiday specials and crossover episodes
- 🎥 Featurettes and making-of documentaries
- 📰 Recap episodes and previews

---

## YouTube search strategy

For each missing episode, ExtrarrFin searches in two steps:

1. **`"Series Name" + "Episode Title"`**  
   e.g. `Breaking Bad Behind the Scenes`

2. **`"Episode Title"` only** (fallback if step 1 returns no results)  
   e.g. `Behind the Scenes`

Results are scored by an intelligent algorithm — only videos above `min_score` (default: 50.0) are accepted.  
→ See [SCORING.md](../SCORING.md) for full scoring documentation.

---

## Download process

For each matched episode:

1. ⬇️ Download video from YouTube (best quality MP4)
2. 📝 Download subtitles (configurable languages)
3. 🎬 Convert subtitles to SRT format
4. 💾 Save as `Series Name - S00E01 - Episode Title.mp4`
5. 📁 Place in `/path/to/series/Specials/`
6. 🔄 Trigger Sonarr rescan (unless `--no-scan`)

---

## File structure

```
/path/to/series/Breaking Bad/
└── Specials/
    ├── Breaking Bad - S00E01 - Pilot.mp4
    ├── Breaking Bad - S00E01 - Pilot.fr.srt
    ├── Breaking Bad - S00E01 - Pilot.en.srt
    ├── Breaking Bad - S00E01 - Pilot.nfo
    └── Breaking Bad - S00E02 - Inside Breaking Bad.mp4
```

Naming format: `{SeriesName} - S{Season:02d}E{Episode:02d} - {EpisodeTitle}.{ext}`

---

## Example workflow

```
Monitored series in Sonarr: "Breaking Bad"
├─ Season 0 (Specials)
│  ├─ S00E01 "Pilot" .................. [monitored, no file] → ✅ Will download
│  ├─ S00E02 "Inside Breaking Bad" .... [monitored, no file] → ✅ Will download
│  ├─ S00E03 "Making of Season 1" ..... [NOT monitored] ...... → ❌ Skipped
│  └─ S00E04 "Deleted Scenes" ......... [monitored, has file] → ❌ Skipped (already exists)
```

Only S00E01 and S00E02 will be downloaded.

---

## Commands

```bash
# Download all missing Season 0 episodes
python extrarrfin.py download

# Dry-run
python extrarrfin.py download --dry-run

# Limit to one series
python extrarrfin.py download --limit "Breaking Bad"

# Target a specific episode
python extrarrfin.py download --limit "Breaking Bad" --episode 2

# Force re-download
python extrarrfin.py download --force

# Verbose (show scoring details)
python extrarrfin.py download --verbose
```
