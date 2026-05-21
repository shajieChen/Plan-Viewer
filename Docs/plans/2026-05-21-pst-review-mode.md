# PST §11 REVIEW Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a §11 REVIEW Mode to project-state-tracker that audits ready LandingPrompts against their Plan's Acceptance Criteria and architecture design intent.

**Architecture:** A new Python tool (`review_quality.py`) extracts structured context from status.yaml + Plan/Decision/Result files. The agent then reads code and Result files to judge AC satisfaction and architecture conformance. Output goes to `views/review_report.md` + session summary.

**Tech Stack:** Python 3 (same as existing PST tools), Markdown skill files

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools\review_quality.py` | Create | Extract review context JSON from status.yaml + project files |
| `C:\Users\chenshajie\.kiro\skills\project-state-tracker\SKILL.md` | Modify | Add §2 routing + §11 REVIEW Mode definition |

---

### Task 1: Create review_quality.py — Core Structure and Status Loading

**Files:**
- Create: `C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools\review_quality.py`

- [ ] **Step 1: Create the file with imports and argument parsing**

```python
"""Extract review context for PST §11 REVIEW Mode.

Reads status.yaml, finds ready LandingPrompts, traces back to their Plan and
Decision artifacts, extracts Acceptance Criteria and architecture info, and
writes a structured JSON to status/.cache/review_context.json.

Usage:
    python review_quality.py --project <pst_root>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _yaml_compat as yaml


def main():
    ap = argparse.ArgumentParser(description="Extract review context for §11 REVIEW")
    ap.add_argument("--project", default=".", help="PST root directory")
    args = ap.parse_args()

    project = os.path.abspath(args.project)
    status_path = os.path.join(project, "status", "status.yaml")

    if not os.path.isfile(status_path):
        print(f"[review_quality] FAIL: status.yaml not found at {status_path}", file=sys.stderr)
        sys.exit(2)

    with open(status_path, "r", encoding="utf-8") as f:
        status = yaml.load(f.read()) or {}

    meta = status.get("meta") or {}
    artifacts = status.get("artifacts") or []

    # Build lookup indexes
    arts_by_id = {a["id"]: a for a in artifacts if isinstance(a, dict) and "id" in a}

    # Find ready LPs
    ready_lps = [
        a for a in artifacts
        if a.get("type") == "landing_prompt" and a.get("status") == "ready"
    ]

    if not ready_lps:
        # Write empty context and exit cleanly
        _write_context(project, meta, [], None)
        print("[review_quality] No ready LPs found. Nothing to review.")
        sys.exit(0)

    # TODO: will be filled in Task 2 and Task 3
    print(f"[review_quality] Found {len(ready_lps)} ready LP(s)")


def _write_context(project: str, meta: dict, ready_lps: list, architecture: dict | None):
    """Write review_context.json to status/.cache/."""
    cache_dir = os.path.join(project, "status", ".cache")
    os.makedirs(cache_dir, exist_ok=True)
    out_path = os.path.join(cache_dir, "review_context.json")
    context = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_name": meta.get("project_name", "unknown"),
        "ready_lps": ready_lps,
        "architecture": architecture,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2, ensure_ascii=False)
    print(f"[review_quality] Context written to {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script runs without error on a project with no ready LPs**

Run: `python C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools\review_quality.py --project Q:\Plan_Viewer\Docs`
Expected: Prints "No ready LPs found" and exits 0. Creates `status/.cache/review_context.json` with empty `ready_lps`.

- [ ] **Step 3: Commit**

```bash
git add tools/review_quality.py
git commit -m "feat(pst): add review_quality.py skeleton with status loading"
```

---

### Task 2: Add Plan/Decision Tracing Logic

**Files:**
- Modify: `C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools\review_quality.py`

- [ ] **Step 1: Add the `_trace_plan` function**

Insert after the `_write_context` function:

```python
def _trace_plan(art: dict, arts_by_id: dict) -> dict | None:
    """Walk depends_on to find the first Plan artifact. BFS, max depth 3."""
    queue = list(art.get("depends_on") or [])
    visited = set()
    depth = 0
    while queue and depth < 3:
        next_queue = []
        for dep_id in queue:
            if dep_id in visited:
                continue
            visited.add(dep_id)
            dep = arts_by_id.get(dep_id)
            if dep and dep.get("type") == "plan":
                return dep
            if dep:
                next_queue.extend(dep.get("depends_on") or [])
        queue = next_queue
        depth += 1
    return None


def _trace_decision(plan_art: dict, arts_by_id: dict) -> dict | None:
    """From a Plan artifact, find the first Decision in depends_on."""
    for dep_id in plan_art.get("depends_on") or []:
        dep = arts_by_id.get(dep_id)
        if dep and dep.get("type") == "decision":
            return dep
    return None
```

- [ ] **Step 2: Wire tracing into main() — replace the TODO comment**

Replace the `# TODO: will be filled in Task 2 and Task 3` block with:

```python
    lp_contexts = []
    plan_art = None  # Will hold the last found plan for architecture extraction

    for lp in ready_lps:
        lp_ctx = {
            "id": lp["id"],
            "title": lp.get("title", lp["id"]),
            "path": lp.get("path", ""),
            "plan_id": None,
            "plan_path": None,
            "decision_id": None,
            "decision_path": None,
            "acceptance_criteria": [],
            "result_files": [],
            "modified_files": [],
        }

        # Trace to Plan
        found_plan = _trace_plan(lp, arts_by_id)
        if found_plan:
            plan_art = found_plan
            lp_ctx["plan_id"] = found_plan["id"]
            lp_ctx["plan_path"] = found_plan.get("path")

            # Trace to Decision
            found_decision = _trace_decision(found_plan, arts_by_id)
            if found_decision:
                lp_ctx["decision_id"] = found_decision["id"]
                lp_ctx["decision_path"] = found_decision.get("path")

        lp_contexts.append(lp_ctx)

    # Architecture extraction and AC parsing will be added in Task 3
    _write_context(project, meta, lp_contexts, None)
    print(f"[review_quality] Processed {len(lp_contexts)} LP(s)")
```

- [ ] **Step 3: Commit**

```bash
git add tools/review_quality.py
git commit -m "feat(pst): add Plan/Decision tracing to review_quality.py"
```

---

### Task 3: Add AC Extraction, Result Matching, and Architecture Extraction

**Files:**
- Modify: `C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools\review_quality.py`

- [ ] **Step 1: Add AC extraction functions**

Insert after `_trace_decision`:

```python
def _extract_ac_from_decision(decision_path: str, project: str) -> list:
    """Parse acceptance_criteria from a Decision YAML file."""
    abs_path = os.path.join(project, decision_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return []
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    data = yaml.load(content)
    if not isinstance(data, dict):
        return []
    acs = []
    for ac_group in data.get("acceptance_criteria") or []:
        if isinstance(ac_group, dict):
            ac_id = ac_group.get("id", "")
            for stmt in ac_group.get("statements") or []:
                acs.append({
                    "id": ac_id,
                    "statement": stmt if isinstance(stmt, str) else str(stmt),
                    "validates_property": ac_group.get("validates_property"),
                })
    return acs


def _extract_ac_from_plan(plan_path: str, project: str) -> list:
    """Fallback: parse AC from Plan markdown (## Acceptance Criteria or ## Properties)."""
    abs_path = os.path.join(project, plan_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return []
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    acs = []
    # Look for ## Acceptance Criteria or ## Properties section
    pattern = r"^##\s+(?:Acceptance Criteria|Properties|验收标准)\s*\n(.*?)(?=^##|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        return []
    section = match.group(1)
    # Parse bullet items as AC statements
    ac_num = 0
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            ac_num += 1
            acs.append({
                "id": f"AC-{ac_num}",
                "statement": line[2:].strip(),
                "validates_property": None,
            })
    return acs
```

- [ ] **Step 2: Add Result file matching function**

```python
def _find_result_files(lp_id: str, project: str) -> list:
    """Find Result files for a given LP artifact ID, sorted newest first."""
    result_dir = os.path.join(project, "Result")
    if not os.path.isdir(result_dir):
        return []
    # LP ID may contain dots/dashes; match files starting with the ID
    prefix = lp_id.lower()
    matches = []
    for fn in os.listdir(result_dir):
        if fn.lower().startswith(prefix) and fn.endswith(".md"):
            matches.append(os.path.join("Result", fn))
    # Sort by timestamp in filename (YYYYMMDD-HHmmss), newest first
    matches.sort(reverse=True)
    return matches


def _extract_modified_files(result_path: str, project: str) -> list:
    """Parse '- 修改文件:' line from a Result file."""
    abs_path = os.path.join(project, result_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return []
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Match "- 修改文件:" or "- Modified files:" followed by file list
    pattern = r"[-*]\s*(?:修改文件|Modified files)\s*[:：]\s*(.*)"
    match = re.search(pattern, content)
    if not match:
        return []
    raw = match.group(1).strip()
    # Could be comma-separated or newline-separated
    files = [f.strip() for f in re.split(r"[,\n]", raw) if f.strip()]
    return files
```

- [ ] **Step 3: Add architecture extraction function**

```python
def _extract_architecture(plan_path: str | None, decision_path: str | None,
                          project: str) -> dict | None:
    """Extract architecture section from Plan and constraints from Decision."""
    arch = {
        "decision_summary": None,
        "plan_architecture_section": None,
        "key_constraints": [],
    }
    has_content = False

    # From Plan: extract ## Architecture / ## 架构 section
    if plan_path:
        abs_plan = os.path.join(project, plan_path.replace("/", os.sep))
        if os.path.isfile(abs_plan):
            with open(abs_plan, "r", encoding="utf-8") as f:
                plan_content = f.read()
            pattern = r"^##\s+(?:Architecture|架构)\s*\n(.*?)(?=^##|\Z)"
            match = re.search(pattern, plan_content, re.MULTILINE | re.DOTALL)
            if match:
                arch["plan_architecture_section"] = match.group(1).strip()
                has_content = True

    # From Decision: extract summary and constraints
    if decision_path:
        abs_dec = os.path.join(project, decision_path.replace("/", os.sep))
        if os.path.isfile(abs_dec):
            with open(abs_dec, "r", encoding="utf-8") as f:
                dec_content = f.read()
            dec_data = yaml.load(dec_content)
            if isinstance(dec_data, dict):
                arch["decision_summary"] = dec_data.get("title") or dec_data.get("summary")
                # Extract constraints from various possible fields
                constraints = dec_data.get("constraints") or []
                if isinstance(constraints, list):
                    arch["key_constraints"] = [str(c) for c in constraints]
                elif isinstance(constraints, str):
                    arch["key_constraints"] = [constraints]
                has_content = True

    return arch if has_content else None
```

- [ ] **Step 4: Wire everything into main() — update the LP processing loop**

Replace the `# Architecture extraction and AC parsing will be added in Task 3` comment and the `_write_context` call with:

```python
    # Extract AC for each LP
    for lp_ctx in lp_contexts:
        # Try Decision first, fall back to Plan
        if lp_ctx["decision_path"]:
            acs = _extract_ac_from_decision(lp_ctx["decision_path"], project)
            if not acs and lp_ctx["plan_path"]:
                acs = _extract_ac_from_plan(lp_ctx["plan_path"], project)
        elif lp_ctx["plan_path"]:
            acs = _extract_ac_from_plan(lp_ctx["plan_path"], project)
        else:
            acs = []
        lp_ctx["acceptance_criteria"] = acs

        # Find Result files
        lp_ctx["result_files"] = _find_result_files(lp_ctx["id"], project)

        # Extract modified files from most recent Result
        if lp_ctx["result_files"]:
            lp_ctx["modified_files"] = _extract_modified_files(
                lp_ctx["result_files"][0], project
            )

    # Extract architecture info (use the first plan found)
    architecture = None
    if plan_art:
        first_decision_path = None
        for lp_ctx in lp_contexts:
            if lp_ctx["decision_path"]:
                first_decision_path = lp_ctx["decision_path"]
                break
        architecture = _extract_architecture(
            plan_art.get("path"), first_decision_path, project
        )

    _write_context(project, meta, lp_contexts, architecture)
    print(f"[review_quality] Processed {len(lp_contexts)} LP(s), "
          f"{sum(len(lp['acceptance_criteria']) for lp in lp_contexts)} AC(s)")
```

- [ ] **Step 5: Run the tool to verify no import/syntax errors**

Run: `python C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools\review_quality.py --project Q:\Plan_Viewer\Docs`
Expected: Exits cleanly (no ready LPs in this project currently).

- [ ] **Step 6: Commit**

```bash
git add tools/review_quality.py
git commit -m "feat(pst): add AC extraction, Result matching, architecture extraction"
```

---

### Task 4: Add §2 Routing and §11 REVIEW Mode to SKILL.md

**Files:**
- Modify: `C:\Users\chenshajie\.kiro\skills\project-state-tracker\SKILL.md`

- [ ] **Step 1: Add "review" to §2 User-intent routing table**

In the `## §2 Mode Detection & Routing` section, find the user-intent routing table. After the last row (`"check handoff status" | — | Render handoff_view`), add:

```markdown
| "review" / "审计质量" / "quality check" / "review landing quality" / "review quality" | §11 | Ready LP quality audit |
```

- [ ] **Step 2: Add §11 REVIEW Mode section**

After the `## §10 scan_changes Path Scope (declaration)` section and before the `---` separator that precedes the Companion Reference, insert the complete §11 definition:

```markdown

---

## §11 REVIEW Mode — Landing Quality Audit

Read-only quality audit of ready LandingPrompts. Traces each ready LP back to its Plan and Decision, then evaluates AC satisfaction and architecture conformance through document-based reasoning.

**Core constraints:**
- Only reads — never modifies status.yaml, never triggers propagate/apply_changes
- Only audits `status == "ready"` LP artifacts
- Agent reads code and Result files for judgment; tool only extracts structured context
- Does not execute tests or run any code

### Preconditions

- `status/status.yaml` exists
- `tools/review_quality.py` exists (installed from PST skill tools/)
- At least one LP artifact with `status == "ready"`

### Pipeline

| Step | Action | Input | Output | Fail |
|------|--------|-------|--------|------|
| 1 | `python tools/review_quality.py --project <p>` | project path | `status/.cache/review_context.json` | No ready LP → report "无可审计对象" and exit |
| 2 | Agent reads review_context.json | JSON | Audit plan | — |
| 3 | **Phase 1: AC satisfaction** — for each ready LP, for each AC: read Result file + code snapshot → judge pass/partial/fail with one-line reason | Result + code | AC verdicts | Single AC unjudgeable → mark `inconclusive` |
| 4 | **Phase 2: Architecture conformance** — read Plan architecture section + Decision constraints + actual code structure → judge each dimension | Plan + Decision + code | Architecture verdicts | Decision missing → skip constraint check |
| 5 | **Phase 3: Overall grade** — combine Phase 1 + 2 into A/B/C/D grade + risks + recommendations (max 5) | Phase 1+2 results | Grade + report | — |
| 6 | Write `views/review_report.md` | All results | Persisted report | Write failure → session summary only |
| 7 | Output session summary | All results | Formatted markdown | — |

### Phase 1 — AC Satisfaction Protocol

For each AC in `review_context.json`:
1. Read the corresponding Result file sections (`## confirmed` + `## 当前 Prompt 执行结果`)
2. Read `modified_files` code snapshots (function signatures, class definitions, core logic)
3. Verdict:
   - `pass` — Result and code clearly satisfy the AC's SHALL statement
   - `partial` — Partially satisfied; edge cases or boundary conditions missing
   - `fail` — Not implemented or contradicts the AC
   - `inconclusive` — Cannot determine (missing Result, code deleted, etc.)
4. One-line reason citing specific code location or Result paragraph

**Token optimization:** When `modified_files` > 5, prioritize files whose names match AC keywords.

### Phase 2 — Architecture Conformance Protocol

1. Read `architecture.plan_architecture_section` (Plan's architecture description)
2. Read `architecture.decision_summary` + `architecture.key_constraints` (Decision's choices and constraints)
3. Read actual code file structure (directory tree + key module imports)
4. Judge each dimension:
   - **Module boundaries** — Do actual files/classes match the design's component split?
   - **Data flow** — Does data pass in the direction the design specifies?
   - **Responsibility separation** — Does each module only do what the design declares?
   - **Constraint adherence** — Are Decision constraints violated?
   - **Rejected alternatives** — Did any rejected approach sneak in?
5. Per dimension: `conformant` / `deviation` / `violation` + reason

### Phase 3 — Overall Grade

| Grade | Condition |
|-------|-----------|
| A (优秀) | All AC pass + all architecture dimensions conformant |
| B (良好) | ≥80% AC pass, zero fail + no architecture violation |
| C (合格) | ≥60% AC pass + no architecture violation |
| D (不合格) | <60% AC pass OR any architecture violation |

Also produce:
- **Key risks** — most impactful partial/fail AC or deviation
- **Recommendations** — concrete, actionable fix directions (max 5)

### Token Budget

| LP count | Strategy |
|----------|----------|
| 1–3 | Read all Result files + all modified_files in full |
| 4–8 | Per LP: latest Result + top 3 most relevant code files |
| >8 | Batch (5 LPs per batch), cache intermediates in `status/.cache/` |

### Output

**Session summary** (always emitted):
```
## Review Summary
Overall Grade: **<grade>**
AC Pass Rate: N/M (percent%)
Architecture: <worst dimension verdict>
Key Findings: ...
Top Recommendations: ...
Full report: views/review_report.md
```

**Persisted report** (`views/review_report.md`): Full detail with AC table per LP, architecture findings table, risks and recommendations. Overwritten on each review run.
```

- [ ] **Step 3: Verify the SKILL.md is well-formed**

Read the modified SKILL.md and confirm:
- §11 appears after §10 and before the Companion Reference section
- The routing table entry is correctly placed
- No broken markdown formatting

- [ ] **Step 4: Commit**

```bash
git add SKILL.md
git commit -m "feat(pst): add §11 REVIEW Mode to SKILL.md"
```

---

### Task 5: Integration Test — End-to-End Dry Run

**Files:**
- No new files created; this task validates the tool works correctly

- [ ] **Step 1: Run review_quality.py against Plan_Viewer project**

Run: `python C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools\review_quality.py --project Q:\Plan_Viewer\Docs`

Expected output: "No ready LPs found" (Plan_Viewer currently has no ready LP artifacts). Verify `Q:\Plan_Viewer\Docs\status\.cache\review_context.json` exists with `"ready_lps": []`.

- [ ] **Step 2: Verify JSON output structure**

Read `Q:\Plan_Viewer\Docs\status\.cache\review_context.json` and confirm it has:
- `generated_at` — valid ISO timestamp
- `project_name` — "Plan_Viewer"
- `ready_lps` — empty list
- `architecture` — null

- [ ] **Step 3: Verify the tool handles missing Result/ directory gracefully**

The Plan_Viewer project has no `Result/` directory. Confirm the tool does not crash and `result_files` would be `[]` for any LP.

- [ ] **Step 4: Verify the tool handles the existing Decision YAML format**

Run a quick parse test on the existing Decision file:

```bash
python -c "import sys; sys.path.insert(0, r'C:\Users\chenshajie\.kiro\skills\project-state-tracker\tools'); import _yaml_compat as yaml; data = yaml.load(open(r'Q:\Plan_Viewer\Docs\decisions\D-001-single-html-react-cdn.yaml', encoding='utf-8').read()); print(type(data), list(data.keys()) if isinstance(data, dict) else 'not dict')"
```

Expected: Prints the top-level keys of the Decision YAML, confirming the parser can handle it.

- [ ] **Step 5: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix(pst): integration test fixes for review_quality.py"
```

Only commit if changes were made. If everything passed cleanly, skip this step.

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Core structure + status loading | `tools/review_quality.py` (create) |
| 2 | Plan/Decision tracing logic | `tools/review_quality.py` (modify) |
| 3 | AC extraction + Result matching + architecture | `tools/review_quality.py` (modify) |
| 4 | §2 routing + §11 definition in SKILL.md | `SKILL.md` (modify) |
| 5 | Integration test dry run | (validation only) |

All tasks operate within `C:\Users\chenshajie\.kiro\skills\project-state-tracker\`. No changes to Execute-LandingPrompt, project-state-spec, or any project-level files (except the test validation reads).
