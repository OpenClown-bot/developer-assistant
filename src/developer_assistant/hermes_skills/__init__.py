"""Shared helpers for project-local Hermes custom skills.

Provides a locale-loading utility used by all three Orchestrator-only
custom skills (dev-assist-classifier, dev-assist-progress-report,
dev-assist-escalation-surface).  Every skill loads its Russian text
resources from its own locale/ru.yaml file — none hardcodes strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def load_locale_yaml(skill_package_path: str) -> dict[str, Any]:
    """Load a locale/ru.yaml file from a skill's package directory.

    Args:
        skill_package_path: Absolute or relative path to the skill's
            package directory (the directory containing locale/).

    Returns:
        Parsed YAML contents as a dict.

    Raises:
        ImportError: if PyYAML is not installed.
        FileNotFoundError: if locale/ru.yaml does not exist.
        ValueError: if the YAML is empty or unparseable.
    """
    if yaml is None:
        raise ImportError(
            "PyYAML is required to load skill locale files. "
            "Install it with: pip install pyyaml"
        )

    locale_file = Path(skill_package_path) / "locale" / "ru.yaml"
    if not locale_file.is_file():
        raise FileNotFoundError(
            f"Locale file not found: {locale_file}"
        )

    raw = locale_file.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if not parsed:
        raise ValueError(
            f"Locale file is empty or invalid: {locale_file}"
        )
    return parsed