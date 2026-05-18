# PST README Auto-Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automatic README generation to render_status.py so that any Agent can understand the project structure, artifact states, and dependency graph by reading a single file.

**Architecture:** Two new render functions in render_status.py — `render_project_readme()` for the PST root index and `render_landing_readme()` for the ELP-compatible landing prompt README. Both are called in `main()` after existing views. A helper `build_dependency_graph()` constructs the text-based dependency visualization, and `topological_sort_lps()` orders LP artifacts for the sequence section.

**Tech Stack:** Python 3, PyYAML (already a dependency), pathlib, existing render_status.py patterns.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `Docs/tools/render_status.py` | Modify | Add 4 new functions + update main() |
| `Docs/tools/tests/test_render_readme.py` | Create | Unit tests for all new functions |
| `Docs/status/status.yaml` | Modify | Add meta fields: source_root, scope, pst_root, coding_standards |
| `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` | Modify | Update §1, §3A, §6G |

---

### Task 1: Update status.yaml meta schema

**Files:**
- Modify: `Docs/status/status.yaml` (meta section, lines 4-10)

- [ ] **Step 1: Add new meta fields to status.yaml**

Add `source_root`, `scope`, `pst_root`, and `coding_standards` to the existing meta block:

```yaml
meta:
  project_name: "Plan_Viewer"
  created: "2026-05-14T00:00:00Z"
  last_updated: "2026-05-14T00:00:00Z"
  total_artifacts: 3
  total_research: 1
  total_blockers: 0
  hotspots: []
  source_root: "Q:\\Plan_Viewer"
  scope:
    - "Q:\\Plan_Viewer"
    - "Q:\\Plan_Viewer\\Docs"
  pst_root: "Q:\\Plan_Viewer\\Docs"
  coding_standards: "Follow existing patterns. Match surrounding file style."
```

- [ ] **Step 2: Validate YAML parses correctly**

Run: `python -c "import yaml; yaml.safe_load(open('Docs/status/status.yaml', encoding='utf-8')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add Docs/status/status.yaml
git commit -m "feat(pst): add source_root, scope, pst_root, coding_standards to meta"
```

---

### Task 2: Implement build_dependency_graph() helper

**Files:**
- Modify: `Docs/tools/render_status.py` (add function before `main()`)
- Create: `Docs/tools/tests/test_render_readme.py`

- [ ] **Step 1: Write the failing test**

Create `Docs/tools/tests/test_render_readme.py`:

```python
#!/usr/bin/env python3
"""Tests for README rendering functions in render_status.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from render_status import build_dependency_graph, topological_sort_lps


class TestBuildDependencyGraph:
    def test_simple_chain(self):
        """R-001 <- D-001 <- Plan.x"""
        status = {
            "artifacts": [
                {"id": "Plan.x", "type": "plan", "status": "draft", "depends_on": ["D-001"]},
            ],
            "research_findings": [
                {"id": "R-001", "title": "Research", "status": "reviewed"},
            ],
            "decisions": [
                {"id": "D-001", "title": "Decision", "status": "accepted", "based_on": ["R-001"]},
            ],
        }
        result = build_dependency_graph(status)
        assert "R-001" in result
        assert "D-001" in result
        assert "Plan.x" in result
        assert "←" in result

    def test_no_dependencies(self):
        """Single artifact with no deps."""
        status = {
            "artifacts": [
                {"id": "R-001", "type": "research", "status": "draft", "depends_on": []},
            ],
            "research_findings": [],
            "decisions": [],
        }
        result = build_dependency_graph(status)
        assert "R-001" in result

    def test_empty_artifacts(self):
        """No artifacts at all."""
        status = {"artifacts": [], "research_findings": [], "decisions": []}
        result = build_dependency_graph(status)
        assert "无依赖关系" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestBuildDependencyGraph -v`
Expected: FAIL with `ImportError: cannot import name 'build_dependency_graph'`

- [ ] **Step 3: Implement build_dependency_graph()**

Add to `Docs/tools/render_status.py` before the `main()` function:

```python
def build_dependency_graph(status: dict) -> str:
    """Build a text-based dependency graph from all artifacts.

    Format: each line shows one edge as 'A ← B' meaning B depends_on A.
    Grouped by topological layer.
    """
    # Collect all artifact IDs and their depends_on
    all_nodes = {}
    edges = []

    for art in status.get("artifacts", []):
        all_nodes[art["id"]] = art.get("type", "artifact")
        for dep in art.get("depends_on", []):
            edges.append((dep, art["id"]))

    for rf in status.get("research_findings", []):
        all_nodes[rf["id"]] = "research"

    for dec in status.get("decisions", []):
        all_nodes[dec["id"]] = "decision"
        for dep in dec.get("based_on", []):
            edges.append((dep, dec["id"]))

    if not edges:
        if all_nodes:
            return "\n".join(f"- {nid} ({ntype})" for nid, ntype in sorted(all_nodes.items()))
        return "_无依赖关系_"

    # Build adjacency for topological layering
    children = {n: [] for n in all_nodes}
    parents = {n: set() for n in all_nodes}
    for src, dst in edges:
        if src in children:
            children[src].append(dst)
        if dst in parents:
            parents[dst].add(src)

    # Kahn's algorithm for layers
    layers = []
    remaining = set(all_nodes.keys())
    while remaining:
        layer = [n for n in remaining if not parents[n] - (set(all_nodes.keys()) - remaining)]
        if not layer:
            # Cycle detected — dump remaining as-is
            layer = sorted(remaining)
            layers.append(layer)
            break
        layers.append(sorted(layer))
        remaining -= set(layer)

    # Format edges grouped by target
    lines = []
    edge_set = set(edges)
    for layer in layers:
        for node in layer:
            deps_of_node = [src for src, dst in edge_set if dst == node]
            if deps_of_node:
                deps_str = ", ".join(sorted(deps_of_node))
                lines.append(f"{deps_str} ← {node}")
            else:
                lines.append(f"{node} (root)")

    if len(edges) > 15:
        lines.append("")
        lines.append("_(完整依赖图见 status/status.yaml)_")

    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestBuildDependencyGraph -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add Docs/tools/render_status.py Docs/tools/tests/test_render_readme.py
git commit -m "feat(pst): add build_dependency_graph() helper"
```

---

### Task 3: Implement topological_sort_lps() helper

**Files:**
- Modify: `Docs/tools/render_status.py` (add function before `main()`)
- Modify: `Docs/tools/tests/test_render_readme.py` (add test class)

- [ ] **Step 1: Write the failing test**

Append to `Docs/tools/tests/test_render_readme.py`:

```python
class TestTopologicalSortLps:
    def test_linear_chain(self):
        """LP-001 -> LP-002 -> LP-003"""
        artifacts = [
            {"id": "LP-003", "type": "landing_prompt", "depends_on": ["LP-002"]},
            {"id": "LP-001", "type": "landing_prompt", "depends_on": ["Plan.x"]},
            {"id": "LP-002", "type": "landing_prompt", "depends_on": ["LP-001"]},
        ]
        result = topological_sort_lps(artifacts)
        assert result == ["LP-001", "LP-002", "LP-003"]

    def test_no_lps(self):
        """No landing prompts in artifacts."""
        artifacts = [
            {"id": "Plan.x", "type": "plan", "depends_on": []},
        ]
        result = topological_sort_lps(artifacts)
        assert result == []

    def test_single_lp(self):
        """One LP with no LP dependencies."""
        artifacts = [
            {"id": "LP-001", "type": "landing_prompt", "depends_on": ["Plan.x"]},
        ]
        result = topological_sort_lps(artifacts)
        assert result == ["LP-001"]

    def test_cycle_fallback_to_sorted(self):
        """Cycle between LPs falls back to alphabetical."""
        artifacts = [
            {"id": "LP-002", "type": "landing_prompt", "depends_on": ["LP-001"]},
            {"id": "LP-001", "type": "landing_prompt", "depends_on": ["LP-002"]},
        ]
        result = topological_sort_lps(artifacts)
        # Cycle detected — fallback to sorted by ID
        assert result == ["LP-001", "LP-002"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestTopologicalSortLps -v`
Expected: FAIL with `ImportError` (function not yet exported)

- [ ] **Step 3: Implement topological_sort_lps()**

Add to `Docs/tools/render_status.py` before `main()`:

```python
def topological_sort_lps(artifacts: list) -> list:
    """Sort landing_prompt artifacts by depends_on topology.

    Only considers LP-to-LP dependencies. Non-LP dependencies are ignored
    for ordering purposes. Falls back to alphabetical on cycle detection.
    """
    lps = [a for a in artifacts if a.get("type") == "landing_prompt"]
    if not lps:
        return []

    lp_ids = {a["id"] for a in lps}
    # Build graph of LP-to-LP edges only
    in_degree = {a["id"]: 0 for a in lps}
    children = {a["id"]: [] for a in lps}

    for a in lps:
        for dep in a.get("depends_on", []):
            if dep in lp_ids:
                in_degree[a["id"]] += 1
                children[dep].append(a["id"])

    # Kahn's algorithm
    queue = sorted([nid for nid, deg in in_degree.items() if deg == 0])
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for child in sorted(children[node]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
        queue.sort()

    if len(result) != len(lps):
        # Cycle detected — fallback to alphabetical
        return sorted(lp_ids)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestTopologicalSortLps -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add Docs/tools/render_status.py Docs/tools/tests/test_render_readme.py
git commit -m "feat(pst): add topological_sort_lps() helper"
```

---

### Task 4: Implement render_project_readme()

**Files:**
- Modify: `Docs/tools/render_status.py` (add function before `main()`)
- Modify: `Docs/tools/tests/test_render_readme.py` (add test class)

- [ ] **Step 1: Write the failing test**

Append to `Docs/tools/tests/test_render_readme.py`:

```python
from render_status import render_project_readme
import tempfile
import os


class TestRenderProjectReadme:
    def test_full_output_structure(self, tmp_path):
        """Verify all sections are present in output."""
        # Create directory structure
        (tmp_path / "research").mkdir()
        (tmp_path / "research" / "R-001-test.md").write_text("x")
        (tmp_path / "decisions").mkdir()
        (tmp_path / "decisions" / "D-001-test.yaml").write_text("x")
        (tmp_path / "plan").mkdir()
        (tmp_path / "prompts" / "landing").mkdir(parents=True)
        (tmp_path / "prompts" / "test").mkdir(parents=True)
        (tmp_path / "status").mkdir()
        (tmp_path / "views").mkdir()
        (tmp_path / "tools").mkdir()

        status = {
            "meta": {
                "project_name": "TestProject",
                "last_updated": "2026-05-18T00:00:00Z",
                "total_artifacts": 2,
                "total_research": 1,
                "total_blockers": 0,
            },
            "artifacts": [
                {"id": "Plan.x", "type": "plan", "status": "draft",
                 "path": "plan/x.md", "depends_on": ["D-001"]},
            ],
            "research_findings": [
                {"id": "R-001", "title": "Research", "status": "reviewed",
                 "path": "research/R-001-test.md"},
            ],
            "decisions": [
                {"id": "D-001", "title": "Decision", "status": "accepted",
                 "path": "decisions/D-001-test.yaml", "based_on": ["R-001"]},
            ],
            "handoff_contexts": [],
            "blockers": [],
        }

        result = render_project_readme(status, tmp_path)

        assert "# TestProject — Project State Overview" in result
        assert "Auto-generated by project-state-tracker" in result
        assert "## 目录结构" in result
        assert "research/" in result
        assert "## Artifact 状态总览" in result
        assert "R-001" in result
        assert "## 依赖关系图" in result
        assert "## Handoff 上下文" in result
        assert "无活跃 handoff" in result
        assert "## Blockers" in result
        assert "无阻塞项" in result
        assert "## 快速导航" in result

    def test_with_blockers(self, tmp_path):
        """Blockers section shows open blockers."""
        for d in ["research", "decisions", "plan", "status", "views", "tools"]:
            (tmp_path / d).mkdir(parents=True, exist_ok=True)
        (tmp_path / "prompts" / "landing").mkdir(parents=True)
        (tmp_path / "prompts" / "test").mkdir(parents=True)

        status = {
            "meta": {"project_name": "T", "last_updated": "2026-01-01",
                     "total_artifacts": 0, "total_research": 0, "total_blockers": 1},
            "artifacts": [],
            "research_findings": [],
            "decisions": [],
            "handoff_contexts": [],
            "blockers": [
                {"id": "B-001", "title": "Missing API", "severity": "high",
                 "status": "open", "blocks": ["LP-001"]},
            ],
        }

        result = render_project_readme(status, tmp_path)
        assert "B-001" in result
        assert "Missing API" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestRenderProjectReadme -v`
Expected: FAIL with `ImportError: cannot import name 'render_project_readme'`

- [ ] **Step 3: Implement render_project_readme()**

Add to `Docs/tools/render_status.py` before `main()`:

```python
def render_project_readme(status: dict, project: Path) -> str:
    """Render the PST project root README.md.

    Contains: directory tree, artifact table, dependency graph,
    handoff contexts, blockers, and quick navigation links.
    """
    meta = status.get("meta", {})
    project_name = meta.get("project_name", "Unknown")
    last_updated = meta.get("last_updated", "N/A")

    lines = [
        f"# {project_name} — Project State Overview",
        "",
        "> Auto-generated by project-state-tracker. Do not hand-edit.",
        f"> Last updated: {last_updated}",
        "",
    ]

    # --- Directory tree ---
    lines.append("## 目录结构")
    lines.append("")
    lines.append("```")

    dir_descriptions = {
        "research": "调研事实与证据",
        "decisions": "基于调研的决策",
        "plan": "执行计划与设计",
        "prompts/landing": "实施 Prompt",
        "prompts/test": "验证 Prompt",
        "status": "状态单一真相源",
        "views": "只读派生视图",
        "tools": "Python 状态管理脚本",
    }

    for dir_rel, desc in dir_descriptions.items():
        dir_path = project / dir_rel
        if dir_path.exists():
            file_count = len([
                f for f in dir_path.iterdir()
                if f.is_file() and f.name != ".gitkeep"
            ])
            lines.append(f"{dir_rel + '/': <20} — {desc} ({file_count} files)")
        else:
            lines.append(f"{dir_rel + '/': <20} — {desc} (not created)")

    lines.append("```")
    lines.append("")

    # --- Artifact table ---
    lines.append("## Artifact 状态总览")
    lines.append("")

    all_artifacts = []
    for art in status.get("artifacts", []):
        all_artifacts.append(art)
    for rf in status.get("research_findings", []):
        all_artifacts.append({"id": rf["id"], "type": "research",
                              "status": rf.get("status", "?"),
                              "path": rf.get("path", "?")})
    for dec in status.get("decisions", []):
        all_artifacts.append({"id": dec["id"], "type": "decision",
                              "status": dec.get("status", "?"),
                              "path": dec.get("path", "?")})

    if all_artifacts:
        lines.append("| ID | Type | Status | Path |")
        lines.append("|----|------|--------|------|")
        for art in sorted(all_artifacts, key=lambda a: a.get("id", "")):
            lines.append(
                f"| {art.get('id', '?')} | {art.get('type', '?')} "
                f"| {art.get('status', '?')} | {art.get('path', '?')} |"
            )
    else:
        lines.append("_无已注册 artifact_")

    lines.append("")

    # --- Dependency graph ---
    lines.append("## 依赖关系图")
    lines.append("")
    lines.append("```")
    lines.append(build_dependency_graph(status))
    lines.append("```")
    lines.append("")

    # --- Handoff contexts ---
    lines.append("## Handoff 上下文")
    lines.append("")
    handoffs = status.get("handoff_contexts", [])
    if handoffs:
        lines.append("| HC | Producer | Status | Version | Consumers |")
        lines.append("|----|----------|--------|---------|-----------|")
        for hc in handoffs:
            consumers = ", ".join(hc.get("consumed_by", []))
            lines.append(
                f"| {hc.get('id', '?')} | {hc.get('producer', '?')} | "
                f"{hc.get('status', '?')} | {hc.get('version', 0)} | {consumers} |"
            )
    else:
        lines.append("_无活跃 handoff_")

    lines.append("")

    # --- Blockers ---
    lines.append("## Blockers")
    lines.append("")
    blockers = [b for b in status.get("blockers", []) if b.get("status") == "open"]
    if blockers:
        lines.append("| ID | Title | Severity | Blocks |")
        lines.append("|----|-------|----------|--------|")
        for b in blockers:
            blocks_str = ", ".join(b.get("blocks", []))
            lines.append(
                f"| {b.get('id', '?')} | {b.get('title', '?')} "
                f"| {b.get('severity', '?')} | {blocks_str} |"
            )
    else:
        lines.append("_无阻塞项_")

    lines.append("")

    # --- Quick navigation ---
    lines.append("## 快速导航")
    lines.append("")
    lines.append("- 完整状态数据: `status/status.yaml`")
    lines.append("- 变更日志: `views/change_log_view.md`")
    lines.append("- Prompt 执行链: `views/prompt_chain_view.md`")
    lines.append("- Handoff 状态: `views/handoff_view.md`")
    lines.append("- Agent 索引: `AGENTS.md`")

    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestRenderProjectReadme -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add Docs/tools/render_status.py Docs/tools/tests/test_render_readme.py
git commit -m "feat(pst): add render_project_readme() function"
```

---

### Task 5: Implement render_landing_readme()

**Files:**
- Modify: `Docs/tools/render_status.py` (add function before `main()`)
- Modify: `Docs/tools/tests/test_render_readme.py` (add test class)

- [ ] **Step 1: Write the failing test**

Append to `Docs/tools/tests/test_render_readme.py`:

```python
from render_status import render_landing_readme


class TestRenderLandingReadme:
    def test_generates_full_file_when_no_existing(self, tmp_path):
        """When no README exists, generates front-matter + body."""
        (tmp_path / "prompts" / "landing").mkdir(parents=True)

        status = {
            "meta": {
                "project_name": "TestProject",
                "last_updated": "2026-05-18T00:00:00Z",
                "source_root": "Q:\\TestProject",
                "scope": ["Q:\\TestProject", "Q:\\TestProject\\Docs"],
                "pst_root": "Q:\\TestProject\\Docs",
                "coding_standards": "Use 4-space indent.",
            },
            "artifacts": [
                {"id": "LP-001", "type": "landing_prompt", "status": "ready",
                 "depends_on": ["Plan.x"], "produces_handoffs": ["HC-001"]},
                {"id": "LP-002", "type": "landing_prompt", "status": "draft",
                 "depends_on": ["LP-001"], "produces_handoffs": []},
            ],
            "handoff_contexts": [
                {"id": "HC-001", "producer": "LP-001", "version": 1,
                 "status": "available",
                 "facts": ["fact one", "fact two"],
                 "constraints": ["must not break API"],
                 "consumed_by": ["LP-002"]},
            ],
        }

        result = render_landing_readme(status, tmp_path)

        # Front-matter
        assert result.startswith("---\n")
        assert "source_root:" in result
        assert "Q:\\TestProject" in result
        assert "pst_root:" in result
        # Body
        assert "## LP 序列" in result
        assert "LP-001 -> LP-002" in result
        assert "## Coding Standards" in result
        assert "Use 4-space indent." in result
        assert "## 当前 LP 状态" in result
        assert "## Handoff 上下文摘要" in result
        assert "fact one; fact two" in result

    def test_no_source_root_marks_unconfigured(self, tmp_path):
        """Missing source_root produces placeholder."""
        (tmp_path / "prompts" / "landing").mkdir(parents=True)

        status = {
            "meta": {"project_name": "T", "last_updated": "2026-01-01"},
            "artifacts": [],
            "handoff_contexts": [],
        }

        result = render_landing_readme(status, tmp_path)
        assert "<未配置>" in result

    def test_no_lps_shows_message(self, tmp_path):
        """No LP artifacts shows placeholder message."""
        (tmp_path / "prompts" / "landing").mkdir(parents=True)

        status = {
            "meta": {"project_name": "T", "last_updated": "2026-01-01",
                     "source_root": "/src"},
            "artifacts": [
                {"id": "Plan.x", "type": "plan", "status": "draft", "depends_on": []},
            ],
            "handoff_contexts": [],
        }

        result = render_landing_readme(status, tmp_path)
        assert "尚无已注册的 Landing Prompt" in result

    def test_no_coding_standards_omits_section(self, tmp_path):
        """Missing coding_standards means no section generated."""
        (tmp_path / "prompts" / "landing").mkdir(parents=True)

        status = {
            "meta": {"project_name": "T", "last_updated": "2026-01-01",
                     "source_root": "/src"},
            "artifacts": [],
            "handoff_contexts": [],
        }

        result = render_landing_readme(status, tmp_path)
        assert "## Coding Standards" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestRenderLandingReadme -v`
Expected: FAIL with `ImportError: cannot import name 'render_landing_readme'`

- [ ] **Step 3: Implement render_landing_readme()**

Add to `Docs/tools/render_status.py` before `main()`:

```python
def render_landing_readme(status: dict, project: Path) -> str:
    """Render prompts/landing/README.md with ELP-compatible front-matter.

    If the file already exists with user-written front-matter, only the
    body (after the second '---') is regenerated.
    """
    meta = status.get("meta", {})
    project_name = meta.get("project_name", "Unknown")
    last_updated = meta.get("last_updated", "N/A")
    source_root = meta.get("source_root", "<未配置>")
    scope = meta.get("scope", [source_root] if source_root != "<未配置>" else [])
    pst_root = meta.get("pst_root", str(project))
    coding_standards = meta.get("coding_standards")

    # --- Generate front-matter ---
    fm_lines = [
        "---",
        f'source_root: "{source_root}"',
        "scope:",
    ]
    for s in scope:
        fm_lines.append(f'  - "{s}"')
    fm_lines.append(f'pst_root: "{pst_root}"')
    fm_lines.append("---")

    frontmatter = "\n".join(fm_lines)

    # --- Generate body ---
    body_lines = [
        f"# {project_name} LandingPrompt",
        "",
        "> Auto-generated body by project-state-tracker. Front-matter preserved if pre-existing.",
        f"> Last updated: {last_updated}",
        "",
    ]

    # LP sequence
    body_lines.append("## LP 序列")
    body_lines.append("")
    artifacts = status.get("artifacts", [])
    lp_order = topological_sort_lps(artifacts)
    if lp_order:
        body_lines.append(" -> ".join(lp_order))
    else:
        body_lines.append("_尚无已注册的 Landing Prompt_")
    body_lines.append("")

    # Coding Standards (only if configured)
    if coding_standards:
        body_lines.append("## Coding Standards")
        body_lines.append("")
        body_lines.append(coding_standards)
        body_lines.append("")

    # LP status table
    body_lines.append("## 当前 LP 状态")
    body_lines.append("")
    lps = [a for a in artifacts if a.get("type") == "landing_prompt"]
    if lps:
        body_lines.append("| ID | Status | Depends On | Produces HC |")
        body_lines.append("|----|--------|------------|-------------|")
        for lp in sorted(lps, key=lambda a: a.get("id", "")):
            deps = ", ".join(lp.get("depends_on", []))
            hcs = ", ".join(lp.get("produces_handoffs", []))
            body_lines.append(f"| {lp['id']} | {lp.get('status', '?')} | {deps} | {hcs} |")
    else:
        body_lines.append("_尚无已注册的 Landing Prompt_")
    body_lines.append("")

    # Handoff summary
    body_lines.append("## Handoff 上下文摘要")
    body_lines.append("")
    handoffs = status.get("handoff_contexts", [])
    if handoffs:
        body_lines.append("| HC | Facts | Constraints | Consumed By |")
        body_lines.append("|----|-------|-------------|-------------|")
        for hc in handoffs:
            facts_str = "; ".join(hc.get("facts", []))
            constraints_str = "; ".join(hc.get("constraints", []))
            consumed_str = ", ".join(hc.get("consumed_by", []))
            body_lines.append(
                f"| {hc.get('id', '?')} | {facts_str} | {constraints_str} | {consumed_str} |"
            )
    else:
        body_lines.append("_无活跃 handoff_")

    body = "\n".join(body_lines) + "\n"

    return frontmatter + "\n\n" + body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestRenderLandingReadme -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add Docs/tools/render_status.py Docs/tools/tests/test_render_readme.py
git commit -m "feat(pst): add render_landing_readme() function"
```

---

### Task 6: Implement front-matter preservation and integrate into main()

**Files:**
- Modify: `Docs/tools/render_status.py` (add helper + update main())
- Modify: `Docs/tools/tests/test_render_readme.py` (add test class)

- [ ] **Step 1: Write the failing test for front-matter preservation**

Append to `Docs/tools/tests/test_render_readme.py`:

```python
from render_status import write_with_frontmatter_preservation


class TestFrontmatterPreservation:
    def test_preserves_existing_frontmatter(self, tmp_path):
        """Existing front-matter is kept, body from new content is used."""
        readme = tmp_path / "README.md"
        readme.write_text(
            '---\nsource_root: "Q:\\\\Custom"\nscope:\n  - "Q:\\\\Custom"\n---\n\n# Old body\n',
            encoding="utf-8",
        )

        # new_content includes its own front-matter (generated from meta)
        new_content = '---\nsource_root: "Q:\\\\Generated"\n---\n\n# New body\n\nNew content here.\n'
        write_with_frontmatter_preservation(readme, new_content)

        result = readme.read_text(encoding="utf-8")
        # Existing front-matter preserved
        assert 'source_root: "Q:\\Custom"' in result
        # New body used
        assert "# New body" in result
        assert "# Old body" not in result
        # Generated front-matter NOT present
        assert "Q:\\Generated" not in result

    def test_writes_full_content_when_no_file(self, tmp_path):
        """When file doesn't exist, writes full content as-is."""
        readme = tmp_path / "README.md"
        content = "---\nsource_root: /src\n---\n\n# Body\n"
        write_with_frontmatter_preservation(readme, content)

        result = readme.read_text(encoding="utf-8")
        assert result == content

    def test_writes_full_when_no_frontmatter(self, tmp_path):
        """Existing file without front-matter gets fully replaced."""
        readme = tmp_path / "README.md"
        readme.write_text("# Just a plain file\n", encoding="utf-8")

        new_content = "---\nsource_root: /src\n---\n\n# New\n"
        write_with_frontmatter_preservation(readme, new_content)

        result = readme.read_text(encoding="utf-8")
        assert result == new_content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestFrontmatterPreservation -v`
Expected: FAIL with `ImportError: cannot import name 'write_with_frontmatter_preservation'`

- [ ] **Step 3: Implement write_with_frontmatter_preservation()**

Add to `Docs/tools/render_status.py` before `main()`:

```python
def write_with_frontmatter_preservation(path: Path, new_content: str) -> None:
    """Write README, preserving existing YAML front-matter if present.

    new_content may include its own front-matter (generated from meta).
    If the file already exists with user-written front-matter, the existing
    front-matter is preserved and only the body from new_content is used.

    If the file doesn't exist or has no front-matter, writes new_content as-is.
    """
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing.startswith("---"):
            # Find the closing '---' in existing file
            second_marker = existing.find("---", 3)
            if second_marker != -1:
                frontmatter = existing[: second_marker + 3]
                # Extract body from new_content (skip its front-matter if present)
                new_body = new_content
                if new_content.startswith("---"):
                    new_second = new_content.find("---", 3)
                    if new_second != -1:
                        new_body = new_content[new_second + 3:].lstrip("\n")
                final = frontmatter + "\n\n" + new_body
                path.write_text(final, encoding="utf-8")
                return

    # No existing file or no front-matter — write as-is
    path.write_text(new_content, encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py::TestFrontmatterPreservation -v`
Expected: 3 passed

- [ ] **Step 5: Update main() to call the new render functions**

In `Docs/tools/render_status.py`, replace the end of `main()` (after the AGENTS.md rendering) with:

```python
    # Render AGENTS.md at project root
    agents_path = project / "AGENTS.md"
    with open(agents_path, "w", encoding="utf-8") as f:
        f.write(render_agents_md(status))
    print(f"  Rendered: {agents_path}")

    # Render project root README.md
    readme_content = render_project_readme(status, project)
    readme_path = project / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"  Rendered: {readme_path}")

    # Render prompts/landing/README.md (with front-matter preservation)
    landing_dir = project / "prompts" / "landing"
    landing_dir.mkdir(parents=True, exist_ok=True)
    landing_readme_path = landing_dir / "README.md"
    landing_full_content = render_landing_readme(status, project)
    # render_landing_readme returns full content (frontmatter + body).
    # write_with_frontmatter_preservation will keep existing frontmatter
    # if the file already exists, replacing only the body portion.
    write_with_frontmatter_preservation(landing_readme_path, landing_full_content)
    print(f"  Rendered: {landing_readme_path}")

    print(f"\nAll views regenerated ({len(views)} files + AGENTS.md + 2 READMEs).")
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest Docs/tools/tests/test_render_readme.py -v`
Expected: All tests pass (3 + 4 + 2 + 4 + 3 = 16 tests)

- [ ] **Step 7: Run render_status.py end-to-end**

Run: `python Docs/tools/render_status.py --project Docs`
Expected: Output includes `Rendered: ...README.md` lines for both READMEs. Verify files exist:
- `Docs/README.md` — contains project overview with directory tree
- `Docs/prompts/landing/README.md` — contains front-matter + LP info

- [ ] **Step 8: Commit**

```bash
git add Docs/tools/render_status.py Docs/tools/tests/test_render_readme.py
git commit -m "feat(pst): integrate README rendering into main() with frontmatter preservation"
```

---

### Task 7: Update PST Skill Prompt

**Files:**
- Modify: `Prompt_project-state-tracker_生成项目使用的Workflow_State.md`

- [ ] **Step 1: Update §1 Core Constraints — Write boundaries**

Add to the Write boundaries list:

```markdown
- `README.md`, `prompts/landing/README.md` — regenerated by `render_status.py`
```

- [ ] **Step 2: Update §3A INIT_FROM_DOCS — scaffold step**

In Step 1, add `prompts/landing/` to the scaffold list:

```markdown
1. Scaffold: `status/`, `status/.cache/`, `views/`, `tools/`, `prompts/landing/`, `prompts/test/`
```

- [ ] **Step 3: Add meta field documentation**

At the end of §7 Hard Constraints, add a note about the new meta fields:

```markdown
**meta schema extensions (for README generation):**
- `source_root`: string, optional — source code root directory for ELP
- `scope`: string[], optional — allowed operation paths for ELP
- `pst_root`: string, optional — PST management root (defaults to status.yaml parent)
- `coding_standards`: string, optional — coding conventions for ELP to follow
```

- [ ] **Step 4: Commit**

```bash
git add "Prompt_project-state-tracker_生成项目使用的Workflow_State.md"
git commit -m "docs(pst): update skill prompt with README generation rules and meta fields"
```

---

### Task 8: End-to-end verification

**Files:**
- None (verification only)

- [ ] **Step 1: Run full render pipeline**

Run: `python Docs/tools/render_status.py --project Docs`
Expected output includes:
```
  Rendered: ...\Docs\views\overview_view.md
  Rendered: ...\Docs\views\blocker_view.md
  Rendered: ...\Docs\views\prompt_chain_view.md
  Rendered: ...\Docs\views\handoff_view.md
  Rendered: ...\Docs\views\change_log_view.md
  Rendered: ...\Docs\AGENTS.md
  Rendered: ...\Docs\README.md
  Rendered: ...\Docs\prompts\landing\README.md

All views regenerated (5 files + AGENTS.md + 2 READMEs).
```

- [ ] **Step 2: Verify README.md content**

Open `Docs/README.md` and confirm:
- Title is "Plan_Viewer — Project State Overview"
- Directory tree shows actual file counts
- Artifact table lists R-001, D-001, Plan.dashboard-design
- Dependency graph shows R-001 ← D-001 ← Plan.dashboard-design
- Handoff section shows "无活跃 handoff"
- Blockers section shows "无阻塞项"

- [ ] **Step 3: Verify prompts/landing/README.md content**

Open `Docs/prompts/landing/README.md` and confirm:
- Front-matter has source_root, scope, pst_root from meta
- LP 序列 shows "尚无已注册的 Landing Prompt" (no LPs registered yet)
- Coding Standards section present with meta value
- LP 状态 table shows placeholder message

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest Docs/tools/tests/ -v`
Expected: All tests pass (existing + new)

- [ ] **Step 5: Final commit**

```bash
git add Docs/README.md Docs/prompts/landing/README.md
git commit -m "feat(pst): generate initial READMEs via render_status.py"
```
