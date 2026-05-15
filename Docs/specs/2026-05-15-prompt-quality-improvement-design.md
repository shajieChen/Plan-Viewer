# Design: Project State Tracker Prompt Quality Improvement

## Overview

Rewrite the `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` from ~8000 words of repetitive prose into a ~1850-word layered instruction architecture. The core innovation is adding an Inference Engine that reads existing documents and derives structure (artifacts, dependencies, preconditions, handoffs) — a capability completely absent from the current prompt.

The improved prompt serves dual purposes:
1. As the internal instruction set for the `project-state-tracker` skill (read by Kiro/Claude when the skill is invoked)
2. As a standalone prompt that can be pasted into any capable LLM to bootstrap the skill from scratch

## Problem Statement

The current prompt has these quality issues:
- **No inference capability**: Only describes "create empty structure if missing" — cannot analyze existing docs to derive meaningful state
- **Extreme redundancy**: Rules like "don't copy research text" repeated 5+ times across sections
- **No mode distinction**: Cold-start and incremental-update logic interleaved without clear branching
- **No quality standards**: No definition of what constitutes a "high quality" workflow (completeness, connectivity, coverage)
- **Poor token efficiency**: ~8000 words where ~1850 suffice, wasting context budget when used as skill instructions

## Architecture: 4-Layer Instruction Stack

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Identity & Objective (~150 words)      │
│  - What this skill is                            │
│  - Single-paragraph mission statement            │
│  - Dual-mode declaration (init / audit)          │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Layer 2: Decision Logic (~300 words)            │
│  - Entry-point flowchart                         │
│  - Project state detection algorithm             │
│  - Mode selection: INIT vs AUDIT                 │
│  - User-intent routing table                     │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Layer 3: Inference Engine (~800 words)           │
│  - Document scanning & ID extraction             │
│  - Dependency inference from content             │
│  - Auto-generation of preconditions/gates        │
│  - Handoff context inference                     │
│  - Quality validation checklist                  │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Layer 4: Reference Appendix (~600 words)        │
│  - status.yaml canonical schema                  │
│  - Artifact state machine (9 states)             │
│  - Propagation rules (5 rules, compact)          │
│  - Output format template                        │
│  - Hard constraints (do/don't list)              │
└─────────────────────────────────────────────────┘
```

## Layer 1: Identity & Objective

```
You are a Project State Tracker — a skill that manages the lifecycle of
Research → Decision → Plan → LandingPrompt → TestPrompt artifacts through
a central status.yaml database.

You operate in two modes automatically:
- INIT: When no status.yaml exists, scan existing docs, infer structure,
  and bootstrap a complete project state.
- AUDIT: When status.yaml exists, detect changes, propagate impacts,
  validate quality, and report.

Your core capability is INFERENCE: reading document content to extract
artifact IDs, dependency relationships, preconditions, and handoff contexts
— not just filing documents into directories.

You never edit user-authored files. You only write to: status.yaml (via
approved_transitions), views/*, AGENTS.md, and status/.cache/*.
```

## Layer 2: Decision Logic

### Project State Detection

```
DETECT project state:
  has_status_yaml  = exists(status/status.yaml)
  has_artifacts    = count(research/ + decisions/ + plan/ + prompts/) > 0
  has_tools        = exists(tools/render_status.py)

ROUTE:
  if !has_status_yaml && !has_artifacts:
      MODE = INIT_EMPTY        → scaffold all dirs + empty status.yaml
  if !has_status_yaml && has_artifacts:
      MODE = INIT_FROM_DOCS    → scan docs, infer structure, generate status.yaml
  if has_status_yaml && has_artifacts:
      MODE = AUDIT             → scan changes, propagate, validate quality
  if has_status_yaml && !has_artifacts:
      MODE = INIT_EMPTY        → treat as fresh (status.yaml is orphaned)
```

### User-Intent Routing Table

| User says (pattern) | Mode override | Action scope |
|---------------------|---------------|--------------|
| "init" / "initialize" | INIT_* | Full scaffold + inference |
| "audit" / "check status" / "full check" | AUDIT | Scan → propagate → validate → report |
| "research updated" / "I changed R-*" | AUDIT | Research-scoped propagation |
| "can LP-* execute" / "check landing prompt" | AUDIT | Precondition evaluation only |
| "regenerate views" | — | Render only, no state mutation |
| "improve quality" / "check completeness" | AUDIT | Quality validation checklist |
| "infer dependencies" / "rebuild graph" | AUDIT | Re-run inference engine on all docs |

### Execution Pipeline (both modes)

```
1. Detect state → select mode
2. Scaffold missing dirs/files (if INIT)
3. Run Inference Engine (Layer 3)
4. Execute propagation rules (if AUDIT with changes)
5. Run quality validation checklist
6. Generate views + AGENTS.md
7. Emit structured report (Layer 4 output format)
```

## Layer 3: Inference Engine

Priority order: Smart inference > Dependency completeness > Gate coverage.

### Phase 1: Document Scanning & ID Extraction

```
For each file in research/, decisions/, plan/, prompts/landing/, prompts/test/:
  1. Extract ID from:
     - Filename pattern: R-001-*.md → id="R-001"
     - YAML front-matter: id: field if present
     - First H1 heading: "# R-001: Platform Limits" → id="R-001"
     - Fallback: derive from filename stem (slugify)

  2. Extract title from:
     - YAML front-matter: title: field
     - First H1 heading text (without ID prefix)
     - Fallback: humanize filename stem

  3. Classify type from directory:
     - research/         → research_finding
     - decisions/        → decision
     - plan/             → plan (artifact)
     - prompts/landing/  → landing_prompt (artifact)
     - prompts/test/     → test_prompt (artifact)
```

### Phase 2: Dependency Inference from Content

```
For each scanned document:
  1. REFERENCE SCAN: Find all occurrences of known IDs in the text body.
     - Pattern: R-\d{3}, D-\d{3}, Plan\.\w+, LP-\d{3}, TP-\d{3}, HC-\d{3}
     - Each reference = candidate dependency edge

  2. SEMANTIC MARKERS: Look for explicit relationship declarations:
     - "based on R-001"         → depends_on: [R-001]
     - "implements D-002"       → depends_on: [D-002]
     - "invalidates A-001"      → invalidates: [A-001]
     - "affects Plan.*"         → affects: [Plan.*]
     - "requires LP-001 output" → consumes_handoffs candidate
     - "rejects: [option A]"    → rejects field for decisions

  3. STRUCTURAL INFERENCE (when no explicit markers):
     - Decision file mentions R-* → based_on: [R-*]
     - Plan file mentions D-*    → depends_on: [D-*]
     - LP file mentions Plan.*   → depends_on: [Plan.*]
     - TP file mentions LP-*     → depends_on: [LP-*] (verifies relationship)

  4. CONFIDENCE SCORING:
     - Explicit marker in text       = high   → auto-register
     - ID appears in body text       = medium → register with requires_agent_review
     - Only structural (plausible)   = low    → suggest, don't register
```

### Phase 3: Auto-generation of Preconditions & Gates

```
For each landing_prompt artifact LP:
  1. For each Plan in LP.depends_on:
     → Generate PC: requires Plan.status in [approved, ready]

  2. For each test_prompt TP where TP.depends_on includes LP:
     → Generate PC: requires TP.status in [ready]

  3. For each HC in LP.consumes_handoffs:
     → Generate PC: requires HC.status in [available, consumed]
     → Generate PC: requires HC.version >= 1

For the project as a whole:
  If any LP has preconditions:
    → Generate Gate G-001: "LP executable gate"
    → Gate checks: no_high_open_blockers + all LP preconditions pass
```

### Phase 4: Handoff Context Inference

```
For each landing_prompt LP that is referenced by another LP or TP:
  If LP produces output that downstream artifacts consume:
    → Suggest HandoffContext creation
    → Extract facts: key conclusions from LP file (first 3 bullet points or summary)
    → Extract constraints: any "must not" / "required" / "constraint" statements
    → Set consumed_by: all downstream artifacts that reference this LP
```

### Phase 5: Quality Validation Checklist

```
QUALITY CHECKS (ordered by priority):
  □ No orphan artifacts (every artifact has ≥1 depends_on or is root Research)
  □ No broken references (every ID in depends_on exists in the project)
  □ No circular dependencies (topological sort succeeds)
  □ Every LP has at least one precondition
  □ Every LP with consumes_handoffs has matching PC for each HC
  □ Every TP references at least one LP
  □ No artifact in "ready" while upstream is "needs_update" or "invalidated"
  □ Handoff chain connectivity: producer → HC → consumer path is complete
  □ All gates have at least one check

REPORT: ✓ passed / ✗ failed (count) / ⚠ warning (count)
For each failure: artifact ID + what's wrong + suggested fix
```

### Mode Differentiation

| Phase | INIT_FROM_DOCS | AUDIT |
|-------|----------------|-------|
| Phase 1: Scan | Scan ALL files, register all | Scan only CHANGED files |
| Phase 2: Infer deps | Infer for ALL artifacts | Re-infer for changed + dependents |
| Phase 3: Gen preconditions | Generate all from scratch | Validate existing, add missing |
| Phase 4: Handoff inference | Suggest all candidates | Check existing HCs for staleness |
| Phase 5: Quality check | Full check, report all | Incremental on affected subgraph |

## Layer 4: Reference Appendix

### 4A. Directory Layout

```
<project>/
  research/           R-xxx-*.md
  decisions/          D-xxx-*.yaml
  plan/               P-xxx-*.md | plan.md
  prompts/landing/    LP-xxx-*.md
  prompts/test/       TP-xxx-*.md
  status/
    status.yaml       (authoritative state)
    schema.yaml       (structural constraints)
    .cache/           (changed_files, candidates, approved_transitions)
  tools/              (scan_changes, validate_status, propagate, apply_changes, render_status)
  views/              (read-only derived output)
  AGENTS.md           (one-page index)
```

### 4B. State Machine

```
draft → reviewed → approved → ready
ready → needs_update | blocked
needs_update → draft | reviewed
blocked → draft | reviewed
Any non-terminal → invalidated | deprecated | archived
```

### 4C. Propagation Rules

```
Rule 1: Research changed   → dependent Plans → needs_update
Rule 2: Plan changed       → dependent LPs/TPs → needs_update
Rule 3: LP changed         → dependent TPs → needs_update; produced HCs → stale
Rule 4: TP ready           → re-evaluate LP preconditions
Rule 5: Blocker open/close → recompute affected artifacts + gates
Rule 6: HC stale/invalid   → consumers → needs_update | blocked
```

### 4D. status.yaml Canonical Fields

```yaml
meta: {project_name, created, last_updated, total_artifacts, total_research, total_blockers, hotspots}
artifacts: [{id, type, path, status, depends_on, produces_handoffs?, consumes_handoffs?}]
research_findings: [{id, title, path, status, evidence?, affects?, invalidates?}]
decisions: [{id, title, path, status, based_on, rejects?, affects?}]
assumptions: [{id, statement, status, source?}]
evidence: [{label, source, confidence, supports}]
blockers: [{id, title, severity, status, source, blocks}]
gates: [{id, name, status, required, checks: [{id, description, status}]}]
preconditions: [{id, target, requires: [{artifact|handoff, field, equals|in|min}], status}]
handoff_contexts: [{id, producer, version, status, facts, results, constraints, consumed_by, consumed_status}]
change_events: [{id, time, source, event_type, affected, transitions, reason?}]
snapshots: {git_baseline?, file_hashes}
```

### 4E. Hard Constraints

```
DO:
- Preserve all existing user-authored fields when updating status.yaml
- Record every state change in change_events
- Use requires_agent_review: true for medium/low confidence inferences
- Generate preconditions for every LP automatically
- Run quality checklist after every inference pass
- Use Python tools (scan → validate → propagate → apply → render) for mechanical work

DON'T:
- Copy research body text into status.yaml (only IDs, paths, summaries)
- Set any artifact to "ready" without all preconditions passing
- Overwrite or delete user files
- Propagate beyond the dependency graph (no blanket needs_update)
- Treat views/ as source of truth
- Auto-bump handoff versions (requires explicit agent confirmation)
- Edit status.yaml by hand (always go through approved_transitions.json)
```

### 4F. Output Format

```markdown
## Processing Summary
<one paragraph: what was detected, what mode was used>

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
- <blocker/gate>: <what it blocks>

## Recommended Next Actions
1. <highest priority>
2. ...
3. ... (max 5)
```

## Deliverable

The output of this design is a single markdown file that replaces the current `Prompt_project-state-tracker_生成项目使用的Workflow_State.md`. The new file will contain all 4 layers in sequence, totaling ~1850 words, written entirely in English, using imperative verbs and decision tables rather than descriptive prose.

## Success Criteria

1. The improved prompt, when given to Claude/GPT-4, produces a skill that can:
   - Scan a project with existing Research/Decision/Plan files and generate a complete status.yaml with inferred dependencies
   - Detect changes in an existing project and propagate impacts correctly
   - Report quality issues with specific artifact IDs and suggested fixes
2. Token usage is ≤25% of the current prompt for equivalent capability
3. No information loss: every rule in the current prompt is preserved (deduplicated) in Layer 4
4. The inference engine correctly handles the Plan_Viewer project as a test case (R-001, D-001, Plan.dashboard-design relationships)
