# laya-server

A FastAPI service that implements TypeSafe's Jev API contract over the local Laya decision engine, so the official `typesafe-sdk-python` can drive locally-served, non-autoregressive typed decisions.

## Language

### The Jev contract

**Jev API**:
The typed-decision request/response contract this service speaks, defined by TypeSafe. A client posts a *State* and a set of *Questions* and receives typed *Answers*.
_Avoid_: the protocol, the schema

**System One**:
The single decision operation: evaluate one *State* against a set of *Questions* in a single forward pass. Named for fast, intuitive ("System 1") thinking.
_Avoid_: predict, inference call, systemone (as prose)

**State**:
The content under evaluation. May be text, an object, or a list.
_Avoid_: input, prompt, document, payload

**Questions**:
A named set of *Question*s posed about a *State* in one *System One* call.
_Avoid_: schema, fields, prompts

**Question** (a.k.a. **Decision Primitive**):
One typed thing to decide about the *State*. Exactly three types exist — *Noul*, *Choice*, *Score*.
_Avoid_: field, task, prompt

**Noul**:
A *Question* type returning a calibrated boolean as a probability from 0 to 1.
_Avoid_: boolean, flag, yes/no

**Choice**:
A *Question* type that selects one option from a defined set, returning the chosen option, the full probability distribution, and a *Confidence*.
_Avoid_: category, enum, classification

**Score**:
A *Question* type that rates the *State* on an ordered rubric of at least two levels, returning a probability-weighted value and a *Confidence*.
_Avoid_: rating, rank, grade

**Criteria**:
What a *Question* is judged against: the option set for a *Choice*, or the ordered rubric levels for a *Score*.
_Avoid_: options, choices, rubric (in isolation)

**Answer**:
The typed result for one *Question*, mirroring that Question's type.
_Avoid_: result, output, response (for a single question)

**Confidence**:
A 0–1 certainty for a *Choice* or *Score* *Answer*, derived from its probability distribution.
_Avoid_: certainty, probability (when referring to Choice/Score confidence)

**Usage**:
Token accounting for a *System One* call. Carries `input_tokens`; `output_tokens` is always 0 because the engine is non-autoregressive and generates no tokens.
_Avoid_: tokens, cost, metering

### Models and the engine

**Laya**:
The local, non-autoregressive engine that computes decisions. The service's inference backend.
_Avoid_: the model, the backend, the runtime

**Model**:
A Jev-facing identifier a client requests (e.g. `jev-latest`, `jev-1.13.0`). What a caller names; not a concrete weight set.
_Avoid_: model name, version (interchangeably with Checkpoint)

**Checkpoint**:
A concrete Laya weight set that serves a *Model* (`laya`, `laya-multilingual`, `laya-typed-decisions`).
_Avoid_: model, weights, variant

**Served Model**:
The single *Model* a given deployment is configured to answer for. Requests resolving to anything else are rejected.
_Avoid_: active model, loaded model

**Auto** (a.k.a. **Router**):
Laya's automatic per-request *Checkpoint* selection, requested as the `auto` *Model*.
_Avoid_: automatic mode, dynamic model

**Alias Table**:
A configurable, feature-flagged mapping from additional *Model* ids to a *Served Model*. Distinct from the always-on `jev-latest`/`jev-preview` compatibility shim.
_Avoid_: model map, aliases (in isolation)
