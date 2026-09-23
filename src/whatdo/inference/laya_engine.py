"""The real inference engine, backed by the Laya decision engine.

``laya`` (and its torch/transformers stack) is an optional dependency: install
``whatdo[laya]``. It is imported lazily inside :meth:`load` so the base
install and CI stay lean and never import torch.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from whatdo.inference.base import PredictResult
from whatdo.inference.translate import to_jev_answer, to_laya_question
from whatdo.schemas.jev import Answer, JSONContent, Question

logger = logging.getLogger(__name__)

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

    def __repr__(self) -> str:
        return (
            f"LayaEngine(checkpoint={self._checkpoint!r}, device={self._device!r}, "
            f"subfolder={self._subfolder!r})"
        )

    def load(self) -> None:
        """Load the Laya checkpoint. Device auto-detects CUDA/MPS/CPU when unset."""
        if self._agent is not None:
            logger.debug("Laya agent injected; skipping checkpoint load")
            return
        try:
            import laya
        except (
            ImportError
        ) as error:  # pragma: no cover - exercised only without the extra
            raise RuntimeError(
                "The 'laya' package is required for the Laya engine. "
                "Install it with: pip install 'whatdo[laya]'."
            ) from error
        logger.info(
            "Loading Laya checkpoint=%r device=%s subfolder=%r",
            self._checkpoint,
            self._device or "auto",
            self._subfolder,
        )
        started = time.perf_counter()
        self._agent = laya.load(
            self._checkpoint, device=self._device, subfolder=self._subfolder
        )
        # Laya auto-detects the device and may silently fall back to CPU, so
        # report what it actually resolved to.
        logger.info(
            "Loaded Laya checkpoint=%r on device=%s dtype=%s in %.1fs",
            self._checkpoint,
            getattr(self._agent, "device", "unknown"),
            getattr(self._agent, "dtype", "unknown"),
            time.perf_counter() - started,
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
        # The state may carry user data, so only the questions are logged.
        logger.debug("Laya predict: questions=%s", laya_questions)
        started = time.perf_counter()
        result = self._agent.predict(state, laya_questions)
        elapsed = time.perf_counter() - started
        answers: dict[str, Answer] = {
            name: to_jev_answer(answer) for name, answer in result["answers"].items()
        }
        # Laya always reports tokenizer-derived usage; fail loud if it doesn't.
        input_tokens = int(result["usage"]["input_tokens"])
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Laya predict done in %.1fms: input_tokens=%d answers=%s",
                elapsed * 1000,
                input_tokens,
                {name: answer.model_dump() for name, answer in answers.items()},
            )
        return PredictResult(answers=answers, input_tokens=input_tokens)
