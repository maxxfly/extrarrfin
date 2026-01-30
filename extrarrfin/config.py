"""
Configuration management
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Config:
    """Application configuration"""

    sonarr_url: str
    sonarr_api_key: str
    radarr_url: str | None = None
    radarr_api_key: str | None = None
    media_directory: str | None = None
    sonarr_directory: str | None = None
    radarr_directory: str | None = None
    yt_dlp_format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    max_results: int = 1
    log_level: str = "INFO"
    schedule_enabled: bool = False
    schedule_interval: int = 1
    schedule_unit: str = "hours"
    mode: str | list[str] = "season0"  # "season0", "tag", or ["season0", "tag"]
    # Subtitle options
    subtitle_languages: list = field(
        default_factory=lambda: ["fr", "en", "fr-FR", "en-US", "en-GB"]
    )
    download_all_subtitles: bool = False
    # STRM file option
    use_strm_files: bool = False
    # Jellyfin integration
    jellyfin_url: str | None = None
    jellyfin_api_key: str | None = None
    # YouTube search options
    min_score: float = 50.0  # Minimum score to accept a video match
    youtube_search_results: int = 10  # Number of YouTube results to fetch (5-20)
    # Movie extras search keywords (configurable)
    movie_extras_keywords: list = field(
        default_factory=lambda: [
            "behind the scenes",
            "making of",
            "featurette",
            "interviews",
            "deleted scenes",
            "bloopers",
            "vfx",
            "special effects",
            "visual effects",
        ]
    )

    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """Load configuration from a YAML file"""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(**data)

    @classmethod
    def from_env_and_file(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from file and/or environment variables"""
        config_data: dict[str, Any] = {}

        # Load from file if specified
        if config_path and config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        # Environment variables take priority
        if os.getenv("SONARR_URL"):
            config_data["sonarr_url"] = os.getenv("SONARR_URL")
        if os.getenv("SONARR_API_KEY"):
            config_data["sonarr_api_key"] = os.getenv("SONARR_API_KEY")
        if os.getenv("RADARR_URL"):
            config_data["radarr_url"] = os.getenv("RADARR_URL")
        if os.getenv("RADARR_API_KEY"):
            config_data["radarr_api_key"] = os.getenv("RADARR_API_KEY")
        if os.getenv("MEDIA_DIRECTORY"):
            config_data["media_directory"] = os.getenv("MEDIA_DIRECTORY")
        if os.getenv("SONARR_DIRECTORY"):
            config_data["sonarr_directory"] = os.getenv("SONARR_DIRECTORY")
        if os.getenv("RADARR_DIRECTORY"):
            config_data["radarr_directory"] = os.getenv("RADARR_DIRECTORY")

        # Subtitle configuration from environment
        subtitle_langs_env = os.getenv("SUBTITLE_LANGUAGES")
        if subtitle_langs_env:
            # Parse comma-separated list of languages
            config_data["subtitle_languages"] = [
                lang.strip() for lang in subtitle_langs_env.split(",")
            ]

        download_all_subs_env = os.getenv("DOWNLOAD_ALL_SUBTITLES")
        if download_all_subs_env:
            config_data["download_all_subtitles"] = download_all_subs_env.lower() in [
                "true",
                "1",
                "yes",
            ]

        if "sonarr_url" not in config_data or "sonarr_api_key" not in config_data:
            raise ValueError(
                "Incomplete configuration. Sonarr URL and API Key are required. "
                "Use a config file or environment variables."
            )

        return cls(**config_data)

    def to_file(self, config_path: Path):
        """Save configuration to a YAML file"""
        data = {
            "sonarr_url": self.sonarr_url,
            "sonarr_api_key": self.sonarr_api_key,
            "media_directory": self.media_directory,
            "sonarr_directory": self.sonarr_directory,
            "yt_dlp_format": self.yt_dlp_format,
            "max_results": self.max_results,
            "log_level": self.log_level,
            "schedule_enabled": self.schedule_enabled,
            "schedule_interval": self.schedule_interval,
            "schedule_unit": self.schedule_unit,
            "subtitle_languages": self.subtitle_languages,
            "download_all_subtitles": self.download_all_subtitles,
            "use_strm_files": self.use_strm_files,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
