# 📝 Advanced Usage

← [Back to README](../README.md)

---

## Directory mapping

Use this when ExtrarrFin runs on a **different machine** than Sonarr/Radarr (e.g. on the NAS host while Sonarr runs in Docker).

Sonarr reports paths like `/tv/Breaking Bad` (its internal container path), but the actual location on your machine might be `/mnt/nas/media/TV Shows/Breaking Bad`.

Configure the mapping:

```yaml
# Path as seen by Sonarr/Radarr
sonarr_directory: "/tv"
radarr_directory: "/movies"

# Real path on the machine running ExtrarrFin
media_directory: "/mnt/nas/media/TV Shows"
```

ExtrarrFin will automatically convert:  
`/tv/Breaking Bad` → `/mnt/nas/media/TV Shows/Breaking Bad`

---

## Schedule mode with systemd

For a persistent, auto-restarting service:

```bash
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
ExecStart=/home/user/extrarrfin/.venv/bin/python \
  /home/user/extrarrfin/extrarrfin.py \
  --config /home/user/extrarrfin/config.yaml \
  schedule-mode
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable extrarrfin
sudo systemctl start extrarrfin
sudo systemctl status extrarrfin
sudo journalctl -u extrarrfin -f
```

---

## Automation with cron

One-time runs on a schedule (alternative to schedule-mode):

```bash
crontab -e
```

```cron
# Run every day at 2 AM
0 2 * * * cd /home/user/extrarrfin && .venv/bin/python extrarrfin.py --config config.yaml download >> /var/log/extrarrfin.log 2>&1

# Refresh STRM URLs every 4 hours (if using STRM mode)
0 */4 * * * cd /home/user/extrarrfin && .venv/bin/python extrarrfin.py --config config.yaml download --no-scan >> /var/log/extrarrfin.log 2>&1
```

---

## Wrapper script

```bash
#!/bin/bash
# /usr/local/bin/extrarrfin-run.sh

cd /home/user/extrarrfin
source .venv/bin/activate
python extrarrfin.py download --log-level INFO
deactivate
```

```bash
chmod +x /usr/local/bin/extrarrfin-run.sh
```

---

## Troubleshooting

### No video found on YouTube

The tool searches in two steps:
1. `"Series name" + "Episode title"`
2. `"Episode title"` only (fallback)

If still no results:
- Check episode names are accurate in Sonarr
- Lower `min_score` in config (try 40-45)
- Increase `youtube_search_results` (try 15)
- Verify network access to YouTube

```bash
# Debug with verbose mode
python extrarrfin.py download --limit "Series Name" --verbose --dry-run
```

→ See [SCORING.md](../SCORING.md) for detailed scoring documentation.

### Sonarr connection error

```bash
python extrarrfin.py test
```

- Verify the URL includes the port (e.g. `http://localhost:8989`)
- Check the API key in Sonarr → Settings → General
- Ensure the Sonarr instance is reachable from this machine

### FFmpeg not found

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### Incorrect file paths

Configure directory mapping (see [Directory mapping](#directory-mapping) above):

```yaml
media_directory: "/your/real/path"
sonarr_directory: "/path/as/seen/by/sonarr"
```

### Rate limiting (429 errors)

ExtrarrFin already adds delays between requests. If you still hit limits:
- Lower `youtube_search_results` to reduce API calls
- Increase `schedule_interval` to run less frequently
- Use `--limit` to process one series at a time
