"""Write the command reference (``docs/cli.md``) from the argument parser itself."""

from __future__ import annotations

import argparse

from riskwren.cli import build_parser

HEADER = """# Command reference

Every `riskwren` command. This page is written from the program itself, so it always matches
the version it ships with. Run commands with `uv run riskwren …` from the project directory.

Options that come before the command apply to all of them:

```text
{usage}
```
"""


def _subcommands(parser: argparse.ArgumentParser) -> list[tuple[str, str, argparse.ArgumentParser]]:
    found = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            helps = {choice.dest: choice.help or "" for choice in action._choices_actions}
            found += [(name, helps.get(name, ""), sub) for name, sub in action.choices.items()]
    return found


def _options(parser: argparse.ArgumentParser) -> list[str]:
    lines = []
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction | argparse._SubParsersAction):
            continue
        if action.option_strings:
            name = ", ".join(f"`{flag}`" for flag in action.option_strings)
            if action.metavar or (action.nargs != 0 and action.type):
                name += f" `{action.metavar or action.dest.upper()}`"
        else:
            name = f"`{action.metavar or action.dest.upper()}`"
        lines.append(f"| {name} | {(action.help or '').replace('|', '\\|')} |")
    return lines


def _section(path: str, summary: str, parser: argparse.ArgumentParser, level: int) -> list[str]:
    out = [f"{'#' * level} `{path}`", ""]
    out += [parser.description or summary, ""]
    options = _options(parser)
    if options:
        out += ["| Option | Meaning |", "|---|---|", *options, ""]
    for name, help_text, sub in _subcommands(parser):
        out += _section(f"{path} {name}", help_text, sub, level + 1)
    return out


def render() -> str:
    parser = build_parser()
    # Fix the width so the page does not change with the terminal it was generated in.
    usage = parser.format_usage().replace("usage: ", "").strip()
    usage = " ".join(usage.split())
    lines = [HEADER.format(usage=usage)]
    lines += ["## Commands", "", "| Command | What it does |", "|---|---|"]
    for name, help_text, _ in _subcommands(parser):
        lines.append(
            f"| [`riskwren {name}`](#riskwren-{name}) | {help_text[:1].upper()}{help_text[1:]} |"
        )
    lines.append("")
    for name, help_text, sub in _subcommands(parser):
        lines += _section(f"riskwren {name}", help_text, sub, 2)
    return "\n".join(lines).rstrip() + "\n"
