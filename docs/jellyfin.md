# 📺 Jellyfin Integration

← [Back to README](../README.md)

ExtrarrFin can automatically trigger a Jellyfin library refresh after downloading new content, so your media server recognises new files immediately.

---

## Configuration

Add to `config.yaml`:
```yaml
jellyfin_url: "http://localhost:8096"
jellyfin_api_key: "your_jellyfin_api_key_here"
```

Or via environment variables:
```bash
export JELLYFIN_URL="http://localhost:8096"
export JELLYFIN_API_KEY="your_jellyfin_api_key_here"
```

Or as CLI arguments:
```bash
python extrarrfin.py download \
  --jellyfin-url http://localhost:8096 \
  --jellyfin-api-key YOUR_KEY
```

---

## Getting your API key

1. Open your Jellyfin web interface
2. Go to **Dashboard** → **API Keys**
3. Click **+**, give it a name (e.g. "ExtrarrFin")
4. Copy the generated key

---

## How it works

- The refresh is triggered **only after at least one successful download**
- It is **skipped in dry-run mode**
- If Jellyfin is unreachable, ExtrarrFin continues without error

---

## Test the connection

```bash
python extrarrfin.py test
```

Expected output:
```
Testing Jellyfin connection...
  URL: http://localhost:8096
  ✓ Jellyfin connection successful!
  Server: My Jellyfin Server  v10.8.13
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Refresh fails | Verify the URL is correct and Jellyfin is running |
| Invalid API key | Re-generate the key in Dashboard → API Keys |
| Timeout | Check network connectivity between ExtrarrFin and Jellyfin |

> Jellyfin integration is completely optional. ExtrarrFin works normally without it.
