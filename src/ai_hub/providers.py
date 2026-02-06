"""AI provider implementations."""

import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProviderResponse:
    """Response from an AI provider."""

    text: str
    session_id: str | None = None
    model: str | None = None
    cost_usd: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(ABC):
    """Base class for AI providers."""

    @abstractmethod
    def send(
        self,
        message: str,
        files: list[Path] | None = None,
        session_id: str | None = None,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        allowed_tools: tuple[str, ...] | None = None,
        add_dirs: list[str] | None = None,
        permission_mode: str | None = None,
    ) -> ProviderResponse:
        """Send a message and return a ProviderResponse."""


class ClaudeCodeProvider(Provider):
    """Claude Code CLI provider.

    Uses the local Claude Code installation, which authenticates
    through the user's Max/Pro plan subscription. No separate API
    key is required.
    """

    def __init__(self, default_tools: tuple[str, ...] = ("Read",)) -> None:
        self._default_tools = default_tools

    def send(
        self,
        message: str,
        files: list[Path] | None = None,
        session_id: str | None = None,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        allowed_tools: tuple[str, ...] | None = None,
        add_dirs: list[str] | None = None,
        permission_mode: str | None = None,
    ) -> ProviderResponse:
        tools = allowed_tools if allowed_tools is not None else self._default_tools
        prompt = self._build_prompt(message, files)
        cmd = self._build_command(
            session_id, model, system_prompt, tools, add_dirs, permission_mode
        )

        # Sanitize prompt to remove surrogate characters that can't be encoded
        # (common in PDF text extraction)
        prompt = prompt.encode("utf-8", errors="surrogatepass").decode(
            "utf-8", errors="replace"
        )

        # Pass prompt via stdin to avoid shell escaping issues with special
        # characters (e.g. prompts starting with '-' being parsed as options)
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for complex tasks
            )
        except subprocess.TimeoutExpired:
            return ProviderResponse(
                text="Request timed out after 10 minutes. The task may be too complex. "
                     "Try breaking it into smaller steps or simplifying the request.",
                session_id=session_id,
            )

        if result.returncode != 0:
            return ProviderResponse(
                text=f"Error: {result.stderr.strip()}",
                session_id=session_id,
            )

        return self._parse_response(result.stdout, session_id)

    def _build_prompt(self, message: str, files: list[Path] | None) -> str:
        if not files:
            return message

        refs = "\n".join(f"- {f.resolve()}" for f in files)
        return f"{message}\n\nReferenced files:\n{refs}"

    def _build_command(
        self,
        session_id: str | None,
        model: str | None,
        system_prompt: str | None,
        allowed_tools: tuple[str, ...],
        add_dirs: list[str] | None,
        permission_mode: str | None,
    ) -> list[str]:
        cmd = ["claude", "-p", "--output-format", "json"]

        if session_id:
            cmd.extend(["--resume", session_id])

        if model:
            cmd.extend(["--model", model])

        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        if add_dirs:
            cmd.extend(["--add-dir", *add_dirs])

        if permission_mode:
            cmd.extend(["--permission-mode", permission_mode])

        return cmd

    def _parse_response(
        self, stdout: str, fallback_session_id: str | None
    ) -> ProviderResponse:
        try:
            data = json.loads(stdout)
            text = data.get("result", stdout.strip())
            sid = data.get("session_id", fallback_session_id)
            cost = data.get("total_cost_usd")

            usage = data.get("usage", {})
            in_tokens = usage.get("input_tokens", 0)
            out_tokens = usage.get("output_tokens", 0)

            model_usage = data.get("modelUsage", {})
            model_name = next(iter(model_usage), None) if model_usage else None

            return ProviderResponse(
                text=text,
                session_id=sid,
                model=model_name,
                cost_usd=cost,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
        except json.JSONDecodeError:
            return ProviderResponse(
                text=stdout.strip(),
                session_id=fallback_session_id,
            )
