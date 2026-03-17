"""
Theme mode handler - Download musical themes for series and movies
"""

import logging

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.radarr import RadarrClient
from extrarrfin.sonarr import SonarrClient

logger = logging.getLogger(__name__)
console = Console()


def _series_has_content(series) -> bool:
    """Return True if the series has at least one downloaded episode file."""
    return any(s.statistics.get("episodeFileCount", 0) > 0 for s in series.seasons)


def download_theme_mode(
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    radarr: RadarrClient | None = None,
    limit: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False,
):
    """
    Download musical themes (theme.mp3) for all series and movies.

    Sources are tried in order for each title:
      1. ThemerrDB — direct lookup by TVDB/TMDB ID
      2. TelevisionTunes — web search + MP3 download
      3. YouTube — scored yt-dlp search (fallback)

    Saves the result as theme.mp3 in the root folder of each series/movie.
    Skips entries where theme.mp3 already exists.

    Returns:
        Tuple of (total, successful, failed)
    """
    total = 0
    successful = 0
    failed = 0

    # ------------------------------------------------------------------ series
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching series from Sonarr…", total=None)
        all_series = sonarr.get_all_series()
        progress.update(task, completed=True)

    if limit:
        if limit.isdigit():
            limit_id = int(limit)
            all_series = [s for s in all_series if s.id == limit_id]
        else:
            limit_lower = limit.lower()
            all_series = [s for s in all_series if limit_lower in s.title.lower()]

    # Only process series that have at least one downloaded episode
    all_series = [s for s in all_series if _series_has_content(s)]

    for series in all_series:
        total += 1
        root_dir = downloader.get_series_root_directory(
            series, config.media_directory, config.sonarr_directory
        )
        theme_file = root_dir / "theme.mp3"

        if theme_file.exists() and not force:
            if verbose:
                console.print(
                    f"[dim]Skipping {series.title} (theme.mp3 already exists)[/dim]"
                )
            successful += 1
            continue

        console.print(
            f"[bold cyan]Downloading theme:[/bold cyan] {series.title}  "
            f"[dim]→ {root_dir}[/dim]"
        )

        ok, path, err = downloader.download_theme(
            series.title,
            root_dir,
            dry_run=dry_run,
            force=force,
            year=series.year,
            tvdb_id=series.tvdb_id,
            network=series.network,
        )

        if ok:
            if dry_run:
                console.print(f"  [yellow]DRY RUN:[/yellow] Would save to {path}")
            else:
                console.print(f"  [green]✓ Saved to {path}[/green]")
            successful += 1
        else:
            console.print(f"  [red]✗ Failed:[/red] {err}")
            failed += 1

    # ------------------------------------------------------------------ movies
    if radarr:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching movies from Radarr…", total=None)
            all_movies = radarr.get_all_movies()
            progress.update(task, completed=True)

        if limit:
            if limit.isdigit():
                limit_id = int(limit)
                all_movies = [m for m in all_movies if m.id == limit_id]
            else:
                limit_lower = limit.lower()
                all_movies = [m for m in all_movies if limit_lower in m.title.lower()]

        # Only process movies that have a downloaded file
        all_movies = [m for m in all_movies if m.has_file]

        for movie in all_movies:
            total += 1
            root_dir = downloader.get_movie_root_directory(
                movie, config.media_directory, config.radarr_directory
            )
            theme_file = root_dir / "theme.mp3"

            if theme_file.exists() and not force:
                if verbose:
                    console.print(
                        f"[dim]Skipping {movie.title} (theme.mp3 already exists)[/dim]"
                    )
                successful += 1
                continue

            console.print(
                f"[bold cyan]Downloading theme:[/bold cyan] {movie.title}  "
                f"[dim]→ {root_dir}[/dim]"
            )

            ok, path, err = downloader.download_theme(
                movie.title,
                root_dir,
                dry_run=dry_run,
                force=force,
                year=movie.year,
                tmdb_id=movie.tmdb_id,
                network=movie.studio,
            )

            if ok:
                if dry_run:
                    console.print(f"  [yellow]DRY RUN:[/yellow] Would save to {path}")
                else:
                    console.print(f"  [green]✓ Saved to {path}[/green]")
                successful += 1
            else:
                console.print(f"  [red]✗ Failed:[/red] {err}")
                failed += 1

    return total, successful, failed
