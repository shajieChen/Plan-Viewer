# Project State Tracker — Companion Reference

> Load sections on-demand per the pointer table in the core prompt §6.
> Discard from working memory after the corresponding step completes.

---

## Part A: SCL Phase Contracts

### Step 2: Metadata Re-extraction

**Input contract:**
- `changed_files.json` (from scan_changes.py): `{changes: [{path, classification, change_type}]}`
- Source files on disk (for reading content)

**Output contract:**
- Updated artifact records with fields: `{id, title, type, path, depends_on[], status}`
- Each record must have all 5 fields populated

**Failure modes:**
- Parse error reading source file → set `requires_agent_review: true` on that artifact
- ID extraction fails (no pattern match) → use fallback slugify: `<Type>.<filename_stem>`
- Dependency inference ambiguous → register with confidence=medium

**Recovery:** Never skip a changed file. Always produce a record, even if partial.

### Step 4: Agent Review Protocol

**Input contract:**
- `candidate_transitions.json`: `{candidates: [{artifact, from, to, reason, requires_agent_review}]}`
- Current `status.yaml` for verification

**Decision criteria per candidate:**
1. Verify `from` matches current status in status.yaml
2. Verify `to` is a valid state machine transition
3. Verify `reason` — the claimed change actually occurred in the file
4. Assess confidence: high → auto-approve; medium → approve with flag; low → hold

**Confidence thresholds:**
- High (≥90%): Explicit marker found, valid transition, reason verified
- Medium (60-89%): Structural inference only, or reason partially verified
- Low (<60%): No evidence found, or conflicting signals

**Output contract:**
- `approved_transitions.json`: `{transitions: [{artifact, from, to, reason, confidence}]}`
- Held candidates reported in §5 output under "Recommended Next Actions"

---

## Part B: Demand Paging Rules

### Loading Protocol

1. Read current pipeline step number from execution context
2. Consult §6 pointer table in core prompt for matching subsection
3. Load the matching Part C subsection into working memory
4. Execute the step using loaded reference
5. After step completes, mark section as "discardable"
6. On next step, discard previous section (unless still needed)

### Priority Matrix

| Token budget remaining | Load policy |
|------------------------|-------------|
| ≤2000 tokens | High-priority sections ONLY |
| 2001–4000 tokens | High + medium priority |
| >4000 tokens | Load as needed by step |

### Conflict Resolution

- Two sections needed simultaneously → load higher priority first
- Section already loaded from previous step → retain (zero reload cost)
- Section marked "NEVER load" (§6D, §6E) → always skip, Python handles these

---

## Part C: §6 Reference Rules (Full Text)

### §6A ID & Title Extraction

**ID** (first match wins):
1. Filename pattern: `R-001-*.md` → `R-001`, `D-001-*.yaml` → `D-001`, `LP-001-*.md` → `LP-001`, `TP-001-*.md` → `TP-001`
2. YAML front-matter `id:` field
3. H1 with prefix: `# R-001: Title` → `R-001`
4. Fallback: slugify → `Plan.<stem>`, `LP.<stem>`, `TP.<stem>`

**Title** (first match): YAML `title:` → H1 text → humanized filename

**Type** from directory: research/ → research_finding, decisions/ → decision, plan/ → plan, prompts/landing/ → landing_prompt, prompts/test/ → test_prompt

### §6B Dependency Inference (4-Step Process)

**Step A — Reference Scan:** Find artifact IDs in body text.
- Patterns: `R-\d{3}`, `D-\d{3}`, `Plan\.\w+`, `LP-\d{3}`, `TP-\d{3}`, `HC-\d{3}`

**Step B — Semantic Markers:** Keywords near IDs:
- "based on R-001" → depends_on
- "implements D-002" → depends_on
- "invalidates A-001" → invalidates
- "affects Plan.*" → affects
- "requires LP-001 output" → consumes_handoffs

**Step C — Structural Inference** (no explicit markers):
- Decision→R-* = based_on; Plan→D-* = depends_on; LP→Plan.* = depends_on; TP→LP-* = depends_on

**Step D — Confidence Scoring:**
- Explicit semantic marker = high → auto-register
- ID in body, no marker = medium → `requires_agent_review: true`
- Structural only = low → suggest in report only

### §6C Precondition Generation

Per LP:
- Each upstream Plan P → PC: `P.status ∈ [approved, ready]`
- Each downstream TP → PC: `TP.status ∈ [ready]`
- Each consumed HC → PC: `HC.status ∈ [available, consumed], version ≥ 1`

Generate Gate G-001 if any LP has PCs. Sequential IDs: PC-001, PC-002...
Do NOT regenerate existing PCs in AUDIT mode.

### §6F Handoff Context Management

When LP referenced downstream and no HC exists:
- Suggest: `{id: HC-<next>, producer: LP.id, status: draft}`
- Extract facts: bullets under Summary/Output/Results (max 3)
- Extract constraints: sentences with "must not"/"required"/"constraint" (max 3)
- Set consumed_by from downstream depends_on
- Mark `requires_agent_review: true`

Never auto-bump HC versions.

### §6G status.yaml Schema (Compact)

```yaml
meta: {project_name, created, last_updated, total_artifacts, total_research, total_blockers, hotspots}
artifacts: [{id, type, path, status, depends_on[], produces_handoffs?[], consumes_handoffs?[]}]
research_findings: [{id, title, path, status, evidence?[], affects?[]}]
decisions: [{id, title, path, status, based_on[], rejects?[], affects?[]}]
blockers: [{id, title, severity, status, blocks[]}]
gates: [{id, name, status, checks[{id, description, status}]}]
preconditions: [{id, target, requires[{artifact|handoff, field, condition}], status}]
handoff_contexts: [{id, producer, version, status, facts[], constraints[], consumed_by[], consumed_status[]}]
change_events: [{id, time, source, event_type, affected[], transitions[{artifact, from, to, reason}]}]
snapshots: {git_baseline, file_hashes: {path: sha256}}
```
