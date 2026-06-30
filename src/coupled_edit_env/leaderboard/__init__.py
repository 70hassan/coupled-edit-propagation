"""Leaderboard infrastructure: model adapters and rollout runner."""

from coupled_edit_env.leaderboard.adapters import (
    ModelAdapter,
    NoopBaseline,
    GoldBaseline,
    PartialBaseline,
    OpenAIAdapter,
    AnthropicAdapter,
    OpenRouterAdapter,
)
from coupled_edit_env.leaderboard.runner import run_leaderboard, LeaderboardReport

__all__ = [
    "ModelAdapter",
    "NoopBaseline",
    "GoldBaseline",
    "PartialBaseline",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "OpenRouterAdapter",
    "run_leaderboard",
    "LeaderboardReport",
]
