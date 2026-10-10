"""
ThemerrDB client - https://app.lizardbyte.dev/ThemerrDB/

ThemerrDB is a community-curated database that maps a title to the YouTube
video of its theme music. The site is a static Jekyll build published from the
``gh-pages`` branch of ``LizardByte/ThemerrDB``; every entry is served as a JSON
file keyed by the id of the upstream metadata database::

    tv_shows/themoviedb/{tmdb_id}.json   -> series
    movies/themoviedb/{tmdb_id}.json     -> movies
    movies/imdb/{imdb_id}.json           -> movies (alternate key)

Note that series are keyed by **TMDB** id, not TVDB id.

The interesting key of each response is ``youtube_theme_url``. Entries that
exist but have no curated theme yet simply omit it, which is reported as a miss.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Primary origin: the exact files the ThemerrDB web app loads.
APP_BASE = "https://app.lizardbyte.dev/ThemerrDB"

# Fallback origin: the same ``gh-pages`` content served straight from GitHub.
RAW_BASE = "https://raw.githubusercontent.com/LizardByte/ThemerrDB/gh-pages"

DEFAULT_TIMEOUT = 10


@dataclass
class ThemerrTheme:
    """A curated theme returned by ThemerrDB."""

    youtube_url: str
    title: str | None
    source_url: str


class ThemerrDBClient:
    """Read-only client for the ThemerrDB static JSON database."""

    def __init__(
        self,
        bases: Iterable[str] = (APP_BASE, RAW_BASE),
        timeout: int = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ):
        self.bases = [base.rstrip("/") for base in bases if base] or [APP_BASE]
        self.timeout = timeout
        self.session = session or requests.Session()

    # ------------------------------------------------------------------ public
    def lookup_series(self, tmdb_id: int | None) -> ThemerrTheme | None:
        """Return the curated theme of a series, or ``None`` when unknown."""
        if not tmdb_id:
            logger.debug("ThemerrDB: no TMDB id available for series lookup")
            return None
        return self._lookup(f"tv_shows/themoviedb/{tmdb_id}.json")

    def lookup_movie(
        self,
        tmdb_id: int | None,
        imdb_id: str | None = None,
    ) -> ThemerrTheme | None:
        """Return the curated theme of a movie, or ``None`` when unknown.

        TMDB is tried first because it is the id Radarr always exposes, IMDb is
        used as an alternate key when the TMDB lookup misses.
        """
        paths = []
        if tmdb_id:
            paths.append(f"movies/themoviedb/{tmdb_id}.json")
        if imdb_id:
            paths.append(f"movies/imdb/{imdb_id}.json")

        if not paths:
            logger.debug("ThemerrDB: no TMDB/IMDb id available for movie lookup")
            return None

        for path in paths:
            theme = self._lookup(path)
            if theme:
                return theme
        return None

    # ------------------------------------------------------------------ private
    def _lookup(self, path: str) -> ThemerrTheme | None:
        """Fetch *path* from each origin in order until one yields a theme.

        A 404 means the entry is absent from the database; the remaining
        origins are still tried so that a partial mirror cannot hide a valid
        entry. Transport errors are logged and swallowed: ThemerrDB is only the
        first of several theme sources, so a failure must not abort the search.
        """
        for base in self.bases:
            url = f"{base}/{path}"
            data = self._fetch_json(url)
            if data is None:
                continue
            theme = self._extract(data, url)
            if theme:
                return theme
        return None

    def _fetch_json(self, url: str) -> Any | None:
        """Return the JSON payload at *url*, or ``None`` on any failure."""
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            logger.debug(f"ThemerrDB: request failed for {url}: {exc}")
            return None

        if resp.status_code == 404:
            logger.debug(f"ThemerrDB: no entry at {url}")
            return None
        if resp.status_code != 200:
            logger.debug(f"ThemerrDB: HTTP {resp.status_code} for {url}")
            return None

        try:
            return resp.json()
        except ValueError as exc:
            logger.debug(f"ThemerrDB: invalid JSON at {url}: {exc}")
            return None

    @staticmethod
    def _extract(data: Any, url: str) -> ThemerrTheme | None:
        """Build a :class:`ThemerrTheme` from a fetched payload."""
        if not isinstance(data, dict):
            logger.debug(f"ThemerrDB: unexpected payload shape at {url}")
            return None

        youtube_url = data.get("youtube_theme_url")
        if not isinstance(youtube_url, str) or not youtube_url.strip():
            logger.debug(f"ThemerrDB: no youtube_theme_url at {url}")
            return None

        title = data.get("title") or data.get("name")
        return ThemerrTheme(
            youtube_url=youtube_url.strip(),
            title=title if isinstance(title, str) else None,
            source_url=url,
        )
