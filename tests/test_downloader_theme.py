from pathlib import Path
from unittest.mock import patch

from extrarrfin.downloader import Downloader


class _FakeYoutubeDL:
    def __init__(self, _opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, query, download=False):
        if query.startswith("ytsearch"):
            return {
                "entries": [
                    {
                        "id": "unavailable-id",
                        "title": "Fallback Show Main Theme",
                        "channel": "Theme Channel",
                        "description": "Main theme.",
                        "view_count": 5000,
                        "duration": 70,
                    },
                    {
                        "id": "available-id",
                        "title": "Fallback Show Opening Theme",
                        "channel": "Theme Channel",
                        "description": "Opening theme.",
                        "view_count": 4000,
                        "duration": 75,
                    },
                ]
            }
        return {"id": query, "title": query}


def test_try_youtube_theme_skips_unavailable_top_candidate(tmp_path):
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    with patch("extrarrfin.downloader.yt_dlp.YoutubeDL", _FakeYoutubeDL):
        with patch.object(
            downloader.scorer,
            "score_theme_videos",
            side_effect=lambda videos, *_args, **_kwargs: videos[0] if videos else None,
        ):
            with patch.object(
                downloader,
                "_is_youtube_video_available",
                side_effect=lambda video_id: video_id == "available-id",
            ):
                with patch.object(downloader, "_download_audio_from_url") as mock_dl:
                    mock_dl.return_value = (True, str(tmp_path / "theme.mp3"), None)

                    ok, _path, err = downloader._try_youtube_theme(
                        title="Fallback Show",
                        year=2024,
                        output_dir=Path(tmp_path),
                        dry_run=False,
                        network=None,
                    )

    assert ok, err
    assert mock_dl.called
    assert mock_dl.call_args[0][0] == "https://www.youtube.com/watch?v=available-id"


def test_youtube_availability_probe_keeps_candidate_on_transient_error():
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    class _TransientFailureYoutubeDL:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _query, download=False):
            raise Exception("HTTP Error 429: Too Many Requests")

    with patch("extrarrfin.downloader.yt_dlp.YoutubeDL", _TransientFailureYoutubeDL):
        assert downloader._is_youtube_video_available("candidate-id") is True


def test_youtube_availability_probe_rejects_explicitly_unavailable_video():
    downloader = Downloader(youtube_search_results=10, min_score=30.0, verbose=False)

    class _UnavailableYoutubeDL:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _query, download=False):
            raise Exception("This video is not available")

    with patch("extrarrfin.downloader.yt_dlp.YoutubeDL", _UnavailableYoutubeDL):
        assert downloader._is_youtube_video_available("candidate-id") is False