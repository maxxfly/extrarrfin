"""
Command Line Interface (CLI) with Click
"""

import logging
import sys

import click
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

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching series...", total=None)
            series_list = sonarr.get_monitored_series()
            progress.update(task, completed=True)

        # Filter to keep only those with monitored season 0
        series_with_season0 = [
            s for s in series_list if sonarr.has_monitored_season_zero(s)
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
        table.add_column("Missing episodes", style="yellow")

        for series in series_with_season0:
            # Get season 0 episodes
            episodes = sonarr.get_season_zero_episodes(series.id)
            missing = [e for e in episodes if e.monitored and not e.has_file]

            table.add_row(str(series.id), series.title, series.path, str(len(missing)))

        console.print(table)

        # Display missing episodes details
        console.print("\n[bold]Missing episodes details:[/bold]\n")
        for series in series_with_season0:
            episodes = sonarr.get_season_zero_episodes(series.id)
            missing = [e for e in episodes if e.monitored and not e.has_file]

            if missing:
                console.print(f"[green]{series.title}[/green] (ID: {series.id})")
                for ep in missing:
                    console.print(
                        f"  • S{ep.season_number:02d}E{ep.episode_number:02d} - {ep.title}"
                    )
                console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        logger.exception("Error during listing")
        sys.exit(1)


@cli.command()
@click.option("--limit", "-l", help="Limit to specific series (name or ID)")
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
@click.pass_context
def download(ctx, limit, dry_run, force, no_scan):
    """Download missing season 0 episodes"""

    config: Config = ctx.obj["config"]
    sonarr: SonarrClient = ctx.obj["sonarr"]
    downloader: Downloader = ctx.obj["downloader"]

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

        # Filter to keep only those with monitored season 0
        series_with_season0 = [
            s for s in series_list if sonarr.has_monitored_season_zero(s)
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

        # Process each series
        total_downloads = 0
        successful_downloads = 0
        failed_downloads = 0

        for series in series_with_season0:
            console.print(f"\n[bold cyan]Processing:[/bold cyan] {series.title}")

            # Get missing episodes
            episodes = sonarr.get_season_zero_episodes(series.id)
            missing = [e for e in episodes if e.monitored and not e.has_file]

            if not missing:
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
            for episode in missing:
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
                    if downloader.file_exists(series, episode, output_dir):
                        console.print(f"    [dim]File already present[/dim]")
                    continue

                console.print(f"  [blue]Downloading:[/blue] {ep_info}")

                # Download episode
                success, file_path, error = downloader.download_episode(
                    series,
                    episode,
                    output_dir,
                    force=force,
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
@click.pass_context
def scan(ctx, series_id):
    """Trigger a manual scan of a series in Sonarr"""

    sonarr: SonarrClient = ctx.obj["sonarr"]

    try:
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

        with_season0 = [s for s in monitored if sonarr.has_monitored_season_zero(s)]
        console.print(f"With monitored season 0: {len(with_season0)}")

    except Exception as e:
        console.print(f"[red]✗ Connection error:[/red] {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    cli(obj={})


if __name__ == "__main__":
    main()
