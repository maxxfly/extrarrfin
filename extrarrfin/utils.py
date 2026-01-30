"""
Miscellaneous utilities
"""

import logging


def setup_logging(log_level: str = "INFO"):
    """Configure logging system"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def format_episode_info(
    series_title: str, season: int, episode: int, title: str
) -> str:
    """Format episode information for display"""
    return f"{series_title} - S{season:02d}E{episode:02d} - {title}"
