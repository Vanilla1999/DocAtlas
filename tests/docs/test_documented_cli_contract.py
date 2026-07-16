from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re
import shlex

import click
import pytest

from docmancer.cli.__main__ import cli


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_COMMAND_DOCS = (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "SKILL.md",
    ROOT / ".github" / "copilot-instructions.md",
    *sorted((ROOT / "docs").glob("*.md")),
    *sorted((ROOT / "wiki").glob("*.md")),
)
SHELL_FENCE_RE = re.compile(r"```(?:bash|console|sh|shell)\s*\n(.*?)```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`([^`\n]*\bdoc-atlas\b[^`\n]*)`")
DIRECT_COMMAND_RE = re.compile(r"^\s*doc-atlas(?:\s|$)")
BRACED_COMMAND_RE = re.compile(r"^\{([^{}]+)\}$")


def _documented_commands(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    commands: list[str] = []

    for snippet in INLINE_CODE_RE.findall(text):
        snippet = snippet.strip()
        if DIRECT_COMMAND_RE.match(snippet):
            commands.append(snippet)

    for block in SHELL_FENCE_RE.findall(text):
        for line in block.splitlines():
            line = line.strip()
            if DIRECT_COMMAND_RE.match(line):
                commands.append(line.rstrip(" \\"))

    return sorted(set(commands))


def _clean_token(token: str) -> str:
    return token.strip("[](),.;:")


def _option_names(command: click.Command) -> set[str]:
    names: set[str] = {"--help"}
    for parameter in command.params:
        if isinstance(parameter, click.Option):
            names.update(parameter.opts)
            names.update(parameter.secondary_opts)
    return names


def _command_variants(tokens: list[str]) -> Iterable[list[str]]:
    for index, token in enumerate(tokens):
        match = BRACED_COMMAND_RE.match(_clean_token(token))
        if match:
            for value in match.group(1).split(","):
                yield tokens[:index] + [value.strip()] + tokens[index + 1 :]
            return
    yield tokens


def _assert_documented_command(command_line: str, source: Path) -> None:
    try:
        tokens = shlex.split(command_line, comments=True)
    except ValueError as exc:
        raise AssertionError(f"{source}: cannot parse {command_line!r}: {exc}") from exc

    assert tokens and tokens[0] == "doc-atlas", f"{source}: invalid command {command_line!r}"
    if len(tokens) == 1:
        return

    for variant in _command_variants(tokens[1:]):
        current: click.Command = cli
        command_path = ["doc-atlas"]
        option_owners: list[click.Command] = [cli]

        for raw_token in variant:
            token = _clean_token(raw_token)
            if not token or token in {"...", "…", "\\"}:
                continue
            if token.startswith("<") or token.startswith("{"):
                if isinstance(current, click.Group):
                    break
                continue
            if token.startswith("-"):
                option = token.split("=", maxsplit=1)[0]
                available = set().union(*(_option_names(owner) for owner in option_owners))
                assert option in available, (
                    f"{source}: {option!r} is not exposed by {' '.join(command_path)!r} "
                    f"in {command_line!r}"
                )
                continue
            if isinstance(current, click.Group) and token in current.commands:
                current = current.commands[token]
                command_path.append(token)
                option_owners.append(current)
                continue
            if isinstance(current, click.Group):
                raise AssertionError(
                    f"{source}: {' '.join(command_path + [token])!r} is not exposed in --help "
                    f"for {command_line!r}"
                )
            # The first non-option token after a leaf command is an argument.
            continue


def test_every_documented_doc_atlas_command_exists_in_click_help() -> None:
    checked = 0
    for path in ACTIVE_COMMAND_DOCS:
        commands = _documented_commands(path)
        for command_line in commands:
            _assert_documented_command(command_line, path)
            checked += 1
    assert checked >= 80


def test_docs_mcp_command_is_discoverable_from_public_help() -> None:
    assert isinstance(cli, click.Group)
    assert "mcp" in cli.commands
    mcp = cli.commands["mcp"]
    assert isinstance(mcp, click.Group)
    assert "docs-serve" in mcp.commands


def test_options_after_documented_arguments_are_still_validated() -> None:
    source = ROOT / "docs" / "capabilities.md"
    _assert_documented_command("doc-atlas add <url> --browser", source)
    with pytest.raises(AssertionError, match="--not-a-real-option"):
        _assert_documented_command("doc-atlas add <url> --not-a-real-option", source)
