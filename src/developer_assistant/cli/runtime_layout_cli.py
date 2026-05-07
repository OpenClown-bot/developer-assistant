from __future__ import annotations

import argparse
import sys
from pathlib import Path

from developer_assistant.runtime_layout import (
    ALLOWED_ROLES,
    render_runtime_config,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="runtime-layout",
        description=(
            "Render per-runtime Hermes config files for a given role. "
            "Used by the install script during setup."
        ),
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=sorted(ALLOWED_ROLES),
        help="Role id (one of the five allowed values)",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="Directory to write rendered files to",
    )
    parser.add_argument(
        "--secrets-env-path",
        required=True,
        help="Path to the secrets .env file (e.g., /srv/devassist/secrets/SELF-DEPLOY.env)",
    )
    parser.add_argument(
        "--operational-db-path",
        required=True,
        help="Path to operational.db (e.g., /srv/devassist/state/operational.db)",
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Path to the repository root (e.g., /srv/devassist/repo)",
    )
    parser.add_argument(
        "--omniroute-base-url",
        default="https://omniroute.infinitycore.space:8443/v1",
        help="OmniRoute base URL (default: https://omniroute.infinitycore.space:8443/v1)",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    try:
        files = render_runtime_config(
            role=args.role,
            secrets_env_path=args.secrets_env_path,
            state_db_path=args.operational_db_path,
            repo_path=args.repo_path,
            omniroute_base_url=args.omniroute_base_url,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in files.items():
        target = out_dir / filename
        target.write_text(content, encoding="utf-8")
        print(f"  wrote {target}")

    print(f"Rendered {len(files)} files for role '{args.role}' to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())