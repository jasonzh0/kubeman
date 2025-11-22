# Kubeman

A Python library for rendering Helm charts and ArgoCD applications.

## Features

- Abstract base class for defining Helm charts
- Chart registry for managing multiple charts
- Git operations for manifest repository management
- Docker image build and push utilities
- Settings management for environment configuration

## Installation

Using `uv` (recommended):

```bash
uv pip install -e .
```

Or using `pip`:

```bash
pip install -e .
```

## Development

Install development dependencies:

```bash
uv sync --dev
```

Format code:

```bash
uv tool run black .
```

## Usage

```python
from kubeman import HelmChart, ChartRegistry

@ChartRegistry.register
class MyChart(HelmChart):
    @property
    def name(self) -> str:
        return "my-chart"
    
    # ... implement required abstract methods
```

## License

MIT

