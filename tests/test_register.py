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

    def test_register_does_not_build(self, monkeypatch):
        """Registration must NOT execute build() (no import-time side effects)."""
        from kubeman.kubernetes import KubernetesResource

        TemplateRegistry.clear()

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

        assert build_called == []

    def test_run_build_steps_executes_build(self, monkeypatch):
        """Test that build() runs when run_build_steps() is called."""
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

        TemplateRegistry.run_build_steps()
        assert build_called == [True]

    def test_run_build_steps_skips_build_when_skipped(self, monkeypatch):
        """Test that build() is skipped when skip_builds is True."""
        from kubeman.kubernetes import KubernetesResource

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

        TemplateRegistry.run_build_steps(skip_builds=True)
        assert build_called == []

    def test_run_build_steps_build_failure(self, monkeypatch):
        """Test that a build step failure raises a clear error."""
        from kubeman.kubernetes import KubernetesResource

        TemplateRegistry.clear()

        @TemplateRegistry.register
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
            TemplateRegistry.run_build_steps()

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
