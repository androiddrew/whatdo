# In-process thread worker pool with a bounded queue and 529 overload

Laya `predict()` is a synchronous torch forward pass, and operators may have VRAM for several model copies to raise throughput. We serve inference with an **in-process thread pool of `pool_size` model copies fed by a single shared bounded queue**: torch releases the GIL during the forward pass, so threaded copies run in parallel, and one queue gives predictable backpressure. When the queue is saturated the server returns **HTTP 529** (overload), which the official SDK already retries with backoff. Horizontal scaling is left to container replicas.

## Considered options

- **Multiple OS processes** (one model per process) — rejected for v1: true isolation but IPC overhead and separate CUDA contexts; replicas cover the same need more simply.
- **Unbounded queue** — rejected: hides overload as unbounded latency instead of a retryable 529.
- **429 rate-limiting** — out of scope for v1; 529 is the only overload signal.
