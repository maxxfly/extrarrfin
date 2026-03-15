# 📝 Subtitle Management

← [Back to README](../README.md)

ExtrarrFin automatically downloads and manages subtitles alongside every video it downloads.

---

## Features

- **Auto-download** when available on YouTube
- **Multiple languages** with configurable priority order
- **Smart fallback**: manual subtitles first, then auto-generated
- **Format conversion**: all subtitles converted to SRT
- **Dual output**: subtitles are both embedded in the video file and saved as separate `.srt` files

---

## Configuration

```yaml
# Priority language list (downloaded in this order)
subtitle_languages:
  - "fr"      # French
  - "en"      # English
  - "fr-FR"   # French (France)
  - "en-US"   # English (US)
  - "en-GB"   # English (UK)
  - "de"      # German
  - "es"      # Spanish
  - "it"      # Italian
  - "pt"      # Portuguese

# Set to true to download ALL available languages
download_all_subtitles: false
```

Or via environment variable:
```bash
export SUBTITLE_LANGUAGES="fr,en,de,es"
export DOWNLOAD_ALL_SUBTITLES="false"
```

---

## Language codes

Use ISO 639-1 codes or regional variants:

| Code | Language |
|------|----------|
| `fr` / `fr-FR` / `fr-CA` | French |
| `en` / `en-US` / `en-GB` | English |
| `de` | German |
| `es` / `es-ES` / `es-MX` | Spanish |
| `it` | Italian |
| `pt` / `pt-BR` / `pt-PT` | Portuguese |
| `ja` | Japanese |
| `ko` | Korean |
| `zh` | Chinese |

---

## Common configurations

**French content with English fallback:**
```yaml
subtitle_languages: ["fr", "fr-FR", "en"]
```

**All available languages:**
```yaml
download_all_subtitles: true
```

**Multi-language setup:**
```yaml
subtitle_languages: ["fr", "en", "es", "de", "it"]
download_all_subtitles: false
```

---

## Output files

Subtitles are saved as:

```
Breaking Bad/Specials/
├── Breaking Bad - S00E01 - Pilot.mp4      ← subtitles embedded inside
├── Breaking Bad - S00E01 - Pilot.fr.srt   ← external French subtitles
└── Breaking Bad - S00E01 - Pilot.en.srt   ← external English subtitles
```

This ensures maximum compatibility with Jellyfin, Plex, Emby, Kodi, and other media servers.
