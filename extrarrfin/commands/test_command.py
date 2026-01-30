"""Test command to verify Sonarr, Radarr and Jellyfin connections"""

import sys

from rich.console import Console

from ..config import Config
from ..jellyfin import JellyfinClient
from ..radarr import RadarrClient
from ..sonarr import SonarrClient

console = Console()


def test_command(
    config: Config,
    sonarr: SonarrClient,
    radarr: RadarrClient | None,
    jellyfin_url: str | None,
    jellyfin_api_key: str | None,
):
    """Test connection to Sonarr, Radarr (if configured) and Jellyfin

    Args:
        config: Application configuration
        sonarr: Sonarr API client
        radarr: Radarr API client (optional)
        jellyfin_url: Jellyfin server URL (overrides config)
        jellyfin_api_key: Jellyfin API key (overrides config)
    """
    try:
        console.print("[bold]Testing Sonarr connection...[/bold]")
        console.print(f"URL: {config.sonarr_url}")

        series = sonarr.get_all_series()
        console.print("[green]✓ Connection successful![/green]")
        console.print(f"Number of series: {len(series)}")

        monitored = [s for s in series if s.monitored]
        console.print(f"Monitored series: {len(monitored)}")

        with_season0 = [
            s for s in monitored if sonarr.has_monitored_season_zero_episodes(s)
        ]
        console.print(f"With monitored season 0 episodes: {len(with_season0)}")

        with_tag = [s for s in monitored if sonarr.has_want_extras_tag(s)]
        console.print(f"With want-extras tag: {len(with_tag)}")

        # Test Radarr connection if configured
        if radarr:
            console.print("\n[bold]Testing Radarr connection...[/bold]")
            console.print(f"URL: {config.radarr_url}")

            try:
                movies = radarr.get_all_movies()
                console.print("[green]✓ Connection successful![/green]")
                console.print(f"Number of movies: {len(movies)}")

                monitored_movies = [m for m in movies if m.monitored]
                console.print(f"Monitored movies: {len(monitored_movies)}")

                movies_with_tag = [
                    m for m in monitored_movies if radarr.has_want_extras_tag(m)
                ]
                console.print(f"With want-extras tag: {len(movies_with_tag)}")
            except Exception as e:
                console.print(f"[red]✗ Radarr connection error:[/red] {e}")
        else:
            console.print("\n[dim]Radarr not configured (skipping test)[/dim]")

        # Test Jellyfin connection if configured
        jf_url = jellyfin_url or config.jellyfin_url
        jf_api_key = jellyfin_api_key or config.jellyfin_api_key

        if jf_url and jf_api_key:
            console.print("\n[bold]Testing Jellyfin connection...[/bold]")
            console.print(f"URL: {jf_url}")

            try:
                jellyfin = JellyfinClient(jf_url, jf_api_key)
                if jellyfin.test_connection():
                    console.print("[green]✓ Jellyfin connection successful![/green]")
                else:
                    console.print("[red]✗ Jellyfin connection failed[/red]")
            except Exception as e:
                console.print(f"[red]✗ Jellyfin connection error:[/red] {e}")
        else:
            console.print("\n[dim]Jellyfin not configured (skipping test)[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Connection error:[/red] {e}")
        sys.exit(1)
