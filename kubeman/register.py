import logging
from typing import List, Type, Dict, Callable, Optional
from kubeman.template import Template
from kubeman.chart import HelmChart
from kubeman.kubernetes import KubernetesResource

logger = logging.getLogger(__name__)


class TemplateRegistry:
    """
    Registry for managing template classes.

    Provides registration, filtering, and grouping capabilities for templates.
    """

    _templates: List[Type[Template]] = []
    _skip_builds: bool = False
    _skip_loads: bool = False

    @classmethod
    def set_skip_builds(cls, skip: bool) -> None:
        """
        Set whether build steps should be skipped during registration.

        Args:
            skip: If True, build steps will be skipped
        """
        cls._skip_builds = skip

    @classmethod
    def set_skip_loads(cls, skip: bool) -> None:
        """
        Set whether load steps should be skipped during registration.

        Args:
            skip: If True, load steps will be skipped
        """
        cls._skip_loads = skip

    @classmethod
    def _has_custom_build(cls, template_class: Type[Template]) -> bool:
        """
        Check if a template class has a custom build() method implementation.

        Args:
            template_class: Template class to check

        Returns:
            True if the template has a custom build() method, False otherwise
        """
        build_method = getattr(template_class, "build", None)
        if build_method is None:
            return False

        base_build_method = getattr(Template, "build", None)
        if base_build_method is None:
            return True

        return build_method is not base_build_method

    @classmethod
    def _has_custom_load(cls, template_class: Type[Template]) -> bool:
        """
        Check if a template class has a custom load() method implementation.

        Args:
            template_class: Template class to check

        Returns:
            True if the template has a custom load() method, False otherwise
        """
        load_method = getattr(template_class, "load", None)
        if load_method is None:
            return False

        base_load_method = getattr(Template, "load", None)
        if base_load_method is None:
            return True

        return load_method is not base_load_method

    @classmethod
    def register(cls, template_class: Type[Template]) -> Type[Template]:
        """
        Register a template class.
        Can be used as a decorator or called directly.

        If the template has a build() method, it will be executed sequentially
        during registration (unless builds are skipped). If the template has a
        load() method, it will be executed after build steps (unless loads are skipped).

        Args:
            template_class: Template class to register

        Returns:
            The registered template class
        """
        if template_class not in cls._templates:
            cls._templates.append(template_class)

            if not cls._skip_builds and cls._has_custom_build(template_class):
                try:
                    logger.info(f"Executing build step for template: {template_class.__name__}")
                    template_instance = template_class()
                    template_instance.build()
                    logger.info(f"✓ Build step completed for template: {template_class.__name__}")
                except Exception as e:
                    logger.error(
                        f"✗ Build step failed for template {template_class.__name__}: {e}",
                        exc_info=True,
                    )
                    raise RuntimeError(
                        f"Build step failed for template {template_class.__name__}: {e}"
                    ) from e

            if not cls._skip_loads and cls._has_custom_load(template_class):
                try:
                    logger.info(f"Executing load step for template: {template_class.__name__}")
                    template_instance = template_class()
                    template_instance.load()
                    logger.info(f"✓ Load step completed for template: {template_class.__name__}")
                except Exception as e:
                    logger.error(
                        f"✗ Load step failed for template {template_class.__name__}: {e}",
                        exc_info=True,
                    )
                    raise RuntimeError(
                        f"Load step failed for template {template_class.__name__}: {e}"
                    ) from e

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
            instance = template_class()
            return instance.namespace
        except Exception:
            return None
