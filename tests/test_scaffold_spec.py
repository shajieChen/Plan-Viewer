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
