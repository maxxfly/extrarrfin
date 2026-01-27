"""
CLI configuration handler
"""

import sys
from pathlib import Path

from rich.console import Console

from .config import Config
from .downloader import Downloader
from .sonarr import SonarrClient

console = Console()


def load_config_from_args(
    config_file: str | None,
    sonarr_url: str | None,
    sonarr_api_key: str | None,
    media_dir: str | None,
    sonarr_dir: str | None,
    log_level: str,
) -> Config:
    """
    Load configuration from CLI arguments and files

    Args:
        config_file: Path to config file
        sonarr_url: Sonarr URL from CLI
        sonarr_api_key: Sonarr API key from CLI
        media_dir: Media directory from CLI
        sonarr_dir: Sonarr directory from CLI
        log_level: Log level

    Returns:
        Config object

    Raises:
        SystemExit if configuration is invalid
    """
    try:
        if config_file:
            cfg = Config.from_env_and_file(Path(config_file))
        elif sonarr_url and sonarr_api_key:
            cfg = Config(
                sonarr_url=sonarr_url,
                sonarr_api_key=sonarr_api_key,
                media_directory=media_dir,
                sonarr_directory=sonarr_dir,
                log_level=log_level,
            )
        else:
            # Try to load from default file
            default_config = Path("config.yaml")
            if default_config.exists():
                cfg = Config.from_env_and_file(default_config)
            else:
                console.print(
                    "[red]Error:[/red] Missing configuration. Use --config or environment variables."
                )
                console.print("\nExample:")
                console.print(
                    "  python extrarrfin.py --sonarr-url http://localhost:8989 --sonarr-api-key YOUR_KEY list"
                )
                console.print(
                    "\nOr create a config.yaml file (see config.example.yaml)"
                )
                sys.exit(1)
    except Exception as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        sys.exit(1)

    return cfg


def validate_sonarr_connection(config: Config) -> SonarrClient:
    """
    Validate Sonarr connection and return client

    Args:
        config: Configuration object

    Returns:
        SonarrClient instance

    Raises:
        SystemExit if connection fails
    """
    try:
        sonarr_client = SonarrClient(config.sonarr_url, config.sonarr_api_key)
        # Quick check to validate API key and URL
        sonarr_client.get_all_series()
        return sonarr_client
    except Exception as e:
        console.print(f"[red]Sonarr connection failed:[/red] {e}")
        console.print("\nPlease verify:")
        console.print("  - Sonarr URL is correct (with port)")
        console.print("  - API key is valid (Settings > General in Sonarr)")
        console.print("  - Sonarr is accessible from your machine")
        sys.exit(1)


def setup_context(
    config: Config,
    sonarr_client: SonarrClient,
) -> dict:
    """
    Setup CLI context with config, sonarr client and downloader

    Args:
        config: Configuration object
        sonarr_client: SonarrClient instance

    Returns:
        Dictionary with context objects
    """
    return {
        "config": config,
        "sonarr": sonarr_client,
        "downloader": Downloader(
            config.yt_dlp_format,
            subtitle_languages=config.subtitle_languages,
            download_all_subtitles=config.download_all_subtitles,
            use_strm_files=config.use_strm_files,
            min_score=config.min_score,
        ),
    }
