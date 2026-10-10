"""
Miscellaneous utilities
"""

import logging
from collections.abc import Sequence

VALID_MODES = ("season0", "tag", "theme")


def normalize_modes(value: object) -> list[str]:
    """Flatten a ``mode`` setting into a list of strings.

    Accepts the shapes the config file and the CLI can produce: ``None``, a
    plain string (``mode: season0``), a YAML list (``mode: ["season0", "tag"]``)
    or a Click tuple from a repeated ``--mode`` option. Nested sequences are
    flattened defensively so a doubly-wrapped value cannot silently select no
    mode at all.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        flattened: list[str] = []
        for item in value:
            flattened.extend(normalize_modes(item))
        return flattened
    return [str(value)]


def resolve_modes(
    cli_modes: Sequence[str] | None = None,
    config_modes: str | Sequence[str] | None = None,
    default: str = "season0",
    valid_modes: tuple[str, ...] = VALID_MODES,
) -> list[str]:
    """Return the modes to run, CLI taking priority over the config file.

    Raises:
        ValueError: when a requested mode is unknown. Failing loudly matters
            here: a mode list that matches nothing makes the command report
            success with zero work done.
    """
    source = cli_modes if cli_modes else config_modes
    modes = normalize_modes(source if source else default)

    # De-duplicate while preserving order (e.g. --mode season0 --mode season0).
    unique = list(dict.fromkeys(modes))

    unknown = [m for m in unique if m not in valid_modes]
    if unknown:
        raise ValueError(
            f"unknown mode(s): {', '.join(unknown)}. "
            f"Valid modes: {', '.join(valid_modes)}"
        )

    return unique


def setup_logging(log_level: str = "INFO") -> None:
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
