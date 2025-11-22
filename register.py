from typing import List, Type
from kubeman.template import Template


class TemplateRegistry:
    _templates: List[Type[Template]] = []

    @classmethod
    def register(cls, template_class: Type[Template]) -> Type[Template]:
        """
        Register a template class.
        Can be used as a decorator or called directly.
        """
        if template_class not in cls._templates:
            cls._templates.append(template_class)
        return template_class

    @classmethod
    def get_registered_templates(cls) -> List[Type[Template]]:
        """Return all registered templates"""
        return cls._templates.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered templates"""
        cls._templates.clear()
