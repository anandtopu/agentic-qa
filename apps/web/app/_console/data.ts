/* Demo data for the AgenticQA operator console — checkout-discount-PR scenario. */

export type Workspace = {
  id: string;
  mark: string;
  name: string;
  repo: string;
  env: string;
  stats: { runsToday: number; openFails: number; riskAvg: number };
};

export type RunStatus = "running" | "passed" | "failed" | "blocked";

export type RecentRun = {
  id: string;
  pr: string;
  title: string;
  status: RunStatus;
  risk: number;
  classification: string;
  dur: string;
  started: string;
};

export type Approval = {
  id: string;
  title: string;
  sub: string;
  icon: string;
  urgency: "high" | "normal";
};

export type AgentTest = {
  name: string;
  type: string;
  status: "pass" | "fail";
  ms: number;
  failureId?: string;
};

export type AgentToolCall = {
  name: string;
  args: Record<string, unknown>;
  result: string;
};

export type AgentStep = {
  key: string;
  agent: string;
  title: string;
  duration: number;
  model?: string;
  costUsd?: number;
  tokensIn?: number;
  tokensOut?: number;
  summary: string;
  bullets: string[];
  tool?: AgentToolCall;
  tests?: AgentTest[];
};

export type PullRequest = {
  number: number;
  title: string;
  author: string;
  authorAvatar: string;
  branch: string;
  base: string;
  files: number;
  additions: number;
  deletions: number;
  acceptanceCriteria: string[];
};

export type AgentRun = {
  id: string;
  startedAt: string;
  pr: PullRequest;
  steps: AgentStep[];
};

export type EvidenceItem = { text: string; src: string };

export type Failure = {
  id: string;
  testName: string;
  agent: string;
  classificationLabel: string;
  classificationDesc: string;
  confidence: number;
  suspectedCause: string;
  evidence: EvidenceItem[];
  request: string;
  response: string;
  recommendedOwner: string;
  ticketTitle: string;
};

export type RiskDriver = {
  label: string;
  sub: string;
  pts: number;
  severity: "high" | "med" | "low" | "warn";
};

export type Risk = {
  score: number;
  level: "low" | "med" | "medium" | "high" | "critical";
  recommendation: string;
  reasonsShort: string[];
  drivers: RiskDriver[];
};

export type EvalMetric = {
  agent: string;
  metric: string;
  value: number;
  target: string;
  color: "ok" | "warn" | "high" | "med" | "low";
};

export type AuditEvent = {
  ts: string;
  actor: string;
  action: string;
  target: string;
  sig: string;
};

export const WORKSPACES: Workspace[] = [
  { id: "ws_payments", mark: "PM", name: "Payments service", repo: "acme/payments-service", env: "staging", stats: { runsToday: 14, openFails: 1, riskAvg: 32 } },
  { id: "ws_storefront", mark: "SF", name: "Storefront web", repo: "acme/storefront-web", env: "staging", stats: { runsToday: 27, openFails: 0, riskAvg: 18 } },
  { id: "ws_inventory", mark: "IV", name: "Inventory API", repo: "acme/inventory-api", env: "staging", stats: { runsToday: 9, openFails: 2, riskAvg: 41 } },
  { id: "ws_admin", mark: "AD", name: "Merchant admin", repo: "acme/merchant-admin", env: "staging", stats: { runsToday: 6, openFails: 0, riskAvg: 22 } },
  { id: "ws_search", mark: "SR", name: "Search & discovery", repo: "acme/search-svc", env: "staging", stats: { runsToday: 11, openFails: 1, riskAvg: 27 } },
  { id: "ws_notif", mark: "NT", name: "Notifications", repo: "acme/notif-svc", env: "staging", stats: { runsToday: 4, openFails: 0, riskAvg: 14 } },
];

export const ACTIVE_WS = WORKSPACES[0]!;

export const RECENT_RUNS: RecentRun[] = [
  { id: "run_a3f2b1c8e9", pr: "#4827", title: "feat(checkout): support stacked discount codes", status: "running", risk: 78, classification: "product_defect", dur: "running…", started: "14:02" },
  { id: "run_2c1de8f04a", pr: "#4825", title: "fix(api): retry transient timeouts in idempotent ops", status: "passed", risk: 12, classification: "—", dur: "0:38", started: "12:11" },
  { id: "run_9b7f3a1c20", pr: "#4824", title: "refactor: split PaymentsAuthorizer module", status: "passed", risk: 18, classification: "—", dur: "0:51", started: "11:42" },
  { id: "run_4e8a216f7d", pr: "#4823", title: "chore(deps): bump cryptography 41 → 42", status: "passed", risk: 24, classification: "—", dur: "0:44", started: "10:08" },
  { id: "run_b1c44a02e8", pr: "#4821", title: "feat(refunds): partial refund endpoint", status: "blocked", risk: 67, classification: "test_gap", dur: "0:46", started: "09:31" },
  { id: "run_77c9120acb", pr: "—", title: "scheduled · nightly regression", status: "passed", risk: 21, classification: "—", dur: "4:12", started: "02:00" },
];

export const APPROVALS: Approval[] = [
  { id: "ap_1", title: "Override merge block · PR #4827", sub: "release_mgr · risk score 78 ≥ block threshold 60", icon: "ShieldCheck", urgency: "high" },
  { id: "ap_2", title: "Run destructive SQL · cleanup_tokens()", sub: "db_test.agent · staging · 1,402 rows", icon: "Database", urgency: "normal" },
  { id: "ap_3", title: "File Jira ticket · WPMT-3201", sub: "defect_triage.agent · payments-eng-lead", icon: "Bug", urgency: "normal" },
  { id: "ap_4", title: "Cost cap raise · run_b1c44a02e8", sub: "$5.00 → $7.50 · UI re-test fan-out", icon: "Zap", urgency: "normal" },
];

export const AGENT_RUN: AgentRun = {
  id: "run_a3f2b1c8e9",
  startedAt: "2026-05-06 14:02:18",
  pr: {
    number: 4827,
    title: "feat(checkout): support stacked discount codes",
    author: "elena.kovacs",
    authorAvatar: "EK",
    branch: "feat/checkout-stacked-discounts",
    base: "main",
    files: 9,
    additions: 312,
    deletions: 84,
    acceptanceCriteria: [
      "User can apply up to 3 stacked discount codes per cart.",
      "Discount stacking respects per-code per-user limits.",
      "Cart total recalculates on each code applied/removed.",
      "Payment authorization succeeds when stacked total > $0.",
    ],
  },
  steps: [
    {
      key: "planner", agent: "planner.agent", title: "Generated test plan from PR diff + acceptance criteria",
      duration: 3200, model: "claude-sonnet-4", costUsd: 0.018, tokensIn: 12400, tokensOut: 1820,
      summary: "Read PR diff, parsed 4 acceptance criteria, and produced a coverage plan across API, UI, DB, and E2E test types.",
      bullets: [
        "Identified 9 changed files; 3 are tested by existing fixtures.",
        "Mapped each AC to ≥1 test type for evidence-grade coverage.",
        "Selected staging env per default workspace policy.",
      ],
      tool: { name: "github.diff", args: { pr: 4827, base: "main" }, result: "9 files · +312 −84" },
    },
    {
      key: "test_design", agent: "test_design.agent", title: "Drafted 21 test cases with golden expectations",
      duration: 4100, model: "claude-sonnet-4", costUsd: 0.024, tokensIn: 9200, tokensOut: 3100,
      summary: "Generated test cases in API, UI, DB, and E2E categories. Tagged 4 cases as high-priority based on AC weight.",
      bullets: [
        "7 API contract tests · 6 UI scenarios · 4 DB invariants · 2 E2E happy/sad paths.",
        "Property tests added for stacking-order commutativity.",
        "All tests carry `prompt_version_id` for reproducibility.",
      ],
    },
    {
      key: "api", agent: "api_test.agent", title: "Executed contract tests against staging",
      duration: 5800, model: "claude-haiku-4-5", costUsd: 0.011, tokensIn: 6800, tokensOut: 760,
      summary: "Ran 7 contract tests via Newman. One assertion failed on stacked-discount authorization.",
      bullets: [
        "All non-stacked authorize/capture paths green.",
        "Stacked-discount path returned `expired_token` despite fresh token (anomaly).",
      ],
      tool: { name: "newman.run", args: { collection: "payments_v3.postman.json", env: "staging" }, result: "6 pass · 1 fail · 0 anomaly" },
      tests: [
        { name: "POST /authorize · single code", type: "api", status: "pass", ms: 312 },
        { name: "POST /authorize · no code", type: "api", status: "pass", ms: 287 },
        { name: "POST /authorize · stacked (2 codes)", type: "api", status: "fail", ms: 412, failureId: "fail_a3f2_p001" },
        { name: "POST /authorize · stacked (3 codes)", type: "api", status: "pass", ms: 401 },
        { name: "POST /capture · partial", type: "api", status: "pass", ms: 256 },
        { name: "POST /void · idempotent", type: "api", status: "pass", ms: 198 },
        { name: "GET /tokens/:id · TTL", type: "api", status: "pass", ms: 142 },
      ],
    },
    {
      key: "ui", agent: "ui_test.agent", title: "Drove the storefront checkout in headless Chromium",
      duration: 6200, model: "claude-sonnet-4", costUsd: 0.022, tokensIn: 8400, tokensOut: 1240,
      summary: "Played 6 UI scenarios in Playwright. Discount UI surfaces the right error states; pay-button blocks correctly when stacking limit hit.",
      bullets: [
        "Cart total recalculates within 220 ms median on each apply/remove.",
        "Codepath for 3rd code shows the correct \"max codes reached\" toast.",
      ],
      tool: { name: "playwright.run", args: { suite: "checkout_stacked", workers: 4 }, result: "6 pass · 0 fail" },
      tests: [
        { name: "checkout · apply 1 code", type: "ui", status: "pass", ms: 1820 },
        { name: "checkout · apply 2 codes (stack)", type: "ui", status: "pass", ms: 2110 },
        { name: "checkout · apply 3 codes (max)", type: "ui", status: "pass", ms: 2380 },
        { name: "checkout · remove middle code", type: "ui", status: "pass", ms: 1604 },
        { name: "checkout · expired code message", type: "ui", status: "pass", ms: 1402 },
        { name: "checkout · per-user limit", type: "ui", status: "pass", ms: 1808 },
      ],
    },
    {
      key: "db", agent: "db_test.agent", title: "Verified DB invariants in read-only mode",
      duration: 3700, model: "claude-haiku-4-5", costUsd: 0.007, tokensIn: 4200, tokensOut: 510,
      summary: "Validated `payment_tokens` and `discount_applications` constraints. Detected an anomaly: tokens get re-issued unnecessarily on stacking.",
      bullets: [
        "Foreign-key integrity holds across all sampled rows.",
        "Anomaly: 14% of stacked carts produce orphan token rows (read-only assertion).",
      ],
      tool: { name: "duckdb.query", args: { sql: "SELECT count(*) FROM payment_tokens t LEFT JOIN charges c USING(token_id) WHERE c.id IS NULL AND t.created_at > now() - interval '1 hour'", mode: "read-only" }, result: "1 anomaly · 142 orphan tokens" },
    },
    {
      key: "e2e", agent: "e2e_test.agent", title: "Ran full purchase journey · stacked codes",
      duration: 7600, model: "claude-sonnet-4", costUsd: 0.027, tokensIn: 10100, tokensOut: 1640,
      summary: "Composed UI + API + DB into 2 E2E flows. Happy path passed. Stacked-discount path partially completed: cart finalised, payment failed at authorize step.",
      bullets: [
        "happy_path · 1 code · checkout completed in 6.2s.",
        "sad_path · 2 codes · checkout failed at authorize (matches API failure).",
      ],
      tool: { name: "e2e.compose", args: { flows: ["happy_path", "sad_path"] }, result: "1 pass · 1 partial" },
    },
    {
      key: "classifier", agent: "failure_classifier.agent", title: "Classified failures · cross-referenced evidence",
      duration: 4400, model: "claude-sonnet-4", costUsd: 0.019, tokensIn: 7800, tokensOut: 980,
      summary: "Joined the API failure with the DB anomaly and the diff. Classified as product_defect (not flake / not infra) at 86% confidence.",
      bullets: [
        "Evidence cluster size: 4 (API · DB · diff · history).",
        "Signature is new on this branch — no flake history on main.",
        "Suspected file: apps/api/payments/authorizer.py · re-tokenization branch.",
      ],
      tool: { name: "evidence.join", args: { signals: ["api.fail", "db.anomaly", "git.diff", "history.30d"] }, result: "product_defect · conf 0.86" },
    },
    {
      key: "risk", agent: "release_risk.agent", title: "Computed release risk score",
      duration: 3300, model: "claude-sonnet-4", costUsd: 0.014, tokensIn: 5400, tokensOut: 720,
      summary: "Scored the run at 78 / 100 (high). Recommendation: BLOCK merge. Score driven by failed authorize path on a payments-critical surface.",
      bullets: [
        "Path criticality (payments authorize) → +28 points.",
        "Defect type product_defect at 86% conf → +24 points.",
        "DB anomaly correlated with same root cause → +14 points.",
        "Untested branch in diff (else-clause) → +12 points.",
      ],
      tool: { name: "risk.score", args: { run_id: "run_a3f2b1c8e9", model: "logistic_v1.9" }, result: "78 · high · BLOCK" },
    },
    {
      key: "triage", agent: "defect_triage.agent", title: "Drafted Jira ticket · awaiting approval",
      duration: 3500, model: "claude-haiku-4-5", costUsd: 0.008, tokensIn: 4900, tokensOut: 880,
      summary: "Drafted WPMT-3201 with reproduction steps, expected vs. actual, suspected file, and links to the run + evidence report.",
      bullets: [
        "Owner suggested: payments-eng-lead (file ownership).",
        "Severity: P1 (blocks release).",
        "External issue creation requires human approval (in queue).",
      ],
    },
    {
      key: "report", agent: "report.agent", title: "Generated evidence report and posted to PR",
      duration: 3900, model: "claude-sonnet-4", costUsd: 0.016, tokensIn: 5800, tokensOut: 1620,
      summary: "Compiled the full evidence package · markdown for PR comment · HTML for archival to S3 · signed audit-log entry.",
      bullets: [
        "Posted as comment on PR #4827.",
        "Archived to s3://acme-aqa-evidence/run_a3f2b1c8e9/.",
        "Audit event run.completed signed (HMAC-SHA256).",
      ],
    },
  ],
};

export const FAILURE: Failure = {
  id: "fail_a3f2_p001",
  testName: "POST /authorize · stacked (2 codes)",
  agent: "failure_classifier.agent",
  classificationLabel: "Product defect",
  classificationDesc: "New regression introduced by re-tokenization branch in PR #4827. Not a flake — signature absent from 30 days of main-branch history.",
  confidence: 0.86,
  suspectedCause: "When two discount codes are applied, the authorizer calls `tokens.refresh()`, which raises on still-valid tokens that the call assumes to be expired. The else-branch was added in this PR but never exercised by existing tests.",
  evidence: [
    { text: "API contract test failed with `expired_token` on a token issued 1.2s prior.", src: "api_test.agent · newman" },
    { text: "DB invariant detected 142 orphan token rows in the last hour, all stacked-discount carts.", src: "db_test.agent · duckdb" },
    { text: "Diff hunk in `authorizer.py` introduces unconditional refresh on `len(discount_codes) > 1`.", src: "git.diff · PR #4827" },
    { text: "No history of this signature on main in 30d. New branch only.", src: "history.30d · evidence-store" },
  ],
  request: `POST /v1/authorize HTTP/1.1
content-type: application/json

{
  "card_token": "tok_4Ji…REDACTED",
  "amount_cents": 4288,
  "currency": "usd",
  "discount_codes": ["SUMMER10","WELCOME15"]
}`,
  response: `HTTP/1.1 402 Payment Required
content-type: application/json

{
  "error": "expired_token",
  "decline_code": "expired_token",
  "trace_id": "tr_b1c8e9a3f2"
}`,
  recommendedOwner: "payments-eng-lead · elena.kovacs",
  ticketTitle: "WPMT-3201 · Stacked discount authorize fails on still-valid token (regression in PR #4827)",
};

export const RISK: Risk = {
  score: 78,
  level: "high",
  recommendation: "BLOCK merge",
  reasonsShort: [
    "1 API contract test failed on payments authorize — release-critical surface.",
    "Defect cluster size 4 (API + DB + diff + history) — high evidence weight.",
    "Untested branch in diff hunk: else-clause never reached by existing fixtures.",
  ],
  drivers: [
    { label: "Path criticality · payments.authorize", sub: "service tier 0 · revenue-impact", pts: 28, severity: "high" },
    { label: "Defect type · product_defect", sub: "classifier confidence 0.86", pts: 24, severity: "high" },
    { label: "DB anomaly correlated", sub: "142 orphan tokens · same root cause", pts: 14, severity: "med" },
    { label: "Untested diff branch", sub: "authorizer.py L132–L149", pts: 12, severity: "med" },
  ],
};

export const EVAL_METRICS: EvalMetric[] = [
  { agent: "planner.agent", metric: "ac_coverage", value: 0.96, target: "≥0.95", color: "ok" },
  { agent: "planner.agent", metric: "plan_validity (judge-of-judge)", value: 0.92, target: "≥0.90", color: "ok" },
  { agent: "test_design.agent", metric: "case_uniqueness", value: 0.88, target: "≥0.85", color: "ok" },
  { agent: "test_design.agent", metric: "exec_pass_rate (golden)", value: 0.94, target: "≥0.93", color: "ok" },
  { agent: "failure_classifier.agent", metric: "precision (product_defect)", value: 0.91, target: "≥0.90", color: "ok" },
  { agent: "failure_classifier.agent", metric: "recall (product_defect)", value: 0.83, target: "≥0.85", color: "warn" },
  { agent: "failure_classifier.agent", metric: "calibration (ECE)", value: 0.04, target: "≤0.05", color: "ok" },
  { agent: "release_risk.agent", metric: "AUC (block-correctness)", value: 0.89, target: "≥0.88", color: "ok" },
  { agent: "release_risk.agent", metric: "Brier score", value: 0.11, target: "≤0.13", color: "ok" },
  { agent: "report.agent", metric: "factuality (claim-grounding)", value: 0.97, target: "≥0.95", color: "ok" },
];

export const AUDIT_EVENTS: AuditEvent[] = [
  { ts: "14:04:03", actor: "report.agent", action: "report.posted", target: "github://acme/payments-service/pulls/4827", sig: "9a3f…b1c8" },
  { ts: "14:03:58", actor: "release_risk.agent", action: "risk.scored", target: "run_a3f2b1c8e9 · score=78", sig: "f04a…2c1d" },
  { ts: "14:03:31", actor: "failure_classifier.agent", action: "classification.emitted", target: "fail_a3f2_p001 · product_defect", sig: "e8f0…7d4b" },
  { ts: "14:03:02", actor: "db_test.agent", action: "tool.invoked", target: "duckdb.query · read-only", sig: "1c20…9b7f" },
  { ts: "14:02:56", actor: "api_test.agent", action: "test.failed", target: "POST /authorize · stacked (2 codes)", sig: "3a1c…b1c4" },
  { ts: "14:02:28", actor: "policy_guard", action: "policy.checked", target: "destructive_sql=false · ext_issue=approval", sig: "0acb…77c9" },
  { ts: "14:02:18", actor: "orchestrator", action: "run.started", target: "run_a3f2b1c8e9 · pr=4827", sig: "f7d4…4e8a" },
  { ts: "13:58:11", actor: "release-mgr-1", action: "approval.granted", target: "run_b1c44a02e8 · cost-cap raise", sig: "5d2e…8b1f" },
  { ts: "13:42:09", actor: "evals.runner", action: "regression.detected", target: "failure_classifier.recall=0.83 (was 0.86)", sig: "a012…4c3d" },
];
