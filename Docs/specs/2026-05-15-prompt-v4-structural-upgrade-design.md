# Design: Project State Tracker Prompt v4 — Structural Upgrade

## Overview

Upgrade the project-state-tracker prompt from v3 (~1650 words, monolithic) to v4 (~1200 words core + companion file), incorporating two methodological frameworks:

1. **Structured Cognitive Loop (SCL)** — explicit Input/Output/Fail contracts for each pipeline stage
2. **Demand Paging** — trigger/discard conditions for reference knowledge sections

Additionally, offload the §6E Quality Checklist (10 rules) entirely to a new `quality_check.py`, eliminating the highest-variance AI dependency.

## Problem Statement

The v3 prompt works well with strong models (Claude Opus, GPT-4) but exhibits quality degradation with weaker models in three areas:

1. **Quality check execution** — weaker models skip rules, miscount violations, or produce false positives on the 10-item §6E checklist
2. **Pipeline stage ambiguity** — without explicit I/O contracts, models sometimes produce wrong intermediate formats or skip steps
3. **Token waste** — §6 reference rules occupy ~600 words permanently, even when only 1-2 subsections are needed per execution

## Design Philosophy

```
Prompt = cross-era interface contract (stable across AI generations)
Python = deterministic execution layer (immune to AI capability variance)
Companion = on-demand reference material (loaded only when needed)
```

**Stability guarantee across AI capability levels:**
- Strong AI (Opus-class): Core prompt only, rarely loads companion
- Medium AI (Sonnet/GPT-4o): Core prompt + selective companion sections
- Weak AI (local models): Core prompt + full companion, but Python guarantees correctness of mechanical operations

## Architecture: Three-Layer System

```
┌─────────────────────────────────────────────────────────┐
│  Core Prompt (≤1200 words)                               │
│  §0 Context Engineering Meta-Layer (trimmed)             │
│  §1 Core Constraints                                     │
│  §2 Mode Detection & Routing                             │
│  §3 INIT Mode                                            │
│  §4 AUDIT Mode (with inline SCL contracts)               │
│  §5 Output Report                                        │
│  §6 Reference Rules → pointer table to companion         │
│  §7 Hard Constraints                                     │
│  §8 Session Memory                                       │
└─────────────────────────────────────────────────────────┘
         │ demand-page reference
         ▼
┌─────────────────────────────────────────────────────────┐
│  Companion: prompt_appendix.md                           │
│  Part A: SCL Phase Contracts (detailed I/O/Fail specs)   │
│  Part B: Demand Paging Rules (load/discard priorities)   │
│  Part C: §6 Reference Rules (full text, moved from core)│
└─────────────────────────────────────────────────────────┘
         │ deterministic offload
         ▼
┌─────────────────────────────────────────────────────────┐
│  Python Layer                                            │
│  validate_status.py  — schema validation                 │
│  quality_check.py    — §6E semantic quality (NEW)        │
│  dirty_check.py      — file change detection             │
│  scan_changes.py     — change classification             │
│  propagate.py        — dependency graph traversal        │
│  apply_changes.py    — atomic state writes               │
│  render_status.py    — view generation                   │
└─────────────────────────────────────────────────────────┘
```

## Change 1: SCL Phase Contracts in §4

Replace the current §4 pipeline table with an SCL-annotated version. Each step declares:
- **Input**: what data it consumes (file path, JSON structure, or status.yaml)
- **Output**: what it produces (specific JSON/YAML structure with named fields)
- **Fail**: what happens on error (fallback action, never silent failure)

### Pipeline with Contracts

| Step | Action | Input | Output | Fail |
|------|--------|-------|--------|------|
| 0 | `dirty_check.py` | project path | `{status: "dirty"\|"clean", dirty_files: [{path, change_type}]}` | `status: "error"` → fall through to §3 |
| 1 | `scan_changes.py` | project path | `changed_files.json: {changes: [{path, classification, change_type}]}` | empty changes → skip to Step 7 |
| 2 | Re-extract metadata | changed_files.json + source files | updated artifact records (id, title, type, depends_on) | parse error → mark `requires_agent_review: true` |
| 3 | `propagate.py` | changed_files.json + status.yaml | `candidate_transitions.json: {candidates: [{artifact, from, to, reason, requires_agent_review}]}` | no candidates → skip to Step 6 |
| 4 | **Agent reviews candidates** | candidates JSON | `approved_transitions.json: {transitions: [...]}` | <80% confidence on any candidate → hold that candidate, proceed with rest |
| 5 | `apply_changes.py` | approved_transitions.json | updated status.yaml | write error → abort, report error in §5 output |
| 6 | `quality_check.py` | status.yaml | `{passed: [...], failed: [...], warnings: [...], score: "N/10"}` | — (always produces output) |
| 7 | `render_status.py` | status.yaml | views/* + AGENTS.md | — |
| 8 | Emit report (§5 format) | all above outputs | formatted markdown | — |

**Key insight**: Step 4 is the ONLY step requiring AI judgment. All others are deterministic Python execution. The prompt's primary job is teaching AI how to do Step 4 (review candidates) and Step 8 (format report).

### Step 4 Decision Protocol

For each candidate transition, the agent evaluates:
1. Is the `from` status correct? (verify against status.yaml)
2. Is the `to` status a valid transition? (check state machine)
3. Is the `reason` accurate? (verify the claimed change actually occurred)
4. Confidence assessment: high (auto-approve), medium (approve with flag), low (hold)

## Change 2: Demand Paging for §6

The core prompt's §6 becomes a pointer table. Full rules live in companion Part C.

### Pointer Table (in core prompt)

```markdown
## §6 Reference Rules — Demand-Paged

Load subsection from companion ONLY when executing the matching step.
Discard from working memory after step completes.

| Subsection | Load WHEN | Discard WHEN | Priority |
|------------|-----------|--------------|----------|
| §6A ID Extraction | Step 2 (re-extract metadata) | Step 2 done | high |
| §6B Dependency Inference | Step 2 (new files only) | Step 3 starts | high |
| §6C Precondition Gen | Step 4 (LP candidates present) | Step 4 done | medium |
| §6D Propagation Rules | NEVER (in propagate.py) | — | — |
| §6E Quality Checklist | NEVER (in quality_check.py) | — | — |
| §6F Handoff Management | Step 4 (HC candidates present) | Step 4 done | low |
| §6G Schema Reference | On validation error only | Error resolved | low |
```

### Paging Priority Rules (in companion Part B)

When token budget is constrained:
1. Load high-priority sections first
2. If budget allows, load medium
3. Low-priority sections only on explicit need
4. Never load §6D or §6E (fully in Python)

## Change 3: quality_check.py — Full §6E Offload

New Python tool implementing all 10 quality rules deterministically.

### Interface

```
python tools/quality_check.py --project <path> [--scope full|incremental] [--affected <id1,id2,...>]
```

### Output Format

```json
{
  "score": "8/10",
  "passed": [
    {"id": "Q1", "check": "No orphan artifacts", "severity": "warn"},
    ...
  ],
  "failed": [
    {"id": "Q2", "check": "No broken references", "severity": "error",
     "details": "D-001 references R-002 which does not exist"}
  ],
  "warnings": [
    {"id": "Q4", "check": "Every LP has ≥1 PC", "severity": "warn",
     "details": "LP-001 has no preconditions"}
  ]
}
```

### Implementation Rules

| # | Check | Algorithm | Severity |
|---|-------|-----------|----------|
| Q1 | No orphan artifacts | For each artifact: has depends_on OR is type=research | warn |
| Q2 | No broken references | All IDs in depends_on/based_on/affects exist in project | error |
| Q3 | No circular deps | Topological sort on dependency graph; detect cycles | error |
| Q4 | Every LP has ≥1 PC | Filter type=landing_prompt, check preconditions list | warn |
| Q5 | LP consumes_handoffs matches PC | Cross-validate HC refs against precondition entries | error |
| Q6 | Every TP refs ≥1 LP | Filter type=test_prompt, check depends_on contains LP-* | warn |
| Q7 | No "ready" with upstream "needs_update" | BFS upstream from each "ready" artifact | error |
| Q8 | Every HC has producer + ≥1 consumer | Validate handoff_contexts entries | warn |
| Q9 | All gates have ≥1 check | Validate gates[].checks non-empty | warn |
| Q10 | No duplicate IDs | Collect all IDs into set, compare count | error |

### Incremental Mode

When `--scope incremental --affected <ids>` is provided:
- Only check rules that could be affected by the listed artifacts
- Q1-Q3: check affected + their direct dependents
- Q4-Q6: check only if affected includes LP or TP types
- Q7: check affected + upstream chain
- Q8-Q9: check only if affected includes HC or gate changes
- Q10: always full scan (cheap operation)

## Change 4: Core Prompt Content Reduction

### Removed from Core Prompt

| Content | Destination |
|---------|-------------|
| §6A-§6G full rule text (~600 words) | companion Part C |
| §6E quality checklist rules | `quality_check.py` (no longer in any prompt file) |
| §6D propagation rules | `propagate.py` (already exists, remove prompt duplication) |
| §4 Mode Differentiation table | companion Part A (part of SCL contracts) |
| v2→v3 Optimization Delta appendix | remove entirely (historical, no runtime value) |

### Retained in Core Prompt

| Content | Reason |
|---------|--------|
| §0 Context Engineering (trimmed) | Token budget + fast-path still needed |
| §1 Core Constraints | Write boundaries are safety-critical |
| §2 Mode Detection | Entry-point routing must be immediate |
| §3 INIT Mode (steps only) | Scaffold sequence |
| §4 AUDIT Mode (SCL table) | Primary execution path |
| §5 Output Report format | AI needs this for Step 8 |
| §6 Pointer table | Demand paging index |
| §7 Hard Constraints | DO/DON'T list is safety-critical |
| §8 Session Memory | Persistence rules |

### Estimated Word Counts

| Component | v3 | v4 |
|-----------|----|----|
| Core Prompt | ~1650 | ~1200 |
| Companion (prompt_appendix.md) | — | ~800 |
| quality_check.py | — | ~200 lines Python |
| Total "prompt knowledge" | ~1650 | ~2000 (but only ~1200 loaded at any time) |

## Companion File Structure: prompt_appendix.md

```markdown
# Project State Tracker — Companion Reference

## Part A: SCL Phase Contracts

### Step 2: Metadata Re-extraction
- Input contract: ...
- Output contract: ...
- Failure modes: ...
- Recovery actions: ...

### Step 4: Agent Review Protocol
- Input contract: ...
- Decision criteria: ...
- Confidence thresholds: ...
- Output contract: ...

## Part B: Demand Paging Rules

### Loading Protocol
- Check current step number
- Load matching §6 subsection from Part C
- After step completes, mark section as "discardable"

### Priority Matrix
- Budget ≤2000 tokens remaining: load only high-priority
- Budget ≤4000 tokens remaining: load high + medium
- Budget >4000 tokens: load as needed

### Conflict Resolution
- If two sections needed simultaneously: load higher priority first
- If section already loaded from previous step: retain (no reload cost)

## Part C: §6 Reference Rules (Full Text)

### §6A ID & Title Extraction
[full text from v3 §6A]

### §6B Dependency Inference
[full text from v3 §6B]

### §6C Precondition Generation
[full text from v3 §6C]

### §6F Handoff Context Management
[full text from v3 §6F]

### §6G status.yaml Schema
[full text from v3 §6G]
```

## AI Capability Variance Analysis

### Where Different AIs Fail (Before v4)

| Failure Mode | Affected Models | Root Cause | v4 Mitigation |
|---|---|---|---|
| Skip quality rules | GPT-4o-mini, local 7B | Instruction following degrades with list length | Moved to quality_check.py — zero AI involvement |
| Wrong intermediate format | Sonnet 3.5, Gemini Pro | No explicit output schema | SCL contracts define exact JSON structure |
| Load all §6 at once | All models under pressure | No guidance on what to skip | Demand paging pointer table |
| False positive propagation | Weaker models | Misread dependency direction | propagate.py handles this deterministically |
| Inconsistent report format | GPT-4o, local models | Long prompt → format drift | §5 template is short, stays in core |

### What ONLY AI Can Do (Cannot Offload to Python)

| Task | Why AI is Required |
|------|-------------------|
| Step 2: Extract deps from natural language | Requires reading prose, understanding "based on X" semantics |
| Step 4: Review candidate confidence | Requires judgment about whether a change is cosmetic vs semantic |
| Step 8: Generate human-readable summary | Requires natural language generation |
| Mode routing from ambiguous user input | "check if LP-001 can run" requires intent parsing |

### Future-Proofing Strategy

As AI improves:
- The Python layer remains unchanged (deterministic correctness)
- The core prompt remains unchanged (interface contract)
- The companion can be simplified or removed (strong AI won't need it)
- New capabilities can be added by: (1) new Python tool, (2) new pointer in §6 table, (3) new section in companion

## Success Criteria

1. Core prompt ≤1200 words with no functionality loss
2. `quality_check.py` passes all 10 rules on the current Plan_Viewer project state
3. Companion file provides sufficient detail for medium-capability models to execute correctly
4. The SCL contract table in §4 is self-contained — an AI can execute the pipeline by reading only §4 + calling Python tools
5. No rule from v3 is lost; every rule is either in core prompt, companion, or Python

## Deliverables

1. `Prompt_project-state-tracker_v4.md` — the new core prompt (~1200 words)
2. `Prompt_project-state-tracker_appendix.md` — companion reference file (~800 words)
3. `tools/quality_check.py` — deterministic quality validation (~200 lines)
4. Updated `Prompt_project-state-tracker_生成项目使用的Workflow_State.md` — replaced by v4 (or renamed)

## References

- [Context Engineering for AI Agents](https://www.langchain.com/blog/context-engineering-for-agents) — Karpathy's "LLM=CPU, context=RAM" paradigm
- [Structured Cognitive Loop (SCL)](https://arxiv.org/abs/2511.17673) — R-CCAM 5-phase agent cognition architecture
- [Progressive Disclosure in AI Agents](https://www.mindstudio.ai/blog/progressive-disclosure-ai-agents-context-management) — context rot prevention via layered loading
- [Demand Paging for LLM Context Windows](https://arxiv.org/abs/2603.09023) — OS-inspired context memory management
- [Meta-Prompting for AI Systems](https://arxiv.org/abs/2311.11482) — type-theory approach to prompt structure

Content was rephrased for compliance with licensing restrictions.
