from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DISALLOWED_TRACKED_PREFIXES = (
    "do/",
    "reports/",
    "figures/",
    ".playwright-mcp/",
    ".playwright-cli/",
    "data/raw/",
    "data/processed/",
    "data/site/",
)

TRACKED_PATH_ALLOWLIST = {
    "data/raw/.gitkeep",
    "data/processed/.gitkeep",
    "data/site/.gitkeep",
}

LOCAL_STATE_NAMES = {
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".cache",
}

TEXT_MARKERS = (
    str(Path.home()),
    "Co" + "dex",
    "Clau" + "de",
    "Chat" + "G" + "P" + "T",
    "G" + "P" + "T" + "-Pro",
    "g" + "p" + "t" + "-",
    "Open" + chr(65) + chr(73),
    chr(65) + chr(73) + " assistant",
    "artificial " + "intelligence",
)

TEXT_MARKER_ALLOWLIST = {
    ".gitignore",
    "scripts/check_release_hygiene.py",
}


def git_lines(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return [line for line in result.stdout.splitlines() if line]


def is_text_file(path: Path) -> bool:
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return True


def main() -> int:
    failures: list[str] = []
    tracked = git_lines("ls-files")

    for rel in tracked:
        if rel in TRACKED_PATH_ALLOWLIST:
            continue
        if any(rel.startswith(prefix) for prefix in DISALLOWED_TRACKED_PREFIXES):
            failures.append(f"tracked generated/internal path: {rel}")

    for rel in tracked:
        if rel in TEXT_MARKER_ALLOWLIST:
            continue
        path = ROOT / rel
        if not path.is_file() or not is_text_file(path):
            continue
        text = path.read_text(encoding="utf-8")
        for marker in TEXT_MARKERS:
            if marker in text:
                failures.append(f"tracked text marker {marker!r}: {rel}")

    for path in ROOT.rglob("*"):
        if path == ROOT:
            continue
        if ".git" in path.parts:
            continue
        if path.name in LOCAL_STATE_NAMES and path.exists():
            failures.append(f"repo-local env/cache path exists: {path.relative_to(ROOT)}")

    if failures:
        print("Release hygiene check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Release hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
