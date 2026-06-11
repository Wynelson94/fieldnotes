"""Diagnostics for a fieldnotes installation: is everything wired correctly?

`run_diagnostics` returns a structured report. The CLI renders it; tests
exercise it directly.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from fieldnotes import __version__
from fieldnotes.githook import git_hook_installed, git_toplevel
from fieldnotes.store import (
    DOT_DIR,
    RepoNotInitializedError,
    find_repo_root,
    iter_note_files,
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    fix: str | None = None


@dataclass
class DiagnosticsReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, *checks: CheckResult) -> None:
        self.checks.extend(checks)


def check_binary() -> tuple[CheckResult, str | None]:
    resolved = shutil.which("fieldnotes")
    if resolved is None:
        return (
            CheckResult(
                name="binary on PATH",
                ok=False,
                detail="not found",
                fix=(
                    "Install fieldnotes into the Python that hosts your other CLI "
                    "agents, e.g. `<python> -m pip install -e <repo>`. Hook subshells "
                    "don't inherit your interactive PATH, so installing into a venv "
                    "you don't activate globally won't work."
                ),
            ),
            None,
        )
    return (
        CheckResult(name="binary on PATH", ok=True, detail=resolved),
        resolved,
    )


def check_package() -> CheckResult:
    return CheckResult(
        name="package importable",
        ok=True,
        detail=f"fieldnotes {__version__}",
    )


def _command_uses_binary(command: str, expected_binary: str | None) -> bool:
    """True if the hook command starts with `<expected_binary> ...`. If no
    expected binary is known, accepts anything ending in `fieldnotes`."""
    head = command.strip().split(" ", 1)[0]
    if expected_binary is not None:
        return head == expected_binary
    return head == "fieldnotes" or head.endswith("/fieldnotes")


def check_hooks(settings_path: Path, expected_binary: str | None) -> list[CheckResult]:
    if not settings_path.exists():
        return [
            CheckResult(
                name="hooks installed",
                ok=False,
                detail=f"{settings_path} does not exist",
                fix="Run `fieldnotes install-hooks --apply`.",
            )
        ]
    try:
        data = json.loads(settings_path.read_text() or "{}")
    except json.JSONDecodeError as exc:
        return [
            CheckResult(
                name="hooks installed",
                ok=False,
                detail=f"could not parse {settings_path}: {exc}",
                fix="Repair settings.json by hand, then re-run install-hooks.",
            )
        ]

    hooks = data.get("hooks") or {}
    out: list[CheckResult] = []

    for event, looking_for in (
        ("SessionStart", "brief"),
        ("PostToolUse", "touched"),
        ("Stop", "handoff"),
    ):
        entries = hooks.get(event) or []
        matching = [
            e
            for e in entries
            for h in (e.get("hooks") or [])
            if h.get("type") == "command"
            and isinstance(h.get("command"), str)
            and looking_for in h["command"]
            and "fieldnotes" in h["command"]
        ]
        if not matching:
            out.append(
                CheckResult(
                    name=f"{event} hook",
                    ok=False,
                    detail=f"no fieldnotes {looking_for} entry in {event}",
                    fix=f"Run `fieldnotes install-hooks --apply` to add the {event} hook.",
                )
            )
            continue
        # Inspect the path inside the command.
        first_cmd = next(
            (
                h["command"]
                for e in matching
                for h in (e.get("hooks") or [])
                if h.get("type") == "command"
                and isinstance(h.get("command"), str)
                and looking_for in h["command"]
            ),
            "",
        )
        if not _command_uses_binary(first_cmd, expected_binary):
            head = first_cmd.split(" ", 1)[0]
            out.append(
                CheckResult(
                    name=f"{event} hook",
                    ok=False,
                    detail=(f"present, but command uses {head!r} (expected {expected_binary!r})"),
                    fix=(
                        "Re-run `fieldnotes install-hooks --apply` to update the "
                        "path to the currently-installed binary."
                    ),
                )
            )
        else:
            out.append(
                CheckResult(
                    name=f"{event} hook",
                    ok=True,
                    detail=f"present at {settings_path}",
                )
            )
    return out


def check_cwd_repo(cwd: Path) -> CheckResult:
    try:
        root = find_repo_root(cwd)
    except RepoNotInitializedError:
        return CheckResult(
            name="cwd has .fieldnotes/",
            ok=False,
            detail=f"no {DOT_DIR}/ in {cwd} or any parent",
            fix="Run `fieldnotes init` inside the repo you want to take notes on.",
        )
    n = sum(1 for _ in iter_note_files(root))
    return CheckResult(
        name="cwd has .fieldnotes/",
        ok=True,
        detail=f"{root} ({n} note{'s' if n != 1 else ''})",
    )


def check_git_hook(cwd: Path) -> CheckResult | None:
    """Whether the fieldnotes pre-commit gate is wired for cwd's repo.

    Returns None when cwd isn't inside a fieldnotes repo, or that repo isn't a
    git repo — the gate doesn't apply there, so doctor stays quiet about it.
    """
    try:
        root = find_repo_root(cwd)
    except RepoNotInitializedError:
        return None
    if git_toplevel(root) is None:
        return None
    installed, hook_path = git_hook_installed(root)
    if installed:
        return CheckResult(
            name="git pre-commit gate",
            ok=True,
            detail=f"installed at {hook_path}",
        )
    return CheckResult(
        name="git pre-commit gate",
        ok=False,
        detail="no fieldnotes pre-commit hook in this repo",
        fix="Run `fieldnotes install-git-hook` to block commits that stale a note.",
    )


def run_diagnostics(
    settings_path: Path | None = None,
    cwd: Path | None = None,
) -> DiagnosticsReport:
    settings = settings_path or (Path.home() / ".claude" / "settings.json")
    where = cwd or Path.cwd()
    report = DiagnosticsReport()

    binary_check, resolved = check_binary()
    report.add(binary_check)
    report.add(check_package())
    report.add(*check_hooks(settings, resolved))
    report.add(check_cwd_repo(where))
    git_hook = check_git_hook(where)
    if git_hook is not None:
        report.add(git_hook)
    return report
