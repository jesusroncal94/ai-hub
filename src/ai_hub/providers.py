"""AI provider implementations."""

import json
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class Provider(ABC):
    """Base class for AI providers."""

    @abstractmethod
    def send(self, message: str, files: list[Path] | None = None) -> str:
        """Send a message and return the response."""

    @abstractmethod
    def reset(self) -> None:
        """Reset conversation state."""


class ClaudeCodeProvider(Provider):
    """Claude Code CLI provider.

    Uses the local Claude Code installation, which authenticates
    through the user's Max/Pro plan subscription. No separate API
    key is required.
    """

    def __init__(self, allowed_tools: tuple[str, ...] = ("Read",)) -> None:
        self._allowed_tools = allowed_tools
        self._session_id: str | None = None

    def send(self, message: str, files: list[Path] | None = None) -> str:
        prompt = self._build_prompt(message, files)
        cmd = self._build_command(prompt)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"

        return self._parse_response(result.stdout)

    def reset(self) -> None:
        self._session_id = None

    def _build_prompt(self, message: str, files: list[Path] | None) -> str:
        if not files:
            return message

        refs = "\n".join(f"- {f.resolve()}" for f in files)
        return f"{message}\n\nReferenced files:\n{refs}"

    def _build_command(self, prompt: str) -> list[str]:
        cmd = ["claude", "-p", prompt, "--output-format", "json"]

        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        if self._allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self._allowed_tools)])

        return cmd

    def _parse_response(self, stdout: str) -> str:
        try:
            data = json.loads(stdout)
            self._session_id = data.get("session_id", self._session_id)
            return data.get("result", stdout.strip())
        except json.JSONDecodeError:
            return stdout.strip()
