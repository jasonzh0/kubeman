from typing import List, Type
from kubeman.chart import HelmChart


class ChartRegistry:
    _charts: List[Type[HelmChart]] = []

    @classmethod
    def register(cls, chart_class: Type[HelmChart]) -> Type[HelmChart]:
        """
        Register a HelmChart class.
        Can be used as a decorator or called directly.
        """
        if chart_class not in cls._charts:
            cls._charts.append(chart_class)
        return chart_class

    @classmethod
    def get_registered_charts(cls) -> List[Type[HelmChart]]:
        """Return all registered chart classes"""
        return cls._charts.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered charts"""
        cls._charts.clear()
