"""
Path management utilities for media files
"""

import re
from pathlib import Path

from ..models import Episode, Movie, Series


class PathManager:
    """Manages paths and filenames for media files"""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Clean a filename to make it compatible with filesystems"""
        # Replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)
        # Replace multiple spaces
        filename = re.sub(r"\s+", " ", filename)
        return filename.strip()

    @staticmethod
    def build_jellyfin_filename(series: Series, episode: Episode) -> str:
        """
        Build a Jellyfin-compatible filename
        Format: SeriesName - S00E## - EpisodeTitle.ext
        """
        series_name = PathManager.sanitize_filename(series.title)
        episode_title = PathManager.sanitize_filename(episode.title)

        # Jellyfin format for specials
        filename = f"{series_name} - S{episode.season_number:02d}E{episode.episode_number:02d} - {episode_title}"

        return filename

    @staticmethod
    def build_movie_extras_filename(movie: Movie, video_title: str) -> str:
        """Build a filename for movie extras"""
        movie_name = PathManager.sanitize_filename(movie.title)
        video_title_clean = PathManager.sanitize_filename(video_title)
        return f"{movie_name} - {video_title_clean}"

    @staticmethod
    def get_series_directory(
        series: Series,
        media_directory: str | None = None,
        sonarr_directory: str | None = None,
    ) -> Path:
        """
        Determine the target directory for the series (Specials folder)

        If media_directory and sonarr_directory are provided, do path mapping
        Otherwise use Sonarr path directly
        """
        real_path = PathManager._map_path(
            series.path, media_directory, sonarr_directory
        )

        # Create Specials directory if it doesn't exist
        specials_dir = real_path / "Specials"
        specials_dir.mkdir(parents=True, exist_ok=True)

        return specials_dir

    @staticmethod
    def get_extras_directory(
        series: Series,
        media_directory: str | None = None,
        sonarr_directory: str | None = None,
    ) -> Path:
        """
        Determine the target directory for extras (behind the scenes)
        """
        real_path = PathManager._map_path(
            series.path, media_directory, sonarr_directory
        )

        # Create extras directory if it doesn't exist
        extras_dir = real_path / "extras"
        extras_dir.mkdir(parents=True, exist_ok=True)

        return extras_dir

    @staticmethod
    def get_movie_directory(
        movie: Movie,
        media_directory: str | None = None,
        radarr_directory: str | None = None,
    ) -> Path:
        """
        Determine the target directory for the movie

        If media_directory and radarr_directory are provided, do path mapping
        Otherwise use Radarr path directly
        """
        real_path = PathManager._map_path(
            movie.path, media_directory, radarr_directory
        )

        # Create extras directory inside movie directory
        extras_dir = real_path / "extras"
        extras_dir.mkdir(parents=True, exist_ok=True)

        return extras_dir

    @staticmethod
    def get_movie_extras_directory(
        movie: Movie,
        media_directory: str | None = None,
        radarr_directory: str | None = None,
    ) -> Path:
        """Alias for get_movie_directory - extras go in movie folder"""
        return PathManager.get_movie_directory(movie, media_directory, radarr_directory)

    @staticmethod
    def _map_path(
        source_path: str,
        media_directory: str | None,
        arr_directory: str | None,
    ) -> Path:
        """
        Map a path from *arr application to real filesystem path

        Args:
            source_path: Path as reported by Sonarr/Radarr
            media_directory: Real filesystem path
            arr_directory: Path as configured in *arr application
        """
        if media_directory and arr_directory:
            source = Path(source_path)
            try:
                # Replace *arr root with real root
                relative_path = source.relative_to(arr_directory)
                return Path(media_directory) / relative_path
            except ValueError:
                # If path is not relative to arr_directory, use as-is
                return Path(source_path)
        return Path(source_path)
