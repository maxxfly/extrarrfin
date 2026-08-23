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


def test_theme_scoring_prefers_official_soundtrack_metadata_over_sequence_repost():
    scorer = VideoScorer(min_score=30.0, verbose=False)

    videos = [
        {
            "id": "sequence-repost",
            "title": "Atlas Main Title Sequence | Apple TV+ | 4K",
            "channel": "FrameVault",
            "view_count": 16000,
            "duration": 61.0,
            "description": "A clean upload of the Atlas main title sequence.",
        },
        {
            "id": "official-soundtrack",
            "title": "Anne Nikitin - Atlas Main Theme | Apple TV+ Original Series Soundtrack",
            "channel": "Lakeshore Records",
            "view_count": 12000,
            "duration": 95.0,
            "description": (
                "Official soundtrack release from Atlas. Music by Anne Nikitin. "
                "Listen to the soundtrack now on Apple TV+."
            ),
        },
    ]

    best = scorer.score_theme_videos(videos, "Atlas", year=2024, network="Apple TV")

    assert best is not None
    assert best["id"] == "official-soundtrack"


def test_theme_scoring_prioritizes_opening_over_soundtrack_when_both_exist():
    scorer = VideoScorer(min_score=30.0, verbose=False)

    videos = [
        {
            "id": "opening-choice",
            "title": "Peaky Blinders Title sequence BBC TWO",
            "channel": "Pierrick Allan",
            "view_count": 9768,
            "duration": 72.0,
            "description": "Opening title sequence for Peaky Blinders.",
        },
        {
            "id": "ost-choice",
            "title": "Nick Cave And The Bad Seeds - Red Right Hand (Peaky Blinders OST)",
            "channel": "Hege Abel",
            "view_count": 63882143,
            "duration": 374.0,
            "description": "Song used in the Peaky Blinders soundtrack.",
        },
    ]

    best = scorer.score_theme_videos(videos, "Peaky Blinders", year=2013, network="BBC")

    assert best is not None
    assert best["id"] == "opening-choice"
