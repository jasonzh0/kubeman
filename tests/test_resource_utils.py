"""Unit tests for resource_utils path-safety helpers."""

import pytest

from kubeman.resource_utils import (
    validate_path_component,
    ensure_within,
    safe_manifest_path,
    is_cluster_scoped,
)


class TestValidatePathComponent:
    """Validation that prevents path traversal via resource names."""

    @pytest.mark.parametrize("value", ["backend-api", "svc", "a.b.c", "x_y", "Deployment"])
    def test_accepts_safe_names(self, value):
        assert validate_path_component(value) == value

    @pytest.mark.parametrize(
        "value",
        ["../evil", "a/b", "a\\b", "..", ".", "", "foo/../bar", "/abs", "x" * 254],
    )
    def test_rejects_unsafe_names(self, value):
        with pytest.raises(ValueError):
            validate_path_component(value)

    def test_rejects_non_string(self):
        with pytest.raises(ValueError):
            validate_path_component(None)  # type: ignore[arg-type]


class TestEnsureWithin:
    def test_allows_path_inside_base(self, tmp_path):
        target = tmp_path / "sub" / "file.yaml"
        assert ensure_within(tmp_path, target) == target.resolve()

    def test_rejects_escape(self, tmp_path):
        with pytest.raises(ValueError):
            ensure_within(tmp_path / "out", tmp_path / "out" / ".." / ".." / "etc")


class TestSafeManifestPath:
    def test_builds_expected_path(self, tmp_path):
        path = safe_manifest_path(tmp_path, "my-svc", "service")
        assert path == (tmp_path / "my-svc-service.yaml").resolve()

    def test_rejects_traversal_in_name(self, tmp_path):
        with pytest.raises(ValueError):
            safe_manifest_path(tmp_path, "../../etc/passwd", "service")

    def test_rejects_traversal_in_kind(self, tmp_path):
        with pytest.raises(ValueError):
            safe_manifest_path(tmp_path, "svc", "../evil")


def test_is_cluster_scoped():
    assert is_cluster_scoped("Namespace") is True
    assert is_cluster_scoped("Deployment") is False
