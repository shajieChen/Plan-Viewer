use std::path::{Path, PathBuf};

use tauri::{AppHandle, Emitter};

use crate::models::{
    AddProjectError, AddProjectResponse, DashboardData, DeleteProjectResponse, ProjectEntry,
    ProjectsConfig, ProjectUpdatePayload, UpdateStatusResponse, VALID_STATUSES,
};
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

/// Normalize a path by resolving `.`, `..`, trailing separators, and producing
/// an absolute path. Uses `std::fs::canonicalize` when the path exists on disk;
/// otherwise falls back to manual component-based normalization.
/// On Windows, strips the `\\?\` extended-length prefix that canonicalize adds.
pub(crate) fn normalize_path(input: &str) -> Result<PathBuf, AddProjectError> {
    let path = PathBuf::from(input);
    let canonical = std::fs::canonicalize(&path).unwrap_or_else(|_| {
        // If canonicalize fails (path doesn't exist yet), do manual normalization
        let mut result = PathBuf::new();
        for component in path.components() {
            match component {
                std::path::Component::ParentDir => {
                    result.pop();
                }
                std::path::Component::CurDir => {}
                other => result.push(other),
            }
        }
        result
    });

    // On Windows, canonicalize produces \\?\ prefix — strip it for cleaner paths
    #[cfg(windows)]
    {
        let s = canonical.to_string_lossy();
        if let Some(stripped) = s.strip_prefix(r"\\?\") {
            return Ok(PathBuf::from(stripped));
        }
    }

    Ok(canonical)
}

/// Normalize a path string for comparison purposes.
/// On Windows: strips `\\?\` extended-length prefix, lowercases, and normalizes
/// all slashes to backslash.
/// On all platforms: strips trailing path separators.
pub(crate) fn normalize_for_compare(path: &str) -> String {
    let p = path.trim_end_matches(['/', '\\']);
    #[cfg(windows)]
    {
        let stripped = p.strip_prefix(r"\\?\").unwrap_or(p);
        stripped.to_lowercase().replace('/', "\\")
    }
    #[cfg(not(windows))]
    {
        p.to_string()
    }
}

/// Load projects from projects.json, or return an empty list if the file doesn't exist.
pub(crate) fn load_or_create_projects(projects_path: &Path) -> Result<Vec<ProjectEntry>, AddProjectError> {
    if !projects_path.exists() {
        return Ok(vec![]);
    }
    let content = std::fs::read_to_string(projects_path).map_err(|e| AddProjectError {
        code: "read_failed".into(),
        message: format!("读取 projects.json 失败: {}", e),
    })?;
    let config: ProjectsConfig = serde_json::from_str(&content).map_err(|e| AddProjectError {
        code: "read_failed".into(),
        message: format!("解析 projects.json 失败: {}", e),
    })?;
    Ok(config.projects)
}

/// Atomic write: serialize config to JSON, write to .tmp file, then rename over original.
fn atomic_write_projects(projects_path: &Path, config: &ProjectsConfig) -> Result<(), AddProjectError> {
    let json = serde_json::to_string_pretty(config).map_err(|e| AddProjectError {
        code: "write_failed".into(),
        message: format!("序列化失败: {}", e),
    })?;

    // Ensure parent directory exists
    if let Some(parent) = projects_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| AddProjectError {
            code: "write_failed".into(),
            message: format!("创建目录失败: {}", e),
        })?;
    }

    let tmp_path = projects_path.with_extension("json.tmp");

    std::fs::write(&tmp_path, &json).map_err(|e| AddProjectError {
        code: "write_failed".into(),
        message: format!("写入失败: {}", e),
    })?;

    std::fs::rename(&tmp_path, projects_path).map_err(|e| {
        let _ = std::fs::remove_file(&tmp_path);
        AddProjectError {
            code: "write_failed".into(),
            message: format!("写入失败: {}", e),
        }
    })?;

    Ok(())
}

/// Validate that a path is not empty or whitespace-only.
/// Returns Ok(()) if the path has non-whitespace content, or an AddProjectError with
/// code "empty_path" if the path is empty or whitespace-only.
pub(crate) fn validate_path_not_empty(path: &str) -> Result<(), AddProjectError> {
    if path.trim().is_empty() {
        return Err(AddProjectError {
            code: "empty_path".into(),
            message: "路径不能为空".into(),
        });
    }
    Ok(())
}

#[tauri::command]
pub fn add_project(app: AppHandle, path: String) -> Result<AddProjectResponse, AddProjectError> {
    // 1. Reject empty/whitespace
    validate_path_not_empty(&path)?;

    // 2. Normalize path
    let normalized = normalize_path(&path)?;

    // 3. Check existence (must be a directory)
    if !normalized.exists() || !normalized.is_dir() {
        return Err(AddProjectError {
            code: "path_not_found".into(),
            message: "路径不存在".into(),
        });
    }

    // 4. Check duplicate
    let projects_path = projects_json_path();
    let entries = load_or_create_projects(&projects_path)?;
    let norm_str = normalized.to_string_lossy().to_string();
    if entries
        .iter()
        .any(|e| normalize_for_compare(&e.path) == normalize_for_compare(&norm_str))
    {
        return Err(AddProjectError {
            code: "duplicate_project".into(),
            message: "项目已存在".into(),
        });
    }

    // 5. Check initialization
    let not_initialized = !normalized.join("status").join("status.yaml").exists();

    // 6. Persist (atomic write)
    let mut config = ProjectsConfig { projects: entries };
    config.projects.push(ProjectEntry {
        path: norm_str.clone(),
    });
    atomic_write_projects(&projects_path, &config)?;

    // 7. Emit event
    let _ = app.emit(
        "project-updated",
        &ProjectUpdatePayload {
            project_path: norm_str.clone(),
            timestamp: chrono::Utc::now().to_rfc3339(),
        },
    );

    Ok(AddProjectResponse {
        path: norm_str,
        not_initialized,
    })
}

/// Testable helper: core logic of delete_project without AppHandle or event emission.
/// Accepts an explicit projects_path so tests can point to a temp file.
pub(crate) fn delete_project_impl(
    projects_path: &Path,
    path: &str,
) -> Result<DeleteProjectResponse, AddProjectError> {
    // 1. Reject empty/whitespace
    validate_path_not_empty(path)?;

    // 2. Load current projects
    let entries = load_or_create_projects(projects_path)?;

    // 3. Find matching entry using normalized comparison
    let norm_input = normalize_for_compare(path);
    let index = entries
        .iter()
        .position(|e| normalize_for_compare(&e.path) == norm_input)
        .ok_or_else(|| AddProjectError {
            code: "project_not_found".into(),
            message: "项目未找到".into(),
        })?;

    // 4. Remove entry and persist
    let mut config = ProjectsConfig { projects: entries };
    let removed = config.projects.remove(index);
    atomic_write_projects(projects_path, &config)?;

    Ok(DeleteProjectResponse {
        path: removed.path,
    })
}

#[tauri::command]
pub fn delete_project(app: AppHandle, path: String) -> Result<DeleteProjectResponse, AddProjectError> {
    let projects_path = projects_json_path();
    let result = delete_project_impl(&projects_path, &path)?;

    // Emit event on success
    let _ = app.emit(
        "project-updated",
        &ProjectUpdatePayload {
            project_path: result.path.clone(),
            timestamp: chrono::Utc::now().to_rfc3339(),
        },
    );

    Ok(result)
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

/// Resolve a project name to its filesystem path by matching against
/// `meta.project_name` in each project's status.yaml, or falling back
/// to the directory name.
#[tauri::command]
pub fn resolve_project_path(project_name: String) -> Result<String, String> {
    resolve_project_path_impl(&project_name).map(|p| p.to_string_lossy().to_string())
}

fn resolve_project_path_impl(project_name: &str) -> Result<PathBuf, String> {
    let projects_path = projects_json_path();
    let entries = project_reader::load_projects(&projects_path)?;

    for entry in &entries {
        let project_path = Path::new(&entry.path);
        let status_file = project_path.join("status").join("status.yaml");

        // First try matching by directory name (works for all projects)
        let dir_name = project_path
            .file_name()
            .unwrap_or_default()
            .to_str()
            .unwrap_or("");

        if dir_name == project_name {
            return Ok(project_path.to_path_buf());
        }

        // Then try matching by meta.project_name from status.yaml
        if !status_file.exists() {
            continue;
        }
        let content = match std::fs::read_to_string(&status_file) {
            Ok(c) => c,
            Err(_) => continue,
        };
        let data: serde_yaml::Value = match serde_yaml::from_str(&content) {
            Ok(d) => d,
            Err(_) => continue,
        };
        let meta_name = data
            .get("meta")
            .and_then(|m| m.get("project_name"))
            .and_then(|v| v.as_str())
            .unwrap_or("");

        if meta_name == project_name {
            return Ok(project_path.to_path_buf());
        }
    }

    Err(format!("Project not found: '{}'", project_name))
}

/// Testable helper: update an artifact's status directly in a given status.yaml file.
/// This function encapsulates the core validation and file-mutation logic without
/// requiring Tauri app state or project resolution from projects.json.
pub fn update_status_in_file(
    status_file: &Path,
    artifact_id: &str,
    new_status: &str,
) -> Result<UpdateStatusResponse, String> {
    // Validate new_status against allowed values
    if !VALID_STATUSES.contains(&new_status) {
        return Err(format!(
            "Invalid status '{}'. Valid values: {}",
            new_status,
            VALID_STATUSES.join(", ")
        ));
    }

    // Read status.yaml
    let content = std::fs::read_to_string(status_file)
        .map_err(|e| format!("Failed to read status.yaml: {}", e))?;

    // Parse as serde_yaml::Value
    let mut data: serde_yaml::Value = serde_yaml::from_str(&content)
        .map_err(|e| format!("Failed to parse status.yaml: {}", e))?;

    // Find artifact by id in the artifacts sequence
    let artifacts = data
        .get_mut("artifacts")
        .and_then(|v| v.as_sequence_mut())
        .ok_or_else(|| format!("Artifact not found: '{}' in file", artifact_id))?;

    let artifact = artifacts
        .iter_mut()
        .find(|a| {
            a.get("id")
                .and_then(|v| v.as_str())
                .map(|s| s == artifact_id)
                .unwrap_or(false)
        })
        .ok_or_else(|| format!("Artifact not found: '{}' in file", artifact_id))?;

    // Update the artifact's status field
    if let Some(mapping) = artifact.as_mapping_mut() {
        mapping.insert(
            serde_yaml::Value::String("status".to_string()),
            serde_yaml::Value::String(new_status.to_string()),
        );
    }

    // Update meta.last_updated to current UTC ISO 8601
    let now = chrono::Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string();
    if let Some(meta) = data.get_mut("meta").and_then(|m| m.as_mapping_mut()) {
        meta.insert(
            serde_yaml::Value::String("last_updated".to_string()),
            serde_yaml::Value::String(now),
        );
    }

    // Serialize back to YAML
    let yaml_output = serde_yaml::to_string(&data)
        .map_err(|e| format!("Failed to write status.yaml: {}", e))?;

    // Write to .tmp file then atomic rename
    let tmp_path = status_file.with_extension("yaml.tmp");
    std::fs::write(&tmp_path, &yaml_output)
        .map_err(|e| format!("Failed to write status.yaml: {}", e))?;

    std::fs::rename(&tmp_path, status_file)
        .map_err(|e| {
            let _ = std::fs::remove_file(&tmp_path);
            format!("Failed to write status.yaml: {}", e)
        })?;

    Ok(UpdateStatusResponse {
        artifact_id: artifact_id.to_string(),
        new_status: new_status.to_string(),
    })
}

#[tauri::command]
pub fn update_artifact_status(
    project_name: String,
    artifact_id: String,
    new_status: String,
) -> Result<UpdateStatusResponse, String> {
    // Validate non-empty parameters
    if project_name.is_empty() {
        return Err("Missing required parameter: project_name".to_string());
    }
    if artifact_id.is_empty() {
        return Err("Missing required parameter: artifact_id".to_string());
    }
    if new_status.is_empty() {
        return Err("Missing required parameter: new_status".to_string());
    }

    // Resolve project path
    let project_path = resolve_project_path_impl(&project_name)?;
    let status_file = project_path.join("status").join("status.yaml");

    update_status_in_file(&status_file, &artifact_id, &new_status)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::VALID_STATUSES;
    use proptest::prelude::*;
    use std::fs;
    use tempfile::TempDir;

    /// Create a temporary status.yaml with the given number of artifacts.
    /// Returns (TempDir, path to status.yaml, list of artifact IDs).
    fn create_test_status_yaml(artifact_count: usize) -> (TempDir, PathBuf, Vec<String>) {
        let tmp_dir = TempDir::new().unwrap();
        let status_file = tmp_dir.path().join("status.yaml");

        let mut artifact_ids = Vec::new();
        let mut artifacts_yaml = String::new();

        for i in 0..artifact_count {
            let id = format!("artifact-{}", i);
            artifact_ids.push(id.clone());
            artifacts_yaml.push_str(&format!(
                "  - id: \"{}\"\n    type: \"research\"\n    status: \"draft\"\n    path: \"docs/{}.md\"\n",
                id, id
            ));
        }

        let yaml_content = format!(
            "meta:\n  project_name: \"test-project\"\n  last_updated: \"2025-01-01T00:00:00Z\"\nartifacts:\n{}",
            artifacts_yaml
        );

        fs::write(&status_file, &yaml_content).unwrap();

        (tmp_dir, status_file, artifact_ids)
    }

    // Feature: add-project-button, Property 2: Whitespace-only paths are always rejected
    // **Validates: Requirements 7.5**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]
        #[test]
        fn whitespace_only_paths_rejected(
            ws in "[ \\t\\n\\r]*",
        ) {
            // Act: validate the whitespace-only (or empty) string
            let result = validate_path_not_empty(&ws);

            // Assert: must be an error with code "empty_path"
            prop_assert!(result.is_err(), "Expected error for whitespace-only path {:?}, got Ok", ws);
            let err = result.unwrap_err();
            prop_assert_eq!(
                &err.code, "empty_path",
                "Expected error code 'empty_path' for input {:?}, got '{}'", ws, err.code
            );
            prop_assert!(
                !err.message.is_empty(),
                "Error message should not be empty for input {:?}", ws
            );
        }
    }

    // Feature: status-change-interaction, Property 1: Status update round-trip
    // **Validates: Requirements 1.1, 1.2**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]
        #[test]
        fn status_update_round_trip(
            status_idx in 0..9usize,
            artifact_idx in 0..5usize,
        ) {
            let artifact_count = 5;
            let (_tmp_dir, status_file, artifact_ids) = create_test_status_yaml(artifact_count);

            let chosen_status = VALID_STATUSES[status_idx];
            let chosen_artifact = &artifact_ids[artifact_idx];

            // Act: call update logic
            let result = update_status_in_file(&status_file, chosen_artifact, chosen_status);

            // Assert: result is Ok with correct fields
            let response = result.unwrap();
            prop_assert_eq!(&response.artifact_id, chosen_artifact);
            prop_assert_eq!(&response.new_status, chosen_status);

            // Assert: re-read file, verify status matches
            let content = fs::read_to_string(&status_file).unwrap();
            let data: serde_yaml::Value = serde_yaml::from_str(&content).unwrap();

            let artifacts = data.get("artifacts").unwrap().as_sequence().unwrap();
            let artifact = artifacts.iter().find(|a| {
                a.get("id").and_then(|v| v.as_str()) == Some(chosen_artifact.as_str())
            }).unwrap();

            let file_status = artifact.get("status").unwrap().as_str().unwrap();
            prop_assert_eq!(file_status, chosen_status);

            // Assert: meta.last_updated is valid ISO 8601 UTC timestamp
            let last_updated = data.get("meta").unwrap()
                .get("last_updated").unwrap()
                .as_str().unwrap();

            // Verify it matches YYYY-MM-DDTHH:MM:SSZ format
            let parsed = chrono::NaiveDateTime::parse_from_str(last_updated, "%Y-%m-%dT%H:%M:%SZ");
            prop_assert!(parsed.is_ok(), "meta.last_updated '{}' is not valid ISO 8601 UTC", last_updated);
        }
    }

    // Feature: status-change-interaction, Property 2: Invalid status rejection
    // **Validates: Requirements 1.3**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]
        #[test]
        fn invalid_status_rejected(
            bad_status in "[a-z]{1,20}".prop_filter("not a valid status", |s| !VALID_STATUSES.contains(&s.as_str())),
        ) {
            // Setup: create temp status.yaml with known content
            let (_tmp_dir, status_file, artifact_ids) = create_test_status_yaml(3);

            // Record file bytes before the call
            let bytes_before = fs::read(&status_file).unwrap();

            // Act: call update with bad_status
            let result = update_status_in_file(&status_file, &artifact_ids[0], &bad_status);

            // Assert: error returned containing "Invalid status"
            prop_assert!(result.is_err(), "Expected error for invalid status '{}', got Ok", bad_status);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Invalid status"),
                "Error message '{}' should contain 'Invalid status'", err_msg
            );

            // Assert: file is byte-for-byte identical to before
            let bytes_after = fs::read(&status_file).unwrap();
            prop_assert_eq!(bytes_before, bytes_after, "File was modified despite invalid status '{}'", bad_status);
        }
    }

    // Feature: status-change-interaction, Property 3: Non-existent entity rejection
    // **Validates: Requirements 1.4, 1.5**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]
        #[test]
        fn nonexistent_artifact_rejected(
            random_id in "[a-zA-Z0-9_-]{1,30}",
        ) {
            // Known artifact IDs in our test file
            let known_ids: Vec<String> = (0..3).map(|i| format!("artifact-{}", i)).collect();

            // Filter out any generated ID that happens to match a known one
            prop_assume!(!known_ids.contains(&random_id));

            let (_tmp_dir, status_file, _artifact_ids) = create_test_status_yaml(3);

            // Capture file content before the call
            let content_before = fs::read_to_string(&status_file).unwrap();

            // Act: call update with non-existent artifact ID
            let result = update_status_in_file(&status_file, &random_id, "approved");

            // Assert: error returned containing "Artifact not found"
            prop_assert!(result.is_err(), "Expected error for non-existent artifact '{}'", random_id);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Artifact not found"),
                "Error message '{}' should contain 'Artifact not found'", err_msg
            );

            // Assert: file is byte-for-byte unchanged
            let content_after = fs::read_to_string(&status_file).unwrap();
            prop_assert_eq!(content_before, content_after, "File should not be modified for non-existent artifact");
        }
    }

    // Feature: status-change-interaction, Property 4: Empty parameter validation
    // **Validates: Requirements 1.7**
    //
    // For any combination where at least one parameter is empty, verify:
    // - error identifying the empty parameter(s)
    // - no file modification

    /// Strategy: generate non-empty strings for the "filled" parameters
    fn non_empty_param() -> impl Strategy<Value = String> {
        "[a-zA-Z0-9_-]{1,20}"
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 4: When project_name is empty, error is returned identifying it.
        #[test]
        fn empty_project_name_rejected(
            artifact_id in non_empty_param(),
            new_status in non_empty_param(),
        ) {
            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                String::new(),
                artifact_id,
                new_status,
            );

            // Must be an error
            prop_assert!(result.is_err(), "Expected error for empty project_name, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );
            prop_assert!(
                err_msg.contains("project_name"),
                "Error should identify 'project_name' as the empty parameter, got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }

        /// Property 4: When artifact_id is empty, error is returned identifying it.
        #[test]
        fn empty_artifact_id_rejected(
            project_name in non_empty_param(),
            new_status in non_empty_param(),
        ) {
            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                project_name,
                String::new(),
                new_status,
            );

            prop_assert!(result.is_err(), "Expected error for empty artifact_id, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );
            prop_assert!(
                err_msg.contains("artifact_id"),
                "Error should identify 'artifact_id' as the empty parameter, got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }

        /// Property 4: When new_status is empty, error is returned identifying it.
        #[test]
        fn empty_new_status_rejected(
            project_name in non_empty_param(),
            artifact_id in non_empty_param(),
        ) {
            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                project_name,
                artifact_id,
                String::new(),
            );

            prop_assert!(result.is_err(), "Expected error for empty new_status, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );
            prop_assert!(
                err_msg.contains("new_status"),
                "Error should identify 'new_status' as the empty parameter, got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }

        /// Property 4: Random combination where at least one param is empty.
        /// Uses a bitmask (1-7) to randomly make at least one parameter empty.
        #[test]
        fn random_empty_combination_rejected(
            base_project in non_empty_param(),
            base_artifact in non_empty_param(),
            base_status in non_empty_param(),
            // Bitmask 1-7: at least one bit set means that param is empty
            empty_mask in 1u8..8u8,
        ) {
            let project_name = if empty_mask & 1 != 0 { String::new() } else { base_project };
            let artifact_id = if empty_mask & 2 != 0 { String::new() } else { base_artifact };
            let new_status = if empty_mask & 4 != 0 { String::new() } else { base_status };

            let (_tmp_dir, status_file, _) = create_test_status_yaml(3);
            let original_content = fs::read(&status_file).unwrap();

            let result = update_artifact_status(
                project_name,
                artifact_id,
                new_status,
            );

            prop_assert!(result.is_err(), "Expected error when at least one param is empty, got: {:?}", result);
            let err_msg = result.unwrap_err();
            prop_assert!(
                err_msg.contains("Missing required parameter"),
                "Error should mention 'Missing required parameter', got: {}",
                err_msg
            );

            // File must be unchanged
            let after_content = fs::read(&status_file).unwrap();
            prop_assert_eq!(original_content, after_content, "File should not be modified");
        }
    }

    // Feature: add-project-button, Property 1: Path normalization produces clean absolute paths
    // **Validates: Requirements 7.2, 7.4**

    /// Strategy: generate a "dirty" path string by taking a real temp directory path
    /// and injecting `.`, `..` segments, trailing separators, and mixed `/` and `\`.
    fn dirty_path_suffix() -> impl Strategy<Value = String> {
        // Generate a sequence of "noise" segments to append/inject
        prop::collection::vec(
            prop_oneof![
                Just(".".to_string()),
                Just("..".to_string()),
                Just("subdir/..".to_string()),
                Just("./".to_string()),
                Just(".\\".to_string()),
                Just("sub/../".to_string()),
                Just("sub\\..\\".to_string()),
            ],
            0..4,
        )
        .prop_map(|segments| segments.join(""))
    }

    fn trailing_separator() -> impl Strategy<Value = String> {
        prop_oneof![
            Just("".to_string()),
            Just("/".to_string()),
            Just("\\".to_string()),
            Just("//".to_string()),
            Just("\\\\".to_string()),
        ]
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(256))]

        /// Property 1: Path normalization produces clean absolute paths.
        /// For any existing directory path with injected `.`, `..`, trailing separators,
        /// and mixed separators, normalize_path produces a result that:
        /// (a) is absolute, (b) contains no `.` or `..` segments, (c) has no trailing separator.
        #[test]
        fn path_normalization_produces_clean_absolute_paths(
            suffix in dirty_path_suffix(),
            trailing in trailing_separator(),
            use_forward_slashes in proptest::bool::ANY,
        ) {
            // Create a real temp directory so canonicalize can resolve it
            let tmp_dir = TempDir::new().unwrap();
            let base_path = tmp_dir.path().to_string_lossy().to_string();

            // Build a dirty path: base + noise segments + trailing separator
            let mut dirty = format!("{}/{}{}", base_path, suffix, trailing);

            // Optionally mix separator styles (replace some \ with / or vice versa)
            if use_forward_slashes {
                dirty = dirty.replace('\\', "/");
            }

            // Act
            let result = normalize_path(&dirty);

            // Assert: result is Ok
            prop_assert!(result.is_ok(), "normalize_path failed for input '{}': {:?}", dirty, result);
            let normalized = result.unwrap();

            // (a) Path is absolute
            prop_assert!(normalized.is_absolute(),
                "Expected absolute path, got: {:?} (input: '{}')", normalized, dirty);

            // (b) No `.` or `..` components
            for component in normalized.components() {
                match component {
                    std::path::Component::CurDir => {
                        prop_assert!(false, "Path contains '.' segment: {:?} (input: '{}')", normalized, dirty);
                    }
                    std::path::Component::ParentDir => {
                        prop_assert!(false, "Path contains '..' segment: {:?} (input: '{}')", normalized, dirty);
                    }
                    _ => {}
                }
            }

            // (c) No trailing path separator
            let path_str = normalized.to_string_lossy().to_string();
            prop_assert!(
                !path_str.ends_with('/') && !path_str.ends_with('\\'),
                "Path has trailing separator: '{}' (input: '{}')", path_str, dirty
            );
        }
    }

    // Feature: add-project-button, Property 3: Duplicate detection is path-format-invariant
    // **Validates: Requirements 3.3**
    //
    // For any directory path already present in projects.json, attempting to add the
    // same directory again — regardless of trailing separators, relative segment
    // injection, or case variation (on Windows) — SHALL produce the same normalized
    // comparison string via `normalize_for_compare`, proving duplicate detection is
    // format-invariant.

    /// Strategy: generate a random directory name component (alphanumeric, 1-12 chars)
    fn dir_name_component() -> impl Strategy<Value = String> {
        "[a-zA-Z][a-zA-Z0-9_-]{0,11}"
    }

    /// Strategy: generate a random Windows-style absolute path with 1-4 components
    fn random_absolute_path() -> impl Strategy<Value = String> {
        prop::collection::vec(dir_name_component(), 1..=4).prop_map(|parts| {
            format!("C:\\{}", parts.join("\\"))
        })
    }

    /// Strategy: pick a random path transformation
    /// 0 = add trailing backslash
    /// 1 = add trailing forward slash
    /// 2 = change to uppercase
    /// 3 = change to lowercase
    /// 4 = replace all backslashes with forward slashes
    /// 5 = add multiple trailing separators (mixed)
    fn compare_transformation() -> impl Strategy<Value = u8> {
        0u8..6u8
    }

    /// Apply a transformation to a path string to create a format variation
    fn apply_compare_transform(base: &str, transform: u8) -> String {
        match transform {
            0 => format!("{}\\", base),
            1 => format!("{}/", base),
            2 => base.to_uppercase(),
            3 => base.to_lowercase(),
            4 => base.replace('\\', "/"),
            5 => format!("{}\\/\\", base),
            _ => base.to_string(),
        }
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 3: All format variations of the same path produce the same
        /// normalized comparison string via `normalize_for_compare`, ensuring
        /// duplicate detection is path-format-invariant.
        #[test]
        fn duplicate_detection_is_path_format_invariant(
            base in random_absolute_path(),
            transform1 in compare_transformation(),
            transform2 in compare_transformation(),
        ) {
            // The canonical normalized form of the base path
            let base_normalized = normalize_for_compare(&base);

            // Apply two (possibly different) transformations
            let variation1 = apply_compare_transform(&base, transform1);
            let variation2 = apply_compare_transform(&base, transform2);

            let norm1 = normalize_for_compare(&variation1);
            let norm2 = normalize_for_compare(&variation2);

            // All variations must produce the same normalized string as the base.
            // On Windows, normalize_for_compare lowercases, strips trailing seps,
            // and normalizes / to \. All our transformations (trailing seps, case,
            // slash direction) are handled by this function.
            prop_assert_eq!(
                &norm1, &base_normalized,
                "Variation '{}' (transform {}) should normalize to '{}', got '{}'",
                variation1, transform1, base_normalized, norm1
            );
            prop_assert_eq!(
                &norm2, &base_normalized,
                "Variation '{}' (transform {}) should normalize to '{}', got '{}'",
                variation2, transform2, base_normalized, norm2
            );

            // Both variations must be equal to each other (transitivity)
            prop_assert_eq!(
                &norm1, &norm2,
                "Two variations of '{}' should produce the same normalized form. \
                 Variation1='{}' -> '{}', Variation2='{}' -> '{}'",
                base, variation1, norm1, variation2, norm2
            );
        }
    }

    // Feature: add-project-button, Property 4: Successful add persists path to projects.json
    // **Validates: Requirements 4.1**
    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 4: For any valid directory path not already in projects.json,
        /// persisting it results in entry count increasing by exactly 1 and the
        /// normalized path being present in the file.
        #[test]
        fn successful_add_persists_path(
            dir_name in "[a-zA-Z][a-zA-Z0-9_-]{0,19}",
        ) {
            // Setup: create a temp directory to hold projects.json and a project subdirectory
            let tmp_dir = TempDir::new().unwrap();
            let pj_path = tmp_dir.path().join("projects.json");

            // Create a subdirectory that will serve as the "project" to add
            let project_dir = tmp_dir.path().join(&dir_name);
            fs::create_dir_all(&project_dir).unwrap();

            // Load current entries (should be empty since projects.json doesn't exist yet)
            let entries_before = load_or_create_projects(&pj_path).unwrap();
            let count_before = entries_before.len();

            // The normalized path string for the new project
            let norm_path = project_dir.to_string_lossy().to_string();

            // Ensure it's not already present (it shouldn't be since we start fresh)
            let already_present = entries_before.iter().any(|e| {
                normalize_for_compare(&e.path) == normalize_for_compare(&norm_path)
            });
            prop_assume!(!already_present);

            // Construct the new config with the entry appended
            let mut config = ProjectsConfig { projects: entries_before };
            config.projects.push(ProjectEntry { path: norm_path.clone() });

            // Persist via atomic write
            atomic_write_projects(&pj_path, &config).unwrap();

            // Read back and verify
            let entries_after = load_or_create_projects(&pj_path).unwrap();

            // Assert: entry count increased by exactly 1
            prop_assert_eq!(
                entries_after.len(),
                count_before + 1,
                "Entry count should increase by exactly 1, was {} now {}",
                count_before,
                entries_after.len()
            );

            // Assert: the normalized path is present in the persisted entries
            let path_present = entries_after.iter().any(|e| {
                normalize_for_compare(&e.path) == normalize_for_compare(&norm_path)
            });
            prop_assert!(
                path_present,
                "Persisted entries should contain the normalized path '{}'",
                norm_path
            );
        }

        /// Property 4 (extended): Adding to a non-empty projects.json still increases
        /// count by exactly 1 and preserves all existing entries.
        #[test]
        fn successful_add_to_existing_projects(
            existing_count in 1usize..5,
            new_dir_name in "[a-zA-Z][a-zA-Z0-9_-]{0,19}",
        ) {
            // Setup: create a temp directory with a pre-populated projects.json
            let tmp_dir = TempDir::new().unwrap();
            let pj_path = tmp_dir.path().join("projects.json");

            // Create existing project entries (real directories)
            let mut existing_entries = Vec::new();
            for i in 0..existing_count {
                let existing_dir = tmp_dir.path().join(format!("existing_project_{}", i));
                fs::create_dir_all(&existing_dir).unwrap();
                existing_entries.push(ProjectEntry {
                    path: existing_dir.to_string_lossy().to_string(),
                });
            }

            // Write initial projects.json with existing entries
            let initial_config = ProjectsConfig { projects: existing_entries.clone() };
            atomic_write_projects(&pj_path, &initial_config).unwrap();

            // Create the new project directory to add
            let new_project_dir = tmp_dir.path().join(&new_dir_name);
            fs::create_dir_all(&new_project_dir).unwrap();
            let new_norm_path = new_project_dir.to_string_lossy().to_string();

            // Load current entries
            let entries_before = load_or_create_projects(&pj_path).unwrap();
            let count_before = entries_before.len();

            // Ensure the new path is not already present
            let already_present = entries_before.iter().any(|e| {
                normalize_for_compare(&e.path) == normalize_for_compare(&new_norm_path)
            });
            prop_assume!(!already_present);

            // Append and persist
            let mut config = ProjectsConfig { projects: entries_before };
            config.projects.push(ProjectEntry { path: new_norm_path.clone() });
            atomic_write_projects(&pj_path, &config).unwrap();

            // Read back and verify
            let entries_after = load_or_create_projects(&pj_path).unwrap();

            // Assert: entry count increased by exactly 1
            prop_assert_eq!(
                entries_after.len(),
                count_before + 1,
                "Entry count should increase by exactly 1, was {} now {}",
                count_before,
                entries_after.len()
            );

            // Assert: the new normalized path is present
            let path_present = entries_after.iter().any(|e| {
                normalize_for_compare(&e.path) == normalize_for_compare(&new_norm_path)
            });
            prop_assert!(
                path_present,
                "Persisted entries should contain the new path '{}'",
                new_norm_path
            );

            // Assert: all previous entries are still present
            for entry in existing_entries.iter() {
                let still_present = entries_after.iter().any(|e| {
                    normalize_for_compare(&e.path) == normalize_for_compare(&entry.path)
                });
                prop_assert!(
                    still_present,
                    "Previously existing entry '{}' should still be present",
                    entry.path
                );
            }
        }
    }

    // =========================================================================
    // Feature: add-project-button, Property 5: Error responses contain valid code and non-empty message
    // **Validates: Requirements 7.3**
    // =========================================================================

    /// The set of valid error codes that add_project can produce.
    const VALID_ERROR_CODES: &[&str] = &[
        "empty_path",
        "path_not_found",
        "duplicate_project",
        "read_failed",
        "write_failed",
    ];

    /// Helper: assert that an AddProjectError has a valid code and non-empty message.
    fn assert_valid_error(err: &AddProjectError) -> Result<(), proptest::test_runner::TestCaseError> {
        prop_assert!(
            VALID_ERROR_CODES.contains(&err.code.as_str()),
            "Error code '{}' is not one of the valid codes: {:?}",
            err.code,
            VALID_ERROR_CODES
        );
        prop_assert!(
            !err.message.is_empty(),
            "Error message must be non-empty, got empty message for code '{}'",
            err.code
        );
        Ok(())
    }

    /// Simulate the add_project validation pipeline without AppHandle.
    /// Returns Err(AddProjectError) for invalid inputs, Ok(()) if the path would pass validation.
    fn validate_add_project_path(
        path: &str,
        projects_path: &Path,
    ) -> Result<(), AddProjectError> {
        // 1. Reject empty/whitespace
        validate_path_not_empty(path)?;

        // 2. Normalize path
        let normalized = normalize_path(path)?;

        // 3. Check existence (must be a directory)
        if !normalized.exists() || !normalized.is_dir() {
            return Err(AddProjectError {
                code: "path_not_found".into(),
                message: "路径不存在".into(),
            });
        }

        // 4. Check duplicate
        let entries = load_or_create_projects(projects_path)?;
        let norm_str = normalized.to_string_lossy().to_string();
        if entries
            .iter()
            .any(|e| normalize_for_compare(&e.path) == normalize_for_compare(&norm_str))
        {
            return Err(AddProjectError {
                code: "duplicate_project".into(),
                message: "项目已存在".into(),
            });
        }

        Ok(())
    }

    /// Strategy: generate whitespace-only strings for empty_path error triggers
    fn whitespace_only_strings_p5() -> impl Strategy<Value = String> {
        proptest::collection::vec(
            prop_oneof![
                Just(' '),
                Just('\t'),
                Just('\n'),
                Just('\r'),
            ],
            0..20,
        )
        .prop_map(|chars| chars.into_iter().collect::<String>())
    }

    /// Strategy: generate random non-existent path strings
    fn nonexistent_path_strings_p5() -> impl Strategy<Value = String> {
        "[a-zA-Z]{1,8}".prop_map(|s| {
            format!("C:\\__nonexistent_test_root_xyz_prop5__\\{}", s)
        })
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 5a: Empty/whitespace paths produce errors with valid code and non-empty message.
        #[test]
        fn prop5_error_from_empty_path_has_valid_structure(
            path in whitespace_only_strings_p5(),
        ) {
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            let result = validate_add_project_path(&path, &projects_path);
            prop_assert!(result.is_err(), "Expected error for whitespace path {:?}, got Ok", path);
            let err = result.unwrap_err();
            assert_valid_error(&err)?;
            prop_assert_eq!(&err.code, "empty_path");
        }

        /// Property 5b: Non-existent paths produce errors with valid code and non-empty message.
        #[test]
        fn prop5_error_from_nonexistent_path_has_valid_structure(
            path in nonexistent_path_strings_p5(),
        ) {
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            let result = validate_add_project_path(&path, &projects_path);
            prop_assert!(result.is_err(), "Expected error for non-existent path '{}', got Ok", path);
            let err = result.unwrap_err();
            assert_valid_error(&err)?;
            prop_assert_eq!(&err.code, "path_not_found");
        }

        /// Property 5c: File paths (not directories) produce errors with valid code and non-empty message.
        #[test]
        fn prop5_error_from_file_path_has_valid_structure(
            filename in "[a-zA-Z0-9_]{1,10}\\.[a-z]{1,4}",
        ) {
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            // Create a file (not a directory)
            let file_path = tmp_dir.path().join(&filename);
            fs::write(&file_path, "test content").unwrap();

            let result = validate_add_project_path(
                file_path.to_str().unwrap(),
                &projects_path,
            );
            prop_assert!(result.is_err(), "Expected error for file path '{}', got Ok", file_path.display());
            let err = result.unwrap_err();
            assert_valid_error(&err)?;
            prop_assert_eq!(&err.code, "path_not_found");
        }

        /// Property 5d: Duplicate paths produce errors with valid code and non-empty message.
        #[test]
        fn prop5_error_from_duplicate_path_has_valid_structure(
            dirname in "[a-zA-Z0-9_]{1,10}",
        ) {
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            // Create a directory
            let dir_path = tmp_dir.path().join(&dirname);
            fs::create_dir_all(&dir_path).unwrap();

            // Write projects.json with this directory already present
            let canonical = std::fs::canonicalize(&dir_path).unwrap();
            let canonical_str = canonical.to_string_lossy().to_string();
            let config = ProjectsConfig {
                projects: vec![ProjectEntry { path: canonical_str.clone() }],
            };
            let json = serde_json::to_string_pretty(&config).unwrap();
            fs::write(&projects_path, &json).unwrap();

            let result = validate_add_project_path(
                dir_path.to_str().unwrap(),
                &projects_path,
            );
            prop_assert!(result.is_err(), "Expected error for duplicate path '{}', got Ok", dir_path.display());
            let err = result.unwrap_err();
            assert_valid_error(&err)?;
            prop_assert_eq!(&err.code, "duplicate_project");
        }

        /// Property 5e: Corrupted projects.json produces errors with valid code and non-empty message.
        #[test]
        fn prop5_error_from_corrupted_json_has_valid_structure(
            dirname in "[a-zA-Z0-9_]{1,10}",
            garbage in "[^{}\\[\\]]{5,30}",
        ) {
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            // Create a valid directory so we pass the existence check
            let dir_path = tmp_dir.path().join(&dirname);
            fs::create_dir_all(&dir_path).unwrap();

            // Write corrupted JSON
            fs::write(&projects_path, &garbage).unwrap();

            let result = validate_add_project_path(
                dir_path.to_str().unwrap(),
                &projects_path,
            );
            prop_assert!(result.is_err(), "Expected error for corrupted JSON, got Ok");
            let err = result.unwrap_err();
            assert_valid_error(&err)?;
            prop_assert_eq!(&err.code, "read_failed");
        }
    }

    // =========================================================================
    // Feature: delete-project-button, Property 5: Deletion never removes disk files
    // **Validates: Requirements 3.8**
    // =========================================================================

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(50))]

        /// Property 5: For any project directory that exists on disk and is registered
        /// in projects.json, calling delete_project_impl with that path SHALL not
        /// delete, modify, or rename the directory or any of its contents on disk.
        #[test]
        fn deletion_never_removes_disk_files(
            dir_count in 1usize..=5,
            delete_idx_raw in 0usize..5,
        ) {
            // Clamp delete index to valid range
            let delete_idx = delete_idx_raw % dir_count;

            // Setup: create a temp root and multiple project directories inside it
            let tmp_root = TempDir::new().unwrap();
            let projects_path = tmp_root.path().join("projects.json");

            let mut project_dirs: Vec<PathBuf> = Vec::new();
            let mut entries: Vec<ProjectEntry> = Vec::new();

            for i in 0..dir_count {
                let dir = tmp_root.path().join(format!("project_{}", i));
                fs::create_dir_all(&dir).unwrap();
                // Also create a file inside each directory to verify contents are preserved
                fs::write(dir.join("README.md"), format!("Project {}", i)).unwrap();
                let path_str = dir.to_string_lossy().to_string();
                entries.push(ProjectEntry { path: path_str });
                project_dirs.push(dir);
            }

            // Write projects.json with all entries
            let config = ProjectsConfig { projects: entries };
            atomic_write_projects(&projects_path, &config).unwrap();

            // Act: delete the project at delete_idx
            let path_to_delete = project_dirs[delete_idx].to_string_lossy().to_string();
            let result = delete_project_impl(&projects_path, &path_to_delete);

            // Assert: deletion succeeds
            prop_assert!(
                result.is_ok(),
                "Expected Ok for deleting '{}', got Err({:?})",
                path_to_delete, result.err()
            );

            // Assert: the deleted project's directory STILL EXISTS on disk
            prop_assert!(
                project_dirs[delete_idx].exists(),
                "Directory '{}' should still exist on disk after deletion from projects.json",
                project_dirs[delete_idx].display()
            );
            prop_assert!(
                project_dirs[delete_idx].is_dir(),
                "Path '{}' should still be a directory after deletion",
                project_dirs[delete_idx].display()
            );
            // Verify file inside the deleted directory is also preserved
            let readme_path = project_dirs[delete_idx].join("README.md");
            prop_assert!(
                readme_path.exists(),
                "README.md inside '{}' should still exist after deletion",
                project_dirs[delete_idx].display()
            );

            // Assert: ALL other directories also still exist on disk
            for (i, dir) in project_dirs.iter().enumerate() {
                prop_assert!(
                    dir.exists(),
                    "Directory '{}' (index {}) should still exist on disk after deleting index {}",
                    dir.display(), i, delete_idx
                );
                prop_assert!(
                    dir.is_dir(),
                    "Path '{}' (index {}) should still be a directory",
                    dir.display(), i
                );
                let inner_readme = dir.join("README.md");
                prop_assert!(
                    inner_readme.exists(),
                    "README.md inside '{}' (index {}) should still exist",
                    dir.display(), i
                );
            }
        }
    }

    // =========================================================================
    // Feature: delete-project-button, Property 1: Whitespace-only paths are always rejected
    // **Validates: Requirements 3.2**
    // =========================================================================

    /// Strategy: generate random whitespace strings including empty, spaces, tabs, \r\n, mixed
    fn whitespace_strings_for_delete() -> impl Strategy<Value = String> {
        proptest::collection::vec(
            prop_oneof![
                Just(' '),
                Just('\t'),
                Just('\n'),
                Just('\r'),
            ],
            0..30,
        )
        .prop_map(|chars| chars.into_iter().collect::<String>())
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 1: For any string composed entirely of whitespace characters
        /// (spaces, tabs, newlines, or the empty string), calling delete_project_impl
        /// returns an error with code "empty_path" and the projects.json file content
        /// is unchanged.
        #[test]
        fn delete_whitespace_only_paths_rejected(
            ws in whitespace_strings_for_delete(),
        ) {
            // Setup: create a temp directory with a valid projects.json containing some entries
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            let initial_config = ProjectsConfig {
                projects: vec![
                    ProjectEntry { path: "C:\\Projects\\Alpha".to_string() },
                    ProjectEntry { path: "C:\\Projects\\Beta".to_string() },
                ],
            };
            let json = serde_json::to_string_pretty(&initial_config).unwrap();
            fs::write(&projects_path, &json).unwrap();

            // Capture file content before the call
            let content_before = fs::read(&projects_path).unwrap();

            // Act: call delete_project_impl with whitespace-only path
            let result = delete_project_impl(&projects_path, &ws);

            // Assert: must be an error with code "empty_path"
            prop_assert!(
                result.is_err(),
                "Expected error for whitespace-only path {:?}, got Ok({:?})",
                ws, result.ok()
            );
            let err = result.unwrap_err();
            prop_assert_eq!(
                &err.code, "empty_path",
                "Expected error code 'empty_path' for input {:?}, got '{}'",
                ws, err.code
            );
            prop_assert!(
                !err.message.is_empty(),
                "Error message should not be empty for input {:?}",
                ws
            );

            // Assert: projects.json file content is byte-for-byte unchanged
            let content_after = fs::read(&projects_path).unwrap();
            prop_assert_eq!(
                content_before, content_after,
                "projects.json should not be modified for whitespace-only path {:?}",
                ws
            );
        }
    }

    // =========================================================================
    // Feature: delete-project-button, Property 3: Non-matching paths return project_not_found
    // **Validates: Requirements 3.4**
    // =========================================================================

    /// Strategy: generate a list of 1-10 project path strings (Windows-style absolute paths)
    fn project_path_list_for_p3() -> impl Strategy<Value = Vec<String>> {
        prop::collection::vec(
            prop::collection::vec(
                "[a-zA-Z][a-zA-Z0-9_-]{0,11}".prop_map(|s| s),
                1..=3,
            )
            .prop_map(|parts| format!("C:\\Projects\\{}", parts.join("\\"))),
            1..=10,
        )
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 3: For any path string that, after normalization, does not match
        /// any entry in projects.json, calling delete_project_impl returns an error
        /// with code "project_not_found" and projects.json remains unchanged.
        #[test]
        fn delete_nonmatching_path_returns_project_not_found(
            paths in project_path_list_for_p3(),
            suffix in "[a-zA-Z0-9]{4,12}",
        ) {
            // Setup: create a temp directory with a projects.json containing the generated entries
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            let entries: Vec<ProjectEntry> = paths.iter()
                .map(|p| ProjectEntry { path: p.clone() })
                .collect();
            let config = ProjectsConfig { projects: entries };
            let json = serde_json::to_string_pretty(&config).unwrap();
            fs::write(&projects_path, &json).unwrap();

            // Generate a path guaranteed to NOT match any entry after normalization:
            // Use a unique prefix + suffix that cannot collide with generated paths
            let non_matching_path = format!("C:\\NonExistent\\__unique_{}__", suffix);

            // Double-check: ensure the generated path does not match any entry
            let norm_non_matching = normalize_for_compare(&non_matching_path);
            let matches_any = paths.iter().any(|p| normalize_for_compare(p) == norm_non_matching);
            prop_assume!(!matches_any);

            // Capture file content before the call
            let content_before = fs::read(&projects_path).unwrap();

            // Act: call delete_project_impl with the non-matching path
            let result = delete_project_impl(&projects_path, &non_matching_path);

            // Assert: must be an error with code "project_not_found"
            prop_assert!(
                result.is_err(),
                "Expected error for non-matching path {:?}, got Ok({:?})",
                non_matching_path, result.ok()
            );
            let err = result.unwrap_err();
            prop_assert_eq!(
                &err.code, "project_not_found",
                "Expected error code 'project_not_found' for input {:?}, got '{}'",
                non_matching_path, err.code
            );
            prop_assert!(
                !err.message.is_empty(),
                "Error message should not be empty for input {:?}",
                non_matching_path
            );

            // Assert: projects.json file content is byte-for-byte unchanged
            let content_after = fs::read(&projects_path).unwrap();
            prop_assert_eq!(
                content_before, content_after,
                "projects.json should not be modified for non-matching path {:?}",
                non_matching_path
            );
        }
    }

    // =========================================================================
    // Feature: delete-project-button, Property 2: Path matching is format-invariant
    // **Validates: Requirements 3.3**
    // =========================================================================

    /// Strategy: generate a random Windows-style absolute path for delete P2 tests
    fn random_project_path_for_delete_p2() -> impl Strategy<Value = String> {
        prop::collection::vec("[a-zA-Z][a-zA-Z0-9_-]{0,11}", 1..=4).prop_map(|parts| {
            format!("C:\\Users\\{}", parts.join("\\"))
        })
    }

    /// Strategy: pick a random path format transformation for delete P2 tests
    /// 0 = add trailing backslash
    /// 1 = add trailing forward slash
    /// 2 = change to uppercase (Windows case-insensitive)
    /// 3 = change to lowercase (Windows case-insensitive)
    /// 4 = replace all backslashes with forward slashes
    /// 5 = add multiple trailing separators (mixed)
    /// 6 = mixed case (alternate upper/lower)
    fn delete_p2_transformation() -> impl Strategy<Value = u8> {
        0u8..7u8
    }

    /// Apply a format transformation to a path string for P2 tests
    fn apply_delete_p2_transform(base: &str, transform: u8) -> String {
        match transform {
            0 => format!("{}\\", base),
            1 => format!("{}/", base),
            2 => base.to_uppercase(),
            3 => base.to_lowercase(),
            4 => base.replace('\\', "/"),
            5 => format!("{}\\/\\", base),
            6 => {
                // Mixed case: alternate upper/lower on each char
                base.chars()
                    .enumerate()
                    .map(|(i, c)| {
                        if i % 2 == 0 {
                            c.to_uppercase().next().unwrap_or(c)
                        } else {
                            c.to_lowercase().next().unwrap_or(c)
                        }
                    })
                    .collect()
            }
            _ => base.to_string(),
        }
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 2: For any project path stored in projects.json, providing that
        /// same path with different formatting (trailing separators added/removed,
        /// forward/back slash variations, case variations on Windows) to
        /// delete_project_impl SHALL successfully locate and remove the entry.
        #[test]
        fn delete_path_matching_is_format_invariant(
            base_path in random_project_path_for_delete_p2(),
            transform in delete_p2_transformation(),
        ) {
            // Setup: create a temp directory with a projects.json containing the base path
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            // Store the base path as-is in projects.json along with some other entries
            let initial_config = ProjectsConfig {
                projects: vec![
                    ProjectEntry { path: "C:\\Other\\ProjectA".to_string() },
                    ProjectEntry { path: base_path.clone() },
                    ProjectEntry { path: "C:\\Other\\ProjectB".to_string() },
                ],
            };
            let json = serde_json::to_string_pretty(&initial_config).unwrap();
            fs::write(&projects_path, &json).unwrap();

            // Apply a format transformation to create a variant of the path
            let variant_path = apply_delete_p2_transform(&base_path, transform);

            // Act: call delete_project_impl with the variant path
            let result = delete_project_impl(&projects_path, &variant_path);

            // Assert: the entry is found and removed successfully
            prop_assert!(
                result.is_ok(),
                "Expected Ok for variant '{}' (transform {}) of base '{}', got Err({:?})",
                variant_path, transform, base_path, result.err()
            );

            let response = result.unwrap();
            // The returned path should be the original stored path
            prop_assert_eq!(
                &response.path, &base_path,
                "Returned path should be the original stored path '{}', got '{}'",
                base_path, response.path
            );

            // Assert: the projects.json now has exactly 2 entries (the other two)
            let entries_after = load_or_create_projects(&projects_path).unwrap();
            prop_assert_eq!(
                entries_after.len(), 2,
                "Expected 2 remaining entries after deletion, got {}",
                entries_after.len()
            );

            // Assert: the deleted path is no longer present
            let still_present = entries_after.iter().any(|e| {
                normalize_for_compare(&e.path) == normalize_for_compare(&base_path)
            });
            prop_assert!(
                !still_present,
                "Deleted path '{}' should no longer be present in projects.json",
                base_path
            );

            // Assert: the other entries are still present and in order
            let has_a = entries_after.iter().any(|e| e.path == "C:\\Other\\ProjectA");
            let has_b = entries_after.iter().any(|e| e.path == "C:\\Other\\ProjectB");
            prop_assert!(has_a, "ProjectA should still be present");
            prop_assert!(has_b, "ProjectB should still be present");
        }
    }

    // =========================================================================
    // Feature: delete-project-button, Property 4: Deletion removes exactly one entry and preserves order
    // **Validates: Requirements 3.5, 6.3**
    // =========================================================================

    /// Strategy: generate a Vec of 1–20 unique project path strings
    fn unique_project_paths(count: usize) -> Vec<String> {
        (0..count)
            .map(|i| format!("C:\\Projects\\Project_{}", i))
            .collect()
    }

    proptest! {
        #![proptest_config(ProptestConfig::with_cases(100))]

        /// Property 4: For any projects.json containing N >= 1 entries, successfully
        /// deleting one entry produces a projects.json with exactly N-1 entries,
        /// where all non-deleted entries appear in their original relative order
        /// with identical path values.
        #[test]
        fn deletion_removes_exactly_one_and_preserves_order(
            count in 1usize..=20,
            delete_index_raw in 0usize..20,
        ) {
            // Constrain delete_index to valid range for the generated count
            let delete_index = delete_index_raw % count;

            // Setup: create a temp directory with a projects.json containing `count` entries
            let tmp_dir = TempDir::new().unwrap();
            let projects_path = tmp_dir.path().join("projects.json");

            let paths = unique_project_paths(count);
            let entries: Vec<ProjectEntry> = paths.iter()
                .map(|p| ProjectEntry { path: p.clone() })
                .collect();

            let initial_config = ProjectsConfig { projects: entries.clone() };
            let json = serde_json::to_string_pretty(&initial_config).unwrap();
            fs::write(&projects_path, &json).unwrap();

            // The path to delete
            let path_to_delete = &paths[delete_index];

            // Act: call delete_project_impl
            let result = delete_project_impl(&projects_path, path_to_delete);

            // Assert: result is Ok with the deleted path
            prop_assert!(
                result.is_ok(),
                "Expected Ok for deleting path '{}' at index {}, got Err({:?})",
                path_to_delete, delete_index, result.err()
            );
            let response = result.unwrap();
            prop_assert_eq!(
                &response.path, path_to_delete,
                "Response path should be '{}', got '{}'",
                path_to_delete, response.path
            );

            // Read back the projects.json
            let entries_after = load_or_create_projects(&projects_path).unwrap();

            // Assert: exactly N-1 entries
            prop_assert_eq!(
                entries_after.len(), count - 1,
                "Expected {} entries after deletion, got {}",
                count - 1, entries_after.len()
            );

            // Build expected entries: original list without the deleted index
            let expected: Vec<&ProjectEntry> = entries.iter()
                .enumerate()
                .filter(|(i, _)| *i != delete_index)
                .map(|(_, e)| e)
                .collect();

            // Assert: all non-deleted entries in original relative order with identical path values
            for (i, expected_entry) in expected.iter().enumerate() {
                prop_assert_eq!(
                    &entries_after[i].path, &expected_entry.path,
                    "Entry at position {} should be '{}', got '{}'. \
                     Original list had {} entries, deleted index {}.",
                    i, expected_entry.path, entries_after[i].path, count, delete_index
                );
            }
        }
    }
}
