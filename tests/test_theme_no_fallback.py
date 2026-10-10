"""
Offline unit tests for the ``--no-fallback`` theme option.

``--no-fallback`` restricts theme resolution to the two curated sources
(ThemerrDB then TelevisionTunes) and never reaches the YouTube search.

No network access: every source method is replaced by a recorder, so these
tests run with ``pytest -m "not integration"``.

Run:
    .venv/bin/pytest tests/test_theme_no_fallback.py -v
"""

from pathlib import Path

import pytest

from extrarrfin.downloader import Downloader
from extrarrfin.models import Movie, Season, Series


class _SourceRecorder:
    """Record calls to a theme source and return a canned result."""

    def __init__(self, name: str, calls: list[str], succeed: bool = False):
        self.name = name
        self.calls = calls
        self.succeed = succeed

    def __call__(self, *_args, **_kwargs):
        self.calls.append(self.name)
        if self.succeed:
            return True, "/tmp/theme.mp3", None
        return False, None, f"{self.name}: nothing found"


def _make_downloader(calls: list[str], themerrdb_ok: bool = False, tunes_ok: bool = False):
    """Return a Downloader whose three theme sources are recorders."""
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)
    downloader._try_themerrdb = _SourceRecorder(  # type: ignore[method-assign]
        "themerrdb", calls, succeed=themerrdb_ok
    )
    downloader._try_televisiontunes = _SourceRecorder(  # type: ignore[method-assign]
        "televisiontunes", calls, succeed=tunes_ok
    )
    downloader._try_youtube_theme = _SourceRecorder("youtube", calls)  # type: ignore[method-assign]
    return downloader


# ---------------------------------------------------------------------------
# Downloader.download_theme(no_fallback=...)
# ---------------------------------------------------------------------------


def test_no_fallback_never_calls_youtube(tmp_path: Path):
    calls: list[str] = []
    downloader = _make_downloader(calls)

    ok, path, err = downloader.download_theme(
        "Uncovered Movie", tmp_path, dry_run=True, tmdb_id=517302,
        is_series=False, no_fallback=True,
    )

    assert ok is False
    assert path is None
    assert calls == ["themerrdb"], "only ThemerrDB may run for a movie"
    assert err is not None and "YouTube" not in err


def test_no_fallback_still_tries_televisiontunes_for_series(tmp_path: Path):
    calls: list[str] = []
    downloader = _make_downloader(calls)

    ok, _path, _err = downloader.download_theme(
        "Uncovered Show", tmp_path, dry_run=True, tmdb_id=86831,
        is_series=True, no_fallback=True,
    )

    assert ok is False
    assert calls == ["themerrdb", "televisiontunes"]


def test_no_fallback_succeeds_when_themerrdb_has_the_theme(tmp_path: Path):
    calls: list[str] = []
    downloader = _make_downloader(calls, themerrdb_ok=True)

    ok, path, err = downloader.download_theme(
        "Game of Thrones", tmp_path, dry_run=True, tmdb_id=1399, no_fallback=True
    )

    assert ok is True
    assert path == "/tmp/theme.mp3"
    assert err is None
    assert calls == ["themerrdb"]


def test_no_fallback_succeeds_when_televisiontunes_has_the_theme(tmp_path: Path):
    calls: list[str] = []
    downloader = _make_downloader(calls, tunes_ok=True)

    ok, path, _err = downloader.download_theme(
        "Breaking Bad", tmp_path, dry_run=True, tmdb_id=81189, no_fallback=True
    )

    assert ok is True
    assert path == "/tmp/theme.mp3"
    assert calls == ["themerrdb", "televisiontunes"]


def test_no_fallback_reports_both_curated_errors(tmp_path: Path):
    calls: list[str] = []
    downloader = _make_downloader(calls)

    _ok, _path, err = downloader.download_theme(
        "Uncovered Show", tmp_path, dry_run=True, tmdb_id=86831, no_fallback=True
    )

    assert err is not None
    assert "themerrdb" in err.lower()
    assert "televisiontunes" in err.lower()


def test_no_fallback_for_series_without_id_still_uses_televisiontunes(tmp_path: Path):
    """TelevisionTunes searches by title, so it stays available without an id."""
    calls: list[str] = []
    downloader = _make_downloader(calls)

    ok, _path, err = downloader.download_theme(
        "No Ids Show", tmp_path, dry_run=True, is_series=True, no_fallback=True
    )

    assert ok is False
    assert calls == ["televisiontunes"]
    assert err is not None and "themerrdb" not in err.lower()


def test_no_fallback_movie_without_any_id_explains_why(tmp_path: Path):
    """A movie needs an id for ThemerrDB and never uses TelevisionTunes, so
    with no id at all there is no curated source to try."""
    calls: list[str] = []
    downloader = _make_downloader(calls)

    ok, _path, err = downloader.download_theme(
        "No Ids Movie", tmp_path, dry_run=True, is_series=False, no_fallback=True
    )

    assert ok is False
    assert calls == []
    assert err is not None
    assert "no curated source available" in err


def test_default_behaviour_still_falls_back_to_youtube(tmp_path: Path):
    """Without the flag the YouTube fallback must remain reachable."""
    calls: list[str] = []
    downloader = _make_downloader(calls)

    ok, _path, _err = downloader.download_theme(
        "Uncovered Movie", tmp_path, dry_run=True, tmdb_id=517302, is_series=False
    )

    assert ok is False
    assert calls == ["themerrdb", "youtube"]


def test_default_behaviour_for_series_keeps_all_three_sources(tmp_path: Path):
    calls: list[str] = []
    downloader = _make_downloader(calls)

    _ok, _path, _err = downloader.download_theme(
        "Uncovered Show", tmp_path, dry_run=True, tmdb_id=86831
    )

    assert calls == ["themerrdb", "televisiontunes", "youtube"]


def test_no_fallback_does_not_bypass_existing_theme_file(tmp_path: Path):
    """An already downloaded theme.mp3 is still skipped before any source."""
    calls: list[str] = []
    downloader = _make_downloader(calls)
    (tmp_path / "theme.mp3").write_bytes(b"fake")

    ok, path, err = downloader.download_theme(
        "Any Show", tmp_path, dry_run=False, tmdb_id=1399, no_fallback=True
    )

    assert ok is True
    assert path == str(tmp_path / "theme.mp3")
    assert err is None
    assert calls == []


# ---------------------------------------------------------------------------
# download_theme_mode() propagation
# ---------------------------------------------------------------------------


class _FakeSonarr:
    def __init__(self, series):
        self._series = series

    def get_all_series(self):
        return self._series


class _FakeConfig:
    media_directory = None
    sonarr_directory = None
    radarr_directory = None


def _series_with_content(title: str, tmdb_id: int) -> Series:
    return Series(
        id=1,
        title=title,
        path="/media/TV/Show",
        monitored=True,
        seasons=[Season(season_number=1, monitored=True, statistics={"episodeFileCount": 5})],
        tmdb_id=tmdb_id,
    )


@pytest.mark.parametrize("no_fallback", [True, False])
def test_download_theme_mode_propagates_no_fallback(tmp_path: Path, no_fallback: bool):
    from extrarrfin.commands.theme_handler import download_theme_mode

    seen: dict = {}
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    def _capture(*_args, **kwargs):
        seen.update(kwargs)
        return True, str(tmp_path / "theme.mp3"), None

    downloader.download_theme = _capture  # type: ignore[method-assign]
    downloader.get_series_root_directory = lambda *_a, **_k: tmp_path  # type: ignore[assignment]

    total, successful, failed = download_theme_mode(
        _FakeConfig(),  # type: ignore[arg-type]
        _FakeSonarr([_series_with_content("Severance", 95396)]),  # type: ignore[arg-type]
        downloader,
        radarr=None,
        dry_run=True,
        no_fallback=no_fallback,
    )

    assert (total, successful, failed) == (1, 1, 0)
    assert seen.get("no_fallback") is no_fallback


def test_download_theme_mode_passes_tmdb_id_for_series(tmp_path: Path):
    from extrarrfin.commands.theme_handler import download_theme_mode

    seen: dict = {}
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    def _capture(*_args, **kwargs):
        seen.update(kwargs)
        return True, str(tmp_path / "theme.mp3"), None

    downloader.download_theme = _capture  # type: ignore[method-assign]
    downloader.get_series_root_directory = lambda *_a, **_k: tmp_path  # type: ignore[assignment]

    download_theme_mode(
        _FakeConfig(),  # type: ignore[arg-type]
        _FakeSonarr([_series_with_content("Severance", 95396)]),  # type: ignore[arg-type]
        downloader,
        radarr=None,
        dry_run=True,
    )

    assert seen.get("tmdb_id") == 95396


def test_download_theme_mode_passes_imdb_id_for_movies(tmp_path: Path):
    from extrarrfin.commands.theme_handler import download_theme_mode

    seen: dict = {}
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    def _capture(*_args, **kwargs):
        seen.update(kwargs)
        return True, str(tmp_path / "theme.mp3"), None

    downloader.download_theme = _capture  # type: ignore[method-assign]
    downloader.get_movie_root_directory = lambda *_a, **_k: tmp_path  # type: ignore[assignment]

    movie = Movie(
        id=2,
        title="Metropolis",
        path="/media/Films/Metropolis",
        monitored=True,
        tmdb_id=None,
        imdb_id="tt0017136",
        has_file=True,
    )

    class _FakeRadarr:
        def get_all_movies(self):
            return [movie]

    download_theme_mode(
        _FakeConfig(),  # type: ignore[arg-type]
        _FakeSonarr([]),  # type: ignore[arg-type]
        downloader,
        radarr=_FakeRadarr(),  # type: ignore[arg-type]
        dry_run=True,
        no_fallback=True,
    )

    assert seen.get("imdb_id") == "tt0017136"
    assert seen.get("no_fallback") is True
    assert seen.get("is_series") is False
