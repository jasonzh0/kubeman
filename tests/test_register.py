"""Unit tests for ChartRegistry."""
import pytest
from kubeman.register import ChartRegistry
from kubeman.chart import HelmChart


class TestChartRegistry:
    """Test cases for ChartRegistry class."""

    def setup_method(self):
        """Clear registry before each test."""
        ChartRegistry.clear()

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

        ChartRegistry.register(TestChart)
        charts = ChartRegistry.get_registered_charts()
        assert len(charts) == 1
        assert TestChart in charts

    def test_register_as_decorator(self):
        """Test using register as a decorator."""

        @ChartRegistry.register
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

        charts = ChartRegistry.get_registered_charts()
        assert len(charts) == 1
        assert TestChart in charts

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

        ChartRegistry.register(TestChart)
        ChartRegistry.register(TestChart)
        charts = ChartRegistry.get_registered_charts()
        assert len(charts) == 1

    def test_get_registered_charts_returns_copy(self):
        """Test that get_registered_charts returns a copy."""

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

        ChartRegistry.register(TestChart)
        charts1 = ChartRegistry.get_registered_charts()
        charts2 = ChartRegistry.get_registered_charts()

        # Should be different objects
        assert charts1 is not charts2
        # But should have same content
        assert charts1 == charts2

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

        ChartRegistry.register(TestChart)
        assert len(ChartRegistry.get_registered_charts()) == 1

        ChartRegistry.clear()
        assert len(ChartRegistry.get_registered_charts()) == 0
