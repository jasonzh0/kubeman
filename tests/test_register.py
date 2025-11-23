"""Unit tests for TemplateRegistry."""

import pytest
from kubeman.register import TemplateRegistry
from kubeman.chart import HelmChart


class TestTemplateRegistry:
    """Test cases for TemplateRegistry class."""

    def setup_method(self):
        """Clear registry before each test."""
        TemplateRegistry.clear()

    def test_register_chart(self):
        """Test registering a chart class."""

        class TestChart(HelmChart):
            @property
            def name(self):
                return "test"

            @property
            def repository(self):
                return {"type": "none"}

            @property
            def namespace(self):
                return "default"

            @property
            def version(self):
                return "1.0.0"

            def generate_values(self):
                return {}

        TemplateRegistry.register(TestChart)
        templates = TemplateRegistry.get_registered_templates()
        assert len(templates) == 1
        assert TestChart in templates

    def test_register_as_decorator(self):
        """Test using register as a decorator."""

        @TemplateRegistry.register
        class TestChart(HelmChart):
            @property
            def name(self):
                return "test"

            @property
            def repository(self):
                return {"type": "none"}

            @property
            def namespace(self):
                return "default"

            @property
            def version(self):
                return "1.0.0"

            def generate_values(self):
                return {}

        templates = TemplateRegistry.get_registered_templates()
        assert len(templates) == 1
        assert TestChart in templates

    def test_register_duplicate(self):
        """Test that registering the same chart twice doesn't duplicate."""

        class TestChart(HelmChart):
            @property
            def name(self):
                return "test"

            @property
            def repository(self):
                return {"type": "none"}

            @property
            def namespace(self):
                return "default"

            @property
            def version(self):
                return "1.0.0"

            def generate_values(self):
                return {}

        TemplateRegistry.register(TestChart)
        TemplateRegistry.register(TestChart)
        templates = TemplateRegistry.get_registered_templates()
        assert len(templates) == 1

    def test_get_registered_templates_returns_copy(self):
        """Test that get_registered_templates returns a copy."""

        class TestChart(HelmChart):
            @property
            def name(self):
                return "test"

            @property
            def repository(self):
                return {"type": "none"}

            @property
            def namespace(self):
                return "default"

            @property
            def version(self):
                return "1.0.0"

            def generate_values(self):
                return {}

        TemplateRegistry.register(TestChart)
        templates1 = TemplateRegistry.get_registered_templates()
        templates2 = TemplateRegistry.get_registered_templates()

        assert templates1 is not templates2
        assert templates1 == templates2

    def test_clear(self):
        """Test clearing the registry."""

        class TestChart(HelmChart):
            @property
            def name(self):
                return "test"

            @property
            def repository(self):
                return {"type": "none"}

            @property
            def namespace(self):
                return "default"

            @property
            def version(self):
                return "1.0.0"

            def generate_values(self):
                return {}

        TemplateRegistry.register(TestChart)
        assert len(TemplateRegistry.get_registered_templates()) == 1

        TemplateRegistry.clear()
        assert len(TemplateRegistry.get_registered_templates()) == 0

    def test_register_executes_build_step(self, monkeypatch):
        """Test that build() method is executed during registration."""
        from kubeman.kubernetes import KubernetesResource

        TemplateRegistry.clear()
        TemplateRegistry.set_skip_builds(False)

        build_called = []

        @TemplateRegistry.register
        class TestResource(KubernetesResource):
            def __init__(self):
                super().__init__()
                self.name = "test-resource"
                self.namespace = "default"

            def build(self):
                build_called.append(True)

            def render(self):
                pass

        assert len(build_called) == 1
        assert build_called[0] is True

    def test_register_skips_build_when_skipped(self, monkeypatch):
        """Test that build() is skipped when skip_builds is True."""
        from kubeman.kubernetes import KubernetesResource

        build_called = []

        TemplateRegistry.set_skip_builds(True)

        @TemplateRegistry.register
        class TestResource(KubernetesResource):
            def __init__(self):
                super().__init__()
                self.name = "test-resource"
                self.namespace = "default"

            def build(self):
                build_called.append(True)

            def render(self):
                pass

        assert len(build_called) == 0

        TemplateRegistry.set_skip_builds(False)

    def test_register_build_step_failure(self, monkeypatch):
        """Test that build step failure raises error."""
        from kubeman.kubernetes import KubernetesResource

        TemplateRegistry.clear()

        class TestResource(KubernetesResource):
            def __init__(self):
                super().__init__()
                self.name = "test-resource"
                self.namespace = "default"

            def build(self):
                raise RuntimeError("Build failed")

            def render(self):
                pass

        with pytest.raises(RuntimeError, match="Build step failed for template"):
            TemplateRegistry.register(TestResource)

    def test_register_no_build_method(self, monkeypatch):
        """Test that templates without build() method work normally."""
        from kubeman.kubernetes import KubernetesResource

        @TemplateRegistry.register
        class TestResource(KubernetesResource):
            def __init__(self):
                super().__init__()
                self.name = "test-resource"
                self.namespace = "default"

            def render(self):
                pass

        templates = TemplateRegistry.get_registered_templates()
        assert len(templates) == 1
        assert TestResource in templates
