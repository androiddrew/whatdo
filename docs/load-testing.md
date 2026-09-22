# Load testing

Load tests use [k6](https://k6.io/) to drive `POST /v1/systemone` against a
running deployment and measure throughput and latency — including how the worker
pool sheds load with a retryable `529` when its bounded queue saturates.

The scripts live in `tests/load/` and each request exercises all three decision
primitives (a **Noul**, a **Choice**, and a **Score**) in one **System One** call:

| Script | Profile | Purpose |
| ------ | ------- | ------- |
| `smoke.js` | 1 VU, 10 iterations | Correctness under light load — every request must succeed. |
| `load.js` | ramping arrival rate (up to 50 req/s) | Throughput/latency under sustained load; a `529` is an accepted, expected response. |

Both enforce **thresholds** on p95 latency (`http_req_duration`) and the failure
rate (`http_req_failed`). In `load.js` a `529` is treated as expected (via a
response callback) so it does not count as a failure — only genuine errors do.

## Run

Install [k6](https://k6.io/docs/get-started/installation/), start a server, then:

```bash
make load-test BASE_URL=http://localhost:8000        # both scripts
make load-test BASE_URL=https://laya.example.com API_KEY=sk-…   # against auth mode
```

Or run a single script directly:

```bash
k6 run -e BASE_URL=http://localhost:8000 tests/load/smoke.js
```

!!! note "Real-model deployment"
    Run these against a **real-model** deployment (the CUDA image or a
    GPU host) to get meaningful numbers; the `FakeEngine` is deterministic and
    sub-millisecond, so it measures the HTTP path, not inference. Load tests are
    **not** gated in CI.

## Configuration

All knobs are environment variables (defaults in parentheses):

| Variable | Meaning |
| -------- | ------- |
| `BASE_URL` | Server under test (`http://localhost:8000`). |
| `API_KEY` | Bearer token, sent only if set (no-auth mode by default). |
| `MODEL` | Requested **Model** id (`jev-latest`). |
| `P95_MS` | p95 `http_req_duration` threshold in ms (`1500`). |
| `FAIL_RATE` | Max `http_req_failed` rate for `load.js` (`0.01`). |

## What to watch

- **Throughput** scales with `WHATDO_SERVER__POOL_SIZE` (engine copies) up to the
  host's resources.
- **`529` rate** rises once the bounded queue (`WHATDO_SERVER__QUEUE_MAX`)
  saturates — the deliberate, retryable backpressure signal rather than
  unbounded latency.
- **Latency** (`http_req_duration`) should track the `laya.inference.duration`
  metric when [Observability](observability.md) is enabled.
