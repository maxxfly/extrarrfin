"""
Integration tests – download a theme from ThemerrDB (app.lizardbyte.dev).

These are the first tests that exercise the whole curated-theme path:
ThemerrDB lookup → yt-dlp → FFmpeg → ``theme.mp3`` on disk.  They need a live
internet connection and are therefore marked ``integration``.

Run:
    .venv/bin/pytest tests/test_themerrdb_download.py -v -m integration

Skip when offline:
    .venv/bin/pytest -m "not integration"

How to add / update expected URLs
---------------------------------
1. Remove the URL from ``THEME_CASES`` for the title you want to re-check.
2. Run the test – it skips and prints the URL ThemerrDB currently serves, e.g.
       SKIPPED - No expected_url configured for 'Severance'. Found: https://…
3. Paste that URL back into ``THEME_CASES`` after verifying it is the real
   main theme.
"""

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
import requests

from extrarrfin.downloader import Downloader
from extrarrfin.themerrdb import APP_BASE, ThemerrDBClient

pytestmark = pytest.mark.integration

# YouTube rate-limits its media servers and answers HTTP 403/429 when several
# downloads run back to back. That is an environment limitation, not a
# ThemerrDB regression, so the download tests retry and then skip.
_TRANSIENT_YOUTUBE_MARKERS = ("403", "429", "Forbidden", "Too Many Requests")
_MAX_ATTEMPTS = 3
_RETRY_PAUSE_S = 3.0


@dataclass
class ThemeCase:
    """One ThemerrDB entry to verify."""

    title: str
    is_series: bool
    tmdb_id: int | None
    imdb_id: str | None
    expected_url: str | None


# Entries verified against ThemerrDB and against the actual theme music.
THEME_CASES = [
    ThemeCase(
        "Game of Thrones", True, 1399, None,
        "https://www.youtube.com/watch?v=uXZd_W5B7N0",
    ),
    ThemeCase(
        "Severance", True, 95396, None,
        # ThemerrDB points at the official "Main Titles" from the soundtrack
        # (ComingSoon.net). The fan upload used by test_youtube_search.py is a
        # different video of the same theme.
        "https://www.youtube.com/watch?v=BNQS5u7SHiI",
    ),
    ThemeCase(
        "Inception", False, 27205, None,
        "https://www.youtube.com/watch?v=RxabLA7UQ9k",
    ),
    # No TMDB id on purpose: exercises the IMDb key for movies.
    ThemeCase(
        "Metropolis", False, None, "tt0017136",
        "https://www.youtube.com/watch?v=HRKAhKKMDuc",
    ),
]

# A ThemerrDB entry that exists but has no curated theme yet.
UNCOVERED_SERIES_TMDB_ID = 86831  # Love, Death & Robots

_CASE_IDS = [c.title for c in THEME_CASES]


def _app_available() -> bool:
    """Return True when the ThemerrDB site answers."""
    try:
        resp = requests.get(f"{APP_BASE}/tv_shows/pages.json", timeout=10)
    except requests.RequestException:
        return False
    return resp.status_code == 200


def _youtube_available() -> bool:
    """Return True when YouTube answers (yt-dlp needs it to download audio)."""
    try:
        resp = requests.get("https://www.youtube.com", timeout=10)
    except requests.RequestException:
        return False
    return resp.status_code == 200


@pytest.fixture(scope="module")
def require_themerrdb() -> None:
    if not _app_available():
        pytest.skip("ThemerrDB (app.lizardbyte.dev) is unreachable")


def _lookup(case: ThemeCase) -> str | None:
    client = ThemerrDBClient()
    theme = (
        client.lookup_series(case.tmdb_id)
        if case.is_series
        else client.lookup_movie(case.tmdb_id, case.imdb_id)
    )
    return theme.youtube_url if theme else None


# ---------------------------------------------------------------------------
# 1. The curated lookup itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", THEME_CASES, ids=_CASE_IDS)
def test_themerrdb_lookup_returns_curated_youtube_url(
    require_themerrdb: None, case: ThemeCase
):
    youtube_url = _lookup(case)

    if case.expected_url is None:
        pytest.skip(
            f"No expected_url configured for '{case.title}'. Found: {youtube_url}"
        )

    assert youtube_url is not None, (
        f"ThemerrDB no longer serves a theme for '{case.title}' "
        f"(tmdb_id={case.tmdb_id}, imdb_id={case.imdb_id}) — the endpoint layout "
        "may have changed again"
    )
    assert youtube_url == case.expected_url


def test_themerrdb_lookup_reports_uncovered_entry_as_miss(require_themerrdb: None):
    """A title present in ThemerrDB but without a theme must be a clean miss."""
    assert _lookup(ThemeCase("Love, Death & Robots", True, UNCOVERED_SERIES_TMDB_ID, None, None)) is None


# ---------------------------------------------------------------------------
# 2. The first real download: ThemerrDB → theme.mp3
# ---------------------------------------------------------------------------


def _audio_info(path: Path) -> dict[str, str] | None:
    """Return the ffprobe stream info for *path*, or None when unreadable."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    cmd = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name,duration",
        "-of",
        "default=noprint_wrappers=1",
        str(path),
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    info: dict[str, str] = {}
    for line in out.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            info[key.strip()] = value.strip()
    return info


def _is_transient_youtube_error(err: str | None) -> bool:
    """Return True when *err* is a YouTube rate-limit/block, not a bug."""
    if not err:
        return False
    return any(marker in err for marker in _TRANSIENT_YOUTUBE_MARKERS)


def _run_with_retry(call) -> tuple[bool, str | None, str | None]:
    """Run a download *call* until it succeeds or the retries are exhausted.

    Returns the last (ok, path, err) triple.  When every attempt failed on a
    transient YouTube error, the caller skips via :func:`_skip_if_transient`.
    """
    result = (False, None, None)
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        result = call()
        if result[0]:
            return result
        if not _is_transient_youtube_error(result[2]):
            return result
        if attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_PAUSE_S)
    return result


def _skip_if_transient(result: tuple[bool, str | None, str | None]) -> None:
    """Skip the test when the failure was a transient YouTube error."""
    ok, _path, err = result
    if ok:
        return
    if not _youtube_available():
        pytest.skip(f"YouTube unreachable, cannot download: {err}")
    if _is_transient_youtube_error(err):
        pytest.skip(
            f"YouTube rate-limited the download after {_MAX_ATTEMPTS} attempts: {err}"
        )


def _make_downloader() -> Downloader:
    return Downloader(youtube_search_results=10, min_score=30.0, verbose=False)


def _download_theme(
    downloader: Downloader, case: ThemeCase, output_dir: Path
) -> tuple[bool, str | None, str | None]:
    """Call ``_try_themerrdb`` with retry on transient YouTube failures."""
    return _run_with_retry(
        lambda: downloader._try_themerrdb(
            case.title,
            output_dir,
            dry_run=False,
            tmdb_id=case.tmdb_id,
            imdb_id=case.imdb_id,
            is_series=case.is_series,
        )
    )


@pytest.mark.parametrize("case", THEME_CASES[:2], ids=_CASE_IDS[:2])
def test_themerrdb_download_writes_theme_mp3(
    require_themerrdb: None, tmp_path: Path, case: ThemeCase
):
    """Download the curated theme and check a real MP3 lands on disk."""
    downloader = _make_downloader()
    output_dir = tmp_path / case.title
    output_dir.mkdir(parents=True)

    result = _download_theme(downloader, case, output_dir)
    _skip_if_transient(result)
    ok, path, err = result

    assert ok, f"ThemerrDB download failed for '{case.title}': {err}"
    assert path is not None
    theme_file = Path(path)
    assert theme_file == output_dir / "theme.mp3"
    assert theme_file.exists(), f"ThemerrDB reported success but {theme_file} is missing"

    size_bytes = theme_file.stat().st_size
    assert size_bytes > 20_000, f"theme.mp3 suspiciously small: {size_bytes} bytes"

    # No intermediate webm/mp4/m4a may survive next to the mp3.
    leftovers = [p.name for p in output_dir.glob("theme.*") if p.suffix != ".mp3"]
    assert leftovers == [], f"intermediate files left behind: {leftovers}"

    info = _audio_info(theme_file)
    if info is None:
        pytest.skip("ffprobe unavailable, audio content not verified")
    assert info.get("codec_name") == "mp3", f"expected an mp3 stream, got {info}"
    duration = float(info.get("duration") or 0.0)
    assert duration > 5.0, f"theme.mp3 is only {duration:.1f}s long"


def test_download_theme_prefers_themerrdb_over_youtube(
    require_themerrdb: None, tmp_path: Path
):
    """End-to-end: download_theme() must succeed on the first source.

    The later sources are replaced by recorders so the test can prove
    ThemerrDB won instead of the chain having fallen through to them.
    """
    case = THEME_CASES[0]
    downloader = _make_downloader()
    output_dir = tmp_path / "series"
    later_sources: list[str] = []

    def _record(name):
        def _inner(*_args, **_kwargs):
            later_sources.append(name)
            return False, None, f"{name} blocked by test"

        return _inner

    downloader._try_televisiontunes = _record("televisiontunes")  # type: ignore[method-assign]
    downloader._try_youtube_theme = _record("youtube")  # type: ignore[method-assign]

    def _attempt():
        # Only the last attempt's fall-through matters: earlier attempts may
        # have hit a transient YouTube error and legitimately tried the next
        # source before being retried.
        later_sources.clear()
        return downloader.download_theme(
            case.title,
            output_dir,
            dry_run=False,
            tmdb_id=case.tmdb_id,
        )

    result = _run_with_retry(_attempt)
    _skip_if_transient(result)
    ok, path, err = result

    assert ok, f"download_theme() failed for '{case.title}': {err}"
    assert path is not None and Path(path).exists()
    assert later_sources == [], (
        f"download_theme() fell through to {later_sources} instead of stopping "
        "at ThemerrDB"
    )


def test_download_theme_dry_run_reports_themerrdb(tmp_path: Path):
    """Dry-run must name the curated URL without writing anything."""
    case = THEME_CASES[0]
    downloader = _make_downloader()
    output_dir = tmp_path / "series"

    ok, path, err = downloader.download_theme(
        case.title,
        output_dir,
        dry_run=True,
        tmdb_id=case.tmdb_id,
    )

    assert ok, err
    assert path == str(output_dir / "theme.mp3")
    assert not output_dir.exists(), "dry-run must not create the output directory"


# ---------------------------------------------------------------------------
# 3. --no-fallback: curated sources only
# ---------------------------------------------------------------------------


def test_no_fallback_succeeds_on_curated_match_without_youtube(
    require_themerrdb: None, tmp_path: Path
):
    """With no_fallback the curated theme must still download, and the YouTube
    search must never run."""
    case = THEME_CASES[0]
    downloader = _make_downloader()
    output_dir = tmp_path / "series"

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("YouTube fallback must not run with no_fallback=True")

    downloader._try_youtube_theme = _forbidden  # type: ignore[method-assign]

    result = _run_with_retry(
        lambda: downloader.download_theme(
            case.title,
            output_dir,
            dry_run=False,
            tmdb_id=case.tmdb_id,
            no_fallback=True,
        )
    )
    _skip_if_transient(result)
    ok, path, err = result

    assert ok, f"no_fallback download failed for '{case.title}': {err}"
    assert path is not None
    theme_file = Path(path)
    assert theme_file.exists() and theme_file.stat().st_size > 20_000


def test_no_fallback_fails_cleanly_on_uncovered_title(
    require_themerrdb: None, tmp_path: Path
):
    """A title absent from the curated sources must fail instead of silently
    falling back to YouTube."""
    downloader = _make_downloader()
    output_dir = tmp_path / "series"
    youtube_calls: list[str] = []

    def _record_youtube(*_args, **_kwargs):
        youtube_calls.append("youtube")
        return False, None, "youtube blocked by test"

    # TelevisionTunes coverage changes over time; stub it as a miss so the test
    # stays deterministic while still proving the chain was walked in order.
    downloader._try_televisiontunes = lambda *_a, **_k: (  # type: ignore[method-assign]
        False,
        None,
        "TelevisionTunes: no results found",
    )
    downloader._try_youtube_theme = _record_youtube  # type: ignore[method-assign]

    ok, path, err = downloader.download_theme(
        "Love, Death & Robots",
        output_dir,
        dry_run=True,
        tmdb_id=UNCOVERED_SERIES_TMDB_ID,
        no_fallback=True,
    )

    assert ok is False
    assert path is None
    assert youtube_calls == [], "YouTube must not be consulted with no_fallback=True"
    assert err is not None
    assert "ThemerrDB" in err
    # TelevisionTunes is a curated source too, so it was legitimately tried.
    assert "TelevisionTunes" in err


def test_no_fallback_dry_run_for_curated_movie(tmp_path: Path):
    """Movies rely on ThemerrDB only (TelevisionTunes is series-only)."""
    case = next(c for c in THEME_CASES if not c.is_series)
    downloader = _make_downloader()
    output_dir = tmp_path / "movie"

    ok, path, err = downloader.download_theme(
        case.title,
        output_dir,
        dry_run=True,
        tmdb_id=case.tmdb_id,
        imdb_id=case.imdb_id,
        is_series=False,
        no_fallback=True,
    )

    assert ok, err
    assert path == str(output_dir / "theme.mp3")
    assert not output_dir.exists()
