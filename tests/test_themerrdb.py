"""
Offline unit tests for the ThemerrDB client (``extrarrfin.themerrdb``).

No network access: ``requests.Session.get`` is replaced by a fake that answers
from a small routing table, so these tests run with ``pytest -m "not
integration"``.

Run:
    .venv/bin/pytest tests/test_themerrdb.py -v
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from yt_dlp.utils import DownloadError

from extrarrfin.downloader import Downloader
from extrarrfin.themerrdb import (
    APP_BASE,
    RAW_BASE,
    ThemerrDBClient,
    ThemerrTheme,
)

GOOT_THEME_URL = "https://www.youtube.com/watch?v=uXZd_W5B7N0"
INCEPTION_THEME_URL = "https://www.youtube.com/watch?v=RxabLA7UQ9k"
METROPOLIS_THEME_URL = "https://www.youtube.com/watch?v=HRKAhKKMDuc"


class _FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(self, status_code: int, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class _FakeSession:
    """Serve canned responses from a ``url -> _FakeResponse`` mapping.

    Unknown URLs answer 404, which mirrors a missing ThemerrDB entry. Raised
    exceptions are recorded so tests can assert the fallback behaviour.
    """

    def __init__(self, routes: dict[str, _FakeResponse | Exception]):
        self.routes = routes
        self.requested: list[str] = []

    def get(self, url, timeout=None, **_kwargs):
        self.requested.append(url)
        route = self.routes.get(url)
        if route is None:
            return _FakeResponse(404)
        if isinstance(route, Exception):
            raise route
        return route


def _url(base: str, path: str) -> str:
    return f"{base}/{path}"


def _client(routes: dict[str, _FakeResponse | Exception]) -> ThemerrDBClient:
    return ThemerrDBClient(session=_FakeSession(routes))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# URL construction / happy paths
# ---------------------------------------------------------------------------


def test_lookup_series_builds_themoviedb_url():
    path = "tv_shows/themoviedb/1399.json"
    client = _client(
        {_url(APP_BASE, path): _FakeResponse(200, {"youtube_theme_url": GOOT_THEME_URL})}
    )

    theme = client.lookup_series(1399)

    assert isinstance(theme, ThemerrTheme)
    assert theme.youtube_url == GOOT_THEME_URL
    assert theme.source_url == _url(APP_BASE, path)
    assert client.session.requested == [_url(APP_BASE, path)]  # type: ignore[attr-defined]


def test_lookup_movie_prefers_themoviedb():
    tmdb_path = "movies/themoviedb/27205.json"
    client = _client(
        {
            _url(
                APP_BASE, tmdb_path
            ): _FakeResponse(200, {"title": "Inception", "youtube_theme_url": INCEPTION_THEME_URL})
        }
    )

    theme = client.lookup_movie(27205, "tt1375666")

    assert theme is not None
    assert theme.youtube_url == INCEPTION_THEME_URL
    assert theme.title == "Inception"
    # The IMDb key must not be queried when TMDB already answered.
    assert client.session.requested == [_url(APP_BASE, tmdb_path)]  # type: ignore[attr-defined]


def test_lookup_movie_falls_back_to_imdb_key():
    imdb_path = "movies/imdb/tt0017136.json"
    client = _client(
        {
            _url(
                APP_BASE, imdb_path
            ): _FakeResponse(200, {"title": "Metropolis", "youtube_theme_url": METROPOLIS_THEME_URL})
        }
    )

    theme = client.lookup_movie(999999, "tt0017136")

    assert theme is not None
    assert theme.youtube_url == METROPOLIS_THEME_URL
    assert theme.source_url == _url(APP_BASE, imdb_path)


def test_series_title_falls_back_to_name_key():
    path = "tv_shows/themoviedb/615.json"
    client = _client(
        {
            _url(
                APP_BASE, path
            ): _FakeResponse(200, {"name": "Futurama", "youtube_theme_url": GOOT_THEME_URL})
        }
    )

    theme = client.lookup_series(615)

    assert theme is not None
    assert theme.title == "Futurama"


# ---------------------------------------------------------------------------
# Misses and error tolerance
# ---------------------------------------------------------------------------


def test_lookup_series_returns_none_when_entry_absent():
    client = _client({})

    assert client.lookup_series(12345) is None


def test_lookup_returns_none_when_theme_key_missing():
    """An entry can exist without a curated theme yet."""
    path = "tv_shows/themoviedb/86831.json"
    client = _client({_url(APP_BASE, path): _FakeResponse(200, {"name": "Love, Death & Robots"})})

    assert client.lookup_series(86831) is None


@pytest.mark.parametrize("value", ["", "   ", None, 42])
def test_lookup_returns_none_for_unusable_theme_url(value):
    path = "movies/themoviedb/550.json"
    client = _client(
        {_url(APP_BASE, path): _FakeResponse(200, {"youtube_theme_url": value})}
    )

    assert client.lookup_movie(550) is None


def test_no_id_means_no_http_request():
    session = _FakeSession({})
    client = ThemerrDBClient(session=session)  # type: ignore[arg-type]

    assert client.lookup_series(None) is None
    assert client.lookup_movie(None) is None
    assert client.lookup_movie(None, None) is None
    assert session.requested == []


def test_theme_url_is_trimmed():
    path = "tv_shows/themoviedb/615.json"
    client = _client(
        {_url(APP_BASE, path): _FakeResponse(200, {"youtube_theme_url": f"  {GOOT_THEME_URL} "})}
    )

    theme = client.lookup_series(615)

    assert theme is not None
    assert theme.youtube_url == GOOT_THEME_URL


def test_http_error_is_treated_as_miss():
    path = "tv_shows/themoviedb/1399.json"
    client = _client({_url(APP_BASE, path): _FakeResponse(503)})

    assert client.lookup_series(1399) is None


def test_invalid_json_is_treated_as_miss():
    path = "tv_shows/themoviedb/1399.json"
    client = _client({_url(APP_BASE, path): _FakeResponse(200, None)})

    assert client.lookup_series(1399) is None


def test_non_dict_payload_is_treated_as_miss():
    path = "tv_shows/themoviedb/1399.json"
    client = _client({_url(APP_BASE, path): _FakeResponse(200, ["unexpected", "list"])})

    assert client.lookup_series(1399) is None


def test_raw_githubusercontent_is_tried_when_app_fails():
    """A transport failure on the primary origin must not hide a valid entry."""
    path = "tv_shows/themoviedb/1399.json"
    session = _FakeSession(
        {
            _url(APP_BASE, path): requests.ConnectionError("dns failure"),
            _url(RAW_BASE, path): _FakeResponse(200, {"youtube_theme_url": GOOT_THEME_URL}),
        }
    )
    client = ThemerrDBClient(session=session)  # type: ignore[arg-type]

    theme = client.lookup_series(1399)

    assert theme is not None
    assert theme.source_url == _url(RAW_BASE, path)
    assert session.requested == [_url(APP_BASE, path), _url(RAW_BASE, path)]


def test_lookup_survives_total_origin_failure():
    """Network errors must never propagate: YouTube fallback still has to run."""
    client = ThemerrDBClient(
        session=_FakeSession(  # type: ignore[arg-type]
            {
                url: requests.Timeout("timed out")
                for base in (APP_BASE, RAW_BASE)
                for url in (
                    _url(base, "tv_shows/themoviedb/1399.json"),
                    _url(base, "movies/themoviedb/27205.json"),
                    _url(base, "movies/imdb/tt1375666.json"),
                )
            }
        )
    )

    assert client.lookup_series(1399) is None
    assert client.lookup_movie(27205, "tt1375666") is None


def test_bases_are_normalised_and_never_empty():
    client = ThemerrDBClient(bases=["https://example.com/"])

    assert client.bases == ["https://example.com"]

    assert ThemerrDBClient(bases=[]).bases == [APP_BASE]


# ---------------------------------------------------------------------------
# Downloader integration (still offline)
# ---------------------------------------------------------------------------


def _downloader_with_theme(youtube_url: str | None) -> Downloader:
    """Return a Downloader whose ThemerrDB client always yields *youtube_url*."""
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)
    theme = (
        ThemerrTheme(
            youtube_url=youtube_url,
            title="Sample",
            source_url=_url(APP_BASE, "tv_shows/themoviedb/1399.json"),
        )
        if youtube_url
        else None
    )
    # The lambdas take fewer/renamed params than the real methods, so mypy flags
    # the monkeypatch; the call sites in Downloader only pass positionally.
    downloader.themerrdb.lookup_series = lambda *_a: theme  # type: ignore[assignment]
    downloader.themerrdb.lookup_movie = lambda *_a, **_k: theme  # type: ignore[assignment]
    return downloader


def test_try_themerrdb_dry_run_reports_target_path(tmp_path: Path):
    downloader = _downloader_with_theme(GOOT_THEME_URL)

    ok, path, err = downloader._try_themerrdb(
        "Game of Thrones", tmp_path, dry_run=True, tmdb_id=1399
    )

    assert ok is True
    assert err is None
    assert path == str(tmp_path / "theme.mp3")
    assert not (tmp_path / "theme.mp3").exists()


def test_try_themerrdb_download_delegates_to_audio_downloader(tmp_path: Path):
    downloader = _downloader_with_theme(INCEPTION_THEME_URL)

    with pytest.MonkeyPatch.context() as monkeypatch:
        calls: list[str] = []

        def _fake_download(url: str, output_dir: Path):
            calls.append(url)
            return True, str(output_dir / "theme.mp3"), None

        monkeypatch.setattr(
            downloader, "_download_audio_from_url", _fake_download, raising=False
        )
        ok, path, err = downloader._try_themerrdb(
            "Inception", tmp_path, dry_run=False, tmdb_id=27205, is_series=False
        )

    assert ok is True
    assert err is None
    assert path == str(tmp_path / "theme.mp3")
    assert calls == [INCEPTION_THEME_URL]


def test_try_themerrdb_miss_reports_ids_without_breaking_the_chain(tmp_path: Path):
    downloader = _downloader_with_theme(None)

    ok, path, err = downloader._try_themerrdb(
        "Unknown Show", tmp_path, dry_run=True, tmdb_id=4242
    )

    assert ok is False
    assert path is None
    # The message is unprefixed: download_theme() adds the source label.
    assert err is not None
    assert err == "no curated theme for tmdb_id=4242"


def test_try_themerrdb_miss_message_for_movies(tmp_path: Path):
    downloader = _downloader_with_theme(None)

    _ok, _path, err = downloader._try_themerrdb(
        "Unknown Movie", tmp_path, dry_run=True, tmdb_id=1, imdb_id="tt1", is_series=False
    )

    assert err is not None
    assert err == "no curated theme for tmdb_id=1 / imdb_id=tt1"


def test_try_themerrdb_without_any_id(tmp_path: Path):
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    ok, _path, err = downloader._try_themerrdb("No IDs", tmp_path, dry_run=True)

    assert ok is False
    assert err is not None
    assert "no TMDB ID available" in err


def test_audio_download_reports_yt_dlp_failure(tmp_path: Path):
    """A yt-dlp error (e.g. HTTP 403 rate limit) must be surfaced, not the
    misleading "no audio file found to convert"."""
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    class _ForbiddenYoutubeDL:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, _urls):
            raise DownloadError(
                "ERROR: unable to download video data: HTTP Error 403: Forbidden"
            )

    output_dir = tmp_path / "show"

    with patch("extrarrfin.downloader.yt_dlp.YoutubeDL", _ForbiddenYoutubeDL):
        ok, path, err = downloader._download_audio_from_url(
            "https://www.youtube.com/watch?v=whatever", output_dir
        )

    assert ok is False
    assert path is None
    assert err is not None
    assert "yt-dlp download failed" in err
    assert "403" in err


def test_try_themerrdb_client_crash_is_reported_as_miss(tmp_path: Path):
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    def _boom(_tmdb_id):
        raise RuntimeError("unexpected client bug")

    downloader.themerrdb.lookup_series = _boom  # type: ignore[method-assign]

    ok, _path, err = downloader._try_themerrdb(
        "Broken", tmp_path, dry_run=True, tmdb_id=1399
    )

    assert ok is False
    assert err is not None
    assert err.startswith("ThemerrDB error: ")


def test_download_theme_skips_themerrdb_without_ids(tmp_path: Path):
    """No curated lookup is attempted when neither TMDB nor IMDb is known.

    ThemerrDB has no TVDB index, so a series identified only by its TVDB id
    (which is what the broken lookup used to rely on) must skip the source
    instead of requesting a URL that cannot exist.
    """
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)
    attempts: list[str] = []

    def _record(*_args, **_kwargs):
        attempts.append("themerrdb")
        return False, None, "not reached"

    downloader._try_themerrdb = _record  # type: ignore[method-assign]
    downloader._try_televisiontunes = lambda *_a, **_k: (False, None, "nope")  # type: ignore[assignment]
    downloader._try_youtube_theme = lambda *_a, **_k: (False, None, "nope")  # type: ignore[assignment]

    ok, path, err = downloader.download_theme("No IDs Show", tmp_path, dry_run=True)
    assert ok is False
    assert path is None
    assert attempts == []
    assert err is not None and "YouTube" in err


def test_download_theme_uses_themerrdb_first(tmp_path: Path):
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)
    calls: list[str] = []

    def _fake_themerrdb(*_args, **_kwargs):
        calls.append("themerrdb")
        return True, str(tmp_path / "theme.mp3"), None

    def _fake_televisiontunes(*_args, **_kwargs):
        calls.append("televisiontunes")
        return True, str(tmp_path / "theme.mp3"), None

    downloader._try_themerrdb = _fake_themerrdb  # type: ignore[method-assign]
    downloader._try_televisiontunes = _fake_televisiontunes  # type: ignore[method-assign]

    ok, path, err = downloader.download_theme(
        "Game of Thrones", tmp_path, dry_run=True, tmdb_id=1399
    )

    assert ok is True
    assert err is None
    assert path == str(tmp_path / "theme.mp3")
    assert calls == ["themerrdb"]


def test_download_theme_falls_through_to_next_source(tmp_path: Path):
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    downloader._try_themerrdb = lambda *_a, **_k: (  # type: ignore[method-assign]
        False,
        None,
        "ThemerrDB: no curated theme for tmdb_id=86831",
    )
    downloader._try_televisiontunes = lambda *_a, **_k: (  # type: ignore[assignment]
        True,
        str(tmp_path / "theme.mp3"),
        None,
    )

    ok, path, err = downloader.download_theme(
        "Love, Death & Robots", tmp_path, dry_run=True, tmdb_id=86831
    )

    assert ok is True
    assert err is None
    assert path == str(tmp_path / "theme.mp3")


def test_download_theme_passes_imdb_id_for_movies(tmp_path: Path):
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)
    seen: dict = {}

    def _capture(title, output_dir, dry_run, tmdb_id=None, imdb_id=None, is_series=True):
        seen.update(
            tmdb_id=tmdb_id, imdb_id=imdb_id, is_series=is_series, title=title
        )
        return True, str(output_dir / "theme.mp3"), None

    downloader._try_themerrdb = _capture  # type: ignore[method-assign]

    ok, _path, _err = downloader.download_theme(
        "Metropolis",
        tmp_path,
        dry_run=True,
        tmdb_id=None,
        imdb_id="tt0017136",
        is_series=False,
    )

    assert ok is True
    assert seen == {
        "tmdb_id": None,
        "imdb_id": "tt0017136",
        "is_series": False,
        "title": "Metropolis",
    }
