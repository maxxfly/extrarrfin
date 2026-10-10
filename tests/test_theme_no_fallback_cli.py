"""
Offline tests for the ``--no-fallback`` CLI wiring.

The CLI entry point lives in ``extrarrfin.py`` at the project root, which is
shadowed by the ``extrarrfin/`` package, so it is loaded explicitly from its
file path.  Every network touch point (config loading, Sonarr validation) is
patched, so these tests need no server and no internet.

Two things are verified:
  * the flag is advertised by the commands that resolve themes, and only by
    those;
  * the flag reaches ``download_theme_mode(no_fallback=...)``.

Run:
    .venv/bin/pytest tests/test_theme_no_fallback_cli.py -v
"""

import importlib.util
import inspect
import sys
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from extrarrfin.config import Config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_cli_module():
    """Load ``extrarrfin.py`` as a module distinct from the ``extrarrfin`` pkg."""
    path = PROJECT_ROOT / "extrarrfin.py"
    spec = importlib.util.spec_from_file_location("extrarrfin_cli", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["extrarrfin_cli"] = module
    spec.loader.exec_module(module)
    return module


cli_module = _load_cli_module()

CONFIG = Config(sonarr_url="http://localhost:8989", sonarr_api_key="key")


class _StubDownloader:
    """Enough of a Downloader for the CLI to set ``verbose`` on it."""

    verbose = False


@pytest.fixture()
def runner():
    return CliRunner()


def _command(name: str) -> click.Command:
    return cli_module.cli.commands[name]


def _options(command: click.Command) -> dict[str, click.Option]:
    return {
        p.name: p for p in command.params if isinstance(p, click.Option) and p.name
    }


# ---------------------------------------------------------------------------
# Flag presence (pure introspection, no invocation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command_name", ["theme", "download", "schedule-mode"])
def test_no_fallback_option_exists(command_name: str):
    assert "no_fallback" in _options(_command(command_name))


@pytest.mark.parametrize("command_name", ["theme", "download", "schedule-mode"])
def test_no_fallback_is_a_boolean_flag(command_name: str):
    command = _command(command_name)
    option = _options(command)["no_fallback"]

    assert option.is_flag is True
    # ``option.default`` is an implementation detail: click 8.5 replaced the
    # False default of flags with a Sentinel whose ``bool()`` is True.
    # ``get_default`` is the public API and resolves to False on every version.
    assert option.get_default(click.Context(command)) is False


@pytest.mark.parametrize("command_name", ["theme", "download", "schedule-mode"])
def test_no_fallback_help_mentions_curated_sources(command_name: str):
    option = _options(_command(command_name))["no_fallback"]
    help_text = option.help or ""

    assert "ThemerrDB" in help_text
    assert "TelevisionTunes" in help_text
    assert "YouTube" in help_text


@pytest.mark.parametrize("command_name", ["list-themes", "list", "scan", "test"])
def test_unrelated_commands_do_not_advertise_the_flag(command_name: str):
    assert "no_fallback" not in _options(_command(command_name))


@pytest.mark.parametrize("command_name", ["theme", "download", "schedule-mode"])
def test_callback_signature_accepts_no_fallback(command_name: str):
    """Guard against ctx.invoke() passing a kwarg the callback cannot take."""
    callback = _command(command_name).callback
    assert callback is not None

    assert "no_fallback" in inspect.signature(callback).parameters


# ---------------------------------------------------------------------------
# Invocation helpers
# ---------------------------------------------------------------------------


def _invoke(runner, args, extra_patches, config=None):
    """Invoke the CLI with config/sonarr validation neutralised."""
    cfg = config or CONFIG
    ctx_data = {
        "config": cfg,
        "sonarr": object(),
        "downloader": _StubDownloader(),
    }
    patches = [
        patch.object(cli_module, "load_config_from_args", return_value=cfg),
        patch.object(cli_module, "validate_sonarr_connection", return_value=object()),
        patch.object(cli_module, "setup_context", return_value=ctx_data),
    ]
    for p in patches:
        p.start()
    try:
        for p in extra_patches:
            p.start()
        result = runner.invoke(cli_module.cli, args, obj={})
    finally:
        for p in reversed(extra_patches):
            p.stop()
        for p in reversed(patches):
            p.stop()
    return result


@pytest.fixture()
def theme_handler():
    """Patch download_theme_mode and capture its kwargs."""
    calls: list[dict] = []

    def _handler(*_args, **kwargs):
        calls.append(kwargs)
        return 1, 1, 0

    calls_handler = _handler
    calls_handler.calls = calls  # type: ignore[attr-defined]
    with patch.object(cli_module, "download_theme_mode", side_effect=_handler):
        yield calls_handler


# ---------------------------------------------------------------------------
# Flag propagation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flag", [True, False])
def test_theme_command_forwards_no_fallback(runner, theme_handler, flag):
    args = ["theme", "--dry-run"] + (["--no-fallback"] if flag else [])

    result = _invoke(runner, args, [])

    assert result.exit_code == 0, result.output
    assert len(theme_handler.calls) == 1  # type: ignore[attr-defined]
    assert theme_handler.calls[0]["no_fallback"] is flag  # type: ignore[attr-defined]


@pytest.mark.parametrize("flag", [True, False])
def test_download_command_forwards_no_fallback(runner, theme_handler, flag):
    args = ["download", "--mode", "theme", "--dry-run"] + (
        ["--no-fallback"] if flag else []
    )

    patch_season0 = patch.object(cli_module, "download_season0_mode", return_value=(0, 0, 0))
    result = _invoke(runner, args, [patch_season0])

    assert result.exit_code == 0, result.output
    assert len(theme_handler.calls) == 1  # type: ignore[attr-defined]
    assert theme_handler.calls[0]["no_fallback"] is flag  # type: ignore[attr-defined]


def test_theme_command_announces_curated_only_mode(runner, theme_handler):
    result = _invoke(runner, ["theme", "--dry-run", "--no-fallback"], [])

    assert result.exit_code == 0, result.output
    assert "YouTube fallback disabled" in result.output


def test_theme_command_stays_quiet_without_the_flag(runner, theme_handler):
    result = _invoke(runner, ["theme", "--dry-run"], [])

    assert result.exit_code == 0, result.output
    assert "YouTube fallback disabled" not in result.output


def test_download_command_announces_curated_only_mode(runner, theme_handler):
    patch_season0 = patch.object(cli_module, "download_season0_mode", return_value=(0, 0, 0))
    result = _invoke(
        runner,
        ["download", "--mode", "theme", "--dry-run", "--no-fallback"],
        [patch_season0],
    )

    assert result.exit_code == 0, result.output
    assert "YouTube fallback disabled" in result.output


def test_theme_command_still_reports_the_summary(runner, theme_handler):
    result = _invoke(runner, ["theme", "--dry-run", "--no-fallback"], [])

    assert result.exit_code == 0, result.output
    assert "Theme download summary" in result.output


# ---------------------------------------------------------------------------
# schedule-mode: the flag must reach the download it invokes
# ---------------------------------------------------------------------------


def test_schedule_mode_forwards_no_fallback_to_download(runner, theme_handler):
    """schedule-mode runs its first job immediately; the flag must survive the
    ctx.invoke(download, ...) hop and reach download_theme_mode.

    schedule-mode has no ``--mode`` option, so the theme branch is driven by
    ``config.mode``.  ``schedule.run_pending`` raises KeyboardInterrupt to stop
    the command's ``while True`` loop right after that first job.
    """
    # NOTE: a list-valued ``mode`` in config.yaml is mis-handled by the
    # download command (it yields [["theme"]] and no mode runs). That is a
    # pre-existing bug unrelated to --no-fallback, so the string form is used
    # here.
    schedule_config = Config(
        sonarr_url="http://localhost:8989",
        sonarr_api_key="key",
        mode="theme",
    )
    patch_run_pending = patch.object(
        cli_module.schedule, "run_pending", side_effect=KeyboardInterrupt
    )

    result = _invoke(
        runner,
        [
            "schedule-mode",
            "--interval",
            "1",
            "--unit",
            "hours",
            "--dry-run",
            "--no-fallback",
        ],
        [patch_run_pending],
        config=schedule_config,
    )

    assert result.exit_code == 0, result.output or repr(result.exception)
    # The immediate run reached the theme handler through the download command.
    assert len(theme_handler.calls) == 1  # type: ignore[attr-defined]
    assert theme_handler.calls[0]["no_fallback"] is True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Argument parsing sanity
# ---------------------------------------------------------------------------


def test_misspelled_flag_is_rejected(runner, theme_handler):
    result = _invoke(runner, ["theme", "--no-falllback"], [])

    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_flag_cannot_take_a_value(runner, theme_handler):
    result = _invoke(runner, ["theme", "--no-fallback=true"], [])

    assert result.exit_code != 0
