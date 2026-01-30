"""
Radarr API Client
"""

import logging
from typing import Any

from .base_client import BaseArrClient
from .models import Movie

logger = logging.getLogger(__name__)


class RadarrClient(BaseArrClient[Movie]):
    """Client to interact with Radarr API"""

    def get_all_items(self) -> list[Movie]:
        """Fetch all movies (alias for get_all_movies)"""
        return self.get_all_movies()

    def get_monitored_items(self) -> list[Movie]:
        """Fetch all monitored movies (alias for get_monitored_movies)"""
        return self.get_monitored_movies()

    def rescan(self, item_id: int) -> Any:
        """Trigger a rescan for a specific movie"""
        return self.rescan_movie(item_id)

    def get_all_movies(self) -> list[Movie]:
        """Fetch all movies"""
        data = self._get("movie")
        movie_list = []

        for item in data:
            movie = Movie(
                id=item["id"],
                title=item["title"],
                path=item["path"],
                monitored=item["monitored"],
                year=item.get("year"),
                tmdb_id=item.get("tmdbId"),
                studio=item.get("studio"),
                tags=item.get("tags", []),
                has_file=item.get("hasFile", False),
            )
            movie_list.append(movie)

        return movie_list

    def get_monitored_movies(self) -> list[Movie]:
        """Fetch all monitored movies"""
        all_movies = self.get_all_movies()
        return [m for m in all_movies if m.monitored]

    def rescan_movie(self, movie_id: int) -> Any:
        """Trigger a rescan for a specific movie"""
        data = {"name": "RescanMovie", "movieId": movie_id}
        return self._post("command", data)
