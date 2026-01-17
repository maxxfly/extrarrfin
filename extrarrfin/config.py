"""
Configuration management
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    """Application configuration"""

    sonarr_url: str
    sonarr_api_key: str
    media_directory: str | None = None
    sonarr_directory: str | None = None
    yt_dlp_format: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    max_results: int = 1
    log_level: str = "INFO"

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
        config_data = {}

        # Load from file if specified
        if config_path and config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        # Environment variables take priority
        if os.getenv("SONARR_URL"):
            config_data["sonarr_url"] = os.getenv("SONARR_URL")
        if os.getenv("SONARR_API_KEY"):
            config_data["sonarr_api_key"] = os.getenv("SONARR_API_KEY")
        if os.getenv("MEDIA_DIRECTORY"):
            config_data["media_directory"] = os.getenv("MEDIA_DIRECTORY")
        if os.getenv("SONARR_DIRECTORY"):
            config_data["sonarr_directory"] = os.getenv("SONARR_DIRECTORY")

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
            "youtube_search_suffix": self.youtube_search_suffix,
            "yt_dlp_format": self.yt_dlp_format,
            "max_results": self.max_results,
            "log_level": self.log_level,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
