from typing import List, Type, Dict, Callable, Optional
from kubeman.template import Template
from kubeman.chart import HelmChart
from kubeman.kubernetes import KubernetesResource


class TemplateRegistry:
    """
    Registry for managing template classes.

    Provides registration, filtering, and grouping capabilities for templates.
    """

    _templates: List[Type[Template]] = []

    @classmethod
    def register(cls, template_class: Type[Template]) -> Type[Template]:
        """
        Register a template class.
        Can be used as a decorator or called directly.

        Args:
            template_class: Template class to register

        Returns:
            The registered template class
        """
        if template_class not in cls._templates:
            cls._templates.append(template_class)
        return template_class

    @classmethod
    def get_registered_templates(cls) -> List[Type[Template]]:
        """
        Return all registered templates.

        Returns:
            List of registered template classes
        """
        return cls._templates.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered templates."""
        cls._templates.clear()

    @classmethod
    def get_by_namespace(cls, namespace: str) -> List[Type[Template]]:
        """
        Get all templates for a specific namespace.

        Args:
            namespace: Namespace to filter by

        Returns:
            List of template classes matching the namespace
        """
        return [
            template_class
            for template_class in cls._templates
            if cls._get_template_namespace(template_class) == namespace
        ]

    @classmethod
    def get_by_type(cls, template_type: Type[Template]) -> List[Type[Template]]:
        """
        Get all templates of a specific type.

        Args:
            template_type: Template type to filter by (e.g., HelmChart, KubernetesResource)

        Returns:
            List of template classes of the specified type
        """
        return [
            template_class
            for template_class in cls._templates
            if issubclass(template_class, template_type)
        ]

    @classmethod
    def filter(cls, predicate: Callable[[Type[Template]], bool]) -> List[Type[Template]]:
        """
        Filter templates using a custom predicate function.

        Args:
            predicate: Function that takes a template class and returns True to include it

        Returns:
            List of template classes matching the predicate
        """
        return [template_class for template_class in cls._templates if predicate(template_class)]

    @classmethod
    def group_by_namespace(cls) -> Dict[str, List[Type[Template]]]:
        """
        Group templates by namespace.

        Returns:
            Dictionary mapping namespace to list of template classes
        """
        grouped: Dict[str, List[Type[Template]]] = {}
        for template_class in cls._templates:
            namespace = cls._get_template_namespace(template_class)
            if namespace not in grouped:
                grouped[namespace] = []
            grouped[namespace].append(template_class)
        return grouped

    @classmethod
    def group_by_type(cls) -> Dict[str, List[Type[Template]]]:
        """
        Group templates by type (HelmChart vs KubernetesResource).

        Returns:
            Dictionary mapping type name to list of template classes
        """
        grouped: Dict[str, List[Type[Template]]] = {
            "HelmChart": [],
            "KubernetesResource": [],
            "Other": [],
        }
        for template_class in cls._templates:
            if issubclass(template_class, HelmChart):
                grouped["HelmChart"].append(template_class)
            elif issubclass(template_class, KubernetesResource):
                grouped["KubernetesResource"].append(template_class)
            else:
                grouped["Other"].append(template_class)
        return grouped

    @classmethod
    def _get_template_namespace(cls, template_class: Type[Template]) -> Optional[str]:
        """
        Get the namespace from a template class instance.

        Args:
            template_class: Template class

        Returns:
            Namespace string or None if unable to determine
        """
        try:
            # Create a temporary instance to get the namespace
            # This is safe because namespace is a required property
            instance = template_class()
            return instance.namespace
        except Exception:
            # If we can't instantiate or get namespace, return None
            return None
