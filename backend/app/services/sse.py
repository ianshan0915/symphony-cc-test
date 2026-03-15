"""Shared SSE event type used by the agent service and deepagents adapter."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    """A Server-Sent Event to be streamed to the client.

    Used throughout the streaming pipeline:

    * ``deepagents_adapter`` creates SSEEvent instances from LangGraph chunks.
    * ``agent_service`` yields them (and creates additional ones for lifecycle
      events like ``message_start`` / ``message_end``).
    * ``chat.py`` encodes and streams them over HTTP.
    """

    event: str
    data: dict[str, Any] = field(default_factory=dict)

    def encode(self) -> str:
        """Encode as SSE wire format."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"
