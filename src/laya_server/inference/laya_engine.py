"""The real inference engine, backed by the Laya decision engine.

``laya`` (and its torch/transformers stack) is an optional dependency: install
``laya-server[laya]``. It is imported lazily inside :meth:`load` so the base
install and CI stay lean and never import torch.
"""

from __future__ import annotations

from typing import Any

from laya_server.inference.base import PredictResult
from laya_server.inference.translate import to_jev_answer, to_laya_question
from laya_server.schemas.jev import Answer, JSONContent, Question

# Default Laya checkpoint (the English root of the bundled repo).
DEFAULT_CHECKPOINT = "convaiinnovations/laya"


class LayaEngine:
    """A ``DecisionEngine`` backed by ``laya.load(...)`` / ``agent.predict(...)``."""

    def __init__(
        self,
        checkpoint: str = DEFAULT_CHECKPOINT,
        device: str | None = None,
        subfolder: str | None = None,
        agent: Any = None,
    ) -> None:
        self._checkpoint = checkpoint
        self._device = device
        self._subfolder = subfolder
        # An injected agent (used by tests) is treated as already loaded.
        self._agent = agent

    def load(self) -> None:
        """Load the Laya checkpoint. Device auto-detects CUDA/MPS/CPU when unset."""
        if self._agent is not None:
            return
        try:
            import laya
        except (
            ImportError
        ) as error:  # pragma: no cover - exercised only without the extra
            raise RuntimeError(
                "The 'laya' package is required for the Laya engine. "
                "Install it with: pip install 'laya-server[laya]'."
            ) from error
        self._agent = laya.load(
            self._checkpoint, device=self._device, subfolder=self._subfolder
        )

    def is_ready(self) -> bool:
        return self._agent is not None

    def predict(
        self, state: JSONContent, questions: dict[str, Question]
    ) -> PredictResult:
        if self._agent is None:
            raise RuntimeError("LayaEngine.load() must be called before predict().")
        laya_questions = {
            name: to_laya_question(question) for name, question in questions.items()
        }
        result = self._agent.predict(state, laya_questions)
        answers: dict[str, Answer] = {
            name: to_jev_answer(answer) for name, answer in result["answers"].items()
        }
        # Laya always reports tokenizer-derived usage; fail loud if it doesn't.
        input_tokens = int(result["usage"]["input_tokens"])
        return PredictResult(answers=answers, input_tokens=input_tokens)
