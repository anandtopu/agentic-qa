// Failure classification scenario — Epic 4.5.
// AC: classification < 60s p95 at 10x concurrency.

import http from "k6/http";
import { check, sleep } from "k6";
import { authHeaders, BUDGETS, envOrFail, p95Under } from "../lib/checks.js";

export const options = {
  scenarios: {
    failure_classify: {
      executor: "constant-vus",
      vus: 10,
      duration: "5m",
    },
  },
  thresholds: {
    "http_req_duration{capability:failure_classification}": p95Under(
      BUDGETS.failure_classification,
    ),
    http_req_failed: ["rate<0.01"],
  },
};

const BASE_URL = envOrFail("QAFORGE_BASE_URL").replace(/\/$/, "");

export default function () {
  const body = JSON.stringify({
    signal_id: `vu-${__VU}-iter-${__ITER}`,
    test_name: "test_login",
    error_message: "AssertionError: expected 200 got 500",
    http_status_code: 500,
  });
  const res = http.post(`${BASE_URL}/api/v1/failures/classify`, body, {
    headers: authHeaders(),
    tags: { capability: "failure_classification" },
  });
  check(res, {
    "classification returned": (r) => r.status === 200,
  });
  sleep(0.2);
}
