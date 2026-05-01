// AQAOClient — Story 5.3.

import { errorForStatus, AQAOError } from "./errors.js";

export interface AQAOClientOptions {
  baseUrl: string;
  token: string;
  tenantId: string;
  role?: string;
  timeoutMs?: number;
  /**
   * Override the underlying fetch — useful for tests + edge runtimes.
   */
  fetch?: FetchSender;
}

export type FetchSender = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

interface RequestArgs {
  method: string;
  path: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  idempotencyKey?: string;
}

function newIdempotencyKey(): string {
  // Modern runtimes ship crypto.randomUUID; fall back to a poor-man's
  // generator only when it's missing (older Node).
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Array.from({ length: 32 }, () =>
    Math.floor(Math.random() * 16).toString(16),
  ).join("");
}

export class AQAOClient {
  private readonly baseUrl: string;
  private readonly token: string;
  private readonly tenantId: string;
  private readonly role: string | undefined;
  private readonly timeoutMs: number;
  private readonly fetcher: FetchSender;

  readonly workspaces: WorkspacesResource;
  readonly testRuns: TestRunsResource;
  readonly approvals: ApprovalsResource;
  readonly usage: UsageResource;

  constructor(opts: AQAOClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/$/, "");
    this.token = opts.token;
    this.tenantId = opts.tenantId;
    this.role = opts.role;
    this.timeoutMs = opts.timeoutMs ?? 30_000;
    this.fetcher = opts.fetch ?? (globalThis.fetch.bind(globalThis));

    this.workspaces = new WorkspacesResource(this);
    this.testRuns = new TestRunsResource(this);
    this.approvals = new ApprovalsResource(this);
    this.usage = new UsageResource(this);
  }

  /** @internal */
  async request<T = unknown>(args: RequestArgs): Promise<T> {
    const url = new URL(this.baseUrl + args.path);
    if (args.query !== undefined) {
      for (const [k, v] of Object.entries(args.query)) {
        if (v !== undefined) {
          url.searchParams.set(k, String(v));
        }
      }
    }
    const headers: Record<string, string> = {
      Authorization: `Bearer ${this.token}`,
      "X-AQAO-Tenant-Id": this.tenantId,
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (this.role !== undefined) {
      headers["X-AQAO-Role"] = this.role;
    }
    if (args.idempotencyKey !== undefined) {
      headers["Idempotency-Key"] = args.idempotencyKey;
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let response: Response;
    try {
      response = await this.fetcher(url.toString(), {
        method: args.method,
        headers,
        body: args.body !== undefined ? JSON.stringify(args.body) : undefined,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      throw await this.toError(response);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  private async toError(response: Response): Promise<AQAOError> {
    let payload: Record<string, unknown> = {};
    try {
      payload = (await response.json()) as Record<string, unknown>;
    } catch {
      payload = { detail: await response.text() };
    }
    let retryAfterSeconds: number | undefined;
    if (response.status === 429) {
      const raw = response.headers.get("Retry-After");
      const parsed = raw === null ? Number.NaN : Number(raw);
      retryAfterSeconds = Number.isFinite(parsed) ? parsed : undefined;
    }
    const detailsRaw = payload["errors"];
    const details = Array.isArray(detailsRaw)
      ? (detailsRaw as Record<string, unknown>[])
      : [];
    return errorForStatus({
      statusCode: response.status,
      message: String(payload["detail"] ?? `HTTP ${response.status}`),
      traceId: response.headers.get("X-AQAO-Trace-Id") ?? undefined,
      details,
      retryAfterSeconds,
    });
  }
}

class WorkspacesResource {
  constructor(private readonly c: AQAOClient) {}

  create(opts: { name: string; applicationType: string }): Promise<{ id: string } & Record<string, unknown>> {
    return this.c.request({
      method: "POST",
      path: "/api/v1/workspaces",
      body: { name: opts.name, application_type: opts.applicationType },
      idempotencyKey: newIdempotencyKey(),
    });
  }

  get(workspaceId: string): Promise<Record<string, unknown>> {
    return this.c.request({
      method: "GET",
      path: `/api/v1/workspaces/${workspaceId}`,
    });
  }

  setPolicy(workspaceId: string, opts: { sourceYaml: string }): Promise<Record<string, unknown>> {
    return this.c.request({
      method: "PUT",
      path: `/api/v1/workspaces/${workspaceId}/policy`,
      body: { source_yaml: opts.sourceYaml, activate: true },
      idempotencyKey: newIdempotencyKey(),
    });
  }
}

class TestRunsResource {
  constructor(private readonly c: AQAOClient) {}

  create(opts: {
    workspaceId: string;
    repository: string;
    pullNumber: number;
    headSha: string;
  }): Promise<{ id: string } & Record<string, unknown>> {
    return this.c.request({
      method: "POST",
      path: "/api/v1/test-runs",
      body: {
        workspace_id: opts.workspaceId,
        repository: opts.repository,
        pull_number: opts.pullNumber,
        head_sha: opts.headSha,
      },
      idempotencyKey: newIdempotencyKey(),
    });
  }

  get(runId: string): Promise<Record<string, unknown>> {
    return this.c.request({ method: "GET", path: `/api/v1/test-runs/${runId}` });
  }

  failures(runId: string): Promise<Record<string, unknown>[]> {
    return this.c.request({
      method: "GET",
      path: `/api/v1/test-runs/${runId}/failures`,
    });
  }
}

class ApprovalsResource {
  constructor(private readonly c: AQAOClient) {}

  list(opts: { state?: string; workspaceId?: string; limit?: number } = {}): Promise<Record<string, unknown>> {
    return this.c.request({
      method: "GET",
      path: "/api/v1/approvals",
      query: {
        state: opts.state,
        workspace_id: opts.workspaceId,
        limit: opts.limit ?? 100,
      },
    });
  }

  approve(requestId: string, opts: { comment?: string } = {}): Promise<Record<string, unknown>> {
    return this.c.request({
      method: "POST",
      path: `/api/v1/approvals/${requestId}/approve`,
      body: { comment: opts.comment ?? null },
    });
  }
}

class UsageResource {
  constructor(private readonly c: AQAOClient) {}

  summary(opts: { workspaceId?: string; since?: string; until?: string } = {}): Promise<Record<string, unknown>> {
    return this.c.request({
      method: "GET",
      path: "/api/v1/usage/summary",
      query: {
        workspace_id: opts.workspaceId,
        since: opts.since,
        until: opts.until,
      },
    });
  }
}
