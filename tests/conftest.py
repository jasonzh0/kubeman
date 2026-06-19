"""Pytest configuration and shared fixtures."""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from kubeman.register import TemplateRegistry


@pytest.fixture(autouse=True)
def reset_template_registry():
    """
    Isolate the global TemplateRegistry between tests.

    TemplateRegistry keeps class-level mutable state (the list of registered
    templates and the _skip_builds/_skip_loads flags). Without this fixture a
    test that registers templates or flips a skip flag leaks that state into
    every subsequent test, making the suite order-dependent. Snapshot the
    state before each test and restore it afterwards.
    """
    saved_templates = list(TemplateRegistry._templates)
    saved_skip_builds = TemplateRegistry._skip_builds
    saved_skip_loads = TemplateRegistry._skip_loads
    try:
        yield
    finally:
        TemplateRegistry._templates[:] = saved_templates
        TemplateRegistry._skip_builds = saved_skip_builds
        TemplateRegistry._skip_loads = saved_skip_loads
