from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from developer_assistant.model_catalog import (
    CatalogViolation,
    get_all_roles,
    paid_third_party_external_service_not_yet_supported_error,
    probe_omniroute,
    verify_runtime_config,
)


def _cmd_verify_runtime(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    if not config_path.exists():
        print("ERROR: config file not found: {p}".format(p=args.config), file=sys.stderr)
        return 1
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print("ERROR: failed to read config: {e}".format(e=exc), file=sys.stderr)
        return 1
    try:
        verify_runtime_config(args.role, config)
    except CatalogViolation as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _cmd_probe_omniroute(args: argparse.Namespace) -> int:
    base_url = "http://127.0.0.1:{port}".format(port=args.omniroute_port)
    roles = [args.role] if args.role else get_all_roles()

    all_results: list = []
    for role in roles:
        results = probe_omniroute(
            base_url, role,
            exhaustive=args.exhaustive,
        )
        all_results.extend(results)

    print("{role:<15} {id:<50} {ok:<8} {reason:<20} {lat}".format(
        role="Role", id="Identifier", ok="OK", reason="Reason", lat="Latency(ms)"
    ))
    print("-" * 100)
    for r in all_results:
        ok_str = "yes" if r.ok else "no"
        lat_str = "{:.1f}".format(r.latency_ms) if r.latency_ms is not None else "N/A"
        reason_str = r.reason or ""
        print("{role:<15} {id:<50} {ok:<8} {reason:<20} {lat}".format(
            role=r.role, id=r.identifier, ok=ok_str, reason=reason_str, lat=lat_str
        ))

    failures = [r for r in all_results if not r.ok]
    if failures:
        for f in failures:
            try:
                paid_third_party_external_service_not_yet_supported_error(
                    f.role, f.identifier, f.reason or "unknown"
                )
            except CatalogViolation:
                pass
        print(
            "FAIL: {n} probe(s) failed. Escalation rule "
            "paid:third_party_external_service_not_yet_supported raised.".format(
                n=len(failures)
            ),
            file=sys.stderr,
        )
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="model-catalog",
        description="Model-catalog enforcement helper and OmniRoute resolution probe.",
    )
    subparsers = parser.add_subparsers(dest="command")

    verify_p = subparsers.add_parser(
        "verify-runtime",
        help="Verify a runtime config against the model catalog.",
    )
    verify_p.add_argument("--role", required=True, help="Role id to verify")
    verify_p.add_argument("--config", required=True, help="Path to runtime config JSON")

    probe_p = subparsers.add_parser(
        "probe-omniroute",
        help="Probe OmniRoute for model resolution.",
    )
    probe_p.add_argument(
        "--omniroute-port", required=True, type=int, help="OmniRoute localhost port"
    )
    probe_p.add_argument("--role", default=None, help="Single role to probe (default: all)")
    probe_p.add_argument(
        "--exhaustive", action="store_true",
        help="Probe every (role, identifier) pair (mains + fallbacks = 20 probes)",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.command == "verify-runtime":
        return _cmd_verify_runtime(args)
    elif args.command == "probe-omniroute":
        return _cmd_probe_omniroute(args)
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
