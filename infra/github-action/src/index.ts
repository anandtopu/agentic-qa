import * as core from "@actions/core";
import * as github from "@actions/github";

interface ActionInputs {
  aqaoUrl: string;
  aqaoToken: string;
  workspaceId: string;
  testPlanId: string | null;
  riskThreshold: number;
  maxRiskBand: RiskBand | null;
  pollIntervalMs: number;
  pollTimeoutMs: number;
}

type RiskBand = "low" | "medium" | "high" | "critical";

const RISK_BAND_RANK: Record<RiskBand, number> = {
  low: 0,
  medium: 1,
  high: 2,
  critical: 3,
};

interface RiskScoreSummary {
  score: number;
  band: RiskBand;
  recommendation: string;
}

interface TestRunSummary {
  id: string;
  state: string;
  finished_at: string | null;
  summary: Record<string, unknown>;
}

interface PrCommentBody {
  test_run_id: string;
  body: string;
  marker: string;
}

interface FailureRow {
  category: string;
}

const PR_COMMENT_MARKER = "<!-- aqao:pr-comment:v1 -->";

async function main(): Promise<void> {
  const inputs = readInputs();
  core.debug(
    `Agentic QA Orchestrator action starting for workspace=${inputs.workspaceId} ` +
      `pr=${github.context.payload.pull_request?.number ?? "n/a"}`,
  );

  if (!inputs.testPlanId) {
    core.setFailed(
      "test-plan-id is required for Phase 1. Run the planner first via " +
        "POST /api/v1/test-plans, or wait for the auto-plan flow shipping " +
        "in Phase 2.",
    );
    return;
  }

  // 1. Start a test run
  const startBody = JSON.stringify({
    test_plan_id: inputs.testPlanId,
    idempotency_key: `gh-${github.context.runId}-${github.context.sha.slice(
      0,
      12,
    )}`,
  });
  const startRes = await fetch(`${inputs.aqaoUrl}/api/v1/test-runs`, {
    method: "POST",
    headers: jsonHeaders(inputs),
    body: startBody,
  });
  if (!startRes.ok) {
    core.setFailed(
      `start test_run failed: ${startRes.status} ${await startRes.text()}`,
    );
    return;
  }
  const started = (await startRes.json()) as { run: TestRunSummary };
  const testRunId = started.run.id;
  core.info(`Started test_run ${testRunId}`);
  core.setOutput("test-run-id", testRunId);

  // 2. Poll until terminal
  const finalRun = await pollUntilTerminal(testRunId, inputs);
  core.setOutput("final-state", finalRun.state);
  core.info(`test_run ${testRunId} reached state=${finalRun.state}`);

  // 3. Pull failure classifications for the gate
  const failuresRes = await fetch(
    `${inputs.aqaoUrl}/api/v1/test-runs/${testRunId}/failures`,
    { headers: jsonHeaders(inputs) },
  );
  const failures = failuresRes.ok
    ? ((await failuresRes.json()) as FailureRow[])
    : [];
  const productDefectCount = failures.filter(
    (f) => f.category === "product_defect",
  ).length;
  core.setOutput("failure-count", String(failures.length));
  core.setOutput("product-defect-count", String(productDefectCount));

  // 4. Render + post PR comment
  const prComment = await fetchPrComment(testRunId, inputs);
  const prCommentUrl = await upsertPrComment(prComment.body);
  if (prCommentUrl) {
    core.setOutput("pr-comment-url", prCommentUrl);
  }

  // 5. Quality gate — prefer release-risk band (Story 2.3.3) when the
  // backend has produced a score; fall back to product_defect count for
  // older deployments that haven't yet wired the scorer into the
  // orchestrator graph.
  if (finalRun.state === "failed") {
    core.setFailed(`test_run ${testRunId} ended in state=failed`);
    return;
  }

  const riskScore = extractRiskScore(finalRun.summary);
  if (riskScore !== null) {
    core.setOutput("risk-score", String(riskScore.score));
    core.setOutput("risk-band", riskScore.band);
    core.setOutput("risk-recommendation", riskScore.recommendation);
    if (
      inputs.maxRiskBand !== null &&
      RISK_BAND_RANK[riskScore.band] > RISK_BAND_RANK[inputs.maxRiskBand]
    ) {
      core.setFailed(
        `release risk band ${riskScore.band} (score ${riskScore.score}) ` +
          `exceeds maximum allowed ${inputs.maxRiskBand}`,
      );
      return;
    }
  }

  if (productDefectCount > inputs.riskThreshold) {
    core.setFailed(
      `${productDefectCount} product_defect failures exceeds risk threshold ` +
        `${inputs.riskThreshold}`,
    );
    return;
  }
  core.info("Agentic QA Orchestrator gate passed.");
}

function extractRiskScore(
  summary: Record<string, unknown>,
): RiskScoreSummary | null {
  const raw = summary["risk_score"];
  if (raw === null || raw === undefined || typeof raw !== "object") {
    return null;
  }
  const obj = raw as Record<string, unknown>;
  if (
    typeof obj.score !== "number" ||
    typeof obj.band !== "string" ||
    typeof obj.recommendation !== "string"
  ) {
    return null;
  }
  if (!(obj.band in RISK_BAND_RANK)) {
    return null;
  }
  return {
    score: obj.score,
    band: obj.band as RiskBand,
    recommendation: obj.recommendation,
  };
}

function readInputs(): ActionInputs {
  const rawBand = (core.getInput("max-risk-band") || "").toLowerCase();
  const maxRiskBand =
    rawBand === "" ? null : (rawBand as RiskBand);
  if (maxRiskBand !== null && !(maxRiskBand in RISK_BAND_RANK)) {
    throw new Error(
      `max-risk-band must be one of low|medium|high|critical (got ${rawBand})`,
    );
  }
  return {
    aqaoUrl: core.getInput("aqao-url", { required: true }).replace(/\/$/, ""),
    aqaoToken: core.getInput("aqao-token", { required: true }),
    workspaceId: core.getInput("workspace-id", { required: true }),
    testPlanId: core.getInput("test-plan-id") || null,
    riskThreshold: Number(core.getInput("risk-threshold") || "0"),
    maxRiskBand,
    pollIntervalMs:
      Number(core.getInput("poll-interval-seconds") || "10") * 1000,
    pollTimeoutMs:
      Number(core.getInput("poll-timeout-seconds") || "1800") * 1000,
  };
}

function jsonHeaders(inputs: ActionInputs): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${inputs.aqaoToken}`,
    "X-AQAO-Tenant-Id": inputs.workspaceId, // Phase 1 reuses workspace as tenant scope
  };
}

const TERMINAL_STATES = new Set(["done", "failed", "paused_for_approval"]);

async function pollUntilTerminal(
  testRunId: string,
  inputs: ActionInputs,
): Promise<TestRunSummary> {
  const deadline = Date.now() + inputs.pollTimeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(
      `${inputs.aqaoUrl}/api/v1/test-runs/${testRunId}`,
      { headers: jsonHeaders(inputs) },
    );
    if (!res.ok) {
      throw new Error(
        `poll failed: ${res.status} ${await res.text()}`,
      );
    }
    const run = (await res.json()) as TestRunSummary;
    if (TERMINAL_STATES.has(run.state)) {
      return run;
    }
    await sleep(inputs.pollIntervalMs);
  }
  throw new Error(`poll timed out after ${inputs.pollTimeoutMs}ms`);
}

async function fetchPrComment(
  testRunId: string,
  inputs: ActionInputs,
): Promise<PrCommentBody> {
  const res = await fetch(
    `${inputs.aqaoUrl}/api/v1/test-runs/${testRunId}/pr-comment`,
    {
      method: "POST",
      headers: jsonHeaders(inputs),
      body: JSON.stringify({
        run_url: `${inputs.aqaoUrl}/test-runs/${testRunId}`,
      }),
    },
  );
  if (!res.ok) {
    throw new Error(
      `pr-comment fetch failed: ${res.status} ${await res.text()}`,
    );
  }
  return (await res.json()) as PrCommentBody;
}

async function upsertPrComment(body: string): Promise<string | null> {
  const ghToken = process.env.GITHUB_TOKEN;
  const pr = github.context.payload.pull_request;
  if (!ghToken || !pr) {
    core.warning(
      "GITHUB_TOKEN missing or not a pull_request event — skipping comment.",
    );
    return null;
  }
  const octokit = github.getOctokit(ghToken);
  const { owner, repo } = github.context.repo;
  const prNumber = pr.number as number;

  const existing = await octokit.paginate(
    octokit.rest.issues.listComments,
    { owner, repo, issue_number: prNumber, per_page: 100 },
  );
  const existingAQAO = existing.find((c) =>
    (c.body || "").includes(PR_COMMENT_MARKER),
  );

  if (existingAQAO) {
    const updated = await octokit.rest.issues.updateComment({
      owner,
      repo,
      comment_id: existingAQAO.id,
      body,
    });
    return updated.data.html_url;
  }
  const created = await octokit.rest.issues.createComment({
    owner,
    repo,
    issue_number: prNumber,
    body,
  });
  return created.data.html_url;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

void main().catch((err: unknown) => {
  core.setFailed(err instanceof Error ? err.message : String(err));
});
