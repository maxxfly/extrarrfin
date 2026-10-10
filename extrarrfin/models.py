"""
Data models for ExtrarrFin
"""

from dataclasses import dataclass
from typing import Any, TypedDict

# Raw metadata dictionaries produced by yt-dlp (``YoutubeDL.extract_info``).
# yt-dlp ships no type stubs, so the values are genuinely heterogeneous and
# stay ``Any``: naming the alias documents the boundary without pretending the
# keys are checked. Read every value through ``.get(key, default)``.
VideoInfo = dict[str, Any]


class EpisodeFileInfo(TypedDict):
    """Inventory of files already present for one episode.

    Built by ``Downloader.get_episode_file_info`` and read by the list command.
    """

    has_video: bool
    has_strm: bool
    video_file: str | None
    strm_file: str | None
    # language code -> subtitle filenames
    subtitles: dict[str, list[str]]
    subtitle_count: int


@dataclass
class Episode:
    """Represents an episode in Sonarr"""

    id: int
    series_id: int
    episode_number: int
    season_number: int
    title: str
    has_file: bool
    monitored: bool
    air_date: str | None = None
    overview: str | None = None


@dataclass
class Season:
    """Represents a season in Sonarr"""

    season_number: int
    monitored: bool
    # Keys are Sonarr's fixed statistic names; values are counts, ratios or flags.
    statistics: dict[str, int | float | bool]


@dataclass
class Series:
    """Represents a series in Sonarr"""

    id: int
    title: str
    path: str
    monitored: bool
    seasons: list[Season]
    year: int | None = None
    tvdb_id: int | None = None
    tmdb_id: int | None = None
    network: str | None = None
    tags: list[int] | None = None  # List of tag IDs from Sonarr


@dataclass
class Movie:
    """Represents a movie in Radarr"""

    id: int
    title: str
    path: str
    monitored: bool
    year: int | None = None
    tmdb_id: int | None = None
    imdb_id: str | None = None
    studio: str | None = None
    tags: list[int] | None = None  # List of tag IDs from Radarr
    has_file: bool = False


@dataclass
class DownloadResult:
    """Download result"""

    success: bool
    episode: Episode
    series: Series
    file_path: str | None = None
    error: str | None = None
