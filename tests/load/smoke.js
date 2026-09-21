// Smoke test (#12): correctness under light load. A single VU makes a handful of
// requests; every one must succeed (no overload expected at this volume), so
// http_req_failed must be zero and p95 latency stays under the threshold.
import { P95_MS, systemOne } from "./common.js";

export const options = {
  vus: 1,
  iterations: 10,
  thresholds: {
    // No 529s expected under light load, so any non-2xx is a real failure.
    http_req_failed: ["rate==0"],
    http_req_duration: [`p(95)<${P95_MS}`],
  },
};

export default function () {
  systemOne(false);
}
