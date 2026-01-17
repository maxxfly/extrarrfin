"""
Data models for ExtrarrFin
"""

from dataclasses import dataclass
from typing import List


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
    statistics: dict


@dataclass
class Series:
    """Represents a series in Sonarr"""

    id: int
    title: str
    path: str
    monitored: bool
    seasons: List[Season]
    year: int | None = None
    tvdb_id: int | None = None


@dataclass
class DownloadResult:
    """Download result"""

    success: bool
    episode: Episode
    series: Series
    file_path: str | None = None
    error: str | None = None
