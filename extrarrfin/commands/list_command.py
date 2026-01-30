"""
List command - Display series with monitored season 0 or want-extras tag, and movies with want-extras tag
"""

import logging
from typing import Literal, TypedDict, cast

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.models import Movie, Series
from extrarrfin.radarr import RadarrClient
from extrarrfin.sonarr import SonarrClient

logger = logging.getLogger(__name__)
console = Console()


class MediaItem(TypedDict):
    type: Literal["series", "movie"]
    data: Series | Movie


def list_command(
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    radarr: RadarrClient | None = None,
    limit: str | None = None,
    mode: tuple | None = None,
) -> None:
    """Execute the list command logic for series and movies"""

    # Use mode from command line or config
    if mode:
        active_modes = list(mode)
    elif isinstance(config.mode, list):
        active_modes = config.mode
    else:
        active_modes = [config.mode]

    # Fetch series and movies
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching series...", total=None)
        series_list = sonarr.get_monitored_series()
        progress.update(task, description="Fetching movies...")

        # Fetch movies if Radarr configured and tag mode active
        movies_list: list[Movie] = []
        if radarr and "tag" in active_modes:
            try:
                movies_list = radarr.get_monitored_movies()
            except Exception as e:
                logger.warning(f"Error fetching movies from Radarr: {e}")

        progress.update(task, completed=True)

    # Filter based on mode(s) - combine series and movies into a single list
    filtered_items: list[MediaItem] = []

    # Process series
    for s in series_list:
        include = False
        if "tag" in active_modes and sonarr.has_want_extras_tag(s):
            include = True
        if "season0" in active_modes and sonarr.has_monitored_season_zero_episodes(s):
            include = True
        if include:
            filtered_items.append({"type": "series", "data": s})

    # Process movies (only for tag mode)
    if "tag" in active_modes:
        for m in movies_list:
            if radarr and radarr.has_want_extras_tag(m):
                filtered_items.append({"type": "movie", "data": m})

    # Filter by name/ID if specified
    if limit:
        if limit.isdigit():
            filtered_items = [
                item for item in filtered_items if item["data"].id == int(limit)
            ]
        else:
            filtered_items = [
                item
                for item in filtered_items
                if limit.lower() in item["data"].title.lower()
            ]

    if not filtered_items:
        if len(active_modes) > 1:
            console.print(
                f"[yellow]No series/movies found for modes: {', '.join(active_modes)}[/yellow]"
            )
        elif "tag" in active_modes:
            console.print(
                "[yellow]No series/movies found with want-extras tag[/yellow]"
            )
        else:
            console.print("[yellow]No series found with monitored season 0[/yellow]")
        return

    # Display table
    series_count = sum(1 for item in filtered_items if item["type"] == "series")
    movies_count = sum(1 for item in filtered_items if item["type"] == "movie")

    if len(active_modes) > 1:
        table_title = f"Series & Movies ({', '.join(active_modes)}) - {len(filtered_items)} items ({series_count} series, {movies_count} movies)"
    elif "tag" in active_modes:
        table_title = f"Series & Movies with want-extras tag ({len(filtered_items)} items: {series_count} series, {movies_count} movies)"
    else:
        table_title = f"Series with Monitored Season 0 ({len(filtered_items)})"

    table = Table(title=table_title)
    table.add_column("Type", style="yellow", width=9)
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Path", style="dim")
    table.add_column("Downloaded", style="blue")
    table.add_column("Missing", style="yellow")
    table.add_column("Subtitles", style="magenta")
    table.add_column("Size", style="cyan")

    total_size = 0

    for item in filtered_items:
        item_type = item["type"]
        media = item["data"]

        # Type indicator
        type_emoji = "📺" if item_type == "series" else "🎬"
        type_text = (
            f"{type_emoji} TV" if item_type == "series" else f"{type_emoji} Movie"
        )

        # Initialize counters
        downloaded_count = 0
        missing_count = 0
        subtitle_counts: dict[str, int] = {}
        item_size = 0
        processed_season0 = False

        if item_type == "series":
            series = cast(Series, media)
            has_tag = sonarr.has_want_extras_tag(series)
            has_season0 = sonarr.has_monitored_season_zero_episodes(series)

            # Process Season 0 episodes if applicable
            if has_season0 and "season0" in active_modes:
                processed_season0 = True
                try:
                    episodes = sonarr.get_season_zero_episodes(series.id)
                    monitored_episodes = [e for e in episodes if e.monitored]
                    output_dir = downloader.get_series_directory(
                        series, config.media_directory, config.sonarr_directory
                    )
                    counted_srt_files: set[str] = set()

                    for ep in monitored_episodes:
                        file_info = downloader.get_episode_file_info(
                            series, ep, output_dir
                        )

                        if file_info["has_video"] or file_info["has_strm"]:
                            downloaded_count += 1
                            if file_info["video_file"]:
                                video_path = output_dir / file_info["video_file"]
                                if video_path.exists():
                                    item_size += video_path.stat().st_size
                            if file_info["strm_file"]:
                                strm_path = output_dir / file_info["strm_file"]
                                if strm_path.exists():
                                    item_size += strm_path.stat().st_size
                        else:
                            missing_count += 1

                        for lang, srt_files in file_info["subtitles"].items():
                            subtitle_counts[lang] = subtitle_counts.get(lang, 0) + len(
                                srt_files
                            )
                            for srt_filename in srt_files:
                                counted_srt_files.add(srt_filename)
                                srt_path = output_dir / srt_filename
                                if srt_path.exists():
                                    item_size += srt_path.stat().st_size

                    # Scan all .srt files in directory
                    try:
                        for srt_file in output_dir.glob("*.srt"):
                            if (
                                not srt_file.is_file()
                                or srt_file.name in counted_srt_files
                            ):
                                continue
                            parts = srt_file.stem.split(".")
                            if len(parts) >= 2:
                                lang = parts[-1]
                                if lang == "forced" and len(parts) >= 3:
                                    lang = parts[-2]
                            else:
                                lang = "unknown"
                            subtitle_counts[lang] = subtitle_counts.get(lang, 0) + 1
                            item_size += srt_file.stat().st_size
                    except Exception as e:
                        logger.warning(
                            f"Error scanning srt files for {series.title}: {e}"
                        )
                except Exception as e:
                    logger.warning(f"Error processing season0 for {series.title}: {e}")

            # Process extras (tag mode) if applicable
            if has_tag and "tag" in active_modes:
                try:
                    extras_dir = downloader.get_extras_directory(
                        series, config.media_directory, config.sonarr_directory
                    )
                    if extras_dir.exists():
                        for file in extras_dir.iterdir():
                            if not file.is_file():
                                continue
                            file_size = file.stat().st_size
                            if file.suffix.lower() in {
                                ".mp4",
                                ".mkv",
                                ".avi",
                                ".mov",
                                ".wmv",
                                ".webm",
                            }:
                                downloaded_count += 1
                                item_size += file_size
                            elif file.suffix.lower() == ".srt":
                                item_size += file_size
                                parts = file.stem.split(".")
                                if len(parts) >= 2:
                                    lang = parts[-1]
                                    if lang == "forced" and len(parts) >= 3:
                                        lang = parts[-2]
                                    subtitle_counts[lang] = (
                                        subtitle_counts.get(lang, 0) + 1
                                    )
                except Exception as e:
                    logger.warning(f"Error processing extras for {series.title}: {e}")

        else:
            # Process movie
            movie = cast(Movie, media)
            try:
                extras_dir = downloader.get_movie_extras_directory(
                    movie, config.media_directory, config.radarr_directory
                )
                if extras_dir.exists():
                    for file in extras_dir.iterdir():
                        if not file.is_file():
                            continue
                        file_size = file.stat().st_size
                        if file.suffix.lower() in {
                            ".mp4",
                            ".mkv",
                            ".avi",
                            ".mov",
                            ".wmv",
                            ".webm",
                        }:
                            downloaded_count += 1
                            item_size += file_size
                        elif file.suffix.lower() == ".srt":
                            item_size += file_size
                            parts = file.stem.split(".")
                            if len(parts) >= 2:
                                lang = parts[-1]
                                if lang == "forced" and len(parts) >= 3:
                                    lang = parts[-2]
                                subtitle_counts[lang] = subtitle_counts.get(lang, 0) + 1
            except Exception as e:
                logger.warning(f"Error processing extras for movie {movie.title}: {e}")

        total_size += item_size

        # Format subtitle info
        if subtitle_counts:
            parts_list = [
                f"{count} {lang}" for lang, count in sorted(subtitle_counts.items())
            ]
            srt_info = ", ".join(parts_list)
        else:
            srt_info = "0"

        # Format size
        if item_size > 0:
            if item_size >= 1024**3:
                size_str = f"{item_size / (1024**3):.2f} GB"
            elif item_size >= 1024**2:
                size_str = f"{item_size / (1024**2):.2f} MB"
            elif item_size >= 1024:
                size_str = f"{item_size / 1024:.2f} KB"
            else:
                size_str = f"{item_size} B"
        else:
            size_str = "-"

        missing_str = str(missing_count) if processed_season0 else "-"

        table.add_row(
            type_text,
            str(media.id),
            media.title,
            media.path,
            str(downloaded_count),
            missing_str,
            srt_info,
            size_str,
        )

    console.print(table)

    # Display total size
    if total_size > 0:
        if total_size >= 1024**3:
            total_size_str = f"{total_size / (1024**3):.2f} GB"
        elif total_size >= 1024**2:
            total_size_str = f"{total_size / (1024**2):.2f} MB"
        elif total_size >= 1024:
            total_size_str = f"{total_size / 1024:.2f} KB"
        else:
            total_size_str = f"{total_size} B"
        console.print(f"\n[bold cyan]Total size:[/bold cyan] {total_size_str}")
