# 📺 STRM File Mode

← [Back to README](../README.md)

STRM mode creates small `.strm` text files instead of downloading videos. Your media server streams content directly from YouTube on playback.

---

## What is a STRM file?

A `.strm` file is a plain-text file containing a single URL. When a compatible media server opens it, it streams the content from that URL rather than playing a local file.

---

## Enable STRM mode

In `config.yaml`:
```yaml
use_strm_files: true
```

Or via environment variable:
```bash
export USE_STRM_FILES=true
```

---

## Benefits vs limitations

| ✅ Benefits | ⚠️ / 🔴 Limitations |
|------------|---------------------|
| Saves disk space (50 bytes vs 1+ GB) | Requires active internet for playback |
| Instant "download" | Content must remain available on YouTube |
| Subtitles still downloaded as `.srt` | URLs expire after **~6 hours** |
| | Stream URLs are IP-signed — remote clients cannot play them |
| | Not all media servers support STRM equally |

---

## File structure comparison

**Normal mode (MP4 download):**
```
Breaking Bad/Specials/
└── Breaking Bad - S00E01 - Pilot.mp4   (1.2 GB)
```

**STRM mode:**
```
Breaking Bad/Specials/
├── Breaking Bad - S00E01 - Pilot.strm   (50 bytes)
├── Breaking Bad - S00E01 - Pilot.fr.srt
└── Breaking Bad - S00E01 - Pilot.en.srt
```

Content of the `.strm` file:
```
https://www.youtube.com/watch?v=...
```

---

## Media server compatibility

| Media Server | STRM Support | Notes |
|-------------|--------------|-------|
| **Jellyfin** | ✅ Excellent | Full support |
| **Emby** | ✅ Good | Supported with minor limitations |
| **Kodi** | ✅ Excellent | Native support |
| **Plex** | ⚠️ Limited | Requires Plex Pass, may be unstable |

---

## URL expiration — important

YouTube stream URLs expire after approximately **6 hours**. You must regenerate them periodically:

**Manual refresh:**
```bash
python extrarrfin.py download --force
```

**Automated refresh with cron:**
```bash
# Refresh every 4 hours
0 */4 * * * cd /path/to/extrarrfin && python extrarrfin.py download --no-scan
```

> ⚠️ STRM URLs are IP-signed for the server that generated them.  
> Remote users on a different IP **cannot** play STRM files.  
> If you have remote users, download MP4 files instead.

---

## When to use STRM mode?

**Good use cases:**
- Limited disk space
- One-time viewing content (behind-the-scenes, interviews)
- Testing before committing disk space

**Not recommended for:**
- Main episodes you want to keep long-term
- Areas with unreliable internet
- Content with remote users

---

## Switching between modes

To convert existing MP4 files to STRM (or vice versa):

```bash
# 1. Change use_strm_files in config.yaml
# 2. Force re-download
python extrarrfin.py download --force --limit "Series Name"
```

`--force` will delete the existing video/STRM file and create the new format. Subtitle files are always refreshed.
