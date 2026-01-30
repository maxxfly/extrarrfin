"""
Base API Client for *arr applications (Sonarr, Radarr, etc.)
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

import requests

logger = logging.getLogger(__name__)

# Generic type for media items (Series, Movie, etc.)
T = TypeVar("T")


class BaseArrClient(ABC, Generic[T]):
    """Base client for *arr applications API"""

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(
            {"X-Api-Key": api_key, "Content-Type": "application/json"}
        )
        # Cache for tags
        self._tags_cache: dict[int, str] | None = None

    def _get(self, endpoint: str, params: dict | None = None) -> Any:
        """Perform a GET request to the API"""
        url = f"{self.url}/api/v3/{endpoint}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: dict) -> Any:
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

    def has_want_extras_tag(self, media: Any) -> bool:
        """Check if media item has 'want-extras' or 'want_extras' tag"""
        if not hasattr(media, "tags") or not media.tags:
            return False

        # Get all tags to map IDs to labels
        all_tags = self.get_all_tags()

        # Check if any of the media tags match want-extras or want_extras
        for tag_id in media.tags:
            tag_label = all_tags.get(tag_id, "").lower()
            if tag_label in ["want-extras", "want_extras"]:
                return True

        return False

    def test_connection(self) -> bool:
        """Test the connection to the *arr application"""
        try:
            self._get("system/status")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    @abstractmethod
    def get_all_items(self) -> list[T]:
        """Fetch all items (series/movies) - must be implemented by subclasses"""
        pass

    @abstractmethod
    def get_monitored_items(self) -> list[T]:
        """Fetch all monitored items - must be implemented by subclasses"""
        pass

    @abstractmethod
    def rescan(self, item_id: int) -> Any:
        """Trigger a rescan for a specific item - must be implemented by subclasses"""
        pass
