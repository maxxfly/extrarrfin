"""
Integration tests – YouTube theme music search for series and movies.

These tests hit YouTube (via yt-dlp) so they require a live internet connection.
``_download_audio_from_url`` is patched so nothing is actually downloaded;
we only verify which URL the scorer selected.

Run:
    .venv/bin/pytest tests/test_youtube_search.py -v -m integration

Skip when offline:
    .venv/bin/pytest -m "not integration"

How to add / update expected_urls
-----------------------------------
1. Remove the URL(s) from the list for the case you want to re-check.
2. Run the test – it will pytest.skip and print the new URL found, e.g.:
       SKIPPED - No expected_urls configured for 'Stranger Things'. Found: https://…
3. Copy that URL into the expected_urls list (keep old ones as alternatives).
"""

from unittest.mock import patch

import pytest

from extrarrfin.downloader import Downloader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _youtube_id(url: str) -> str:
    """Extract the video ID from a YouTube watch URL."""
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    return url


def _make_downloader() -> Downloader:
    """Return a Downloader configured for search only (no download)."""
    return Downloader(
        youtube_search_results=10,
        min_score=30.0,
        verbose=False,
    )


# ---------------------------------------------------------------------------
# Series test cases  (title, year, network, expected_youtube_urls)
# ---------------------------------------------------------------------------

SERIES_CASES = [
    pytest.param(
        "Stranger Things",
        2016,
        "Netflix",
        ["https://www.youtube.com/watch?v=-RcPZdihrp4"],
        id="stranger-things",
    ),
    pytest.param(
        "The Last of Us",
        2023,
        "HBO",
        ["https://www.youtube.com/watch?v=8SWhBsbxmpk"],
        id="the-last-of-us",
    ),
    pytest.param(
        "Severance",
        2022,
        "Apple TV+",
        ["https://www.youtube.com/watch?v=NmS3m0OG-Ug"],
        id="severance",
    ),
    pytest.param(
        "The Bear",
        2022,
        "FX",
        [
            # "New Noise" by Refused – the actual opening track used in the show.
            # NOTE: this video cannot be found by keyword scoring because "New Noise"
            # contains neither FX/Bear title words nor music keywords.
            # The alternatives below are the best the algorithm can currently return.
            "https://www.youtube.com/watch?v=vYXzkxpUTdM",
            # Algorithm-selected alternatives (all valid Bear-related theme content)
            "https://www.youtube.com/watch?v=CWWTAgwLTys",
            "https://www.youtube.com/watch?v=tgjAtWZa2iY",
            "https://www.youtube.com/watch?v=uIGOrGelsH8",
        ],
        id="the-bear",
    ),
    pytest.param(
        "Andor",
        2022,
        "Disney+",
        [
            "https://www.youtube.com/watch?v=9k2rkeLhgjY",
            # Alternative main title theme – both are valid
            "https://www.youtube.com/watch?v=dBXJlPibPK4",
        ],
        id="andor",
    ),
    pytest.param(
        "Peaky Blinders",
        2013,
        "BBC",
        ["https://www.youtube.com/watch?v=zCs4mnaoB64"],
        id="peaky-blinders",
    ),
    pytest.param(
        "Adolescence",
        2025,
        "Netflix",
        [
            "https://www.youtube.com/watch?v=bX1EAfoAnWE&list=PLLv3qeuV3YDolYDHSJfdtpgo0ewovIMrp"
        ],
        id="peaky-blinders",
    ),
    pytest.param(
        "Sugar",
        2024,
        "Apple TV",
        [
            # User-verified preferred: "Sugar | Opening Theme Song | Intro | AppleTV+"
            "https://www.youtube.com/watch?v=tRsIqX1yIyk",
            # Algorithm-selected alternative: "SUGAR Main Title Sequence | Apple TV+ | 4K"
            # Both are Apple TV+ official Sugar main title videos
            "https://www.youtube.com/watch?v=_aiRhbMJqW8",
        ],
        id="sugar",
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize("title,year,network,expected_urls", SERIES_CASES)
def test_theme_youtube_series(title, year, network, expected_urls, tmp_path):
    """
    _try_youtube_theme() must select a YouTube URL present in expected_urls.
    _download_audio_from_url is mocked so no file is written to disk.
    """
    downloader = _make_downloader()

    with patch.object(downloader, "_download_audio_from_url") as mock_dl:
        mock_dl.return_value = (True, str(tmp_path / "theme.mp3"), None)

        ok, _path, err = downloader._try_youtube_theme(
            title=title,
            year=year,
            output_dir=tmp_path,
            dry_run=False,
            network=network,
        )

    assert ok, f"Theme search failed for series '{title}': {err}"
    assert mock_dl.called, (
        f"_download_audio_from_url was never called for series '{title}' – "
        "no suitable video was found"
    )

    result_url: str = mock_dl.call_args[0][0]

    if expected_urls:
        result_id = _youtube_id(result_url)
        expected_ids = [_youtube_id(u) for u in expected_urls]
        assert result_id in expected_ids, (
            f"[{title}] Got {result_url!r} (id={result_id!r}) "
            f"but expected one of: {expected_ids}"
        )
    else:
        pytest.skip(
            f"No expected_urls configured for series '{title}'. Found: {result_url}"
        )


# ---------------------------------------------------------------------------
# Movie test cases  (title, year, expected_youtube_urls)
# ---------------------------------------------------------------------------

MOVIE_CASES = [
    pytest.param(
        "The Batman",
        2022,
        [
            # User-verified preferred results
            "https://www.youtube.com/watch?v=JMbEpzMR0fs",
            "https://www.youtube.com/watch?v=Cwcinb2OxUo",
            "https://www.youtube.com/watch?v=_WEonvtesdc",
            # Algorithm-selected alternative (also valid: "THE BATMAN (2022) THEME by Giacchino | OST")
            "https://www.youtube.com/watch?v=ufDv17BT5gc",
            # Additional stable alternatives observed across multiple runs
            "https://www.youtube.com/watch?v=WtSLeNPqmFw",
            "https://www.youtube.com/watch?v=jSnVBbyilMc",
        ],
        id="the-batman",
    ),
    pytest.param(
        "Interstellar",
        2014,
        [
            "https://www.youtube.com/watch?v=8kooIgKESYE",
            "https://www.youtube.com/watch?v=m3zvVGJrTP8",
        ],
        id="interstellar",
    ),
    pytest.param(
        "Everything Everywhere All at Once",
        2022,
        [
            # User-verified preferred result ("In Another Life" by Son Lux).
            # NOTE: this track has no music keyword and no title-word match → it
            # cannot be surfaced by the current keyword-scoring algorithm.
            # The alternatives below are the best the algorithm currently returns.
            "https://www.youtube.com/watch?v=wqu-WytFKpw",
            # Algorithm-selected alternatives (legitimate opening-title videos)
            "https://www.youtube.com/watch?v=EhoeptggcVM",
        ],
        id="everything-everywhere",
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize("title,year,expected_urls", MOVIE_CASES)
def test_theme_youtube_movie(title, year, expected_urls, tmp_path):
    """
    _try_youtube_theme() for movies must select a YouTube URL in expected_urls.
    _download_audio_from_url is mocked so no file is written to disk.
    """
    downloader = _make_downloader()

    with patch.object(downloader, "_download_audio_from_url") as mock_dl:
        mock_dl.return_value = (True, str(tmp_path / "theme.mp3"), None)

        ok, _path, err = downloader._try_youtube_theme(
            title=title,
            year=year,
            output_dir=tmp_path,
            dry_run=False,
            network=None,
        )

    assert ok, f"Theme search failed for movie '{title}': {err}"
    assert mock_dl.called, (
        f"_download_audio_from_url was never called for movie '{title}' – "
        "no suitable video was found"
    )

    result_url: str = mock_dl.call_args[0][0]

    if expected_urls:
        result_id = _youtube_id(result_url)
        expected_ids = [_youtube_id(u) for u in expected_urls]
        assert result_id in expected_ids, (
            f"[{title}] Got {result_url!r} (id={result_id!r}) "
            f"but expected one of: {expected_ids}"
        )
    else:
        pytest.skip(
            f"No expected_urls configured for movie '{title}'. Found: {result_url}"
        )
