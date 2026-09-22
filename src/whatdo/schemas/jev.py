"""Pydantic models mirroring the Jev API wire contract (``POST /v1/systemone``).

These are the server's own models, independent of the client SDK. They are kept
faithful to the API's OpenAPI schema so the official ``typesafe-sdk-python`` can
serialize requests to, and strictly validate responses from, this server.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# State, instructions, and criteria descriptions may be text, an object, or a list.
JSONContent = str | dict[str, Any] | list[Any]


# --------------------------------------------------------------------------- #
# Request: questions                                                          #
# --------------------------------------------------------------------------- #
class _Question(BaseModel):
    # Question objects are strict: unknown fields are rejected (422).
    model_config = ConfigDict(extra="forbid")


class NoulCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    true: JSONContent | None = None
    false: JSONContent | None = None


class NoulQuestion(_Question):
    """A calibrated yes/no (boolean) question."""

    type: Literal["noul"] = "noul"
    instructions: JSONContent | None = None
    criteria: NoulCriteria | None = None


class ChoiceQuestion(_Question):
    """Select one option from a named set."""

    type: Literal["choice"] = "choice"
    instructions: JSONContent | None = None
    criteria: dict[str, JSONContent | None]


class ScoreQuestion(_Question):
    """Rate on an ordered rubric. The Jev API requires at least one level."""

    type: Literal["score"] = "score"
    instructions: JSONContent | None = None
    criteria: list[JSONContent] = Field(min_length=1)


Question = Annotated[
    NoulQuestion | ChoiceQuestion | ScoreQuestion, Field(discriminator="type")
]


class SystemOneRequest(BaseModel):
    # Unknown top-level fields are accepted and ignored (SDK `extra_body`
    # forward-compat). `protected_namespaces=()` allows the `model` field.
    model_config = ConfigDict(extra="ignore", protected_namespaces=())

    state: JSONContent
    model: str
    questions: dict[str, Question] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Response: answers                                                           #
# --------------------------------------------------------------------------- #
class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float


class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    confidence: float
    probabilities: dict[str, float]


class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    confidence: float
    legend: dict[str, JSONContent]
    probabilities: dict[str, float]


Answer = Annotated[NoulAnswer | ChoiceAnswer | ScoreAnswer, Field(discriminator="type")]


class Usage(BaseModel):
    input_tokens: int
    # Non-autoregressive engine: no generated tokens (see CONTEXT.md / ADRs).
    output_tokens: int = 0


class SystemOneResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model: str
    answers: dict[str, Answer] = Field(min_length=1)
    usage: Usage


# --------------------------------------------------------------------------- #
# GET /v1/models                                                             #
# --------------------------------------------------------------------------- #
class ModelMetadata(BaseModel):
    name: str
    description: str
    release_date: str


class ModelsResponse(BaseModel):
    models: list[ModelMetadata]
