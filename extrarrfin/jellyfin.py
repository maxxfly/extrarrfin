"""
Jellyfin API client for library refresh
"""

import logging

import requests

logger = logging.getLogger(__name__)


class JellyfinClient:
    """Client to interact with Jellyfin API"""

    def __init__(self, url: str, api_key: str):
        """
        Initialize Jellyfin client

        Args:
            url: Jellyfin server URL (e.g., http://localhost:8096)
            api_key: Jellyfin API key/token
        """
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "X-Emby-Token": api_key,
            "Content-Type": "application/json",
        }

    def refresh_library(self) -> bool:
        """
        Trigger a library refresh/scan in Jellyfin

        Returns:
            True if successful, False otherwise
        """
        try:
            # Endpoint to refresh all libraries
            endpoint = f"{self.url}/Library/Refresh"

            logger.info(f"Triggering Jellyfin library refresh at {self.url}")
            response = requests.post(endpoint, headers=self.headers, timeout=10)

            if response.status_code == 204:
                logger.info("Jellyfin library refresh triggered successfully")
                return True
            else:
                logger.warning(
                    f"Jellyfin refresh returned status code {response.status_code}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to trigger Jellyfin library refresh: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test connection to Jellyfin server

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            endpoint = f"{self.url}/System/Info"
            response = requests.get(endpoint, headers=self.headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Connected to Jellyfin server: {data.get('ServerName', 'Unknown')} "
                    f"(version {data.get('Version', 'Unknown')})"
                )
                return True
            else:
                logger.warning(
                    f"Jellyfin connection test failed with status {response.status_code}"
                )
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Jellyfin: {e}")
            return False
