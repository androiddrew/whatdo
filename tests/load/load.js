// Load test (#12): a ramping-arrival-rate profile that pushes request rate up to
// probe throughput and latency, and the worker pool's retryable 529 overload
// signal. A 529 is an expected response here (not a failure), so it is excluded
// from http_req_failed; genuine errors (5xx, timeouts) still count.
import http from "k6/http";
import { FAIL_RATE, P95_MS, systemOne } from "./common.js";

// Treat 200 and 529 as expected; everything else is a failure.
http.setResponseCallback(http.expectedStatuses(200, 529));

export const options = {
  scenarios: {
    ramp: {
      executor: "ramping-arrival-rate",
      startRate: 5,
      timeUnit: "1s",
      preAllocatedVUs: 20,
      maxVUs: 100,
      stages: [
        { target: 20, duration: "30s" },
        { target: 50, duration: "1m" },
        { target: 50, duration: "30s" },
        { target: 0, duration: "15s" },
      ],
    },
  },
  thresholds: {
    http_req_failed: [`rate<${FAIL_RATE}`],
    http_req_duration: [`p(95)<${P95_MS}`],
  },
};

export default function () {
  // Overload (529) is acceptable under sustained arrival rate.
  systemOne(true);
}
