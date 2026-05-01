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

FRONTMATTER_PATTERNS = {
    "docs/architecture/ARCH-*.md": ("id", "version", "status"),
    "docs/architecture/adr/*.md": ("id", "version", "status"),
    "docs/tickets/*.md": ("id", "version", "status"),
    "docs/prd/*.md": ("id", "version", "status"),
    "docs/reviews/*.md": ("id", "version", "status"),
    "docs/backlog/*.md": ("id", "version", "status"),
    "docs/questions/*.md": ("id", "version", "status"),
    "docs/orchestration/*.md": ("id", "version", "status"),
    "docs/prompts/*.md": ("id", "version", "status"),
}

TICKET_REQUIRED_SECTIONS = list(range(1, 11))

TICKET_SECTION_RE = re.compile(r"^##\s+(\d+)\.", re.MULTILINE)

FRONTMATTER_RE = re.compile(r"^---\n(?P<body>.*?)\n---\n", re.DOTALL)


def validate_required_paths(root: Path, errors: list[str]) -> None:
    for directory in REQUIRED_DIRS:
        path = root / directory
        if not path.is_dir():
            errors.append(f"Missing required directory: {directory}")

    for file_name in REQUIRED_FILES:
        path = root / file_name
        if not path.is_file():
            errors.append(f"Missing required file: {file_name}")


def parse_frontmatter(text: str) -> str | None:
    match = FRONTMATTER_RE.match(text)
    if match:
        return match.group("body")
    return None


def validate_frontmatter_keys(
    root: Path, path: Path, required_keys: tuple[str, ...], errors: list[str]
) -> None:
    relative = path.relative_to(root)
    text = path.read_text(encoding="utf-8")
    body = parse_frontmatter(text)
    if body is None:
        errors.append(f"Missing YAML frontmatter: {relative}")
        return
    for key in required_keys:
        if not re.search(rf"^{key}:\s*.+$", body, re.MULTILINE):
            errors.append(f"Missing frontmatter key '{key}': {relative}")


def validate_ticket_sections(root: Path, path: Path, errors: list[str]) -> None:
    relative = path.relative_to(root)
    text = path.read_text(encoding="utf-8")
    found_sections: set[int] = set()
    for match in TICKET_SECTION_RE.finditer(text):
        found_sections.add(int(match.group(1)))
    for section_num in TICKET_REQUIRED_SECTIONS:
        if section_num not in found_sections:
            errors.append(f"Missing section {section_num}: {relative}")


def collect_markdown_files(root: Path) -> dict[Path, tuple[str, ...]]:
    file_keys: dict[Path, tuple[str, ...]] = {}
    for pattern, keys in FRONTMATTER_PATTERNS.items():
        for path in root.glob(pattern):
            if path.name == ".gitkeep":
                continue
            file_keys.setdefault(path, keys)
    return file_keys


def run_validation(root: Path) -> list[str]:
    errors: list[str] = []
    validate_required_paths(root, errors)

    file_keys = collect_markdown_files(root)

    for path in sorted(file_keys):
        keys = file_keys[path]
        validate_frontmatter_keys(root, path, keys, errors)

    tickets_dir = root / "docs" / "tickets"
    if tickets_dir.is_dir():
        for path in sorted(tickets_dir.glob("*.md")):
            if path.name == ".gitkeep":
                continue
            validate_ticket_sections(root, path, errors)

    return errors


def main() -> int:
    errors = run_validation(ROOT)

    if errors:
        for msg in errors:
            print(f"ERROR: {msg}")
        print(f"\nValidation failed with {len(errors)} error(s).")
        return 1

    print("Docs validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
