"""
Download module via yt-dlp with Jellyfin formatting
"""

import logging
import re
from pathlib import Path
from typing import Tuple

import yt_dlp

from .downloader_utils.nfo import NFOWriter
from .downloader_utils.paths import PathManager
from .downloader_utils.strm import STRMWriter
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

        # Initialize helper classes
        self._path_manager = PathManager()
        self._nfo_writer = NFOWriter()
        self._strm_writer = STRMWriter()

    # Delegate to PathManager
    def sanitize_filename(self, filename: str) -> str:
        """Clean a filename to make it compatible"""
        return PathManager.sanitize_filename(filename)

    def build_jellyfin_filename(self, series: Series, episode: Episode) -> str:
        """Build a Jellyfin-compatible filename"""
        return PathManager.build_jellyfin_filename(series, episode)

    def get_series_directory(
        self,
        series: Series,
        media_directory: str | None = None,
        sonarr_directory: str | None = None,
    ) -> Path:
        """Determine the target directory for the series (Specials)"""
        return PathManager.get_series_directory(
            series, media_directory, sonarr_directory
        )

    def get_extras_directory(
        self,
        series: Series,
        media_directory: str | None = None,
        sonarr_directory: str | None = None,
    ) -> Path:
        """Determine the target directory for extras"""
        return PathManager.get_extras_directory(
            series, media_directory, sonarr_directory
        )

    def get_movie_directory(
        self,
        movie: Movie,
        media_directory: str | None = None,
        radarr_directory: str | None = None,
    ) -> Path:
        """Determine the target directory for movie extras"""
        return PathManager.get_movie_directory(movie, media_directory, radarr_directory)

    def get_movie_extras_directory(
        self,
        movie: Movie,
        media_directory: str | None = None,
        radarr_directory: str | None = None,
    ) -> Path:
        """Alias for get_movie_directory"""
        return PathManager.get_movie_extras_directory(
            movie, media_directory, radarr_directory
        )

    def build_movie_extras_filename(self, movie: Movie, video_title: str) -> str:
        """Build a filename for movie extras"""
        return PathManager.build_movie_extras_filename(movie, video_title)

    # Delegate to NFOWriter
    def create_nfo_file(
        self,
        base_filename: str,
        output_directory: Path,
        video_info: dict,
        nfo_type: str = "episode",
    ) -> None:
        """Create a .nfo file with video metadata"""
        NFOWriter.create_nfo_file(base_filename, output_directory, video_info, nfo_type)

    def get_existing_video_ids(self, directory: Path) -> set[str]:
        """Get video IDs from existing NFO files in a directory"""
        return NFOWriter.extract_video_ids_from_nfo_files(directory)

    # Delegate to STRMWriter
    def create_strm_file(
        self,
        youtube_url: str,
        base_filename: str,
        output_directory: Path,
    ) -> Path:
        """Create a .strm file containing the YouTube URL"""
        return STRMWriter.create_strm_file(youtube_url, base_filename, output_directory)

    @staticmethod
    def _cleanup_part_files(output_directory: Path, base_filename: str) -> None:
        """Clean up any .part files left behind after a failed download"""
        try:
            for part_file in output_directory.glob(f"{base_filename}.*.part"):
                logger.info(f"Cleaning up incomplete file: {part_file.name}")
                part_file.unlink()
        except Exception as e:
            logger.warning(f"Could not clean up .part files: {e}")

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

    def search_youtube_behind_scenes(
        self, series: Series, exclude_ids: set[str] | None = None
    ) -> list[dict] | None:
        """
        Search for behind the scenes videos on YouTube
        Returns a list of video dictionaries with metadata (id, title, url, etc.)

        Searches for: "series title - behind the scenes"
        Uses the scoring system to find the best matches

        Args:
            series: Series object to search for
            exclude_ids: Set of video IDs to exclude (already downloaded)
        """
        if exclude_ids is None:
            exclude_ids = set()

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
                    # Filter out already downloaded videos before scoring
                    filtered_entries = [
                        entry
                        for entry in result["entries"]
                        if entry
                        and entry.get("id")
                        and entry.get("id") not in exclude_ids
                    ]

                    if self.verbose and len(filtered_entries) < len(result["entries"]):
                        excluded_count = len(result["entries"]) - len(filtered_entries)
                        logger.info(
                            f"[VERBOSE] Excluded {excluded_count} already downloaded videos"
                        )

                    # Score each result to find the best matches
                    scored_videos = self.scorer.score_behind_scenes_videos(
                        filtered_entries, series
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
        self,
        query: str,
        title: str,
        verbose: bool = False,
        year: int | None = None,
        exclude_ids: set[str] | None = None,
    ) -> dict | None:
        """
        Generic search for extras content on YouTube (movies or series)
        Returns the best matching video after validation

        Args:
            query: Search query (e.g., "Movie Title behind the scenes")
            title: Title to match against (movie or series name)
            verbose: Enable verbose logging
            year: Optional year of the movie (for better filtering)
            exclude_ids: Set of video IDs to exclude (already downloaded)

        Returns:
            Video info dict or None if no suitable video found
        """
        if exclude_ids is None:
            exclude_ids = set()

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": f"ytsearch{self.youtube_search_results}",
            "sleep_requests": 1,
        }

        if verbose:
            logger.info(f"[VERBOSE] YouTube search query: '{query}'")

        title_lower = title.lower()

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_url = f"ytsearch{self.youtube_search_results}:{query}"
                if verbose:
                    logger.info(f"[VERBOSE] Full search URL: {search_url}")

                result = ydl.extract_info(search_url, download=False)

                if result and "entries" in result and result["entries"]:
                    # Score and filter candidates
                    candidates = []
                    for video in result["entries"]:
                        if not video or not video.get("id"):
                            continue

                        video_id = video.get("id")
                        # Skip videos already downloaded in this session
                        if video_id in exclude_ids:
                            if verbose:
                                logger.info(
                                    f"[VERBOSE] Skipping already downloaded: {video.get('title')}"
                                )
                            continue

                        video_title = video.get("title", "").lower()
                        score = 0

                        # Must contain movie/series title
                        if title_lower in video_title:
                            score += 50
                        else:
                            # Skip videos that don't mention the title at all
                            continue

                        # Bonus if video mentions the year (for movies)
                        if year:
                            if str(year) in video_title:
                                score += 40
                            # Also check for adjacent years (sometimes listed differently)
                            elif (
                                str(year - 1) in video_title
                                or str(year + 1) in video_title
                            ):
                                score += 20

                        # Penalty if video contains other movie/show names
                        # (indicates it's for a different production)
                        other_titles_keywords = [
                            "rapunzel",
                            "tangled",
                            "white collar",
                            "the wanted",
                            "most wanted",
                            "america's most wanted",
                            "wanted man",
                        ]
                        for other_title in other_titles_keywords:
                            if other_title in video_title:
                                score -= 100  # Heavy penalty

                        # Bonus for extras-related keywords
                        extras_keywords = [
                            "behind the scenes",
                            "making of",
                            "featurette",
                            "interview",
                            "deleted",
                            "bloopers",
                            "bts",
                            "on set",
                            "alternate",
                            "gag reel",
                            "vfx",
                            "special effect",
                            "visual effect",
                        ]
                        for keyword in extras_keywords:
                            if keyword in video_title:
                                score += 30
                                break

                        # Penalty for unrelated content
                        penalty_keywords = [
                            "gameplay",
                            "walkthrough",
                            "reaction",
                            "review",
                            "trailer",
                            "teaser",
                            "music video",
                            "official video",
                            "lyric",
                            "movie clip",
                            "scene",
                            "all action",
                            "then and now",
                            "cast then",
                            "best scenes",
                            "full movie",
                            "movie mistakes",
                            "where to watch",
                            "how to watch",
                            "explained",
                            "breakdown",
                            "rampage",
                            "analysis",
                            "the guns of",
                            "the art of",
                            "(action)",
                            "(horror)",
                            "(comedy)",
                            "(drama)",
                            "full hd",
                            "1080p",
                            "4k uhd",
                        ]
                        for keyword in penalty_keywords:
                            if keyword in video_title:
                                score -= 40

                        if score > 0:
                            candidates.append((score, video))
                            if verbose:
                                logger.info(
                                    f"[VERBOSE] Candidate: {video.get('title')} (score: {score})"
                                )

                    # Sort by score (highest first)
                    candidates.sort(key=lambda x: x[0], reverse=True)

                    # Try each candidate until we find one that's accessible
                    for score, video in candidates:
                        video_id = video["id"]
                        video_url = f"https://www.youtube.com/watch?v={video_id}"

                        # Validate video is accessible
                        try:
                            validate_opts = {
                                "quiet": True,
                                "no_warnings": True,
                                "skip_download": True,
                            }
                            with yt_dlp.YoutubeDL(validate_opts) as validate_ydl:
                                video_info = validate_ydl.extract_info(
                                    video_url, download=False
                                )
                                if video_info:
                                    result_info = {
                                        "id": video_id,
                                        "url": video_url,
                                        "webpage_url": video_url,
                                        "title": video_info.get("title", "Unknown"),
                                        "channel": video_info.get("channel", "Unknown"),
                                        "uploader": video_info.get(
                                            "uploader",
                                            video_info.get("channel", "Unknown"),
                                        ),
                                        "description": video_info.get(
                                            "description", ""
                                        ),
                                        "duration": video_info.get("duration", 0),
                                        "view_count": video_info.get("view_count", 0),
                                    }

                                    if verbose:
                                        logger.info(
                                            f"[VERBOSE] Valid video found: {result_info['title']} (score: {score})"
                                        )
                                        logger.info(f"[VERBOSE] Video URL: {video_url}")

                                    return result_info
                        except Exception as e:
                            if verbose:
                                logger.info(
                                    f"[VERBOSE] Video {video_id} not accessible: {e}"
                                )
                            continue

        except Exception as e:
            logger.error(f"Error during YouTube search: {e}")

        return None

    def create_strm_file_for_episode(
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
                "sleep_subtitles": 3,  # Sleep 3 seconds before downloading subtitles
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
            return self.create_strm_file_for_episode(
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
            "sleep_subtitles": 3,  # Sleep 3 seconds before downloading subtitles
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
                print(
                    f"[Download] Attempt {attempt + 1}/{max_retries} for: {youtube_url}"
                )
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
                        print(
                            f"[Download] Rate limit error, retrying in {delay}s... (attempt {attempt + 2}/{max_retries})"
                        )
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
        # Check if file already exists (exclude .part and .nfo files)
        video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}
        existing_files = [
            f
            for f in output_directory.glob(f"{base_filename}.*")
            if f.suffix in video_extensions and not f.name.endswith(".part")
        ]

        # If not force mode and valid files exist, just return
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
            "sleep_subtitles": 3,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": self.subtitle_languages,
            "continuedl": True,  # Resume partial downloads
            "noprogress": False,
            "allsubtitles": self.download_all_subtitles,
            "subtitlesformat": "srt",
            "ignore_no_formats_error": True,  # Don't fail if subtitle format unavailable
            "skip_unavailable_fragments": True,  # Skip unavailable subtitle fragments
            "ignoreerrors": "only_download",  # Ignore subtitle errors but not video errors
            "fragment_retries": 10,  # Retry fragments (parts of video) up to 10 times
            "retries": 10,  # Retry failed downloads up to 10 times
            "file_access_retries": 3,  # Retry file access operations
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

        # First, get video info to check available subtitles (avoids 429 errors on unavailable languages)
        try:
            info_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(info_opts) as info_ydl:
                video_info = info_ydl.extract_info(youtube_url, download=False)

                # Get available subtitle languages
                available_subs = set()
                if video_info:
                    if video_info.get("subtitles"):
                        available_subs.update(video_info["subtitles"].keys())
                    if video_info.get("automatic_captions"):
                        available_subs.update(video_info["automatic_captions"].keys())

                # Filter requested languages to only those available
                if available_subs:
                    requested_langs = set(self.subtitle_languages)
                    available_requested = requested_langs.intersection(available_subs)

                    if available_requested:
                        # Only request exact matches to avoid 429 on unavailable languages
                        ydl_opts["subtitleslangs"] = list(available_requested)
                        if self.verbose:
                            logger.info(
                                f"[VERBOSE] Available subtitles: {', '.join(sorted(available_subs))}"
                            )
                            logger.info(
                                f"[VERBOSE] Requesting only available: {', '.join(sorted(available_requested))}"
                            )
                    else:
                        # No matching subtitles, disable subtitle download to avoid 429
                        ydl_opts["writesubtitles"] = False
                        ydl_opts["writeautomaticsub"] = False
                        if self.verbose:
                            logger.info(
                                "[VERBOSE] No requested subtitles available, skipping subtitle download"
                            )
                else:
                    # No subtitles at all
                    ydl_opts["writesubtitles"] = False
                    ydl_opts["writeautomaticsub"] = False
                    if self.verbose:
                        logger.info("[VERBOSE] No subtitles available for this video")
        except Exception as e:
            # If we can't get info, continue with original settings
            if self.verbose:
                logger.warning(f"[VERBOSE] Could not pre-check subtitles: {e}")

        # Small delay after subtitle check to avoid immediate rate limiting
        import time

        time.sleep(2)

        # Retry logic with exponential backoff
        max_retries = 5
        base_delay = 2
        last_error = None
        tried_fallback_format = False

        for attempt in range(max_retries):
            try:
                # Clean up .part files before retry to avoid corruption issues
                if attempt > 0:
                    self._cleanup_part_files(output_directory, base_filename)
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Retry attempt {attempt + 1}/{max_retries}"
                        )

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)

                    # Check if download was actually successful
                    if not info:
                        raise Exception(
                            "No video info returned - download may have failed"
                        )

                    ext = info.get("ext", "mp4")
                    final_file = output_directory / f"{base_filename}.{ext}"

                    if final_file.exists():
                        if self.verbose:
                            logger.info(f"[VERBOSE] Download successful: {final_file}")
                        else:
                            logger.info(f"Download successful: {final_file}")
                        return True, str(final_file), None, info
                    else:
                        # File not found - might be a rate limit or download failure
                        # Check for common error indicators in the process
                        raise Exception(
                            "Downloaded file not found - download may have been blocked"
                        )

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if (
                    "403" in error_str
                    or "forbidden" in error_str
                    or "429" in error_str
                    or "too many" in error_str
                ):
                    # Clean up .part files immediately after error
                    self._cleanup_part_files(output_directory, base_filename)

                    if attempt < max_retries - 1:
                        import time

                        delay = base_delay * (2**attempt)

                        # After 2 failed attempts with 403, try a simpler format
                        if (
                            "403" in error_str
                            and attempt >= 2
                            and not tried_fallback_format
                        ):
                            ydl_opts["format"] = "best[ext=mp4]/best"
                            tried_fallback_format = True
                            logger.warning(
                                "403 Forbidden - trying simpler format: best[ext=mp4]/best"
                            )
                        else:
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
                    # Clean up any .part files left behind
                    self._cleanup_part_files(output_directory, base_filename)
                    return False, None, error_msg, None

        error_msg = f"Download error: {last_error}"
        logger.error(error_msg)
        # Clean up any .part files left behind
        self._cleanup_part_files(output_directory, base_filename)
        return False, None, error_msg, None

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
