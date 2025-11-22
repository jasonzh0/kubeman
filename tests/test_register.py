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

        # Should be different objects
        assert templates1 is not templates2
        # But should have same content
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
