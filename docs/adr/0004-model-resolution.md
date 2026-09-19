# One served model per deployment, with a built-in jev-latest shim

A deployment loads exactly **one served model** (its worker pool holds N copies of that single checkpoint), so VRAM cost stays predictable (`pool_size × one checkpoint`). Requests resolving to any other model return **422 "model not served"**; the response always echoes the concrete resolved checkpoint id so clients can pin. Because the official SDK sends `model="jev-latest"` by default, an **always-on compatibility shim** maps `jev-latest`/`jev-preview` to the served model so an unconfigured SDK works out of the box; a separate, feature-flagged **alias table** handles other `jev-*` ids for operators who want them.

## Consequences

- Serving multiple distinct checkpoints from one process is deliberately deferred; run separate deployments per model for now.
- The `jev-latest` shim is intentionally independent of the alias-table flag, so out-of-the-box SDK compatibility never depends on operator configuration.
