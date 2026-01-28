"""
Radarr API Client
"""

import logging
from typing import List

import requests

from .models import Movie

logger = logging.getLogger(__name__)


class RadarrClient:
    """Client to interact with Radarr API"""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {"X-Api-Key": api_key, "Content-Type": "application/json"}
        )
        # Cache for tags
        self._tags_cache: dict[int, str] | None = None

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

    def get_all_tags(self) -> dict[int, str]:
        """Fetch all tags and return a mapping of tag_id -> tag_label"""
        if self._tags_cache is not None:
            return self._tags_cache

        data = self._get("tag")
        self._tags_cache = {tag["id"]: tag["label"] for tag in data}
        return self._tags_cache

    def get_all_movies(self) -> List[Movie]:
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

    def get_monitored_movies(self) -> List[Movie]:
        """Fetch all monitored movies"""
        all_movies = self.get_all_movies()
        return [m for m in all_movies if m.monitored]

    def rescan_movie(self, movie_id: int):
        """Trigger a rescan for a specific movie"""
        data = {"name": "RescanMovie", "movieId": movie_id}
        return self._post("command", data)

    def has_want_extras_tag(self, movie: Movie) -> bool:
        """Check if movie has 'want-extras' or 'want_extras' tag"""
        if not movie.tags:
            return False

        # Get all tags to map IDs to labels
        all_tags = self.get_all_tags()

        # Check if any of the movie tags match want-extras or want_extras
        for tag_id in movie.tags:
            tag_label = all_tags.get(tag_id, "").lower()
            if tag_label in ["want-extras", "want_extras"]:
                return True

        return False

    def test_connection(self) -> bool:
        """Test the connection to Radarr"""
        try:
            self._get("system/status")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
