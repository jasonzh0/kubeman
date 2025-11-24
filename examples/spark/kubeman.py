"""
Templates for Spark deployment.

This file imports template modules to trigger registration via @TemplateRegistry.register decorators.

Usage:
    # From the examples/spark directory:
    kubeman render
    kubeman apply

    # Or with explicit path from project root:
    kubeman render --file examples/spark/kubeman.py
    kubeman apply --file examples/spark/kubeman.py
"""

import sys
from pathlib import Path

# Add the examples/spark/templates directory to the path so we can import the template modules
_spark_templates_dir = Path(__file__).parent / "templates"
if str(_spark_templates_dir) not in sys.path:
    sys.path.insert(0, str(_spark_templates_dir))

# Import template classes to trigger registration via @TemplateRegistry.register decorators
# These imports cause the decorators to execute and register the templates
import spark_operator  # noqa: F401
import spark_application  # noqa: F401
import custom_pyspark_job  # noqa: F401
