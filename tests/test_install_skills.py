"""Tests for Tools/install_skills.py.

Validates correctness properties P2-P5 from the design doc
``Docs/specs/2026-05-18-skill-installer-multi-agent-design.md`` plus
unit-level edge cases. Every test uses ``tmp_path``; nothing ever writes
to ``%USERPROFILE%``.
"""

from __future__ import annotations

import hashlib
import re
import string
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

# Make Tools/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Tools"))

from install_skills import (  # noqa: E402  (sys.path mutation above)
    Skill,
    _install_folder,
    build_shared_content,
    discover_skills,
    install_cursor,
    install_kiro,
    install_shared,
    load_skill,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_skill_dir(
    parent: Path,
    name: str,
    body: str,
    *,
    description: str = "A test skill",
) -> Path:
    """Create ``parent/name/SKILL.md`` with valid front-matter and given body.

    Returns the directory path.
    """
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    front_matter = f"---\nname: {name}\ndescription: {description}\n---\n"
    (skill_dir / "SKILL.md").write_text(front_matter + body, encoding="utf-8")
    return skill_dir


def folder_target(target_root: Path) -> dict:
    """Build an Agent dict for folder-style targets (Kiro/Claude shape)."""
    return {"id": "kiro", "kind": "folder", "target": target_root}


def cursor_target(target_root: Path) -> dict:
    return {"id": "cursor", "kind": "mdc", "target": target_root}


def shared_target(target_path: Path) -> dict:
    return {"id": "copilot", "kind": "shared", "target": target_path}


# ---------------------------------------------------------------------------
# Unit: discover_skills
# ---------------------------------------------------------------------------


class TestDiscoverSkills:
    def test_returns_sorted_subdirs_with_skill_md(self, tmp_path):
        make_skill_dir(tmp_path, "zebra", "body")
        make_skill_dir(tmp_path, "alpha", "body")
        make_skill_dir(tmp_path, "mango", "body")
        result = discover_skills(tmp_path)
        assert [p.name for p in result] == ["alpha", "mango", "zebra"]

    def test_skips_subdirs_without_skill_md(self, tmp_path, capsys):
        make_skill_dir(tmp_path, "with-skill", "body")
        (tmp_path / "no-skill-here").mkdir()
        result = discover_skills(tmp_path)
        assert [p.name for p in result] == ["with-skill"]
        out = capsys.readouterr().out
        assert "SKIP: no-skill-here (no SKILL.md)" in out

    def test_raises_when_source_dir_missing(self, tmp_path):
        missing = tmp_path / "does-not-exist"
        with pytest.raises(FileNotFoundError):
            discover_skills(missing)

    def test_returns_empty_list_when_no_qualifying_dirs(self, tmp_path):
        (tmp_path / "stray-file.txt").write_text("not a skill")
        result = discover_skills(tmp_path)
        assert result == []

    def test_load_skill_round_trip(self, tmp_path):
        make_skill_dir(tmp_path, "demo", "# Body content\n")
        skill = load_skill(tmp_path / "demo")
        assert skill.name == "demo"
        assert skill.metadata["name"] == "demo"
        assert skill.metadata["description"] == "A test skill"
        assert "Body content" in skill.body


# ---------------------------------------------------------------------------
# Unit: build_shared_content
# ---------------------------------------------------------------------------


class TestBuildSharedContent:
    def test_empty_list_returns_empty_string(self):
        assert build_shared_content([]) == ""

    def test_single_skill_one_marker_pair(self):
        skill = Skill(
            name="solo",
            source_dir=Path("/dummy"),
            metadata={"name": "solo", "description": "x"},
            body="# Hello\n",
        )
        out = build_shared_content([skill])
        assert out.count("<!-- BEGIN: solo -->") == 1
        assert out.count("<!-- END: solo -->") == 1
        assert "# Hello" in out

    def test_multiple_skills_input_order_preserved(self):
        skills = [
            Skill(
                name=name,
                source_dir=Path("/dummy"),
                metadata={"name": name, "description": "x"},
                body=f"body of {name}",
            )
            for name in ("alpha", "beta", "gamma")
        ]
        out = build_shared_content(skills)
        # Markers appear in the input order
        positions = [out.index(f"<!-- BEGIN: {n} -->") for n in ("alpha", "beta", "gamma")]
        assert positions == sorted(positions)

    def test_body_with_internal_triple_dash_lines_preserved(self):
        skill = Skill(
            name="raw",
            source_dir=Path("/dummy"),
            metadata={"name": "raw", "description": "x"},
            body="head\n---\nmid\n---\ntail\n",
        )
        out = build_shared_content([skill])
        assert "head\n---\nmid\n---\ntail" in out

    def test_output_uses_lf_only(self):
        skill = Skill(
            name="lf-test",
            source_dir=Path("/dummy"),
            metadata={"name": "lf-test", "description": "x"},
            body="line1\r\nline2\r\nline3\r\n",
        )
        out = build_shared_content([skill])
        assert "\r\n" not in out
        assert "\r" not in out


# ---------------------------------------------------------------------------
# Property tests (P2, P3, P4, P5)
# ---------------------------------------------------------------------------


# Skill name strategy: lowercase + digits + hyphen, length 1-32, no leading/trailing hyphen
_skill_name_strategy = st.from_regex(
    r"\A[a-z0-9](?:[a-z0-9\-]{0,30}[a-z0-9])?\Z",
    fullmatch=True,
)

# Body strategy: arbitrary text including unicode + emoji + line endings + --- lines
_body_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # exclude unpaired surrogates
    min_size=0,
    max_size=300,
)


@st.composite
def _unique_skill_lists(draw, min_size: int = 1, max_size: int = 8):
    names = draw(
        st.lists(_skill_name_strategy, min_size=min_size, max_size=max_size, unique=True)
    )
    out: list[Skill] = []
    for n in names:
        body = draw(_body_strategy)
        out.append(
            Skill(
                name=n,
                source_dir=Path("/dummy"),
                metadata={"name": n, "description": "x"},
                body=body,
            )
        )
    return out


def _extract_block(text: str, name: str) -> str:
    """Return the substring strictly between BEGIN/END markers for ``name``.

    The markers themselves are not included; the two blank-line paddings that
    ``build_shared_content`` wraps around the body are stripped (BEGIN + "\\n\\n"
    + body + "\\n\\n" + END), so the returned string equals the rstripped body.
    """
    begin = f"<!-- BEGIN: {name} -->"
    end = f"<!-- END: {name} -->"
    start = text.index(begin) + len(begin)
    finish = text.index(end, start)
    inner = text[start:finish]
    # Padding scheme: exactly two leading and two trailing newlines around body.
    if inner.startswith("\n\n"):
        inner = inner[2:]
    if inner.endswith("\n\n"):
        inner = inner[:-2]
    return inner


@given(skills=_unique_skill_lists())
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_p2_concatenation_round_trip(skills):
    """Property 2 (design §9): each skill's body is recoverable byte-for-byte
    from the marker block in ``build_shared_content`` output (after rstrip
    + LF normalization which the function applies)."""
    out = build_shared_content(skills)
    for skill in skills:
        expected = skill.body.replace("\r\n", "\n").rstrip()
        # Empty bodies render as a single blank line between markers; allow that case
        actual = _extract_block(out, skill.name)
        # The function pads body with a trailing blank line; after our extraction
        # actual == expected exactly (both empty string when body was whitespace-only).
        assert actual == expected, f"body mismatch for skill {skill.name!r}"


@given(skills=_unique_skill_lists(min_size=2))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_p3_sort_order_after_caller_sort(skills):
    """Property 3 (design §9): when the caller sorts skills by name (lex),
    the BEGIN markers in the output appear in the same lex order."""
    sorted_skills = sorted(skills, key=lambda s: s.name)
    out = build_shared_content(sorted_skills)
    positions = [out.index(f"<!-- BEGIN: {s.name} -->") for s in sorted_skills]
    assert positions == sorted(positions)


@st.composite
def _folder_tree(draw):
    """Generate a small synthetic folder tree (relative path -> bytes)."""
    n_files = draw(st.integers(min_value=1, max_value=5))
    files: dict[str, bytes] = {}
    name_strategy = st.text(alphabet=string.ascii_letters + string.digits + "_", min_size=1, max_size=12)
    for _ in range(n_files):
        # 1-3 path segments
        seg_count = draw(st.integers(min_value=1, max_value=3))
        segments = [draw(name_strategy) for _ in range(seg_count)]
        rel = "/".join(segments) + ".txt"
        if rel in files:
            continue
        content = draw(st.binary(min_size=0, max_size=120))
        files[rel] = content
    return files


@given(tree=_folder_tree())
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
def test_p4_folder_copy_fidelity(tmp_path_factory, tree):
    """Property 4 (design §9): every source file (excluding pycache/pyc) appears
    at the target with byte-identical content; excluded patterns do not appear."""
    tmpdir = tmp_path_factory.mktemp("p4")
    src_root = tmpdir / "source"
    skill_name = "test-skill"
    skill_dir = src_root / skill_name
    skill_dir.mkdir(parents=True)

    # Required SKILL.md
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: x\n---\nbody\n", encoding="utf-8"
    )

    # Synthetic files
    for rel, content in tree.items():
        full = skill_dir / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)

    # Add excluded patterns
    pyc_dir = skill_dir / "__pycache__"
    pyc_dir.mkdir()
    (pyc_dir / "junk.cache").write_bytes(b"should-not-copy")
    (skill_dir / "stray.pyc").write_bytes(b"also-not-copy")

    skill = Skill(
        name=skill_name,
        source_dir=skill_dir,
        metadata={"name": skill_name, "description": "x"},
        body="body\n",
    )
    target_root = tmpdir / "target"
    agent = folder_target(target_root)
    result = _install_folder(skill, agent)
    assert result.success, result.error

    # Every non-excluded source file is present at target with identical bytes
    target_dir = target_root / skill_name
    for rel, content in tree.items():
        assert (target_dir / rel).read_bytes() == content
    # SKILL.md preserved
    assert (target_dir / "SKILL.md").read_text(encoding="utf-8").startswith("---\nname:")
    # Excluded patterns absent
    assert not (target_dir / "__pycache__").exists()
    assert not (target_dir / "stray.pyc").exists()


def _hash_tree(root: Path) -> dict[str, str]:
    """Return ``{relpath: sha256}`` for every file under ``root``."""
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


@given(skills=_unique_skill_lists(min_size=1, max_size=4))
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
def test_p5_idempotence(tmp_path_factory, skills):
    """Property 5 (design §9): running the install pipeline twice produces
    byte-identical target files."""
    tmpdir = tmp_path_factory.mktemp("p5")
    src_root = tmpdir / "source"
    src_root.mkdir()

    real_skills: list[Skill] = []
    for s in skills:
        skill_dir = make_skill_dir(src_root, s.name, s.body, description="x")
        real_skills.append(load_skill(skill_dir))

    folder_root = tmpdir / "kiro"
    cursor_root = tmpdir / "cursor"
    shared_path = tmpdir / "copilot.md"

    folder_agent = folder_target(folder_root)
    cursor_agent = cursor_target(cursor_root)
    shared_agent = shared_target(shared_path)

    def run_install():
        for skill in real_skills:
            install_kiro(skill, folder_agent)
            install_cursor(skill, cursor_agent)
        install_shared(build_shared_content(real_skills), shared_agent)

    run_install()
    h1_folder = _hash_tree(folder_root)
    h1_cursor = _hash_tree(cursor_root)
    h1_shared = hashlib.sha256(shared_path.read_bytes()).hexdigest()

    run_install()
    h2_folder = _hash_tree(folder_root)
    h2_cursor = _hash_tree(cursor_root)
    h2_shared = hashlib.sha256(shared_path.read_bytes()).hexdigest()

    assert h1_folder == h2_folder
    assert h1_cursor == h2_cursor
    assert h1_shared == h2_shared


# ---------------------------------------------------------------------------
# Unit tests for I/O helpers
# ---------------------------------------------------------------------------


class TestIOHelpers:
    def test_install_cursor_writes_valid_mdc(self, tmp_path):
        skill = Skill(
            name="demo",
            source_dir=tmp_path,
            metadata={"name": "demo", "description": "Hello world"},
            body="# Body\n",
        )
        target_dir = tmp_path / "rules"
        agent = cursor_target(target_dir)
        result = install_cursor(skill, agent)
        assert result.success, result.error
        out = (target_dir / "demo.mdc").read_text(encoding="utf-8")
        assert "description:" in out
        assert 'globs: ""' in out
        assert "alwaysApply: true" in out
        assert "# Body" in out

    def test_install_cursor_creates_missing_parent(self, tmp_path):
        skill = Skill(
            name="demo",
            source_dir=tmp_path,
            metadata={"name": "demo", "description": "x"},
            body="body",
        )
        agent = cursor_target(tmp_path / "deep" / "nested" / "rules")
        result = install_cursor(skill, agent)
        assert result.success, result.error
        assert (tmp_path / "deep" / "nested" / "rules" / "demo.mdc").is_file()

    def test_install_shared_creates_missing_parent_and_writes_lf(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "copilot-instructions.md"
        agent = shared_target(target)
        content = "line1\nline2\n"
        result = install_shared(content, agent)
        assert result.success, result.error
        raw = target.read_bytes()
        assert b"\r\n" not in raw
        assert raw == content.encode("utf-8")

    def test_install_kiro_overwrites_stale_target(self, tmp_path):
        # Source skill
        skill_dir = make_skill_dir(tmp_path, "demo", "fresh-body")
        skill = load_skill(skill_dir)

        # Pre-populate target with stale content
        target_root = tmp_path / "target"
        stale = target_root / "demo" / "stale.txt"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale", encoding="utf-8")
        (target_root / "demo" / "SKILL.md").write_text(
            "old content", encoding="utf-8"
        )

        agent = folder_target(target_root)
        result = install_kiro(skill, agent)
        assert result.success, result.error

        # SKILL.md replaced; stale file remains because copytree adds, doesn't prune.
        # That's the documented "overwrite" semantics for shared targets — we only
        # guarantee that source files appear at target with current contents.
        new_skill_md = (target_root / "demo" / "SKILL.md").read_text(encoding="utf-8")
        assert "fresh-body" in new_skill_md


def test_project_state_spec_is_discovered():
    """Verify project-state-spec is present and parseable in Tools/Skills/."""
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo / "Tools"))
    sys.path.insert(0, str(repo / "Docs" / "tools"))
    from install_skills import discover_skills, load_skill, SKILLS_SOURCE_DIR  # type: ignore

    discovered = discover_skills(SKILLS_SOURCE_DIR)
    names = [d.name for d in discovered]
    assert "project-state-spec" in names

    skill_dir = next(d for d in discovered if d.name == "project-state-spec")
    skill = load_skill(skill_dir)
    assert skill.metadata["name"] == "project-state-spec"
    assert "Requirement" in skill.metadata["description"] or "Three-stage" in skill.metadata["description"]
    assert skill.body.strip().startswith("# project-state-spec")
