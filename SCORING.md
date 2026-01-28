# 🎯 ExtrarrFin - Scoring System

ExtrarrFin uses a sophisticated scoring system to automatically identify and select the best YouTube videos matching the episodes you're looking for.

## 📊 Overview

The scoring system analyzes multiple criteria for each candidate YouTube video and calculates a total score. Only videos exceeding the configured minimum threshold are considered valid matches.

### Basic Configuration

```yaml
# Minimum score required to accept a video
min_score: 50.0

# Number of YouTube results to analyze
youtube_search_results: 10
```

**Parameters:**
- `min_score`: Minimum required score (default: 50.0)
  - Typical values: 40-70
  - Lower = more permissive, more false positives
  - Higher = stricter, risk of missing valid videos
- `youtube_search_results`: Number of videos to analyze (3-20, default: 10)
  - More results = better chances of finding a match
  - More processing time

## 🔍 Scoring Criteria

### 1. Title Match (up to 100 points)

The video title is compared to the episode title and series name.

**Bonuses:**
- ✅ Exact episode title match: **+50 points**
- ✅ Partial episode title match: **+25 points**
- ✅ Series name present in title: **+20 points**
- ✅ Episode title keywords present: **+5 points per keyword**

**Example:**
```
Series: "Breaking Bad"
Episode: "Pilot"

YouTube Title: "Breaking Bad: Pilot - Full Episode"
→ Exact match "Pilot": +50
→ "Breaking Bad" present: +20
→ Total: 70 points
```

### 2. Channel Name Match (up to 30 points)

The YouTube channel name is compared to the series' broadcast network.

**Bonuses:**
- ✅ Exact network name: **+30 points**
- ✅ Partial network name: **+15 points**
- ✅ Recognized official channel: **+10 points**

**Recognized official channels:**
- `official`, `hd`, `full episode`, `full episodes`
- Series name present in channel name

**Example:**
```
Network: "AMC"
YouTube Channel: "AMC Networks"
→ Partial match: +15 points
```

### 3. Video Duration (up to 20 points)

Favors videos with reasonable duration for an episode.

**Bonuses:**
- ✅ Duration between 5 and 120 minutes: **+20 points**
- ⚠️ Duration < 2 minutes: **-10 points** (likely a clip)
- ⚠️ Duration > 180 minutes: **-5 points** (likely a compilation)

**Example:**
```
Duration: 45 minutes
→ In optimal range: +20 points

Duration: 1 minute 30
→ Too short: -10 points
```

### 4. Quality Indicators (up to 25 points)

Detection of keywords in the title indicating official or quality content.

**Positive keywords (+5 points each):**
- `full episode`, `official`, `hd`, `behind the scenes`
- `documentary`, `featurette`, `interview`, `making of`
- `exclusive`, `original`, `complete`

**Negative keywords (-10 points each):**
- `reaction`, `review`, `commentary`, `recap`
- `trailer`, `preview`, `clip`, `scene`
- `fan made`, `parody`, `spoof`

**Example:**
```
Title: "Breaking Bad - Official Behind the Scenes HD"
→ "official": +5
→ "behind the scenes": +5
→ "hd": +5
→ Total: +15 points
```

### 5. View Count (up to 10 points)

Favors popular videos, which are generally of better quality.

**Scale:**
- ✅ 1M+ views: **+10 points**
- ✅ 500K+ views: **+8 points**
- ✅ 100K+ views: **+5 points**
- ✅ 50K+ views: **+3 points**
- ✅ 10K+ views: **+1 point**

**Example:**
```
Views: 2,500,000
→ Over 1M views: +10 points
```

### 6. Upload Date (up to 5 points)

Slight bonus for more recent videos (upload_date close to the episode's air date).

**Bonuses:**
- ✅ Uploaded within 30 days of air date: **+5 points**
- ✅ Uploaded within 90 days: **+3 points**
- ✅ Uploaded within the year: **+1 point**

### 7. Video Quality (up to 15 points)

Favors high-quality videos.

**Bonuses:**
- ✅ 1080p (HD) or better: **+15 points**
- ✅ 720p: **+10 points**
- ✅ 480p: **+5 points**
- ⚠️ Less than 360p: **-5 points**

**Example:**
```
Resolution: 1920x1080
→ 1080p: +15 points
```

## 🎓 Complete Scoring Examples

### Example 1: Perfect Match

```
Series: "Breaking Bad" (Network: AMC)
Episode: "Pilot"

YouTube Video:
- Title: "Breaking Bad: Pilot - Full Episode (Official HD)"
- Channel: "AMC"
- Duration: 47 minutes
- Views: 3,500,000
- Quality: 1080p

Score Calculation:
+ 50 : Exact title match
+ 20 : Series name present
+ 30 : Exact network (AMC)
+ 20 : Duration in optimal range
+ 10 : "full episode" + "official" + "hd"
+ 10 : Over 1M views
+ 15 : 1080p quality
─────
= 155 points ✅ EXCELLENT
```

### Example 2: Good Match

```
Series: "The Office" (Network: NBC)
Episode: "The Dundies"

YouTube Video:
- Title: "The Office - The Dundies (HD)"
- Channel: "Comedy Central"
- Duration: 22 minutes
- Views: 250,000
- Quality: 720p

Score Calculation:
+ 50 : Exact title match
+ 20 : Series name present
+  0 : No network match
+ 20 : Duration in optimal range
+  5 : "hd"
+  5 : Over 100K views
+ 10 : 720p quality
─────
= 110 points ✅ GOOD
```

### Example 3: Borderline Match

```
Series: "Friends"
Episode: "Behind the Scenes"

YouTube Video:
- Title: "Friends Behind Scenes"
- Channel: "TV Clips"
- Duration: 8 minutes
- Views: 45,000
- Quality: 480p

Score Calculation:
+ 25 : Partial title match
+ 20 : Series name present
+  0 : No network match
+ 20 : Duration in optimal range
+  5 : "behind the scenes"
+  0 : Less than 50K views
+  5 : 480p quality
─────
= 75 points ✅ ACCEPTABLE
```

### Example 4: Poor Match

```
Series: "Breaking Bad"
Episode: "Pilot"

YouTube Video:
- Title: "Breaking Bad Pilot - Fan Reaction and Review"
- Channel: "RandomReviewer"
- Duration: 15 minutes
- Views: 5,000
- Quality: 720p

Score Calculation:
+ 50 : Exact "Pilot" match
+ 20 : "Breaking Bad" present
+  0 : No network match
+ 20 : Duration in optimal range
- 20 : "reaction" + "review" (negative keywords)
+  0 : Less than 10K views
+ 10 : 720p quality
─────
= 80 points ⚠️ High score but wrong content!
```

**Note:** This example shows a system limitation - negative keyword presence should ideally reduce the score further.

### Example 5: Rejection

```
Series: "The Office"
Episode: "Pilot"

YouTube Video:
- Title: "Why The Office is the best show - Video Essay"
- Channel: "FilmCritic"
- Duration: 25 minutes
- Views: 100,000
- Quality: 1080p

Score Calculation:
+ 20 : "The Office" present
+  0 : No network match
+ 20 : Duration in optimal range
+  0 : No quality keywords
+  5 : Over 100K views
+ 15 : 1080p quality
─────
= 60 points (but no title match)
```

With `min_score: 70`, this video would be **rejected** ❌

## ⚙️ Advanced Configuration

### Adjusting the Minimum Threshold

The `min_score` parameter controls the system's selectivity:

```yaml
# Permissive - accepts more videos, risk of false positives
min_score: 40.0

# Balanced (recommended)
min_score: 50.0

# Strict - only accepts best matches
min_score: 70.0
```

**Recommendations by use case:**

| Use Case | min_score | Description |
|----------|-----------|-------------|
| **Initial test** | 40-45 | To see what would be downloaded |
| **Production** | 50-60 | Optimal balance |
| **Official content only** | 70-80 | Very selective |

### Adjusting the Number of Results

```yaml
# Fast search but less exhaustive
youtube_search_results: 5

# Balanced (recommended)
youtube_search_results: 10

# Exhaustive search
youtube_search_results: 20
```

**Impact:**
- More results = better chances of finding the perfect video
- Processing time proportional to number of results
- Beyond 15-20, gains are marginal

## 🔍 Verbose Mode

To understand how scoring works on your searches, use verbose mode:

```bash
python extrarrfin.py download --verbose --dry-run
```

**Detailed output:**
```
Downloading: Breaking Bad - S00E01 - Pilot
  Search query: 'Breaking Bad Pilot'
  [VERBOSE] Series network: AMC
  [VERBOSE] YouTube search query: 'Breaking Bad Pilot'
  [VERBOSE] Full search URL: ytsearch10:Breaking Bad Pilot
  
  [VERBOSE] Candidate 1: Breaking Bad: Pilot - Full Episode (Official)
  [VERBOSE]   - Title match: +50.0 (exact match)
  [VERBOSE]   - Series in title: +20.0
  [VERBOSE]   - Network match: +30.0 (AMC ~ AMC)
  [VERBOSE]   - Duration bonus: +20.0 (47 min)
  [VERBOSE]   - Quality indicators: +15.0 (official, full episode, hd)
  [VERBOSE]   - Views bonus: +10.0 (3.5M views)
  [VERBOSE]   - Quality bonus: +15.0 (1080p)
  [VERBOSE]   → Total score: 160.0
  
  [VERBOSE] Candidate 2: Breaking Bad Pilot Scene Compilation
  [VERBOSE]   - Title match: +50.0 (exact match)
  [VERBOSE]   - Series in title: +20.0
  [VERBOSE]   - Duration bonus: +20.0 (35 min)
  [VERBOSE]   - Quality indicators: -10.0 (clip)
  [VERBOSE]   - Views bonus: +5.0 (150K views)
  [VERBOSE]   - Quality bonus: +10.0 (720p)
  [VERBOSE]   → Total score: 95.0
  
  [VERBOSE] Candidate 3: Breaking Bad Review and Analysis
  [VERBOSE]   - Title match: +20.0 (series match only)
  [VERBOSE]   - Duration bonus: +20.0 (25 min)
  [VERBOSE]   - Quality indicators: -10.0 (review)
  [VERBOSE]   - Views bonus: +3.0 (75K views)
  [VERBOSE]   - Quality bonus: +10.0 (720p)
  [VERBOSE]   → Total score: 43.0 (below threshold)
  
  ✓ Selected: Breaking Bad: Pilot - Full Episode (Official)
  [VERBOSE] Match score: 160.0
  [VERBOSE] Video URL: https://www.youtube.com/watch?v=...
```

## 💡 Tips and Best Practices

### 1. Test Before Mass Downloading

```bash
# See which videos would be selected
python extrarrfin.py download --dry-run --verbose

# Test on a specific series
python extrarrfin.py download --limit "Breaking Bad" --dry-run --verbose
```

### 2. Adjust Progressively

Start with default values, then adjust based on results:

1. Launch with `min_score: 50.0`
2. Examine downloaded videos
3. If too many false positives → increase to `60-70`
4. If too many videos missed → decrease to `40-45`

### 3. Use Sonarr Metadata

Ensure your series in Sonarr have:
- ✅ Accurate episode titles in English (for Season 0)
- ✅ Properly configured network
- ✅ Exact air dates

### 4. Monitor Logs

When in doubt, check logs with `--log-level DEBUG`:

```bash
python extrarrfin.py download --log-level DEBUG --limit "Series"
```

### 5. Special Cases

**For non-English content:**
- System works best with English titles
- Consider a lower `min_score` (40-45)

**For rare content:**
- Increase `youtube_search_results` to 15-20
- Decrease `min_score` to 40-45

**For niche content:**
- Use `--verbose` to understand why certain videos are rejected
- Adjust thresholds accordingly

## 🐛 Common Issues

### Issue: No video found despite content existing

**Possible causes:**
1. Minimum score too high
2. Episode title too specific or incorrect
3. Not enough results analyzed

**Solutions:**
```bash
# Check scoring in verbose mode
python extrarrfin.py download --limit "Series" --episode 1 --verbose --dry-run

# Lower minimum score
min_score: 40.0

# Increase number of results
youtube_search_results: 15
```

### Issue: Downloading incorrect videos

**Possible causes:**
1. Minimum score too low
2. Episode titles too generic
3. Presence of many clips/excerpts

**Solutions:**
```bash
# Increase minimum score
min_score: 65.0

# Fix titles in Sonarr
# Example: "Behind the Scenes" → "Breaking Bad: Behind the Scenes Special"
```

### Issue: High scores for wrong content

**Example:** Reviews or reactions getting high scores

**Cause:** Strong title match despite penalties

**Solutions:**
1. Increase `min_score` to 70+
2. Check selected videos in `--verbose` mode
3. Use `--dry-run` to test without downloading

## 📊 Typical Scoring Statistics

Based on real system usage:

| Video Type | Typical Score | Verdict |
|------------|---------------|----------|
| Official complete episode | 120-180 | ✅ Excellent |
| Official behind-the-scenes content | 90-130 | ✅ Very good |
| Quality fan upload | 60-90 | ✅ Acceptable |
| Official clips/excerpts | 50-70 | ⚠️ Borderline |
| Fan compilations | 30-60 | ⚠️ Risky |
| Reviews/reactions | 20-50 | ❌ Avoid |
| Off-topic content | 0-30 | ❌ Reject |

## 🔬 System Limitations

The scoring system has some limitations to be aware of:

### 1. Dependency on YouTube Metadata

- YouTube titles can be misleading
- Channels can impersonate official names
- Views can be artificially inflated

### 2. Language and Localization

- Optimized for English content
- Titles in other languages may get lower scores

### 3. Recent vs Old Content

- Old content may have fewer views but be good quality
- Upload dates are sometimes incorrect

### 4. Possible False Positives

Even with a good score, some videos may be:
- Extended trailers
- Scene compilations
- Unofficial uploads

**Recommendation:** Always do an initial dry-run and verify some downloads.

## 🎯 Conclusion

ExtrarrFin's scoring system is designed to intelligently automate YouTube video selection. Properly configured, it can automatically find the right content in most cases.

**Key takeaways:**
1. ✅ Start with default values (`min_score: 50.0`)
2. ✅ Use `--verbose --dry-run` to understand behavior
3. ✅ Adjust progressively based on your results
4. ✅ Keep your Sonarr metadata up to date
5. ✅ Monitor initial downloads to validate configuration

For more information, see:
- [Main README](README.md) - General documentation
- [TAG_MODE.md](TAG_MODE.md) - Tag mode for behind-the-scenes
