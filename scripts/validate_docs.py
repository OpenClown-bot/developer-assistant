from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = [
    "docs/prd",
    "docs/architecture",
    "docs/architecture/adr",
    "docs/tickets",
    "docs/reviews",
    "docs/backlog",
    "docs/prompts",
    "docs/questions",
    "docs/orchestration",
]

REQUIRED_FILES = [
    "README.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "docs/orchestration/SESSION-STATE.md",
]

FRONTMATTER_REQUIRED_PATTERNS = [
    "docs/prd/*.md",
    "docs/architecture/*.md",
    "docs/architecture/adr/*.md",
    "docs/tickets/*.md",
    "docs/reviews/*.md",
    "docs/backlog/*.md",
    "docs/questions/*.md",
    "docs/orchestration/*.md",
]

FRONTMATTER_RE = re.compile(r"^---\n(?P<body>.*?)\n---\n", re.DOTALL)


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def validate_required_paths() -> None:
    for directory in REQUIRED_DIRS:
        path = ROOT / directory
        if not path.is_dir():
            fail(f"Missing required directory: {directory}")

    for file_name in REQUIRED_FILES:
        path = ROOT / file_name
        if not path.is_file():
            fail(f"Missing required file: {file_name}")


def iter_markdown_files() -> set[Path]:
    files: set[Path] = set()
    for pattern in FRONTMATTER_REQUIRED_PATTERNS:
        files.update(ROOT.glob(pattern))
    return files


def validate_frontmatter(path: Path) -> None:
    relative = path.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        fail(f"Missing YAML frontmatter: {relative}")

    body = match.group("body")
    for key in ("id", "version", "status"):
        if not re.search(rf"^{key}:\s*.+$", body, re.MULTILINE):
            fail(f"Missing frontmatter key '{key}': {relative}")


def main() -> int:
    validate_required_paths()
    for path in sorted(iter_markdown_files()):
        if path.name == ".gitkeep":
            continue
        validate_frontmatter(path)

    print("Docs validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
