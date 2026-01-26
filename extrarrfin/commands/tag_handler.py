"""
Tag mode handler - Download behind the scenes videos for tagged series
"""

import logging
import time

import yt_dlp
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from extrarrfin.config import Config
from extrarrfin.downloader import Downloader
from extrarrfin.models import Series
from extrarrfin.sonarr import SonarrClient

logger = logging.getLogger(__name__)
console = Console()


def download_tag_mode(
    config: Config,
    sonarr: SonarrClient,
    downloader: Downloader,
    limit: str = None,
    dry_run: bool = False,
    force: bool = False,
    no_scan: bool = False,
    verbose: bool = False,
):
    """
    Download behind the scenes videos for series with want-extras tag

    Args:
        config: Configuration object
        sonarr: Sonarr client
        downloader: Downloader instance
        limit: Optional series name or ID to limit downloads
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

    # Fetch series with tag
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

    # Apply limit filter if specified
    if limit:
        if limit.isdigit():
            tagged_series = [s for s in tagged_series if s.id == int(limit)]
        else:
            tagged_series = [
                s for s in tagged_series if limit.lower() in s.title.lower()
            ]

    if not tagged_series:
        console.print("[yellow]No series with 'want-extras' tag found[/yellow]")
        return total_downloads, successful_downloads, failed_downloads

    # Process each series
    for series in tagged_series:
        console.print(f"\n[bold cyan]Processing:[/bold cyan] {series.title}")

        t, s, f = _download_series_extras(
            series, config, sonarr, downloader, dry_run, force, no_scan, verbose
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
    console.print(f"  [blue]Searching for behind the scenes videos...[/blue]")
    video_urls = downloader.search_youtube_behind_scenes(series)

    if not video_urls:
        console.print(f"  [yellow]No behind the scenes videos found[/yellow]")
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

        # Retry logic for 403 errors
        max_retries = 3
        retry_delay = 3  # seconds
        download_success = False
        last_error = None

        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(video_info["url"], download=True)

                # Create .nfo file with video metadata
                nfo_path = output_dir / f"{base_filename}.nfo"
                with open(nfo_path, "w", encoding="utf-8") as nfo:
                    nfo.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n')
                    nfo.write("<movie>\n")
                    nfo.write(f"  <title>{video_info['title']}</title>\n")
                    nfo.write(f"  <originaltitle>{video_info['title']}</originaltitle>\n")
                    nfo.write(f"  <plot>{video_info.get('description', '')}</plot>\n")
                    nfo.write(f"  <studio>{video_info.get('channel', '')}</studio>\n")
                    nfo.write(f"  <director>{video_info.get('uploader', '')}</director>\n")
                    nfo.write(f"  <source>YouTube</source>\n")
                    nfo.write(f"  <id>{video_info['id']}</id>\n")
                    nfo.write(f"  <youtubeurl>{video_info['url']}</youtubeurl>\n")
                    if video_info.get("duration"):
                        nfo.write(f"  <runtime>{video_info['duration'] // 60}</runtime>\n")
                    nfo.write("</movie>\n")

                console.print(f"    [green]✓ Downloaded {video_title}[/green]")
                successful_downloads += 1
                download_success = True
                break  # Success, exit retry loop

            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if it's a 403 error
                if "403" in error_str or "forbidden" in error_str:
                    if attempt < max_retries - 1:  # Not the last attempt
                        console.print(
                            f"    [yellow]⚠ HTTP 403 error, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})[/yellow]"
                        )
                        time.sleep(retry_delay)
                        continue
                    else:
                        console.print(f"    [red]✗ Failed after {max_retries} attempts:[/red] {e}")
                else:
                    # Not a 403 error, don't retry
                    console.print(f"    [red]✗ Failed:[/red] {e}")
                    break

        if not download_success:
            failed_downloads += 1

    # Trigger Sonarr scan if requested
    if not dry_run and not no_scan and successful_downloads > 0:
        try:
            console.print(f"  [blue]Scanning Sonarr...[/blue]")
            sonarr.rescan_series(series.id)
            console.print(f"    [green]✓ Scan triggered[/green]")
        except Exception as e:
            console.print(f"    [red]Scan error:[/red] {e}")

    return total_downloads, successful_downloads, failed_downloads
