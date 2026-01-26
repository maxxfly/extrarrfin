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
from extrarrfin.commands import (
    download_season0_mode,
    download_tag_mode,
    list_command,
    test_command,
)
from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.jellyfin import JellyfinClient
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
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["season0", "tag"]),
    multiple=True,
    help="List mode: season0 (monitored Season 0 episodes) or tag (series with want-extras tag). Can be specified multiple times.",
)
@click.pass_context
def list(ctx, limit, mode):
    """List all series with monitored season 0 or tagged series"""

    config: Config = ctx.obj["config"]
    sonarr: SonarrClient = ctx.obj["sonarr"]
    downloader: Downloader = ctx.obj["downloader"]

    # Determine which modes to run
    modes = [*mode] if mode else (
        [*config.mode] if isinstance(config.mode, tuple) else 
        [config.mode] if config.mode else 
        ["season0"]
    )

    list_command(config, sonarr, downloader, limit, modes)


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
    "--mode",
    "-m",
    type=click.Choice(["season0", "tag"]),
    multiple=True,
    help="Download mode: season0 (monitored Season 0 episodes) or tag (behind-the-scenes videos for tagged series). Can be specified multiple times.",
)
@click.option(
    "--jellyfin-url",
    envvar="JELLYFIN_URL",
    help="Jellyfin server URL (e.g., http://localhost:8096)",
)
@click.option(
    "--jellyfin-api-key",
    envvar="JELLYFIN_API_KEY",
    help="Jellyfin API key for library refresh",
)
@click.pass_context
def download(
    ctx,
    limit,
    episode,
    dry_run,
    force,
    no_scan,
    verbose,
    mode,
    jellyfin_url,
    jellyfin_api_key,
):
    """Download missing season 0 episodes"""

    config: Config = ctx.obj["config"]
    sonarr: SonarrClient = ctx.obj["sonarr"]
    downloader: Downloader = ctx.obj["downloader"]

    # Enable verbose mode if requested
    downloader.verbose = verbose

    # Determine which modes to run
    # Use mode from CLI if provided, otherwise use config, otherwise default to season0
    modes = (
        [*mode]
        if mode
        else (
            [*config.mode]
            if isinstance(config.mode, tuple)
            else [config.mode]
            if config.mode
            else ["season0"]
        )
    )

    try:
        total_downloads = 0
        successful_downloads = 0
        failed_downloads = 0

        # Run each mode
        for current_mode in modes:
            if current_mode == "season0":
                console.print("\n[bold magenta]Mode: Season 0[/bold magenta]")
                total, success, failed = download_season0_mode(
                    config,
                    sonarr,
                    downloader,
                    limit,
                    episode,
                    dry_run,
                    force,
                    no_scan,
                    verbose,
                )
                total_downloads += total
                successful_downloads += success
                failed_downloads += failed

            elif current_mode == "tag":
                console.print(
                    "\n[bold magenta]Mode: Tag (Behind-the-Scenes)[/bold magenta]"
                )
                total, success, failed = download_tag_mode(
                    config,
                    sonarr,
                    downloader,
                    limit,
                    dry_run,
                    force,
                    no_scan,
                    verbose,
                )
                total_downloads += total
                successful_downloads += success
                failed_downloads += failed

        # Overall summary
        console.print("\n[bold]Overall Summary:[/bold]")
        console.print(f"  Total: {total_downloads}")
        console.print(f"  [green]Success: {successful_downloads}[/green]")
        console.print(f"  [red]Failed: {failed_downloads}[/red]")

        if dry_run:
            console.print("\n[yellow]DRY RUN mode - No downloads performed[/yellow]")

        # Trigger Jellyfin library refresh if configured and downloads were successful
        if successful_downloads > 0 and not dry_run:
            # Use command-line args if provided, otherwise use config
            jf_url = jellyfin_url or config.jellyfin_url
            jf_api_key = jellyfin_api_key or config.jellyfin_api_key

            if jf_url and jf_api_key:
                try:
                    console.print("\n[blue]Refreshing Jellyfin library...[/blue]")
                    jellyfin = JellyfinClient(jf_url, jf_api_key)
                    if jellyfin.refresh_library():
                        console.print(
                            "[green]✓ Jellyfin library refresh triggered[/green]"
                        )
                    else:
                        console.print(
                            "[yellow]⚠ Failed to trigger Jellyfin library refresh[/yellow]"
                        )
                except Exception as e:
                    console.print(f"[red]Jellyfin refresh error:[/red] {e}")
                    logger.exception("Error triggering Jellyfin refresh")

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
@click.option(
    "--jellyfin-url",
    envvar="JELLYFIN_URL",
    help="Jellyfin server URL (e.g., http://localhost:8096)",
)
@click.option(
    "--jellyfin-api-key",
    envvar="JELLYFIN_API_KEY",
    help="Jellyfin API key for library refresh",
)
@click.pass_context
def test(ctx, jellyfin_url, jellyfin_api_key):
    """Test connection to Sonarr and Jellyfin"""
    config: Config = ctx.obj["config"]
    sonarr: SonarrClient = ctx.obj["sonarr"]
    test_command(config, sonarr, jellyfin_url, jellyfin_api_key)


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
