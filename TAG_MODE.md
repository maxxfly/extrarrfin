# Tag Mode - Documentation

## Description

Tag mode allows automatic downloading of "behind the scenes" videos for series and movies marked with the `want-extras` or `want_extras` tag in Sonarr/Radarr.

### Supported Media Types

- **TV Series** - via Sonarr (downloads behind-the-scenes, making of, featurettes)
- **Movies** - via Radarr (downloads behind-the-scenes, making of, deleted scenes, bloopers)

## Differences from Season 0 Mode

### Season 0 Mode (default)
- Downloads special episodes (Season 0) monitored in Sonarr
- Uses TMDB listing to find episode titles
- Saves in the `Specials` folder
- Searches YouTube: "series name + episode title"

### Tag Mode
- Downloads "behind the scenes" videos for series/movies with the `want-extras` or `want_extras` tag
- Works with both Sonarr (series) and Radarr (movies)
- Does NOT depend on TMDB listing
- Saves in the `extras` folder within the series/movie directory
- Searches YouTube: "series/movie name - behind the scenes"
- Uses scoring system to avoid bad videos

## Configuration

### In config.yaml file

```yaml
# Operating mode: "season0" (default) or "tag" or both
mode: "tag"

# Or run both modes
mode: ["season0", "tag"]

# Radarr configuration (optional - for movie extras)
radarr:
  url: "http://localhost:7878"
  api_key: "your_radarr_api_key"
  directory: "/path/to/movies"  # Path where Radarr stores movies
```

### Via command line

```bash
# Use tag mode for a command
python extrarrfin.py download --mode tag

# Use season0 mode (default)
python extrarrfin.py download --mode season0

# Run BOTH modes at once
python extrarrfin.py download --mode season0 --mode tag

# List series with want-extras tag
python extrarrfin.py list --mode tag

# List series with both modes
python extrarrfin.py list --mode season0 --mode tag
```

## Usage

### 1. Add tag in Sonarr/Radarr

**For Series (Sonarr):**
1. In Sonarr, go to Settings > Tags
2. Create a new tag named `want-extras` or `want_extras`
3. Add this tag to series for which you want to download extras

**For Movies (Radarr):**
1. In Radarr, go to Settings > Tags
2. Create a new tag named `want-extras` or `want_extras`
3. Add this tag to movies for which you want to download extras

### 2. List eligible series/movies

```bash
# List tagged series and movies
python extrarrfin.py list --mode tag

# With Radarr support (if configured)
python extrarrfin.py list --mode tag
```

### 3. Download extras

```bash
# Download for all series/movies with the tag
python extrarrfin.py download --mode tag

# Download for a specific series or movie
python extrarrfin.py download --mode tag --limit "Breaking Bad"
python extrarrfin.py download --mode tag --limit "Inception"

# Dry-run mode for testing
python extrarrfin.py download --mode tag --dry-run

# Verbose mode to see details
python extrarrfin.py download --mode tag --verbose

# Force re-download
python extrarrfin.py download --mode tag --force
```

### 4. Schedule mode

```bash
# Run automatically every hour
python extrarrfin.py schedule-mode --mode tag --interval 1 --unit hours
```

## Scoring System

Tag mode uses an advanced scoring system to select the best videos:

### Positive Points (+)
- +50: Contains "behind the scenes", "bts", "making of", "backstage", "featurette"
- +50: Network/Studio name in title (official content)
- +50: Channel matches network/studio
- +40: Contains series/movie title
- +40: VFX breakdown content
- +40: Known BTS channels (FilmIsNow, Rotten Tomatoes, IGN, etc.)
- +30: Word matching ratio
- +20: Official indicators (official, vevo, verified)
- +15: Short title (less likely to be a compilation)
- +15: Character/actor focused BTS content

### Negative Points (-)
- -80: Other movie/series title before target name
- -60: Educational/unrelated content
- -50: Unrelated channel types (schools, museums, etc.)
- -40: Trailer without BTS content
- -30: Undesired keywords (compilation, playlist, reaction, review, ending explained, theories, etc.)

### Minimum Threshold
Only videos with a score ≥ 65 points are downloaded.

### Duplicate Detection
The system removes duplicates based on:
- Title similarity > 80% (Jaccard similarity)
- Duration proximity (< 30 seconds or < 10% difference)

Among duplicates, the video with the highest score is kept.

## File Structure

### For Series

Extras are saved in the following format:

```
/path/to/series/
├── Season 01/
├── Season 02/
└── extras/
    ├── SeriesName - VideoTitle.mp4
    ├── SeriesName - VideoTitle.nfo
    ├── SeriesName - VideoTitle.fr.srt
    ├── SeriesName - AnotherVideo.mp4
    ├── SeriesName - AnotherVideo.nfo
    └── SeriesName - AnotherVideo.en.srt
```

### For Movies

Extras are saved in the following format:

```
/path/to/movies/
└── Movie Name (2023)/
    ├── Movie Name (2023).mp4          # Main movie file
    └── extras/
        ├── Movie Name (2023) - Behind the Scenes.mp4
        ├── Movie Name (2023) - Behind the Scenes.nfo
        ├── Movie Name (2023) - Making Of.mp4
        ├── Movie Name (2023) - Making Of.nfo
        └── Movie Name (2023) - Interviews.mp4
```

### NFO Files

Each video has an accompanying `.nfo` file containing metadata:
- YouTube URL
- Video title
- Channel/Studio
- Description
- Duration
- Video ID

## Limitations

1. The `--episode` option is not compatible with tag mode
2. Tag mode downloads up to 20 videos per series/movie (best rated)
3. Videos must have a minimum score of 65 points to be downloaded
4. After duplicate removal, typically 9-15 unique videos are kept per series/movie
5. Radarr support is optional - ExtrarrFin works fine with Sonarr only if Radarr is not configured

## Complete Examples

### Example 1: Hybrid Configuration (Series Only)

```yaml
# config.yaml
mode: "season0"  # Default mode
```

```bash
# Download season 0 normally
python extrarrfin.py download

# Also download extras for certain series
python extrarrfin.py download --mode tag

# Or run both at once
python extrarrfin.py download --mode season0 --mode tag
```

### Example 2: Both Series and Movies

```yaml
# config.yaml
mode: ["season0", "tag"]

# Add Radarr for movie support
radarr:
  url: "http://localhost:7878"
  api_key: "your_radarr_api_key"
  directory: "/path/to/movies"
```

```bash
# All commands process both series and movies
python extrarrfin.py list
python extrarrfin.py download
```

### Example 3: Tag Mode Only (Series + Movies)

```yaml
# config.yaml
mode: "tag"

# Configure both services
sonarr:
  url: "http://localhost:8989"
  api_key: "your_sonarr_api_key"

radarr:
  url: "http://localhost:7878"
  api_key: "your_radarr_api_key"
  directory: "/path/to/movies"
```

```bash
# All commands use tag mode for both series and movies
python extrarrfin.py list
python extrarrfin.py download
```

### Example 4: Complete Automation

```bash
# Schedule to download both season 0 AND extras every 6 hours
python extrarrfin.py schedule-mode --mode season0 --mode tag --interval 6 --unit hours &
```

## Troubleshooting

### No Series/Movies Found

Check that:
1. The `want-extras` or `want_extras` tag exists in Sonarr/Radarr
2. The tag is assigned to at least one series or movie
3. The connection to Sonarr/Radarr works: `python extrarrfin.py test`
4. If using Radarr, verify the configuration in config.yaml

### No Videos Found

- Search criteria are strict to avoid bad videos
- Try verbose mode: `--verbose` to see scoring details
- Some series/movies may not have "behind the scenes" content on YouTube
- The scoring system may filter out low-quality content

### Inappropriate Videos Downloaded

- Use verbose mode to see scores
- Videos with words like "reaction", "review", "compilation" are penalized
- Report problematic cases to improve the scoring system

### Duplicate Videos

- The system automatically detects and removes duplicates
- Duplicates are identified by title similarity (>80%) and duration proximity
- Use `--verbose` to see which videos are marked as duplicates

### Radarr Not Working

- Verify Radarr URL and API key in config.yaml
- Check `python extrarrfin.py test` output for Radarr connection status
- Ensure the `radarr.directory` path matches your actual movie directory
- Radarr is optional - the tool works fine without it

## Known BTS Channels

The scoring system recognizes these channels as legitimate BTS content sources:
- FilmIsNow (all variants)
- Rotten Tomatoes
- IGN
- Entertainment Weekly
- Collider
- ComicBook.com
- Screen Rant
- Variety
- The Hollywood Reporter
- Deadline
- Den of Geek
- SyFy
- Nerdist
- Movie Trailers Source
- JoBlo

Videos from these channels receive a +40 point bonus.
