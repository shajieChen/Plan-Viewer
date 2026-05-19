# project-state-spec Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `project-state-spec` skill that guides a user through a Requirement → Design → Task three-stage workflow and produces PST five-stage artifacts (R + D + Plan + LP + TP) on disk and in `status.yaml`.

**Architecture:** A prompt-only `SKILL.md` runs the conversation; a companion Python script `scaffold_spec.py` does all side effects (ID allocation, file writes, `apply_changes.py` invocation). A pure-function helper module `_spec_helpers.py` is shared and unit-tested. The skill is distributed through the existing `Tools/install_skills.py` pipeline (drop a folder into `Tools/Skills/`, no new installer code needed).

**Tech Stack:** Python 3 (stdlib only + PyYAML, already in `requirements.txt`), pytest with `tmp_path` fixtures, hypothesis (already in `.hypothesis/`) for property tests where useful.

---

## File Structure

**New files (all under `Tools/Skills/project-state-spec/`):**

| File | Responsibility |
|---|---|
| `SKILL.md` | Conversation protocol: invocation, three-stage flow, EARS validation hints, pause/resume language. |
| `tools/scaffold_spec.py` | CLI with four sub-commands (`--stage requirement|design|tasks|status`). Owns all side effects. |
| `tools/_spec_helpers.py` | Pure utility functions: `slugify`, `today_iso`, `load_status`, `next_id`, `find_artifact_by_topic`, `safe_write`. |
| `templates/r_template.md` | Reference template the skill reads when drafting R content. |
| `templates/d_template.yaml` | Reference template for D content. |
| `templates/plan_template.md` | Reference template for Plan content. |
| `templates/lp_template.md` | Reference template for individual LP content. |
| `templates/tp_template.md` | Reference template for individual TP content. |
| `templates/landing_readme_template.md` | Reference template for `prompts/landing/README.md` body. |

**New test files (under existing `tests/`):**

| File | Coverage |
|---|---|
| `tests/test_spec_helpers.py` | Unit tests for pure functions in `_spec_helpers.py`. |
| `tests/test_scaffold_spec.py` | Integration tests: real subprocess invocation of `scaffold_spec.py` with a stub `apply_changes.py` in `tmp_path`. |

**Modified files:** none. The existing `Tools/install_skills.py` auto-discovers any subdirectory of `Tools/Skills/` containing a `SKILL.md`, so deployment is automatic.

---

## Task 1: Bootstrap skill folder + slugify helper

**Files:**
- Create: `Tools/Skills/project-state-spec/tools/__init__.py` (empty)
- Create: `Tools/Skills/project-state-spec/tools/_spec_helpers.py`
- Test: `tests/test_spec_helpers.py`

- [ ] **Step 1: Create the package directory and empty `__init__.py`**

```bash
mkdir -p Tools/Skills/project-state-spec/tools
type nul > Tools/Skills/project-state-spec/tools/__init__.py
```

- [ ] **Step 2: Write the failing test for `slugify`**

Create `tests/test_spec_helpers.py`:

```python
"""Unit tests for project-state-spec helpers."""

import sys
from pathlib import Path

import pytest

_SKILL_TOOLS = (
    Path(__file__).resolve().parent.parent
    / "Tools" / "Skills" / "project-state-spec" / "tools"
)
sys.path.insert(0, str(_SKILL_TOOLS))

from _spec_helpers import slugify  # noqa: E402


class TestSlugify:
    def test_basic_phrase(self):
        assert slugify("README Guide Button") == "readme-guide-button"

    def test_collapses_repeated_separators(self):
        assert slugify("Hello   --  World") == "hello-world"

    def test_strips_edge_separators(self):
        assert slugify("  spaced out  ") == "spaced-out"

    def test_keeps_digits(self):
        assert slugify("Phase 2 Cleanup") == "phase-2-cleanup"

    def test_handles_chinese_with_fallback(self):
        # Non-ASCII is replaced with '-'; collapsed; result must be non-empty
        # for at least the surrounding ASCII tokens.
        result = slugify("v2 一键启动 server")
        assert result.startswith("v2-")
        assert result.endswith("-server")
        assert "--" not in result
        assert not result.startswith("-")
        assert not result.endswith("-")

    def test_empty_after_normalize_raises(self):
        with pytest.raises(ValueError):
            slugify("   ")

    def test_pure_non_ascii_raises(self):
        with pytest.raises(ValueError):
            slugify("中文")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_spec_helpers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named '_spec_helpers'` or import error.

- [ ] **Step 4: Implement `slugify`**

Create `Tools/Skills/project-state-spec/tools/_spec_helpers.py`:

```python
"""Pure utility functions for project-state-spec scaffold script.

These functions have NO side effects (other than ``safe_write``, which is
explicit) and are unit-tested in tests/test_spec_helpers.py.
"""

from __future__ import annotations

import re as _re
from pathlib import Path


def slugify(text: str) -> str:
    """Lowercase, replace non-ASCII alphanumerics with ``-``, collapse repeats.

    Raises ``ValueError`` if the result would be empty.
    """
    lowered = text.lower()
    # Replace every char that is not [a-z0-9] with a hyphen.
    replaced = _re.sub(r"[^a-z0-9]+", "-", lowered)
    # Collapse runs of hyphens, strip leading/trailing.
    collapsed = _re.sub(r"-+", "-", replaced).strip("-")
    if not collapsed:
        raise ValueError(f"slugify produced empty string from input: {text!r}")
    return collapsed
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_spec_helpers.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/__init__.py Tools/Skills/project-state-spec/tools/_spec_helpers.py tests/test_spec_helpers.py
git commit -m "feat(project-state-spec): bootstrap helper module with slugify"
```

---

## Task 2: today_iso + load_status helpers

**Files:**
- Modify: `Tools/Skills/project-state-spec/tools/_spec_helpers.py`
- Modify: `tests/test_spec_helpers.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_spec_helpers.py`:

```python
import re as _re
import textwrap

from _spec_helpers import today_iso, load_status, StatusYamlMissingError  # noqa: E402


class TestTodayIso:
    def test_format_is_yyyy_mm_dd(self):
        s = today_iso()
        assert _re.fullmatch(r"\d{4}-\d{2}-\d{2}", s), s


class TestLoadStatus:
    def test_loads_existing_yaml(self, tmp_path):
        status_dir = tmp_path / "status"
        status_dir.mkdir()
        (status_dir / "status.yaml").write_text(
            textwrap.dedent(
                """\
                meta:
                  project_name: demo
                artifacts: []
                """
            ),
            encoding="utf-8",
        )
        data = load_status(tmp_path)
        assert data["meta"]["project_name"] == "demo"
        assert data["artifacts"] == []

    def test_missing_status_raises(self, tmp_path):
        with pytest.raises(StatusYamlMissingError):
            load_status(tmp_path)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_spec_helpers.py -v`
Expected: import error / `today_iso`, `load_status`, `StatusYamlMissingError` not defined.

- [ ] **Step 3: Implement helpers**

Append to `Tools/Skills/project-state-spec/tools/_spec_helpers.py`:

```python
import datetime as _dt

import yaml  # PyYAML, already in requirements.txt


class StatusYamlMissingError(FileNotFoundError):
    """Raised when ``<pst_root>/status/status.yaml`` does not exist."""


def today_iso() -> str:
    """Return current UTC date as ``YYYY-MM-DD``."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")


def load_status(pst_root: Path | str) -> dict:
    """Load and return ``<pst_root>/status/status.yaml`` as a dict.

    Raises ``StatusYamlMissingError`` if the file does not exist.
    """
    pst_root = Path(pst_root)
    status_path = pst_root / "status" / "status.yaml"
    if not status_path.is_file():
        raise StatusYamlMissingError(
            f"status.yaml not found at {status_path}. "
            "Run PST INIT first."
        )
    with status_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"status.yaml at {status_path} must be a mapping at top level")
    return data
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_spec_helpers.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/_spec_helpers.py tests/test_spec_helpers.py
git commit -m "feat(project-state-spec): add today_iso and load_status helpers"
```

---

## Task 3: next_id helper

**Files:**
- Modify: `Tools/Skills/project-state-spec/tools/_spec_helpers.py`
- Modify: `tests/test_spec_helpers.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_spec_helpers.py`:

```python
from _spec_helpers import next_id  # noqa: E402


class TestNextId:
    def test_empty_returns_001(self):
        status = {"artifacts": [], "research_findings": [], "decisions": []}
        assert next_id(status, "R") == "R-001"
        assert next_id(status, "D") == "D-001"
        assert next_id(status, "LP") == "LP-001"
        assert next_id(status, "TP") == "TP-001"

    def test_continues_from_max(self):
        status = {
            "artifacts": [
                {"id": "R-001", "type": "research_finding"},
                {"id": "R-009", "type": "research_finding"},
                {"id": "D-005", "type": "decision"},
            ],
            "research_findings": [
                {"id": "R-001"},
                {"id": "R-009"},
            ],
            "decisions": [
                {"id": "D-005"},
            ],
        }
        assert next_id(status, "R") == "R-010"
        assert next_id(status, "D") == "D-006"

    def test_pools_independent(self):
        # Many R's must not affect the LP counter.
        status = {
            "artifacts": [{"id": f"R-{i:03d}"} for i in range(1, 50)] + [
                {"id": "LP-002"}
            ],
        }
        assert next_id(status, "LP") == "LP-003"
        assert next_id(status, "TP") == "TP-001"

    def test_handles_three_digit_pad(self):
        status = {"artifacts": [{"id": "R-099"}]}
        assert next_id(status, "R") == "R-100"

    def test_unknown_prefix_raises(self):
        with pytest.raises(ValueError):
            next_id({"artifacts": []}, "ZZ")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_spec_helpers.py::TestNextId -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement `next_id`**

Append to `Tools/Skills/project-state-spec/tools/_spec_helpers.py`:

```python
_VALID_PREFIXES = {"R", "D", "LP", "TP"}


def next_id(status: dict, prefix: str) -> str:
    """Return the next sequential id for ``prefix`` (one of R, D, LP, TP).

    Scans ``status`` for any string id matching ``<prefix>-<NNN>`` across the
    sections that may contain it (``artifacts``, plus the dedicated
    ``research_findings`` / ``decisions`` lists). Returns the next number
    zero-padded to 3 digits.
    """
    if prefix not in _VALID_PREFIXES:
        raise ValueError(
            f"Unknown id prefix: {prefix!r}. Expected one of {sorted(_VALID_PREFIXES)}."
        )

    pattern = _re.compile(rf"^{_re.escape(prefix)}-(\d+)$")
    seen: list[int] = []

    sections = ["artifacts"]
    if prefix == "R":
        sections.append("research_findings")
    if prefix == "D":
        sections.append("decisions")

    for section in sections:
        for entry in status.get(section, []) or []:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id")
            if not isinstance(entry_id, str):
                continue
            m = pattern.match(entry_id)
            if m:
                seen.append(int(m.group(1)))

    next_num = (max(seen) + 1) if seen else 1
    return f"{prefix}-{next_num:03d}"
```

(`_re` is the module alias chosen in Task 1 (`import re as _re`); both `slugify` and `next_id` use it consistently.)

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_spec_helpers.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/_spec_helpers.py tests/test_spec_helpers.py
git commit -m "feat(project-state-spec): add next_id helper"
```

---

## Task 4: find_artifact_by_topic helper

**Files:**
- Modify: `Tools/Skills/project-state-spec/tools/_spec_helpers.py`
- Modify: `tests/test_spec_helpers.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_spec_helpers.py`:

```python
from _spec_helpers import find_artifact_by_topic  # noqa: E402


class TestFindArtifactByTopic:
    @pytest.fixture
    def status(self):
        return {
            "artifacts": [
                {"id": "R-001", "type": "research_finding",
                 "path": "research/R-001-readme-guide-button.md"},
                {"id": "D-001", "type": "decision",
                 "path": "decisions/D-001-readme-guide-button.yaml"},
                {"id": "Plan.readme-guide-button", "type": "plan",
                 "path": "plan/2026-05-19-readme-guide-button-design.md"},
                {"id": "R-002", "type": "research_finding",
                 "path": "research/R-002-other-topic.md"},
            ]
        }

    def test_finds_research(self, status):
        found = find_artifact_by_topic(status, "readme-guide-button", "research_finding")
        assert found is not None
        assert found["id"] == "R-001"

    def test_finds_decision(self, status):
        found = find_artifact_by_topic(status, "readme-guide-button", "decision")
        assert found["id"] == "D-001"

    def test_finds_plan(self, status):
        found = find_artifact_by_topic(status, "readme-guide-button", "plan")
        assert found["id"] == "Plan.readme-guide-button"

    def test_returns_none_on_miss(self, status):
        assert find_artifact_by_topic(status, "nonexistent", "research_finding") is None

    def test_does_not_match_partial_substring(self, status):
        # "readme" alone must NOT match "readme-guide-button"
        assert find_artifact_by_topic(status, "readme", "research_finding") is None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_spec_helpers.py::TestFindArtifactByTopic -v`
Expected: ImportError.

- [ ] **Step 3: Implement helper**

Append to `Tools/Skills/project-state-spec/tools/_spec_helpers.py`:

```python
def find_artifact_by_topic(
    status: dict, topic: str, artifact_type: str
) -> dict | None:
    """Return the first artifact of ``artifact_type`` whose path matches ``topic``.

    Path-suffix matching rules:
      - research_finding : ``research/R-NNN-<topic>.md``
      - decision         : ``decisions/D-NNN-<topic>.yaml``
      - plan             : ``plan/<DATE>-<topic>-design.md``

    Returns None if no match.
    """
    suffix_map = {
        "research_finding": f"-{topic}.md",
        "decision":         f"-{topic}.yaml",
        "plan":             f"-{topic}-design.md",
    }
    if artifact_type not in suffix_map:
        raise ValueError(f"Unknown artifact_type: {artifact_type!r}")
    suffix = suffix_map[artifact_type]

    for entry in status.get("artifacts", []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != artifact_type:
            continue
        path = entry.get("path", "")
        if isinstance(path, str) and path.endswith(suffix):
            return entry
    return None
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_spec_helpers.py -v`
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/_spec_helpers.py tests/test_spec_helpers.py
git commit -m "feat(project-state-spec): add find_artifact_by_topic helper"
```

---

## Task 5: safe_write helper

**Files:**
- Modify: `Tools/Skills/project-state-spec/tools/_spec_helpers.py`
- Modify: `tests/test_spec_helpers.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_spec_helpers.py`:

```python
from _spec_helpers import safe_write, FileExistsRefuseError  # noqa: E402


class TestSafeWrite:
    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "c.txt"
        safe_write(target, "hello", force=False)
        assert target.read_text(encoding="utf-8") == "hello"

    def test_refuses_existing_without_force(self, tmp_path):
        target = tmp_path / "f.txt"
        target.write_text("old", encoding="utf-8")
        with pytest.raises(FileExistsRefuseError):
            safe_write(target, "new", force=False)
        assert target.read_text(encoding="utf-8") == "old"

    def test_overwrites_with_force(self, tmp_path):
        target = tmp_path / "f.txt"
        target.write_text("old", encoding="utf-8")
        safe_write(target, "new", force=True)
        assert target.read_text(encoding="utf-8") == "new"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_spec_helpers.py::TestSafeWrite -v`
Expected: ImportError.

- [ ] **Step 3: Implement helper**

Append to `Tools/Skills/project-state-spec/tools/_spec_helpers.py`:

```python
class FileExistsRefuseError(FileExistsError):
    """Raised by safe_write when the target file exists and force=False."""


def safe_write(path: Path | str, content: str, force: bool) -> None:
    """Write ``content`` (UTF-8, LF) to ``path``.

    Creates parent directories. If ``path`` already exists and ``force`` is
    False, raises ``FileExistsRefuseError`` and writes nothing.
    """
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsRefuseError(
            f"Refusing to overwrite existing file: {path} (pass --force to override)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_spec_helpers.py -v`
Expected: 23 passed.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/_spec_helpers.py tests/test_spec_helpers.py
git commit -m "feat(project-state-spec): add safe_write helper"
```

---

## Task 6: scaffold_spec.py CLI skeleton + --stage status

**Files:**
- Create: `Tools/Skills/project-state-spec/tools/scaffold_spec.py`
- Test: `tests/test_scaffold_spec.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_scaffold_spec.py`:

```python
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
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_scaffold_spec.py::TestStatusStage -v`
Expected: FAIL — `scaffold_spec.py` does not exist yet.

- [ ] **Step 3: Implement CLI skeleton + status stage**

Create `Tools/Skills/project-state-spec/tools/scaffold_spec.py`:

```python
#!/usr/bin/env python3
"""project-state-spec scaffold script.

Owns all side effects for the project-state-spec skill:
  - ID allocation (R-NNN, D-NNN, LP-NNN, TP-NNN, Plan.<topic>)
  - File writes under PST conventions (research/, decisions/, plan/, prompts/)
  - approved_transitions.json construction
  - tools/apply_changes.py invocation

Usage: see argparse help.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make sibling _spec_helpers importable when the script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _spec_helpers import (  # noqa: E402
    StatusYamlMissingError,
    find_artifact_by_topic,
    load_status,
)


# ---------------------------------------------------------------------------
# Stage handlers
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    pst_root = Path(args.pst_root)
    try:
        status = load_status(pst_root)
    except StatusYamlMissingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    r = find_artifact_by_topic(status, args.topic, "research_finding")
    d = find_artifact_by_topic(status, args.topic, "decision")
    p = find_artifact_by_topic(status, args.topic, "plan")

    lp_count = 0
    tp_count = 0
    if p is not None:
        plan_id = p["id"]
        for entry in status.get("artifacts", []) or []:
            if not isinstance(entry, dict):
                continue
            depends = entry.get("depends_on") or []
            if entry.get("type") == "landing_prompt" and plan_id in depends:
                lp_count += 1
            if entry.get("type") == "test_prompt":
                # TP depends on its LP; check whether ANY LP under this plan is in chain.
                for dep in depends:
                    parent = next(
                        (a for a in status.get("artifacts", []) or []
                         if isinstance(a, dict) and a.get("id") == dep
                         and a.get("type") == "landing_prompt"
                         and plan_id in (a.get("depends_on") or [])),
                        None,
                    )
                    if parent is not None:
                        tp_count += 1
                        break

    req_complete = r is not None and d is not None
    design_complete = req_complete and p is not None
    tasks_complete = (
        design_complete and lp_count > 0 and lp_count == tp_count
    )

    if not req_complete:
        next_stage = "requirement"
    elif not design_complete:
        next_stage = "design"
    elif not tasks_complete:
        next_stage = "tasks"
    else:
        next_stage = "done"

    out = {
        "topic": args.topic,
        "stages": {
            "requirement": {
                "complete": req_complete,
                "r_id": r["id"] if r else None,
                "d_id": d["id"] if d else None,
            },
            "design": {
                "complete": design_complete,
                "plan_id": p["id"] if p else None,
            },
            "tasks": {
                "complete": tasks_complete,
                "lp_count": lp_count,
                "tp_count": tp_count,
            },
        },
        "next_stage": next_stage,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_requirement(args: argparse.Namespace) -> int:
    raise NotImplementedError("requirement stage — implemented in Task 7")


def cmd_design(args: argparse.Namespace) -> int:
    raise NotImplementedError("design stage — implemented in Task 8")


def cmd_tasks(args: argparse.Namespace) -> int:
    raise NotImplementedError("tasks stage — implemented in Task 9")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scaffold_spec.py",
        description="project-state-spec scaffold script.",
    )
    p.add_argument("--stage", required=True,
                   choices=["requirement", "design", "tasks", "status"])
    p.add_argument("--topic", required=True,
                   help="kebab-case slug uniquely identifying this spec")
    p.add_argument("--pst-root", required=True,
                   help="PST project root (directory containing status/status.yaml)")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing files for this stage")
    p.add_argument("--r-content", help="path to tmpfile with R markdown body (stage=requirement)")
    p.add_argument("--d-content", help="path to tmpfile with D yaml body (stage=requirement)")
    p.add_argument("--plan-content", help="path to tmpfile with Plan markdown body (stage=design)")
    p.add_argument("--tasks-manifest", help="path to tmpfile with tasks JSON manifest (stage=tasks)")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.stage == "status":
        return cmd_status(args)
    if args.stage == "requirement":
        return cmd_requirement(args)
    if args.stage == "design":
        return cmd_design(args)
    if args.stage == "tasks":
        return cmd_tasks(args)
    parser.error(f"unknown stage: {args.stage}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_scaffold_spec.py::TestStatusStage -v`
Expected: 2 passed.

Also run the full helpers suite to confirm nothing regressed:

Run: `pytest tests/test_spec_helpers.py tests/test_scaffold_spec.py -v`
Expected: 25 passed.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/scaffold_spec.py tests/test_scaffold_spec.py
git commit -m "feat(project-state-spec): scaffold_spec CLI skeleton + status stage"
```

---

## Task 7: --stage requirement implementation

**Files:**
- Modify: `Tools/Skills/project-state-spec/tools/scaffold_spec.py`
- Modify: `tests/test_scaffold_spec.py`

- [ ] **Step 1: Append failing test**

Append to `tests/test_scaffold_spec.py`:

```python
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
        assert result.returncode != 0
        # Files should still exist (no rollback per Property 7).
        assert (tmp_path / "research" / "R-001-demo.md").is_file()
        assert (tmp_path / "decisions" / "D-001-demo.yaml").is_file()
        assert "boom" in result.stderr or "PST AUDIT" in result.stderr
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_scaffold_spec.py::TestRequirementStage -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement requirement stage**

Replace the body of `cmd_requirement` and add helpers in `Tools/Skills/project-state-spec/tools/scaffold_spec.py`. Add the following imports near the top:

```python
import json
import subprocess
from _spec_helpers import (
    FileExistsRefuseError,
    StatusYamlMissingError,
    find_artifact_by_topic,
    load_status,
    next_id,
    safe_write,
    slugify,
    today_iso,
)
```

(Replace the existing partial import. Keep `find_artifact_by_topic`, `load_status`, `StatusYamlMissingError` from before.)

Add these helpers above `cmd_requirement`:

```python
def _topic_title(topic: str) -> str:
    """Convert kebab-case slug to Title Case for display."""
    return " ".join(word.capitalize() for word in topic.split("-"))


def _write_transitions_and_apply(
    pst_root: Path,
    transitions: list[dict],
    event_summary: str,
    event_type: str,
) -> None:
    """Write approved_transitions.json then invoke apply_changes.py.

    Raises subprocess.CalledProcessError on apply_changes failure.
    """
    cache_dir = pst_root / "status" / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "event_summary": event_summary,
        "event_type": event_type,
        "transitions": transitions,
    }
    (cache_dir / "approved_transitions.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    apply_script = pst_root / "tools" / "apply_changes.py"
    if not apply_script.is_file():
        raise FileNotFoundError(
            f"apply_changes.py not found at {apply_script}. "
            "Run PST INIT to create the tools/ directory."
        )
    subprocess.run(
        [sys.executable, str(apply_script), "--project", str(pst_root)],
        check=True,
    )
```

Now implement `cmd_requirement`:

```python
def cmd_requirement(args: argparse.Namespace) -> int:
    if not args.r_content or not args.d_content:
        print("ERROR: --stage requirement requires --r-content and --d-content",
              file=sys.stderr)
        return 2

    pst_root = Path(args.pst_root)
    try:
        status = load_status(pst_root)
    except StatusYamlMissingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    topic = slugify(args.topic)

    # Allocate ids.
    r_id = next_id(status, "R")
    d_id = next_id(status, "D")
    title = _topic_title(topic)

    r_path_rel = f"research/{r_id}-{topic}.md"
    d_path_rel = f"decisions/{d_id}-{topic}.yaml"
    r_path = pst_root / r_path_rel
    d_path = pst_root / d_path_rel

    r_body = Path(args.r_content).read_text(encoding="utf-8")
    d_body = Path(args.d_content).read_text(encoding="utf-8")

    r_full = f"# {r_id}: {title}\n\n{r_body.lstrip()}"
    d_full = (
        f"id: {d_id}\n"
        f"title: \"{title}\"\n"
        f"status: draft\n"
        f"based_on: [{r_id}]\n"
        f"{d_body.lstrip()}"
    )

    try:
        safe_write(r_path, r_full, force=args.force)
        safe_write(d_path, d_full, force=args.force)
    except FileExistsRefuseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    transitions = [
        {"artifact": r_id, "type": "research_finding",
         "from": None, "to": "draft",
         "path": r_path_rel,
         "reason": f"project-state-spec scaffold: requirement stage for {topic}",
         "source": "project-state-spec"},
        {"artifact": d_id, "type": "decision",
         "from": None, "to": "draft",
         "path": d_path_rel,
         "depends_on": [r_id],
         "reason": f"project-state-spec scaffold: requirement stage for {topic}",
         "source": "project-state-spec"},
    ]
    try:
        _write_transitions_and_apply(
            pst_root,
            transitions,
            event_summary=f"project-state-spec scaffold: requirement stage for {topic}",
            event_type="spec_scaffold",
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ERROR: apply_changes.py failed: {exc}", file=sys.stderr)
        print("Files were written but status.yaml was not updated. "
              "Run PST AUDIT to reconcile.", file=sys.stderr)
        return 3

    print(json.dumps({
        "r_id": r_id, "d_id": d_id,
        "r_path": r_path_rel, "d_path": d_path_rel,
    }, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_scaffold_spec.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/scaffold_spec.py tests/test_scaffold_spec.py
git commit -m "feat(project-state-spec): implement requirement stage"
```

---

## Task 8: --stage design implementation

**Files:**
- Modify: `Tools/Skills/project-state-spec/tools/scaffold_spec.py`
- Modify: `tests/test_scaffold_spec.py`

- [ ] **Step 1: Append failing test**

Append to `tests/test_scaffold_spec.py`:

```python
class TestDesignStage:
    def _run_requirement(self, root):
        r_body = root / "_r.md"
        d_body = root / "_d.yaml"
        r_body.write_text("## Background\nx\n", encoding="utf-8")
        d_body.write_text(
            "problem_statement: x\ndecision: x\n"
            "acceptance_criteria: []\nrationale: x\n"
            "alternatives_considered: []\n",
            encoding="utf-8",
        )
        ok = run_script(
            "--stage", "requirement",
            "--topic", "demo",
            "--pst-root", str(root),
            "--r-content", str(r_body),
            "--d-content", str(d_body),
        )
        assert ok.returncode == 0, ok.stderr

    def test_design_creates_plan_and_registers(self, tmp_path):
        make_pst_skeleton(tmp_path)
        self._run_requirement(tmp_path)

        plan_body = tmp_path / "_plan.md"
        plan_body.write_text(
            "## Overview\nA small plan.\n\n## Architecture\n...\n",
            encoding="utf-8",
        )

        result = run_script(
            "--stage", "design",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
            "--plan-content", str(plan_body),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert out["plan_id"] == "Plan.demo"
        plan_path = tmp_path / out["plan_path"]
        assert plan_path.is_file()
        text = plan_path.read_text(encoding="utf-8")
        assert text.startswith("# Plan.demo:")
        assert "based_on" in text and "R-001" in text and "D-001" in text

    def test_design_without_requirement_exits_2(self, tmp_path):
        make_pst_skeleton(tmp_path)
        plan_body = tmp_path / "_plan.md"
        plan_body.write_text("## Overview\n", encoding="utf-8")
        result = run_script(
            "--stage", "design",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
            "--plan-content", str(plan_body),
        )
        assert result.returncode == 2
        assert "requirement" in result.stderr.lower()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_scaffold_spec.py::TestDesignStage -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement `cmd_design`**

Replace `cmd_design` in `Tools/Skills/project-state-spec/tools/scaffold_spec.py`:

```python
def cmd_design(args: argparse.Namespace) -> int:
    if not args.plan_content:
        print("ERROR: --stage design requires --plan-content", file=sys.stderr)
        return 2

    pst_root = Path(args.pst_root)
    try:
        status = load_status(pst_root)
    except StatusYamlMissingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    topic = slugify(args.topic)

    r = find_artifact_by_topic(status, topic, "research_finding")
    d = find_artifact_by_topic(status, topic, "decision")
    if r is None or d is None:
        print(
            f"ERROR: No R/D found for topic {topic!r}. "
            "Run --stage requirement first.",
            file=sys.stderr,
        )
        return 2

    plan_id = f"Plan.{topic}"
    plan_path_rel = f"plan/{today_iso()}-{topic}-design.md"
    plan_path = pst_root / plan_path_rel

    title = _topic_title(topic)
    body = Path(args.plan_content).read_text(encoding="utf-8")
    full = (
        f"# {plan_id}: {title}\n\n"
        f"<!-- based_on: [{r['id']}, {d['id']}] -->\n\n"
        f"{body.lstrip()}"
    )

    try:
        safe_write(plan_path, full, force=args.force)
    except FileExistsRefuseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    transitions = [{
        "artifact": plan_id, "type": "plan",
        "from": None, "to": "draft",
        "path": plan_path_rel,
        "depends_on": [r["id"], d["id"]],
        "reason": f"project-state-spec scaffold: design stage for {topic}",
        "source": "project-state-spec",
    }]
    try:
        _write_transitions_and_apply(
            pst_root,
            transitions,
            event_summary=f"project-state-spec scaffold: design stage for {topic}",
            event_type="spec_scaffold",
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ERROR: apply_changes.py failed: {exc}", file=sys.stderr)
        print("Files were written but status.yaml was not updated. "
              "Run PST AUDIT to reconcile.", file=sys.stderr)
        return 3

    print(json.dumps({
        "plan_id": plan_id, "plan_path": plan_path_rel,
    }, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_scaffold_spec.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/scaffold_spec.py tests/test_scaffold_spec.py
git commit -m "feat(project-state-spec): implement design stage"
```

---

## Task 9: --stage tasks implementation

**Files:**
- Modify: `Tools/Skills/project-state-spec/tools/scaffold_spec.py`
- Modify: `tests/test_scaffold_spec.py`

- [ ] **Step 1: Append failing test**

Append to `tests/test_scaffold_spec.py`:

```python
class TestTasksStage:
    def _run_requirement_and_design(self, root):
        r_body = root / "_r.md"
        d_body = root / "_d.yaml"
        plan_body = root / "_plan.md"
        r_body.write_text("## Background\nx\n", encoding="utf-8")
        d_body.write_text("problem_statement: x\ndecision: x\nacceptance_criteria: []\nrationale: x\nalternatives_considered: []\n", encoding="utf-8")
        plan_body.write_text("## Overview\nx\n", encoding="utf-8")
        assert run_script("--stage", "requirement", "--topic", "demo", "--pst-root", str(root), "--r-content", str(r_body), "--d-content", str(d_body)).returncode == 0
        assert run_script("--stage", "design", "--topic", "demo", "--pst-root", str(root), "--plan-content", str(plan_body)).returncode == 0

    def test_tasks_creates_lp_tp_pairs_and_readme(self, tmp_path):
        make_pst_skeleton(tmp_path)
        self._run_requirement_and_design(tmp_path)

        lp1 = tmp_path / "_lp1.md"
        tp1 = tmp_path / "_tp1.md"
        lp2 = tmp_path / "_lp2.md"
        tp2 = tmp_path / "_tp2.md"
        for f in (lp1, tp1, lp2, tp2):
            f.write_text(f"# Goal\nbody for {f.name}\n", encoding="utf-8")

        manifest = tmp_path / "_manifest.json"
        manifest.write_text(json.dumps({
            "tasks": [
                {"slug": "alpha", "lp_content": str(lp1), "tp_content": str(tp1),
                 "validates_ac": ["AC-1"], "validates_property": ["P1"]},
                {"slug": "beta", "lp_content": str(lp2), "tp_content": str(tp2),
                 "validates_ac": ["AC-2"], "validates_property": ["P2"]},
            ],
            "lp_sequence": ["alpha", "beta"],
            "coding_standards": "- Use 4 spaces.\n- No tabs.\n",
        }), encoding="utf-8")

        result = run_script(
            "--stage", "tasks",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
            "--tasks-manifest", str(manifest),
        )
        assert result.returncode == 0, result.stderr
        out = json.loads(result.stdout)
        assert len(out["tasks"]) == 2
        assert out["tasks"][0]["lp_id"] == "LP-001"
        assert out["tasks"][0]["tp_id"] == "TP-001"
        assert out["tasks"][1]["lp_id"] == "LP-002"
        assert out["tasks"][1]["tp_id"] == "TP-002"

        # Files exist.
        assert (tmp_path / "prompts" / "landing" / "LP-001-alpha.md").is_file()
        assert (tmp_path / "prompts" / "landing" / "LP-002-beta.md").is_file()
        assert (tmp_path / "prompts" / "test" / "TP-001-alpha.md").is_file()
        assert (tmp_path / "prompts" / "test" / "TP-002-beta.md").is_file()

        readme = (tmp_path / "prompts" / "landing" / "README.md").read_text(encoding="utf-8")
        assert "## LP 序列" in readme
        assert "LP-001-alpha -> LP-002-beta" in readme
        assert "## Coding Standards" in readme
        assert "Use 4 spaces" in readme
        # Front-matter contains source_root.
        assert readme.startswith("---")
        assert "source_root:" in readme

        # Property 5: every transition recorded in the change_event carries
        # source="project-state-spec".
        # Property 8: every TP depends_on entry references an LP.
        import yaml as _yaml
        status = _yaml.safe_load((tmp_path / "status" / "status.yaml").read_text(encoding="utf-8"))
        events = status.get("change_events", [])
        assert events, "no change_events recorded"
        last = events[-1]
        srcs = {t.get("source") for t in last["transitions"]}
        assert srcs == {"project-state-spec"}, srcs
        tps = [t for t in last["transitions"] if t.get("type") == "test_prompt"]
        assert tps, "no TP transitions recorded"
        for tp in tps:
            assert any(d.startswith("LP-") for d in tp["depends_on"])

    def test_tasks_without_design_exits_2(self, tmp_path):
        make_pst_skeleton(tmp_path)
        manifest = tmp_path / "_manifest.json"
        manifest.write_text(json.dumps({"tasks": [], "lp_sequence": []}), encoding="utf-8")
        result = run_script(
            "--stage", "tasks",
            "--topic", "demo",
            "--pst-root", str(tmp_path),
            "--tasks-manifest", str(manifest),
        )
        assert result.returncode == 2
        assert "plan" in result.stderr.lower()

    def test_tasks_status_marks_done_when_all_present(self, tmp_path):
        make_pst_skeleton(tmp_path)
        self._run_requirement_and_design(tmp_path)
        lp1 = tmp_path / "_lp1.md"
        tp1 = tmp_path / "_tp1.md"
        lp1.write_text("body\n", encoding="utf-8")
        tp1.write_text("body\n", encoding="utf-8")
        manifest = tmp_path / "_manifest.json"
        manifest.write_text(json.dumps({
            "tasks": [{"slug": "alpha", "lp_content": str(lp1), "tp_content": str(tp1),
                       "validates_ac": [], "validates_property": []}],
            "lp_sequence": ["alpha"],
        }), encoding="utf-8")
        assert run_script("--stage", "tasks", "--topic", "demo", "--pst-root", str(tmp_path), "--tasks-manifest", str(manifest)).returncode == 0

        status_result = run_script("--stage", "status", "--topic", "demo", "--pst-root", str(tmp_path))
        assert status_result.returncode == 0
        info = json.loads(status_result.stdout)
        assert info["next_stage"] == "done"
        assert info["stages"]["tasks"]["lp_count"] == 1
        assert info["stages"]["tasks"]["tp_count"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_scaffold_spec.py::TestTasksStage -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement `cmd_tasks`**

Replace `cmd_tasks` in `Tools/Skills/project-state-spec/tools/scaffold_spec.py`:

```python
def cmd_tasks(args: argparse.Namespace) -> int:
    if not args.tasks_manifest:
        print("ERROR: --stage tasks requires --tasks-manifest", file=sys.stderr)
        return 2

    pst_root = Path(args.pst_root)
    try:
        status = load_status(pst_root)
    except StatusYamlMissingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    topic = slugify(args.topic)
    plan = find_artifact_by_topic(status, topic, "plan")
    if plan is None:
        print(
            f"ERROR: No Plan found for topic {topic!r}. "
            "Run --stage design first.",
            file=sys.stderr,
        )
        return 2
    plan_id = plan["id"]

    manifest = json.loads(Path(args.tasks_manifest).read_text(encoding="utf-8"))
    tasks: list[dict] = manifest.get("tasks", [])
    if not tasks:
        print("ERROR: tasks manifest contains no tasks", file=sys.stderr)
        return 2
    lp_sequence: list[str] = manifest.get("lp_sequence", [t["slug"] for t in tasks])
    coding_standards: str | None = manifest.get("coding_standards")

    # Allocate sequential ids in manifest order.
    base_lp = next_id(status, "LP")  # e.g. "LP-001"
    base_tp = next_id(status, "TP")
    base_lp_n = int(base_lp.split("-")[1])
    base_tp_n = int(base_tp.split("-")[1])

    written_pairs = []
    transitions: list[dict] = []
    for i, t in enumerate(tasks):
        lp_id = f"LP-{base_lp_n + i:03d}"
        tp_id = f"TP-{base_tp_n + i:03d}"
        slug = slugify(t["slug"])

        lp_path_rel = f"prompts/landing/{lp_id}-{slug}.md"
        tp_path_rel = f"prompts/test/{tp_id}-{slug}.md"
        lp_path = pst_root / lp_path_rel
        tp_path = pst_root / tp_path_rel

        lp_body = Path(t["lp_content"]).read_text(encoding="utf-8")
        tp_body = Path(t["tp_content"]).read_text(encoding="utf-8")

        validates_ac = t.get("validates_ac", [])
        validates_property = t.get("validates_property", [])
        meta_block = (
            f"<!-- validates_ac: {validates_ac} -->\n"
            f"<!-- validates_property: {validates_property} -->\n"
        )

        lp_full = f"# {lp_id}: {slug}\n\n{meta_block}\n{lp_body.lstrip()}"
        tp_full = f"# {tp_id}: {slug}\n\n{meta_block}\n{tp_body.lstrip()}"

        try:
            safe_write(lp_path, lp_full, force=args.force)
            safe_write(tp_path, tp_full, force=args.force)
        except FileExistsRefuseError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        transitions.append({
            "artifact": lp_id, "type": "landing_prompt",
            "from": None, "to": "draft",
            "path": lp_path_rel,
            "depends_on": [plan_id],
            "reason": f"project-state-spec scaffold: tasks stage for {topic}",
            "source": "project-state-spec",
        })
        transitions.append({
            "artifact": tp_id, "type": "test_prompt",
            "from": None, "to": "draft",
            "path": tp_path_rel,
            "depends_on": [lp_id],
            "reason": f"project-state-spec scaffold: tasks stage for {topic}",
            "source": "project-state-spec",
        })
        written_pairs.append({
            "slug": slug, "lp_id": lp_id, "tp_id": tp_id,
            "lp_path": lp_path_rel, "tp_path": tp_path_rel,
        })

    # Landing README.
    meta = status.get("meta", {}) or {}
    fm_source_root = meta.get("source_root") or "<未配置>"
    fm_scope = meta.get("scope")
    fm_pst_root = meta.get("pst_root")

    fm_lines = ["---", f'source_root: "{fm_source_root}"']
    if fm_scope:
        fm_lines.append("scope:")
        for s in fm_scope:
            fm_lines.append(f'  - "{s}"')
    if fm_pst_root:
        fm_lines.append(f'pst_root: "{fm_pst_root}"')
    fm_lines.append("---")
    front_matter = "\n".join(fm_lines)

    sequence_tokens = []
    for slug in lp_sequence:
        match = next((p for p in written_pairs if p["slug"] == slugify(slug)), None)
        if match:
            sequence_tokens.append(f"{match['lp_id']}-{match['slug']}")
    lp_seq_line = " -> ".join(sequence_tokens)

    standards_section = ""
    if coding_standards:
        standards_section = f"\n## Coding Standards\n\n{coding_standards.strip()}\n"

    readme_text = (
        f"{front_matter}\n\n"
        f"# Landing Prompts for {_topic_title(topic)}\n\n"
        f"## LP 序列\n\n"
        f"{lp_seq_line}\n"
        f"{standards_section}"
    )
    readme_path = pst_root / "prompts" / "landing" / "README.md"
    try:
        safe_write(readme_path, readme_text, force=True)
    except FileExistsRefuseError as exc:  # pragma: no cover - force=True
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if fm_source_root == "<未配置>":
        print(
            "WARNING: meta.source_root is missing or placeholder. "
            "Set it before running Execute-LandingPrompt.",
            file=sys.stderr,
        )

    try:
        _write_transitions_and_apply(
            pst_root,
            transitions,
            event_summary=f"project-state-spec scaffold: tasks stage for {topic}",
            event_type="spec_scaffold",
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ERROR: apply_changes.py failed: {exc}", file=sys.stderr)
        print("Files were written but status.yaml was not updated. "
              "Run PST AUDIT to reconcile.", file=sys.stderr)
        return 3

    print(json.dumps({"tasks": written_pairs}, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_scaffold_spec.py -v`
Expected: 10 passed.

Also re-run helpers suite to confirm nothing regressed:

Run: `pytest tests/ -v`
Expected: all green; the 25 helpers tests still pass.

- [ ] **Step 5: Commit**

```bash
git add Tools/Skills/project-state-spec/tools/scaffold_spec.py tests/test_scaffold_spec.py
git commit -m "feat(project-state-spec): implement tasks stage with LP/TP pairing"
```

---

## Task 10: Author content templates

**Files:**
- Create: `Tools/Skills/project-state-spec/templates/r_template.md`
- Create: `Tools/Skills/project-state-spec/templates/d_template.yaml`
- Create: `Tools/Skills/project-state-spec/templates/plan_template.md`
- Create: `Tools/Skills/project-state-spec/templates/lp_template.md`
- Create: `Tools/Skills/project-state-spec/templates/tp_template.md`

These templates are reference scaffolds the SKILL.md instructs the agent to follow when drafting content for each tmpfile passed to `scaffold_spec.py`. They are not consumed by the script directly.

- [ ] **Step 1: Write `r_template.md`**

Create `Tools/Skills/project-state-spec/templates/r_template.md`:

```markdown
## Background
<触发点：为什么现在做？谁在用、在什么场景下？>

## Current State
<现状描述：当前怎么实现的、相关代码/产物的指针、已观察到的痛点>

## Constraints
<技术：语言、框架、版本>
<性能：延迟、吞吐、内存上限>
<合规：安全、隐私、协议>
<风格：与项目现有规范保持一致的部分>

## References
<外部链接：文档、issue、相关文章>
<内部 artifact：相关的 R-NNN / D-NNN / Plan / LP / TP>
```

- [ ] **Step 2: Write `d_template.yaml`**

Create `Tools/Skills/project-state-spec/templates/d_template.yaml`:

```yaml
problem_statement: <一句话问题陈述>
decision: |
  <决定做什么。包含 1..N 个 User Story：
  As a <role>, I want <feature>, so that <benefit>.>
acceptance_criteria:
  - id: AC-1
    user_story: "As a <role>, I want <feature>, so that <benefit>."
    statements:
      - "WHEN <trigger>, THE system SHALL <action>."
      - "IF <condition>, THEN <action>."
      - "WHILE <state>, WHEN <trigger>, THE system SHALL <action>."
  - id: AC-2
    user_story: "..."
    statements:
      - "..."
rationale: <为什么这么决定，而不是其他方案>
alternatives_considered:
  - option: <方案 A>
    rejected_because: <为什么不选>
  - option: <方案 B>
    rejected_because: <为什么不选>
```

- [ ] **Step 3: Write `plan_template.md`**

Create `Tools/Skills/project-state-spec/templates/plan_template.md`:

```markdown
## Overview
<一段话：要做什么、整体方向、关键技术选型>

## Architecture
<Mermaid 图或文字描述：模块、组件、数据流>

## Components and Interfaces
### Component A
- **职责：** <一句话>
- **接口：** <props / 函数签名 / API>
- **内部状态：** <如有>

### Component B
...

## Data Models
<TypeScript / Python type 定义>

## Correctness Properties
### Property 1: <名字>
*For any* <input>, <component> SHALL <invariant>.
**Validates: AC-N**

## Error Handling
| 场景 | 处理 |
|---|---|

## Testing Strategy
- Property tests: <列出 Property → AC 映射>
- Unit tests: <关键边界>
- Integration tests: <端到端>
```

- [ ] **Step 4: Write `lp_template.md`**

Create `Tools/Skills/project-state-spec/templates/lp_template.md`:

```markdown
# Goal
<一句话目标>

# Allowed Files
- <相对路径>
- <相对路径>

# Steps
1. <动作>
2. <动作>
3. <动作>

# Acceptance Gates
- 引用 AC：<AC-N>
- 引用 Property：<P-N>
- 通过条件：<具体可验证的条件>

# Handoff Plan
- 给下一个 LP 的事实：<F-1, F-2>
- 给下一个 LP 的约束：<C-1, C-2>
```

- [ ] **Step 5: Write `tp_template.md`**

Create `Tools/Skills/project-state-spec/templates/tp_template.md`:

```markdown
# Test Goal
<这个测试 prompt 的目标>

# Validates
- AC：<AC-N>
- Property：<P-N>

# Test Cases
## Property Tests
- 生成器：<输入空间>
- 断言：<必须成立的条件>
- 最少迭代：100

## Unit Tests
- <边界 1>
- <边界 2>

## Integration Tests
- <端到端 1>

# Pass Criteria
- 所有 property tests 通过 100 次以上迭代
- 所有 unit tests 通过
- 集成测试通过
```

- [ ] **Step 6: Verify files exist**

Run:

```bash
dir Tools\Skills\project-state-spec\templates
```

Expected: 5 files listed.

- [ ] **Step 7: Commit**

```bash
git add Tools/Skills/project-state-spec/templates/
git commit -m "feat(project-state-spec): add content templates for R/D/Plan/LP/TP"
```

---

## Task 11: Author SKILL.md

**Files:**
- Create: `Tools/Skills/project-state-spec/SKILL.md`

- [ ] **Step 1: Write the SKILL.md**

Create `Tools/Skills/project-state-spec/SKILL.md`:

```markdown
---
name: project-state-spec
description: "Three-stage spec authoring workflow (Requirement → Design → Task) that produces PST-conformant artifacts (R + D + Plan + LP + TP) on disk and registers them via apply_changes.py. Use when the user wants to author a new spec for a feature in a PST-managed project, or to resume an in-progress spec."
---

# project-state-spec — Three-Stage Spec Workflow

Guide the user through Requirement → Design → Task three stages, producing a complete PST artifact set (R + D + Plan + LP[] + TP[]) for one feature.

## Invocation

```text
Skill project-state-spec + new <topic>
Skill project-state-spec + continue <topic>
```

`<topic>` is a kebab-case slug uniquely naming this spec, e.g. `readme-guide-button`.

On `new`: start at Stage 1.
On `continue`: query `tools/scaffold_spec.py --stage status` and resume at `next_stage`. If `next_stage == done`, ask which stage the user wants to revise.

## Hard Preconditions

Before starting any stage:
1. The current workspace must contain `<pst_root>/status/status.yaml`. If missing, tell the user to run PST INIT first and STOP.
2. Resolve `<pst_root>` from the user's invocation context. If ambiguous, ask the user.

## Stage 1 — Requirement (produces R + D)

### Step 1.1 — Probe
Ask the user, ONE AT A TIME:
1. One-sentence goal of this feature?
2. Trigger / pain point — why now?
3. Who is the user, in what scenario?
4. Existing constraints (tech stack, performance targets, compliance)?

Do not write anything yet.

### Step 1.2 — Draft R
Read `templates/r_template.md`. Compose a markdown body following that structure.
- `## Background`: trigger and context
- `## Current State`: facts about the existing system, code/artifact pointers
- `## Constraints`: tech / performance / compliance / style
- `## References`: external links + internal artifact IDs

Show the draft to the user and ask for confirmation. Iterate until they approve.

### Step 1.3 — Draft D
Read `templates/d_template.yaml`. Compose a yaml body. **Critical:** every Acceptance Criterion's `statements` MUST use EARS keywords (SHALL, WHEN, IF, WHILE). Self-check before showing the draft. If a statement does not contain SHALL, rewrite it.

Show the draft to the user. Iterate until approved.

### Step 1.4 — Scaffold
Write the approved R body to a tmpfile and the approved D body to a tmpfile, then invoke:

```text
python <pst_root>/Tools/Skills/project-state-spec/tools/scaffold_spec.py \
    --stage requirement \
    --topic <topic> \
    --pst-root <pst_root> \
    --r-content <r-tmpfile> \
    --d-content <d-tmpfile>
```

(If the script lives in a different absolute path because the skill was installed via `install_skills.py`, use that path. The skill installation directory is typically `~/.kiro/skills/project-state-spec/`.)

Parse the JSON output. Tell the user the allocated `R-NNN` and `D-NNN` ids.

### Step 1.5 — Pause Gate
Ask: **"Requirement stage complete (R-NNN + D-NNN registered as draft). Continue to Design? Or pause here?"**

If pause → STOP. Tell the user they can resume with `Skill project-state-spec + continue <topic>`.

## Stage 2 — Design (produces Plan)

### Step 2.1 — Load context
Read the R-NNN and D-NNN files just written. Read relevant code regions in `meta.source_root` to understand the current implementation surface.

### Step 2.2 — Propose architectures
Present 2–3 architecture options. For each: trade-offs, recommendation, reasoning. User picks one.

### Step 2.3 — Draft Plan
Read `templates/plan_template.md`. Compose a markdown body following that structure. Every Property MUST include a `**Validates: AC-N**` line referencing a specific AC from D.

Show the draft. Iterate until approved.

### Step 2.4 — Scaffold
Write the approved Plan body to a tmpfile, then:

```text
python <scaffold_spec.py> --stage design --topic <topic> --pst-root <pst_root> --plan-content <plan-tmpfile>
```

Parse JSON, tell user the `Plan.<topic>` id.

### Step 2.5 — Pause Gate
Ask: **"Design stage complete. Continue to Tasks? Or pause here?"**

## Stage 3 — Tasks (produces LP[] + TP[])

### Step 3.1 — Decompose
Read the Plan. Propose a task list. Each task is one cohesive unit of work with clear file boundaries. For each task, list:
- slug (kebab-case)
- one-sentence description
- which AC ids it validates
- which Property ids it validates

Self-check: every task references at least one AC. If not, ask the user; possibly the AC is missing from D and should be added (in which case go back to Stage 1 in --force mode).

User confirms task list.

### Step 3.2 — Draft LP + TP for each task
For each task, read `templates/lp_template.md` and `templates/tp_template.md`. Draft both. Show drafts in batches. Iterate until approved.

### Step 3.3 — Compose tasks manifest
Build a JSON manifest:

```json
{
  "tasks": [
    {"slug": "...", "lp_content": "<tmpfile>", "tp_content": "<tmpfile>",
     "validates_ac": [...], "validates_property": [...]},
    ...
  ],
  "lp_sequence": ["slug1", "slug2", ...],
  "coding_standards": "<optional>"
}
```

If the user has project-wide coding standards (check `.kiro/steering/` or ask), include them.

### Step 3.4 — Scaffold
```text
python <scaffold_spec.py> --stage tasks --topic <topic> --pst-root <pst_root> --tasks-manifest <manifest-tmpfile>
```

Parse JSON. Tell the user every LP and TP id allocated.

### Step 3.5 — Closing
Tell the user:
- Spec is complete and registered in `status.yaml` as `draft` artifacts.
- To execute: `Skill Execute-LandingPrompt + <pst_root>/prompts/landing/LP-001-<slug>.md`.
- After hand-edits to any artifact, run PST AUDIT to reconcile.

## Continue Command

When the user invokes `continue <topic>`:

1. Run `--stage status` and parse JSON.
2. Look at `next_stage`:
   - `requirement` → start at Stage 1.1
   - `design` → start at Stage 2.1
   - `tasks` → start at Stage 3.1
   - `done` → tell the user the spec is complete, ask if they want to revise a stage. If yes, use `--force` for that stage.

## Self-Checks (before invoking the script)

- All Acceptance Criteria use EARS keywords (SHALL, WHEN, IF, WHILE).
- Every Property has `**Validates: AC-N**`.
- Every task references at least one AC.
- LP file count == TP file count (each LP has its TP).
- No placeholders in drafts (`TBD`, `TODO`, `<...>` left unfilled).

## Error Handling

| Scenario | Behavior |
|---|---|
| status.yaml missing | Tell user to run PST INIT, STOP. |
| Script returns exit code 2 | Print stderr to user, ask how to proceed. |
| Script returns exit code 3 (apply_changes failure) | Tell user files were written but status.yaml is out of sync; run PST AUDIT. |
| User says "rewrite" at confirmation | Re-draft within stage; do NOT invoke script. |
| User wants to abort mid-stage | Acknowledge; what's been written remains; resume with `continue`. |

## What This Skill Does NOT Do

- Does not execute LPs (use `Execute-LandingPrompt`).
- Does not run PST AUDIT (run it manually or let the next AUDIT pick up changes).
- Does not edit `status.yaml` directly — only via `apply_changes.py`.
```

- [ ] **Step 2: Verify the front-matter parses**

Run a quick Python check (no test file needed; this is a one-off):

```python
python -c "import sys; sys.path.insert(0, 'Docs/tools'); from distribute_skill import parse_front_matter; meta, body = parse_front_matter(open('Tools/Skills/project-state-spec/SKILL.md', encoding='utf-8').read()); print('OK', meta['name'])"
```

Expected output: `OK project-state-spec`.

- [ ] **Step 3: Commit**

```bash
git add Tools/Skills/project-state-spec/SKILL.md
git commit -m "feat(project-state-spec): author SKILL.md conversation protocol"
```

---

## Task 12: Verify install_skills.py picks up the new skill

**Files:**
- Test: `tests/test_install_skills.py` (already exists; we add one assertion)

The existing `Tools/install_skills.py` discovers any subdirectory of `Tools/Skills/` that contains a `SKILL.md`. Verify the new skill is picked up and that its content survives the front-matter parse.

- [ ] **Step 1: Inspect existing test conventions**

Read `tests/test_install_skills.py`. Note how the test discovers existing skills.

```bash
type tests\test_install_skills.py | more
```

- [ ] **Step 2: Add a discovery test**

Append to `tests/test_install_skills.py` (or create a small additional test if the file's structure makes appending awkward):

```python
def test_project_state_spec_is_discovered():
    """Verify project-state-spec is present and parseable in Tools/Skills/."""
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo / "Tools"))
    sys.path.insert(0, str(repo / "Docs" / "tools"))
    from install_skills import discover_skills, load_skill, SKILLS_SOURCE_DIR  # type: ignore

    discovered = discover_skills(SKILLS_SOURCE_DIR)
    names = [d.name for d in discovered]
    assert "project-state-spec" in names

    skill_dir = next(d for d in discovered if d.name == "project-state-spec")
    skill = load_skill(skill_dir)
    assert skill.metadata["name"] == "project-state-spec"
    assert "Requirement" in skill.metadata["description"] or "Three-stage" in skill.metadata["description"]
    assert skill.body.strip().startswith("# project-state-spec")
```

- [ ] **Step 3: Run the test**

Run: `pytest tests/test_install_skills.py -v -k project_state_spec`
Expected: 1 passed.

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all previously passing tests still pass; new tests added in this plan (~28 new) all pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_install_skills.py
git commit -m "test(project-state-spec): verify install_skills discovers new skill"
```

---

## Task 13: Smoke test end-to-end on a tmp project

**Files:**
- None modified; this is a manual verification step.

- [ ] **Step 1: Build a tmp PST project**

```bash
mkdir Q:\tmp\pss-smoke
mkdir Q:\tmp\pss-smoke\status Q:\tmp\pss-smoke\status\.cache Q:\tmp\pss-smoke\tools
mkdir Q:\tmp\pss-smoke\research Q:\tmp\pss-smoke\decisions Q:\tmp\pss-smoke\plan
mkdir Q:\tmp\pss-smoke\prompts Q:\tmp\pss-smoke\prompts\landing Q:\tmp\pss-smoke\prompts\test
```

Write `Q:\tmp\pss-smoke\status\status.yaml`:

```yaml
meta:
  project_name: smoke
  source_root: "Q:/tmp/pss-smoke/src"
artifacts: []
research_findings: []
decisions: []
change_events: []
```

Copy a stub `apply_changes.py` (the same shape used in `test_scaffold_spec.py`) into `Q:\tmp\pss-smoke\tools\apply_changes.py`.

- [ ] **Step 2: Run requirement stage**

Create `Q:\tmp\rbody.md`, `Q:\tmp\dbody.yaml` with simple content. Then:

```bash
python Tools\Skills\project-state-spec\tools\scaffold_spec.py --stage requirement --topic smoke-test --pst-root Q:\tmp\pss-smoke --r-content Q:\tmp\rbody.md --d-content Q:\tmp\dbody.yaml
```

Expected: JSON with `r_id: R-001`, `d_id: D-001`. Files exist on disk.

- [ ] **Step 3: Run design stage**

Create `Q:\tmp\plan.md` with simple content.

```bash
python Tools\Skills\project-state-spec\tools\scaffold_spec.py --stage design --topic smoke-test --pst-root Q:\tmp\pss-smoke --plan-content Q:\tmp\plan.md
```

Expected: JSON with `plan_id: Plan.smoke-test`.

- [ ] **Step 4: Run tasks stage**

Create LP/TP tmpfiles and a manifest. Run:

```bash
python Tools\Skills\project-state-spec\tools\scaffold_spec.py --stage tasks --topic smoke-test --pst-root Q:\tmp\pss-smoke --tasks-manifest Q:\tmp\manifest.json
```

Expected: JSON listing LP-001/TP-001 (and more). README.md generated under `prompts/landing/`.

- [ ] **Step 5: Verify status query**

```bash
python Tools\Skills\project-state-spec\tools\scaffold_spec.py --stage status --topic smoke-test --pst-root Q:\tmp\pss-smoke
```

Expected: `next_stage: done`.

- [ ] **Step 6: Cleanup**

```bash
rmdir /s /q Q:\tmp\pss-smoke
del Q:\tmp\rbody.md Q:\tmp\dbody.yaml Q:\tmp\plan.md Q:\tmp\manifest.json
```

- [ ] **Step 7: No commit needed for the smoke test itself**

---

## Self-Review

**Spec coverage:**
- Architecture (skill + script + helpers) → Tasks 1–11 ✓
- Stage-to-artifact mapping (R+D / Plan / LP+TP) → Tasks 7, 8, 9 ✓
- CLI surface (4 stages) → Tasks 6, 7, 8, 9 ✓
- Helpers (`slugify`, `today_iso`, `load_status`, `next_id`, `find_artifact_by_topic`, `safe_write`) → Tasks 1–5 ✓
- Tasks manifest data model → Task 9 ✓
- Templates → Task 10 ✓
- SKILL.md conversation protocol → Task 11 ✓
- Property 1 (stage ordering) → covered by `test_design_without_requirement_exits_2` (Task 8) and `test_tasks_without_design_exits_2` (Task 9) ✓
- Property 2 (monotonic IDs) → `test_continues_from_max`, `test_pools_independent` (Task 3) ✓
- Property 3 (LP/TP 1:1) → `test_tasks_creates_lp_tp_pairs_and_readme` (Task 9) ✓
- Property 4 (status query) → `test_status_on_empty_project_says_requirement_next` (Task 6), `test_tasks_status_marks_done_when_all_present` (Task 9) ✓
- Property 5 (source attribution) → asserted in `test_tasks_creates_lp_tp_pairs_and_readme` (Task 9) ✓
- Property 6 (idempotency) → `test_repeated_without_force_exits_2` (Task 7) ✓
- Property 7 (no rollback on failure) → `test_apply_changes_failure_keeps_files` (Task 7) ✓
- Property 8 (depends_on chain) → asserted in `test_tasks_creates_lp_tp_pairs_and_readme` (Task 9) ✓
- Distribution → Task 12 ✓

**Stronger Property 5 + 8 assertions:** the assertions are folded into Task 9's test directly (no separate fix step needed).

**Placeholder scan:** No `TBD`/`TODO`/"implement later"/"similar to" found. Templates contain `<...>` placeholders intentionally — these are part of the template content for the agent to fill, not plan placeholders. ✓

**Type consistency:**
- `slugify` used same way in helpers, scaffold_spec, manifest task slug normalization ✓
- `next_id` returns `f"{prefix}-{NNN:03d}"` consistently ✓
- `find_artifact_by_topic` uses `artifact_type` matching `type` field used in `apply_changes` stub ✓
- Exit codes: 0 success / 2 user error / 3 apply_changes failure — used consistently across all stages ✓
- `--pst-root` used consistently as the CLI flag name in script and tests ✓

**Inline fix applied:** The Property 5/8 assertions are listed in the self-review. When implementing Task 9, add them to the test as shown.

---

## Execution Handoff

Plan complete and saved to `Docs/plans/2026-05-19-project-state-spec.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
