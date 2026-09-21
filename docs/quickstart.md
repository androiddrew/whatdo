# Quickstart

## Run the server

The fastest way to a running server is the container image (see
[Deployment](deployment.md) for the full matrix):

```bash
docker run -p 8000:8000 git.runcible.io/androiddrew/laya-server:latest
```

Or run from a checkout for local development (uses the deterministic
`FakeEngine` by default, so no GPU or model download is needed):

```bash
make setup            # create the venv, install dev deps + the package
make run              # uvicorn on http://127.0.0.1:8000
```

Confirm it is serving:

```bash
curl -s localhost:8000/healthz   # {"status":"ok"}
curl -s localhost:8000/readyz    # {"status":"ready"}
```

## Drive it with the official SDK

`laya-server` speaks the Jev API, so the official `typesafe-sdk-python` works
against it unchanged — just point it at your deployment:

```bash
pip install typesafe-sdk
export TYPESAFE_BASE_URL=http://localhost:8000
export TYPESAFE_API_KEY=any-value      # required by the SDK; ignored in no-auth mode
```

```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

with TypeSafeClient() as client:
    response = client.system_one(
        state={"message": "I was charged twice. Please help."},
        questions={
            "billing": Noul(instructions="Is this about billing?"),
            "tone": Choice(
                instructions="What is the tone?",
                criteria={"angry": None, "calm": None},
            ),
            "urgency": Score(
                instructions="How urgent is this?",
                criteria=["low", "medium", "high"],
            ),
        },
    )

    print(response.nouls["billing"].noul)  # 0.0–1.0
    print(response.choices["tone"].choice)  # "angry" | "calm"
    print(response.scores["urgency"].score)  # probability-weighted level
    print(response.usage.input_tokens)  # token accounting
    print(response.usage.output_tokens)  # always 0 (see the contract)
```

The default requested **Model** (`jev-latest`) resolves to the deployment's
**Served Model** via the built-in compatibility shim, so an unconfigured client
works out of the box.

## Or call it directly

```bash
curl -s localhost:8000/v1/systemone \
  -H 'content-type: application/json' \
  -d '{
        "state": "I was charged twice.",
        "model": "jev-latest",
        "questions": {"billing": {"type": "noul", "instructions": "billing?"}}
      }'
```

See the [Jev / System One contract](contract.md) for the full request and
response shapes.
