"""
Sonarr API Client
"""

import logging
from typing import Any

from .base_client import BaseArrClient
from .models import Episode, Season, Series

logger = logging.getLogger(__name__)


class SonarrClient(BaseArrClient[Series]):
    """Client to interact with Sonarr API"""

    def get_all_items(self) -> list[Series]:
        """Fetch all series (alias for get_all_series)"""
        return self.get_all_series()

    def get_monitored_items(self) -> list[Series]:
        """Fetch all monitored series (alias for get_monitored_series)"""
        return self.get_monitored_series()

    def rescan(self, item_id: int) -> Any:
        """Trigger a rescan for a specific series"""
        return self.rescan_series(item_id)

    def get_all_series(self) -> list[Series]:
        """Fetch all series"""
        data = self._get("series")
        series_list = []

        for item in data:
            seasons = [
                Season(
                    season_number=s["seasonNumber"],
                    monitored=s["monitored"],
                    statistics=s.get("statistics", {}),
                )
                for s in item.get("seasons", [])
            ]

            series = Series(
                id=item["id"],
                title=item["title"],
                path=item["path"],
                monitored=item["monitored"],
                seasons=seasons,
                year=item.get("year"),
                tvdb_id=item.get("tvdbId"),
                network=item.get("network"),
                tags=item.get("tags", []),
            )
            series_list.append(series)

        return series_list

    def get_monitored_series(self) -> list[Series]:
        """Fetch all monitored series"""
        all_series = self.get_all_series()
        return [s for s in all_series if s.monitored]

    def get_series_episodes(
        self, series_id: int, season_number: int | None = None
    ) -> list[Episode]:
        """Fetch episodes for a series"""
        params: dict[str, Any] = {"seriesId": series_id}
        if season_number is not None:
            params["seasonNumber"] = season_number

        data = self._get("episode", params=params)
        episodes = []

        for item in data:
            episode = Episode(
                id=item["id"],
                series_id=item["seriesId"],
                episode_number=item["episodeNumber"],
                season_number=item["seasonNumber"],
                title=item.get("title", "TBA"),
                has_file=item.get("hasFile", False),
                monitored=item.get("monitored", False),
                air_date=item.get("airDate"),
                overview=item.get("overview"),
            )
            episodes.append(episode)

        return episodes

    def get_season_zero_episodes(self, series_id: int) -> list[Episode]:
        """Fetch season 0 episodes (specials)"""
        return self.get_series_episodes(series_id, season_number=0)

    def has_monitored_season_zero(self, series: Series) -> bool:
        """Check if series has a monitored season 0"""
        for season in series.seasons:
            if season.season_number == 0 and season.monitored:
                return True
        return False

    def has_monitored_season_zero_episodes(self, series: Series) -> bool:
        """Check if series has monitored episodes in season 0"""
        try:
            episodes = self.get_season_zero_episodes(series.id)
            return any(ep.monitored for ep in episodes)
        except Exception as e:
            logger.warning(
                f"Error checking season 0 episodes for series {series.id}: {e}"
            )
            return False

    def rescan_series(self, series_id: int) -> Any:
        """Trigger a series scan in Sonarr"""
        logger.info(f"Triggering scan for series ID {series_id}")
        try:
            data = {"name": "RescanSeries", "seriesId": series_id}
            result = self._post("command", data)
            logger.info(f"Scan successfully triggered for series ID {series_id}")
            return result
        except Exception as e:
            logger.error(f"Error triggering scan: {e}")
            raise
