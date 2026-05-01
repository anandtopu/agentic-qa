// PR analysis scenario — Epic 4.5.
// AC: PR analysis < 60s p95 at 10x concurrency.

import http from "k6/http";
import { check, sleep } from "k6";
import { authHeaders, BUDGETS, envOrFail, p95Under } from "../lib/checks.js";

export const options = {
  scenarios: {
    pr_analysis: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "60s", target: 10 },
        { duration: "5m", target: 10 },
        { duration: "30s", target: 0 },
      ],
      gracefulStop: "30s",
    },
  },
  thresholds: {
    "http_req_duration{capability:pr_analysis}": p95Under(
      BUDGETS.pr_analysis,
    ),
    http_req_failed: ["rate<0.01"], // 99% successful
  },
};

const BASE_URL = envOrFail("AQAO_BASE_URL").replace(/\/$/, "");

export default function () {
  const body = JSON.stringify({
    repository: "aqao/sample-app",
    pull_number: 42 + __VU,
    head_sha: "0".repeat(40),
  });
  const res = http.post(`${BASE_URL}/api/v1/test-runs`, body, {
    headers: authHeaders(),
    tags: { capability: "pr_analysis" },
  });
  check(res, {
    "test_run accepted": (r) => r.status >= 200 && r.status < 300,
  });
  sleep(0.5);
}
