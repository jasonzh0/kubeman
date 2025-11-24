"""
Output utility for kubeman CLI with colors, progress indicators, and verbosity control.

Provides a centralized output manager using Rich library for professional
CLI output with colors, progress bars, spinners, and formatted messages.
"""

from enum import IntEnum
from typing import Optional, List, Dict, Any, Iterator, ContextManager
from contextlib import contextmanager

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box


class Verbosity(IntEnum):
    """Verbosity levels for output."""

    QUIET = 0  # Only errors and final results
    NORMAL = 1  # Standard output with colors
    VERBOSE = 2  # Detailed output including file paths, command execution


class OutputManager:
    """
    Centralized output manager for kubeman CLI.

    Provides methods for formatted output with colors, progress indicators,
    and verbosity control.
    """

    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL):
        """
        Initialize the output manager.

        Args:
            verbosity: Verbosity level for output
        """
        self.verbosity = verbosity
        self.console = Console()
        self.error_console = Console(stderr=True)
        self._progress: Optional[Progress] = None
        self._current_progress: Optional[Progress] = None

    def set_verbosity(self, verbosity: Verbosity) -> None:
        """Set the verbosity level."""
        self.verbosity = verbosity

    def success(self, message: str) -> None:
        """Print a success message in green."""
        if self.verbosity != Verbosity.QUIET:
            self.console.print(f"[green]✓[/green] {message}")

    def error(self, message: str, suggestion: Optional[str] = None) -> None:
        """Print an error message in red to stderr."""
        # Also output plain text format for backwards compatibility with tests
        error_text = f"✗ {message}"
        self.error_console.print(f"[red]{error_text}[/red]", style="red")
        if suggestion and self.verbosity >= Verbosity.NORMAL:
            self.error_console.print(f"[yellow]💡 {suggestion}[/yellow]", style="yellow")

    def warning(self, message: str) -> None:
        """Print a warning message in yellow."""
        if self.verbosity != Verbosity.QUIET:
            self.console.print(f"[yellow]⚠[/yellow] {message}", style="yellow")

    def info(self, message: str) -> None:
        """Print an info message in blue."""
        if self.verbosity >= Verbosity.NORMAL:
            self.console.print(f"[blue]ℹ[/blue] {message}", style="blue")

    def print(self, message: str, style: Optional[str] = None) -> None:
        """Print a plain message."""
        if self.verbosity != Verbosity.QUIET:
            self.console.print(message, style=style)

    def verbose(self, message: str) -> None:
        """Print a verbose message (only shown in VERBOSE mode)."""
        if self.verbosity >= Verbosity.VERBOSE:
            self.console.print(f"[dim]{message}[/dim]", style="dim")

    def section(self, title: str) -> None:
        """Print a section header."""
        if self.verbosity != Verbosity.QUIET:
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]")

    def panel(self, content: str, title: Optional[str] = None, border_style: str = "blue") -> None:
        """Print content in a panel."""
        if self.verbosity != Verbosity.QUIET:
            self.console.print(Panel(content, title=title, border_style=border_style))

    def table(
        self,
        title: str,
        columns: List[str],
        rows: List[List[str]],
        show_header: bool = True,
    ) -> None:
        """Print a table."""
        if self.verbosity != Verbosity.QUIET:
            table = Table(title=title, show_header=show_header, box=box.ROUNDED)
            for col in columns:
                table.add_column(col)
            for row in rows:
                table.add_row(*row)
            self.console.print(table)

    @contextmanager
    def progress(self, description: str, total: int = 0) -> Iterator[Optional[Progress]]:
        """
        Context manager for progress bars.

        Args:
            description: Description of the operation
            total: Total number of items (0 for indeterminate)

        Yields:
            Progress instance for updating progress (None in quiet mode)
        """
        if self.verbosity == Verbosity.QUIET:
            # In quiet mode, don't show progress
            yield None
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
            transient=False,
        ) as progress:
            task_id = progress.add_task(description, total=total)
            self._current_progress = progress
            try:
                yield progress
            finally:
                self._current_progress = None

    def update_progress(
        self, task_id: TaskID, advance: int = 1, description: Optional[str] = None
    ) -> None:
        """Update progress for a task."""
        if self._current_progress:
            self._current_progress.update(task_id, advance=advance, description=description)

    @contextmanager
    def spinner(self, message: str) -> Iterator[None]:
        """
        Context manager for spinner (indeterminate progress).

        Args:
            message: Message to display with spinner

        Yields:
            None
        """
        if self.verbosity == Verbosity.QUIET:
            yield
            return

        with self.console.status(f"[cyan]{message}[/cyan]"):
            yield

    def rule(self, title: Optional[str] = None) -> None:
        """Print a horizontal rule."""
        if self.verbosity != Verbosity.QUIET:
            self.console.rule(title)

    def newline(self) -> None:
        """Print a newline."""
        if self.verbosity != Verbosity.QUIET:
            self.console.print()


# Global output manager instance
_output_manager: Optional[OutputManager] = None


def get_output() -> OutputManager:
    """
    Get the global output manager instance.

    Returns:
        OutputManager instance
    """
    global _output_manager
    if _output_manager is None:
        _output_manager = OutputManager()
    return _output_manager


def set_output(manager: OutputManager) -> None:
    """Set the global output manager instance."""
    global _output_manager
    _output_manager = manager
