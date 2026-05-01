// Shared thresholds + helpers — Epic 4.5.
//
// PRD §14.5 ceilings, mirrored from
// apps/api/src/aqao_api/perf/budgets.py. Keep both in sync; the
// Python smoke-test asserts the values match.

export const BUDGETS = {
  pr_analysis: 60_000,
  test_plan_generation: 90_000,
  api_smoke: 180_000,
  ui_smoke: 600_000,
  failure_classification: 60_000,
  evidence_report: 30_000,
};

export function envOrFail(name) {
  const v = __ENV[name];
  if (!v || v.length === 0) {
    throw new Error(`required env var ${name} is empty`);
  }
  return v;
}

export function authHeaders() {
  return {
    Authorization: `Bearer ${envOrFail("AQAO_TOKEN")}`,
    "X-AQAO-Tenant-Id": envOrFail("AQAO_TENANT_ID"),
    "X-AQAO-Role": "engineer",
    "Content-Type": "application/json",
  };
}

// Convert a milliseconds budget to a k6 threshold string at p95.
export function p95Under(budgetMs) {
  return [`p(95)<${budgetMs}`];
}
