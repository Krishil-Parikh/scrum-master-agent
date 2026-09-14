import pytest

from app.tools.filesystem import PathTraversalError, read_text, safe_join, write_text


def test_safe_join_allows_normal_relative_path(tmp_path):
    result = safe_join(tmp_path, "src/app.py")
    assert result == (tmp_path / "src" / "app.py").resolve()


def test_safe_join_blocks_parent_traversal(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "../../etc/passwd")


def test_safe_join_blocks_absolute_escape(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, f"../{outside.name}")


def test_write_then_read_roundtrip(tmp_path):
    write_text(tmp_path, "notes/readme.md", "hello world")
    assert read_text(tmp_path, "notes/readme.md") == "hello world"


def test_write_creates_parent_dirs(tmp_path):
    path = write_text(tmp_path, "a/b/c/d.txt", "nested")
    assert path.exists()
    assert path.read_text() == "nested"
