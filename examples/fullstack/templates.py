"""
Templates for fullstack TODO application deployment.

This file imports template modules to trigger registration via @TemplateRegistry.register decorators.

Usage:
    # From the examples/fullstack directory:
    kubeman render
    kubeman apply

    # Or with explicit path from project root:
    kubeman render --file examples/fullstack/templates.py
    kubeman apply --file examples/fullstack/templates.py
"""

import sys
from pathlib import Path

# Add the examples/fullstack directory to the path so we can import the template modules
_fullstack_dir = Path(__file__).parent
if str(_fullstack_dir) not in sys.path:
    sys.path.insert(0, str(_fullstack_dir))

# Import template classes to trigger registration via @TemplateRegistry.register decorators
# These imports cause the decorators to execute and register the templates
# Order matters: database first, then backend, then frontend
import postgres_db  # noqa: F401
import backend  # noqa: F401
import frontend  # noqa: F401
