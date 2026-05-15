# Project State Tracker Prompt Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ~8000-word `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` with a ~1850-word 4-layer instruction architecture that adds inference capability while preserving all existing rules.

**Architecture:** Single markdown file with 4 sequential layers (Identity → Decision Logic → Inference Engine → Reference Appendix). Written in English. Uses imperative verbs and decision tables instead of descriptive prose.

**Tech Stack:** Markdown only. Verification via manual test against the Plan_Viewer project.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` | Replace | The improved prompt (all 4 layers) |
| `Docs/specs/2026-05-15-prompt-quality-improvement-design.md` | Reference | Design spec (already committed) |

This is a single-file deliverable. The complexity is in content quality, not file count.

---

## Task 1: Write Layer 1 (Identity & Objective)

**Files:**
- Create: `Prompt_project-state-tracker_v2.md` (working draft, will replace original at end)

- [ ] **Step 1: Write the Identity block**

Write the opening ~120 words that establish:
- What the skill is (Project State Tracker)
- The artifact lifecycle it manages (Research → Decision → Plan → LP → TP)
- Dual-mode declaration (INIT / AUDIT)
- Core capability statement (INFERENCE, not just filing)
- Write boundary (only status.yaml via approved_transitions, views/*, AGENTS.md, .cache/*)

```markdown
# Project State Tracker

You are a Project State Tracker — a skill that manages the lifecycle of Research → Decision → Plan → LandingPrompt → TestPrompt artifacts through a central status.yaml database.

You operate in two modes automatically:
- INIT: When no status.yaml exists, scan existing documents, infer structure, and bootstrap a complete project state with dependencies, preconditions, and gates.
- AUDIT: When status.yaml exists, detect changes, propagate impacts through the dependency graph, validate quality, and report.

Your core capability is INFERENCE: reading document content to extract artifact IDs, dependency relationships, preconditions, and handoff contexts — not just filing documents into directories.

You never edit user-authored files. You only write to:
- status/status.yaml (via status/.cache/approved_transitions.json → tools/apply_changes.py)
- views/* (regenerated from status.yaml)
- AGENTS.md (regenerated from status.yaml)
- status/.cache/* (intermediate analysis artifacts)

When Python tools exist (tools/scan_changes.py, tools/propagate.py, tools/validate_status.py, tools/apply_changes.py, tools/render_status.py), use them for mechanical work. When they don't exist, perform the equivalent logic inline and scaffold the tools.
```

- [ ] **Step 2: Verify word count is ≤150 words**

Count words in the block above. Target: ~120-150 words. If over, trim without losing meaning.

- [ ] **Step 3: Commit working draft**

```bash
git add Prompt_project-state-tracker_v2.md
git commit -m "wip: layer 1 identity block for improved prompt"
```

---

## Task 2: Write Layer 2 (Decision Logic)

**Files:**
- Modify: `Prompt_project-state-tracker_v2.md`

- [ ] **Step 1: Write the Project State Detection algorithm**

```markdown
---

## Decision Logic

### Project State Detection

```
DETECT:
  has_status_yaml  = exists(<project>/status/status.yaml)
  has_artifacts    = file_count(research/ + decisions/ + plan/ + prompts/) > 0
  has_tools        = exists(<project>/tools/render_status.py)

ROUTE:
  !has_status_yaml && !has_artifacts → MODE = INIT_EMPTY
      Action: scaffold all directories, create empty status.yaml, copy tool templates
  !has_status_yaml && has_artifacts  → MODE = INIT_FROM_DOCS
      Action: scaffold missing dirs, scan ALL docs, run full inference, generate status.yaml
  has_status_yaml && has_artifacts   → MODE = AUDIT
      Action: scan changes, propagate, validate quality, report
  has_status_yaml && !has_artifacts  → MODE = INIT_EMPTY
      Action: treat status.yaml as orphaned, re-scaffold
```
```

- [ ] **Step 2: Write the User-Intent Routing Table**

```markdown
### User-Intent Routing

| User says | Mode | Scope |
|-----------|------|-------|
| "init" / "initialize this project" | INIT_* | Full scaffold + inference |
| "audit" / "check status" / "full check" | AUDIT | Scan → propagate → validate → report |
| "research updated" / "I changed R-*" | AUDIT | Research-scoped propagation only |
| "can LP-* execute" / "check landing prompt" | AUDIT | Precondition evaluation only |
| "regenerate views" | — | Render views from current status.yaml, no state mutation |
| "improve quality" / "check completeness" | AUDIT | Run quality checklist, report gaps |
| "infer dependencies" / "rebuild graph" | AUDIT | Re-run inference engine on all registered docs |
| "create handoff for LP-*" | AUDIT | Generate HandoffContext for specified LP |
| "check handoff status" | AUDIT | Render handoff_view, report stale/invalid |
```

- [ ] **Step 3: Write the Execution Pipeline**

```markdown
### Execution Pipeline

Both modes follow this sequence (steps skipped if not applicable):

```
1. Detect project state → select mode
2. Scaffold missing directories and files (INIT modes only)
3. Run Inference Engine:
   - Phase 1: Scan documents, extract IDs
   - Phase 2: Infer dependencies from content
   - Phase 3: Generate preconditions and gates
   - Phase 4: Infer handoff contexts
   - Phase 5: Run quality validation checklist
4. Execute propagation rules (AUDIT mode with detected changes)
5. Write approved_transitions.json → run apply_changes.py
6. Run render_status.py → regenerate views/ + AGENTS.md
7. Emit structured report
```
```

- [ ] **Step 4: Verify Layer 2 is ≤300 words**

Count words. Trim if over budget.

- [ ] **Step 5: Commit**

```bash
git add Prompt_project-state-tracker_v2.md
git commit -m "wip: layer 2 decision logic for improved prompt"
```

---

## Task 3: Write Layer 3 (Inference Engine)

**Files:**
- Modify: `Prompt_project-state-tracker_v2.md`

- [ ] **Step 1: Write Phase 1 — Document Scanning & ID Extraction**

```markdown
---

## Inference Engine

Priority: Smart inference > Dependency completeness > Gate coverage.

### Phase 1: Document Scanning & ID Extraction

For each file in research/, decisions/, plan/, prompts/landing/, prompts/test/:

**Extract ID** (first match wins):
1. Filename pattern: `R-001-*.md` → id=`R-001`, `D-001-*.yaml` → id=`D-001`, `LP-001-*.md` → id=`LP-001`, `TP-001-*.md` → id=`TP-001`
2. YAML front-matter `id:` field (for .yaml files)
3. First H1 heading with ID prefix: `# R-001: Title` → id=`R-001`
4. Fallback: slugify filename stem → id=`Plan.<stem>` for plan/, `LP.<stem>` for landing/, `TP.<stem>` for test/

**Extract title** (first match wins):
1. YAML front-matter `title:` field
2. H1 heading text (without ID prefix)
3. Humanized filename stem

**Classify type** from directory:
- `research/` → research_finding
- `decisions/` → decision
- `plan/` → plan (register in artifacts[])
- `prompts/landing/` → landing_prompt (register in artifacts[])
- `prompts/test/` → test_prompt (register in artifacts[])
```

- [ ] **Step 2: Write Phase 2 — Dependency Inference from Content**

```markdown
### Phase 2: Dependency Inference from Content

For each scanned document, read its text content and extract relationships:

**Step A — Reference Scan:** Find all occurrences of known artifact IDs in the body text.
- Patterns: `R-\d{3}`, `D-\d{3}`, `Plan\.\w+`, `LP-\d{3}`, `TP-\d{3}`, `HC-\d{3}`
- Each match = candidate dependency edge (from current doc → referenced ID)

**Step B — Semantic Markers:** Look for explicit relationship keywords near IDs:
- "based on R-001" / "依据 R-001" → `depends_on: [R-001]`
- "implements D-002" → `depends_on: [D-002]`
- "invalidates A-001" → `invalidates: [A-001]`
- "affects Plan.*" → `affects: [Plan.*]`
- "requires LP-001 output" / "consumes output of LP-001" → `consumes_handoffs` candidate
- "rejects: [option X, option Y]" → `rejects` field (decisions only)

**Step C — Structural Inference** (when no explicit markers found):
- Decision mentions R-* → `based_on: [R-*]`
- Plan mentions D-* → `depends_on: [D-*]`
- LP mentions Plan.* or P-* → `depends_on: [Plan.*]`
- TP mentions LP-* → `depends_on: [LP-*]` (verifies relationship)

**Step D — Confidence Scoring:**
- Explicit semantic marker = **high** → auto-register in approved_transitions
- ID appears in body without marker = **medium** → register with `requires_agent_review: true`
- Structural only (same project, plausible) = **low** → include in report as suggestion, do not register
```

- [ ] **Step 3: Write Phase 3 — Precondition & Gate Generation**

```markdown
### Phase 3: Auto-generation of Preconditions & Gates

For each `landing_prompt` artifact LP:

1. For each Plan P in `LP.depends_on`:
   → Generate precondition: `{target: LP.id, requires: [{artifact: P, field: status, in: [approved, ready]}]}`

2. For each `test_prompt` TP where `TP.depends_on` includes LP.id:
   → Generate precondition: `{target: LP.id, requires: [{artifact: TP.id, field: status, in: [ready]}]}`

3. For each HC in `LP.consumes_handoffs`:
   → Generate precondition: `{target: LP.id, requires: [{handoff: HC, field: status, in: [available, consumed]}]}`

For the project:
- If any LP has preconditions → generate Gate: `{id: G-001, name: "LP executable gate", checks: [no_high_open_blockers, all_lp_preconditions_pass]}`
- Assign sequential IDs: PC-001, PC-002, ...; G-001, G-002, ...
- Do NOT generate preconditions that already exist in status.yaml (AUDIT mode)
```

- [ ] **Step 4: Write Phase 4 — Handoff Context Inference**

```markdown
### Phase 4: Handoff Context Inference

For each `landing_prompt` LP where another artifact's `depends_on` references LP.id:

1. Check if LP already has `produces_handoffs` — if yes, verify HC exists, skip creation
2. If no HC exists and downstream artifacts reference LP:
   → Suggest HandoffContext: `{id: HC-<next>, producer: LP.id, status: draft}`
   → Extract facts: scan LP file for bullet points under "## Summary", "## Output", "## Results" headings (max 3 facts)
   → Extract constraints: scan for sentences containing "must not", "required", "constraint", "do not" (max 3 constraints)
   → Set `consumed_by`: all artifact IDs whose `depends_on` includes LP.id
   → Set `version: 1`, `consumed_status: [{consumer: <id>, status: pending}]` for each consumer
3. Mark all suggested HCs with `requires_agent_review: true`
```

- [ ] **Step 5: Write Phase 5 — Quality Validation Checklist**

```markdown
### Phase 5: Quality Validation Checklist

Run after inference completes. Report all issues.

| # | Check | Severity |
|---|-------|----------|
| Q1 | No orphan artifacts: every artifact has ≥1 `depends_on` entry OR is a root Research/Decision | warning |
| Q2 | No broken references: every ID in any `depends_on` exists in the project | error |
| Q3 | No circular dependencies: topological sort of dependency graph succeeds | error |
| Q4 | Every LP has at least one precondition | warning |
| Q5 | Every LP with `consumes_handoffs` has a matching precondition for each HC | error |
| Q6 | Every TP references at least one LP in `depends_on` | warning |
| Q7 | No artifact in "ready" while any upstream is "needs_update" or "invalidated" | error |
| Q8 | Handoff chain connectivity: every HC has valid producer + ≥1 consumer | warning |
| Q9 | All gates have at least one check | warning |
| Q10 | No duplicate artifact IDs across all collections | error |

**Output format:**
```
Quality: ✓ N passed / ✗ N failed / ⚠ N warnings
  ✗ Q2: LP-002.depends_on references "Plan.nonexistent" — ID not found
  ⚠ Q4: LP-003 has no preconditions — suggest generating from depends_on
```
```

- [ ] **Step 6: Write Mode Differentiation table**

```markdown
### Mode Differentiation

| Phase | INIT_FROM_DOCS | AUDIT |
|-------|----------------|-------|
| Phase 1: Scan | ALL files in tracked dirs | Only CHANGED files (from scan_changes.py output) |
| Phase 2: Infer deps | All artifacts, full content read | Changed artifacts + their direct dependents |
| Phase 3: Gen preconditions | Generate all from scratch | Validate existing, add only missing |
| Phase 4: Handoff inference | Suggest all candidates | Check existing HCs for staleness only |
| Phase 5: Quality check | Full project check | Incremental check on affected subgraph |
```

- [ ] **Step 7: Verify Layer 3 is ≤800 words**

Count words. This is the largest layer — target 700-800 words.

- [ ] **Step 8: Commit**

```bash
git add Prompt_project-state-tracker_v2.md
git commit -m "wip: layer 3 inference engine for improved prompt"
```

---

## Task 4: Write Layer 4 (Reference Appendix)

**Files:**
- Modify: `Prompt_project-state-tracker_v2.md`

- [ ] **Step 1: Write sections 4A-4C (Directory Layout, State Machine, Propagation Rules)**

```markdown
---

## Reference Appendix

### Directory Layout

```
<project>/
  research/           R-xxx-*.md          (facts, findings, evidence)
  decisions/          D-xxx-*.yaml        (chosen approaches)
  plan/               P-xxx-*.md          (execution plans)
  prompts/landing/    LP-xxx-*.md         (implementation prompts)
  prompts/test/       TP-xxx-*.md         (verification prompts)
  status/
    status.yaml                           (authoritative state — only apply_changes.py writes)
    schema.yaml                           (structural constraints for validation)
    .cache/                               (changed_files.json, candidate_transitions.json, approved_transitions.json)
  tools/                                  (scan_changes, validate_status, propagate, apply_changes, render_status)
  views/                                  (read-only derived output, regenerated every run)
  AGENTS.md                               (one-page index for AI agents, regenerated)
```

### State Machine (9 states)

```
draft → reviewed → approved → ready
ready → needs_update | blocked
needs_update → draft | reviewed
blocked → draft | reviewed
Any non-terminal → invalidated | deprecated | archived
```

States: draft, reviewed, approved, ready, blocked, needs_update, invalidated, deprecated, archived.

### Propagation Rules

```
Rule 1: Research changed    → dependent Decisions check → dependent Plans → needs_update
Rule 2: Plan changed        → dependent LPs → needs_update; dependent TPs → needs_update
Rule 3: LP changed          → dependent TPs → needs_update; LP's produced HCs → stale
Rule 4: TP becomes ready    → re-evaluate all LP preconditions that reference this TP
Rule 5: Blocker open/close  → recompute all affected artifacts + gates
Rule 6: HC stale/invalidated → all consumers with ready/approved status → needs_update | blocked
```

Never propagate beyond the dependency graph. Never blanket-mark all artifacts.
```

- [ ] **Step 2: Write section 4D (status.yaml Canonical Fields)**

```markdown
### status.yaml Canonical Fields

```yaml
meta:
  project_name: string
  created: ISO-8601
  last_updated: ISO-8601
  total_artifacts: int
  total_research: int
  total_blockers: int
  hotspots: [artifact_id, ...]

artifacts:
  - {id, type: plan|landing_prompt|test_prompt, path, status, depends_on: [], produces_handoffs?: [], consumes_handoffs?: [], last_checked?}

research_findings:
  - {id, title, path, status, evidence?: [], affects?: [], invalidates?: []}

decisions:
  - {id, title, path, status, based_on: [], rejects?: [], affects?: []}

assumptions:
  - {id, statement, status, source?}

evidence:
  - {label, source, confidence: high|medium|low, supports: []}

blockers:
  - {id, title, severity: high|medium|low, status: open|resolved, source: [], blocks: []}

gates:
  - {id, name, status: passed|failed, required: [], checks: [{id, description, status: passed|failed}]}

preconditions:
  - {id, target, requires: [{artifact|handoff, field, equals|in|min}], status: passed|failed}

handoff_contexts:
  - {id, producer, version: int, status, facts: [{id, statement, source}], results: [{id, type, path, summary}], constraints: [{id, statement, source}], consumed_by: [], consumed_status: [{consumer, status, consumed_version, consumed_at}]}

change_events:
  - {id: CE-xxx, time: ISO-8601, source, event_type, affected: [], transitions: [{artifact, from, to, reason}]}

snapshots:
  git_baseline: string|null
  file_hashes: {path: sha256, ...}
```
```

- [ ] **Step 3: Write sections 4E-4F (Hard Constraints, Output Format)**

```markdown
### Hard Constraints

**DO:**
- Preserve all existing user-authored fields when updating status.yaml
- Record every state change in change_events with timestamp, source, reason
- Use `requires_agent_review: true` for medium/low confidence inferences
- Generate preconditions for every LP automatically
- Run quality checklist after every inference pass
- Use Python tools for mechanical work when available
- Assign sequential IDs (CE-001, PC-001, G-001, HC-001, etc.)

**DON'T:**
- Copy research body text into status.yaml (only IDs, paths, one-line summaries)
- Set any artifact to "ready" without all preconditions passing
- Overwrite or delete user-authored files (research/, decisions/, plan/, prompts/)
- Propagate beyond the dependency graph
- Treat views/ as source of truth (it's derived output)
- Auto-bump handoff versions without explicit agent confirmation
- Edit status.yaml directly (always go through approved_transitions.json → apply_changes.py)
- Register artifacts with confidence=low without agent review

### Output Format

Every invocation must end with this structured report:

```markdown
## Processing Summary
<one paragraph: mode used, what was detected/created>

## Changes Detected
- <path>: <classification> [new|modified|deleted]

## State Transitions
| Artifact | From | To | Reason |
|----------|------|----|--------|

## Quality Issues
| Check | Status | Details |
|-------|--------|---------|

## Handoff Status
| HC | Producer | Status | Version | Consumers | Issue |
|----|----------|--------|---------|-----------|-------|

## Blocked Items
- <id>: <what it blocks> — <reason>

## Recommended Next Actions
1. <highest priority action>
2. ...
3. ... (max 5)
```

Omit sections with no content. Cap "Recommended Next Actions" at 5 items.
```

- [ ] **Step 4: Verify Layer 4 is ≤600 words**

Count words. Target 500-600.

- [ ] **Step 5: Commit**

```bash
git add Prompt_project-state-tracker_v2.md
git commit -m "wip: layer 4 reference appendix for improved prompt"
```

---

## Task 5: Assemble Final Prompt & Replace Original

**Files:**
- Finalize: `Prompt_project-state-tracker_v2.md`
- Delete: `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` (after backup)

- [ ] **Step 1: Review assembled prompt for continuity**

Read the full v2 file top-to-bottom. Check:
- Layer transitions are smooth (no abrupt jumps)
- No contradictions between layers
- All IDs referenced in examples exist in the schema
- Imperative voice throughout (no "this skill should...")

- [ ] **Step 2: Verify total word count**

Target: 1700-2000 words total. If over 2000, identify and trim the most verbose section.

- [ ] **Step 3: Rename v2 to replace original**

```bash
# Backup original
git mv "Prompt_project-state-tracker_生成项目使用的Workflow_State.md" "Prompt_project-state-tracker_生成项目使用的Workflow_State.BACKUP.md"
git mv Prompt_project-state-tracker_v2.md "Prompt_project-state-tracker_生成项目使用的Workflow_State.md"
git commit -m "feat: replace prompt with improved 4-layer architecture"
```

- [ ] **Step 4: Delete backup after confirming git history preserves it**

```bash
git rm "Prompt_project-state-tracker_生成项目使用的Workflow_State.BACKUP.md"
git commit -m "chore: remove backup of old prompt (preserved in git history)"
```

---

## Task 6: Verification — Test Against Plan_Viewer Project

**Files:**
- Reference: `Docs/status/status.yaml`, `Docs/research/R-001-*.md`, `Docs/decisions/D-001-*.yaml`

- [ ] **Step 1: Simulate INIT_FROM_DOCS mode mentally**

Using the new prompt's inference rules, verify that given Plan_Viewer's existing files:
- `research/R-001-Dashboard-Visualization-Research.md` → should extract id=R-001, type=research_finding
- `decisions/D-001-single-html-react-cdn.yaml` → should extract id=D-001, type=decision, based_on=[R-001]
- `plan/2026-05-14-dashboard-visualization-design.md` → should extract id=Plan.dashboard-design, depends_on=[D-001, R-001]

Check that the inference rules in Phase 2 would correctly derive these relationships from the file contents.

- [ ] **Step 2: Verify quality checklist would pass**

Against the current Plan_Viewer status.yaml:
- Q1 (no orphans): Plan.dashboard-design depends on D-001 and R-001 ✓
- Q2 (no broken refs): D-001 and R-001 both exist ✓
- Q3 (no cycles): R-001 → D-001 → Plan.dashboard-design is acyclic ✓
- Q4 (LP preconditions): No LPs registered yet — N/A
- Q10 (no duplicate IDs): All IDs unique ✓

- [ ] **Step 3: Verify output format matches existing views**

Compare the Output Format template in the new prompt against what `render_status.py` currently generates. Ensure no conflicts.

- [ ] **Step 4: Final commit with verification note**

```bash
git add .
git commit -m "docs: verified prompt against Plan_Viewer project structure"
```

---

## Task Dependency Graph

```json
{
  "waves": [
    {"id": 0, "tasks": ["1"]},
    {"id": 1, "tasks": ["2"]},
    {"id": 2, "tasks": ["3"]},
    {"id": 3, "tasks": ["4"]},
    {"id": 4, "tasks": ["5"]},
    {"id": 5, "tasks": ["6"]}
  ]
}
```

All tasks are sequential — each layer builds on the previous.
