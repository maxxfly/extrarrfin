"""
Miscellaneous utilities
"""

import logging
from pathlib import Path


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


def validate_directory(path: str | None, create: bool = False) -> Path | None:
    """Validate that a path is a valid directory"""
    if not path:
        return None

    dir_path = Path(path)

    if not dir_path.exists():
        if create:
            dir_path.mkdir(parents=True, exist_ok=True)
            return dir_path
        else:
            raise ValueError(f"Directory does not exist: {path}")

    if not dir_path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    return dir_path
