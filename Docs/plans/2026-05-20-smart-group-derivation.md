# Smart Group Derivation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable intelligent artifact grouping so that Plan + LP + TP display as columns regardless of naming convention, using explicit `group` field with dependency-chain inference fallback.

**Architecture:** Two-layer change: (1) refactor `derive_group()` in render_dashboard.py to read explicit `group` field from status.yaml with ID-keyword fallback, (2) make frontend SwimLaneView and DAGView use dynamic columns derived from data instead of hardcoded group names.

**Tech Stack:** Python 3.11+ (render_dashboard.py), React 18 + Babel JSX (dashboard_template.html), pytest + hypothesis (tests)

---

### Task 1: Refactor `derive_group()` to support explicit group field

**Files:**
- Modify: `Q:\Plan_Viewer\render_dashboard.py` (lines 135–152, line 596)

- [ ] **Step 1: Rename existing `derive_group` to `_derive_group_from_id`**

In `render_dashboard.py`, rename the existing function:

```python
def _derive_group_from_id(artifact_id: str) -> str:
    """Derive phase group from artifact ID using case-insensitive priority matching.

    Priority order: phase1, phase2, phase3, phase4, phase5, codegen, then "Other".
    """
    id_lower = artifact_id.lower()
    if "phase1" in id_lower:
        return "Phase1"
    elif "phase2" in id_lower:
        return "Phase2"
    elif "phase3" in id_lower:
        return "Phase3"
    elif "phase4" in id_lower:
        return "Phase4"
    elif "phase5" in id_lower:
        return "Phase5"
    elif "codegen" in id_lower:
        return "CodeGen"
    else:
        return "Other"
```

- [ ] **Step 2: Add new `derive_group` that accepts a dict**

Add this function directly above `_derive_group_from_id`:

```python
def derive_group(artifact: dict | str) -> str:
    """Derive group for an artifact.

    Accepts either a full artifact dict or a plain artifact ID string
    (for backward compatibility with existing callers/tests).

    Priority:
    1. Explicit 'group' field from status.yaml (if artifact is a dict)
    2. Fallback: keyword matching on artifact ID
    """
    if isinstance(artifact, str):
        # Backward compat: called with just an ID string
        return _derive_group_from_id(artifact)

    # Priority 1: explicit group field
    group = artifact.get("group", "")
    if group:
        return group

    # Priority 2: fallback to ID-based keyword matching
    return _derive_group_from_id(artifact.get("id", ""))
```

- [ ] **Step 3: Update the call site in `build_project_data()`**

In `ProjectReader.build_project_data()`, change line ~596 from:

```python
group=derive_group(a.get("id", "")),
```

to:

```python
group=derive_group(a),
```

- [ ] **Step 4: Run existing tests to verify backward compatibility**

Run: `pytest tests/test_group_derivation.py -v`

Expected: All existing tests PASS (because `derive_group` still accepts a string via the `isinstance` check).

- [ ] **Step 5: Commit**

```bash
git add render_dashboard.py
git commit -m "refactor: derive_group accepts dict with explicit group field priority"
```

---

### Task 2: Add tests for explicit group field priority

**Files:**
- Modify: `Q:\Plan_Viewer\tests\test_group_derivation.py`

- [ ] **Step 1: Add new test class for explicit group field**

Append to `tests/test_group_derivation.py`:

```python
class TestGroupDerivationExplicitField:
    """Tests for explicit group field taking priority over ID matching."""

    def test_explicit_group_field_takes_priority(self):
        """When artifact dict has a non-empty 'group' field, it is returned directly."""
        artifact = {"id": "Plan.Phase1-Something", "group": "CustomGroup"}
        result = derive_group(artifact)
        assert result == "CustomGroup"

    def test_empty_group_field_falls_back_to_id(self):
        """When artifact dict has group='', falls back to ID matching."""
        artifact = {"id": "Plan.Phase1-Something", "group": ""}
        result = derive_group(artifact)
        assert result == "Phase1"

    def test_missing_group_field_falls_back_to_id(self):
        """When artifact dict has no 'group' key, falls back to ID matching."""
        artifact = {"id": "Plan.Phase2-Registry"}
        result = derive_group(artifact)
        assert result == "Phase2"

    def test_string_input_backward_compat(self):
        """Passing a plain string still works (backward compat)."""
        result = derive_group("Plan.Phase3-Fragment")
        assert result == "Phase3"

    def test_explicit_group_overrides_phase_keyword(self):
        """Explicit group wins even when ID contains a phase keyword."""
        artifact = {"id": "Plan.Phase1-BitStream", "group": "CodeGen"}
        result = derive_group(artifact)
        assert result == "CodeGen"

    def test_no_id_no_group_returns_other(self):
        """Artifact with no id and no group returns 'Other'."""
        artifact = {"id": "", "group": ""}
        result = derive_group(artifact)
        assert result == "Other"

    @given(group_name=st.text(min_size=1, max_size=30).filter(lambda s: s.strip()))
    @settings(max_examples=30)
    def test_any_nonempty_group_returned_directly(self, group_name: str):
        """Any non-empty group string is returned as-is."""
        artifact = {"id": "anything", "group": group_name}
        result = derive_group(artifact)
        assert result == group_name
```

- [ ] **Step 2: Run the new tests**

Run: `pytest tests/test_group_derivation.py::TestGroupDerivationExplicitField -v`

Expected: All PASS.

- [ ] **Step 3: Run full test suite to confirm no regressions**

Run: `pytest tests/test_group_derivation.py -v`

Expected: All tests PASS (old + new).

- [ ] **Step 4: Commit**

```bash
git add tests/test_group_derivation.py
git commit -m "test: add tests for explicit group field priority in derive_group"
```

---

### Task 3: Frontend — Dynamic columns in SwimLaneView

**Files:**
- Modify: `Q:\Plan_Viewer\dashboard_template.html` (SwimLaneView component, ~line 180)

- [ ] **Step 1: Add `sortGroups` utility function**

In `dashboard_template.html`, add this function after the `STATUS_COLORS` definition (around line 158, before the `SwimLaneView` component):

```javascript
        // Sort group names: Phase1..N first (numeric), then alphabetical, "Other" last
        function sortGroups(groups) {
            const phaseRegex = /^Phase(\d+)$/i;
            const phases = [];
            const others = [];
            let hasOther = false;

            groups.forEach(g => {
                const match = g.match(phaseRegex);
                if (match) {
                    phases.push({ name: g, num: parseInt(match[1]) });
                } else if (g === 'Other') {
                    hasOther = true;
                } else {
                    others.push(g);
                }
            });

            phases.sort((a, b) => a.num - b.num);
            others.sort((a, b) => a.localeCompare(b));

            const result = [
                ...phases.map(p => p.name),
                ...others,
            ];
            if (hasOther) result.push('Other');
            return result;
        }
```

- [ ] **Step 2: Replace hardcoded GROUPS in SwimLaneView**

In the `SwimLaneView` component, replace:

```javascript
            const GROUPS = ['Phase1', 'Phase2', 'Phase3', 'Phase4', 'Phase5', 'CodeGen', 'Other'];
```

with:

```javascript
            const GROUPS = useMemo(() => {
                const groupSet = new Set(artifacts.map(a => a.group || 'Other'));
                return sortGroups([...groupSet]);
            }, [artifacts]);
```

- [ ] **Step 3: Update cellMap to handle dynamic groups**

The existing `cellMap` useMemo already uses `GROUPS.forEach(g => ...)` to initialize the map, so it will work with the dynamic array. However, we need to add `GROUPS` to its dependency array. Replace:

```javascript
            const cellMap = useMemo(() => {
                const map = {};
                GROUPS.forEach(g => {
                    map[g] = {};
                    ALL_TYPES.forEach(t => { map[g][t] = []; });
                });
                artifacts.forEach(artifact => {
                    const group = artifact.group || 'Other';
                    const type = artifact.type;
                    if (map[group] && map[group][type]) {
                        map[group][type].push(artifact);
                    }
                });
                return map;
            }, [artifacts]);
```

with:

```javascript
            const cellMap = useMemo(() => {
                const map = {};
                GROUPS.forEach(g => {
                    map[g] = {};
                    ALL_TYPES.forEach(t => { map[g][t] = []; });
                });
                artifacts.forEach(artifact => {
                    const group = artifact.group || 'Other';
                    const type = artifact.type;
                    if (map[group] && map[group][type]) {
                        map[group][type].push(artifact);
                    }
                });
                return map;
            }, [artifacts, GROUPS]);
```

- [ ] **Step 4: Verify the template renders correctly**

Run: `python dashboard_server.py` (or `serve.bat`)

Open browser to `http://localhost:8000/dashboard.html`, switch to SwimLane view.

Expected: UE_Iris still shows Phase1–Phase5, CodeGen, Other columns as before.

- [ ] **Step 5: Commit**

```bash
git add dashboard_template.html
git commit -m "feat: SwimLaneView uses dynamic columns from artifact group data"
```

---

### Task 4: Frontend — Dynamic columns in DAGView

**Files:**
- Modify: `Q:\Plan_Viewer\dashboard_template.html` (DAGView component, ~line 365)

- [ ] **Step 1: Replace hardcoded GROUP_ORDER in DAGView**

In the `DAGView` component, replace:

```javascript
            // Ordered group names for consistent rendering
            const GROUP_ORDER = ['Phase1', 'Phase2', 'Phase3', 'Phase4', 'Phase5', 'CodeGen', 'Other'];

            // Get visible group names (non-empty groups only)
            const visibleGroups = useMemo(() => {
                return GROUP_ORDER.filter(g => groups[g] && groups[g].length > 0);
            }, [groups]);
```

with:

```javascript
            // Dynamically derive ordered group names from data
            const GROUP_ORDER = useMemo(() => {
                const allGroups = Object.keys(groups);
                return sortGroups(allGroups);
            }, [groups]);

            // Get visible group names (non-empty groups only)
            const visibleGroups = useMemo(() => {
                return GROUP_ORDER.filter(g => groups[g] && groups[g].length > 0);
            }, [groups, GROUP_ORDER]);
```

- [ ] **Step 2: Verify DAGView renders correctly**

Run: `python dashboard_server.py`

Open browser, switch to DAG view.

Expected: UE_Iris DAG still shows subgraphs for Phase1–Phase5, CodeGen, Other as before.

- [ ] **Step 3: Commit**

```bash
git add dashboard_template.html
git commit -m "feat: DAGView uses dynamic group ordering from artifact data"
```

---

### Task 5: Update project-state-tracker SKILL.md schema

**Files:**
- Modify: `C:\Users\chenshajie\.kiro\skills\project-state-tracker\SKILL.md`

- [ ] **Step 1: Add group field reference in §1 or relevant section**

No direct schema definition lives in SKILL.md (it references companion.md §6G). Add a brief mention in §4 Step 2 description. In the AUDIT pipeline table (§4), update Step 2's Action cell:

Find:
```
| 2 | Re-extract metadata | changed_files + sources | updated artifact records | parse error → `requires_agent_review: true` |
```

Replace with:
```
| 2 | Re-extract metadata + derive groups | changed_files + sources | updated artifact records (incl. `group` field) | parse error → `requires_agent_review: true` |
```

- [ ] **Step 2: Add §3A step 2.5 reference**

In §3A INIT_FROM_DOCS, after step 2 ("Scan ALL tracked files → extract ID + title + type"), add:

```
2.5. Derive groups for all artifacts (load companion §6H)
```

- [ ] **Step 3: Commit**

```bash
cd C:\Users\chenshajie\.kiro\skills\project-state-tracker
git add SKILL.md
git commit -m "feat: add group derivation step references to AUDIT and INIT"
```

---

### Task 6: Add §6H Group Derivation Rules to companion.md

**Files:**
- Modify: `C:\Users\chenshajie\.kiro\skills\project-state-tracker\companion.md`

- [ ] **Step 1: Add §6H section at the end of companion.md**

Append to `companion.md`:

```markdown
### §6H Group Derivation Rules

**Purpose:** Assign a `group` field to each artifact for dashboard column grouping. Runs during INIT §3A (Step 2.5) and AUDIT §4 (Step 2, for artifacts missing `group`).

**Priority (per artifact):**
1. If `group` is already non-empty → skip (user-declared, never overwrite)
2. If `type == "plan"` → `group = extract_topic(id)`
3. If `type in ("landing_prompt", "test_prompt")` → walk `depends_on` to find root Plan → use that Plan's group
4. Otherwise → `group = "Other"`

**`extract_topic(plan_id)`:**
1. Strip `Plan.` prefix (case-sensitive)
2. If remainder matches `Phase\d+.*` → return `Phase{N}` (e.g., `Plan.Phase1-BitStream` → `Phase1`)
3. If remainder contains `codegen` (case-insensitive) → return `CodeGen`
4. Otherwise return remainder as-is (e.g., `Plan.PR3_Runtime` → `PR3_Runtime`)

**`find_root_plan(artifact)` — Dependency Chain Walk:**
1. BFS through `depends_on[]` (resolve IDs against `artifacts[]`)
2. Max depth: 5 (prevents infinite loops)
3. Return the first artifact with `type: plan` encountered
4. If multiple Plans at same depth, use the first in `depends_on` order
5. If no Plan found → return None

**`extract_topic_from_id(artifact_id)` — Orphan LP/TP Fallback:**
Used only when `find_root_plan` returns None.
1. Strip known type prefixes: `LP.`, `TP.`, `LandingPrompt.`, `TestPrompt.`, `Plan.`
2. Strip leading numeric prefix + separator (regex: `^\d+[_-]`)
3. Extract first underscore-or-hyphen-delimited segment as candidate
4. Search all Plan artifacts for one whose `extract_topic(plan.id)` starts with or equals candidate
5. If found → return that Plan's group
6. If not found → return None (artifact gets `group: "Other"`)

**Constraints:**
- MUST NOT modify any artifact field other than `group`
- MUST NOT overwrite existing non-empty `group` values
- MUST run AFTER dependency inference (§6B) so `depends_on` is available
- Max BFS depth: 5
```

- [ ] **Step 2: Update §6G schema to include group field**

In the §6G schema section, find:

```
artifacts: [{id, type, path, status, depends_on[], produces_handoffs?[], consumes_handoffs?[], last_checked?}]
```

Replace with:

```
artifacts: [{id, type, path, status, depends_on[], group?, produces_handoffs?[], consumes_handoffs?[], last_checked?}]
```

- [ ] **Step 3: Add §6H to the §6 pointer table in SKILL.md**

In SKILL.md §6, add a row to the table:

```
| §6H Group Derivation | Step 2 (derive groups) | medium |
```

- [ ] **Step 4: Commit**

```bash
cd C:\Users\chenshajie\.kiro\skills\project-state-tracker
git add companion.md SKILL.md
git commit -m "feat: add §6H Group Derivation Rules to companion reference"
```

---

### Task 7: Regenerate dashboard and verify end-to-end

**Files:**
- No new files; verification only

- [ ] **Step 1: Regenerate the dashboard**

Run: `python render_dashboard.py --project Q:\PortNotes\UE_Iris --project Q:\PortNotes\RB_MM --output views/dashboard.html`

Expected: No errors. Dashboard HTML generated.

- [ ] **Step 2: Start server and verify UE_Iris**

Run: `python dashboard_server.py`

Open `http://localhost:8000/dashboard.html`, select UE_Iris project.

Expected in SwimLane view: Columns show Phase1, Phase2, Phase3, Phase4, Phase5, CodeGen, Other (same as before — backward compat confirmed).

- [ ] **Step 3: Verify RB_MM (before skill AUDIT)**

Switch to RB_MM project in the dashboard.

Expected: All artifacts in "Other" column (no `group` field written yet — this is expected pre-AUDIT behavior).

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`

Expected: All tests PASS.

- [ ] **Step 5: Commit regenerated dashboard**

```bash
git add views/dashboard.html
git commit -m "chore: regenerate dashboard with dynamic group support"
```

---

### Task 8: Integration test — Run PST AUDIT on a project to verify group writing

**Files:**
- No code changes; manual verification of skill behavior

- [ ] **Step 1: Invoke project-state-tracker on UE_Iris**

In a Kiro session with the UE_Iris project open, invoke:
```
Skill project-state-tracker audit
```

Expected: The AUDIT should now derive and write `group` fields to `status/status.yaml` for all artifacts.

- [ ] **Step 2: Verify status.yaml has group fields**

Check `Q:\PortNotes\UE_Iris\status\status.yaml` — artifacts should now have `group:` fields like:
- `Plan.Phase1-BitStream-NetSerializer` → `group: "Phase1"`
- `Plan.net-codegen-tool-design` → `group: "CodeGen"`
- `LandingPrompt.Phase3-DescriptorRegistry` → `group: "Phase3"` (via dependency chain to Plan.Phase3-*)

- [ ] **Step 3: Regenerate dashboard and verify columns use explicit group**

Run: `python dashboard_server.py`

Expected: Same visual result as before, but now driven by explicit `group` field rather than ID keyword matching.

- [ ] **Step 4: Document completion**

The skill-side group derivation is now a behavioral contract in the SKILL.md/companion.md. Future AUDITs will automatically populate `group` for new artifacts.
