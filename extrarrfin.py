"""
Command Line Interface (CLI) with Click
"""

import logging
import sys
import time

import click
import schedule
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from extrarrfin.cli_config import (
    load_config_from_args,
    setup_context,
    validate_sonarr_connection,
)
from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.sonarr import SonarrClient
from extrarrfin.utils import format_episode_info, setup_logging

logger = logging.getLogger(__name__)
console = Console()


@click.group()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="YAML configuration file"
)
@click.option("--sonarr-url", envvar="SONARR_URL", help="Sonarr URL")
@click.option("--sonarr-api-key", envvar="SONARR_API_KEY", help="Sonarr API key")
@click.option("--media-dir", help="Media directory")
@click.option("--sonarr-dir", help="Sonarr root directory")
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
)
@click.pass_context
def cli(ctx, config, sonarr_url, sonarr_api_key, media_dir, sonarr_dir, log_level):
    """ExtrarrFin - Special episodes (Season 0) downloader for Sonarr"""

    # Setup logging
    setup_logging(log_level)

    # Load and validate configuration
    cfg = load_config_from_args(
        config, sonarr_url, sonarr_api_key, media_dir, sonarr_dir, log_level
    )

    # Validate Sonarr connection
    sonarr_client = validate_sonarr_connection(cfg)

    # Setup context
    ctx.ensure_object(dict)
    ctx.obj.update(setup_context(cfg, sonarr_client))


@cli.command()
@click.option("--limit", "-l", help="Limit to specific series (name or ID)")
@click.pass_context
def list(ctx, limit):
    """List all series with monitored season 0"""

    config: Config = ctx.obj["config"]
    sonarr: SonarrClient = ctx.obj["sonarr"]
    downloader: Downloader = ctx.obj["downloader"]

    try:
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
                series_with_season0 = [
                    s for s in series_with_season0 if s.id == int(limit)
                ]
            else:
                series_with_season0 = [
                    s for s in series_with_season0 if limit.lower() in s.title.lower()
                ]

        if not series_with_season0:
            console.print("[yellow]No series found with monitored season 0[/yellow]")
            return

        # Display table
        table = Table(
            title=f"Series with Monitored Season 0 ({len(series_with_season0)})"
        )
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="green")
        table.add_column("Path", style="dim")
        table.add_column("Downloaded", style="blue")
        table.add_column("Missing", style="yellow")
        table.add_column("Subtitles", style="magenta")
        table.add_column("Size", style="cyan")

        total_size = 0

        for series in series_with_season0:
            # Get season 0 episodes
            episodes = sonarr.get_season_zero_episodes(series.id)
            monitored_episodes = [e for e in episodes if e.monitored]
            missing = [e for e in monitored_episodes if not e.has_file]
            downloaded = [e for e in monitored_episodes if e.has_file]

            # Count subtitles and calculate size for downloaded episodes
            # We scan ALL monitored episodes, not just those Sonarr considers downloaded
            # because STRM files might not be detected by Sonarr
            subtitle_by_lang = {}
            series_size = 0

            try:
                output_dir = downloader.get_series_directory(
                    series, config.media_directory, config.sonarr_directory
                )

                # Scan all monitored episodes to detect files
                for ep in monitored_episodes:
                    file_info = downloader.get_episode_file_info(series, ep, output_dir)

                    # Only count if there are actual files
                    if (
                        not file_info["has_video"]
                        and not file_info["has_strm"]
                        and not file_info["subtitles"]
                    ):
                        continue

                    # Count subtitles by language
                    for lang, files in file_info["subtitles"].items():
                        if lang not in subtitle_by_lang:
                            subtitle_by_lang[lang] = 0
                        subtitle_by_lang[lang] += len(files)

                    # Calculate file sizes
                    if file_info["video_file"]:
                        video_path = output_dir / file_info["video_file"]
                        if video_path.exists():
                            series_size += video_path.stat().st_size

                    if file_info["strm_file"]:
                        strm_path = output_dir / file_info["strm_file"]
                        if strm_path.exists():
                            series_size += strm_path.stat().st_size

                    # Add subtitle file sizes
                    for srt_files_list in file_info["subtitles"].values():
                        for srt_file in srt_files_list:
                            srt_path = output_dir / srt_file
                            if srt_path.exists():
                                series_size += srt_path.stat().st_size

                total_size += series_size
            except Exception:
                # If we can't access the directory, just skip counting
                pass

            # Format subtitle info
            if subtitle_by_lang:
                # Show count per language: "3 fr, 2 en"
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

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Error during listing")
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", help="Limit to specific series (name or ID)")
@click.option(
    "--episode", "-e", type=int, help="Target a specific episode number (S00Exx)"
)
@click.option("--dry-run", "-d", is_flag=True, help="Simulation mode (don't download)")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force re-download even if file exists",
)
@click.option(
    "--no-scan",
    is_flag=True,
    help="Don't trigger Sonarr scan after download",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose mode (show detailed YouTube search and download info)",
)
@click.pass_context
def download(ctx, limit, episode, dry_run, force, no_scan, verbose):
    """Download missing season 0 episodes"""

    config: Config = ctx.obj["config"]
    sonarr: SonarrClient = ctx.obj["sonarr"]
    downloader: Downloader = ctx.obj["downloader"]

    # Enable verbose mode if requested
    downloader.verbose = verbose

    try:
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
                series_with_season0 = [
                    s for s in series_with_season0 if s.id == int(limit)
                ]
            else:
                series_with_season0 = [
                    s for s in series_with_season0 if limit.lower() in s.title.lower()
                ]

        if not series_with_season0:
            console.print("[yellow]No series found[/yellow]")
            return

        # Validation: episode option requires limit
        if episode is not None and not limit:
            console.print(
                "[red]Error:[/red] --episode requires --limit to specify a series"
            )
            console.print(
                "[dim]Example: python extrarrfin.py download --limit 'Series Name' --episode 5[/dim]"
            )
            return

        # Safety check: warn if force mode is used without limit
        if force and not limit and not dry_run:
            console.print(
                f"\n[bold yellow]Warning:[/bold yellow] Force mode will re-download "
                f"ALL episodes for {len(series_with_season0)} series!"
            )
            console.print("[dim]Tip: Use --limit to target a specific series[/dim]")

            if not click.confirm("Do you want to continue?", default=False):
                console.print("[yellow]Operation cancelled[/yellow]")
                return

        # Process each series
        total_downloads = 0
        successful_downloads = 0
        failed_downloads = 0

        for series in series_with_season0:
            console.print(f"\n[bold cyan]Processing:[/bold cyan] {series.title}")

            # Get episodes to process
            episodes = sonarr.get_season_zero_episodes(series.id)

            # Filter by episode number if specified
            if episode is not None:
                episodes = [e for e in episodes if e.episode_number == episode]
                if not episodes:
                    console.print(f"  [yellow]Episode {episode} not found[/yellow]")
                    continue

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
                continue

            # Determine output directory
            try:
                output_dir = downloader.get_series_directory(
                    series, config.media_directory, config.sonarr_directory
                )
                console.print(f"  [dim]Directory:[/dim] {output_dir}")
            except Exception as e:
                console.print(f"  [red]Error:[/red] {e}")
                continue

            # Process each episode
            for episode in to_process:
                total_downloads += 1
                ep_info = format_episode_info(
                    series.title,
                    episode.season_number,
                    episode.episode_number,
                    episode.title,
                )

                if dry_run:
                    console.print(f"  [yellow]DRY RUN:[/yellow] {ep_info}")
                    # Check if file exists
                    file_info = downloader.get_episode_file_info(
                        series, episode, output_dir
                    )
                    if file_info["has_video"] or file_info["has_strm"]:
                        console.print(f"    [dim]File already present[/dim]")
                    else:
                        console.print(
                            f"    [dim]Would search and download from YouTube[/dim]"
                        )

                    # Show what would happen with force mode
                    if force and (file_info["has_video"] or file_info["has_strm"]):
                        console.print(
                            f"    [dim]Would delete existing file and re-download[/dim]"
                        )

                    successful_downloads += 1
                    continue

                console.print(f"  [blue]Downloading:[/blue] {ep_info}")

                # Show verbose info if enabled
                if verbose:
                    console.print(
                        f"    [dim]Search query: '{series.title} {episode.title}'[/dim]"
                    )

                # Download episode
                success, file_path, error = downloader.download_episode(
                    series,
                    episode,
                    output_dir,
                    force=force,
                    dry_run=dry_run,
                )

                if success:
                    successful_downloads += 1
                    console.print(f"    [green]✓ Downloaded:[/green] {file_path}")
                else:
                    failed_downloads += 1
                    console.print(f"    [red]✗ Failed:[/red] {error}")

            # Trigger Sonarr scan if requested and if some downloads succeeded
            if not dry_run and not no_scan and successful_downloads > 0:
                try:
                    console.print(f"  [blue]Scanning Sonarr...[/blue]")
                    sonarr.rescan_series(series.id)
                    console.print(f"    [green]✓ Scan triggered[/green]")
                except Exception as e:
                    console.print(f"    [red]Scan error:[/red] {e}")

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  Total: {total_downloads}")
        console.print(f"  [green]Success: {successful_downloads}[/green]")
        console.print(f"  [red]Failed: {failed_downloads}[/red]")

        if dry_run:
            console.print("\n[yellow]DRY RUN mode - No downloads performed[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Error during download")
        sys.exit(1)


@cli.command()
@click.argument("series_id", type=int)
@click.option("--dry-run", "-d", is_flag=True, help="Simulation mode (don't scan)")
@click.pass_context
def scan(ctx, series_id, dry_run):
    """Trigger a manual scan of a series in Sonarr"""

    sonarr: SonarrClient = ctx.obj["sonarr"]

    try:
        if dry_run:
            console.print(
                f"[yellow]DRY RUN:[/yellow] Would trigger scan for series ID {series_id}"
            )
            console.print("[dim]No actual scan will be performed[/dim]")
        else:
            console.print(f"Triggering scan for series ID {series_id}...")
            sonarr.rescan_series(series_id)
            console.print("[green]✓ Scan triggered successfully[/green]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def test(ctx):
    """Test connection to Sonarr"""

    config: Config = ctx.obj["config"]
    sonarr: SonarrClient = ctx.obj["sonarr"]

    try:
        console.print("Testing Sonarr connection...")
        console.print(f"URL: {config.sonarr_url}")

        series = sonarr.get_all_series()
        console.print(f"[green]✓ Connection successful![/green]")
        console.print(f"Number of series: {len(series)}")

        monitored = [s for s in series if s.monitored]
        console.print(f"Monitored series: {len(monitored)}")

        with_season0 = [
            s for s in monitored if sonarr.has_monitored_season_zero_episodes(s)
        ]
        console.print(f"With monitored season 0 episodes: {len(with_season0)}")

    except Exception as e:
        console.print(f"[red]✗ Connection error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", help="Limit to specific series (name or ID)")
@click.option(
    "--episode", "-e", type=int, help="Target a specific episode number (S00Exx)"
)
@click.option("--dry-run", "-d", is_flag=True, help="Simulation mode (don't download)")
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force re-download even if file exists",
)
@click.option(
    "--no-scan",
    is_flag=True,
    help="Don't trigger Sonarr scan after download",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Verbose mode (show detailed YouTube search and download info)",
)
@click.option(
    "--interval",
    type=int,
    help="Override schedule interval from config",
)
@click.option(
    "--unit",
    type=click.Choice(["seconds", "minutes", "hours", "days", "weeks"]),
    help="Override schedule unit from config",
)
@click.pass_context
def schedule_mode(
    ctx, limit, episode, dry_run, force, no_scan, verbose, interval, unit
):
    """Run downloads on a schedule"""

    config: Config = ctx.obj["config"]

    # Use command-line args if provided, otherwise use config
    schedule_interval = interval if interval is not None else config.schedule_interval
    schedule_unit = unit if unit is not None else config.schedule_unit

    # Validate schedule unit
    valid_units = ["seconds", "minutes", "hours", "days", "weeks"]
    if schedule_unit not in valid_units:
        console.print(f"[red]Invalid schedule unit:[/red] {schedule_unit}")
        console.print(f"Valid units: {', '.join(valid_units)}")
        sys.exit(1)

    console.print("[bold cyan]ExtrarrFin - Schedule Mode[/bold cyan]")
    console.print(f"Running downloads every {schedule_interval} {schedule_unit}")
    console.print("Press Ctrl+C to stop\n")

    def run_download():
        """Run the download command"""
        try:
            console.print(f"\n[bold blue]{'=' * 60}[/bold blue]")
            console.print(
                f"[bold blue]Running scheduled download at {time.strftime('%Y-%m-%d %H:%M:%S')}[/bold blue]"
            )
            console.print(f"[bold blue]{'=' * 60}[/bold blue]\n")

            # Call the download command logic
            ctx.invoke(
                download,
                limit=limit,
                episode=episode,
                dry_run=dry_run,
                force=force,
                no_scan=no_scan,
                verbose=verbose,
            )

            console.print(
                f"\n[dim]Next run in {schedule_interval} {schedule_unit}[/dim]"
            )

        except Exception as e:
            console.print(f"[red]Error during scheduled download:[/red] {e}")
            logger.exception("Error during scheduled download")

    # Setup schedule based on unit
    schedule_job = schedule.every(schedule_interval)

    if schedule_unit == "seconds":
        schedule_job.seconds.do(run_download)
    elif schedule_unit == "minutes":
        schedule_job.minutes.do(run_download)
    elif schedule_unit == "hours":
        schedule_job.hours.do(run_download)
    elif schedule_unit == "days":
        schedule_job.days.do(run_download)
    elif schedule_unit == "weeks":
        schedule_job.weeks.do(run_download)

    # Run immediately on start
    console.print("[yellow]Running initial download...[/yellow]")
    run_download()

    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Schedule mode stopped by user[/yellow]")
        sys.exit(0)


def main():
    """Main entry point"""
    cli(obj={})


if __name__ == "__main__":
    main()
