"""
Download module via yt-dlp with Jellyfin formatting
"""

import logging
import re
from pathlib import Path
from typing import Tuple

import yt_dlp

from .models import Episode, Series

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
            "extract_flat": True,
            "default_search": "ytsearch5",  # Get top 5 results for better matching
            "sleep_requests": 1,  # Sleep 1 second between requests to avoid 429 errors
        }

        # First attempt: series title + episode title
        if episode.title and episode.title != "TBA":
            query_with_series = f"{series.title} {episode.title}"
            if self.verbose:
                logger.info(f"[VERBOSE] YouTube search query: '{query_with_series}'")
            else:
                logger.info(f"YouTube search (with series): {query_with_series}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_url = f"ytsearch5:{query_with_series}"
                    if self.verbose:
                        logger.info(f"[VERBOSE] Full search URL: {search_url}")

                    result = ydl.extract_info(search_url, download=False)

                    if result and "entries" in result and result["entries"]:
                        # Score each result to find the best match
                        best_video = self._score_and_select_video(
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
                    search_url = f"ytsearch5:{query_episode_only}"
                    if self.verbose:
                        logger.info(f"[VERBOSE] Full search URL: {search_url}")

                    result = ydl.extract_info(search_url, download=False)

                    if result and "entries" in result and result["entries"]:
                        # Score each result to find the best match
                        best_video = self._score_and_select_video(
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

    def _score_and_select_video(
        self, videos: list, series: Series, episode_title: str
    ) -> dict | None:
        """
        Score video results based on title matching and select the best one

        Scoring factors:
        - Exact title match: +100 points
        - Contains episode title: +50 points
        - Channel matches network: +40 points
        - Word match ratio: +40 points max
        - Contains series title: +30 points
        - Shorter title (less extra content): +20 points max
        - Official/verified channel indicators: +10 points

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

        if self.verbose and network_lower:
            logger.info(f"[VERBOSE] Series network: {series.network}")

        for video in videos:
            if not video:
                continue

            title = video.get("title", "")
            title_lower = title.lower()
            channel = video.get("channel", "")
            channel_lower = channel.lower()
            score = 0

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

            # Word matching ratio
            title_words = set(title_lower.split())
            common_words = search_words & title_words
            if search_words:
                word_ratio = len(common_words) / len(search_words)
                score += word_ratio * 40

            # Prefer shorter titles (less likely to be compilations or unrelated content)
            title_length = len(title)
            if title_length < 100:
                score += 20 * (1 - title_length / 100)

            # Check for official/quality indicators
            title_and_channel = (title + " " + video.get("channel", "")).lower()
            if any(
                word in title_and_channel for word in ["official", "vevo", "verified"]
            ):
                score += 10

            # Penalize certain patterns that indicate wrong content
            if any(
                word in title_lower
                for word in ["compilation", "playlist", "all episodes", "full series"]
            ):
                score -= 30

            # Store score in video dict
            video["_score"] = score
            scored_videos.append(video)

            if self.verbose:
                logger.info(
                    f"[VERBOSE] Candidate: {title[:60]}... (score: {score:.2f})"
                )

        # Return video with highest score
        if scored_videos:
            best = max(scored_videos, key=lambda v: v.get("_score", 0))
            return best

        return None

    def create_strm_file(
        self,
        series: Series,
        episode: Episode,
        output_directory: Path,
        youtube_url: str,
        dry_run: bool = False,
    ) -> Tuple[bool, str | None, str | None]:
        """
        Create a STRM file pointing to direct video stream URL and download subtitles

        Args:
            series: Series object
            episode: Episode object
            output_directory: Directory to save the STRM file
            youtube_url: YouTube URL to extract stream from
            dry_run: If True, simulate without creating files

        Returns:
            Tuple (success, file_path, error_message)
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
                    return False, None, "Could not extract stream URL"

            if dry_run:
                logger.info(f"DRY RUN: Would create STRM file: {strm_file}")
                return True, str(strm_file), None

            # Write direct stream URL to STRM file
            with open(strm_file, "w", encoding="utf-8") as f:
                f.write(stream_url)

            logger.info(f"STRM file created: {strm_file}")

            # Download subtitles separately (they will be placed next to the STRM file)
            self._download_subtitles_only(youtube_url, output_directory, base_filename)

            return True, str(strm_file), None

        except Exception as e:
            error_msg = f"Error creating STRM file: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

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
    ) -> Tuple[bool, str | None, str | None]:
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
            Tuple (success, file_path, error_message)
        """
        # Build filename
        base_filename = self.build_jellyfin_filename(series, episode)

        # Check if file already exists
        existing_files = list(output_directory.glob(f"{base_filename}.*"))

        # If dry-run and files exist, report and return early
        if dry_run and existing_files:
            if force:
                logger.info(
                    f"DRY RUN: Would delete and re-download: {existing_files[0].name}"
                )
            else:
                logger.info(f"DRY RUN: File already exists: {existing_files[0].name}")
            return True, str(existing_files[0]), None

        # If not force mode and files exist, just return (file already present)
        if existing_files and not force:
            logger.info(f"File already exists: {existing_files[0].name}")
            return True, str(existing_files[0]), None

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
                return False, None, error_msg

        # If dry-run mode, return success without downloading
        if dry_run:
            logger.info(f"DRY RUN: Would download from {youtube_url}")
            output_template = f"{base_filename}.mp4"
            return True, str(output_directory / output_template), None

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

        try:
            if self.verbose:
                logger.info(f"[VERBOSE] Starting download from: {youtube_url}")
                logger.info(f"[VERBOSE] Output template: {output_template}")
                logger.info(f"[VERBOSE] Format: {self.format_string}")
                logger.info(
                    f"[VERBOSE] Subtitle languages: {', '.join(self.subtitle_languages)}"
                )
            else:
                logger.info(f"Downloading from: {youtube_url}")

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
                    return True, str(final_file), None
                else:
                    error_msg = "Downloaded file not found"
                    logger.error(error_msg)
                    return False, None, error_msg

        except Exception as e:
            error_msg = f"Download error: {str(e)}"
            logger.error(error_msg)
            return False, None, error_msg

    def file_exists(
        self, series: Series, episode: Episode, output_directory: Path
    ) -> bool:
        """Check if a file already exists for this episode"""
        base_filename = self.build_jellyfin_filename(series, episode)
        existing_files = list(output_directory.glob(f"{base_filename}.*"))
        return len(existing_files) > 0

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

        # Use pathlib to list all files in directory and filter manually
        # This avoids glob pattern issues with special characters
        try:
            all_files = list(output_directory.iterdir())
        except Exception:
            all_files = []

        # Filter files that start with our base_filename
        existing_files = [
            f
            for f in all_files
            if f.is_file() and f.name.startswith(base_filename + ".")
        ]

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
                # Remove base_filename and leading dot to get the remaining part
                remaining = file.stem[len(base_filename) :]
                if remaining.startswith("."):
                    remaining = remaining[1:]

                # If there's a remaining part, it's the language code
                if remaining:
                    lang = remaining.split(".")[0]  # Take first part if multiple dots
                else:
                    lang = "unknown"

                subtitles_dict = info["subtitles"]
                if lang not in subtitles_dict:
                    subtitles_dict[lang] = []
                subtitles_dict[lang].append(file.name)
                info["subtitle_count"] = info["subtitle_count"] + 1

        return info
