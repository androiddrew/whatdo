# Load testing

Load tests use [k6](https://k6.io/) to drive `POST /v1/systemone` against a
running server and measure throughput and latency under concurrency — including
how the worker pool sheds load with `529` when its bounded queue saturates.

!!! note "Harness"
    A bundled k6 script set and a `make load-test` target ship with the
    load-testing work; the example below runs against any live server today.

## Run a load test

Install k6 (see the [k6 install docs](https://k6.io/docs/get-started/installation/)),
start a server, then run a script against it:

```bash
docker run -p 8000:8000 git.runcible.io/androiddrew/laya-server:latest
k6 run -e BASE_URL=http://localhost:8000 loadtest.js
```

## Example script

```javascript
import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  // Ramp concurrency to probe throughput and the 529 overload signal.
  stages: [
    { duration: "30s", target: 20 },
    { duration: "1m", target: 50 },
    { duration: "30s", target: 0 },
  ],
};

const payload = JSON.stringify({
  state: "I was charged twice.",
  model: "jev-latest",
  questions: {
    billing: { type: "noul", instructions: "Is this about billing?" },
  },
});

export default function () {
  const res = http.post(`${BASE_URL}/v1/systemone`, payload, {
    headers: { "Content-Type": "application/json" },
  });
  // 529 is an expected, retryable overload response under saturation.
  check(res, {
    "served or shed": (r) => r.status === 200 || r.status === 529,
  });
}
```

## What to watch

- **Throughput** scales with `LAYA_SERVER__POOL_SIZE` (engine copies) up to the
  host's resources.
- **`529` rate** rises once the bounded queue (`LAYA_SERVER__QUEUE_MAX`)
  saturates — the deliberate, retryable backpressure signal rather than
  unbounded latency.
- **Latency** (`http_req_duration`) and the `laya.inference.duration` metric (if
  [Observability](observability.md) is enabled) should track each other.
