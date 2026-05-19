"""Integration tests for scaffold_spec.py.

Tests run the script as a subprocess against a tmp_path PST project skeleton
that includes a stub apply_changes.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "Tools" / "Skills" / "project-state-spec" / "tools" / "scaffold_spec.py"


def make_pst_skeleton(root: Path, *, with_apply_changes: bool = True) -> None:
    """Lay out a minimal PST project rooted at ``root``."""
    (root / "status").mkdir(parents=True)
    (root / "status" / ".cache").mkdir()
    (root / "tools").mkdir()
    (root / "research").mkdir()
    (root / "decisions").mkdir()
    (root / "plan").mkdir()
    (root / "prompts" / "landing").mkdir(parents=True)
    (root / "prompts" / "test").mkdir(parents=True)

    (root / "status" / "status.yaml").write_text(
        textwrap.dedent(
            """\
            meta:
              project_name: demo
              source_root: "<未配置>"
            artifacts: []
            research_findings: []
            decisions: []
            change_events: []
            """
        ),
        encoding="utf-8",
    )

    if with_apply_changes:
        # A stub that consumes approved_transitions.json, appends entries to
        # status.yaml, and exits 0. Good enough for integration testing.
        (root / "tools" / "apply_changes.py").write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import argparse, json, sys
                from pathlib import Path
                import yaml

                ap = argparse.ArgumentParser()
                ap.add_argument("--project", required=True)
                args = ap.parse_args()
                root = Path(args.project)
                cache = root / "status" / ".cache" / "approved_transitions.json"
                payload = json.loads(cache.read_text(encoding="utf-8"))
                status_path = root / "status" / "status.yaml"
                status = yaml.safe_load(status_path.read_text(encoding="utf-8")) or {}
                status.setdefault("artifacts", [])
                for t in payload.get("transitions", []):
                    if t.get("op"):
                        # Handoff op — out of scope for this stub.
                        continue
                    status["artifacts"].append({
                        "id": t["artifact"],
                        "type": t.get("type", "unknown"),
                        "path": t.get("path", ""),
                        "status": t["to"],
                        "depends_on": t.get("depends_on", []),
                    })
                status.setdefault("change_events", []).append({
                    "summary": payload.get("event_summary", ""),
                    "transitions": payload.get("transitions", []),
                })
                status_path.write_text(yaml.safe_dump(status, sort_keys=False),
                                      encoding="utf-8")
                """
            ),
            encoding="utf-8",
        )


def run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class TestStatusStage:
    def test_status_on_empty_project_says_requirement_next(self, tmp_path):
        make_pst_skeleton(tmp_path)
        result = run_script(
            "--stage", "status",
            "--topic", "demo-feature",
            "--pst-root", str(tmp_path),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["topic"] == "demo-feature"
        assert out["stages"]["requirement"]["complete"] is False
        assert out["stages"]["design"]["complete"] is False
        assert out["stages"]["tasks"]["complete"] is False
        assert out["next_stage"] == "requirement"

    def test_status_missing_status_yaml_exits_2(self, tmp_path):
        # No skeleton: tmp_path has no status/ folder.
        result = run_script(
            "--stage", "status",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
        )
        assert result.returncode == 2
        assert "status.yaml" in result.stderr.lower()


class TestRequirementStage:
    def test_creates_r_and_d_and_registers(self, tmp_path):
        make_pst_skeleton(tmp_path)
        r_body = tmp_path / "_r.md"
        d_body = tmp_path / "_d.yaml"
        r_body.write_text(
            "## Background\nDemo background.\n\n"
            "## Current State\nNothing exists.\n\n"
            "## Constraints\nMust be small.\n\n"
            "## References\nNone.\n",
            encoding="utf-8",
        )
        d_body.write_text(
            "problem_statement: A small demo problem.\n"
            "decision: |\n"
            "  Build a small thing.\n"
            "acceptance_criteria:\n"
            "  - id: AC-1\n"
            "    user_story: \"As a user, I want X, so that Y.\"\n"
            "    statements:\n"
            "      - \"WHEN x, THE system SHALL y.\"\n"
            "rationale: Because.\n"
            "alternatives_considered: []\n",
            encoding="utf-8",
        )

        result = run_script(
            "--stage", "requirement",
            "--topic", "demo-feature",
            "--pst-root", str(tmp_path),
            "--r-content", str(r_body),
            "--d-content", str(d_body),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["r_id"] == "R-001"
        assert out["d_id"] == "D-001"
        assert out["r_path"].replace("\\", "/") == "research/R-001-demo-feature.md"
        assert out["d_path"].replace("\\", "/") == "decisions/D-001-demo-feature.yaml"

        r_file = tmp_path / "research" / "R-001-demo-feature.md"
        d_file = tmp_path / "decisions" / "D-001-demo-feature.yaml"
        assert r_file.is_file()
        assert d_file.is_file()
        assert r_file.read_text(encoding="utf-8").startswith("# R-001:")
        d_yaml = d_file.read_text(encoding="utf-8")
        assert "id: D-001" in d_yaml
        assert "based_on:" in d_yaml and "R-001" in d_yaml

    def test_repeated_without_force_exits_2(self, tmp_path):
        make_pst_skeleton(tmp_path)
        r_body = tmp_path / "_r.md"
        d_body = tmp_path / "_d.yaml"
        r_body.write_text("## Background\n", encoding="utf-8")
        d_body.write_text(
            "problem_statement: x\ndecision: x\n"
            "acceptance_criteria: []\nrationale: x\n"
            "alternatives_considered: []\n",
            encoding="utf-8",
        )

        ok = run_script(
            "--stage", "requirement",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
            "--r-content", str(r_body),
            "--d-content", str(d_body),
        )
        assert ok.returncode == 0, ok.stderr

        again = run_script(
            "--stage", "requirement",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
            "--r-content", str(r_body),
            "--d-content", str(d_body),
        )
        assert again.returncode == 2
        assert "exist" in again.stderr.lower()

    def test_apply_changes_failure_keeps_files(self, tmp_path):
        make_pst_skeleton(tmp_path)
        # Replace the stub with a script that always fails.
        (tmp_path / "tools" / "apply_changes.py").write_text(
            "import sys; sys.stderr.write('boom\\n'); sys.exit(7)\n",
            encoding="utf-8",
        )
        r_body = tmp_path / "_r.md"
        d_body = tmp_path / "_d.yaml"
        r_body.write_text("## Background\n", encoding="utf-8")
        d_body.write_text("problem_statement: x\ndecision: x\nacceptance_criteria: []\nrationale: x\nalternatives_considered: []\n", encoding="utf-8")

        result = run_script(
            "--stage", "requirement",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
            "--r-content", str(r_body),
            "--d-content", str(d_body),
        )
        assert result.returncode == 3
        # Files should still exist (no rollback per Property 7).
        assert (tmp_path / "research" / "R-001-demo.md").is_file()
        assert (tmp_path / "decisions" / "D-001-demo.yaml").is_file()
        assert "boom" in result.stderr or "PST AUDIT" in result.stderr
