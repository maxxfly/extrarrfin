"""
List command - Display series with monitored season 0 or want-extras tag
"""

import logging
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.sonarr import SonarrClient

logger = logging.getLogger(__name__)
console = Console()


def list_command(
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    limit: str = None,
    mode: tuple = None,
):
    """Execute the list command logic"""

    # Use mode from command line or config
    # If multiple modes specified, use them; otherwise use config mode
    if mode:
        active_modes = [*mode]
    elif not isinstance(config.mode, str):
        active_modes = (
            [*config.mode] if hasattr(config.mode, "__iter__") else [config.mode]
        )
    else:
        active_modes = [config.mode]

    # Fetch series
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching series...", total=None)
        series_list = sonarr.get_monitored_series()
        progress.update(task, completed=True)

    # Filter based on mode(s)
    filtered_series = []
    for series in series_list:
        include = False
        if "tag" in active_modes and sonarr.has_want_extras_tag(series):
            include = True
        if "season0" in active_modes and sonarr.has_monitored_season_zero_episodes(
            series
        ):
            include = True
        if include:
            filtered_series.append(series)

    # Filter by name/ID if specified
    if limit:
        if limit.isdigit():
            filtered_series = [s for s in filtered_series if s.id == int(limit)]
        else:
            filtered_series = [
                s for s in filtered_series if limit.lower() in s.title.lower()
            ]

    if not filtered_series:
        if len(active_modes) > 1:
            console.print(
                f"[yellow]No series found for modes: {', '.join(active_modes)}[/yellow]"
            )
        elif "tag" in active_modes:
            console.print("[yellow]No series found with want-extras tag[/yellow]")
        else:
            console.print("[yellow]No series found with monitored season 0[/yellow]")
        return

    # Display table
    if len(active_modes) > 1:
        table_title = f"Series ({', '.join(active_modes)}) - {len(filtered_series)}"
    elif "tag" in active_modes:
        table_title = f"Series with want-extras tag ({len(filtered_series)})"
    else:
        table_title = f"Series with Monitored Season 0 ({len(filtered_series)})"

    table = Table(title=table_title)
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Path", style="dim")
    table.add_column("Downloaded", style="blue")
    table.add_column("Missing", style="yellow")
    table.add_column("Subtitles", style="magenta")
    table.add_column("Size", style="cyan")

    total_size = 0

    for series in filtered_series:
        # Determine which mode(s) apply to this series
        has_tag = sonarr.has_want_extras_tag(series)
        has_season0 = sonarr.has_monitored_season_zero_episodes(series)

        # Initialize counters
        downloaded_count = 0
        missing_count = 0
        subtitle_by_lang = {}
        series_size = 0

        # Process Season 0 episodes if applicable
        if has_season0 and "season0" in active_modes:
            try:
                episodes = sonarr.get_season_zero_episodes(series.id)
                monitored_episodes = [e for e in episodes if e.monitored]

                output_dir = downloader.get_series_directory(
                    series, config.media_directory, config.sonarr_directory
                )

                # Track which subtitle files we've already counted
                counted_srt_files = set()

                # Count files by actually scanning the directory
                for ep in monitored_episodes:
                    file_info = downloader.get_episode_file_info(series, ep, output_dir)

                    # Check if episode has a file
                    if file_info["has_video"] or file_info["has_strm"]:
                        downloaded_count += 1

                        # Add video file size
                        if file_info["video_file"]:
                            video_path = output_dir / file_info["video_file"]
                            if video_path.exists():
                                series_size += video_path.stat().st_size

                        # Add STRM file size (tiny but for completeness)
                        if file_info["strm_file"]:
                            strm_path = output_dir / file_info["strm_file"]
                            if strm_path.exists():
                                series_size += strm_path.stat().st_size
                    else:
                        # No file = missing
                        missing_count += 1

                    # Count subtitles for this episode
                    for lang, srt_files in file_info["subtitles"].items():
                        # Count all subtitle files for this language
                        subtitle_by_lang[lang] = subtitle_by_lang.get(lang, 0) + len(
                            srt_files
                        )

                        # Add sizes and track files
                        for srt_filename in srt_files:
                            counted_srt_files.add(srt_filename)
                            srt_path = output_dir / srt_filename
                            if srt_path.exists():
                                series_size += srt_path.stat().st_size

                # Also scan ALL .srt files in the directory (including non-monitored episodes)
                # to give a complete picture of what's actually on disk
                try:
                    all_srt_files = list(output_dir.glob("*.srt"))
                    for srt_file in all_srt_files:
                        if not srt_file.is_file() or srt_file.name in counted_srt_files:
                            continue

                        # This is a subtitle for a non-monitored episode
                        parts = srt_file.stem.split(".")
                        if len(parts) >= 2:
                            lang = parts[-1]
                            if lang == "forced" and len(parts) >= 3:
                                lang = parts[-2]
                        else:
                            lang = "unknown"

                        subtitle_by_lang[lang] = subtitle_by_lang.get(lang, 0) + 1
                        series_size += srt_file.stat().st_size
                except Exception as e:
                    logger.warning(
                        f"Error scanning all srt files for {series.title}: {e}"
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
                            # Video file in extras
                            downloaded_count += 1
                            series_size += file_size

                        elif file.suffix.lower() == ".srt":
                            # Subtitle in extras
                            series_size += file_size
                            parts = file.stem.split(".")
                            if len(parts) >= 2:
                                lang = parts[-1]
                                if lang == "forced" and len(parts) >= 3:
                                    lang = parts[-2]
                                subtitle_by_lang[lang] = (
                                    subtitle_by_lang.get(lang, 0) + 1
                                )
            except Exception as e:
                logger.warning(f"Error processing extras for {series.title}: {e}")

        total_size += series_size

        # Format subtitle info
        if subtitle_by_lang:
            parts = [
                f"{count} {lang}" for lang, count in sorted(subtitle_by_lang.items())
            ]
            srt_info = ", ".join(parts)
        else:
            srt_info = "0"

        # Format size
        if series_size > 0:
            if series_size >= 1024**3:  # GB
                size_str = f"{series_size / (1024**3):.2f} GB"
            elif series_size >= 1024**2:  # MB
                size_str = f"{series_size / (1024**2):.2f} MB"
            elif series_size >= 1024:  # KB
                size_str = f"{series_size / 1024:.2f} KB"
            else:
                size_str = f"{series_size} B"
        else:
            size_str = "-"

        # Show missing count or dash
        missing_str = str(missing_count) if missing_count > 0 else "-"

        table.add_row(
            str(series.id),
            series.title,
            series.path,
            str(downloaded_count),
            missing_str,
            srt_info,
            size_str,
        )

    console.print(table)

    # Display total size
    if total_size > 0:
        if total_size >= 1024**3:  # GB
            total_size_str = f"{total_size / (1024**3):.2f} GB"
        elif total_size >= 1024**2:  # MB
            total_size_str = f"{total_size / (1024**2):.2f} MB"
        elif total_size >= 1024:  # KB
            total_size_str = f"{total_size / 1024:.2f} KB"
        else:
            total_size_str = f"{total_size} B"

        console.print(f"\n[bold cyan]Total size:[/bold cyan] {total_size_str}")
