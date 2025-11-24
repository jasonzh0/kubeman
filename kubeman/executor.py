"""
Command execution abstraction for consistent subprocess handling.

Provides a unified interface for executing shell commands with consistent
error handling, logging, and retry logic.
"""

import subprocess
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from kubeman.output import get_output

logger = logging.getLogger(__name__)


class CommandExecutor:
    """
    Abstraction for executing shell commands with consistent error handling.

    Provides a unified interface for subprocess calls across the codebase,
    making it easier to test, mock, and extend command execution behavior.
    """

    def __init__(self, check: bool = True, capture_output: bool = False, text: bool = True):
        """
        Initialize the command executor.

        Args:
            check: If True, raise CalledProcessError on non-zero exit codes
            capture_output: If True, capture stdout and stderr
            text: If True, return strings instead of bytes
        """
        self.check = check
        self.capture_output = capture_output
        self.text = text

    def run(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        check: Optional[bool] = None,
        capture_output: Optional[bool] = None,
        text: Optional[bool] = None,
        input: Optional[str] = None,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        """
        Execute a command and return the result.

        Args:
            cmd: Command to execute as a list of strings
            cwd: Working directory for the command
            env: Environment variables to set
            check: Override default check behavior
            capture_output: Override default capture_output behavior
            text: Override default text behavior
            input: Input to send to stdin
            **kwargs: Additional arguments to pass to subprocess.run

        Returns:
            CompletedProcess instance with stdout, stderr, and returncode

        Raises:
            subprocess.CalledProcessError: If check=True and command fails
            FileNotFoundError: If command executable is not found
        """
        # Use instance defaults if not overridden
        check = check if check is not None else self.check
        capture_output = capture_output if capture_output is not None else self.capture_output
        text = text if text is not None else self.text

        # Convert Path to string for cwd
        cwd_str = str(cwd) if cwd else None
        output = get_output()

        logger.debug(f"Executing command: {' '.join(cmd)}")
        output.verbose(f"Executing: {' '.join(cmd)}")
        if cwd_str:
            logger.debug(f"Working directory: {cwd_str}")
            output.verbose(f"Working directory: {cwd_str}")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd_str,
                env=env,
                check=check,
                capture_output=capture_output,
                text=text,
                input=input,
                **kwargs,
            )
            logger.debug(f"Command completed with return code: {result.returncode}")
            output.verbose(f"Command completed with return code: {result.returncode}")
            if result.stdout and output.verbosity.value >= 2:
                output.verbose(f"Stdout: {result.stdout}")
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"Return code: {e.returncode}")
            output.error(
                f"Command failed: {' '.join(cmd)}",
                suggestion=f"Return code: {e.returncode}. Check command syntax and permissions.",
            )
            if e.stderr:
                logger.error(f"Stderr: {e.stderr}")
                output.verbose(f"Stderr: {e.stderr}")
            if e.stdout:
                output.verbose(f"Stdout: {e.stdout}")
            raise
        except FileNotFoundError as e:
            logger.error(f"Command not found: {cmd[0]}")
            output.error(
                f"Command not found: {cmd[0]}",
                suggestion=f"Ensure {cmd[0]} is installed and available in your PATH",
            )
            raise

    def run_silent(
        self,
        cmd: List[str],
        cwd: Optional[Path] = None,
        **kwargs: Any,
    ) -> subprocess.CompletedProcess:
        """
        Execute a command silently (captures output, doesn't log).

        Args:
            cmd: Command to execute
            cwd: Working directory
            **kwargs: Additional arguments

        Returns:
            CompletedProcess instance
        """
        return self.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            check=False,
            **kwargs,
        )


# Default executor instance for convenience
_default_executor = CommandExecutor()


def get_executor() -> CommandExecutor:
    """
    Get the default command executor instance.

    Returns:
        Default CommandExecutor instance
    """
    return _default_executor
