"""
Regression tests for ``config.mode`` resolution.

A list-valued ``mode`` in ``config.yaml`` — the form advertised by
``config.example.yaml``, ``docs/configuration.md`` and ``TAG_MODE.md`` — used to
be wrapped in a nested list by the CLI, so no mode ever matched and the command
reported success with zero work done.  These tests pin the fixed behaviour.

Run:
    .venv/bin/pytest tests/test_modes.py -v
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from extrarrfin.config import Config
from extrarrfin.utils import normalize_modes, resolve_modes

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_cli_module():
    """Load ``extrarrfin.py`` (its name is shadowed by the package)."""
    path = PROJECT_ROOT / "extrarrfin.py"
    spec = importlib.util.spec_from_file_location("extrarrfin_cli_modes", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["extrarrfin_cli_modes"] = module
    spec.loader.exec_module(module)
    return module


cli_module = _load_cli_module()


# ---------------------------------------------------------------------------
# normalize_modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, []),
        ("season0", ["season0"]),
        (["season0", "tag"], ["season0", "tag"]),
        (["theme"], ["theme"]),
        (("season0", "tag"), ["season0", "tag"]),
        ([], []),
        # A doubly-wrapped value must not survive: that nesting was the bug.
        ([["season0", "tag"]], ["season0", "tag"]),
    ],
)
def test_normalize_modes_flattens(value, expected):
    assert normalize_modes(value) == expected


def test_normalize_modes_returns_a_new_list():
    """The result must not alias the config list."""
    source = ["season0", "tag"]
    result = normalize_modes(source)
    result.append("theme")

    assert source == ["season0", "tag"]


# ---------------------------------------------------------------------------
# resolve_modes
# ---------------------------------------------------------------------------


def test_resolve_defaults_to_season0():
    assert resolve_modes() == ["season0"]
    assert resolve_modes(cli_modes=None, config_modes=None) == ["season0"]
    assert resolve_modes(cli_modes=(), config_modes=[]) == ["season0"]


@pytest.mark.parametrize(
    "config_modes,expected",
    [
        ("season0", ["season0"]),
        ("theme", ["theme"]),
        (["season0", "tag"], ["season0", "tag"]),
        (["season0", "tag", "theme"], ["season0", "tag", "theme"]),
    ],
)
def test_resolve_from_config(config_modes, expected):
    assert resolve_modes(config_modes=config_modes) == expected


def test_cli_modes_take_priority_over_config():
    assert resolve_modes(cli_modes=("tag",), config_modes=["season0", "theme"]) == ["tag"]


def test_cli_modes_are_flattened():
    assert resolve_modes(cli_modes=("season0", "theme")) == ["season0", "theme"]


def test_duplicates_are_removed_order_preserved():
    assert resolve_modes(cli_modes=("season0", "season0", "tag")) == ["season0", "tag"]
    assert resolve_modes(config_modes=["tag", "season0", "tag"]) == ["tag", "season0"]


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="unknown mode"):
        resolve_modes(config_modes=["season0", "bogus"])
    with pytest.raises(ValueError, match="unknown mode"):
        resolve_modes(cli_modes=("nope",))


def test_unknown_mode_message_lists_valid_modes():
    with pytest.raises(ValueError, match="season0, tag, theme"):
        resolve_modes(config_modes=["season0", "typo"])


def test_custom_valid_modes_accepted():
    assert resolve_modes(config_modes=["x"], valid_modes=("x", "y")) == ["x"]


# ---------------------------------------------------------------------------
# The original bug, end to end through the CLI
# ---------------------------------------------------------------------------


class _StubDownloader:
    verbose = False


def _counting_handler(bucket: list[str], name: str):
    def _handler(*_args, **_kwargs):
        bucket.append(name)
        return 1, 1, 0

    return _handler


@pytest.fixture()
def invoke_download():
    """Invoke ``download`` with the network layer patched; return its handler calls."""

    def _run(config_modes, extra_args=()):
        bucket: list[str] = []
        cfg = Config(
            sonarr_url="http://localhost:8989",
            sonarr_api_key="key",
            mode=config_modes,
        )
        with patch.object(cli_module, "load_config_from_args", return_value=cfg), \
            patch.object(
                cli_module, "validate_sonarr_connection", return_value=object()
            ), \
            patch.object(
                cli_module,
                "setup_context",
                return_value={
                    "config": cfg,
                    "sonarr": object(),
                    "downloader": _StubDownloader(),
                },
            ), \
            patch.object(
                cli_module,
                "download_season0_mode",
                side_effect=_counting_handler(bucket, "season0"),
            ), \
            patch.object(
                cli_module,
                "download_tag_mode",
                side_effect=_counting_handler(bucket, "tag"),
            ), \
            patch.object(
                cli_module,
                "download_theme_mode",
                side_effect=_counting_handler(bucket, "theme"),
            ):
            result = CliRunner().invoke(
                cli_module.cli, ["download", "--dry-run", *extra_args], obj={}
            )
        return result, bucket

    return _run


def test_list_valued_config_mode_now_runs_both_modes(invoke_download):
    """The regression: this used to run nothing at all and still exit 0."""
    result, bucket = invoke_download(["season0", "tag"])

    assert result.exit_code == 0, result.output
    assert bucket == ["season0", "tag"]


def test_three_modes_from_config_all_run(invoke_download):
    result, bucket = invoke_download(["season0", "tag", "theme"])

    assert result.exit_code == 0, result.output
    assert bucket == ["season0", "tag", "theme"]


def test_single_item_list_mode_runs(invoke_download):
    result, bucket = invoke_download(["theme"])

    assert result.exit_code == 0, result.output
    assert bucket == ["theme"]


def test_string_config_mode_still_works(invoke_download):
    """The previously-working shape must be untouched."""
    result, bucket = invoke_download("season0")

    assert result.exit_code == 0, result.output
    assert bucket == ["season0"]


def test_cli_mode_overrides_list_config(invoke_download):
    result, bucket = invoke_download(["season0", "tag"], extra_args=["--mode", "theme"])

    assert result.exit_code == 0, result.output
    assert bucket == ["theme"]


def test_unknown_mode_in_config_fails_loudly(invoke_download):
    """A typo must not silently do nothing anymore."""
    result, bucket = invoke_download(["season0", "typo"])

    assert result.exit_code != 0
    assert bucket == []
    assert "unknown mode" in result.output.lower()


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config_modes,expected",
    [
        (["season0", "tag"], ["season0", "tag"]),
        ("season0", ["season0"]),
        (["season0", "theme"], ["season0"]),
    ],
)
def test_list_command_receives_flattened_modes(config_modes, expected):
    """The modes handed to list_command() must be plain strings.

    ``["season0", "theme"]`` also checks that the theme branch strips itself
    and forwards only the remaining modes.
    """
    forwarded: list = []
    cfg = Config(
        sonarr_url="http://localhost:8989", sonarr_api_key="key", mode=config_modes
    )

    def _capture(_config, _sonarr, _downloader, _radarr, _limit, modes=None):
        forwarded.append(list(modes) if isinstance(modes, (list, tuple)) else modes)

    with patch.object(cli_module, "load_config_from_args", return_value=cfg), \
        patch.object(cli_module, "validate_sonarr_connection", return_value=object()), \
        patch.object(
            cli_module,
            "setup_context",
            return_value={
                "config": cfg,
                "sonarr": object(),
                "downloader": _StubDownloader(),
            },
        ), \
        patch.object(cli_module, "list_command", side_effect=_capture), \
        patch.object(cli_module, "list_themes", side_effect=lambda *_a, **_k: None):
        result = CliRunner().invoke(cli_module.cli, ["list"], obj={})

    assert result.exit_code == 0, result.output
    assert forwarded == [expected], forwarded


def test_theme_only_config_mode_uses_list_themes_only():
    forwarded: list = []
    cfg = Config(
        sonarr_url="http://localhost:8989", sonarr_api_key="key", mode=["theme"]
    )

    with patch.object(cli_module, "load_config_from_args", return_value=cfg), \
        patch.object(cli_module, "validate_sonarr_connection", return_value=object()), \
        patch.object(
            cli_module,
            "setup_context",
            return_value={
                "config": cfg,
                "sonarr": object(),
                "downloader": _StubDownloader(),
            },
        ), \
        patch.object(
            cli_module,
            "list_command",
            side_effect=lambda *a, **k: forwarded.append("list_command"),
        ), \
        patch.object(
            cli_module,
            "list_themes",
            side_effect=lambda *a, **k: forwarded.append("list_themes"),
        ):
        result = CliRunner().invoke(cli_module.cli, ["list"], obj={})

    assert result.exit_code == 0, result.output
    assert forwarded == ["list_themes"]


def test_list_command_module_uses_shared_resolver():
    """list_command() must no longer carry its own copy of the logic."""
    source = (
        PROJECT_ROOT / "extrarrfin" / "commands" / "list_command.py"
    ).read_text(encoding="utf-8")

    assert "resolve_modes" in source
    assert "isinstance(config.mode, list)" not in source


def test_cli_no_longer_contains_the_dead_tuple_check():
    source = (PROJECT_ROOT / "extrarrfin.py").read_text(encoding="utf-8")

    assert "isinstance(config.mode, tuple)" not in source
