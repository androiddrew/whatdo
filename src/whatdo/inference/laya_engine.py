"""The real inference engine, backed by the Laya decision engine.

``laya`` (and its torch/transformers stack) ships with every install of whatdo
(ADR-0007). It is still imported lazily inside :meth:`load`, so importing the
app, building engines, and the fake-engine test suite never pay for torch.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from whatdo.inference.base import PredictResult
from whatdo.inference.translate import to_jev_answer, to_laya_question
from whatdo.schemas.jev import Answer, JSONContent, Question

logger = logging.getLogger(__name__)

# Default Laya checkpoint (the English root of the bundled repo).
DEFAULT_CHECKPOINT = "convaiinnovations/laya"

# laya imports transformers lazily inside ``laya.load``, and transformers
# resolves its tokenizer/model classes lazily on first use; neither is
# thread-safe, so pool workers loading concurrently on a cold process fail with
# e.g. "cannot import name 'AutoTokenizer'". The first successful load in the
# process therefore runs alone; once it has imported everything, the remaining
# copies load in parallel. It also means a checkpoint is downloaded only once.
_first_load_lock = threading.Lock()
_first_load_done = False


def resolves_to_mps(device: str | None) -> bool:
    """Whether ``laya.load`` would place a copy on Apple's MPS backend.

    Mirrors laya's device selection (explicit device, else CUDA, then MPS, then
    CPU; an unavailable accelerator falls back to CPU) without loading anything.
    Without torch installed nothing can load, so nothing is on MPS.
    """
    try:
        import torch
    except ImportError:  # pragma: no cover - broken install only
        return False
    mps_available = bool(torch.backends.mps.is_available())
    if device is None:
        return mps_available and not torch.cuda.is_available()
    return mps_available and torch.device(device).type == "mps"


def _load_agent(
    laya: Any, checkpoint: str, *, device: str | None, subfolder: str | None
) -> Any:
    """``laya.load``, with the process's first load serialized (see above)."""
    global _first_load_done
    with _first_load_lock:
        if not _first_load_done:
            agent = laya.load(checkpoint, device=device, subfolder=subfolder)
            # Only a successful load has imported everything; after a failure
            # the next caller retries alone.
            _first_load_done = True
            return agent
    return laya.load(checkpoint, device=device, subfolder=subfolder)


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
        except ImportError as error:  # pragma: no cover - broken install only
            raise RuntimeError(
                "The 'laya' package is missing, but it ships with whatdo; "
                "reinstall with: pip install --force-reinstall whatdo"
            ) from error
        logger.info(
            "Loading Laya checkpoint=%r device=%s subfolder=%r",
            self._checkpoint,
            self._device or "auto",
            self._subfolder,
        )
        started = time.perf_counter()
        self._agent = _load_agent(
            laya, self._checkpoint, device=self._device, subfolder=self._subfolder
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
