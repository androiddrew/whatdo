// Shared helpers for the k6 load tests (#12).
//
// Target and thresholds are configurable via environment variables:
//   BASE_URL    server under test          (default http://localhost:8000)
//   API_KEY     bearer token, if auth is on (default: none / no-auth mode)
//   MODEL       requested Model id          (default jev-latest)
//   P95_MS      p95 latency threshold, ms   (default 1500)
//   FAIL_RATE   max http_req_failed rate    (default 0.01)
import http from "k6/http";
import { check } from "k6";

export const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
export const MODEL = __ENV.MODEL || "jev-latest";
export const P95_MS = Number(__ENV.P95_MS || 1500);
export const FAIL_RATE = Number(__ENV.FAIL_RATE || 0.01);

// One request per decision primitive, so a run exercises Noul, Choice, and Score.
const BODY = JSON.stringify({
  state: "I was charged twice. Please help.",
  model: MODEL,
  questions: {
    billing: { type: "noul", instructions: "Is this about billing?" },
    tone: {
      type: "choice",
      instructions: "What is the tone?",
      criteria: { angry: null, calm: null },
    },
    urgency: {
      type: "score",
      instructions: "How urgent is this?",
      criteria: ["low", "medium", "high"],
    },
  },
});

function headers() {
  const h = { "Content-Type": "application/json" };
  if (__ENV.API_KEY) {
    h["Authorization"] = `Bearer ${__ENV.API_KEY}`;
  }
  return h;
}

// Fire one System One request and check the outcome. `allowOverload` accepts a
// 529 (the retryable overload signal) as a valid response under saturation.
export function systemOne(allowOverload) {
  const res = http.post(`${BASE_URL}/v1/systemone`, BODY, {
    headers: headers(),
  });
  check(res, {
    "status ok": (r) =>
      r.status === 200 || (allowOverload === true && r.status === 529),
    "answers present on 200": (r) =>
      r.status !== 200 || (r.json("answers") && r.json("answers.billing.noul") !== undefined),
  });
  return res;
}
