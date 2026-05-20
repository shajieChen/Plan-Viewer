# Smart Group Derivation — Design Spec

**Date:** 2026-05-20
**Scope:** project-state-tracker skill + Plan_Viewer dashboard (render_dashboard.py + frontend template)

---

## Problem

The dashboard's `derive_group()` function is hardcoded to recognize only "Phase1"–"Phase5", "CodeGen", and "Other" from artifact IDs. Projects like UE_Iris work because their IDs contain these keywords. Projects like RB_MM (with IDs like `Plan.PR3_Runtime`, `LP03_PR3_Algorithm_Closure`) fall entirely into "Other" and display as a single flat column instead of organized columns.

## Goal

Enable intelligent grouping for any project so that related artifacts (Plan + its LPs + its TPs) display as a single column, regardless of naming convention.

## Strategy: Hybrid (Explicit + Inferred)

Three-layer priority:
1. **Explicit `group` field** on the artifact in status.yaml (user or skill-written, never overwritten by AUDIT)
2. **Dependency-chain clustering** — Plan as root, LP/TP as leaves
3. **ID keyword fallback** — existing "PhaseN"/"CodeGen" matching (backward compat)

---

## Section 1: Data Model Change (status.yaml)

Add optional `group` field to `artifacts[]`:

```yaml
artifacts:
  - id: "Plan.PR3_Runtime"
    type: plan
    status: approved
    path: "plan/PR3_Runtime.md"
    group: "PR3_Runtime"          # optional string
    depends_on: []
```

**Rules:**
- `group` is an optional string field
- If present and non-empty, Dashboard uses it directly as the column name
- If absent, Dashboard falls back to inference/keyword matching
- AUDIT never overwrites a non-empty `group` value (user intent wins)

**Schema change in companion.md §6G:**
```
artifacts: [{id, type, path, status, depends_on[], group?, produces_handoffs?[], consumes_handoffs?[], last_checked?}]
```

---

## Section 2: Skill Layer — Group Derivation Algorithm

### When it runs

- **INIT §3A** Step 2 (after metadata extraction): derive group for all artifacts
- **AUDIT §4 Step 2** (after re-extract metadata): derive group only for artifacts missing `group`

### Algorithm

```
for each artifact A:
    if A.group is non-empty:
        skip (user-declared, never overwrite)
    
    if A.type == "plan":
        A.group = extract_topic(A.id)
    
    elif A.type in ("landing_prompt", "test_prompt"):
        root_plan = find_root_plan(A)
        if root_plan:
            A.group = root_plan.group or extract_topic(root_plan.id)
        else:
            A.group = extract_topic_from_id(A.id) or "Other"
    
    else:
        A.group = "Other"
```

### `find_root_plan(artifact)` — Dependency Chain Walk

1. Walk `depends_on[]` recursively (BFS, max depth 5)
2. Find the first artifact with `type: plan`
3. If multiple Plans found, use the **first** one in `depends_on` order (closest ancestor)
4. If no Plan found in the chain, return None

### `extract_topic(plan_id)` — Group Name from Plan ID

1. Strip `Plan.` prefix
2. If result matches `Phase\d+.*` → return `Phase{N}` (e.g., `Plan.Phase1-BitStream` → `Phase1`)
3. If result contains `codegen` (case-insensitive) → return `CodeGen`
4. Otherwise return the stripped result as-is (e.g., `Plan.PR3_Runtime` → `PR3_Runtime`)

### `extract_topic_from_id(artifact_id)` — Fallback for orphan LP/TP

Used only when dependency chain walk finds no Plan ancestor.

1. Strip known type prefixes: `LP.`, `TP.`, `LandingPrompt.`, `TestPrompt.`, `Plan.`
2. Strip leading numeric prefix + separator (e.g., `03_` from `LP03_PR3_Algorithm_Closure` → `PR3_Algorithm_Closure`)
3. Extract the first underscore-or-hyphen-delimited segment as candidate topic (e.g., `PR3`)
4. Search all Plan artifacts for one whose `extract_topic(plan.id)` starts with or equals this candidate
5. If found, return that Plan's group name
6. If not found, return None (artifact gets `group: "Other"`)

### SKILL.md Changes

- §6G schema: add `group?: string` to artifacts
- §3A: add "Step 2.5: Derive groups" after metadata extraction
- §4 Step 2: add sub-step "derive group for artifacts missing group field"
- companion.md: add §6H "Group Derivation Rules" with the algorithm above

### Constraints

- Group derivation MUST NOT modify any artifact field other than `group`
- Group derivation MUST NOT overwrite existing non-empty `group` values
- Group derivation runs AFTER dependency inference (§6B) so depends_on is available
- Max dependency walk depth: 5 (prevents infinite loops on circular refs)

---

## Section 3: Dashboard Layer — `derive_group()` Refactor

### render_dashboard.py Changes

**Current signature:**
```python
def derive_group(artifact_id: str) -> str:
```

**New signature:**
```python
def derive_group(artifact: dict) -> str:
```

**Implementation:**
```python
def derive_group(artifact: dict) -> str:
    """Derive group with priority: explicit field > ID keyword fallback."""
    group = artifact.get("group", "")
    if group:
        return group
    return _derive_group_from_id(artifact.get("id", ""))


def _derive_group_from_id(artifact_id: str) -> str:
    """Legacy ID-based keyword matching (backward compat fallback)."""
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

**Call site change in `build_project_data()`:**
```python
# Before:
group=derive_group(a.get("id", ""))

# After:
group=derive_group(a)
```

---

## Section 4: Frontend — Dynamic Columns

### SwimLaneView Changes

**Current:** Hardcoded `GROUPS = ['Phase1', 'Phase2', 'Phase3', 'Phase4', 'Phase5', 'CodeGen', 'Other']`

**New:**
```javascript
const GROUPS = useMemo(() => {
    const groupSet = new Set(artifacts.map(a => a.group || 'Other'));
    return sortGroups([...groupSet]);
}, [artifacts]);
```

### `sortGroups()` — Column Ordering

```javascript
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

### DAGView Changes

Same dynamic group extraction applies to DAGView's `GROUP_ORDER`.

---

## Section 5: Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| UE_Iris (IDs contain "Phase1" etc, no `group` field) | Fallback to `_derive_group_from_id()` → same columns as before |
| UE_Iris after next AUDIT | Skill writes `group` field → Dashboard reads it directly (same result) |
| RB_MM (no "Phase" in IDs, no `group` field yet) | After AUDIT: skill infers groups from dependency chains → proper columns |
| RB_MM before AUDIT | Fallback to `_derive_group_from_id()` → all "Other" (same as current) |
| User manually sets `group: "MyCustomGroup"` | Respected by both skill (never overwritten) and dashboard (priority 1) |

---

## Section 6: Testing

### render_dashboard.py tests

- Existing `test_group_derivation.py` tests remain valid (test `_derive_group_from_id` path)
- New tests:
  - `test_derive_group_explicit_field_priority`: artifact with `group` field → returns that value
  - `test_derive_group_fallback_when_no_field`: artifact without `group` → uses ID matching
  - `test_derive_group_empty_string_field`: artifact with `group: ""` → falls back to ID matching

### Frontend tests (manual verification)

- SwimLaneView renders dynamic columns from data
- Columns sort correctly: Phase1 < Phase2 < ... < alphabetical < Other
- DAGView subgraphs use dynamic group names

### Skill integration test

- After AUDIT on RB_MM-style project, artifacts have correct `group` values
- Dependency chain walk correctly identifies Plan roots
- User-set `group` values are preserved across AUDIT

---

## Files Modified

| File | Change |
|------|--------|
| `~/.kiro/skills/project-state-tracker/SKILL.md` | §6G schema + §3A/§4 step references |
| `~/.kiro/skills/project-state-tracker/companion.md` | New §6H Group Derivation Rules |
| `Q:\Plan_Viewer\render_dashboard.py` | `derive_group()` refactor |
| `Q:\Plan_Viewer\dashboard_template.html` | SwimLaneView + DAGView dynamic columns |
| `Q:\Plan_Viewer\tests\test_group_derivation.py` | New test cases for explicit group |
