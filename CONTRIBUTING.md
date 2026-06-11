# Contributing to fieldnotes

Glad you're here. This tool was designed and is maintained by Claude (an AI) on Nate's machine — contributions are reviewed the same way regardless of who or what wrote them: on the work.

## Ground rules (the short version)

1. **Nothing fails silently.** This is the house rule and it's load-bearing. A wrong line range must surface as a stale pin, never as quietly-wrong content. A hook that can't run must degrade visibly or harmlessly, never invisibly. If your change introduces a failure path, make it loud or make it safe — there is no third option.
2. **Tests first, red first.** Every behavior change starts with a failing test. The suite is fast (`pytest` runs in seconds); there's no excuse to skip the red step. PRs whose tests obviously passed on the first run get asked about it.
3. **No new dependencies.** Plaintext + git + Python stdlib (plus the existing pydantic/typer/rich/frontmatter). Parser-free resolvers are a deliberate choice, not an oversight — see issue #3 before reaching for tree-sitter.
4. **This repo gates its own commits.** `.fieldnotes/` here is real and the pre-commit gate is installed. If your change drifts a note, heal it properly: `fieldnotes diff <id>` → actually re-read the claim → `fieldnotes verify --update` → `fieldnotes confirm <id> --by <your-identity>` if the claim holds, or fix the prose if it doesn't. Blind re-pinning defeats the entire tool.

## Dev setup

```bash
git clone https://github.com/Wynelson94/fieldnotes && cd fieldnotes
pip install -e .
pytest                  # all green before you start
ruff check && ruff format --check
```

## Before you open a PR

- `ruff check` and `ruff format --check` clean
- `pytest` fully green (300+ tests)
- New behavior has tests that failed before your change
- `fieldnotes verify --check` green (the gate enforces this at commit time anyway)
- One concern per PR; small is good

## Releases

Maintainer-only: tag push triggers GitHub Actions → PyPI via OIDC Trusted Publishing (`claude-fieldnotes`). Don't bump versions in PRs.

## Where to start

The [open issues](https://github.com/Wynelson94/fieldnotes/issues) are the live punch list — they come from real usage, not speculation. #1 is a well-scoped first bug with a repro.
