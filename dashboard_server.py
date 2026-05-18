"""Dashboard One-Click Server.

Lightweight HTTP server based on Python standard library.
Serves static files from views/ and provides REST API endpoints
for project management.
"""

import json
import socket
import sys
import webbrowser
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yaml

from project_store import load_projects, save_projects
from render_dashboard import DashboardGenerator

HOST = "0.0.0.0"
PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
VIEWS_DIR = BASE_DIR / "views"


def regenerate_dashboard() -> Path | None:
    """Regenerate the dashboard HTML using all projects in projects.json.

    Returns:
        The output path on success, or None if no projects are configured.

    Raises:
        SystemExit: If DashboardGenerator.generate() calls sys.exit(1)
                    when all projects fail to load.
    """
    projects = load_projects()
    if not projects:
        return None

    project_paths = [Path(p["path"]) for p in projects]
    output_path = VIEWS_DIR / "dashboard.html"
    template_path = BASE_DIR / "dashboard_template.html"

    generator = DashboardGenerator(project_paths, output_path, template_path)
    generator.generate()
    return output_path


def _initialize_project_structure(project_path: Path) -> None:
    """Initialize a project directory with the project-state-tracker structure.

    Creates missing directories and files according to the standard workflow.
    Does not overwrite existing files.
    """
    project_name = project_path.name
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Directory structure to create
    dirs = [
        "research",
        "decisions",
        "plan",
        "prompts/landing",
        "prompts/test",
        "status",
        "tools",
        "views",
    ]

    for d in dirs:
        (project_path / d).mkdir(parents=True, exist_ok=True)

    # Create status/status.yaml if missing
    status_file = project_path / "status" / "status.yaml"
    if not status_file.exists():
        status_content = f"""## Project State — Single Source of Truth
## Managed by project-state-tracker skill. Do not hand-edit unless you know the schema.

meta:
  project_name: "{project_name}"
  created: "{now}"
  last_updated: "{now}"
  total_artifacts: 0
  total_research: 0
  total_blockers: 0
  hotspots: []

artifacts: []

research_findings: []

decisions: []

assumptions: []

evidence: []

blockers: []

gates: []

preconditions: []

handoff_contexts: []

change_events: []

snapshots:
  enabled: true
  file_hashes: {{}}
"""
        status_file.write_text(status_content, encoding="utf-8")

    # Create status/schema.yaml if missing
    schema_file = project_path / "status" / "schema.yaml"
    if not schema_file.exists():
        schema_content = """## Schema definition for status.yaml
## Used by validate_status.py to check structural correctness.

required_top_level_keys:
  - meta
  - artifacts
  - research_findings
  - decisions
  - assumptions
  - evidence
  - blockers
  - gates
  - preconditions
  - handoff_contexts
  - change_events
  - snapshots

artifact_statuses:
  - draft
  - reviewed
  - approved
  - ready
  - blocked
  - needs_update
  - invalidated
  - deprecated
  - archived

artifact_types:
  - plan
  - landing_prompt
  - test_prompt

meta_required_fields:
  - project_name
  - created
  - last_updated
  - total_artifacts
  - total_research
  - total_blockers
  - hotspots

artifact_required_fields:
  - id
  - type
  - path
  - status
  - depends_on

research_finding_required_fields:
  - id
  - path
  - title
  - status

blocker_required_fields:
  - id
  - title
  - severity
  - blocks
  - status

handoff_context_required_fields:
  - id
  - producer
  - version
  - status
  - consumed_by
  - consumed_status
"""
        schema_file.write_text(schema_content, encoding="utf-8")

    # Create .gitkeep files in empty directories
    for d in dirs:
        gitkeep = project_path / d / ".gitkeep"
        if not gitkeep.exists() and not any((project_path / d).iterdir()):
            gitkeep.write_text("", encoding="utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler with routing for static files and API endpoints."""

    def end_headers(self):
        """Override to inject CORS headers on every response."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Route: /dashboard.html -> serve views/dashboard.html
        # If it doesn't exist yet (no projects), serve the template with empty data
        if path == "/dashboard.html":
            dashboard_file = VIEWS_DIR / "dashboard.html"
            if dashboard_file.is_file():
                self._serve_static_file(dashboard_file)
            else:
                self._serve_empty_dashboard()
            return

        # Route: /views/... -> serve static files from views/
        if path.startswith("/views/"):
            rel_path = path[len("/views/"):]
            file_path = VIEWS_DIR / rel_path
            self._serve_static_file(file_path)
            return

        # API: GET /api/projects
        if path == "/api/projects":
            self._handle_get_projects()
            return

        # API: GET /api/file?path=<relative_path> - serve a source file from a project
        if path == "/api/file":
            self._handle_get_file(parsed.query)
            return

        # Default: 404
        self._send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/projects":
            self._handle_post_project()
            return

        if path == "/api/projects/initialize":
            self._handle_initialize_project()
            return

        if path == "/api/regenerate":
            self._handle_regenerate()
            return

        self._send_error(404, "Not Found")

    def _handle_post_project(self):
        """Handle POST /api/projects - add a new project."""
        # Parse JSON body
        try:
            body = json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError):
            self._send_error(400, "Invalid JSON body")
            return

        # Validate "path" field exists
        project_path = body.get("path")
        if not project_path:
            self._send_error(400, "Missing 'path' field")
            return

        # Validate path exists on disk
        resolved_path = Path(project_path).resolve()
        if not resolved_path.exists():
            self._send_error(400, "路径不存在")
            return

        # Validate status/status.yaml exists
        status_file = resolved_path / "status" / "status.yaml"
        if not status_file.exists():
            # Return 422 to indicate the directory needs initialization
            self._send_json(422, {
                "error": "not_initialized",
                "path": str(resolved_path),
                "message": "该目录不是合规项目，是否需要初始化？",
            })
            return

        # Validate project not already added
        projects = load_projects()
        resolved_str = str(resolved_path)
        for entry in projects:
            if str(Path(entry["path"]).resolve()) == resolved_str:
                self._send_error(409, "项目已存在")
                return

        # Add project and save
        projects.append({"path": resolved_str})
        save_projects(projects)

        # Trigger dashboard regeneration
        self._trigger_regenerate()

        # Return success
        self._send_json(200, {"message": "Project added", "path": resolved_str})

    def _trigger_regenerate(self):
        """Trigger dashboard regeneration (non-fatal on failure)."""
        try:
            regenerate_dashboard()
        except SystemExit:
            pass  # Regeneration failure is non-fatal for add/delete operations
        except Exception:
            pass

    def _handle_initialize_project(self):
        """Handle POST /api/projects/initialize - initialize a project directory."""
        try:
            body = json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError):
            self._send_error(400, "Invalid JSON body")
            return

        project_path = body.get("path")
        if not project_path:
            self._send_error(400, "Missing 'path' field")
            return

        resolved_path = Path(project_path).resolve()
        if not resolved_path.exists():
            self._send_error(400, "路径不存在")
            return

        # Initialize the project structure
        try:
            _initialize_project_structure(resolved_path)
        except Exception as e:
            self._send_error(500, f"初始化失败: {e}")
            return

        # Add to projects.json
        projects = load_projects()
        resolved_str = str(resolved_path)
        # Check not already added
        already_exists = any(
            str(Path(p["path"]).resolve()) == resolved_str for p in projects
        )
        if not already_exists:
            projects.append({"path": resolved_str})
            save_projects(projects)

        # Trigger regeneration
        self._trigger_regenerate()

        self._send_json(200, {"message": "Project initialized and added", "path": resolved_str})

    def _handle_regenerate(self):
        """Handle POST /api/regenerate - manually trigger dashboard regeneration."""
        projects = load_projects()
        if not projects:
            self._send_json(200, {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "project_count": 0,
            })
            return

        try:
            regenerate_dashboard()
        except SystemExit:
            self._send_error(500, "All projects failed to generate")
            return

        self._send_json(200, {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_count": len(projects),
        })

    def _handle_patch_artifact_status(self):
        """Handle PATCH /api/artifact/status - change an artifact's status."""
        VALID_STATUSES = [
            "draft", "reviewed", "approved", "ready", "blocked",
            "needs_update", "invalidated", "deprecated", "archived",
        ]

        # Parse body
        try:
            body = json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError):
            self._send_error(400, "Invalid JSON body")
            return

        # Validate required fields
        project_name = body.get("project")
        artifact_id = body.get("artifact_id")
        new_status = body.get("new_status")

        if not project_name:
            self._send_error(400, "Missing required field: project")
            return
        if not artifact_id:
            self._send_error(400, "Missing required field: artifact_id")
            return
        if not new_status:
            self._send_error(400, "Missing required field: new_status")
            return

        # Validate status value
        if new_status not in VALID_STATUSES:
            self._send_error(400, f"Invalid status: {new_status}")
            return

        # Find the project by name
        projects = load_projects()
        target_project_path = None
        for entry in projects:
            project_path = Path(entry["path"])
            status_file = project_path / "status" / "status.yaml"
            if not status_file.is_file():
                continue

            # Match by directory name first (fast path)
            if project_path.name == project_name:
                target_project_path = project_path
                break

            # Match by meta.project_name in status.yaml
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if isinstance(data, dict):
                    meta = data.get("meta", {})
                    if isinstance(meta, dict) and meta.get("project_name") == project_name:
                        target_project_path = project_path
                        break
            except (OSError, yaml.YAMLError):
                continue

        if target_project_path is None:
            self._send_error(404, "项目未找到")
            return

        # Read and modify status.yaml
        status_file = target_project_path / "status" / "status.yaml"
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (OSError, yaml.YAMLError) as e:
            self._send_error(500, f"读取失败: {e}")
            return

        # Find the artifact
        artifacts = data.get("artifacts", [])
        target_artifact = None
        for artifact in artifacts:
            if artifact.get("id") == artifact_id:
                target_artifact = artifact
                break

        if target_artifact is None:
            self._send_error(404, "Artifact 未找到")
            return

        # Update status
        target_artifact["status"] = new_status

        # Update meta.last_updated
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if "meta" in data and isinstance(data["meta"], dict):
            data["meta"]["last_updated"] = now

        # Write back
        try:
            with open(status_file, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except OSError as e:
            self._send_error(500, f"写入失败: {e}")
            return

        # Trigger regeneration
        self._trigger_regenerate()

        self._send_json(200, {
            "message": "Status updated",
            "artifact_id": artifact_id,
            "new_status": new_status,
        })

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/artifact/status":
            self._handle_patch_artifact_status()
            return

        self._send_error(404, "Not Found")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/projects":
            self._handle_delete_projects()
            return

        self._send_error(404, "Not Found")

    # --- API handlers ---

    def _handle_get_projects(self):
        """Handle GET /api/projects: return project list with validity info."""
        projects = load_projects()
        result = []
        for entry in projects:
            project_path = Path(entry["path"])
            status_file = project_path / "status" / "status.yaml"
            valid = status_file.is_file()
            name = project_path.name  # default: directory name

            if valid:
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        meta = data.get("meta", {})
                        if isinstance(meta, dict) and "project_name" in meta:
                            name = meta["project_name"]
                except (OSError, yaml.YAMLError, TypeError):
                    pass  # keep directory name as fallback

            result.append({
                "path": str(project_path),
                "name": name,
                "valid": valid,
            })

        self._send_json(200, {"projects": result})

    def _handle_get_file(self, query_string: str):
        """Handle GET /api/file?path=<relative_path> - serve a source file from a project."""
        params = parse_qs(query_string)
        rel_path = params.get("path", [None])[0]

        if not rel_path:
            self._send_error(400, "Missing 'path' parameter")
            return

        # Search through all configured projects for this file
        projects = load_projects()
        for entry in projects:
            project_dir = Path(entry["path"])
            file_path = (project_dir / rel_path).resolve()

            # Security: ensure the resolved path is within the project directory
            try:
                if not str(file_path).startswith(str(project_dir.resolve())):
                    continue
            except (OSError, ValueError):
                continue

            if file_path.is_file():
                # Serve directly (bypass BASE_DIR check since we validated against project_dir)
                content_type = self._guess_content_type(file_path)
                try:
                    content = file_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except OSError:
                    self._send_error(500, "Internal Server Error")
                return

        self._send_error(404, "File not found")

    # --- API handler methods ---

    def _handle_delete_projects(self):
        """Handle DELETE /api/projects endpoint.

        Two modes:
        - {"path": "..."} → remove the specified project
        - {"clear_all": true} → remove all projects
        """
        try:
            body = json.loads(self._read_body())
        except (json.JSONDecodeError, ValueError):
            self._send_error(400, "Invalid JSON body")
            return

        projects = load_projects()

        if body.get("clear_all") is True:
            # Clear all projects
            save_projects([])
            # Remove dashboard.html if it exists
            dashboard_path = VIEWS_DIR / "dashboard.html"
            if dashboard_path.is_file():
                try:
                    dashboard_path.unlink()
                except OSError:
                    pass
            self._send_json(200, {"message": "All projects cleared"})
            return

        # Remove a specific project by path
        target_path = body.get("path")
        if not target_path:
            self._send_error(400, "Missing 'path' or 'clear_all' field")
            return

        # Normalize the target path for comparison
        try:
            normalized_target = str(Path(target_path).resolve())
        except (OSError, ValueError):
            self._send_error(400, "Invalid path")
            return

        # Find and remove the matching project
        original_count = len(projects)
        projects = [
            p for p in projects
            if str(Path(p["path"]).resolve()) != normalized_target
        ]

        if len(projects) == original_count:
            self._send_error(404, "Project not found")
            return

        save_projects(projects)

        if projects:
            # Still have projects remaining → regenerate dashboard
            self._trigger_regenerate()
        else:
            # No remaining projects → remove dashboard.html
            dashboard_path = VIEWS_DIR / "dashboard.html"
            if dashboard_path.is_file():
                try:
                    dashboard_path.unlink()
                except OSError:
                    pass

        self._send_json(200, {"message": "Project removed"})

    # --- Helper methods ---

    def _serve_empty_dashboard(self):
        """Serve the template with empty APP_DATA when no dashboard has been generated yet."""
        template_path = BASE_DIR / "dashboard_template.html"
        if not template_path.is_file():
            self._send_error(500, "Template file not found")
            return

        try:
            template_content = template_path.read_text(encoding="utf-8")
            # Inject empty data so React app loads and shows the empty state guide
            empty_data = json.dumps({
                "projects": {},
                "generated_at": "",
                "generator_version": "1.0.0",
            })
            html_content = template_content.replace("{{APP_DATA}}", empty_data)
            content_bytes = html_content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content_bytes)))
            self.end_headers()
            self.wfile.write(content_bytes)
        except OSError:
            self._send_error(500, "Failed to read template")

    def _serve_static_file(self, file_path: Path):
        """Serve a static file from disk."""
        # Prevent path traversal
        try:
            file_path = file_path.resolve()
            if not str(file_path).startswith(str(BASE_DIR)):
                self._send_error(403, "Forbidden")
                return
        except (OSError, ValueError):
            self._send_error(400, "Bad Request")
            return

        if not file_path.is_file():
            self._send_error(404, "Not Found")
            return

        content_type = self._guess_content_type(file_path)
        try:
            content = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            self._send_error(500, "Internal Server Error")

    def _guess_content_type(self, file_path: Path) -> str:
        """Guess MIME type based on file extension."""
        ext = file_path.suffix.lower()
        mime_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
        }
        return mime_types.get(ext, "application/octet-stream")

    def _send_json(self, status_code: int, data: dict):
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status_code: int, message: str):
        """Send an error response as JSON."""
        self._send_json(status_code, {"error": message})

    def _read_body(self) -> bytes:
        """Read the request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(content_length)

    def log_message(self, format, *args):
        """Override to use cleaner log format."""
        print(f"[{self.log_date_time_string()}] {format % args}")


def is_port_available(host: str, port: int) -> bool:
    """Check if the given port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def main():
    """Start the dashboard server."""
    if not is_port_available(HOST, PORT):
        print(f"错误: 端口 {PORT} 已被占用。请关闭占用该端口的进程后重试。")
        print(f"Error: Port {PORT} is already in use. Please close the process using it and try again.")
        sys.exit(1)

    # Startup auto-generation: load projects and generate dashboard
    projects = load_projects()
    if projects:
        try:
            regenerate_dashboard()
            print(f"Dashboard generated with {len(projects)} project(s)")
        except SystemExit:
            print("Warning: Dashboard generation failed, but server will start anyway")
        except Exception as e:
            print(f"Warning: Dashboard generation error ({e}), but server will start anyway")
    else:
        print("No projects configured. Add projects via the browser interface.")

    server = HTTPServer((HOST, PORT), DashboardHandler)
    print(f"Dashboard server running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")

    webbrowser.open(f"http://localhost:{PORT}/dashboard.html")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
