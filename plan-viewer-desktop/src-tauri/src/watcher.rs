use std::path::PathBuf;
use std::sync::mpsc;
use std::time::Duration;

use notify_debouncer_mini::new_debouncer;
use tauri::{AppHandle, Emitter};

use crate::models::ProjectUpdatePayload;
use crate::project_reader;

/// Start watching status.yaml files for all registered projects.
/// Emits "project-updated" event to the frontend when changes are detected.
/// Runs in a background thread.
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
            println!("Watcher: no projects to watch");
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
        let mut watched_count = 0;
        for entry in &entries {
            let status_dir = PathBuf::from(&entry.path).join("status");
            if status_dir.exists() {
                if let Err(e) = debouncer
                    .watcher()
                    .watch(&status_dir, notify::RecursiveMode::NonRecursive)
                {
                    eprintln!("Watcher: failed to watch {}: {}", status_dir.display(), e);
                } else {
                    watched_count += 1;
                }
            }
        }

        println!("Watcher: monitoring {} project(s)", watched_count);

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
                                timestamp,
                            };
                            if let Err(e) = app.emit("project-updated", &payload) {
                                eprintln!("Watcher: failed to emit event: {}", e);
                            }
                            println!("Watcher: detected change in {}", path_str);
                        }
                    }
                }
                Ok(Err(e)) => {
                    eprintln!("Watcher error: {:?}", e);
                }
                Err(e) => {
                    eprintln!("Watcher: channel closed: {}", e);
                    break;
                }
            }
        }
    });
}
