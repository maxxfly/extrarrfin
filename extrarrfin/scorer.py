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
    min_view_count_for_like_ratio: int = 100


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
                video, series_lower, episode_lower, search_words, network_lower, series_year
            )
            
            video["_score"] = score
            scored_videos.append(video)

            if self.verbose:
                title = video.get("title", "")
                logger.info(f"[VERBOSE] Candidate: {title[:60]}... (score: {score:.2f})")

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
        score += self._score_title_match(title_lower, series_lower, episode_lower, search_words)
        score += self._score_network_match(channel, channel_lower, network_lower)
        score += self._score_engagement(view_count, like_count)
        score += self._score_description(description_lower, series_lower, episode_lower, network_lower)
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
        if title_lower == episode_lower or title_lower == f"{series_lower} {episode_lower}":
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

    def _score_engagement(self, view_count: int | None, like_count: int | None) -> float:
        """Score based on view count and like ratio"""
        score = 0.0

        # View count bonus (logarithmic)
        if view_count and view_count > 0:
            view_score = min(
                self.weights.view_count_max,
                max(0, (math.log10(view_count) - 3) * 2)
            )
            score += view_score
            if self.verbose and view_score > 2:
                logger.info(f"[VERBOSE] View count bonus: +{view_score:.1f} ({view_count:,} views)")

        # Like ratio bonus
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
                    logger.info(f"[VERBOSE] Like ratio bonus: +{like_bonus:.1f} ({like_ratio:.1%})")

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

    def _score_upload_date(self, upload_date: str | None, series_year: int | None) -> float:
        """Score based on upload date proximity to series year"""
        if not upload_date or not series_year:
            return 0.0

        try:
            upload_year = int(upload_date[:4])
            year_diff = abs(upload_year - series_year)
            
            # Bonus for videos within 5 years of series start
            if year_diff <= 5:
                year_bonus = self.weights.upload_date_proximity_max * (1 - year_diff / 5)
                if self.verbose and year_bonus > 5:
                    logger.info(f"[VERBOSE] Upload proximity bonus: +{year_bonus:.1f} (uploaded {upload_year})")
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
                logger.info(f"[VERBOSE] Duration penalty: too long ({duration // 60}min)")
            return self.weights.duration_invalid

        return 0.0

    def _penalty_content_type(self, title_lower: str) -> float:
        """Penalty for wrong content types"""
        penalty = 0.0

        # Compilation/playlist indicators
        if any(word in title_lower for word in ["compilation", "playlist", "all episodes", "full series"]):
            penalty += self.weights.compilation_penalty

        # Video game content
        video_game_indicators = [
            "juno new origins", "juno", "kerbal space program", "ksp",
            "gameplay", "game play", "let's play", "walkthrough",
            "gaming", "simulator", "sim", "mod", "modded",
            "pc game", "video game"
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
                    year_penalty = min(self.weights.uploaded_before_series, years_before * 20)
                    if self.verbose:
                        logger.info(f"[VERBOSE] Uploaded before series penalty: -{year_penalty}")
                    penalty += year_penalty
            except (ValueError, TypeError):
                pass

        return penalty

    def _penalty_title_position(self, title: str, title_lower: str, series_lower: str) -> float:
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
            1 for word in original_before.split()
            if word and word[0].isupper()
        )

        # 2+ capitalized words = likely another title
        if capitalized_words >= 2:
            if self.verbose:
                logger.info(f"[VERBOSE] Content before series penalty: '{original_before}'")
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
            logger.info(f"[VERBOSE] ✓ Selected: {best.get('title')} (score: {best_score:.2f})")
            logger.info(f"[VERBOSE] ✓ Video ID: {best.get('id')}")

        return best
