from extrarrfin.scorer import VideoScorer


def test_theme_scoring_rejects_fan_mashup_for_official_soundtrack():
    scorer = VideoScorer(min_score=30.0, verbose=False)

    videos = [
        {
            "id": "juM43FBfcgI",
            "title": "Widow's Bay (Parks & Recreation Opening Titles theme)",
            "channel": "Warren Buchholz",
            "view_count": 4186,
            "duration": 43.0,
            "description": (
                'Fan mashup of the Apple tv show "Widow\'s Bay" '
                'with NBC\'s "Parks and Recreation."'
            ),
        },
        {
            "id": "yks3HunDxUo",
            "title": (
                "David Fleming - The Stone Room | Widow's Bay "
                "(Apple Original Series Soundtrack)"
            ),
            "channel": "SonySoundtracksVEVO",
            "view_count": 14750,
            "duration": 97.0,
            "description": (
                "The Stone Room from Widow's Bay (Apple Original Series "
                "Soundtrack) | Music by David Fleming"
            ),
        },
    ]

    best = scorer.score_theme_videos(videos, "Widow Bay")

    assert best is not None
    assert best["id"] == "yks3HunDxUo"


def test_theme_scoring_matches_network_despite_punctuation_variants():
    scorer = VideoScorer(min_score=30.0, verbose=False)

    videos = [
        {
            "id": "_aiRhbMJqW8",
            "title": "SUGAR Main Title Sequence | Apple TV+ | 4K",
            "channel": "Peterp4k",
            "view_count": 7395,
            "duration": 60.0,
            "description": "Main title sequence for Sugar, now streaming on Apple TV+.",
        },
        {
            "id": "tRsIqX1yIyk",
            "title": "Sugar | Opening Theme Song | Intro | AppleTV+",
            "channel": "Farewell",
            "view_count": 25142,
            "duration": 61.0,
            "description": "Sugar opening theme song. Stream at AppleTV+.",
        },
    ]

    best = scorer.score_theme_videos(videos, "Sugar", year=2024, network="Apple TV")

    assert best is not None
    assert best["id"] == "tRsIqX1yIyk"
