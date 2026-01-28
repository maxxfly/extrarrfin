"""
Download module via yt-dlp with Jellyfin formatting
"""

import logging
import math
import re
import time
from pathlib import Path
from typing import Tuple

import yt_dlp

from .models import Episode, Movie, Series
from .scorer import ScoringWeights, VideoScorer

logger = logging.getLogger(__name__)


class Downloader:
    """YouTube video downloader with Jellyfin-compatible formatting"""

    def __init__(
        self,
        format_string: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        subtitle_languages: list[str] | None = None,
        download_all_subtitles: bool = False,
        use_strm_files: bool = False,
        verbose: bool = False,
        min_score: float = 50.0,
        youtube_search_results: int = 10,
        scoring_weights: ScoringWeights | None = None,
    ):
        self.format_string = format_string
        self.subtitle_languages = subtitle_languages or [
            "fr",
            "en",
            "fr-FR",
            "en-US",
            "en-GB",
        ]
        self.download_all_subtitles = download_all_subtitles
        self.use_strm_files = use_strm_files
        self.verbose = verbose
        self.youtube_search_results = max(
            3, min(20, youtube_search_results)
        )  # Clamp between 3 and 20

        # Initialize video scorer with custom weights if provided
        self.scorer = VideoScorer(
            weights=scoring_weights,
            min_score=min_score,
            verbose=verbose,
        )

    @staticmethod
    def _escape_xml(text: str) -> str:
        """Escape special XML characters to prevent invalid NFO files"""
        if not text:
            return ""
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def sanitize_filename(self, filename: str) -> str:
        """Clean a filename to make it compatible"""
        # Replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)
        # Replace multiple spaces
        filename = re.sub(r"\s+", " ", filename)
        return filename.strip()

    def build_jellyfin_filename(self, series: Series, episode: Episode) -> str:
        """
        Build a Jellyfin-compatible filename
        Format: SeriesName - S00E## - EpisodeTitle.ext
        """
        series_name = self.sanitize_filename(series.title)
        episode_title = self.sanitize_filename(episode.title)

        # Jellyfin format for specials
        filename = f"{series_name} - S{episode.season_number:02d}E{episode.episode_number:02d} - {episode_title}"

        return filename

    def get_series_directory(
        self,
        series: Series,
        media_directory: str | None = None,
        sonarr_directory: str | None = None,
    ) -> Path:
        """
        Determine the target directory for the series

        If media_directory and sonarr_directory are provided, do path mapping
        Otherwise use Sonarr path directly
        """
        if media_directory and sonarr_directory:
            # Map between Sonarr path and real path
            sonarr_path = Path(series.path)
            try:
                # Replace Sonarr root with real root
                relative_path = sonarr_path.relative_to(sonarr_directory)
                real_path = Path(media_directory) / relative_path
            except ValueError:
                # If path is not relative to sonarr_directory, use as-is
                logger.warning(f"Cannot map path for {series.path}")
                real_path = Path(series.path)
        else:
            real_path = Path(series.path)

        # Create Specials directory if it doesn't exist
        specials_dir = real_path / "Specials"
        specials_dir.mkdir(parents=True, exist_ok=True)

        return specials_dir

    def get_extras_directory(
        self,
        series: Series,
        media_directory: str | None = None,
        sonarr_directory: str | None = None,
    ) -> Path:
        """
        Determine the target directory for extras (behind the scenes)

        If media_directory and sonarr_directory are provided, do path mapping
        Otherwise use Sonarr path directly
        """
        if media_directory and sonarr_directory:
            # Map between Sonarr path and real path
            sonarr_path = Path(series.path)
            try:
                # Replace Sonarr root with real root
                relative_path = sonarr_path.relative_to(sonarr_directory)
                real_path = Path(media_directory) / relative_path
            except ValueError:
                # If path is not relative to sonarr_directory, use as-is
                logger.warning(f"Cannot map path for {series.path}")
                real_path = Path(series.path)
        else:
            real_path = Path(series.path)

        # Create extras directory if it doesn't exist
        extras_dir = real_path / "extras"
        extras_dir.mkdir(parents=True, exist_ok=True)

        return extras_dir

    def _clean_episode_title_for_search(self, title: str) -> str:
        """
        Clean episode title before YouTube search to improve results

        Removes:
        - Old years in parentheses like (1978), (1985), etc.
        - Content that appears to be misplaced movie/show titles

        Args:
            title: Original episode title from Sonarr

        Returns:
            Cleaned title suitable for YouTube search
        """
        cleaned = title

        # Remove old years in parentheses (19XX)
        cleaned = re.sub(r"\s*\(19\d{2}\)\s*", " ", cleaned)

        # Remove old years in parentheses (20XX before 2010, likely old content)
        cleaned = re.sub(r"\s*\(200\d\)\s*", " ", cleaned)

        # Remove extra whitespace
        cleaned = " ".join(cleaned.split())

        if self.verbose and cleaned != title:
            logger.info(f"[VERBOSE] Cleaned episode title: '{title}' → '{cleaned}'")

        return cleaned.strip()

    def search_youtube(self, series: Series, episode: Episode) -> str | None:
        """
        Search for a video on YouTube with improved matching
        Returns the URL of the best matching video found

        First tries: series title + episode title
        If not found, tries: episode title only
        Uses a scoring system to find the best match
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",  # Get metadata for each video
            "default_search": f"ytsearch{self.youtube_search_results}",
            "sleep_requests": 1,  # Sleep 1 second between requests to avoid 429 errors
        }

        # First attempt: series title + episode title
        if episode.title and episode.title != "TBA":
            # Clean episode title before search to improve results
            cleaned_title = self._clean_episode_title_for_search(episode.title)
            query_with_series = f"{series.title} {cleaned_title}"
            if self.verbose:
                logger.info(f"[VERBOSE] YouTube search query: '{query_with_series}'")
            else:
                logger.info(f"YouTube search (with series): {query_with_series}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_url = (
                        f"ytsearch{self.youtube_search_results}:{query_with_series}"
                    )
                    if self.verbose:
                        logger.info(f"[VERBOSE] Full search URL: {search_url}")

                    result = ydl.extract_info(search_url, download=False)

                    if result and "entries" in result and result["entries"]:
                        # Score each result to find the best match
                        best_video = self.scorer.score_and_select_video(
                            result["entries"], series, episode.title
                        )

                        if best_video:
                            video_url = (
                                f"https://www.youtube.com/watch?v={best_video['id']}"
                            )
                            if self.verbose:
                                logger.info(
                                    f"[VERBOSE] Video found: {best_video.get('title')}"
                                )
                                logger.info(f"[VERBOSE] Video URL: {video_url}")
                                logger.info(
                                    f"[VERBOSE] Match score: {best_video.get('_score', 0):.2f}"
                                )
                            else:
                                logger.info(
                                    f"Video found: {best_video.get('title')} - {video_url}"
                                )
                            return video_url
            except Exception as e:
                logger.error(f"Error during YouTube search: {e}")

            # Second attempt: episode title only
            query_episode_only = episode.title
            if self.verbose:
                logger.info(
                    f"[VERBOSE] YouTube search query (episode only): '{query_episode_only}'"
                )
            else:
                logger.info(f"YouTube search (episode only): {query_episode_only}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_url = (
                        f"ytsearch{self.youtube_search_results}:{query_episode_only}"
                    )
                    if self.verbose:
                        logger.info(f"[VERBOSE] Full search URL: {search_url}")

                    result = ydl.extract_info(search_url, download=False)

                    if result and "entries" in result and result["entries"]:
                        # Score each result to find the best match
                        best_video = self.scorer.score_and_select_video(
                            result["entries"], series, episode.title
                        )

                        if best_video:
                            video_url = (
                                f"https://www.youtube.com/watch?v={best_video['id']}"
                            )
                            if self.verbose:
                                logger.info(
                                    f"[VERBOSE] Video found: {best_video.get('title')}"
                                )
                                logger.info(f"[VERBOSE] Video URL: {video_url}")
                                logger.info(
                                    f"[VERBOSE] Match score: {best_video.get('_score', 0):.2f}"
                                )
                            else:
                                logger.info(
                                    f"Video found: {best_video.get('title')} - {video_url}"
                                )
                            return video_url
            except Exception as e:
                logger.error(f"Error during YouTube search: {e}")

        return None

    def search_youtube_behind_scenes(self, series: Series) -> list[dict] | None:
        """
        Search for behind the scenes videos on YouTube
        Returns a list of video dictionaries with metadata (id, title, url, etc.)

        Searches for: "series title - behind the scenes"
        Uses the scoring system to find the best matches
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch15",  # Get top 15 results for better matching
            "sleep_requests": 1,  # Sleep 1 second between requests to avoid 429 errors
        }

        query = f"{series.title} - behind the scenes"
        if self.verbose:
            logger.info(f"[VERBOSE] YouTube search query: '{query}'")
        else:
            logger.info(f"YouTube search (behind the scenes): {query}")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_url = f"ytsearch15:{query}"
                if self.verbose:
                    logger.info(f"[VERBOSE] Full search URL: {search_url}")

                result = ydl.extract_info(search_url, download=False)

                if result and "entries" in result and result["entries"]:
                    # Score each result to find the best matches
                    scored_videos = self._score_behind_scenes_videos(
                        result["entries"], series
                    )

                    if scored_videos:
                        video_list = []
                        for video in scored_videos:
                            video_url = f"https://www.youtube.com/watch?v={video['id']}"
                            video_info = {
                                "id": video["id"],
                                "url": video_url,
                                "title": video.get("title", "Unknown"),
                                "channel": video.get("channel", "Unknown"),
                                "uploader": video.get(
                                    "uploader", video.get("channel", "Unknown")
                                ),
                                "description": video.get("description", ""),
                                "duration": video.get("duration", 0),
                                "view_count": video.get("view_count", 0),
                                "score": video.get("_score", 0),
                            }
                            video_list.append(video_info)
                            if self.verbose:
                                logger.info(
                                    f"[VERBOSE] Video found: {video.get('title')}"
                                )
                                logger.info(f"[VERBOSE] Video URL: {video_url}")
                                logger.info(
                                    f"[VERBOSE] Match score: {video.get('_score', 0):.2f}"
                                )
                            else:
                                logger.info(
                                    f"Video found: {video.get('title')} - {video_url}"
                                )
                        return video_list
        except Exception as e:
            logger.error(f"Error during YouTube search: {e}")

        return None

    def search_youtube_for_extras(
        self, query: str, title: str, verbose: bool = False
    ) -> dict | None:
        """
        Generic search for extras content on YouTube (movies or series)
        Returns the best matching video based on scoring

        Args:
            query: Search query (e.g., "Movie Title behind the scenes")
            title: Title to match against (movie or series name)
            verbose: Enable verbose logging

        Returns:
            Video info dict or None if no suitable video found
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": f"ytsearch{self.youtube_search_results}",
            "sleep_requests": 1,
        }

        if verbose:
            logger.info(f"[VERBOSE] YouTube search query: '{query}'")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_url = f"ytsearch{self.youtube_search_results}:{query}"
                if verbose:
                    logger.info(f"[VERBOSE] Full search URL: {search_url}")

                result = ydl.extract_info(search_url, download=False)

                if result and "entries" in result and result["entries"]:
                    # Get the first result that seems relevant
                    for video in result["entries"]:
                        if video and video.get("id"):
                            video_url = f"https://www.youtube.com/watch?v={video['id']}"
                            video_info = {
                                "id": video["id"],
                                "url": video_url,
                                "webpage_url": video_url,
                                "title": video.get("title", "Unknown"),
                                "channel": video.get("channel", "Unknown"),
                                "uploader": video.get(
                                    "uploader", video.get("channel", "Unknown")
                                ),
                                "description": video.get("description", ""),
                                "duration": video.get("duration", 0),
                                "view_count": video.get("view_count", 0),
                            }

                            if verbose:
                                logger.info(
                                    f"[VERBOSE] Video found: {video.get('title')}"
                                )
                                logger.info(f"[VERBOSE] Video URL: {video_url}")

                            return video_info
        except Exception as e:
            logger.error(f"Error during YouTube search: {e}")

        return None

    def _score_behind_scenes_videos(
        self,
        videos: list,
        series: Series,
        min_score: float = 65.0,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Score behind the scenes video results based on title matching

        Scoring factors:
        - Contains "behind the scenes" or "bts" or "making of": +50 points
        - Contains series title: +40 points
        - Network in title (official content): +50 points
        - Channel matches network: +50 points
        - Known BTS content channels: +35 points
        - Word match ratio: +30 points max
        - Official/verified channel indicators: +20 points
        - Shorter title (less extra content): +15 points max

        Penalties:
        - Other movie/series titles before series name: -80 points
        - Unrelated channel types: -50 points
        - Unrelated content indicators: -30 points

        Returns videos with score >= min_score, sorted by score (highest first)
        """
        if not videos:
            return []

        scored_videos = []

        # Known channels that specialize in BTS/behind-the-scenes content
        known_bts_channels = [
            "filmisnow",
            "rotten tomatoes",
            "ign",
            "entertainment weekly",
            "collider",
            "comicbook.com",
            "screen rant",
            "variety",
            "the hollywood reporter",
            "deadline",
            "den of geek",
            "syfy",
            "nerdist",
            "movie trailers source",
            "joblo",
        ]

        # Normalize strings for comparison
        series_lower = series.title.lower()
        network_lower = series.network.lower() if series.network else None

        if self.verbose and network_lower:
            logger.info(f"[VERBOSE] Series network: {series.network}")

        for video in videos:
            if not video:
                continue

            title = video.get("title", "")
            title_lower = title.lower()
            channel = video.get("channel", "")
            channel_lower = channel.lower()
            score: float = 0

            # Contains behind the scenes / bts / making of (essential for this mode)
            if any(
                phrase in title_lower
                for phrase in [
                    "behind the scenes",
                    "behind the scene",
                    "bts",
                    "making of",
                    "making-of",
                    "backstage",
                    "featurette",
                ]
            ):
                score += 50

            # Bonus for VFX/technical breakdown content (interesting BTS content)
            if any(
                phrase in title_lower
                for phrase in ["vfx breakdown", "breakdown", "visual effects"]
            ):
                score += 40
                if self.verbose:
                    logger.info("[VERBOSE] VFX/Breakdown bonus applied")

            # Contains series title
            if series_lower in title_lower:
                score += 40

                # Additional bonus for character/actor focused BTS content
                # (e.g., "Foundation — Demerzel: Behind the Scenes")
                if any(
                    phrase in title_lower
                    for phrase in [":", "with", "interview", "character"]
                ) and any(
                    bts in title_lower
                    for bts in ["behind the scenes", "behind the scene", "bts"]
                ):
                    score += 15
                    if self.verbose:
                        logger.info("[VERBOSE] Character/actor BTS bonus applied")

            # Bonus if network name appears in title (indicates official content)
            if network_lower and network_lower in title_lower:
                score += 50
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] Network in title bonus: {series.network} found in title"
                    )

            # Check if channel matches the network (increased bonus)
            if network_lower and channel:
                if network_lower in channel_lower or channel_lower in network_lower:
                    score += 50  # Increased from 40 to favor official channels
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Network match bonus: {channel} ~ {series.network}"
                        )
                elif len(network_lower) <= 5 and network_lower in channel_lower.split():
                    score += 50
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Network abbreviation match: {channel} ~ {series.network}"
                        )
            else:
                # Check if it's a known BTS content channel (even if not the official network)
                if any(
                    known_channel in channel_lower
                    for known_channel in known_bts_channels
                ):
                    score += (
                        40  # Increased from 35 to better compete with official content
                    )
                    if self.verbose:
                        logger.info(f"[VERBOSE] Known BTS channel bonus: {channel}")
                # Penalize videos from channels that don't match the network
                # when we know the network (helps filter out unrelated content)
                elif network_lower and channel and series_lower in title_lower:
                    # Only penalize if it's clearly not the right channel
                    unrelated_keywords = [
                        "school",
                        "university",
                        "college",
                        "fashion brand",
                        "prada",
                        "museum",
                        "art gallery",
                        "foundation (charity)",
                        "sixth form",
                        "centre",
                    ]
                    if any(keyword in channel_lower for keyword in unrelated_keywords):
                        score -= 50
                        if self.verbose:
                            logger.info(
                                f"[VERBOSE] Penalty: Unrelated channel type: {channel}"
                            )

            # Check title for educational/unrelated indicators (independent check)
            if "sixth form" in title_lower or (
                "durham" in title_lower and "art foundation" in title_lower
            ):
                score -= 60
                if self.verbose:
                    logger.info(
                        "[VERBOSE] Penalty: Educational/unrelated content in title"
                    )

            # Word matching ratio
            series_words = set(series.title.lower().split())
            title_words = set(title_lower.split())
            common_words = series_words & title_words
            if series_words:
                word_ratio = len(common_words) / len(series_words)
                score += word_ratio * 30

            # Check for official/quality indicators
            title_and_channel = (title + " " + channel).lower()
            if any(
                word in title_and_channel for word in ["official", "vevo", "verified"]
            ):
                score += 20

            # Prefer shorter titles (less likely to be compilations)
            title_length = len(title)
            if title_length < 100:
                score += 15 * (1 - title_length / 100)

            # PENALTIES: Detect if another title appears BEFORE the series name
            # This catches cases like "Wrong Turn the Foundation" where "Wrong Turn" is the actual content
            if series_lower in title_lower:
                series_position = title_lower.find(series_lower)
                title_before_series = title_lower[:series_position].strip()

                # Check if there's substantial content before the series name
                # that looks like another title (multiple capitalized words)
                if title_before_series:
                    # Count words that start with capital in original title
                    original_before = title[:series_position].strip()
                    capitalized_words = sum(
                        1
                        for word in original_before.split()
                        if word and word[0].isupper()
                    )

                    # If 2+ capitalized words before series name, likely another title
                    if capitalized_words >= 2:
                        score -= 80
                        if self.verbose:
                            logger.info(
                                f"[VERBOSE] Penalty: Possible other title before series name: '{original_before}'"
                            )

            # Penalize certain patterns that indicate wrong content
            penalty_patterns = [
                "compilation",
                "playlist",
                "all episodes",
                "full series",
                "reaction",
                "review",
                "unboxing",
                "gameplay",
                "walkthrough",
                "interview only",
                "cast interview",
                "ending explained",
                "theories",
            ]
            if any(word in title_lower for word in penalty_patterns):
                score -= 30

            # Penalize trailers if they don't explicitly mention BTS content
            if "trailer" in title_lower:
                has_bts = any(
                    phrase in title_lower
                    for phrase in [
                        "behind the scenes",
                        "behind the scene",
                        "bts",
                        "making of",
                        "featurette",
                    ]
                )
                if not has_bts:
                    score -= 40
                    if self.verbose:
                        logger.info("[VERBOSE] Penalty: Trailer without BTS content")

            if self.verbose:
                logger.info(f"[VERBOSE] Video '{title}' scored {score:.2f} points")

            # Store the score and keep video if it meets minimum
            if score >= min_score:
                video["_score"] = score
                scored_videos.append(video)

        # Sort by score (highest first)
        scored_videos.sort(key=lambda v: v.get("_score", 0), reverse=True)

        # Remove duplicates based on title similarity and duration
        scored_videos = self._remove_duplicate_videos(scored_videos)

        # Limit to max_results best videos
        if len(scored_videos) > max_results:
            scored_videos = scored_videos[:max_results]

        if self.verbose and scored_videos:
            logger.info(
                f"[VERBOSE] Found {len(scored_videos)} videos above minimum score {min_score}"
            )

        return scored_videos

    def _remove_duplicate_videos(self, videos: list[dict]) -> list[dict]:
        """
        Remove duplicate videos based on title similarity and duration proximity
        Keeps the video with the highest score among duplicates

        Two videos are considered duplicates if:
        - Title similarity > 80% (based on word overlap)
        - Duration difference < 10% or < 30 seconds
        """
        if not videos:
            return []

        unique_videos: list = []

        for video in videos:
            is_duplicate = False
            video_title = video.get("title", "").lower()
            video_duration = video.get("duration", 0)

            # Normalize title for comparison (remove common words and punctuation)
            video_words = set(
                word.strip(".,!?-—|:;()[]")
                for word in video_title.split()
                if len(word) > 2 and word not in ["the", "and", "for", "with", "from"]
            )

            for existing in unique_videos:
                existing_title = existing.get("title", "").lower()
                existing_duration = existing.get("duration", 0)

                existing_words = set(
                    word.strip(".,!?-—|:;()[]")
                    for word in existing_title.split()
                    if len(word) > 2
                    and word not in ["the", "and", "for", "with", "from"]
                )

                # Calculate title similarity (Jaccard similarity)
                if video_words and existing_words:
                    common_words = video_words & existing_words
                    all_words = video_words | existing_words
                    similarity = len(common_words) / len(all_words) if all_words else 0
                else:
                    similarity = 0

                # Check duration proximity
                duration_similar = False
                if video_duration and existing_duration:
                    duration_diff = abs(video_duration - existing_duration)
                    duration_ratio = duration_diff / max(
                        video_duration, existing_duration
                    )
                    duration_similar = duration_diff < 30 or duration_ratio < 0.1

                # Consider it a duplicate if titles are very similar
                # OR if titles are somewhat similar AND durations are close
                if similarity > 0.8 or (similarity > 0.6 and duration_similar):
                    is_duplicate = True
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Duplicate detected: '{video.get('title')}' "
                            f"(similarity: {similarity:.2f}, duration diff: {abs(video_duration - existing_duration)}s) "
                            f"vs '{existing.get('title')}'"
                        )
                    break

            if not is_duplicate:
                unique_videos.append(video)

        if self.verbose and len(unique_videos) < len(videos):
            logger.info(
                f"[VERBOSE] Removed {len(videos) - len(unique_videos)} duplicate(s)"
            )

        return unique_videos

    def _score_and_select_video(
        self, videos: list, series: Series, episode_title: str
    ) -> dict | None:
        """
        Score video results based on multiple factors and select the best one

        Scoring factors:
        - Exact title match: +100 points
        - Contains episode title: +50 points
        - Channel matches network: +40 points
        - Word match ratio: +40 points max
        - Contains series title: +30 points
        - Shorter title (less extra content): +20 points max
        - Official/verified channel indicators: +15 points
        - View count bonus: +10 points max (logarithmic)
        - Description contains series/episode: +15 points
        - Upload date near series year: +20 points max

        Penalties:
        - Video game content: -150 points
        - Old year in title: -100 points
        - Video uploaded before series: -120 points
        - Content before series name: -80 points
        - Too short (<1min) or too long (>90min): -50 points
        - Compilation/playlist: -30 points

        Returns the video with the highest score
        """
        if not videos:
            return None

        scored_videos = []

        # Normalize strings for comparison
        series_lower = series.title.lower()
        episode_lower = episode_title.lower()
        search_words = set((series.title + " " + episode_title).lower().split())
        network_lower = series.network.lower() if series.network else None
        series_year = series.year  # Year the series started

        if self.verbose:
            if network_lower:
                logger.info(f"[VERBOSE] Series network: {series.network}")
            if series_year:
                logger.info(f"[VERBOSE] Series year: {series_year}")

        for video in videos:
            if not video:
                continue

            title = video.get("title", "")
            title_lower = title.lower()
            channel = video.get("channel", "")
            channel_lower = channel.lower()
            description = video.get("description", "") or ""
            description_lower = description.lower()
            duration = video.get("duration")  # Duration in seconds
            view_count = video.get("view_count")
            upload_date = video.get("upload_date")  # Format: YYYYMMDD
            score: float = 0

            # ===== POSITIVE SCORING =====

            # Exact match (very rare but best case)
            if (
                title_lower == episode_lower
                or title_lower == f"{series_lower} {episode_lower}"
            ):
                score += 100

            # Contains episode title (case insensitive)
            if episode_lower in title_lower:
                score += 50

            # Check if channel matches the network (high priority)
            if network_lower and channel:
                # Check for exact match or partial match
                if network_lower in channel_lower or channel_lower in network_lower:
                    score += 40
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Network match bonus: {channel} ~ {series.network}"
                        )
                # Check for common abbreviations (e.g., "BBC" in "BBC Studios")
                elif len(network_lower) <= 5 and network_lower in channel_lower.split():
                    score += 40
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Network abbreviation match: {channel} ~ {series.network}"
                        )

            # Word matching ratio
            title_words = set(title_lower.split())
            common_words = search_words & title_words
            if search_words:
                word_ratio = len(common_words) / len(search_words)
                score += word_ratio * 40

            # Contains series title
            if series_lower in title_lower:
                score += 30

            # Prefer shorter titles (less likely to be compilations or unrelated content)
            title_length = len(title)
            if title_length < 100:
                score += 20 * (1 - title_length / 100)

            # [IMPROVEMENT #2] Check for official/verified channel indicators
            title_and_channel = (title + " " + channel).lower()
            if any(
                word in title_and_channel for word in ["official", "vevo", "verified"]
            ):
                score += 15
                if self.verbose:
                    logger.info("[VERBOSE] Official/verified channel bonus: +15")

            # [IMPROVEMENT #4] View count bonus (logarithmic scale)
            # Videos with more views are more likely to be legitimate content
            if view_count and view_count > 0:
                # log10(1000) = 3, log10(1M) = 6, log10(100M) = 8
                # Scale: 0-10 points based on views (1K to 100M range)
                view_score = min(10, max(0, (math.log10(view_count) - 3) * 2))
                score += view_score
                if self.verbose and view_score > 2:
                    logger.info(
                        f"[VERBOSE] View count bonus: +{view_score:.1f} ({view_count:,} views)"
                    )

            # [IMPROVEMENT #10] Like ratio bonus
            # Videos with high like/view ratio are more likely to be quality content
            like_count = video.get("like_count")
            if like_count and view_count and view_count > 100:
                like_ratio = like_count / view_count
                # Typical good ratio is 2-5%, excellent is 5%+
                # Scale: 0-8 points based on like ratio
                if like_ratio >= 0.05:  # 5%+ = excellent engagement
                    like_bonus = 8
                elif like_ratio >= 0.03:  # 3-5% = good engagement
                    like_bonus = 5
                elif like_ratio >= 0.02:  # 2-3% = decent engagement
                    like_bonus = 3
                else:
                    like_bonus = 0
                if like_bonus > 0:
                    score += like_bonus
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Like ratio bonus: +{like_bonus} ({like_ratio:.1%} likes)"
                        )

            # [IMPROVEMENT #5] Description analysis
            # Check if description contains relevant keywords
            if description_lower:
                desc_bonus = 0
                if series_lower in description_lower:
                    desc_bonus += 8
                if episode_lower in description_lower:
                    desc_bonus += 7
                # Check for official content indicators in description
                if any(
                    word in description_lower
                    for word in [
                        "official",
                        "©",
                        "all rights reserved",
                        network_lower or "",
                    ]
                    if word
                ):
                    desc_bonus += 5
                if desc_bonus > 0:
                    score += min(15, desc_bonus)  # Cap at 15 points
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Description match bonus: +{min(15, desc_bonus)}"
                        )

            # [IMPROVEMENT #3] Upload date near series year bonus
            if upload_date and series_year:
                try:
                    upload_year = int(upload_date[:4])
                    year_diff = abs(upload_year - series_year)
                    # Bonus for videos uploaded within 5 years of series start
                    # Full bonus (20) if same year, decreasing to 0 at 5+ years difference
                    if year_diff <= 5:
                        year_bonus = 20 * (1 - year_diff / 5)
                        score += year_bonus
                        if self.verbose and year_bonus > 5:
                            logger.info(
                                f"[VERBOSE] Upload year proximity bonus: +{year_bonus:.1f} (uploaded {upload_year})"
                            )
                except (ValueError, TypeError):
                    pass  # Invalid date format

            # ===== PENALTIES =====

            # Penalize certain patterns that indicate wrong content
            if any(
                word in title_lower
                for word in ["compilation", "playlist", "all episodes", "full series"]
            ):
                score -= 30

            # [IMPROVEMENT #1] Duration penalty - too short or too long
            if duration:
                if duration < 60:  # Less than 1 minute - probably a trailer/teaser
                    score -= 50
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Duration penalty: -50 (too short: {duration}s)"
                        )
                elif duration > 5400:  # More than 90 minutes - probably a compilation
                    score -= 50
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Duration penalty: -50 (too long: {duration // 60}min)"
                        )

            # STRONG PENALTY: Video game content - not official series content
            video_game_indicators = [
                "juno new origins",
                "juno",
                "kerbal space program",
                "ksp",
                "gameplay",
                "game play",
                "let's play",
                "walkthrough",
                "gaming",
                "simulator",
                "sim",
                "mod",
                "modded",
                "pc game",
                "video game",
            ]
            if any(indicator in title_lower for indicator in video_game_indicators):
                score -= 150
                if self.verbose:
                    logger.info(
                        "[VERBOSE] Very strong penalty: Video game/gameplay content detected"
                    )

            # PENALTY: Detect old year in parentheses (e.g., "(1978)") - likely wrong content
            old_year_match = re.search(r"\(19\d{2}\)", title)
            if old_year_match:
                score -= 100
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] Strong penalty: Old year {old_year_match.group()} in title"
                    )

            # [IMPROVEMENT #9] Video uploaded BEFORE series started - very suspicious
            if upload_date and series_year:
                try:
                    upload_year = int(upload_date[:4])
                    if upload_year < series_year - 1:
                        # Video uploaded before series even existed
                        years_before = series_year - upload_year
                        penalty = min(120, years_before * 20)
                        score -= penalty
                        if self.verbose:
                            logger.info(
                                f"[VERBOSE] Strong penalty: Video from {upload_year}, series started {series_year} (-{penalty})"
                            )
                except (ValueError, TypeError):
                    pass

            # PENALTY: Detect if another title appears BEFORE the series name
            if series_lower in title_lower:
                series_position = title_lower.find(series_lower)
                title_before_series = title_lower[:series_position].strip()

                if title_before_series:
                    words_before = title_before_series.split()
                    significant_words = [
                        w
                        for w in words_before
                        if w
                        not in ["-", "|", ":", "the", "a", "an", "for", "and", "of"]
                    ]
                    if len(significant_words) >= 2:
                        score -= 80
                        if self.verbose:
                            logger.info(
                                f"[VERBOSE] Penalty: Content before series name: '{title_before_series}'"
                            )

            # Store score in video dict
            video["_score"] = score
            scored_videos.append(video)

            if self.verbose:
                logger.info(
                    f"[VERBOSE] Candidate: {title[:60]}... (score: {score:.2f})"
                )

        # Return video with highest score if it meets the minimum threshold
        if scored_videos:
            best = max(scored_videos, key=lambda v: v.get("_score", 0))
            best_score = best.get("_score", 0)

            # Check if best video meets minimum score threshold
            if best_score < self.scorer.min_score:
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] ✗ Best video score ({best_score:.2f}) is below minimum threshold ({self.scorer.min_score})"
                    )
                    logger.info(f"[VERBOSE] ✗ Rejected: {best.get('title')}")
                logger.warning(
                    f"No video found with acceptable score (best: {best_score:.2f}, minimum: {self.scorer.min_score})"
                )
                return None

            if self.verbose:
                logger.info(
                    f"[VERBOSE] ✓ Selected video: {best.get('title')} (score: {best_score:.2f})"
                )
                logger.info(f"[VERBOSE] ✓ Video ID: {best.get('id')}")
            return best

        return None

    def create_strm_file(
        self,
        series: Series,
        episode: Episode,
        output_directory: Path,
        youtube_url: str,
        dry_run: bool = False,
    ) -> Tuple[bool, str | None, str | None, dict | None]:
        """
        Create a STRM file pointing to direct video stream URL and download subtitles

        Args:
            series: Series object
            episode: Episode object
            output_directory: Directory to save the STRM file
            youtube_url: YouTube URL to extract stream from
            dry_run: If True, simulate without creating files

        Returns:
            Tuple (success, file_path, error_message, video_info)
        """
        try:
            base_filename = self.build_jellyfin_filename(series, episode)
            strm_file = output_directory / f"{base_filename}.strm"

            # Extract direct stream URL from YouTube
            ydl_opts = {
                "format": self.format_string,
                "quiet": True,
                "no_warnings": True,
                "sleep_requests": 1,  # Sleep 1 second between requests to avoid 429 errors
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)

                # Get the direct URL of the selected format
                if "url" in info:
                    stream_url = info["url"]
                elif "formats" in info and info["formats"]:
                    # Get the best format URL
                    stream_url = info["formats"][-1]["url"]
                else:
                    return False, None, "Could not extract stream URL", None

            if dry_run:
                logger.info(f"DRY RUN: Would create STRM file: {strm_file}")
                return True, str(strm_file), None, info

            # Write direct stream URL to STRM file
            with open(strm_file, "w", encoding="utf-8") as f:
                f.write(stream_url)

            logger.info(f"STRM file created: {strm_file}")

            # Download subtitles separately (they will be placed next to the STRM file)
            self._download_subtitles_only(youtube_url, output_directory, base_filename)

            return True, str(strm_file), None, info

        except Exception as e:
            error_msg = f"Error creating STRM file: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg, None

    def _download_subtitles_only(
        self, youtube_url: str, output_directory: Path, base_filename: str
    ):
        """
        Download only subtitles for a YouTube video

        Args:
            youtube_url: YouTube video URL
            output_directory: Directory to save subtitles
            base_filename: Base filename (without extension)
        """
        try:
            output_template = str(output_directory / f"{base_filename}.%(ext)s")

            ydl_opts = {
                "skip_download": True,  # Don't download the video
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": self.subtitle_languages,
                "allsubtitles": self.download_all_subtitles,
                "subtitlesformat": "srt",
                "outtmpl": output_template,
                "quiet": True,
                "no_warnings": True,
                "ignoreerrors": True,
                "sleep_requests": 1,  # Sleep 1 second between requests to avoid 429 errors
                "sleep_subtitles": 1,  # Sleep 1 second before downloading subtitles
                "postprocessors": [
                    {
                        "key": "FFmpegSubtitlesConvertor",
                        "format": "srt",
                    },
                ],
            }

            logger.info(f"Downloading subtitles for: {youtube_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(youtube_url, download=True)

            logger.info("Subtitles downloaded successfully")

        except Exception as e:
            # Don't fail the whole operation if subtitles fail
            logger.warning(f"Could not download subtitles: {e}")

    def download_episode(
        self,
        series: Series,
        episode: Episode,
        output_directory: Path,
        force: bool = False,
        youtube_url: str | None = None,
        dry_run: bool = False,
    ) -> Tuple[bool, str | None, str | None, dict | None]:
        """
        Download an episode from YouTube

        Args:
            series: Series object
            episode: Episode object
            output_directory: Directory to save the file
            force: If True, re-download even if file exists
            youtube_url: Optional YouTube URL (will search if not provided)
            dry_run: If True, simulate without downloading or deleting files

        Returns:
            Tuple (success, file_path, error_message, video_info)
        """
        # Build filename
        base_filename = self.build_jellyfin_filename(series, episode)

        # Check if file already exists
        existing_files = list(output_directory.glob(f"{base_filename}.*"))

        # If dry-run and files exist without force, return early
        if dry_run and existing_files and not force:
            logger.info(f"DRY RUN: File already exists: {existing_files[0].name}")
            return True, str(existing_files[0]), None, None

        # If not force mode and files exist, just return (file already present)
        if existing_files and not force and not dry_run:
            logger.info(f"File already exists: {existing_files[0].name}")
            return True, str(existing_files[0]), None, None

        # Force mode: delete existing files to allow switching between modes
        if existing_files and force:
            for existing_file in existing_files:
                try:
                    # Don't delete .srt files if we're in STRM mode (we'll regenerate them)
                    if existing_file.suffix == ".srt" and self.use_strm_files:
                        continue
                    # Don't delete .srt files if we're downloading (yt-dlp will handle them)
                    if existing_file.suffix == ".srt" and not self.use_strm_files:
                        continue

                    if dry_run:
                        logger.info(
                            f"DRY RUN: Would delete existing file: {existing_file.name}"
                        )
                    else:
                        logger.info(f"Deleting existing file: {existing_file.name}")
                        existing_file.unlink()
                except Exception as e:
                    logger.warning(f"Could not delete {existing_file.name}: {e}")

        # Search on YouTube if URL is not provided
        if not youtube_url:
            youtube_url = self.search_youtube(series, episode)
            if not youtube_url:
                error_msg = "No video found on YouTube"
                logger.warning(error_msg)
                return False, None, error_msg, None

        # If dry-run mode, extract video info but don't download
        if dry_run:
            logger.info(f"DRY RUN: Would download from {youtube_url}")
            try:
                # Extract video info for NFO file creation
                ydl_opts_info = {
                    "quiet": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    video_info = ydl.extract_info(youtube_url, download=False)

                output_template = f"{base_filename}.mp4"
                return True, str(output_directory / output_template), None, video_info
            except Exception as e:
                logger.warning(f"Could not extract video info: {e}")
                output_template = f"{base_filename}.mp4"
                return True, str(output_directory / output_template), None, None

        # If STRM mode is enabled, create STRM file instead of downloading
        if self.use_strm_files:
            return self.create_strm_file(
                series, episode, output_directory, youtube_url, dry_run=dry_run
            )

        # yt-dlp options
        output_template = str(output_directory / f"{base_filename}.%(ext)s")

        ydl_opts = {
            "format": self.format_string,
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            # Sleep options to avoid 429 errors (Too Many Requests)
            "sleep_interval": 2,  # Sleep 2 seconds between downloads
            "sleep_requests": 1,  # Sleep 1 second between requests
            "sleep_subtitles": 1,  # Sleep 1 second before downloading subtitles
            # Subtitle options - improved
            "writesubtitles": True,  # Download manual subtitles
            "writeautomaticsub": True,  # Download auto-generated subtitles as fallback
            "subtitleslangs": self.subtitle_languages,  # Configurable priority languages
            "allsubtitles": self.download_all_subtitles,  # Download all available subtitles if enabled
            "subtitlesformat": "srt",  # Convert to SRT format (best compatibility)
            "ignoreerrors": True,  # Don't fail if subtitles can't be downloaded
            "postprocessors": [
                {
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",  # Convert all subtitles to SRT
                },
                {
                    "key": "FFmpegEmbedSubtitle",
                    "already_have_subtitle": False,
                },
            ],
        }

        if self.verbose:
            logger.info(f"[VERBOSE] Starting download from: {youtube_url}")
            logger.info(f"[VERBOSE] Output template: {output_template}")
            logger.info(f"[VERBOSE] Format: {self.format_string}")
            logger.info(
                f"[VERBOSE] Subtitle languages: {', '.join(self.subtitle_languages)}"
            )
        else:
            logger.info(f"Downloading from: {youtube_url}")

        # Retry logic with exponential backoff for rate limiting errors
        max_retries = 5
        base_delay = 2  # Base delay in seconds
        last_error = None

        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)

                    # Find downloaded file
                    ext = info.get("ext", "mp4")
                    final_file = output_directory / f"{base_filename}.{ext}"

                    if final_file.exists():
                        if self.verbose:
                            logger.info(f"[VERBOSE] Download successful: {final_file}")
                            logger.info(
                                f"[VERBOSE] File size: {final_file.stat().st_size / (1024 * 1024):.2f} MB"
                            )
                        else:
                            logger.info(f"Download successful: {final_file}")
                        return True, str(final_file), None, info
                    else:
                        error_msg = "Downloaded file not found"
                        logger.error(error_msg)
                        return False, None, error_msg, None

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if it's a rate limit error (403/429)
                if (
                    "403" in error_str
                    or "forbidden" in error_str
                    or "429" in error_str
                    or "too many" in error_str
                ):
                    if attempt < max_retries - 1:  # Not the last attempt
                        # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                        import time

                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Rate limit error, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        error_msg = f"Download failed after {max_retries} attempts: {e}"
                        logger.error(error_msg)
                        return False, None, error_msg, None
                else:
                    # Not a rate limit error, don't retry
                    error_msg = f"Download error: {str(e)}"
                    logger.error(error_msg)
                    return False, None, error_msg, None

        # Should not reach here, but just in case
        error_msg = f"Download error: {last_error}"
        logger.error(error_msg)
        return False, None, error_msg, None

    def download_video_from_url(
        self,
        youtube_url: str,
        base_filename: str,
        output_directory: Path,
        force: bool = False,
        dry_run: bool = False,
    ) -> Tuple[bool, str | None, str | None, dict | None]:
        """
        Download a video from a YouTube URL (generic method for extras, movies, etc.)

        Args:
            youtube_url: YouTube video URL
            base_filename: Base filename (without extension)
            output_directory: Directory to save the file
            force: If True, re-download even if file exists
            dry_run: If True, simulate without downloading

        Returns:
            Tuple (success, file_path, error_message, video_info)
        """
        # Check if file already exists
        existing_files = list(output_directory.glob(f"{base_filename}.*"))

        # If not force mode and files exist, just return
        if existing_files and not force and not dry_run:
            logger.info(f"File already exists: {existing_files[0].name}")
            return True, str(existing_files[0]), None, None

        # Force mode: delete existing files
        if existing_files and force:
            for existing_file in existing_files:
                try:
                    if existing_file.suffix == ".srt":
                        continue
                    if dry_run:
                        logger.info(
                            f"DRY RUN: Would delete existing file: {existing_file.name}"
                        )
                    else:
                        logger.info(f"Deleting existing file: {existing_file.name}")
                        existing_file.unlink()
                except Exception as e:
                    logger.warning(f"Could not delete {existing_file.name}: {e}")

        # If dry-run mode, extract video info but don't download
        if dry_run:
            logger.info(f"DRY RUN: Would download from {youtube_url}")
            try:
                ydl_opts_info = {
                    "quiet": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    video_info = ydl.extract_info(youtube_url, download=False)

                output_template = f"{base_filename}.mp4"
                return True, str(output_directory / output_template), None, video_info
            except Exception as e:
                logger.warning(f"Could not extract video info: {e}")
                output_template = f"{base_filename}.mp4"
                return True, str(output_directory / output_template), None, None

        # yt-dlp options
        output_template = str(output_directory / f"{base_filename}.%(ext)s")

        ydl_opts = {
            "format": self.format_string,
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            "sleep_interval": 2,
            "sleep_requests": 1,
            "sleep_subtitles": 1,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": self.subtitle_languages,
            "allsubtitles": self.download_all_subtitles,
            "subtitlesformat": "srt",
            "ignoreerrors": True,
            "postprocessors": [
                {
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                },
                {
                    "key": "FFmpegEmbedSubtitle",
                    "already_have_subtitle": False,
                },
            ],
        }

        if self.verbose:
            logger.info(f"[VERBOSE] Starting download from: {youtube_url}")
            logger.info(f"[VERBOSE] Output template: {output_template}")
            logger.info(f"[VERBOSE] Format: {self.format_string}")
        else:
            logger.info(f"Downloading from: {youtube_url}")

        # Retry logic with exponential backoff
        max_retries = 5
        base_delay = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)

                    ext = info.get("ext", "mp4")
                    final_file = output_directory / f"{base_filename}.{ext}"

                    if final_file.exists():
                        if self.verbose:
                            logger.info(f"[VERBOSE] Download successful: {final_file}")
                        else:
                            logger.info(f"Download successful: {final_file}")
                        return True, str(final_file), None, info
                    else:
                        error_msg = "Downloaded file not found"
                        logger.error(error_msg)
                        return False, None, error_msg, None

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if (
                    "403" in error_str
                    or "forbidden" in error_str
                    or "429" in error_str
                    or "too many" in error_str
                ):
                    if attempt < max_retries - 1:
                        import time

                        delay = base_delay * (2**attempt)
                        logger.warning(
                            f"Rate limit error, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        error_msg = f"Download failed after {max_retries} attempts: {e}"
                        logger.error(error_msg)
                        return False, None, error_msg, None
                else:
                    error_msg = f"Download error: {str(e)}"
                    logger.error(error_msg)
                    return False, None, error_msg, None

        error_msg = f"Download error: {last_error}"
        logger.error(error_msg)
        return False, None, error_msg, None

    def file_exists(
        self, series: Series, episode: Episode, output_directory: Path
    ) -> bool:
        """Check if a file already exists for this episode"""
        base_filename = self.build_jellyfin_filename(series, episode)
        existing_files = list(output_directory.glob(f"{base_filename}.*"))
        return len(existing_files) > 0

    def create_nfo_file(
        self,
        base_filename: str,
        output_directory: Path,
        video_info: dict,
        nfo_type: str = "episode",
    ) -> None:
        """
        Create a .nfo file with video metadata for Jellyfin/Kodi compatibility

        Args:
            base_filename: Base filename (without extension)
            output_directory: Directory where the NFO file should be saved
            video_info: Dictionary containing video metadata from yt-dlp
            nfo_type: Type of NFO file - "episode" for episodedetails, "movie" for movie format
        """
        nfo_path = output_directory / f"{base_filename}.nfo"

        # Determine root element based on type
        root_element = "episodedetails" if nfo_type == "episode" else "movie"

        # Escape all text content for XML safety
        title = self._escape_xml(video_info.get("title", "Unknown"))
        description = self._escape_xml(video_info.get("description", ""))
        channel = self._escape_xml(video_info.get("channel", ""))
        uploader = self._escape_xml(video_info.get("uploader", ""))
        video_id = self._escape_xml(video_info.get("id", ""))
        video_url = self._escape_xml(
            video_info.get("webpage_url", video_info.get("url", ""))
        )

        try:
            with open(nfo_path, "w", encoding="utf-8") as nfo:
                nfo.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
                nfo.write(f"<{root_element}>\n")
                nfo.write(f"  <title>{title}</title>\n")
                nfo.write(f"  <originaltitle>{title}</originaltitle>\n")
                nfo.write(f"  <studio>{channel}</studio>\n")
                nfo.write(f"  <director>{uploader}</director>\n")
                nfo.write("  <source>YouTube</source>\n")
                nfo.write(f"  <id>{video_id}</id>\n")
                nfo.write(f"  <youtubeurl>{video_url}</youtubeurl>\n")
                if video_info.get("duration"):
                    nfo.write(f"  <runtime>{video_info['duration'] // 60}</runtime>\n")
                nfo.write(f"</{root_element}>\n")
            logger.info(f"Created NFO file: {nfo_path}")
        except Exception as e:
            logger.warning(f"Failed to create NFO file: {e}")

    def get_episode_file_info(
        self, series: Series, episode: Episode, output_directory: Path
    ) -> dict:
        """
        Get detailed information about existing files for an episode

        Returns:
            Dictionary with file information:
            {
                'has_video': bool,
                'has_strm': bool,
                'video_file': str | None,
                'strm_file': str | None,
                'subtitles': {'fr': ['file1.fr.srt'], 'en': ['file2.en.srt']},
                'subtitle_count': int
            }
        """
        base_filename = self.build_jellyfin_filename(series, episode)

        # Create a pattern based on series and episode number only
        # Format: SeriesName - S00E##
        # This allows detection of files even if the episode title differs slightly
        # between Sonarr and the actual filename
        series_name = self.sanitize_filename(series.title)
        episode_pattern = (
            f"{series_name} - S{episode.season_number:02d}E{episode.episode_number:02d}"
        )

        # Use pathlib to list all files in directory and filter manually
        # This avoids glob pattern issues with special characters
        try:
            all_files = list(output_directory.iterdir())
        except Exception:
            all_files = []

        # Filter files that match the episode pattern (SeriesName - S00E##)
        # This is more tolerant than exact title matching and prevents re-downloading
        # files that exist but have slightly different titles
        existing_files = []
        for f in all_files:
            if not f.is_file():
                continue
            # Use the broader episode pattern for all file types
            if f.name.startswith(episode_pattern):
                existing_files.append(f)

        info: dict = {
            "has_video": False,
            "has_strm": False,
            "video_file": None,
            "strm_file": None,
            "subtitles": {},
            "subtitle_count": 0,
        }

        video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}

        for file in existing_files:
            if file.suffix.lower() in video_extensions:
                info["has_video"] = True
                info["video_file"] = file.name
            elif file.suffix.lower() == ".strm":
                info["has_strm"] = True
                info["strm_file"] = file.name
            elif file.suffix.lower() == ".srt":
                # Extract language code from filename
                # Format: Series - S00E01 - Title.lang.srt or Series - S00E01 - Title.srt
                # Remove base_filename to get the remaining part
                # Handle both cases: with dot separator and without
                if file.stem == base_filename:
                    # Exact match, no language code: Series - S00E01 - Title.srt
                    lang = "unknown"
                elif file.stem.startswith(base_filename + "."):
                    # With dot separator: Series - S00E01 - Title.lang.srt
                    remaining = file.stem[len(base_filename) + 1 :]
                    lang = remaining.split(".")[0] if remaining else "unknown"
                else:
                    # Fallback: try to extract from the end of filename
                    # Could be Series - S00E01 - Title.lang.srt or similar variations
                    parts = file.stem.split(".")
                    if len(parts) > 1:
                        # Last part before extension might be language code
                        lang = parts[-1]
                    else:
                        lang = "unknown"

                subtitles_dict = info["subtitles"]
                if lang not in subtitles_dict:
                    subtitles_dict[lang] = []
                subtitles_dict[lang].append(file.name)
                info["subtitle_count"] = info["subtitle_count"] + 1

        return info

    def get_movie_directory(
        self,
        movie: Movie,
        media_directory: str | None = None,
        radarr_directory: str | None = None,
    ) -> Path:
        """
        Determine the target directory for the movie extras

        If media_directory and radarr_directory are provided, do path mapping
        Otherwise use Radarr path directly
        """
        if media_directory and radarr_directory:
            # Map between Radarr path and real path
            radarr_path = Path(movie.path)
            try:
                # Replace Radarr root with real root
                relative_path = radarr_path.relative_to(radarr_directory)
                real_path = Path(media_directory) / relative_path
            except ValueError:
                # If path is not relative to radarr_directory, use as-is
                logger.warning(f"Cannot map path for {movie.path}")
                real_path = Path(movie.path)
        else:
            real_path = Path(movie.path)

        # Create extras directory if it doesn't exist
        extras_dir = real_path / "extras"
        extras_dir.mkdir(parents=True, exist_ok=True)

        return extras_dir

    def get_movie_extras_directory(
        self,
        movie: Movie,
        media_directory: str | None = None,
        radarr_directory: str | None = None,
    ) -> Path:
        """Alias for get_movie_directory for consistency with get_extras_directory"""
        return self.get_movie_directory(movie, media_directory, radarr_directory)

    def build_movie_extras_filename(self, movie: Movie, video_title: str) -> str:
        """
        Build a filename for movie extras
        Format: MovieName (Year) - ExtraTitle.ext
        """
        movie_name = self.sanitize_filename(movie.title)
        extra_title = self.sanitize_filename(video_title)

        year_str = f" ({movie.year})" if movie.year else ""
        filename = f"{movie_name}{year_str} - {extra_title}"

        return filename
