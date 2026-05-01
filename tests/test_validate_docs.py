from __future__ import annotations

import os
import sys
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from validate_docs import (
    REQUIRED_DIRS,
    TICKET_REQUIRED_SECTIONS,
    run_validation,
)

VALID_ADR = textwrap.dedent("""\
    ---
    id: ADR-099
    version: 0.1.0
    status: draft
    ---
    # ADR-099: Test
    ## Context
    test
    ## Decision
    test
    ## Consequences
    test
""")

VALID_ARCH = textwrap.dedent("""\
    ---
    id: ARCH-099
    version: 0.1.0
    status: draft
    ---
    # ARCH-099: Test
""")

VALID_TICKET = textwrap.dedent("""\
    ---
    id: TKT-099
    version: 0.1.0
    status: draft
    ---
    # TKT-099: Test
    ## 1. Scope
    test
    ## 2. Non-scope
    test
    ## 3. Required Context
    test
    ## 4. Acceptance Criteria
    test
    ## 5. Allowed Files
    test
    ## 6. Test/Validation Requirements
    test
    ## 7. PR Requirements
    test
    ## 8. Risks
    test
    ## 9. Dependencies
    test
    ## 10. Execution Log
    test
""")

VALID_PRD = textwrap.dedent("""\
    ---
    id: PRD-099
    version: 0.1.0
    status: draft
    ---
    # PRD-099: Test
""")


def _make_repo(tmp: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return tmp


def _minimal_repo(tmp: Path, extra: dict[str, str] | None = None) -> Path:
    base_files: dict[str, str] = {
        "README.md": "# test",
        "CONTRIBUTING.md": "# test",
        "AGENTS.md": "# test",
    }
    for d in REQUIRED_DIRS:
        base_files[os.path.join(d, ".gitkeep")] = ""
    base_files["docs/orchestration/SESSION-STATE.md"] = (
        "---\nid: SESSION-STATE\nversion: 0.1.0\nstatus: active\n---\n# Session State\n"
    )
    if extra:
        base_files.update(extra)
    return _make_repo(tmp, base_files)


class TestFrontmatterValidation(unittest.TestCase):
    def test_missing_frontmatter_adr(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _minimal_repo(tmp, {"docs/architecture/adr/ADR-099.md": "# no frontmatter\n"})
            errors = run_validation(tmp)
            self.assertTrue(any("Missing YAML frontmatter" in e for e in errors))
            self.assertTrue(any("ADR-099" in e for e in errors))

    def test_missing_frontmatter_key_in_adr(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bad_adr = "---\nid: ADR-099\nversion: 0.1.0\n---\n# ADR-099\n"
            _minimal_repo(tmp, {"docs/architecture/adr/ADR-099.md": bad_adr})
            errors = run_validation(tmp)
            self.assertTrue(any("Missing frontmatter key 'status'" in e and "ADR-099" in e for e in errors))

    def test_missing_frontmatter_key_in_arch(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bad_arch = "---\nid: ARCH-099\n---\n# ARCH-099\n"
            _minimal_repo(tmp, {"docs/architecture/ARCH-099.md": bad_arch})
            errors = run_validation(tmp)
            self.assertTrue(any("Missing frontmatter key 'version'" in e and "ARCH-099" in e for e in errors))
            self.assertTrue(any("Missing frontmatter key 'status'" in e and "ARCH-099" in e for e in errors))

    def test_valid_adr_passes(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _minimal_repo(tmp, {"docs/architecture/adr/ADR-099.md": VALID_ADR})
            errors = run_validation(tmp)
            self.assertEqual(errors, [])

    def test_valid_arch_passes(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _minimal_repo(tmp, {"docs/architecture/ARCH-099.md": VALID_ARCH})
            errors = run_validation(tmp)
            self.assertEqual(errors, [])

    def test_valid_prd_passes(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _minimal_repo(tmp, {"docs/prd/PRD-099.md": VALID_PRD})
            errors = run_validation(tmp)
            self.assertEqual(errors, [])

    def test_exit_nonzero_on_missing_keys(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bad = "---\nid: X\n---\n# X\n"
            _minimal_repo(tmp, {
                "docs/architecture/ARCH-099.md": bad,
                "docs/architecture/adr/ADR-099.md": bad,
            })
            errors = run_validation(tmp)
            self.assertGreater(len(errors), 0)


class TestTicketSectionValidation(unittest.TestCase):
    def test_missing_ticket_sections(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bad_ticket = "---\nid: TKT-099\nversion: 0.1.0\nstatus: draft\n---\n# TKT-099\n## 1. Scope\ntest\n"
            _minimal_repo(tmp, {"docs/tickets/TKT-099.md": bad_ticket})
            errors = run_validation(tmp)
            for i in range(2, 11):
                self.assertTrue(any(f"Missing section {i}" in e and "TKT-099" in e for e in errors))

    def test_valid_ticket_passes(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _minimal_repo(tmp, {"docs/tickets/TKT-099.md": VALID_TICKET})
            errors = run_validation(tmp)
            self.assertEqual(errors, [])

    def test_missing_section_10_only(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            lines = VALID_TICKET.split("\n")
            filtered = [l for l in lines if "## 10." not in l]
            _minimal_repo(tmp, {"docs/tickets/TKT-099.md": "\n".join(filtered)})
            errors = run_validation(tmp)
            self.assertTrue(any("Missing section 10" in e for e in errors))

    def test_all_ten_sections_required(self) -> None:
        self.assertEqual(TICKET_REQUIRED_SECTIONS, list(range(1, 11)))


class TestErrorReporting(unittest.TestCase):
    def test_names_failing_file_and_reason(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            bad_adr = "---\nid: ADR-099\n---\n# ADR-099\n"
            bad_ticket = "---\nid: TKT-099\nversion: 0.1.0\nstatus: draft\n---\n# TKT-099\n## 1. Scope\ntest\n"
            _minimal_repo(tmp, {
                "docs/architecture/adr/ADR-099.md": bad_adr,
                "docs/tickets/TKT-099.md": bad_ticket,
            })
            errors = run_validation(tmp)
            self.assertTrue(any("ADR-099" in e for e in errors))
            self.assertTrue(any("TKT-099" in e for e in errors))
            self.assertTrue(any("Missing frontmatter key" in e for e in errors))
            self.assertTrue(any("Missing section" in e for e in errors))

    def test_multiple_errors_collected(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            _minimal_repo(tmp, {"docs/architecture/adr/ADR-099.md": "# no fm\n"})
            errors = run_validation(tmp)
            self.assertGreaterEqual(len(errors), 1)


class TestRequiredPaths(unittest.TestCase):
    def test_missing_required_directory(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "README.md").write_text("# t", encoding="utf-8")
            (tmp / "CONTRIBUTING.md").write_text("# t", encoding="utf-8")
            (tmp / "AGENTS.md").write_text("# t", encoding="utf-8")
            errors = run_validation(tmp)
            self.assertTrue(any("Missing required directory" in e for e in errors))

    def test_missing_required_file(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            for d in REQUIRED_DIRS:
                (tmp / d).mkdir(parents=True, exist_ok=True)
            errors = run_validation(tmp)
            self.assertTrue(any("Missing required file" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
