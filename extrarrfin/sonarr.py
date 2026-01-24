"""
Sonarr API Client
"""

import logging
from typing import List

import requests

from .models import Episode, Season, Series

logger = logging.getLogger(__name__)


class SonarrClient:
    """Client to interact with Sonarr API"""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {"X-Api-Key": api_key, "Content-Type": "application/json"}
        )

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Perform a GET request to the API"""
        url = f"{self.url}/api/v3/{endpoint}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: dict) -> dict:
        """Perform a POST request to the API"""
        url = f"{self.url}/api/v3/{endpoint}"
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint: str, data: dict) -> dict:
        """Perform a PUT request to the API"""
        url = f"{self.url}/api/v3/{endpoint}"
        response = self.session.put(url, json=data)
        response.raise_for_status()
        return response.json()

    def get_all_series(self) -> List[Series]:
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
            )
            series_list.append(series)

        return series_list

    def get_monitored_series(self) -> List[Series]:
        """Fetch all monitored series"""
        all_series = self.get_all_series()
        return [s for s in all_series if s.monitored]

    def get_series_episodes(
        self, series_id: int, season_number: int | None = None
    ) -> List[Episode]:
        """Fetch episodes for a series"""
        params = {"seriesId": series_id}
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

    def get_season_zero_episodes(self, series_id: int) -> List[Episode]:
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

    def rescan_series(self, series_id: int):
        """Trigger a series scan in Sonarr"""
        logger.info(f"Triggering scan for series ID {series_id}")
        try:
            data = {"name": "RescanSeries", "seriesId": series_id}
            self._post("command", data)
            logger.info(f"Scan successfully triggered for series ID {series_id}")
        except Exception as e:
            logger.error(f"Error triggering scan: {e}")
            raise

    def refresh_series(self, series_id: int):
        """Refresh series metadata"""
        logger.info(f"Refreshing metadata for series ID {series_id}")
        try:
            data = {"name": "RefreshSeries", "seriesId": series_id}
            self._post("command", data)
            logger.info(f"Refresh triggered for series ID {series_id}")
        except Exception as e:
            logger.error(f"Error during refresh: {e}")
            raise

    def rename_files(self, series_id: int, season_number: int):
        """Rename files according to Sonarr rules"""
        logger.info(f"Renaming files for series {series_id}, season {season_number}")
        try:
            # Get series files
            episodes = self.get_series_episodes(series_id, season_number)
            file_ids = [ep.id for ep in episodes if ep.has_file]

            if file_ids:
                data = {"name": "RenameFiles", "seriesId": series_id, "files": file_ids}
                self._post("command", data)
                logger.info(f"Rename triggered for {len(file_ids)} files")
        except Exception as e:
            logger.error(f"Error during rename: {e}")
            raise
