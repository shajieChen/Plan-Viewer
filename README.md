# Plan Viewer

[中文](README_CN.md) | **English**

An interactive visualization tool for project state tracking — Desktop (Tauri) + Web editions.

Transforms `status.yaml` managed by [project-state-tracker](https://github.com/shajieChen/kiro-skill-project-state-tracker) into interactive swim-lane diagrams / DAG dependency graphs, giving you real-time visibility into artifact progress, dependencies, and blockers.

---

## Demo

### Desktop (exe)

![Desktop Demo](Docs/PNG/Plan_Viewer_Exe.gif)

> Always-on-Top floating window, auto-shrinks when cursor leaves, one-click focus on bound process.

### Web

![Web Demo](Docs/PNG/Website_Exe.gif)

> Access directly in browser, Mermaid charts + Markdown preview, REST API for external integrations.

---

## Skill Integration Architecture

Plan Viewer is not a standalone tool — it is the **visualization terminal** of a closed-loop Skill workflow. The diagram below shows how each Skill collaborates:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Skill Closed-Loop Workflow                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────┐  register draft  ┌───────────────────┐              │
│  │  PSS          │ ───────────────▶ │  PST              │              │
│  │  (Spec Author)│                  │  (State Tracking) │              │
│  │               │◀── read deps ──  │                   │              │
│  └───────┬───────┘                  └─────────┬─────────┘              │
│          │                                    │                         │
│          │ generate LandingPrompt             │ generate views/ + README│
│          ▼                                    ▼                         │
│  ┌───────────────┐                  ┌───────────────────┐              │
│  │  ELP          │  flow back status│  Plan Viewer      │              │
│  │  (Execute LP) │ ───────────────▶ │  (Visualization)  │              │
│  └───────┬───────┘                  └───────────────────┘              │
│          │                                    ▲                         │
│          │ persist Result                     │ read status.yaml        │
│          ▼                                    │                         │
│  ┌───────────────┐                            │                         │
│  │  Result/      │ ─── archive history ───────┘                         │
│  └───────────────┘                                                      │
│                                                                         │
│  Loop: PSS → PST → ELP → PST (audit & advance) → Loop                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
status.yaml ──read──▶ Plan Viewer (exe/web) ──display──▶ Swim-lane / DAG
     ▲                                                        │
     │                                                        │ click to change status
     └──────────────── write back ────────────────────────────┘
```

---

## Skill Responsibilities

| Skill | Full Name | Trigger | Responsibility |
|-------|-----------|---------|----------------|
| **PST** | project-state-tracker | `"init"` / `"audit"` | 9-state machine, dependency graph, SCL Pipeline, view rendering |
| **PSS** | project-state-spec | `Skill PSS + new <topic>` | Three-phase Spec authoring (R→D→Task), generates Plan + LP + TP |
| **ELP** | Execute-LandingPrompt | `Skill ELP + <LP file>` | Executes LP implementation tasks, auto-flows status back to status.yaml |
| **MQA** | module-quick-analysis | `Skill MQA + <module>` | 5-minute rapid understanding of unfamiliar module design & responsibilities |

### Skill Installation

All Skill source code lives in `Tools/Skills/`, distributed to AI Agents via a unified install script:

```bash
python Tools/install_skills.py
```

Supported Agent targets:

| Agent | Install Method | Target Path |
|-------|---------------|-------------|
| Kiro | Folder copy | `~/.kiro/skills/<skill>/` |
| Cursor | MDC single file | `~/.cursor/rules/<skill>.mdc` |
| Claude | Folder copy | `~/.claude/skills/<skill>/` |
| Copilot | Merged file | `~/.github/copilot-instructions.md` |
| Codex | Merged file | `~/.codex/AGENTS.md` |

---

## Feature Comparison: Desktop vs Web

| Feature | Desktop (exe) | Web |
|---------|:---:|:---:|
| Swim-lane / DAG dependency graph | ✅ | ✅ |
| Node detail panel (deps, change_events) | ✅ | ✅ |
| Markdown preview | ✅ | ✅ |
| Multi-project management (add/delete/switch) | ✅ | ✅ |
| Click-to-change status (writes back to status.yaml) | ✅ | ✅ |
| Smart Group Derivation (dependency-chain clustering) | ✅ | ✅ |
| Always-on-Top floating window | ✅ | ❌ |
| Auto window resize (shrinks when cursor leaves) | ✅ | ❌ |
| Process binding + one-click focus | ✅ | ❌ |
| Glassmorphism dark transparent theme | ✅ | ❌ |
| Window size memory (per-project) | ✅ | ❌ |
| No install needed, browser access | ❌ | ✅ |
| Mermaid chart rendering | ❌ | ✅ |
| REST API (project CRUD / status changes) | ❌ | ✅ |
| Auto-open browser on start | ❌ | ✅ |

---

## Typical Workflow (From Zero to One)

The following scenario demonstrates a complete project management cycle, showing how each component connects:

```
Step 1 ─ Initialize project structure
         $ cd my-project
         Tell AI: "init"
         → PST creates status/ directory + status.yaml + schema.yaml
                                                          │
Step 2 ─ Author Spec                                     │
         Tell AI: "Skill PSS + new user-auth"            │
         → PSS guides requirement gathering              │
         → Generates Research + Decision                  │
         → Generates Plan + LandingPrompt + TestPrompt   │
         → Auto-registers to status.yaml (draft)         │
                                                          │
Step 3 ─ PST Audit + Render Views                        │
         Tell AI: "audit"                                │
         → PST runs SCL Pipeline                         │
         → Generates views/ (swim-lane, DAG, stats)      │
         → Updates README                                │
                                                          │
Step 4 ─ Execute LandingPrompt                           │
         Tell AI: "Skill ELP + prompts/landing/LP-001.md"│
         → ELP executes implementation steps             │
         → Auto-flows status on completion (draft→ready) │
         → Archives handoff to Result/                   │
                                                          │
Step 5 ─ View Progress                                   │
         Desktop: run build.bat → floating window        │
         Web: python dashboard_server.py → browser opens │
         → Swim-lane shows all artifact states           │
         → Click nodes to view details / change status   │
                                                          │
Step 6 ─ Loop                                            │
         → PST audit discovers next batch of ready items │
         → Return to Step 2, continue next Spec round    │
```

---

## Quick Start

### Prerequisites

- Python 3.9+ (Web edition)
- Rust + Node.js (Desktop compilation)
- `pip install -r requirements.txt`

### Web Edition

```bash
python dashboard_server.py
# Auto-opens http://localhost:8000/dashboard.html
```

Or use the shortcut script:

```bash
serve.bat
```

### Desktop Edition

```bash
cd plan-viewer-desktop
npm install
npm run tauri build
# Output in src-tauri/target/release/
```

Development mode:

```bash
npm run tauri dev
```

---

## Project Structure

```
Plan_Viewer/
├── dashboard_server.py      # Web HTTP server + REST API
├── dashboard_template.html  # Web HTML template (React CDN + Mermaid)
├── render_dashboard.py      # Dashboard generator (reads status.yaml → HTML)
├── project_store.py         # Project list persistence (projects.json)
├── serve.bat                # One-click web server launch
├── build.bat                # One-click desktop build
│
├── plan-viewer-desktop/     # Desktop edition (Tauri + Preact + Vite)
│   ├── src/
│   │   ├── App.jsx          # Main app (swim-lane, detail panel, process binding)
│   │   ├── components/      # UI components (TitleBar, SwimLane, DetailPanel...)
│   │   └── hooks/           # Custom Hooks (useProjects, useWindowAutoShrink...)
│   └── src-tauri/
│       └── src/             # Rust backend (process enum, window focus, file ops)
│
├── Tools/
│   ├── Skills/              # Skill source (git submodules)
│   │   ├── project-state-tracker/
│   │   ├── project-state-spec/
│   │   ├── Execute-LandingPrompt/
│   │   ├── module-quick-analysis/
│   │   └── OpenSpec/
│   └── install_skills.py    # Unified Skill installer (→ Kiro/Cursor/Claude/Copilot/Codex)
│
├── Docs/
│   ├── PNG/                 # Demo GIFs
│   ├── specs/               # Design documents
│   ├── plans/               # Implementation plans
│   └── research/            # Research documents
│
├── views/                   # Generated Dashboard HTML
└── tests/                   # pytest tests
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop Framework | Tauri 2.x (Rust backend) |
| Desktop Frontend | Preact + Vite |
| Web Frontend | React 18 CDN + Tailwind CSS + Mermaid.js + marked.js |
| Web Backend | Python stdlib `http.server` + PyYAML |
| Data Format | YAML (status.yaml) + JSON (projects.json) |
| Testing | pytest + Hypothesis (property-based testing) |
| Skill Distribution | Python script → 5 Agent formats |

---

## REST API (Web Edition)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Add project |
| POST | `/api/projects/initialize` | Initialize project structure |
| DELETE | `/api/projects` | Delete project |
| PATCH | `/api/artifact/status` | Change artifact status |
| POST | `/api/regenerate` | Manually trigger Dashboard regeneration |
| GET | `/api/file?path=<rel>` | Get project source file content |

---

## Testing

```bash
pip install -r requirements.txt
pytest tests/
```

Uses [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing to ensure correctness of state machine transitions and data parsing.

---

## Related Repositories

| Skill | Repository | Purpose |
|-------|-----------|---------|
| project-state-tracker | [GitHub](https://github.com/shajieChen/kiro-skill-project-state-tracker) | Artifact lifecycle management + state tracking |
| project-state-spec | [GitHub](https://github.com/shajieChen/kiro-skill-project-state-spec) | Three-phase Spec authoring (R→D→Task) |
| Execute-LandingPrompt | [GitHub](https://github.com/shajieChen/kiro-skill-execute-landingprompt) | Execute LP and flow status back |
| module-quick-analysis | [GitHub](https://github.com/shajieChen/kiro-skill-module-quick-analysis) | Rapid module analysis |
| OpenSpec | [GitHub](https://github.com/Fission-AI/OpenSpec) | Spec open/navigation |

---

## License

MIT
