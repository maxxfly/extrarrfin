"""
Video scoring system for YouTube search results
Separates scoring logic from download functionality for better testability
"""

import logging
import math
import re
from dataclasses import dataclass

from .models import Series

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable weights for video scoring"""

    # Positive scoring weights
    exact_match: float = 100.0
    episode_in_title: float = 50.0
    network_match: float = 40.0
    word_ratio_max: float = 40.0
    series_in_title: float = 30.0
    title_length_max: float = 20.0
    upload_date_proximity_max: float = 20.0
    official_verified: float = 15.0
    description_match_max: float = 15.0
    view_count_max: float = 10.0
    like_ratio_max: float = 8.0

    # Penalty weights (positive values, will be subtracted)
    video_game_penalty: float = 150.0
    uploaded_before_series: float = 120.0
    old_year_penalty: float = 100.0
    content_before_series: float = 80.0
    duration_invalid: float = 50.0
    compilation_penalty: float = 30.0

    # Thresholds
    min_duration: int = 60  # seconds
    max_duration: int = 5400  # 90 minutes
    min_view_count_for_like_ratio: int = (
        1000  # Increased from 100 to avoid inflated ratios on tiny videos
    )
    min_view_count_for_scoring: int = 50  # Penalty for very low view counts


class VideoScorer:
    """
    Scores YouTube video results based on relevance to episode

    Uses multiple factors including:
    - Title matching (exact, partial, word ratio)
    - Channel/network matching
    - View count and engagement (likes)
    - Upload date proximity to series
    - Description analysis
    - Duration validation
    - Penalties for wrong content types
    """

    def __init__(
        self,
        weights: ScoringWeights | None = None,
        min_score: float = 50.0,
        verbose: bool = False,
    ):
        self.weights = weights or ScoringWeights()
        self.min_score = min_score
        self.verbose = verbose
        # MUCH lower threshold for theme scoring - themes are hard to match
        # Official themes often have lower engagement than regular content
        self.theme_min_score = min(min_score - 15, 35.0)

    def score_and_select_video(
        self, videos: list, series: Series, episode_title: str
    ) -> dict | None:
        """
        Score video results and select the best one

        Args:
            videos: List of video metadata from yt-dlp
            series: Series information
            episode_title: Episode title to match

        Returns:
            Best matching video dict with '_score' field, or None if no acceptable match
        """
        if not videos:
            return None

        scored_videos = []

        # Normalize strings for comparison
        series_lower = series.title.lower()
        episode_lower = episode_title.lower()
        search_words = set((series.title + " " + episode_title).lower().split())
        network_lower = series.network.lower() if series.network else None
        series_year = series.year

        if self.verbose:
            if network_lower:
                logger.info(f"[VERBOSE] Series network: {series.network}")
            if series_year:
                logger.info(f"[VERBOSE] Series year: {series_year}")

        for video in videos:
            if not video:
                continue

            score = self._score_video(
                video,
                series_lower,
                episode_lower,
                search_words,
                network_lower,
                series_year,
            )

            video["_score"] = score
            scored_videos.append(video)

            if self.verbose:
                title = video.get("title", "")
                logger.info(
                    f"[VERBOSE] Candidate: {title[:60]}... (score: {score:.2f})"
                )

        return self._select_best_video(scored_videos)

    def _score_video(
        self,
        video: dict,
        series_lower: str,
        episode_lower: str,
        search_words: set,
        network_lower: str | None,
        series_year: int | None,
    ) -> float:
        """Calculate score for a single video"""

        title = video.get("title", "")
        title_lower = title.lower()
        channel = video.get("channel", "")
        channel_lower = channel.lower()
        description = video.get("description", "") or ""
        description_lower = description.lower()
        duration = video.get("duration")
        view_count = video.get("view_count")
        upload_date = video.get("upload_date")
        like_count = video.get("like_count")

        score: float = 0

        # ===== POSITIVE SCORING =====
        score += self._score_title_match(
            title_lower, series_lower, episode_lower, search_words
        )
        score += self._score_network_match(channel, channel_lower, network_lower)
        score += self._score_engagement(view_count, like_count)
        score += self._score_description(
            description_lower, series_lower, episode_lower, network_lower
        )
        score += self._score_upload_date(upload_date, series_year)

        # ===== PENALTIES =====
        score -= self._penalty_duration(duration)
        score -= self._penalty_content_type(title_lower)
        score -= self._penalty_year_mismatch(title, upload_date, series_year)
        score -= self._penalty_title_position(title, title_lower, series_lower)

        return score

    def _score_title_match(
        self, title_lower: str, series_lower: str, episode_lower: str, search_words: set
    ) -> float:
        """Score based on title matching"""
        score = 0.0

        # Exact match
        if (
            title_lower == episode_lower
            or title_lower == f"{series_lower} {episode_lower}"
        ):
            score += self.weights.exact_match

        # Contains episode title
        if episode_lower in title_lower:
            score += self.weights.episode_in_title

        # Contains series title
        if series_lower in title_lower:
            score += self.weights.series_in_title

        # Word matching ratio
        title_words = set(title_lower.split())
        common_words = search_words & title_words
        if search_words:
            word_ratio = len(common_words) / len(search_words)
            score += word_ratio * self.weights.word_ratio_max

        # Prefer shorter titles (less likely to be compilations)
        title_length = len(title_lower)
        if title_length < 100:
            score += self.weights.title_length_max * (1 - title_length / 100)

        # Official/verified indicators
        if any(word in title_lower for word in ["official", "vevo", "verified"]):
            score += self.weights.official_verified
            if self.verbose:
                logger.info("[VERBOSE] Official/verified bonus")

        return score

    def _score_network_match(
        self, channel: str, channel_lower: str, network_lower: str | None
    ) -> float:
        """Score based on channel matching network"""
        if not network_lower or not channel:
            return 0.0

        # Exact or partial match
        if network_lower in channel_lower or channel_lower in network_lower:
            if self.verbose:
                logger.info(f"[VERBOSE] Network match bonus: {channel}")
            return self.weights.network_match

        # Abbreviation match (e.g., "BBC" in "BBC Studios")
        if len(network_lower) <= 5 and network_lower in channel_lower.split():
            if self.verbose:
                logger.info(f"[VERBOSE] Network abbreviation match: {channel}")
            return self.weights.network_match

        return 0.0

    def _score_engagement(
        self, view_count: int | None, like_count: int | None
    ) -> float:
        """Score based on view count and like ratio"""
        score = 0.0

        # Penalty for very low view counts (indicates obscure or fake content)
        if view_count and view_count < self.weights.min_view_count_for_scoring:
            penalty = 20.0 * (1 - view_count / self.weights.min_view_count_for_scoring)
            score -= penalty
            if self.verbose:
                logger.info(
                    f"[VERBOSE] Low view count penalty: -{penalty:.1f} ({view_count:,} views)"
                )

        # View count bonus (logarithmic)
        if view_count and view_count > 0:
            view_score = min(
                self.weights.view_count_max, max(0, (math.log10(view_count) - 3) * 2)
            )
            score += view_score
            if self.verbose and view_score > 2:
                logger.info(
                    f"[VERBOSE] View count bonus: +{view_score:.1f} ({view_count:,} views)"
                )

        # Like ratio bonus (only on videos with enough views to be meaningful)
        if (
            like_count
            and view_count
            and view_count > self.weights.min_view_count_for_like_ratio
        ):
            like_ratio = like_count / view_count
            if like_ratio >= 0.05:  # 5%+ = excellent
                like_bonus = self.weights.like_ratio_max
            elif like_ratio >= 0.03:  # 3-5% = good
                like_bonus = self.weights.like_ratio_max * 0.625
            elif like_ratio >= 0.02:  # 2-3% = decent
                like_bonus = self.weights.like_ratio_max * 0.375
            else:
                like_bonus = 0

            if like_bonus > 0:
                score += like_bonus
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] Like ratio bonus: +{like_bonus:.1f} ({like_ratio:.1%})"
                    )

        return score

    def _score_description(
        self,
        description_lower: str,
        series_lower: str,
        episode_lower: str,
        network_lower: str | None,
    ) -> float:
        """Score based on description content"""
        if not description_lower:
            return 0.0

        desc_bonus = 0.0
        if series_lower in description_lower:
            desc_bonus += 8
        if episode_lower in description_lower:
            desc_bonus += 7

        # Official content indicators
        official_indicators = ["official", "©", "all rights reserved"]
        if network_lower:
            official_indicators.append(network_lower)

        if any(ind in description_lower for ind in official_indicators):
            desc_bonus += 5

        if desc_bonus > 0:
            desc_bonus = min(self.weights.description_match_max, desc_bonus)
            if self.verbose:
                logger.info(f"[VERBOSE] Description match bonus: +{desc_bonus:.1f}")
            return desc_bonus

        return 0.0

    def _score_upload_date(
        self, upload_date: str | None, series_year: int | None
    ) -> float:
        """Score based on upload date proximity to series year"""
        if not upload_date or not series_year:
            return 0.0

        try:
            upload_year = int(upload_date[:4])
            year_diff = abs(upload_year - series_year)

            # Bonus for videos within 5 years of series start
            if year_diff <= 5:
                year_bonus = self.weights.upload_date_proximity_max * (
                    1 - year_diff / 5
                )
                if self.verbose and year_bonus > 5:
                    logger.info(
                        f"[VERBOSE] Upload proximity bonus: +{year_bonus:.1f} (uploaded {upload_year})"
                    )
                return year_bonus
        except (ValueError, TypeError):
            pass

        return 0.0

    def _penalty_duration(self, duration: int | None) -> float:
        """Penalty for invalid duration (too short or too long)"""
        if not duration:
            return 0.0

        if duration < self.weights.min_duration:
            if self.verbose:
                logger.info(f"[VERBOSE] Duration penalty: too short ({duration}s)")
            return self.weights.duration_invalid

        if duration > self.weights.max_duration:
            if self.verbose:
                logger.info(
                    f"[VERBOSE] Duration penalty: too long ({duration // 60}min)"
                )
            return self.weights.duration_invalid

        return 0.0

    def _penalty_content_type(self, title_lower: str) -> float:
        """Penalty for wrong content types"""
        penalty = 0.0

        # Compilation/playlist indicators
        if any(
            word in title_lower
            for word in ["compilation", "playlist", "all episodes", "full series"]
        ):
            penalty += self.weights.compilation_penalty

        # Video game content
        video_game_indicators = [
            "juno new origins",
            "juno",
            "kerbal space program",
            "ksp",
            "gameplay",
            "game play",
            "let's play",
            "walkthrough",
            "gaming",
            "simulator",
            "sim",
            "mod",
            "modded",
            "pc game",
            "video game",
        ]
        if any(indicator in title_lower for indicator in video_game_indicators):
            if self.verbose:
                logger.info("[VERBOSE] Video game penalty")
            penalty += self.weights.video_game_penalty

        return penalty

    def _penalty_year_mismatch(
        self, title: str, upload_date: str | None, series_year: int | None
    ) -> float:
        """Penalty for year mismatches"""
        penalty = 0.0

        # Old year in title (e.g., "(1978)")
        old_year_match = re.search(r"\(19\d{2}\)", title)
        if old_year_match:
            if self.verbose:
                logger.info(f"[VERBOSE] Old year penalty: {old_year_match.group()}")
            penalty += self.weights.old_year_penalty

        # Uploaded before series started
        if upload_date and series_year:
            try:
                upload_year = int(upload_date[:4])
                if upload_year < series_year - 1:
                    years_before = series_year - upload_year
                    year_penalty = min(
                        self.weights.uploaded_before_series, years_before * 20
                    )
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Uploaded before series penalty: -{year_penalty}"
                        )
                    penalty += year_penalty
            except (ValueError, TypeError):
                pass

        return penalty

    def _penalty_title_position(
        self, title: str, title_lower: str, series_lower: str
    ) -> float:
        """Penalty if another title appears before series name"""
        if series_lower not in title_lower:
            return 0.0

        series_position = title_lower.find(series_lower)
        title_before_series = title_lower[:series_position].strip()

        if not title_before_series:
            return 0.0

        # Check for substantial content before series name
        original_before = title[:series_position].strip()
        capitalized_words = sum(
            1 for word in original_before.split() if word and word[0].isupper()
        )

        # 2+ capitalized words = likely another title
        if capitalized_words >= 2:
            if self.verbose:
                logger.info(
                    f"[VERBOSE] Content before series penalty: '{original_before}'"
                )
            return self.weights.content_before_series

        return 0.0

    def _select_best_video(self, scored_videos: list) -> dict | None:
        """Select the best video from scored list"""
        if not scored_videos:
            return None

        best = max(scored_videos, key=lambda v: v.get("_score", 0))
        best_score = best.get("_score", 0)

        # Check minimum score threshold
        if best_score < self.min_score:
            if self.verbose:
                logger.info(
                    f"[VERBOSE] ✗ Best score ({best_score:.2f}) below threshold ({self.min_score})"
                )
                logger.info(f"[VERBOSE] ✗ Rejected: {best.get('title')}")
            logger.warning(
                f"No video with acceptable score (best: {best_score:.2f}, min: {self.min_score})"
            )
            return None

        if self.verbose:
            logger.info(
                f"[VERBOSE] ✓ Selected: {best.get('title')} (score: {best_score:.2f})"
            )
            logger.info(f"[VERBOSE] ✓ Video ID: {best.get('id')}")

        return best

    def score_behind_scenes_videos(
        self,
        videos: list,
        series: Series,
        min_score: float = 65.0,
        max_results: int = 20,
    ) -> list[dict]:
        """
        Score behind the scenes video results based on title matching

        Scoring factors:
        - Contains "behind the scenes" or "bts" or "making of": +50 points
        - Contains series title: +40 points
        - Network in title (official content): +50 points
        - Channel matches network: +50 points
        - Known BTS content channels: +35 points
        - Word match ratio: +30 points max
        - Official/verified channel indicators: +20 points
        - Shorter title (less extra content): +15 points max

        Penalties:
        - Other movie/series titles before series name: -80 points
        - Unrelated channel types: -50 points
        - Unrelated content indicators: -30 points

        Returns videos with score >= min_score, sorted by score (highest first)
        """
        if not videos:
            return []

        scored_videos = []

        # Known channels that specialize in BTS/behind-the-scenes content
        known_bts_channels = [
            "filmisnow",
            "rotten tomatoes",
            "ign",
            "entertainment weekly",
            "collider",
            "comicbook.com",
            "screen rant",
            "variety",
            "the hollywood reporter",
            "deadline",
            "den of geek",
            "syfy",
            "nerdist",
            "movie trailers source",
            "joblo",
        ]

        # Normalize strings for comparison
        series_lower = series.title.lower()
        network_lower = series.network.lower() if series.network else None

        if self.verbose and network_lower:
            logger.info(f"[VERBOSE] Series network: {series.network}")

        for video in videos:
            if not video:
                continue

            title = video.get("title", "")
            title_lower = title.lower()
            channel = video.get("channel", "")
            channel_lower = channel.lower()
            score: float = 0

            # Contains behind the scenes / bts / making of (essential for this mode)
            if any(
                phrase in title_lower
                for phrase in [
                    "behind the scenes",
                    "behind the scene",
                    "bts",
                    "making of",
                    "making-of",
                    "backstage",
                    "featurette",
                ]
            ):
                score += 50

            # Bonus for VFX/technical breakdown content (interesting BTS content)
            if any(
                phrase in title_lower
                for phrase in ["vfx breakdown", "breakdown", "visual effects"]
            ):
                score += 40
                if self.verbose:
                    logger.info("[VERBOSE] VFX/Breakdown bonus applied")

            # Contains series title
            if series_lower in title_lower:
                score += 40

                # Additional bonus for character/actor focused BTS content
                if any(
                    phrase in title_lower
                    for phrase in [":", "with", "interview", "character"]
                ) and any(
                    bts in title_lower
                    for bts in ["behind the scenes", "behind the scene", "bts"]
                ):
                    score += 15
                    if self.verbose:
                        logger.info("[VERBOSE] Character/actor BTS bonus applied")

            # Bonus if network name appears in title (indicates official content)
            if network_lower and network_lower in title_lower:
                score += 50
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] Network in title bonus: {series.network} found in title"
                    )

            # Check if channel matches the network (increased bonus)
            if network_lower and channel:
                if network_lower in channel_lower or channel_lower in network_lower:
                    score += 50
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Network match bonus: {channel} ~ {series.network}"
                        )
                elif len(network_lower) <= 5 and network_lower in channel_lower.split():
                    score += 50
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Network abbreviation match: {channel} ~ {series.network}"
                        )
            else:
                # Check if it's a known BTS content channel
                if any(
                    known_channel in channel_lower
                    for known_channel in known_bts_channels
                ):
                    score += 40
                    if self.verbose:
                        logger.info(f"[VERBOSE] Known BTS channel bonus: {channel}")
                # Penalize videos from unrelated channels
                elif network_lower and channel and series_lower in title_lower:
                    unrelated_keywords = [
                        "school",
                        "university",
                        "college",
                        "fashion brand",
                        "prada",
                        "museum",
                        "art gallery",
                        "foundation (charity)",
                        "sixth form",
                        "centre",
                    ]
                    if any(keyword in channel_lower for keyword in unrelated_keywords):
                        score -= 50
                        if self.verbose:
                            logger.info(
                                f"[VERBOSE] Penalty: Unrelated channel type: {channel}"
                            )

            # Check title for educational/unrelated indicators
            if "sixth form" in title_lower or (
                "durham" in title_lower and "art foundation" in title_lower
            ):
                score -= 60
                if self.verbose:
                    logger.info(
                        "[VERBOSE] Penalty: Educational/unrelated content in title"
                    )

            # Word matching ratio
            series_words = set(series.title.lower().split())
            title_words = set(title_lower.split())
            common_words = series_words & title_words
            if series_words:
                word_ratio = len(common_words) / len(series_words)
                score += word_ratio * 30

            # Check for official/quality indicators
            title_and_channel = (title + " " + channel).lower()
            if any(
                word in title_and_channel for word in ["official", "vevo", "verified"]
            ):
                score += 20

            # Prefer shorter titles (less likely to be compilations)
            title_length = len(title)
            if title_length < 100:
                score += 15 * (1 - title_length / 100)

            # PENALTIES: Detect if another title appears BEFORE the series name
            if series_lower in title_lower:
                series_position = title_lower.find(series_lower)
                title_before_series = title_lower[:series_position].strip()

                if title_before_series:
                    original_before = title[:series_position].strip()
                    capitalized_words = sum(
                        1
                        for word in original_before.split()
                        if word and word[0].isupper()
                    )
                    if capitalized_words >= 2:
                        score -= 80
                        if self.verbose:
                            logger.info(
                                f"[VERBOSE] Penalty: Possible other title before series name: '{original_before}'"
                            )

            # Penalize certain patterns that indicate wrong content
            penalty_patterns = [
                "compilation",
                "playlist",
                "all episodes",
                "full series",
                "reaction",
                "review",
                "unboxing",
                "gameplay",
                "walkthrough",
                "interview only",
                "cast interview",
                "ending explained",
                "theories",
            ]
            if any(word in title_lower for word in penalty_patterns):
                score -= 30

            # Penalize trailers if they don't explicitly mention BTS content
            if "trailer" in title_lower:
                has_bts = any(
                    phrase in title_lower
                    for phrase in [
                        "behind the scenes",
                        "behind the scene",
                        "bts",
                        "making of",
                        "featurette",
                    ]
                )
                if not has_bts:
                    score -= 40
                    if self.verbose:
                        logger.info("[VERBOSE] Penalty: Trailer without BTS content")

            if self.verbose:
                logger.info(f"[VERBOSE] Video '{title}' scored {score:.2f} points")

            # Store the score and keep video if it meets minimum
            if score >= min_score:
                video["_score"] = score
                scored_videos.append(video)

        # Sort by score (highest first)
        scored_videos.sort(key=lambda v: v.get("_score", 0), reverse=True)

        # Remove duplicates based on title similarity and duration
        scored_videos = self.remove_duplicate_videos(scored_videos)

        # Limit to max_results best videos
        if len(scored_videos) > max_results:
            scored_videos = scored_videos[:max_results]

        if self.verbose and scored_videos:
            logger.info(
                f"[VERBOSE] Found {len(scored_videos)} videos above minimum score {min_score}"
            )

        return scored_videos

    def remove_duplicate_videos(self, videos: list[dict]) -> list[dict]:
        """
        Remove duplicate videos based on title similarity and duration proximity
        Keeps the video with the highest score among duplicates

        Two videos are considered duplicates if:
        - Title similarity > 80% (based on word overlap)
        - Duration difference < 10% or < 30 seconds
        """
        if not videos:
            return []

        unique_videos: list[dict] = []

        for video in videos:
            is_duplicate = False
            video_title = video.get("title", "").lower()
            video_duration = video.get("duration", 0)

            # Normalize title for comparison
            video_words = set(
                word.strip(".,!?-—|:;()[]")
                for word in video_title.split()
                if len(word) > 2 and word not in ["the", "and", "for", "with", "from"]
            )

            for existing in unique_videos:
                existing_title = existing.get("title", "").lower()
                existing_duration = existing.get("duration", 0)

                existing_words = set(
                    word.strip(".,!?-—|:;()[]")
                    for word in existing_title.split()
                    if len(word) > 2
                    and word not in ["the", "and", "for", "with", "from"]
                )

                # Calculate title similarity (Jaccard similarity)
                if video_words and existing_words:
                    common_words = video_words & existing_words
                    all_words = video_words | existing_words
                    similarity = len(common_words) / len(all_words) if all_words else 0
                else:
                    similarity = 0

                # Check duration proximity
                duration_similar = False
                if video_duration and existing_duration:
                    duration_diff = abs(video_duration - existing_duration)
                    duration_ratio = duration_diff / max(
                        video_duration, existing_duration
                    )
                    duration_similar = duration_diff < 30 or duration_ratio < 0.1

                # Consider it a duplicate if titles are very similar
                # OR if titles are somewhat similar AND durations are close
                if similarity > 0.8 or (similarity > 0.6 and duration_similar):
                    is_duplicate = True
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Duplicate detected: '{video.get('title')}' "
                            f"(similarity: {similarity:.2f}, duration diff: {abs(video_duration - existing_duration)}s) "
                            f"vs '{existing.get('title')}'"
                        )
                    break

            if not is_duplicate:
                unique_videos.append(video)

        if self.verbose and len(unique_videos) < len(videos):
            logger.info(
                f"[VERBOSE] Removed {len(videos) - len(unique_videos)} duplicate(s)"
            )

        return unique_videos

    def score_theme_videos(
        self,
        videos: list,
        media_title: str,
        year: int | None = None,
        network: str | None = None,
    ) -> dict | None:
        """
        Score YouTube search results to find the best musical theme.

        Logic inspired by score_behind_scenes_videos which works well:
        - Hard rejection of low-quality/obscure videos (< 200 views)
        - Hard rejection of promotional announcements
        - Positive scoring for theme keywords, title match, network match
        - Penalties for covers, noise, trailers, OST tracks

        Returns the best video dict (with '_score') above theme_min_score, or None.
        """
        if not videos:
            return None

        # --- Minimum view count: themes must have some real reach ---
        # A video with < 200 views is almost certainly NOT an official theme
        # even if the title perfectly matches (e.g. test uploads, re-uploads)
        # The good video has 100k views, the bad one has 21 views.
        MIN_THEME_VIEWS = 200

        _stopwords = {
            "the",
            "a",
            "an",
            "of",
            "in",
            "and",
            "de",
            "du",
            "la",
            "le",
            "les",
        }
        title_words = [
            w.lower()
            for w in re.split(r"\W+", media_title)
            if len(w) >= 3 and w.lower() not in _stopwords
        ]

        strong_theme_kw = [
            "main theme",
            "opening theme",
            "theme song",
            "main title",
            "opening title",  # e.g. "Opening Title Sequence"
            "title sequence",  # e.g. "Season 1 Opening Title Sequence"
            "opening credits",  # e.g. "Opening Credits | HBO Max"
            "opening credit",
            "title theme",
            "intro theme",
            "ost",
            "original soundtrack",
            "original score",
        ]
        soft_theme_kw = [
            "theme",
            "soundtrack",
            "score",
            "title sequence",
            "opening",
            "credits",
        ]
        cover_keywords = [
            "cover",
            "tribute",
            "piano version",
            "piano cover",
            "guitar version",
            "guitar cover",
            "violin",
            "flute",
            "lofi",
            "lo-fi",
            "remix",
            "8-bit",
            "8bit",
            "lyrics",
            "lyric video",
        ]
        # Promotional/noise content — definitely NOT theme music
        reject_keywords = [
            "now on",
            "now available",
            "coming to",
            "available on",
            "premiering on",
            "streaming on",
            "maintenant disponible",
            "disponible sur",
            "reaction",
            "review",
            "top 10",
            "top10",
            "playlist",
            "compilation",
            "all episodes",
            "theory",
            "explained",
            "gameplay",
            "walkthrough",
        ]

        scored: list[dict] = []

        for video in videos:
            if not video or not video.get("id"):
                continue

            vtitle = video.get("title", "")
            vtitle_lower = vtitle.lower()
            duration = video.get("duration")
            view_count = video.get("view_count") or 0
            like_count = video.get("like_count")
            upload_date = video.get("upload_date")
            channel = video.get("channel") or ""
            channel_lower = channel.lower()
            score: float = 0.0

            # ── HARD REJECTIONS (no score computed) ──────────────────────────

            # 1. Minimum view count: obscure uploads can't be official themes
            if view_count < MIN_THEME_VIEWS:
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] Theme: REJECT low views ({view_count} < {MIN_THEME_VIEWS}) — '{vtitle}'"
                    )
                continue

            # 2. Promotional announcements or noise content
            if any(kw in vtitle_lower for kw in reject_keywords):
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] Theme: REJECT promotional/noise content — '{vtitle}'"
                    )
                continue

            # 3. K-drama/K-pop fan video formats:
            #    "[MV]", "[FMV]", "[AMV]", "[PMV]", "[Official MV]" etc.
            _fan_video_prefix = re.match(r"^\[([a-z]{1,8})\]", vtitle_lower)
            if _fan_video_prefix:
                _prefix_tag = _fan_video_prefix.group(1)
                # Block known fan/music video tags that are NOT main themes
                _fan_tags = {"mv", "fmv", "amv", "pmv", "m/v", "audio", "live", "lyric"}
                if any(tag in _prefix_tag for tag in _fan_tags):
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Theme: REJECT fan/music video format [{_prefix_tag.upper()}] — '{vtitle}'"
                        )
                    continue

            # 4. "OST Part.X" or "OST | Track Name" = specific track from an OST album
            if re.search(r"\bost\s+part\b", vtitle_lower) or re.search(
                r"\bost\s*\|", vtitle_lower
            ):
                if self.verbose:
                    logger.info(f"[VERBOSE] Theme: REJECT OST album track — '{vtitle}'")
                continue

            # 5. Must contain at least one music/theme keyword
            # Interviews, making-of, news segments etc. about the show are NOT themes
            all_theme_kw = (
                strong_theme_kw + soft_theme_kw + ["music", "song", "audio", "sound"]
            )
            if not any(kw in vtitle_lower for kw in all_theme_kw):
                if self.verbose:
                    logger.info(
                        f"[VERBOSE] Theme: REJECT no music keyword found — '{vtitle}'"
                    )
                continue

            # ── POSITIVE SCORING ─────────────────────────────────────────────

            # Title word matching against media title
            if title_words:
                matched = sum(1 for w in title_words if w in vtitle_lower)
                ratio = matched / len(title_words)
                if ratio == 1.0:
                    score += 50  # All significant words present
                elif ratio >= 0.5:
                    score += 20  # At least half the words
                else:
                    score -= 50  # Very few matches → probably wrong content
            else:
                if media_title.lower() in vtitle_lower:
                    score += 50
                else:
                    score -= 50

            # Strong theme keyword (main theme, opening theme, ost…)
            if any(kw in vtitle_lower for kw in strong_theme_kw):
                score += 50
                if self.verbose:
                    logger.info("[VERBOSE] Theme: strong theme keyword +50")
            elif any(kw in vtitle_lower for kw in soft_theme_kw):
                score += 25
                if self.verbose:
                    logger.info("[VERBOSE] Theme: soft theme keyword +25")

            # "Official" in title
            if "official" in vtitle_lower:
                score += 15

            # Year match in title
            if year and str(year) in vtitle:
                score += 25

            # Year proximity (upload date)
            if upload_date and year:
                try:
                    upload_year = int(upload_date[:4])
                    year_diff = abs(upload_year - year)
                    if year_diff <= 5:
                        score += 20 * (1 - year_diff / 5)
                except (ValueError, TypeError):
                    pass

            # Network / studio in title or channel (strong official indicator)
            if network:
                network_lower = network.lower()
                if network_lower in vtitle_lower:
                    score += 30
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Theme: network in title +30 ({network})"
                        )
                if network_lower in channel_lower:
                    score += 25
                    if self.verbose:
                        logger.info(f"[VERBOSE] Theme: network channel +25 ({network})")

            # Engagement (view count + like ratio)
            score += self._score_engagement(view_count, like_count)

            # ── PENALTIES ────────────────────────────────────────────────────

            # Old year in title (e.g. series from 2025 but title says 1979)
            if year:
                m = re.search(r"\b((?:18|19|20)\d{2})\b", vtitle)
                if m and year - int(m.group(1)) >= 10:
                    score -= 50
                    if self.verbose:
                        logger.info(
                            f"[VERBOSE] Theme: old year penalty ({m.group(1)}) — '{vtitle}'"
                        )

            # Cover / tribute / remix
            if any(kw in vtitle_lower for kw in cover_keywords):
                score -= 70
                if self.verbose:
                    logger.info(f"[VERBOSE] Theme: cover/tribute penalty — '{vtitle}'")

            # Trailer / teaser
            if "trailer" in vtitle_lower or "teaser" in vtitle_lower:
                score -= 40
                if self.verbose:
                    logger.info(f"[VERBOSE] Theme: trailer/teaser penalty — '{vtitle}'")

            # Duration checks
            if duration is not None:
                if duration < 20:
                    score -= 20
                elif duration > 600:  # > 10 min → likely album/compilation
                    score -= 30

            # Individual OST track patterns (not main theme)
            if re.search(r"(?:soundtrack|score)\s*\|.+\s+-\s+\S", vtitle_lower):
                score -= 60
            if re.search(
                r"\b(?:soundtrack|score)\b[^|]*-\s*0?\d{1,2}[\s:]", vtitle_lower
            ):
                score -= 60

            video["_score"] = score
            scored.append(video)

            if self.verbose:
                logger.info(
                    f"[VERBOSE] Theme candidate: '{vtitle}' "
                    f"→ score {score:.1f} (views: {view_count:,})"
                )

        if not scored:
            logger.warning("No theme videos passed minimum criteria (all rejected)")
            return None

        # Sort and log
        scored.sort(key=lambda v: v.get("_score", 0), reverse=True)
        if self.verbose:
            logger.info(f"[VERBOSE] Theme: {len(scored)} candidate(s) passed filters")
            for v in scored[:5]:
                logger.info(
                    f"[VERBOSE]   '{v.get('title')}' → {v.get('_score', 0):.1f} "
                    f"(views: {v.get('view_count', 0):,})"
                )

        best = scored[0]
        best_score = best.get("_score", 0)

        if best_score < self.theme_min_score:
            if self.verbose:
                logger.info(
                    f"[VERBOSE] Theme: best score {best_score:.1f} below "
                    f"threshold {self.theme_min_score} — rejected"
                )
            logger.warning(
                f"No theme with acceptable score found "
                f"(best: {best_score:.1f}, min: {self.theme_min_score})"
            )
            return None

        if self.verbose:
            logger.info(
                f"[VERBOSE] Theme selected: '{best.get('title')}' "
                f"(score {best_score:.1f})"
            )
        return best
