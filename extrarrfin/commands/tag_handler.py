"""
Tag mode handler - Download behind the scenes videos for tagged series and movies
"""

import logging
import time

import yt_dlp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.models import Movie, Series
from extrarrfin.radarr import RadarrClient
from extrarrfin.sonarr import SonarrClient

logger = logging.getLogger(__name__)
console = Console()


def download_tag_mode(
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    radarr: RadarrClient | None = None,
    limit: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    no_scan: bool = False,
    verbose: bool = False,
):
    """
    Download behind the scenes videos for series and movies with want-extras tag

    Args:
        config: Configuration object
        sonarr: Sonarr client
        downloader: Downloader instance
        radarr: Optional Radarr client
        limit: Optional series/movie name or ID to limit downloads
        dry_run: If True, don't actually download
        force: If True, re-download even if file exists
        no_scan: If True, don't trigger Sonarr/Radarr scan
        verbose: If True, show detailed info

    Returns:
        Tuple of (total_downloads, successful_downloads, failed_downloads)
    """
    total_downloads = 0
    successful_downloads = 0
    failed_downloads = 0

    # Fetch series with tag from Sonarr
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Fetching tagged series...", total=None)
        series_list = sonarr.get_monitored_series()
        progress.update(task, completed=True)

    # Filter for series with the "want-extras" tag
    tagged_series = [s for s in series_list if sonarr.has_want_extras_tag(s)]

    # Fetch movies with tag from Radarr (if configured)
    tagged_movies = []
    if radarr:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching tagged movies...", total=None)
            movie_list = radarr.get_monitored_movies()
            progress.update(task, completed=True)

        # Filter for movies with the "want-extras" tag
        tagged_movies = [m for m in movie_list if radarr.has_want_extras_tag(m)]

    # Apply limit filter if specified
    if limit:
        if limit.isdigit():
            limit_id = int(limit)
            tagged_series = [s for s in tagged_series if s.id == limit_id]
            tagged_movies = [m for m in tagged_movies if m.id == limit_id]
        else:
            limit_lower = limit.lower()
            tagged_series = [s for s in tagged_series if limit_lower in s.title.lower()]
            tagged_movies = [m for m in tagged_movies if limit_lower in m.title.lower()]

    if not tagged_series and not tagged_movies:
        console.print(
            "[yellow]No series or movies with 'want-extras' tag found[/yellow]"
        )
        return total_downloads, successful_downloads, failed_downloads

    # Process each series
    for series in tagged_series:
        console.print(f"\n[bold cyan]Processing Series:[/bold cyan] {series.title}")

        t, s, f = _download_series_extras(
            series, config, sonarr, downloader, dry_run, force, no_scan, verbose
        )
        total_downloads += t
        successful_downloads += s
        failed_downloads += f

    # Process each movie
    for movie in tagged_movies:
        console.print(f"\n[bold cyan]Processing Movie:[/bold cyan] {movie.title}")

        t, s, f = _download_movie_extras(
            movie, config, radarr, downloader, dry_run, force, no_scan, verbose
        )
        total_downloads += t
        successful_downloads += s
        failed_downloads += f

    return total_downloads, successful_downloads, failed_downloads


def _download_series_extras(
    series: Series,
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    dry_run: bool = False,
    force: bool = False,
    no_scan: bool = False,
    verbose: bool = False,
):
    """
    Download behind the scenes videos for a single series

    Args:
        series: The series to process
        config: Configuration object
        sonarr: Sonarr client
        downloader: Downloader instance
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

    # Get output directory for extras
    try:
        output_dir = downloader.get_extras_directory(
            series, config.media_directory, config.sonarr_directory
        )
        console.print(f"  [dim]Directory:[/dim] {output_dir}")
    except Exception as e:
        console.print(f"  [red]Error:[/red] {e}")
        return total_downloads, successful_downloads, failed_downloads

    # Search for behind the scenes videos
    console.print("  [blue]Searching for behind the scenes videos...[/blue]")
    video_urls = downloader.search_youtube_behind_scenes(series)

    if not video_urls:
        console.print("  [yellow]No behind the scenes videos found[/yellow]")
        return total_downloads, successful_downloads, failed_downloads

    console.print(f"  [green]Found {len(video_urls)} videos[/green]")

    # Download each video
    for idx, video_info in enumerate(video_urls, 1):
        total_downloads += 1

        # Use YouTube video title as the filename
        series_name = downloader.sanitize_filename(series.title)
        video_title = downloader.sanitize_filename(video_info["title"])
        base_filename = f"{series_name} - {video_title}"

        # Check if file already exists
        existing_files = [f for f in output_dir.glob(f"{base_filename}.*")]
        if existing_files and not force:
            console.print(f"    [dim]{video_title} already exists, skipping[/dim]")
            successful_downloads += 1
            continue

        if dry_run:
            console.print(f"  [yellow]DRY RUN:[/yellow] Would download {video_title}")
            successful_downloads += 1
            continue

        console.print(f"  [blue]Downloading {video_title}...[/blue]")

        # Download using yt-dlp directly with retry logic for 403 errors
        output_template = str(output_dir / f"{base_filename}.%(ext)s")

        ydl_opts = {
            "format": downloader.format_string,
            "outtmpl": output_template,
            "quiet": not verbose,
            "no_warnings": not verbose,
            "sleep_interval": 2,
            "sleep_requests": 1,
            "sleep_subtitles": 1,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": downloader.subtitle_languages,
            "allsubtitles": downloader.download_all_subtitles,
            "subtitlesformat": "srt",
            "ignoreerrors": True,
            "postprocessors": [
                {
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                },
                {
                    "key": "FFmpegEmbedSubtitle",
                    "already_have_subtitle": False,
                },
            ],
        }

        # Retry logic for 403 errors with exponential backoff
        max_retries = 5
        base_delay = 2  # Base delay in seconds
        download_success = False

        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(video_info["url"], download=True)

                # Create .nfo file using centralized function
                downloader.create_nfo_file(
                    base_filename, output_dir, video_info, nfo_type="movie"
                )

                console.print(f"    [green]✓ Downloaded {video_title}[/green]")
                successful_downloads += 1
                download_success = True
                break  # Success, exit retry loop

            except Exception as e:
                error_str = str(e).lower()

                # Check if it's a 403 or 429 error (quota/rate limiting)
                if (
                    "403" in error_str
                    or "forbidden" in error_str
                    or "429" in error_str
                    or "too many" in error_str
                ):
                    if attempt < max_retries - 1:  # Not the last attempt
                        # Exponential backoff: 2s, 4s, 8s, 16s...
                        delay = base_delay * (2**attempt)
                        console.print(
                            f"    [yellow]⚠ Rate limit error, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})[/yellow]"
                        )
                        time.sleep(delay)
                        continue
                    else:
                        console.print(
                            f"    [red]✗ Failed after {max_retries} attempts:[/red] {e}"
                        )
                else:
                    # Not a rate limit error, don't retry
                    console.print(f"    [red]✗ Failed:[/red] {e}")
                    break

        if not download_success:
            failed_downloads += 1

    # Trigger Sonarr scan if requested
    if not dry_run and not no_scan and successful_downloads > 0:
        try:
            console.print("  [blue]Scanning Sonarr...[/blue]")
            sonarr.rescan_series(series.id)
            console.print("    [green]✓ Scan triggered[/green]")
        except Exception as e:
            console.print(f"    [red]Scan error:[/red] {e}")

    return total_downloads, successful_downloads, failed_downloads


def _download_movie_extras(
    movie: Movie,
    config: Config,
    radarr: RadarrClient,
    downloader: Downloader,
    dry_run: bool = False,
    force: bool = False,
    no_scan: bool = False,
    verbose: bool = False,
):
    """Download behind the scenes extras for a movie"""
    total_downloads = 0
    successful_downloads = 0
    failed_downloads = 0

    # Get output directory
    output_dir = downloader.get_movie_directory(
        movie,
        media_directory=config.media_directory,
        radarr_directory=config.radarr_directory,
    )

    console.print(f"  [dim]Directory:[/dim] {output_dir}")

    # Search terms for behind the scenes content
    search_terms = [
        "behind the scenes",
        "making of",
        "featurette",
        "interviews",
        "deleted scenes",
        "bloopers",
    ]

    for search_term in search_terms:
        query = f"{movie.title} {search_term}"
        console.print(f"\n  [blue]Searching:[/blue] '{query}'")

        # Search for the video
        video_info = downloader.search_youtube_for_extras(query, movie.title, verbose)

        if not video_info:
            console.print(f"    [yellow]✗ No video found[/yellow]")
            continue

        total_downloads += 1

        # Build filename
        base_filename = downloader.build_movie_extras_filename(
            movie, video_info.get("title", search_term)
        )
        file_path = None

        if dry_run:
            console.print(
                f"    [yellow]DRY RUN:[/yellow] Would download: {base_filename}"
            )
            console.print(f"    [dim]Video:[/dim] {video_info.get('title')}")
            successful_downloads += 1
            continue

        # Check if file already exists
        if not force:
            existing_files = list(output_dir.glob(f"{base_filename}.*"))
            if existing_files:
                console.print(
                    f"    [yellow]✓ Already exists:[/yellow] {existing_files[0].name}"
                )
                continue

        # Retry logic for rate limiting
        max_retries = 5
        base_delay = 2
        download_success = False

        # Get YouTube URL from video_info
        youtube_url = video_info.get("webpage_url") or video_info.get("url")

        if not youtube_url:
            console.print(f"    [red]✗ Failed:[/red] No YouTube URL found")
            failed_downloads += 1
            continue

        # Use the downloader's download_video_from_url method
        success, file_path, error, info = downloader.download_video_from_url(
            youtube_url, base_filename, output_dir, force=force, dry_run=dry_run
        )

        if success:
            console.print(f"    [green]✓ Downloaded:[/green] {file_path}")

            # Create NFO file
            try:
                from pathlib import Path

                file_path_obj = Path(file_path)
                base_fn = file_path_obj.stem
                downloader.create_nfo_file(
                    base_fn, output_dir, video_info, nfo_type="movie"
                )
            except Exception as e:
                console.print(f"    [yellow]⚠ NFO creation warning:[/yellow] {e}")

            successful_downloads += 1
        else:
            # Check if it's a rate limit error
            error_str = str(error).lower() if error else ""

            if (
                "403" in error_str
                or "forbidden" in error_str
                or "429" in error_str
                or "too many" in error_str
            ):
                console.print(f"    [yellow]⚠ Rate limit reached[/yellow]")
            else:
                console.print(f"    [red]✗ Failed:[/red] {error}")

            failed_downloads += 1

    # Trigger Radarr scan if requested
    if not dry_run and not no_scan and successful_downloads > 0:
        try:
            console.print("  [blue]Scanning Radarr...[/blue]")
            radarr.rescan_movie(movie.id)
            console.print("    [green]✓ Scan triggered[/green]")
        except Exception as e:
            console.print(f"    [red]Scan error:[/red] {e}")

    return total_downloads, successful_downloads, failed_downloads
