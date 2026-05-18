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

#[tauri::command]
pub fn read_window_sizes(app: tauri::AppHandle) -> Result<String, String> {
    use tauri::Manager;

    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;

    let file_path = data_dir.join("window-sizes.json");

    match std::fs::read_to_string(&file_path) {
        Ok(content) => Ok(content),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok("{}".to_string()),
        Err(e) => Err(format!("Failed to read window-sizes.json: {}", e)),
    }
}

#[tauri::command]
pub fn write_window_sizes(app: tauri::AppHandle, data: String) -> Result<(), String> {
    use tauri::Manager;

    let data_dir = app
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;

    // Ensure the data directory exists
    std::fs::create_dir_all(&data_dir)
        .map_err(|e| format!("Failed to create app data dir: {}", e))?;

    let file_path = data_dir.join("window-sizes.json");
    let tmp_path = data_dir.join("window-sizes.json.tmp");

    // Write to temporary file first
    std::fs::write(&tmp_path, &data)
        .map_err(|e| format!("Failed to write temp file: {}", e))?;

    // Atomic rename
    std::fs::rename(&tmp_path, &file_path)
        .map_err(|e| format!("Failed to rename temp file: {}", e))?;

    Ok(())
}
