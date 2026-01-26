"""Test command to verify Sonarr and Jellyfin connections"""

import sys

from rich.console import Console

from ..config import Config
from ..jellyfin import JellyfinClient
from ..sonarr import SonarrClient

console = Console()


def test_command(
    config: Config,
    sonarr: SonarrClient,
    jellyfin_url: str | None,
    jellyfin_api_key: str | None,
):
    """Test connection to Sonarr and Jellyfin

    Args:
        config: Application configuration
        sonarr: Sonarr API client
        jellyfin_url: Jellyfin server URL (overrides config)
        jellyfin_api_key: Jellyfin API key (overrides config)
    """
    try:
        console.print("[bold]Testing Sonarr connection...[/bold]")
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
