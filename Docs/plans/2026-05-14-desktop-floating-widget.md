# Plan Viewer Desktop Floating Widget — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Tauri v2 desktop floating widget that displays project swim-lane status, stays always-on-top with transparency effects, and auto-refreshes via file watching.

**Architecture:** Tauri v2 (Rust backend + WebView2) with Preact frontend bundled by Vite. Rust reads `projects.json` and each project's `status/status.yaml`, exposes data via Tauri commands, and pushes file-change events to the frontend. The frontend renders a CSS Grid swim-lane view with a detail panel.

**Tech Stack:** Rust (tauri, serde_yaml, notify), Preact, Vite, marked.js

---

## File Structure

```
plan-viewer-desktop/
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── capabilities/
│   │   └── default.json
│   ├── icons/
│   │   └── icon.png
│   └── src/
│       ├── main.rs
│       ├── commands.rs
│       ├── models.rs
│       ├── project_reader.rs
│       └── watcher.rs
├── src/
│   ├── index.html
│   ├── main.jsx
│   ├── App.jsx
│   ├── components/
│   │   ├── TitleBar.jsx
│   │   ├── SwimLane.jsx
│   │   ├── CompactView.jsx
│   │   └── DetailPanel.jsx
│   ├── hooks/
│   │   ├── useProjects.js
│   │   └── useWindowHover.js
│   └── styles.css
├── package.json
└── vite.config.js
```

**Responsibilities:**

| File | Purpose |
|------|---------|
| `src-tauri/src/models.rs` | Rust data structs (Artifact, ProjectData, etc.) matching Python version |
| `src-tauri/src/project_reader.rs` | Read & validate status.yaml, build ProjectData |
| `src-tauri/src/watcher.rs` | File system watcher with 500ms debounce |
| `src-tauri/src/commands.rs` | Tauri command handlers exposed to frontend |
| `src-tauri/src/main.rs` | App setup, window config, tray, watcher init |
| `src/App.jsx` | Root component, responsive layout switching |
| `src/components/SwimLane.jsx` | CSS Grid swim-lane by Phase |
| `src/components/CompactView.jsx` | Narrow-window compressed list |
| `src/components/DetailPanel.jsx` | Artifact detail + markdown preview |
| `src/components/TitleBar.jsx` | Custom drag region + control buttons |
| `src/hooks/useProjects.js` | Data fetching via Tauri invoke + event listener |
| `src/hooks/useWindowHover.js` | Mouse enter/leave for transparency state |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `plan-viewer-desktop/package.json`
- Create: `plan-viewer-desktop/vite.config.js`
- Create: `plan-viewer-desktop/src/index.html`
- Create: `plan-viewer-desktop/src/main.jsx`
- Create: `plan-viewer-desktop/src-tauri/Cargo.toml`
- Create: `plan-viewer-desktop/src-tauri/tauri.conf.json`
- Create: `plan-viewer-desktop/src-tauri/capabilities/default.json`
- Create: `plan-viewer-desktop/src-tauri/src/main.rs`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "plan-viewer-desktop",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "tauri": "tauri"
  },
  "dependencies": {
    "preact": "^10.22.0",
    "marked": "^12.0.0",
    "@tauri-apps/api": "^2.0.0"
  },
  "devDependencies": {
    "@preact/preset-vite": "^2.8.0",
    "vite": "^5.4.0",
    "@tauri-apps/cli": "^2.0.0"
  }
}
```

- [ ] **Step 2: Create vite.config.js**

```javascript
import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    target: ['es2021', 'chrome100'],
    minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
```

- [ ] **Step 3: Create src/index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Plan Viewer</title>
  <link rel="stylesheet" href="./styles.css" />
</head>
<body>
  <div id="app"></div>
  <script type="module" src="./main.jsx"></script>
</body>
</html>
```

- [ ] **Step 4: Create src/main.jsx**

```jsx
import { render } from 'preact';

function App() {
  return <div>Plan Viewer Desktop — scaffolding OK</div>;
}

render(<App />, document.getElementById('app'));
```

- [ ] **Step 5: Create src-tauri/Cargo.toml**

```toml
[package]
name = "plan-viewer-desktop"
version = "0.1.0"
edition = "2021"

[dependencies]
tauri = { version = "2", features = ["tray-icon"] }
tauri-build = { version = "2", features = [] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yaml = "0.9"
notify = "6"
notify-debouncer-mini = "0.4"

[build-dependencies]
tauri-build = { version = "2", features = [] }
```

- [ ] **Step 6: Create src-tauri/tauri.conf.json**

```json
{
  "$schema": "https://raw.githubusercontent.com/tauri-apps/tauri/dev/crates/tauri-config-schema/schema.json",
  "productName": "Plan Viewer",
  "version": "0.1.0",
  "identifier": "com.plan-viewer.desktop",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build"
  },
  "app": {
    "windows": [
      {
        "label": "main",
        "title": "Plan Viewer",
        "width": 400,
        "height": 300,
        "minWidth": 200,
        "minHeight": 150,
        "decorations": false,
        "transparent": true,
        "alwaysOnTop": true,
        "resizable": true
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/icon.png"
    ]
  }
}
```

- [ ] **Step 7: Create src-tauri/capabilities/default.json**

```json
{
  "identifier": "default",
  "description": "Default capability for the main window",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "core:window:allow-close",
    "core:window:allow-hide",
    "core:window:allow-show",
    "core:window:allow-set-always-on-top",
    "core:window:allow-start-dragging"
  ]
}
```

- [ ] **Step 8: Create src-tauri/src/main.rs (minimal)**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 9: Create build.rs**

Create `plan-viewer-desktop/src-tauri/build.rs`:

```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 10: Install dependencies and verify build**

Run from `plan-viewer-desktop/`:
```bash
npm install
cd src-tauri && cargo check
```

Expected: No compilation errors. Dependencies resolve successfully.

- [ ] **Step 11: Commit**

```bash
git add plan-viewer-desktop/
git commit -m "feat: scaffold Tauri v2 + Preact + Vite project"
```

---

## Task 2: Rust Data Models

**Files:**
- Create: `plan-viewer-desktop/src-tauri/src/models.rs`
- Modify: `plan-viewer-desktop/src-tauri/src/main.rs`

- [ ] **Step 1: Create models.rs with all data structures**

```rust
use serde::{Deserialize, Serialize};

/// A project entry from projects.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectEntry {
    pub path: String,
}

/// Top-level projects.json structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectsConfig {
    pub projects: Vec<ProjectEntry>,
}

/// An artifact tracked in status.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Artifact {
    pub id: String,
    #[serde(rename = "type")]
    pub artifact_type: String,
    pub status: String,
    pub path: String,
    #[serde(default)]
    pub depends_on: Vec<serde_yaml::Value>,
    #[serde(default)]
    pub produces_handoffs: Vec<String>,
    #[serde(default)]
    pub consumes_handoffs: Vec<String>,
    #[serde(default)]
    pub last_checked: String,
    /// Derived at runtime, not from YAML
    #[serde(skip_deserializing, default)]
    pub group: String,
}

/// A change event from status.yaml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChangeEvent {
    #[serde(default)]
    pub id: String,
    #[serde(default)]
    pub time: String,
    #[serde(default)]
    pub source: String,
    #[serde(default)]
    pub event_type: String,
    #[serde(default)]
    pub summary: String,
    #[serde(default)]
    pub affected: Vec<String>,
}

/// Markdown preview for an artifact
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarkdownPreview {
    pub title: String,
    pub excerpt: String,
}

/// Complete project data sent to the frontend
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectData {
    pub meta: serde_yaml::Value,
    pub artifacts: Vec<Artifact>,
    pub change_events: Vec<ChangeEvent>,
    pub markdown_previews: std::collections::HashMap<String, MarkdownPreview>,
}

/// Dashboard data envelope
#[derive(Debug, Clone, Serialize)]
pub struct DashboardData {
    pub projects: std::collections::HashMap<String, ProjectData>,
}

/// Payload emitted when a project file changes
#[derive(Debug, Clone, Serialize)]
pub struct ProjectUpdatePayload {
    pub project_path: String,
    pub timestamp: String,
}
```

- [ ] **Step 2: Add module declaration to main.rs**

Update `src-tauri/src/main.rs`:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod models;

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Verify compilation**

Run from `plan-viewer-desktop/src-tauri/`:
```bash
cargo check
```

Expected: Compiles without errors.

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/models.rs src-tauri/src/main.rs
git commit -m "feat: add Rust data models matching Python dataclasses"
```

---

## Task 3: Project Reader (YAML parsing + group derivation)

**Files:**
- Create: `plan-viewer-desktop/src-tauri/src/project_reader.rs`
- Modify: `plan-viewer-desktop/src-tauri/src/main.rs`

- [ ] **Step 1: Create project_reader.rs**

```rust
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use crate::models::{Artifact, ChangeEvent, DashboardData, MarkdownPreview, ProjectData, ProjectEntry, ProjectsConfig};

/// Derive phase group from artifact ID (case-insensitive priority matching).
pub fn derive_group(artifact_id: &str) -> String {
    let id_lower = artifact_id.to_lowercase();
    if id_lower.contains("phase1") {
        "Phase1".to_string()
    } else if id_lower.contains("phase2") {
        "Phase2".to_string()
    } else if id_lower.contains("phase3") {
        "Phase3".to_string()
    } else if id_lower.contains("phase4") {
        "Phase4".to_string()
    } else if id_lower.contains("phase5") {
        "Phase5".to_string()
    } else if id_lower.contains("codegen") {
        "CodeGen".to_string()
    } else {
        "Other".to_string()
    }
}

/// Load projects.json from the given path.
pub fn load_projects(projects_json_path: &Path) -> Result<Vec<ProjectEntry>, String> {
    if !projects_json_path.exists() {
        return Ok(vec![]);
    }
    let content = fs::read_to_string(projects_json_path)
        .map_err(|e| format!("Failed to read projects.json: {}", e))?;
    let config: ProjectsConfig = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to parse projects.json: {}", e))?;
    Ok(config.projects)
}

/// Extract markdown preview (title + first paragraph, max 200 chars).
fn extract_markdown_preview(file_path: &Path) -> MarkdownPreview {
    let fallback_title = file_path
        .file_stem()
        .unwrap_or_default()
        .to_string_lossy()
        .to_string();

    let content = match fs::read_to_string(file_path) {
        Ok(c) => c,
        Err(_) => {
            return MarkdownPreview {
                title: fallback_title,
                excerpt: "[File not found]".to_string(),
            };
        }
    };

    let mut title = fallback_title.clone();
    let mut found_title = false;
    let mut paragraph_lines: Vec<String> = Vec::new();
    let mut in_paragraph = false;
    let mut in_code_fence = false;

    for (i, line) in content.lines().enumerate() {
        if i >= 50 {
            break;
        }
        let stripped = line.trim();

        if stripped.starts_with("```") {
            if in_paragraph {
                break;
            }
            in_code_fence = !in_code_fence;
            continue;
        }
        if in_code_fence {
            continue;
        }
        if !found_title && stripped.starts_with("# ") {
            title = stripped[2..].trim().to_string();
            found_title = true;
            continue;
        }
        if !in_paragraph && stripped.is_empty() {
            continue;
        }
        if stripped.starts_with('>')
            || stripped.starts_with("##")
            || stripped.starts_with("---")
            || stripped.starts_with("| ")
        {
            if in_paragraph {
                break;
            }
            continue;
        }
        if !stripped.is_empty() {
            in_paragraph = true;
            paragraph_lines.push(stripped.to_string());
        } else if in_paragraph {
            break;
        }
    }

    let mut excerpt = paragraph_lines.join(" ");
    if excerpt.len() > 200 {
        excerpt.truncate(200);
    }

    MarkdownPreview { title, excerpt }
}

/// Read a single project's status.yaml and build ProjectData.
pub fn read_project(project_path: &Path) -> Result<ProjectData, String> {
    let status_file = project_path.join("status").join("status.yaml");
    if !status_file.exists() {
        return Err(format!("status.yaml not found: {}", status_file.display()));
    }

    let content = fs::read_to_string(&status_file)
        .map_err(|e| format!("Failed to read {}: {}", status_file.display(), e))?;

    let data: serde_yaml::Value = serde_yaml::from_str(&content)
        .map_err(|e| format!("Failed to parse YAML {}: {}", status_file.display(), e))?;

    let meta = data.get("meta").cloned().unwrap_or(serde_yaml::Value::Null);

    // Parse artifacts
    let raw_artifacts = data
        .get("artifacts")
        .and_then(|v| v.as_sequence())
        .cloned()
        .unwrap_or_default();

    let mut artifacts: Vec<Artifact> = Vec::new();
    let mut markdown_previews: HashMap<String, MarkdownPreview> = HashMap::new();

    for raw in &raw_artifacts {
        let id = raw.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let artifact_type = raw.get("type").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let status = raw.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let path_str = raw.get("path").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let group = derive_group(&id);

        let depends_on = raw
            .get("depends_on")
            .and_then(|v| v.as_sequence())
            .cloned()
            .unwrap_or_default()
            .into_iter()
            .map(|v| v)
            .collect();

        // Extract markdown preview if path exists
        if !path_str.is_empty() {
            let full_path = project_path.join(&path_str);
            let preview = extract_markdown_preview(&full_path);
            markdown_previews.insert(id.clone(), preview);
        }

        artifacts.push(Artifact {
            id,
            artifact_type,
            status,
            path: path_str,
            depends_on,
            produces_handoffs: vec![],
            consumes_handoffs: vec![],
            last_checked: String::new(),
            group,
        });
    }

    // Parse change_events
    let raw_events = data
        .get("change_events")
        .and_then(|v| v.as_sequence())
        .cloned()
        .unwrap_or_default();

    let change_events: Vec<ChangeEvent> = raw_events
        .iter()
        .map(|raw| ChangeEvent {
            id: raw.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            time: raw.get("time").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            source: raw.get("source").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            event_type: raw.get("event_type").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            summary: raw.get("summary").and_then(|v| v.as_str()).unwrap_or("").to_string(),
            affected: raw
                .get("affected")
                .and_then(|v| v.as_sequence())
                .map(|seq| {
                    seq.iter()
                        .filter_map(|v| v.as_str().map(|s| s.to_string()))
                        .collect()
                })
                .unwrap_or_default(),
        })
        .collect();

    Ok(ProjectData {
        meta,
        artifacts,
        change_events,
        markdown_previews,
    })
}

/// Read all projects and build DashboardData.
pub fn read_all_projects(projects_json_path: &Path) -> Result<DashboardData, String> {
    let entries = load_projects(projects_json_path)?;
    let mut projects: HashMap<String, ProjectData> = HashMap::new();

    for entry in &entries {
        let project_path = PathBuf::from(&entry.path);
        match read_project(&project_path) {
            Ok(data) => {
                let name = data
                    .meta
                    .get("project_name")
                    .and_then(|v| v.as_str())
                    .unwrap_or_else(|| {
                        project_path
                            .file_name()
                            .unwrap_or_default()
                            .to_str()
                            .unwrap_or("unknown")
                    })
                    .to_string();
                projects.insert(name, data);
            }
            Err(e) => {
                eprintln!("Warning: skipping project {}: {}", entry.path, e);
            }
        }
    }

    Ok(DashboardData { projects })
}
```

- [ ] **Step 2: Add module to main.rs**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod models;
mod project_reader;

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Verify compilation**

```bash
cargo check
```

Expected: Compiles without errors.

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/project_reader.rs src-tauri/src/main.rs
git commit -m "feat: implement project reader with YAML parsing and group derivation"
```

---

## Task 4: Tauri Commands

**Files:**
- Create: `plan-viewer-desktop/src-tauri/src/commands.rs`
- Modify: `plan-viewer-desktop/src-tauri/src/main.rs`

- [ ] **Step 1: Create commands.rs**

```rust
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

use crate::models::{DashboardData, ProjectEntry};
use crate::project_reader;

/// Resolve the path to projects.json (same directory as the executable, or workspace root in dev).
fn projects_json_path(app: &AppHandle) -> PathBuf {
    // In development, use the workspace root (parent of src-tauri)
    // In production, use the directory containing the executable
    let resource_dir = app
        .path()
        .resource_dir()
        .unwrap_or_else(|_| std::env::current_exe().unwrap().parent().unwrap().to_path_buf());

    // Walk up to find projects.json (handles both dev and prod)
    let mut dir = resource_dir;
    loop {
        let candidate = dir.join("projects.json");
        if candidate.exists() {
            return candidate;
        }
        if !dir.pop() {
            break;
        }
    }

    // Fallback: next to executable
    std::env::current_exe()
        .unwrap()
        .parent()
        .unwrap()
        .join("projects.json")
}

#[tauri::command]
pub fn get_projects(app: AppHandle) -> Result<Vec<ProjectEntry>, String> {
    let path = projects_json_path(&app);
    project_reader::load_projects(&path)
}

#[tauri::command]
pub fn get_dashboard_data(app: AppHandle) -> Result<DashboardData, String> {
    let path = projects_json_path(&app);
    project_reader::read_all_projects(&path)
}

#[tauri::command]
pub fn set_always_on_top(window: tauri::Window, enabled: bool) -> Result<(), String> {
    window
        .set_always_on_top(enabled)
        .map_err(|e| format!("Failed to set always on top: {}", e))
}

#[tauri::command]
pub fn set_opacity(window: tauri::Window, level: f64) -> Result<(), String> {
    // Clamp between 0.0 and 1.0
    let clamped = level.clamp(0.0, 1.0);
    window
        .set_opacity(clamped)
        .map_err(|e| format!("Failed to set opacity: {}", e))
}
```

- [ ] **Step 2: Register commands in main.rs**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod models;
mod project_reader;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::get_projects,
            commands::get_dashboard_data,
            commands::set_always_on_top,
            commands::set_opacity,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Verify compilation**

```bash
cargo check
```

Expected: Compiles without errors.

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/commands.rs src-tauri/src/main.rs
git commit -m "feat: add Tauri commands for projects, dashboard data, and window control"
```

---

## Task 5: File Watcher

**Files:**
- Create: `plan-viewer-desktop/src-tauri/src/watcher.rs`
- Modify: `plan-viewer-desktop/src-tauri/src/main.rs`

- [ ] **Step 1: Create watcher.rs**

```rust
use std::path::PathBuf;
use std::sync::mpsc;
use std::time::Duration;

use notify::{Config, Event, RecommendedWatcher, RecursiveMode, Watcher};
use notify_debouncer_mini::{new_debouncer, DebouncedEventKind};
use tauri::{AppHandle, Emitter, Manager};

use crate::models::ProjectUpdatePayload;
use crate::project_reader;

/// Start watching status.yaml files for all registered projects.
/// Emits "project-updated" event to the frontend when changes are detected.
pub fn start_watching(app: AppHandle, projects_json_path: PathBuf) {
    std::thread::spawn(move || {
        let entries = match project_reader::load_projects(&projects_json_path) {
            Ok(e) => e,
            Err(e) => {
                eprintln!("Watcher: failed to load projects: {}", e);
                return;
            }
        };

        if entries.is_empty() {
            eprintln!("Watcher: no projects to watch");
            return;
        }

        let (tx, rx) = mpsc::channel();

        let mut debouncer = match new_debouncer(Duration::from_millis(500), tx) {
            Ok(d) => d,
            Err(e) => {
                eprintln!("Watcher: failed to create debouncer: {}", e);
                return;
            }
        };

        // Watch each project's status directory
        for entry in &entries {
            let status_dir = PathBuf::from(&entry.path).join("status");
            if status_dir.exists() {
                if let Err(e) = debouncer.watcher().watch(&status_dir, RecursiveMode::NonRecursive) {
                    eprintln!("Watcher: failed to watch {}: {}", status_dir.display(), e);
                }
            }
        }

        println!("Watcher: monitoring {} project(s)", entries.len());

        // Process events
        loop {
            match rx.recv() {
                Ok(Ok(events)) => {
                    for event in events {
                        let path_str = event.path.to_string_lossy().to_string();
                        if path_str.ends_with("status.yaml") {
                            let timestamp = chrono::Utc::now().to_rfc3339();
                            let payload = ProjectUpdatePayload {
                                project_path: path_str.clone(),
                                timestamp: timestamp.clone(),
                            };
                            if let Err(e) = app.emit("project-updated", &payload) {
                                eprintln!("Watcher: failed to emit event: {}", e);
                            }
                            println!("Watcher: detected change in {}", path_str);
                        }
                    }
                }
                Ok(Err(errors)) => {
                    for e in errors {
                        eprintln!("Watcher error: {:?}", e);
                    }
                }
                Err(e) => {
                    eprintln!("Watcher: channel error: {}", e);
                    break;
                }
            }
        }
    });
}
```

- [ ] **Step 2: Add chrono dependency to Cargo.toml**

Add to `[dependencies]` in `src-tauri/Cargo.toml`:

```toml
chrono = "0.4"
```

- [ ] **Step 3: Integrate watcher in main.rs**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod models;
mod project_reader;
mod watcher;

use std::path::PathBuf;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::get_projects,
            commands::get_dashboard_data,
            commands::set_always_on_top,
            commands::set_opacity,
        ])
        .setup(|app| {
            // Determine projects.json path
            let exe_dir = std::env::current_exe()
                .expect("failed to get exe path")
                .parent()
                .expect("failed to get exe dir")
                .to_path_buf();

            // Search for projects.json: exe dir, then parent dirs
            let projects_path = find_projects_json(&exe_dir);

            // Start file watcher
            watcher::start_watching(app.handle().clone(), projects_path);

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn find_projects_json(start_dir: &PathBuf) -> PathBuf {
    let mut dir = start_dir.clone();
    loop {
        let candidate = dir.join("projects.json");
        if candidate.exists() {
            return candidate;
        }
        if !dir.pop() {
            break;
        }
    }
    start_dir.join("projects.json")
}
```

- [ ] **Step 4: Verify compilation**

```bash
cargo check
```

Expected: Compiles without errors.

- [ ] **Step 5: Commit**

```bash
git add src-tauri/src/watcher.rs src-tauri/src/main.rs src-tauri/Cargo.toml
git commit -m "feat: add file watcher with 500ms debounce for status.yaml changes"
```

---

## Task 6: System Tray

**Files:**
- Modify: `plan-viewer-desktop/src-tauri/src/main.rs`
- Create: `plan-viewer-desktop/src-tauri/icons/icon.png` (placeholder 32x32 PNG)

- [ ] **Step 1: Create a placeholder icon**

Create a simple 32x32 PNG icon at `src-tauri/icons/icon.png`. Can use any tool or copy an existing icon. This is needed for the tray.

- [ ] **Step 2: Add tray setup to main.rs**

Update the `setup` closure in `main.rs`:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod models;
mod project_reader;
mod watcher;

use std::path::PathBuf;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager,
};

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::get_projects,
            commands::get_dashboard_data,
            commands::set_always_on_top,
            commands::set_opacity,
        ])
        .setup(|app| {
            // --- System Tray ---
            let show_item = MenuItem::with_id(app, "show", "显示窗口", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            if window.is_visible().unwrap_or(false) {
                                let _ = window.hide();
                            } else {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                    }
                })
                .build(app)?;

            // --- File Watcher ---
            let exe_dir = std::env::current_exe()
                .expect("failed to get exe path")
                .parent()
                .expect("failed to get exe dir")
                .to_path_buf();

            let projects_path = find_projects_json(&exe_dir);
            watcher::start_watching(app.handle().clone(), projects_path);

            Ok(())
        })
        .on_window_event(|window, event| {
            // Intercept close → hide to tray instead of quitting
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

fn find_projects_json(start_dir: &PathBuf) -> PathBuf {
    let mut dir = start_dir.clone();
    loop {
        let candidate = dir.join("projects.json");
        if candidate.exists() {
            return candidate;
        }
        if !dir.pop() {
            break;
        }
    }
    start_dir.join("projects.json")
}
```

- [ ] **Step 3: Verify compilation**

```bash
cargo check
```

Expected: Compiles without errors.

- [ ] **Step 4: Commit**

```bash
git add src-tauri/src/main.rs src-tauri/icons/
git commit -m "feat: add system tray with show/hide toggle and quit menu"
```

---

## Task 7: Frontend — Custom Title Bar + Transparency Hook

**Files:**
- Create: `plan-viewer-desktop/src/components/TitleBar.jsx`
- Create: `plan-viewer-desktop/src/hooks/useWindowHover.js`
- Create: `plan-viewer-desktop/src/styles.css`
- Modify: `plan-viewer-desktop/src/main.jsx`

- [ ] **Step 1: Create styles.css**

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-idle: rgba(0, 0, 0, 0);
  --bg-active: rgba(20, 20, 30, 0.85);
  --text-color: #e2e8f0;
  --accent: #6366f1;
  --border-radius: 8px;
}

html, body, #app {
  height: 100%;
  overflow: hidden;
  background: transparent;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  color: var(--text-color);
  font-size: 13px;
}

/* Transparency states */
.app-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-radius: var(--border-radius);
  transition: background 0.3s ease, opacity 0.3s ease;
  backdrop-filter: blur(0px);
}

.app-container.idle {
  background: var(--bg-idle);
  opacity: 0.6;
}

.app-container.active {
  background: var(--bg-active);
  opacity: 1.0;
  backdrop-filter: blur(12px);
}

/* Title bar */
.title-bar {
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 8px;
  gap: 4px;
  -webkit-app-region: drag;
}

.title-bar button {
  -webkit-app-region: no-drag;
  background: none;
  border: none;
  color: var(--text-color);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.title-bar button:hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.1);
}

/* Content area */
.content {
  flex: 1;
  overflow: auto;
  padding: 8px;
}

/* Status colors */
.status-draft { background-color: #6b7280; }
.status-reviewed { background-color: #3b82f6; }
.status-approved { background-color: #6366f1; }
.status-ready { background-color: #10b981; }
.status-blocked { background-color: #ef4444; }
.status-needs_update { background-color: #f59e0b; }
.status-invalidated { background-color: #991b1b; }
.status-deprecated { background-color: #78716c; }
.status-archived { background-color: #d1d5db; }
```

- [ ] **Step 2: Create useWindowHover.js**

```javascript
import { useState, useEffect, useRef } from 'preact/hooks';

/**
 * Track mouse enter/leave on the document to toggle transparency state.
 * Returns "idle" or "active". Transitions back to idle after 1.5s delay.
 */
export function useWindowHover() {
  const [state, setState] = useState('idle');
  const timeoutRef = useRef(null);

  useEffect(() => {
    const handleEnter = () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      setState('active');
    };

    const handleLeave = () => {
      timeoutRef.current = setTimeout(() => {
        setState('idle');
      }, 1500);
    };

    document.addEventListener('mouseenter', handleEnter);
    document.addEventListener('mouseleave', handleLeave);

    return () => {
      document.removeEventListener('mouseenter', handleEnter);
      document.removeEventListener('mouseleave', handleLeave);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return state;
}
```

- [ ] **Step 3: Create TitleBar.jsx**

```jsx
import { invoke } from '@tauri-apps/api/core';
import { useState } from 'preact/hooks';

export function TitleBar() {
  const [pinned, setPinned] = useState(true);

  const togglePin = async () => {
    const newState = !pinned;
    await invoke('set_always_on_top', { enabled: newState });
    setPinned(newState);
  };

  const hideWindow = async () => {
    const { getCurrentWindow } = await import('@tauri-apps/api/window');
    const win = getCurrentWindow();
    await win.hide();
  };

  return (
    <div class="title-bar" data-tauri-drag-region>
      <button onClick={togglePin} title={pinned ? '取消置顶' : '置顶'}>
        {pinned ? '📌' : '📍'}
      </button>
      <button onClick={hideWindow} title="最小化到托盘">
        ✕
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Update main.jsx with App shell**

```jsx
import { render } from 'preact';
import { TitleBar } from './components/TitleBar.jsx';
import { useWindowHover } from './hooks/useWindowHover.js';
import './styles.css';

function App() {
  const hoverState = useWindowHover();

  return (
    <div class={`app-container ${hoverState}`}>
      <TitleBar />
      <div class="content">
        <p>Loading projects...</p>
      </div>
    </div>
  );
}

render(<App />, document.getElementById('app'));
```

- [ ] **Step 5: Verify dev mode runs**

```bash
cd plan-viewer-desktop
npm run tauri dev
```

Expected: Window appears, transparent background, title bar visible with pin and close buttons.

- [ ] **Step 6: Commit**

```bash
git add src/
git commit -m "feat: add custom title bar, transparency hook, and base styles"
```

---

## Task 8: Frontend — Data Fetching Hook

**Files:**
- Create: `plan-viewer-desktop/src/hooks/useProjects.js`

- [ ] **Step 1: Create useProjects.js**

```javascript
import { useState, useEffect, useCallback } from 'preact/hooks';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

/**
 * Hook to fetch dashboard data and listen for file-change events.
 * Returns { data, loading, error, selectedProject, setSelectedProject, refresh }
 */
export function useProjects() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedProject, setSelectedProject] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const result = await invoke('get_dashboard_data');
      setData(result);
      setError(null);

      // Auto-select first project if none selected
      if (!selectedProject && result.projects) {
        const keys = Object.keys(result.projects);
        if (keys.length > 0) {
          setSelectedProject(keys[0]);
        }
      }
    } catch (e) {
      setError(typeof e === 'string' ? e : e.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [selectedProject]);

  // Initial load
  useEffect(() => {
    refresh();
  }, []);

  // Listen for file-change events from Rust watcher
  useEffect(() => {
    let unlisten;
    listen('project-updated', (_event) => {
      refresh();
    }).then((fn) => {
      unlisten = fn;
    });

    return () => {
      if (unlisten) unlisten();
    };
  }, [refresh]);

  return { data, loading, error, selectedProject, setSelectedProject, refresh };
}
```

- [ ] **Step 2: Commit**

```bash
git add src/hooks/useProjects.js
git commit -m "feat: add useProjects hook with Tauri invoke and event listener"
```

---

## Task 9: Frontend — SwimLane Component

**Files:**
- Create: `plan-viewer-desktop/src/components/SwimLane.jsx`
- Append to: `plan-viewer-desktop/src/styles.css`

- [ ] **Step 1: Create SwimLane.jsx**

```jsx
/**
 * SwimLane view: CSS Grid layout with one column per Phase group.
 * Each artifact is a colored card in its phase column.
 */
export function SwimLane({ artifacts, onSelectArtifact }) {
  // Group artifacts by their derived group
  const groups = {};
  for (const artifact of artifacts) {
    const group = artifact.group || 'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push(artifact);
  }

  // Define column order
  const columnOrder = ['Phase1', 'Phase2', 'Phase3', 'Phase4', 'Phase5', 'CodeGen', 'Other'];
  const activeColumns = columnOrder.filter((col) => groups[col] && groups[col].length > 0);

  if (activeColumns.length === 0) {
    return <div class="swimlane-empty">No artifacts found</div>;
  }

  return (
    <div class="swimlane" style={{ gridTemplateColumns: `repeat(${activeColumns.length}, 1fr)` }}>
      {activeColumns.map((col) => (
        <div class="swimlane-column" key={col}>
          <div class="swimlane-header">{col}</div>
          <div class="swimlane-cards">
            {groups[col].map((artifact) => (
              <div
                class={`swimlane-card status-${artifact.status}`}
                key={artifact.id}
                onClick={() => onSelectArtifact(artifact)}
                title={`${artifact.id} (${artifact.status})`}
              >
                <span class="card-id">{artifact.id}</span>
                <span class="card-type">{artifact.type}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Add SwimLane styles to styles.css**

Append to `src/styles.css`:

```css
/* SwimLane */
.swimlane {
  display: grid;
  gap: 6px;
  height: 100%;
  min-height: 0;
}

.swimlane-column {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.swimlane-header {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.7;
  padding: 2px 4px;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.swimlane-cards {
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow-y: auto;
  flex: 1;
}

.swimlane-card {
  padding: 4px 6px;
  border-radius: 4px;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.1s;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.swimlane-card:hover {
  transform: scale(1.02);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.card-id {
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-type {
  font-size: 9px;
  opacity: 0.7;
  text-transform: uppercase;
}

.swimlane-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  opacity: 0.5;
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/SwimLane.jsx src/styles.css
git commit -m "feat: add SwimLane component with CSS Grid phase columns"
```

---

## Task 10: Frontend — Compact View

**Files:**
- Create: `plan-viewer-desktop/src/components/CompactView.jsx`
- Append to: `plan-viewer-desktop/src/styles.css`

- [ ] **Step 1: Create CompactView.jsx**

```jsx
/**
 * CompactView: shown when window width < 400px.
 * Displays each phase as a single row with a progress bar.
 */
export function CompactView({ artifacts }) {
  const groups = {};
  for (const artifact of artifacts) {
    const group = artifact.group || 'Other';
    if (!groups[group]) groups[group] = [];
    groups[group].push(artifact);
  }

  const columnOrder = ['Phase1', 'Phase2', 'Phase3', 'Phase4', 'Phase5', 'CodeGen', 'Other'];
  const activeColumns = columnOrder.filter((col) => groups[col] && groups[col].length > 0);

  const completedStatuses = new Set(['ready', 'approved', 'archived']);

  return (
    <div class="compact-view">
      {activeColumns.map((col) => {
        const items = groups[col];
        const done = items.filter((a) => completedStatuses.has(a.status)).length;
        const total = items.length;
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;

        return (
          <div class="compact-row" key={col}>
            <span class="compact-label">{col}</span>
            <div class="compact-bar">
              <div class="compact-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span class="compact-count">{done}/{total}</span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Add CompactView styles**

Append to `src/styles.css`:

```css
/* Compact View */
.compact-view {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px;
}

.compact-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.compact-label {
  font-size: 11px;
  font-weight: 500;
  width: 60px;
  flex-shrink: 0;
}

.compact-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
  overflow: hidden;
}

.compact-bar-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.compact-count {
  font-size: 10px;
  opacity: 0.7;
  width: 30px;
  text-align: right;
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/CompactView.jsx src/styles.css
git commit -m "feat: add CompactView for narrow window mode"
```

---

## Task 11: Frontend — Detail Panel

**Files:**
- Create: `plan-viewer-desktop/src/components/DetailPanel.jsx`
- Append to: `plan-viewer-desktop/src/styles.css`

- [ ] **Step 1: Create DetailPanel.jsx**

```jsx
import { useMemo } from 'preact/hooks';
import { marked } from 'marked';

/**
 * DetailPanel: shows artifact details when a swim-lane card is clicked.
 * Displays: ID, status, type, dependencies, recent change events, markdown preview.
 */
export function DetailPanel({ artifact, changeEvents, markdownPreview, onClose }) {
  if (!artifact) return null;

  // Filter change events related to this artifact
  const relatedEvents = useMemo(() => {
    if (!changeEvents) return [];
    return changeEvents
      .filter((e) => e.affected && e.affected.includes(artifact.id))
      .slice(0, 5);
  }, [changeEvents, artifact.id]);

  // Render markdown excerpt
  const excerptHtml = useMemo(() => {
    if (!markdownPreview || !markdownPreview.excerpt) return '';
    return marked.parse(markdownPreview.excerpt, { breaks: true });
  }, [markdownPreview]);

  return (
    <div class="detail-panel">
      <div class="detail-header">
        <h3 class="detail-title">{artifact.id}</h3>
        <button class="detail-close" onClick={onClose}>✕</button>
      </div>

      <div class="detail-meta">
        <span class={`detail-badge status-${artifact.status}`}>{artifact.status}</span>
        <span class="detail-type">{artifact.type}</span>
      </div>

      {artifact.depends_on && artifact.depends_on.length > 0 && (
        <div class="detail-section">
          <h4>Dependencies</h4>
          <ul class="detail-deps">
            {artifact.depends_on.map((dep, i) => (
              <li key={i}>{typeof dep === 'string' ? dep : dep.id || JSON.stringify(dep)}</li>
            ))}
          </ul>
        </div>
      )}

      {relatedEvents.length > 0 && (
        <div class="detail-section">
          <h4>Recent Changes</h4>
          <ul class="detail-events">
            {relatedEvents.map((ev) => (
              <li key={ev.id}>
                <span class="event-time">{ev.time}</span>
                <span class="event-summary">{ev.summary}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {markdownPreview && (
        <div class="detail-section">
          <h4>{markdownPreview.title}</h4>
          <div class="detail-markdown" dangerouslySetInnerHTML={{ __html: excerptHtml }} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add DetailPanel styles**

Append to `src/styles.css`:

```css
/* Detail Panel */
.detail-panel {
  background: rgba(30, 30, 40, 0.95);
  border-radius: 6px;
  padding: 12px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-title {
  font-size: 14px;
  font-weight: 600;
}

.detail-close {
  background: none;
  border: none;
  color: var(--text-color);
  cursor: pointer;
  font-size: 14px;
  opacity: 0.6;
}

.detail-close:hover {
  opacity: 1;
}

.detail-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.detail-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  color: white;
}

.detail-type {
  font-size: 11px;
  opacity: 0.6;
  text-transform: uppercase;
}

.detail-section {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 8px;
}

.detail-section h4 {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.7;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.detail-deps, .detail-events {
  list-style: none;
  font-size: 12px;
}

.detail-deps li, .detail-events li {
  padding: 2px 0;
  opacity: 0.85;
}

.event-time {
  font-size: 10px;
  opacity: 0.5;
  margin-right: 6px;
}

.detail-markdown {
  font-size: 12px;
  line-height: 1.5;
  opacity: 0.85;
}

.detail-markdown p {
  margin-bottom: 4px;
}
```

- [ ] **Step 3: Commit**

```bash
git add src/components/DetailPanel.jsx src/styles.css
git commit -m "feat: add DetailPanel with dependencies, events, and markdown preview"
```

---

## Task 12: Frontend — App Integration (Responsive Layout)

**Files:**
- Create: `plan-viewer-desktop/src/App.jsx`
- Modify: `plan-viewer-desktop/src/main.jsx`

- [ ] **Step 1: Create App.jsx**

```jsx
import { useState, useEffect } from 'preact/hooks';
import { TitleBar } from './components/TitleBar.jsx';
import { SwimLane } from './components/SwimLane.jsx';
import { CompactView } from './components/CompactView.jsx';
import { DetailPanel } from './components/DetailPanel.jsx';
import { useProjects } from './hooks/useProjects.js';
import { useWindowHover } from './hooks/useWindowHover.js';

export function App() {
  const hoverState = useWindowHover();
  const { data, loading, error, selectedProject, setSelectedProject } = useProjects();
  const [selectedArtifact, setSelectedArtifact] = useState(null);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Determine layout mode
  const isCompact = windowWidth < 400;
  const hasSidePanel = windowWidth >= 600;

  // Get current project data
  const projectData = data && selectedProject ? data.projects[selectedProject] : null;
  const artifacts = projectData ? projectData.artifacts : [];
  const changeEvents = projectData ? projectData.change_events : [];
  const markdownPreviews = projectData ? projectData.markdown_previews : {};

  const projectNames = data ? Object.keys(data.projects) : [];

  return (
    <div class={`app-container ${hoverState}`}>
      <TitleBar />

      {/* Project selector */}
      {projectNames.length > 1 && (
        <div class="project-selector">
          <select
            value={selectedProject || ''}
            onChange={(e) => {
              setSelectedProject(e.target.value);
              setSelectedArtifact(null);
            }}
          >
            {projectNames.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        </div>
      )}

      <div class={`content ${hasSidePanel && selectedArtifact ? 'with-side-panel' : ''}`}>
        {loading && <div class="loading">Loading...</div>}
        {error && <div class="error">{error}</div>}

        {!loading && !error && artifacts.length === 0 && (
          <div class="empty-state">
            <p>No projects configured.</p>
            <p style={{ fontSize: '11px', opacity: 0.6 }}>
              Add projects via the browser dashboard or edit projects.json
            </p>
          </div>
        )}

        {!loading && !error && artifacts.length > 0 && (
          <>
            <div class="main-view">
              {isCompact ? (
                <CompactView artifacts={artifacts} />
              ) : (
                <SwimLane
                  artifacts={artifacts}
                  onSelectArtifact={setSelectedArtifact}
                />
              )}
            </div>

            {selectedArtifact && !isCompact && (
              <div class={`detail-container ${hasSidePanel ? 'side' : 'bottom'}`}>
                <DetailPanel
                  artifact={selectedArtifact}
                  changeEvents={changeEvents}
                  markdownPreview={markdownPreviews[selectedArtifact.id]}
                  onClose={() => setSelectedArtifact(null)}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update main.jsx to use App**

```jsx
import { render } from 'preact';
import { App } from './App.jsx';
import './styles.css';

render(<App />, document.getElementById('app'));
```

- [ ] **Step 3: Add layout styles**

Append to `src/styles.css`:

```css
/* Project selector */
.project-selector {
  padding: 0 8px 4px;
}

.project-selector select {
  width: 100%;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-color);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
}

/* Layout modes */
.content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 8px;
}

.content.with-side-panel {
  flex-direction: row;
  gap: 8px;
}

.main-view {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.detail-container.side {
  width: 240px;
  flex-shrink: 0;
  overflow-y: auto;
}

.detail-container.bottom {
  max-height: 40%;
  overflow-y: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 8px;
  margin-top: 8px;
}

/* States */
.loading, .error, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  opacity: 0.7;
}

.error {
  color: #ef4444;
}
```

- [ ] **Step 4: Run dev mode and verify**

```bash
npm run tauri dev
```

Expected: Window shows with project selector (if multiple projects), swim-lane view, clicking a card opens detail panel. Resizing below 400px switches to compact view.

- [ ] **Step 5: Commit**

```bash
git add src/App.jsx src/main.jsx src/styles.css
git commit -m "feat: integrate responsive layout with swim-lane, compact view, and detail panel"
```

---

## Task 13: Build and Test

**Files:**
- No new files

- [ ] **Step 1: Run production build**

```bash
cd plan-viewer-desktop
npm run tauri build
```

Expected: Build completes, produces `src-tauri/target/release/plan-viewer-desktop.exe`

- [ ] **Step 2: Copy exe to Plan_Viewer root**

```bash
copy src-tauri\target\release\plan-viewer-desktop.exe Q:\Plan_Viewer\plan-viewer-desktop.exe
```

- [ ] **Step 3: Test exe**

Double-click `Q:\Plan_Viewer\plan-viewer-desktop.exe`.

Expected behavior:
- Window appears, always on top, transparent background
- Reads `projects.json` from same directory
- Shows swim-lane for configured projects
- Hovering makes window opaque, leaving makes it fade
- Close button hides to tray
- Tray left-click toggles visibility
- Tray right-click shows menu with "显示窗口" and "退出"

- [ ] **Step 4: Test file watching**

Edit a project's `status/status.yaml` (change an artifact status). The swim-lane should update within ~1 second without manual refresh.

- [ ] **Step 5: Test responsive behavior**

- Resize window to < 400px width → compact view with progress bars
- Resize to 400-599px → swim-lane, click card → detail panel from bottom
- Resize to ≥ 600px → swim-lane + side detail panel

- [ ] **Step 6: Commit final state**

```bash
git add .
git commit -m "feat: complete desktop floating widget build and verification"
```

---

## Summary

| Task | Description | Key Output |
|------|-------------|------------|
| 1 | Project scaffolding | Tauri + Preact + Vite skeleton |
| 2 | Rust data models | `models.rs` with all structs |
| 3 | Project reader | YAML parsing, group derivation, markdown preview |
| 4 | Tauri commands | `get_projects`, `get_dashboard_data`, window controls |
| 5 | File watcher | notify crate with 500ms debounce |
| 6 | System tray | Show/hide toggle, quit menu |
| 7 | Title bar + transparency | Custom drag region, hover state machine |
| 8 | Data fetching hook | `useProjects` with invoke + event listener |
| 9 | SwimLane component | CSS Grid phase columns with status-colored cards |
| 10 | Compact view | Progress bars for narrow window |
| 11 | Detail panel | Artifact info, events, markdown preview |
| 12 | App integration | Responsive layout switching |
| 13 | Build and test | Production exe, manual verification |
