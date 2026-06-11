"""Git pre-commit gate — block commits that leave a fieldnotes note stale.

The Claude Code hooks (`brief`, `touched`) *notify* about drift; they don't
*enforce* it. A note silently goes stale the moment a commit changes a file it
pins without the note being updated. This module installs a git `pre-commit`
hook that turns that drift into a hard stop at commit time.

`install_git_hook` is idempotent and never overwrites a pre-commit hook the
tool didn't write.
"""

from __future__ import annotations

import shlex
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

# Marker line carried in every hook the tool generates — lets re-runs tell
# "our hook" apart from one a user (or another tool) hand-rolled.
HOOK_MARKER = "fieldnotes pre-commit gate"


def _git(repo_root: Path, *args: str) -> str | None:
    """Run `git ...` inside `repo_root`. Return stripped stdout, or None on failure."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return out.stdout.strip()


def git_toplevel(start: Path) -> Path | None:
    """Return the git work-tree root containing `start`, or None if not a git repo."""
    out = _git(start, "rev-parse", "--show-toplevel")
    return Path(out) if out else None


def effective_hooks_dir(repo_root: Path) -> Path:
    """The directory git actually reads hooks from for this repo.

    Honors `core.hooksPath` when set (relative values resolve against the work
    tree root); otherwise the repo's standard hooks directory.
    """
    hooks_path = _git(repo_root, "config", "--get", "core.hooksPath")
    if hooks_path:
        p = Path(hooks_path).expanduser()
        return p if p.is_absolute() else (repo_root / p)
    git_path = _git(repo_root, "rev-parse", "--git-path", "hooks")
    if git_path:
        p = Path(git_path)
        return p if p.is_absolute() else (repo_root / p)
    return repo_root / ".git" / "hooks"


def build_hook_script(binary: str) -> str:
    """The `pre-commit` script text, with `binary` baked in as the fieldnotes command.

    `binary` is an absolute path by default (hook subshells don't inherit an
    interactive PATH) — or the bare `fieldnotes` when the caller opts in.
    """
    quoted = shlex.quote(binary)
    return f"""#!/usr/bin/env sh
# {HOOK_MARKER}  ·  installed by `fieldnotes install-git-hook`
#
# Blocks a commit that leaves a fieldnotes note stale — a file a note pins
# changed without the note being updated. Re-pin with `fieldnotes verify --update`.
# Disable by deleting this file.

# Contributors / CI without fieldnotes installed are never blocked.
command -v {quoted} >/dev/null 2>&1 || exit 0

# Only gate repos that actually use fieldnotes.
top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -d "$top/.fieldnotes" ] || exit 0

{quoted} verify --check --quiet --repo "$top" || {{
  echo "fieldnotes: commit blocked — a note is stale (see above)." >&2
  echo "  fix the note, or re-pin with: fieldnotes verify --update" >&2
  exit 1
}}
exit 0
"""


@dataclass(frozen=True)
class GitHookResult:
    """Outcome of an install attempt, surfaced by the CLI."""

    status: str  # installed | updated | unchanged | foreign | not-a-git-repo
    hook_path: Path | None
    detail: str


def hook_is_ours(path: Path) -> bool:
    """True if `path` is a pre-commit hook this tool wrote (carries HOOK_MARKER)."""
    if not path.exists():
        return False
    try:
        return HOOK_MARKER in path.read_text()
    except (OSError, UnicodeDecodeError):
        return False


def _write_hook(path: Path, script: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script)
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_git_hook(repo_root: Path, binary: str) -> GitHookResult:
    """Install (or refresh) the fieldnotes pre-commit gate for `repo_root`.

    Idempotent: re-running refreshes the tool's own hook in place. A pre-commit
    hook the tool did not write is never overwritten.
    """
    top = git_toplevel(repo_root)
    if top is None:
        return GitHookResult("not-a-git-repo", None, f"{repo_root} is not inside a git repository")
    hook_path = effective_hooks_dir(top) / "pre-commit"
    script = build_hook_script(binary)

    if hook_path.exists():
        if not hook_is_ours(hook_path):
            return GitHookResult(
                "foreign",
                hook_path,
                f"a pre-commit hook fieldnotes didn't write already exists at {hook_path}",
            )
        if hook_path.read_text() == script:
            return GitHookResult("unchanged", hook_path, "gate already installed")
        _write_hook(hook_path, script)
        return GitHookResult("updated", hook_path, "refreshed the existing fieldnotes gate")

    _write_hook(hook_path, script)
    return GitHookResult("installed", hook_path, "installed the fieldnotes pre-commit gate")


def git_hook_installed(repo_root: Path) -> tuple[bool, Path | None]:
    """(installed?, hook_path) — whether the fieldnotes gate is wired for `repo_root`.

    `hook_path` is where the hook would live; None when `repo_root` isn't a git repo.
    """
    top = git_toplevel(repo_root)
    if top is None:
        return False, None
    hook_path = effective_hooks_dir(top) / "pre-commit"
    return hook_is_ours(hook_path), hook_path
