"""
Season 0 mode handler - Download monitored season 0 episodes
"""

import logging

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.models import Series
from extrarrfin.sonarr import SonarrClient
from extrarrfin.utils import format_episode_info

logger = logging.getLogger(__name__)
console = Console()


def download_season0_mode(
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    limit: str | None = None,
    episode: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    no_scan: bool = False,
    verbose: bool = False,
):
    """
    Download monitored season 0 episodes

    Args:
        config: Configuration object
        sonarr: Sonarr client
        downloader: Downloader instance
        limit: Optional series name or ID to limit downloads
        episode: Specific episode number to download (None = all)
        dry_run: If True, don't actually download
        force: If True, re-download even if file exists
        no_scan: If True, don't trigger Sonarr scan
        verbose: If True, show detailed info

    Returns:
        Tuple of (total_downloads, successful_downloads, failed_downloads)
    """
    total_downloads = 0
    successful_downloads = 0
    failed_downloads = 0

    # Fetch series
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching series...", total=None)
        series_list = sonarr.get_monitored_series()
        progress.update(task, completed=True)

    # Filter to keep only those with monitored season 0 episodes
    series_with_season0 = [
        s for s in series_list if sonarr.has_monitored_season_zero_episodes(s)
    ]

    # Filter by name/ID if specified
    if limit:
        if limit.isdigit():
            series_with_season0 = [s for s in series_with_season0 if s.id == int(limit)]
        else:
            series_with_season0 = [
                s for s in series_with_season0 if limit.lower() in s.title.lower()
            ]

    if not series_with_season0:
        console.print("[yellow]No series found[/yellow]")
        return total_downloads, successful_downloads, failed_downloads

    # Validation: episode option requires limit
    if episode is not None and not limit:
        console.print(
            "[red]Error:[/red] --episode requires --limit to specify a series"
        )
        console.print(
            "[dim]Example: python extrarrfin.py download --limit 'Series Name' --episode 5[/dim]"
        )
        return total_downloads, successful_downloads, failed_downloads

    # Process each series
    for series in series_with_season0:
        console.print(f"\n[bold cyan]Processing:[/bold cyan] {series.title}")

        t, s, f = _download_series_season0(
            series,
            config,
            sonarr,
            downloader,
            episode,
            dry_run,
            force,
            no_scan,
            verbose,
        )
        total_downloads += t
        successful_downloads += s
        failed_downloads += f

    return total_downloads, successful_downloads, failed_downloads


def _download_series_season0(
    series: Series,
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    episode: int | None = None,
    dry_run: bool = False,
    force: bool = False,
    no_scan: bool = False,
    verbose: bool = False,
):
    """
    Download monitored season 0 episodes for a single series

    Args:
        series: The series to process
        config: Configuration object
        sonarr: Sonarr client
        downloader: Downloader instance
        episode: Specific episode number to download (None = all)
        dry_run: If True, don't actually download
        force: If True, re-download even if file exists
        no_scan: If True, don't trigger Sonarr scan
        verbose: If True, show detailed info

    Returns:
        Tuple of (total_downloads, successful_downloads, failed_downloads)
    """
    total_downloads = 0
    successful_downloads = 0
    failed_downloads = 0

    # Get episodes to process
    episodes = sonarr.get_season_zero_episodes(series.id)

    # Filter by episode number if specified
    if episode is not None:
        episodes = [e for e in episodes if e.episode_number == episode]
        if not episodes:
            console.print(f"  [yellow]Episode {episode} not found[/yellow]")
            return total_downloads, successful_downloads, failed_downloads

    # If force mode, process all monitored episodes; otherwise only missing ones
    if force:
        to_process = [e for e in episodes if e.monitored]
    else:
        to_process = [e for e in episodes if e.monitored and not e.has_file]

    if not to_process:
        if force:
            console.print("  [dim]No monitored episodes[/dim]")
        else:
            console.print("  [dim]No missing episodes[/dim]")
        return total_downloads, successful_downloads, failed_downloads

    # Determine output directory
    try:
        output_dir = downloader.get_series_directory(
            series, config.media_directory, config.sonarr_directory
        )
        console.print(f"  [dim]Directory:[/dim] {output_dir}")
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}")
        return total_downloads, successful_downloads, failed_downloads

    # Process each episode
    for ep in to_process:
        total_downloads += 1
        ep_info = format_episode_info(
            series.title,
            ep.season_number,
            ep.episode_number,
            ep.title,
        )

        if dry_run:
            console.print(f"  [yellow]DRY RUN:[/yellow] {ep_info}")
        else:
            console.print(f"  [blue]Downloading:[/blue] {ep_info}")

        # Show verbose info if enabled
        if verbose:
            console.print(f"    [dim]Search query: '{series.title} {ep.title}'[/dim]")

        # Download episode
        success, file_path, error, video_info = downloader.download_episode(
            series,
            ep,
            output_dir,
            force=force,
            dry_run=dry_run,
        )

        if success:
            successful_downloads += 1
            console.print(f"    [green]✓ Downloaded:[/green] {file_path}")

            # Create NFO file with video metadata if we have video info
            if video_info and file_path:
                try:
                    from pathlib import Path

                    file_path_obj = Path(file_path)
                    base_filename = file_path_obj.stem
                    downloader.create_nfo_file(base_filename, output_dir, video_info)
                except Exception as e:
                    console.print(f"    [yellow]⚠ NFO creation warning:[/yellow] {e}")
        else:
            failed_downloads += 1
            console.print(f"    [red]✗ Failed:[/red] {error}")

    # Trigger Sonarr scan if requested and if some downloads succeeded
    if not dry_run and not no_scan and successful_downloads > 0:
        try:
            console.print("  [blue]Scanning Sonarr...[/blue]")
            sonarr.rescan_series(series.id)
            console.print("    [green]✓ Scan triggered[/green]")
        except Exception as e:
            console.print(f"    [red]Scan error:[/red] {e}")

    return total_downloads, successful_downloads, failed_downloads
