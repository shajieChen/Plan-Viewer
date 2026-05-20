use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::models::{
    Artifact, ChangeEvent, DashboardData, MarkdownPreview, ProjectData, ProjectEntry,
    ProjectsConfig,
};

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

/// Extract topic name from a Plan artifact ID for group naming.
fn extract_topic_from_plan_id(plan_id: &str) -> String {
    let remainder = if plan_id.starts_with("Plan.") {
        &plan_id[5..]
    } else {
        plan_id
    };

    // Check for PhaseN pattern
    let lower = remainder.to_lowercase();
    if lower.starts_with("phase") {
        if let Some(digit_start) = lower.find(|c: char| c.is_ascii_digit()) {
            let digits: String = lower[digit_start..]
                .chars()
                .take_while(|c| c.is_ascii_digit())
                .collect();
            if !digits.is_empty() {
                return format!("Phase{}", digits);
            }
        }
    }

    // Check for codegen
    if lower.contains("codegen") {
        return "CodeGen".to_string();
    }

    // Return remainder as-is
    if remainder.is_empty() {
        "Other".to_string()
    } else {
        remainder.to_string()
    }
}

/// Resolve depends_on entries to string IDs.
fn resolve_dep_ids(deps: &[serde_yaml::Value]) -> Vec<String> {
    deps.iter()
        .filter_map(|d| match d {
            serde_yaml::Value::String(s) => Some(s.clone()),
            serde_yaml::Value::Mapping(m) => m
                .get(&serde_yaml::Value::String("id".to_string()))
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            _ => None,
        })
        .collect()
}

/// BFS to find the nearest Plan ancestor via depends_on chain (max depth 5).
fn find_root_plan_id(
    artifact_id: &str,
    artifact_type_map: &HashMap<String, String>,
    deps_map: &HashMap<String, Vec<String>>,
) -> Option<String> {
    use std::collections::VecDeque;

    let mut queue: VecDeque<(String, usize)> = VecDeque::new();
    let mut visited: std::collections::HashSet<String> =
        std::collections::HashSet::new();
    visited.insert(artifact_id.to_string());

    if let Some(deps) = deps_map.get(artifact_id) {
        for dep_id in deps {
            if !dep_id.is_empty() && visited.insert(dep_id.clone()) {
                queue.push_back((dep_id.clone(), 1));
            }
        }
    }

    while let Some((current_id, depth)) = queue.pop_front() {
        if depth > 5 {
            continue;
        }
        if let Some(t) = artifact_type_map.get(&current_id) {
            if t == "plan" {
                return Some(current_id);
            }
        }
        if let Some(deps) = deps_map.get(&current_id) {
            for dep_id in deps {
                if !dep_id.is_empty() && visited.insert(dep_id.clone()) {
                    queue.push_back((dep_id.clone(), depth + 1));
                }
            }
        }
    }
    None
}

/// Post-process artifacts: infer groups from dependency chains for artifacts with group="Other".
fn infer_groups_from_dependencies(
    artifacts: &mut Vec<Artifact>,
    raw_artifacts: &[serde_yaml::Value],
) {
    // Build lookup maps
    let mut artifact_type_map: HashMap<String, String> = HashMap::new();
    let mut deps_map: HashMap<String, Vec<String>> = HashMap::new();

    for raw in raw_artifacts {
        let id = raw.get("id").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let atype = raw.get("type").and_then(|v| v.as_str()).unwrap_or("").to_string();
        let deps = raw
            .get("depends_on")
            .and_then(|v| v.as_sequence())
            .cloned()
            .unwrap_or_default();
        artifact_type_map.insert(id.clone(), atype);
        deps_map.insert(id, resolve_dep_ids(&deps));
    }

    // Build reverse dependency map: plan_id -> set of artifact ids that depend on it
    let mut plan_has_dependents: std::collections::HashSet<String> =
        std::collections::HashSet::new();
    for (aid, dep_ids) in &deps_map {
        for dep_id in dep_ids {
            if artifact_type_map.get(dep_id).map(|t| t.as_str()) == Some("plan") {
                plan_has_dependents.insert(dep_id.clone());
            }
        }
        let _ = aid; // suppress unused warning
    }

    // Pass 1: For LP/TP/research with group="Other", find root Plan and use its topic
    let mut inferred_groups: HashMap<String, String> = HashMap::new();
    for artifact in artifacts.iter() {
        if artifact.group != "Other" {
            continue;
        }
        if !matches!(
            artifact.artifact_type.as_str(),
            "landing_prompt" | "test_prompt" | "research"
        ) {
            continue;
        }
        if let Some(plan_id) = find_root_plan_id(&artifact.id, &artifact_type_map, &deps_map) {
            let topic = extract_topic_from_plan_id(&plan_id);
            if topic != "Other" {
                inferred_groups.insert(artifact.id.clone(), topic);
            }
        }
    }

    // Apply inferred groups
    for artifact in artifacts.iter_mut() {
        if let Some(group) = inferred_groups.get(&artifact.id) {
            artifact.group = group.clone();
        }
    }

    // Collect which topics are actually used by LP/TP
    let used_topics: std::collections::HashSet<String> = artifacts
        .iter()
        .filter(|a| a.group != "Other" && matches!(a.artifact_type.as_str(), "landing_prompt" | "test_prompt" | "research"))
        .map(|a| a.group.clone())
        .collect();

    // Pass 2: For Plans with group="Other" that have dependents using a matching topic, assign that topic
    for artifact in artifacts.iter_mut() {
        if artifact.group != "Other" || artifact.artifact_type != "plan" {
            continue;
        }
        if !plan_has_dependents.contains(&artifact.id) {
            continue;
        }
        let topic = extract_topic_from_plan_id(&artifact.id);
        if topic != "Other" && used_topics.contains(&topic) {
            artifact.group = topic;
        }
    }
}

/// Load projects from projects.json at the given path.
pub fn load_projects(projects_json_path: &Path) -> Result<Vec<ProjectEntry>, String> {
    if !projects_json_path.exists() {
        return Ok(vec![]);
    }
    let content = fs::read_to_string(projects_json_path)
        .map_err(|e| format!("Failed to read projects.json: {}", e))?;
    let config: ProjectsConfig =
        serde_json::from_str(&content).map_err(|e| format!("Failed to parse projects.json: {}", e))?;
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

    let mut title = fallback_title;
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
        // Find the nearest char boundary at or before 200 bytes
        let mut end = 200;
        while !excerpt.is_char_boundary(end) {
            end -= 1;
        }
        excerpt.truncate(end);
    }

    MarkdownPreview { title, excerpt }
}

/// Read a single project's status.yaml and build ProjectData.
pub fn read_project(project_path: &Path) -> Result<ProjectData, String> {
    let status_file = project_path.join("status").join("status.yaml");
    if !status_file.exists() {
        return Err(format!(
            "status.yaml not found: {}",
            status_file.display()
        ));
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
        let id = raw
            .get("id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let artifact_type = raw
            .get("type")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let status = raw
            .get("status")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let path_str = raw
            .get("path")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let group = raw
            .get("group")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
            .unwrap_or_else(|| derive_group(&id));

        let depends_on = raw
            .get("depends_on")
            .and_then(|v| v.as_sequence())
            .cloned()
            .unwrap_or_default();

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

    // --- Post-process: dependency-chain group inference ---
    // For artifacts with group="Other", infer group from Plan ancestors via depends_on
    infer_groups_from_dependencies(&mut artifacts, &raw_artifacts);

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
            event_type: raw
                .get("event_type")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            summary: raw
                .get("summary")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
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
        let project_path = Path::new(&entry.path);
        let (name, data) = match read_project(project_path) {
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
                (name, data)
            }
            Err(_e) => {
                // Project lacks status.yaml or is unreadable — still show it in the list
                // with an empty placeholder so the user can see it and delete if needed.
                let name = project_path
                    .file_name()
                    .unwrap_or_default()
                    .to_str()
                    .unwrap_or("unknown")
                    .to_string();
                let placeholder = ProjectData {
                    meta: serde_yaml::Value::Null,
                    artifacts: vec![],
                    change_events: vec![],
                    markdown_previews: HashMap::new(),
                };
                (name, placeholder)
            }
        };
        projects.insert(name, data);
    }

    Ok(DashboardData { projects })
}
