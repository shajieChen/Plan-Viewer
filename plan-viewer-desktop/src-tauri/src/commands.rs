use std::path::PathBuf;

use crate::models::{DashboardData, ProjectEntry};
use crate::project_reader;

/// Resolve the path to projects.json.
/// Searches from the executable directory upward until found.
pub fn projects_json_path() -> PathBuf {
    let exe_dir = std::env::current_exe()
        .unwrap_or_default()
        .parent()
        .unwrap_or_else(|| std::path::Path::new("."))
        .to_path_buf();

    let mut dir = exe_dir.clone();
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
    exe_dir.join("projects.json")
}

#[tauri::command]
pub fn get_projects() -> Result<Vec<ProjectEntry>, String> {
    let path = projects_json_path();
    project_reader::load_projects(&path)
}

#[tauri::command]
pub fn get_dashboard_data() -> Result<DashboardData, String> {
    let path = projects_json_path();
    project_reader::read_all_projects(&path)
}

#[tauri::command]
pub fn set_always_on_top(window: tauri::Window, enabled: bool) -> Result<(), String> {
    window
        .set_always_on_top(enabled)
        .map_err(|e| format!("Failed to set always on top: {}", e))
}

// Note: set_opacity is not available in Tauri v2 Window API.
// Opacity is handled purely via CSS on the frontend.
