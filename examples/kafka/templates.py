"""
Templates for Kafka deployment.

This file imports template modules to trigger registration via @TemplateRegistry.register decorators.

Usage:
    # From the examples/kafka directory:
    kubeman render
    kubeman apply

    # Or with explicit path:
    kubeman render --file examples/kafka/templates.py
    kubeman apply --file examples/kafka/templates.py
"""

import sys
from pathlib import Path

# Add the examples/kafka directory to the path so we can import the template modules
_kafka_dir = Path(__file__).parent
if str(_kafka_dir) not in sys.path:
    sys.path.insert(0, str(_kafka_dir))

# Import template classes to trigger registration via @TemplateRegistry.register decorators
# These imports cause the decorators to execute and register the templates
import kafka_example  # noqa: F401
import stock_price_producer  # noqa: F401
import stock_price_consumer  # noqa: F401
