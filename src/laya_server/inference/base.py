"""The inference-engine seam.

Everything above this Protocol (routing, validation, model resolution, auth,
the worker pool) is real; only what happens inside ``predict`` is swapped — a
deterministic ``FakeEngine`` in CI, the real Laya engine on GPU machines. This
is the single substitution seam for the whole service (see the ADRs).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from laya_server.schemas.jev import Answer, JSONContent, Question


@dataclass(frozen=True)
class PredictResult:
    """A completed inference: one answer per question, plus input token count."""

    answers: dict[str, Answer]
    input_tokens: int


@runtime_checkable
class DecisionEngine(Protocol):
    """Computes typed decisions for a State against a set of Questions."""

    def is_ready(self) -> bool:
        """Whether the engine is loaded and able to serve requests."""
        ...

    def predict(
        self, state: JSONContent, questions: dict[str, Question]
    ) -> PredictResult:
        """Answer every question about ``state`` in a single call."""
        ...
