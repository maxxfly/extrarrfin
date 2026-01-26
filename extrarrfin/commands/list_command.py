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

        # In tag mode, we show the series but don't count episodes
        if (
            "tag" in active_modes
            and has_tag
            and not ("season0" in active_modes and has_season0)
        ):
            # Get output directory for extras
            try:
                output_dir = downloader.get_extras_directory(
                    series, config.media_directory, config.sonarr_directory
                )

                # Count files in the extras directory
                subtitle_by_lang = {}
                series_size = 0
                video_count = 0

                if output_dir.exists():
                    for file in output_dir.iterdir():
                        if file.is_file():
                            if file.suffix.lower() in {
                                ".mp4",
                                ".mkv",
                                ".avi",
                                ".mov",
                                ".wmv",
                                ".webm",
                            }:
                                video_count += 1
                                series_size += file.stat().st_size
                            elif file.suffix.lower() == ".srt":
                                # Extract language from subtitle filename
                                # Format: "filename.lang.srt" or "filename.lang.forced.srt"
                                parts = file.stem.split(".")
                                if len(parts) >= 2:
                                    # Get the last part before extension (could be 'forced' or lang code)
                                    lang = parts[-1]
                                    if lang == "forced" and len(parts) >= 3:
                                        lang = parts[-2]

                                    # Count by language
                                    subtitle_by_lang[lang] = (
                                        subtitle_by_lang.get(lang, 0) + 1
                                    )

                total_size += series_size

                # Format subtitle info
                if subtitle_by_lang:
                    parts = [
                        f"{count} {lang}"
                        for lang, count in sorted(subtitle_by_lang.items())
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

                table.add_row(
                    str(series.id),
                    series.title,
                    series.path,
                    str(video_count),
                    "-",
                    srt_info,
                    size_str,
                )
            except Exception as e:
                logger.warning(f"Error processing series {series.title}: {e}")
                table.add_row(
                    str(series.id),
                    series.title,
                    series.path,
                    "Error",
                    "-",
                    "-",
                    "-",
                )
        else:
            # Original season0 mode logic
            # Get season 0 episodes
            episodes = sonarr.get_season_zero_episodes(series.id)
            monitored_episodes = [e for e in episodes if e.monitored]
            missing = [e for e in monitored_episodes if not e.has_file]
            downloaded = [e for e in monitored_episodes if e.has_file]

            # Count subtitles and calculate size for downloaded episodes
            subtitle_by_lang = {}
            series_size = 0

            try:
                output_dir = downloader.get_series_directory(
                    series, config.media_directory, config.sonarr_directory
                )

                # Scan all monitored episodes to detect files
                for ep in monitored_episodes:
                    file_info = downloader.get_episode_file_info(series, ep, output_dir)

                    if file_info["has_video"] or file_info["has_strm"]:
                        # Count size only for video files (not STRM)
                        if file_info["video_path"]:
                            video_path = Path(file_info["video_path"])
                            if video_path.exists():
                                series_size += video_path.stat().st_size

                    # Count subtitles for this episode
                    if file_info["subtitle_files"]:
                        for srt_file in file_info["subtitle_files"]:
                            srt_path = Path(srt_file)
                            parts = srt_path.stem.split(".")
                            if len(parts) >= 2:
                                lang = parts[-1]
                                if lang == "forced" and len(parts) >= 3:
                                    lang = parts[-2]
                                subtitle_by_lang[lang] = (
                                    subtitle_by_lang.get(lang, 0) + 1
                                )

                # Also scan for ALL subtitle files in the directory
                try:
                    all_files = [f for f in output_dir.glob("*.srt")]
                    monitored_ep_nums = [ep.episode_number for ep in monitored_episodes]

                    for file in all_files:
                        # Check if this is a subtitle for a monitored episode
                        # Expected format: "SeriesName - S00E01.lang.srt"
                        if "S00E" in file.stem:
                            ep_num_str = file.stem.split("S00E")[1].split(".")[0]
                            try:
                                ep_num = int(ep_num_str)
                                if ep_num in monitored_ep_nums:
                                    # Extract language
                                    parts = file.stem.split(".")
                                    if len(parts) >= 2:
                                        lang = parts[-1]
                                        if lang == "forced" and len(parts) >= 3:
                                            lang = parts[-2]
                                        if lang not in subtitle_by_lang:
                                            subtitle_by_lang[lang] = (
                                                subtitle_by_lang.get(lang, 0) + 1
                                            )
                            except (ValueError, IndexError):
                                pass
                except Exception as e:
                    logger.warning(
                        f"Error scanning directory for additional subtitles: {e}"
                    )

                total_size += series_size
            except Exception:
                # If we can't access the directory, just skip counting
                pass

            # Format subtitle info
            if subtitle_by_lang:
                parts = [
                    f"{count} {lang}"
                    for lang, count in sorted(subtitle_by_lang.items())
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

            table.add_row(
                str(series.id),
                series.title,
                series.path,
                str(len(downloaded)),
                str(len(missing)),
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
