# Jev / System One contract

A **System One** call evaluates one **State** against a set of **Questions** in a
single forward pass and returns one **Answer** per Question. The wire contract is
TypeSafe's Jev API; this page describes the shape `whatdo` implements.

## Request — `POST /v1/systemone`

```json
{
  "state": "I was charged twice.",
  "model": "jev-latest",
  "questions": {
    "billing": {"type": "noul", "instructions": "Is this about billing?"},
    "tone":    {"type": "choice", "instructions": "Tone?",
                "criteria": {"angry": null, "calm": null}},
    "urgency": {"type": "score", "instructions": "How urgent?",
                "criteria": ["low", "medium", "high"]}
  }
}
```

- **`state`** — the content under evaluation. May be text, an object, or a list.
- **`model`** — the requested **Model** id. It is resolved to the deployment's
  **Served Model**; `jev-latest` / `jev-preview` always resolve via a built-in
  shim, and other ids resolve through the optional **Alias Table**. A model that
  does not resolve is rejected with `422`.
- **`questions`** — a named map of **Question**s (at least one). Each is one of
  three types, distinguished by `type`:

| Type | `criteria` | Answer carries |
| ---- | ---------- | -------------- |
| `noul` | optional `{true, false}` descriptions | `noul` — a probability 0–1 |
| `choice` | a map of option → optional description | `choice`, `confidence`, `probabilities` |
| `score` | an ordered list of ≥1 rubric levels | `score`, `confidence`, `legend`, `probabilities` |

Unknown fields *inside* a Question are rejected (`422`); unknown *top-level*
fields are ignored for forward-compatibility with newer SDKs.

## Response

```json
{
  "model": "auto",
  "answers": {
    "billing": {"type": "noul", "noul": 0.26},
    "tone":    {"type": "choice", "choice": "calm", "confidence": 0.61,
                "probabilities": {"angry": 0.39, "calm": 0.61}},
    "urgency": {"type": "score", "score": 1.2, "confidence": 0.44,
                "legend": {"0": "low", "1": "medium", "2": "high"},
                "probabilities": {"0": 0.2, "1": 0.4, "2": 0.4}}
  },
  "usage": {"input_tokens": 30, "output_tokens": 0}
}
```

- **`model`** echoes the concrete resolved **Served Model** id, so a client can
  pin to it on subsequent calls.
- **`answers`** mirrors the request's Question names, one typed **Answer** each.
- A **Choice**/**Score** Answer includes a **Confidence** — a 0–1 certainty
  derived from its probability distribution.

### `usage.output_tokens` is always `0`

**Usage** reports token accounting for the call. It carries `input_tokens`, but
`output_tokens` is **always `0`** — and that is deliberate, not a placeholder:

!!! note "A deliberate contract quirk"
    Laya is **non-autoregressive**: a System One call is a single forward pass
    that emits typed decisions, not a generated token stream. There are no output
    tokens to count, so `output_tokens` is fixed at `0`. The field is kept in the
    response for Jev-API shape compatibility.

## Error envelope

Errors use the Jev-compatible `{"detail": ...}` shape (the same the official SDK
reads):

| Status | When |
| ------ | ---- |
| `401` | Auth enabled and the bearer token is missing or invalid. |
| `422` | Request validation failed, or the requested **Model** is not served. |
| `529` | Overload — the worker pool's bounded queue is saturated (or a request aged out). Retryable; the official SDK backs off and retries. |

## Schemas

The request/response models are generated from the server's own Pydantic
schemas.

::: whatdo.schemas.jev.SystemOneRequest

::: whatdo.schemas.jev.SystemOneResponse

::: whatdo.schemas.jev.Usage
