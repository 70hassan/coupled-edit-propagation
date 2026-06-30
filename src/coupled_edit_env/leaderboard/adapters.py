"""
Model adapters for the capability-only leaderboard.

Two families of adapters:

1. Deterministic baselines (NoopBaseline, GoldBaseline, PartialBaseline) that
   require no API access. They produce the same answers a noop / partial / gold
   model would produce and let us validate the leaderboard pipeline end-to-end.

2. Real provider adapters (OpenAI, Anthropic, OpenRouter) that require an API
   key in the environment. They are lazily imported so the leaderboard runs
   even when those SDKs are not installed.

The adapter interface is intentionally tiny:
    class ModelAdapter:
        name: str
        provider: str
        def is_available(self) -> bool
        def generate(self, prompt: str, **kwargs) -> str
"""

import os
from abc import ABC, abstractmethod
from typing import Optional

from coupled_edit_env.gold_solutions import GOLD_SOLUTIONS
from coupled_edit_env.partial_solutions import PARTIAL_SOLUTIONS


class ModelAdapter(ABC):
    name: str
    provider: str

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def generate(self, prompt: str, task_id: Optional[str] = None, **kwargs) -> str:
        ...


class NoopBaseline(ModelAdapter):
    """Returns project files unchanged. Floor of the capability ladder."""

    name = "noop-baseline"
    provider = "deterministic"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, task_id: Optional[str] = None, **kwargs) -> str:
        from coupled_edit_env.environment import load_environment
        for split in ["train", "eval"]:
            for t in load_environment(split=split).tasks:
                if t.task_id == task_id:
                    blocks = []
                    for path, content in t.project_files.items():
                        blocks.append(f"--- {path} ---")
                        blocks.append(content)
                    return "\n".join(blocks)
        return ""


class GoldBaseline(ModelAdapter):
    """Returns the reference gold solution. Ceiling of the capability ladder."""

    name = "gold-baseline"
    provider = "deterministic"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, task_id: Optional[str] = None, **kwargs) -> str:
        return GOLD_SOLUTIONS.get(task_id, "")


class PartialBaseline(ModelAdapter):
    """Returns the partial reference solution. Middle of the ladder."""

    name = "partial-baseline"
    provider = "deterministic"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, task_id: Optional[str] = None, **kwargs) -> str:
        return PARTIAL_SOLUTIONS.get(task_id, "")


class OpenAIAdapter(ModelAdapter):
    """OpenAI API adapter. Requires OPENAI_API_KEY in environment."""

    provider = "openai"

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.name = f"openai/{model_name}"
        self.model_name = model_name

    def is_available(self) -> bool:
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def generate(self, prompt: str, task_id: Optional[str] = None, **kwargs) -> str:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return response.choices[0].message.content or ""


class AnthropicAdapter(ModelAdapter):
    """Anthropic API adapter. Requires ANTHROPIC_API_KEY in environment."""

    provider = "anthropic"

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        self.name = f"anthropic/{model_name}"
        self.model_name = model_name

    def is_available(self) -> bool:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def generate(self, prompt: str, task_id: Optional[str] = None, **kwargs) -> str:
        import anthropic
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=self.model_name,
            max_tokens=kwargs.get("max_tokens", 4096),
            temperature=kwargs.get("temperature", 0.0),
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in response.content if hasattr(block, "text")]
        return "".join(parts)


class OpenRouterAdapter(ModelAdapter):
    """OpenRouter API adapter. Requires OPENROUTER_API_KEY in environment.

    Useful because it gives access to many providers (Anthropic, OpenAI, Google,
    Meta, etc.) through one key and one endpoint.
    """

    provider = "openrouter"

    def __init__(self, model_name: str):
        self.name = f"openrouter/{model_name}"
        self.model_name = model_name

    def is_available(self) -> bool:
        if not os.environ.get("OPENROUTER_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def generate(self, prompt: str, task_id: Optional[str] = None, **kwargs) -> str:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 4096),
        )
        return response.choices[0].message.content or ""
