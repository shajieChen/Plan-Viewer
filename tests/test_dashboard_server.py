"""Tests for dashboard_server.py basic framework."""

import io
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard_server import (
    DashboardHandler,
    is_port_available,
    HOST,
    PORT,
    BASE_DIR,
    VIEWS_DIR,
)


class FakeRequest:
    """Minimal fake request for testing the handler."""

    def __init__(self, method: str, path: str):
        self.method = method
        self.path = path


def make_handler(method: str, path: str):
    """Create a DashboardHandler instance for testing without a real socket."""
    handler = DashboardHandler.__new__(DashboardHandler)
    handler.path = path
    handler.headers = {"Content-Length": "0"}
    handler.wfile = io.BytesIO()
    handler.rfile = io.BytesIO(b"")
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.command = method
    handler.request_version = "HTTP/1.1"
    handler.close_connection = True
    # Capture responses
    handler._response_code = None
    handler._response_headers = {}

    original_send_response = DashboardHandler.send_response

    def mock_send_response(self, code, message=None):
        self._response_code = code

    def mock_send_header(self, key, value):
        self._response_headers[key] = value

    def mock_end_headers(self):
        pass

    def mock_log_message(self, format, *args):
        pass

    handler.send_response = mock_send_response.__get__(handler)
    handler.send_header = mock_send_header.__get__(handler)
    handler.end_headers = mock_end_headers.__get__(handler)
    handler.log_message = mock_log_message.__get__(handler)

    return handler


class TestStaticFileServing:
    """Test static file serving from views/ directory."""

    def test_dashboard_html_route_serves_file(self):
        """GET /dashboard.html should serve views/dashboard.html."""
        handler = make_handler("GET", "/dashboard.html")
        # views/dashboard.html exists in the project
        handler.do_GET()
        assert handler._response_code == 200
        assert "text/html" in handler._response_headers.get("Content-Type", "")

    def test_views_subpath_serves_file(self):
        """GET /views/dashboard.html should serve the file."""
        handler = make_handler("GET", "/views/dashboard.html")
        handler.do_GET()
        assert handler._response_code == 200
        assert "text/html" in handler._response_headers.get("Content-Type", "")

    def test_nonexistent_file_returns_404(self):
        """GET for a nonexistent file should return 404."""
        handler = make_handler("GET", "/views/nonexistent.html")
        handler.do_GET()
        assert handler._response_code == 404

    def test_unknown_route_returns_404(self):
        """GET for an unknown route should return 404."""
        handler = make_handler("GET", "/unknown/path")
        handler.do_GET()
        assert handler._response_code == 404


class TestContentTypes:
    """Test MIME type detection."""

    def test_html_content_type(self):
        handler = make_handler("GET", "/dashboard.html")
        handler.do_GET()
        assert "text/html" in handler._response_headers.get("Content-Type", "")

    def test_css_content_type(self):
        """Test that .css files get correct content type."""
        handler = make_handler("GET", "/dashboard.html")
        content_type = handler._guess_content_type(Path("style.css"))
        assert content_type == "text/css; charset=utf-8"

    def test_js_content_type(self):
        """Test that .js files get correct content type."""
        handler = make_handler("GET", "/dashboard.html")
        content_type = handler._guess_content_type(Path("app.js"))
        assert content_type == "application/javascript; charset=utf-8"

    def test_json_content_type(self):
        """Test that .json files get correct content type."""
        handler = make_handler("GET", "/dashboard.html")
        content_type = handler._guess_content_type(Path("data.json"))
        assert content_type == "application/json; charset=utf-8"

    def test_unknown_extension_returns_octet_stream(self):
        """Unknown extensions should return application/octet-stream."""
        handler = make_handler("GET", "/dashboard.html")
        content_type = handler._guess_content_type(Path("file.xyz"))
        assert content_type == "application/octet-stream"


class TestPortAvailability:
    """Test port availability checking."""

    def test_available_port(self):
        """An unused port should be reported as available."""
        # Use a high port that's unlikely to be in use
        assert is_port_available("127.0.0.1", 59999) is True

    def test_occupied_port(self):
        """An occupied port should be reported as unavailable."""
        # Bind a port, then check it
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 59998))
            s.listen(1)
            assert is_port_available("127.0.0.1", 59998) is False


class TestAPIRoutesPlaceholder:
    """Test that unimplemented API routes return 404 for now."""

    def test_post_unknown_route_returns_404(self):
        handler = make_handler("POST", "/api/unknown")
        handler.do_POST()
        assert handler._response_code == 404

    def test_delete_unknown_route_returns_404(self):
        handler = make_handler("DELETE", "/api/unknown")
        handler.do_DELETE()
        assert handler._response_code == 404


class TestMainFunction:
    """Test the main() startup behavior."""

    @patch("dashboard_server.is_port_available", return_value=False)
    def test_exits_when_port_occupied(self, mock_port_check):
        """Server should exit with error when port is occupied."""
        from dashboard_server import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def make_post_handler(path: str, body: dict):
    """Create a handler configured for a POST request with JSON body."""
    body_bytes = json.dumps(body).encode("utf-8")
    handler = DashboardHandler.__new__(DashboardHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body_bytes))}
    handler.wfile = io.BytesIO()
    handler.rfile = io.BytesIO(body_bytes)
    handler.requestline = f"POST {path} HTTP/1.1"
    handler.command = "POST"
    handler.request_version = "HTTP/1.1"
    handler.close_connection = True
    handler._response_code = None
    handler._response_headers = {}
    handler._response_body = None

    def mock_send_response(self, code, message=None):
        self._response_code = code

    def mock_send_header(self, key, value):
        self._response_headers[key] = value

    def mock_end_headers(self):
        pass

    def mock_log_message(self, format, *args):
        pass

    # Capture the JSON body written to wfile
    original_wfile = handler.wfile

    handler.send_response = mock_send_response.__get__(handler)
    handler.send_header = mock_send_header.__get__(handler)
    handler.end_headers = mock_end_headers.__get__(handler)
    handler.log_message = mock_log_message.__get__(handler)

    return handler


class TestPostProjects:
    """Test POST /api/projects endpoint."""

    def test_missing_path_field_returns_400(self):
        """POST without 'path' field should return 400."""
        handler = make_post_handler("/api/projects", {"foo": "bar"})
        handler.do_POST()
        assert handler._response_code == 400

    def test_empty_path_field_returns_400(self):
        """POST with empty 'path' field should return 400."""
        handler = make_post_handler("/api/projects", {"path": ""})
        handler.do_POST()
        assert handler._response_code == 400

    def test_nonexistent_path_returns_400(self, tmp_path):
        """POST with a path that doesn't exist should return 400."""
        fake_path = str(tmp_path / "nonexistent_dir")
        handler = make_post_handler("/api/projects", {"path": fake_path})
        handler.do_POST()
        assert handler._response_code == 400

    def test_path_without_status_yaml_returns_422(self, tmp_path):
        """POST with a path that exists but has no status/status.yaml should return 422."""
        # Create the directory but not status/status.yaml
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        handler = make_post_handler("/api/projects", {"path": str(project_dir)})
        handler.do_POST()
        assert handler._response_code == 422

    @patch("dashboard_server.load_projects", return_value=[])
    @patch("dashboard_server.save_projects")
    def test_valid_project_returns_200(self, mock_save, mock_load, tmp_path):
        """POST with a valid project path should return 200."""
        # Create valid project structure
        project_dir = tmp_path / "valid_project"
        project_dir.mkdir()
        status_dir = project_dir / "status"
        status_dir.mkdir()
        (status_dir / "status.yaml").write_text("meta:\n  project_name: Test\n")

        handler = make_post_handler("/api/projects", {"path": str(project_dir)})
        # Patch _trigger_regenerate on the handler instance to avoid side effects
        handler._trigger_regenerate = lambda: None
        handler.do_POST()
        assert handler._response_code == 200

    @patch("dashboard_server.load_projects")
    def test_duplicate_project_returns_409(self, mock_load, tmp_path):
        """POST with a path that's already in projects should return 409."""
        # Create valid project structure
        project_dir = tmp_path / "dup_project"
        project_dir.mkdir()
        status_dir = project_dir / "status"
        status_dir.mkdir()
        (status_dir / "status.yaml").write_text("meta:\n  project_name: Test\n")

        # Mock load_projects to return the same path
        mock_load.return_value = [{"path": str(project_dir.resolve())}]

        handler = make_post_handler("/api/projects", {"path": str(project_dir)})
        handler.do_POST()
        assert handler._response_code == 409

    def test_invalid_json_body_returns_400(self):
        """POST with invalid JSON body should return 400."""
        handler = DashboardHandler.__new__(DashboardHandler)
        handler.path = "/api/projects"
        handler.headers = {"Content-Length": "12"}
        handler.wfile = io.BytesIO()
        handler.rfile = io.BytesIO(b"not valid json")
        handler.requestline = "POST /api/projects HTTP/1.1"
        handler.command = "POST"
        handler.request_version = "HTTP/1.1"
        handler.close_connection = True
        handler._response_code = None
        handler._response_headers = {}

        def mock_send_response(self, code, message=None):
            self._response_code = code

        def mock_send_header(self, key, value):
            self._response_headers[key] = value

        def mock_end_headers(self):
            pass

        def mock_log_message(self, format, *args):
            pass

        handler.send_response = mock_send_response.__get__(handler)
        handler.send_header = mock_send_header.__get__(handler)
        handler.end_headers = mock_end_headers.__get__(handler)
        handler.log_message = mock_log_message.__get__(handler)

        handler.do_POST()
        assert handler._response_code == 400


class TestGetProjects:
    """Test GET /api/projects endpoint."""

    @patch("dashboard_server.load_projects", return_value=[])
    def test_empty_projects_returns_empty_list(self, mock_load):
        """GET /api/projects with no projects should return empty list."""
        handler = make_handler("GET", "/api/projects")
        handler.do_GET()
        assert handler._response_code == 200
        # Verify JSON body contains empty projects list
        body = handler.wfile.getvalue()
        data = json.loads(body)
        assert data == {"projects": []}

    @patch("dashboard_server.load_projects")
    def test_valid_project_returns_name_and_valid_true(self, mock_load, tmp_path):
        """GET /api/projects should return valid=True and name from status.yaml."""
        # Create a valid project with status.yaml containing meta.project_name
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        status_dir = project_dir / "status"
        status_dir.mkdir()
        (status_dir / "status.yaml").write_text(
            "meta:\n  project_name: My Cool Project\n", encoding="utf-8"
        )

        mock_load.return_value = [{"path": str(project_dir)}]

        handler = make_handler("GET", "/api/projects")
        handler.do_GET()
        assert handler._response_code == 200
        body = handler.wfile.getvalue()
        data = json.loads(body)
        assert len(data["projects"]) == 1
        proj = data["projects"][0]
        assert proj["path"] == str(project_dir)
        assert proj["name"] == "My Cool Project"
        assert proj["valid"] is True

    @patch("dashboard_server.load_projects")
    def test_invalid_project_returns_valid_false(self, mock_load, tmp_path):
        """GET /api/projects should return valid=False when status.yaml missing."""
        # Create a project directory without status/status.yaml
        project_dir = tmp_path / "no_status_project"
        project_dir.mkdir()

        mock_load.return_value = [{"path": str(project_dir)}]

        handler = make_handler("GET", "/api/projects")
        handler.do_GET()
        assert handler._response_code == 200
        body = handler.wfile.getvalue()
        data = json.loads(body)
        assert len(data["projects"]) == 1
        proj = data["projects"][0]
        assert proj["path"] == str(project_dir)
        assert proj["name"] == "no_status_project"  # falls back to dir name
        assert proj["valid"] is False

    @patch("dashboard_server.load_projects")
    def test_project_name_fallback_to_dirname(self, mock_load, tmp_path):
        """When status.yaml exists but has no meta.project_name, use dir name."""
        project_dir = tmp_path / "fallback_project"
        project_dir.mkdir()
        status_dir = project_dir / "status"
        status_dir.mkdir()
        # status.yaml exists but without meta.project_name
        (status_dir / "status.yaml").write_text("items:\n  - task1\n", encoding="utf-8")

        mock_load.return_value = [{"path": str(project_dir)}]

        handler = make_handler("GET", "/api/projects")
        handler.do_GET()
        assert handler._response_code == 200
        body = handler.wfile.getvalue()
        data = json.loads(body)
        proj = data["projects"][0]
        assert proj["name"] == "fallback_project"
        assert proj["valid"] is True

    @patch("dashboard_server.load_projects")
    def test_multiple_projects_mixed_validity(self, mock_load, tmp_path):
        """GET /api/projects with multiple projects, some valid some not."""
        # Valid project
        valid_dir = tmp_path / "valid_proj"
        valid_dir.mkdir()
        (valid_dir / "status").mkdir()
        (valid_dir / "status" / "status.yaml").write_text(
            "meta:\n  project_name: Valid\n", encoding="utf-8"
        )

        # Invalid project (no status.yaml)
        invalid_dir = tmp_path / "invalid_proj"
        invalid_dir.mkdir()

        mock_load.return_value = [
            {"path": str(valid_dir)},
            {"path": str(invalid_dir)},
        ]

        handler = make_handler("GET", "/api/projects")
        handler.do_GET()
        assert handler._response_code == 200
        body = handler.wfile.getvalue()
        data = json.loads(body)
        assert len(data["projects"]) == 2
        assert data["projects"][0]["valid"] is True
        assert data["projects"][0]["name"] == "Valid"
        assert data["projects"][1]["valid"] is False
        assert data["projects"][1]["name"] == "invalid_proj"


class TestRegenerateEndpoint:
    """Test POST /api/regenerate endpoint."""

    def test_regenerate_no_projects_returns_200_with_zero_count(self):
        """POST /api/regenerate with no projects returns 200 with project_count=0."""
        handler = make_handler("POST", "/api/regenerate")
        with patch("dashboard_server.load_projects", return_value=[]):
            handler.do_POST()
        assert handler._response_code == 200
        body = json.loads(handler.wfile.getvalue())
        assert body["project_count"] == 0
        assert "generated_at" in body

    @patch("dashboard_server.regenerate_dashboard")
    @patch("dashboard_server.load_projects")
    def test_regenerate_success_returns_200_with_count(self, mock_load, mock_regen):
        """POST /api/regenerate with valid projects returns 200 with correct count."""
        mock_load.return_value = [
            {"path": "Q:\\Project1"},
            {"path": "Q:\\Project2"},
        ]
        mock_regen.return_value = VIEWS_DIR / "dashboard.html"

        handler = make_handler("POST", "/api/regenerate")
        handler.do_POST()

        assert handler._response_code == 200
        body = json.loads(handler.wfile.getvalue())
        assert body["project_count"] == 2
        assert "generated_at" in body
        mock_regen.assert_called_once()

    @patch("dashboard_server.regenerate_dashboard")
    @patch("dashboard_server.load_projects")
    def test_regenerate_all_fail_returns_500(self, mock_load, mock_regen):
        """POST /api/regenerate returns 500 when all projects fail (SystemExit)."""
        mock_load.return_value = [{"path": "Q:\\BadProject"}]
        mock_regen.side_effect = SystemExit(1)

        handler = make_handler("POST", "/api/regenerate")
        handler.do_POST()

        assert handler._response_code == 500
        body = json.loads(handler.wfile.getvalue())
        assert "error" in body

    def test_regenerate_generated_at_is_iso_format(self):
        """POST /api/regenerate returns generated_at in ISO format."""
        handler = make_handler("POST", "/api/regenerate")
        with patch("dashboard_server.load_projects", return_value=[]):
            handler.do_POST()
        body = json.loads(handler.wfile.getvalue())
        # Should be parseable as ISO datetime
        from datetime import datetime
        dt = datetime.fromisoformat(body["generated_at"])
        assert dt is not None


class TestRegenerateDashboardFunction:
    """Test the module-level regenerate_dashboard() function."""

    @patch("dashboard_server.load_projects", return_value=[])
    def test_returns_none_when_no_projects(self, mock_load):
        """regenerate_dashboard() returns None when no projects configured."""
        from dashboard_server import regenerate_dashboard
        result = regenerate_dashboard()
        assert result is None

    @patch("dashboard_server.DashboardGenerator")
    @patch("dashboard_server.load_projects")
    def test_calls_generator_with_correct_paths(self, mock_load, mock_gen_cls):
        """regenerate_dashboard() creates DashboardGenerator with correct args."""
        mock_load.return_value = [
            {"path": "Q:\\Project1"},
            {"path": "Q:\\Project2"},
        ]
        mock_instance = MagicMock()
        mock_instance.generate.return_value = VIEWS_DIR / "dashboard.html"
        mock_gen_cls.return_value = mock_instance

        from dashboard_server import regenerate_dashboard
        result = regenerate_dashboard()

        mock_gen_cls.assert_called_once()
        call_args = mock_gen_cls.call_args
        # Check project_paths
        assert len(call_args[0][0]) == 2
        # Check output_path
        assert call_args[0][1] == VIEWS_DIR / "dashboard.html"
        # Check template_path
        assert call_args[0][2] == BASE_DIR / "dashboard_template.html"
        mock_instance.generate.assert_called_once()
        assert result == VIEWS_DIR / "dashboard.html"


def make_delete_handler(path: str, body: dict):
    """Create a handler configured for a DELETE request with JSON body."""
    body_bytes = json.dumps(body).encode("utf-8")
    handler = DashboardHandler.__new__(DashboardHandler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(body_bytes))}
    handler.wfile = io.BytesIO()
    handler.rfile = io.BytesIO(body_bytes)
    handler.requestline = f"DELETE {path} HTTP/1.1"
    handler.command = "DELETE"
    handler.request_version = "HTTP/1.1"
    handler.close_connection = True
    handler._response_code = None
    handler._response_headers = {}

    def mock_send_response(self, code, message=None):
        self._response_code = code

    def mock_send_header(self, key, value):
        self._response_headers[key] = value

    def mock_end_headers(self):
        pass

    def mock_log_message(self, format, *args):
        pass

    handler.send_response = mock_send_response.__get__(handler)
    handler.send_header = mock_send_header.__get__(handler)
    handler.end_headers = mock_end_headers.__get__(handler)
    handler.log_message = mock_log_message.__get__(handler)

    return handler


class TestDeleteProjects:
    """Test DELETE /api/projects endpoint."""

    @patch("dashboard_server.save_projects")
    @patch("dashboard_server.load_projects")
    def test_clear_all_returns_200(self, mock_load, mock_save):
        """DELETE with clear_all=true should clear all projects and return 200."""
        mock_load.return_value = [{"path": "Q:\\Project1"}, {"path": "Q:\\Project2"}]

        handler = make_delete_handler("/api/projects", {"clear_all": True})
        handler.do_DELETE()

        assert handler._response_code == 200
        mock_save.assert_called_once_with([])
        body = json.loads(handler.wfile.getvalue())
        assert body["message"] == "All projects cleared"

    @patch("dashboard_server.save_projects")
    @patch("dashboard_server.load_projects")
    def test_remove_specific_project_returns_200(self, mock_load, mock_save, tmp_path):
        """DELETE with a valid path should remove that project and return 200."""
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        resolved = str(project_dir.resolve())

        mock_load.return_value = [{"path": resolved}]

        handler = make_delete_handler("/api/projects", {"path": resolved})
        # Patch _trigger_regenerate to avoid side effects
        handler._trigger_regenerate = lambda: None
        handler.do_DELETE()

        assert handler._response_code == 200
        body = json.loads(handler.wfile.getvalue())
        assert body["message"] == "Project removed"
        mock_save.assert_called_once_with([])

    @patch("dashboard_server.load_projects")
    def test_remove_nonexistent_project_returns_404(self, mock_load, tmp_path):
        """DELETE with a path not in projects should return 404."""
        mock_load.return_value = [{"path": "Q:\\ExistingProject"}]

        handler = make_delete_handler("/api/projects", {"path": "Q:\\NotInList"})
        handler.do_DELETE()

        assert handler._response_code == 404
        body = json.loads(handler.wfile.getvalue())
        assert "error" in body

    def test_delete_missing_path_and_clear_all_returns_400(self):
        """DELETE without 'path' or 'clear_all' should return 400."""
        handler = make_delete_handler("/api/projects", {"foo": "bar"})
        handler.do_DELETE()

        assert handler._response_code == 400

    def test_delete_invalid_json_returns_400(self):
        """DELETE with invalid JSON body should return 400."""
        handler = DashboardHandler.__new__(DashboardHandler)
        handler.path = "/api/projects"
        handler.headers = {"Content-Length": "10"}
        handler.wfile = io.BytesIO()
        handler.rfile = io.BytesIO(b"not json!!")
        handler.requestline = "DELETE /api/projects HTTP/1.1"
        handler.command = "DELETE"
        handler.request_version = "HTTP/1.1"
        handler.close_connection = True
        handler._response_code = None
        handler._response_headers = {}

        def mock_send_response(self, code, message=None):
            self._response_code = code

        def mock_send_header(self, key, value):
            self._response_headers[key] = value

        def mock_end_headers(self):
            pass

        def mock_log_message(self, format, *args):
            pass

        handler.send_response = mock_send_response.__get__(handler)
        handler.send_header = mock_send_header.__get__(handler)
        handler.end_headers = mock_end_headers.__get__(handler)
        handler.log_message = mock_log_message.__get__(handler)

        handler.do_DELETE()
        assert handler._response_code == 400


class TestPathTraversalProtection:
    """Test that path traversal attempts are blocked."""

    def test_path_traversal_returns_403(self):
        """Attempting to access files outside BASE_DIR should return 403."""
        handler = make_handler("GET", "/views/../../../etc/passwd")
        handler.do_GET()
        # Should be either 403 (forbidden) or 404 (not found)
        assert handler._response_code in (403, 404)

    def test_views_path_traversal_blocked(self):
        """Path traversal via /views/../../ should be blocked."""
        handler = make_handler("GET", "/views/../../secret.txt")
        handler.do_GET()
        assert handler._response_code in (403, 404)
