"""
Download module via yt-dlp with Jellyfin formatting
"""

import logging
import os
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
    ):
        self.format_string = format_string

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
        Search for a video on YouTube
        Returns the URL of the first video found

        First tries: series title + episode title
        If not found, tries: episode title only
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch1",
        }

        # First attempt: series title + episode title
        if episode.title and episode.title != "TBA":
            query_with_series = f"{series.title} {episode.title}"
            logger.info(f"YouTube search (with series): {query_with_series}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(
                        f"ytsearch1:{query_with_series}", download=False
                    )

                    if result and "entries" in result and result["entries"]:
                        video = result["entries"][0]
                        video_url = f"https://www.youtube.com/watch?v={video['id']}"
                        logger.info(f"Video found: {video.get('title')} - {video_url}")
                        return video_url
            except Exception as e:
                logger.error(f"Error during YouTube search: {e}")

            # Second attempt: episode title only
            query_episode_only = episode.title
            logger.info(f"YouTube search (episode only): {query_episode_only}")

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(
                        f"ytsearch1:{query_episode_only}", download=False
                    )

                    if result and "entries" in result and result["entries"]:
                        video = result["entries"][0]
                        video_url = f"https://www.youtube.com/watch?v={video['id']}"
                        logger.info(f"Video found: {video.get('title')} - {video_url}")
                        return video_url
            except Exception as e:
                logger.error(f"Error during YouTube search: {e}")

        return None

    def download_episode(
        self,
        series: Series,
        episode: Episode,
        output_directory: Path,
        force: bool = False,
        youtube_url: str | None = None,
    ) -> Tuple[bool, str | None, str | None]:
        """
        Download an episode from YouTube

        Returns:
            Tuple (success, file_path, error_message)
        """
        # Build filename
        base_filename = self.build_jellyfin_filename(series, episode)

        # Check if file already exists
        existing_files = list(output_directory.glob(f"{base_filename}.*"))
        if existing_files and not force:
            logger.info(f"File already exists: {existing_files[0].name}")
            return True, str(existing_files[0]), None

        # Search on YouTube if URL is not provided
        if not youtube_url:
            youtube_url = self.search_youtube(series, episode)
            if not youtube_url:
                error_msg = "No video found on YouTube"
                logger.warning(error_msg)
                return False, None, error_msg

        # yt-dlp options
        output_template = str(output_directory / f"{base_filename}.%(ext)s")

        ydl_opts = {
            "format": self.format_string,
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["fr", "en"],
            "ignoreerrors": True,  # Ignore subtitle download errors
            "postprocessors": [
                {
                    "key": "FFmpegEmbedSubtitle",
                    "already_have_subtitle": False,
                }
            ],
        }

        try:
            logger.info(f"Downloading from: {youtube_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)

                # Find downloaded file
                ext = info.get("ext", "mp4")
                final_file = output_directory / f"{base_filename}.{ext}"

                if final_file.exists():
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
