"use client";

import {
  Fragment,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import {
  ACTIVE_WS,
  AGENT_RUN,
  APPROVALS,
  AUDIT_EVENTS,
  EVAL_METRICS,
  FAILURE,
  RECENT_RUNS,
  RISK,
  WORKSPACES,
  type AgentStep,
  type RunStatus,
  type Workspace,
} from "./data";
import { Icons, getIcon, type IconName } from "./icons";

/* ───────────── Routes & nav ───────────── */

type RouteKey =
  | "workspaces"
  | "dashboard"
  | "runs"
  | "failures"
  | "risk"
  | "report"
  | "evals"
  | "approvals"
  | "audit"
  | "prompts"
  | "settings";

const ROUTES: Record<RouteKey, string[]> = {
  workspaces: ["Workspaces"],
  dashboard: ["acme/payments-service", "Dashboard"],
  runs: ["acme/payments-service", "Test runs", "run_a3f2b1c8e9"],
  failures: ["acme/payments-service", "Failures", "fail_a3f2_p001"],
  risk: ["acme/payments-service", "Release risk", "run_a3f2b1c8e9"],
  report: ["acme/payments-service", "Evidence report", "run_a3f2b1c8e9"],
  evals: ["acme/payments-service", "Evaluations"],
  approvals: ["acme/payments-service", "Approvals"],
  audit: ["acme/payments-service", "Audit log"],
  prompts: ["acme/payments-service", "Prompts"],
  settings: ["acme/payments-service", "Settings"],
};

type NavItem = { key: RouteKey; label: string; icon: IconName; count?: number };
type NavGroup = { group: string; items: NavItem[] };

const NAV: NavGroup[] = [
  {
    group: "Workspace",
    items: [
      { key: "dashboard", label: "Dashboard", icon: "Gauge" },
      { key: "runs", label: "Test runs", icon: "Activity", count: 142 },
      { key: "failures", label: "Failures", icon: "Bug", count: 3 },
      { key: "risk", label: "Release risk", icon: "ShieldCheck" },
      { key: "report", label: "Evidence report", icon: "FileText" },
    ],
  },
  {
    group: "Quality",
    items: [
      { key: "evals", label: "Evaluations", icon: "Beaker" },
      { key: "prompts", label: "Prompts", icon: "ScrollText" },
    ],
  },
  {
    group: "Govern",
    items: [
      { key: "approvals", label: "Approvals", icon: "ClipboardCheck", count: 4 },
      { key: "audit", label: "Audit log", icon: "Search" },
      { key: "settings", label: "Settings", icon: "Settings" },
    ],
  },
];

/* ───────────── Shared atoms ───────────── */

function StatusBadge({ status }: { status: RunStatus | string }): JSX.Element {
  if (status === "running") return <span className="badge badge-info"><span className="badge-dot" />running</span>;
  if (status === "passed") return <span className="badge badge-success"><span className="badge-dot" />passed</span>;
  if (status === "failed") return <span className="badge badge-destructive"><span className="badge-dot" />failed</span>;
  if (status === "blocked") return <span className="badge badge-warning"><span className="badge-dot" />blocked</span>;
  return <span className="badge badge-secondary">{status}</span>;
}

function RiskPill({ score }: { score: number }): JSX.Element {
  let cls = "badge-success";
  let level = "low";
  if (score > 80) { cls = "badge-destructive"; level = "critical"; }
  else if (score > 60) { cls = "badge-destructive"; level = "high"; }
  else if (score > 30) { cls = "badge-warning"; level = "medium"; }
  return <span className={"badge " + cls + " mono"}>{score} · {level}</span>;
}

/* ───────────── Shell ───────────── */

function Sidebar({
  route,
  onNavigate,
  ws,
}: {
  route: RouteKey;
  onNavigate: (r: RouteKey) => void;
  ws: Workspace;
}): JSX.Element {
  return (
    <aside className="side">
      <div className="brand">
        <div className="brand-mark">AQ</div>
        <div>
          <div className="brand-name">AgenticQA</div>
          <div className="brand-sub">Orchestrator</div>
        </div>
      </div>
      <button className="workspace-pick" onClick={() => onNavigate("workspaces")}>
        <div className="ws-mark">{ws.mark}</div>
        <div className="ws-name">{ws.name}</div>
        <Icons.ChevronDown size={12} />
      </button>
      <nav>
        {NAV.map((group) => (
          <div key={group.group}>
            <div className="nav-group-label">{group.group}</div>
            {group.items.map((item) => {
              const IconCmp = Icons[item.icon];
              const active = route === item.key;
              return (
                <button
                  key={item.key}
                  className={"nav-link" + (active ? " active" : "")}
                  onClick={() => onNavigate(item.key)}
                >
                  {IconCmp ? <IconCmp /> : null}
                  <span>{item.label}</span>
                  {item.count != null && <span className="nav-count">{item.count}</span>}
                </button>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="footer">
        <span className="dot" />
        <span>orchestrator · 9 agents healthy</span>
      </div>
    </aside>
  );
}

function Topbar({ crumbs, user = "anand@acme.io" }: { crumbs: string[]; user?: string }): JSX.Element {
  return (
    <header className="top">
      <div className="crumbs">
        {crumbs.map((c, i) => (
          <Fragment key={i}>
            {i > 0 && (
              <span className="sep">
                <Icons.Chevron size={12} />
              </span>
            )}
            <span className={i === crumbs.length - 1 ? "here" : ""}>{c}</span>
          </Fragment>
        ))}
      </div>
      <div className="top-spacer" />
      <button className="btn btn-ghost btn-sm" title="Search">
        <Icons.Search size={14} />
      </button>
      <span className="who">
        <strong>{user}</strong>
      </span>
      <div className="avatar">AC</div>
    </header>
  );
}

/* ───────────── Workspaces ───────────── */

function WorkspacesScreen({ onOpen }: { onOpen: () => void }): JSX.Element {
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Workspaces</h1>
          <p className="sub">Each workspace pins one application under test to its repo, environments, and agent policies.</p>
        </div>
        <div className="actions">
          <button className="btn btn-outline btn-sm">
            <Icons.RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-default btn-sm">
            <Icons.Plus size={14} /> New workspace
          </button>
        </div>
      </div>
      <div className="ws-grid">
        {WORKSPACES.map((ws) => (
          <div key={ws.id} className="ws-card" onClick={onOpen}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div className="ws-mark-lg">{ws.mark}</div>
              <div style={{ flex: 1 }}>
                <h3>{ws.name}</h3>
                <div className="repo">{ws.repo}</div>
              </div>
              <span className="badge badge-outline mono">{ws.env}</span>
            </div>
            <div className="meta">
              <div><strong>{ws.stats.runsToday}</strong> runs today</div>
              <div><strong>{ws.stats.openFails}</strong> open fails</div>
              <div>risk avg <strong>{ws.stats.riskAvg}</strong></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ───────────── Dashboard ───────────── */

function DashboardScreen({ onNavigate }: { onNavigate: (r: RouteKey) => void }): JSX.Element {
  const ws = ACTIVE_WS;
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>{ws.name}</h1>
          <p className="sub">
            <span className="mono">{ws.repo}</span> · {ws.env} · 9 agents healthy
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-outline btn-sm">
            <Icons.GitPullRequest size={14} /> Run on PR
          </button>
          <button className="btn btn-default btn-sm">
            <Icons.Play size={14} /> Run smoke suite
          </button>
        </div>
      </div>

      <div className="stat-row">
        <div className="stat"><div className="k">Runs today</div><div className="v">14</div><div className="s"><span className="delta-up">▲ 3</span> vs. yesterday</div></div>
        <div className="stat"><div className="k">Pass rate · 7d</div><div className="v">94.2%</div><div className="s"><span className="delta-down">▼ 1.1pp</span> vs. last week</div></div>
        <div className="stat"><div className="k">Avg risk · 7d</div><div className="v">32</div><div className="s">low risk band</div></div>
        <div className="stat"><div className="k">Cost · today</div><div className="v">$0.84</div><div className="s">$0.06 / run avg</div></div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <div>
            <div className="title">Recent runs</div>
            <div className="desc">PR-triggered + scheduled runs across this workspace.</div>
          </div>
          <div className="actions">
            <button className="btn btn-ghost btn-sm">
              <Icons.RefreshCw size={14} />
            </button>
            <button className="btn btn-outline btn-sm">View all</button>
          </div>
        </div>
        <table className="tbl">
          <thead>
            <tr>
              <th className="mono">Run</th>
              <th>PR</th>
              <th>Title</th>
              <th>Status</th>
              <th>Risk</th>
              <th>Classification</th>
              <th>Duration</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {RECENT_RUNS.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => onNavigate("runs")}>
                <td className="mono">{r.id.slice(0, 12)}</td>
                <td className="mono muted">{r.pr}</td>
                <td>{r.title}</td>
                <td><StatusBadge status={r.status} /></td>
                <td><RiskPill score={r.risk} /></td>
                <td className="muted">{r.classification}</td>
                <td className="muted mono">{r.dur}</td>
                <td className="muted mono">{r.started}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <div className="card-head">
            <div className="title">Open approvals</div>
            <div className="desc">Human-in-the-loop gates pending action.</div>
          </div>
          <div>
            {APPROVALS.slice(0, 3).map((a) => {
              const IconCmp = getIcon(a.icon);
              return (
                <div key={a.id} className="approval-row">
                  <div className="icon-w">{IconCmp ? <IconCmp /> : null}</div>
                  <div>
                    <div className="title">{a.title}</div>
                    <div className="sub">{a.sub}</div>
                  </div>
                  <div className="actions">
                    <button className="btn btn-ghost btn-sm">Reject</button>
                    <button className="btn btn-default btn-sm">Approve</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <div className="title">Pillars enforced</div>
            <div className="desc">Non-negotiables checked on every run.</div>
          </div>
          <div className="card-body">
            <ul style={{ margin: 0, paddingLeft: 18, color: "var(--sr-fg-muted)", lineHeight: "22px" }}>
              <li>Secrets redacted at every text sink (property-tested).</li>
              <li>Read-only DB by default; destructive SQL gated.</li>
              <li>Every answer traceable via <code>run_id → tool_invocation_id</code>.</li>
              <li>Prompts versioned; <code>prompt_version_id</code> persisted per step.</li>
              <li>Append-only signed audit log (HMAC-SHA256).</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────── Test Run (HERO) ───────────── */

function ProgressBar({ pct }: { pct: number }): JSX.Element {
  return (
    <div className="bar">
      <span style={{ width: pct + "%" }} />
    </div>
  );
}

type StepState = "queued" | "running" | "done" | "fail";

function TimelineItem({
  step,
  state,
  expanded,
  onToggle,
  onOpenFailure,
}: {
  step: AgentStep;
  state: StepState;
  expanded: boolean;
  onToggle: () => void;
  onOpenFailure: (id: string) => void;
}): JSX.Element {
  const dotClass = state === "done" ? "done" : state === "fail" ? "fail" : state === "running" ? "run" : "queued";
  const cardClass = state === "running" ? "tl-card run-glow" : state === "fail" ? "tl-card fail-glow" : "tl-card";
  return (
    <div className="tl-item">
      <div className={"tl-dot " + dotClass} />
      <div className={cardClass}>
        <div className={"tl-head" + (expanded ? " open" : "")} onClick={onToggle}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span className="agent">{step.agent}</span>
              {state === "running" && <span className="badge badge-info"><span className="badge-dot" />running</span>}
              {state === "done" && <span className="badge badge-success"><span className="badge-dot" />done</span>}
              {state === "fail" && <span className="badge badge-destructive"><span className="badge-dot" />fail</span>}
              {state === "queued" && <span className="badge badge-secondary">queued</span>}
            </div>
            <div className="title" style={{ marginTop: 4 }}>{step.title}</div>
          </div>
          <div className="meta">
            {step.model && <span>{step.model}</span>}
            {step.costUsd != null && <span>${step.costUsd.toFixed(3)}</span>}
            <span>{(step.duration / 1000).toFixed(1)}s</span>
          </div>
          <Icons.Chevron size={14} className="chev" />
        </div>
        {expanded && state !== "queued" && (
          <div className="tl-body">
            <div style={{ paddingTop: 12, fontSize: 13, lineHeight: "20px" }}>{step.summary}</div>
            <ul className="step-list">
              {step.bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
            {step.tool && (
              <div className="tool-call">
                <span className="key">tool </span>
                {step.tool.name}
                <span className="key">(</span>
                {Object.entries(step.tool.args).map(([k, v], i) => (
                  <span key={k}>
                    {i > 0 && ", "}
                    <span className="key">{k}=</span>
                    {JSON.stringify(v)}
                  </span>
                ))}
                <span className="key">) → </span>
                <span className={step.tool.result.includes("fail") || step.tool.result.includes("anomaly") ? "bad" : "ok"}>
                  {step.tool.result}
                </span>
              </div>
            )}
            {step.tests && (
              <div style={{ marginTop: 12 }}>
                {step.tests.map((t, i) => (
                  <div key={i} className={"test-row" + (t.status === "fail" ? " is-fail" : "")}>
                    <div className={"pill-mini " + t.status} />
                    <div className="name">{t.name}</div>
                    <div className="type">{t.type}</div>
                    <div className="ms">
                      {t.ms} ms
                      {t.status === "fail" && (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ marginLeft: 6, height: 22, padding: "0 6px" }}
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenFailure(t.failureId ?? "");
                          }}
                        >
                          triage <Icons.ArrowRight size={12} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function TestRunScreen({
  onNavigate,
  autoplay = true,
}: {
  onNavigate: (r: RouteKey) => void;
  autoplay?: boolean;
}): JSX.Element {
  const run = AGENT_RUN;
  const [tick, setTick] = useState(0);
  const [paused, setPaused] = useState(!autoplay);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ planner: true, api: true });

  const offsets = useMemo(() => {
    const out: number[] = [];
    let acc = 0;
    for (const s of run.steps) {
      out.push(acc);
      acc += s.duration;
    }
    return { offsets: out, total: acc };
  }, [run]);

  useEffect(() => {
    if (paused) return;
    let raf = 0;
    let lastT = performance.now();
    const loop = (t: number) => {
      const dt = t - lastT;
      lastT = t;
      setTick((prev) => {
        const next = prev + dt * 1.5;
        return next >= offsets.total ? offsets.total : next;
      });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [paused, offsets.total]);

  function stepIndexAtTime(t: number): number {
    for (let i = run.steps.length - 1; i >= 0; i--) {
      if (t >= offsets.offsets[i]!) return i;
    }
    return -1;
  }

  function stateOf(i: number): StepState {
    const startsAt = offsets.offsets[i]!;
    const step = run.steps[i]!;
    const endsAt = startsAt + step.duration;
    if (tick < startsAt) return "queued";
    if (tick < endsAt) return "running";
    if (step.key === "report") return "done";
    if (step.tests && step.tests.some((t) => t.status === "fail")) return "fail";
    return "done";
  }

  // Auto-expand the running step
  const expandKey = Math.floor(tick / 300);
  useEffect(() => {
    const idx = stepIndexAtTime(tick);
    if (idx >= 0) {
      const k = run.steps[idx]!.key;
      setExpanded((e) => (e[k] ? e : { ...e, [k]: true }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expandKey]);

  const pct = Math.min(100, Math.round((tick / offsets.total) * 100));
  const idx = Math.max(0, stepIndexAtTime(tick));
  const currentStep = run.steps[idx]!;
  const done = pct >= 100;

  const aggSoFar = useMemo(() => {
    let p = 0, f = 0, total = 0, cost = 0, tin = 0, tout = 0;
    run.steps.forEach((s, i) => {
      const st = stateOf(i);
      if (st === "queued" || st === "running") return;
      cost += s.costUsd ?? 0;
      tin += s.tokensIn ?? 0;
      tout += s.tokensOut ?? 0;
      if (s.tests) {
        for (const t of s.tests) {
          total++;
          if (t.status === "pass") p++;
          else if (t.status === "fail") f++;
        }
      }
    });
    const cur = stepIndexAtTime(tick);
    if (cur >= 0 && stateOf(cur) === "running") {
      const s = run.steps[cur]!;
      const localPct = Math.min(1, (tick - offsets.offsets[cur]!) / s.duration);
      cost += (s.costUsd ?? 0) * localPct;
      tin += Math.round((s.tokensIn ?? 0) * localPct);
      tout += Math.round((s.tokensOut ?? 0) * localPct);
    }
    return { p, f, total, cost, tin, tout };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  const activity = useMemo(() => {
    const out: Array<{ ts: string; agent: string; msg: string; kind: "ok" | "warn" | "fail" }> = [];
    out.push({ ts: "14:02:18", agent: "orchestrator", msg: "run.started run_a3f2b1c8 pr=4827 branch=feat/checkout-stacked-discounts", kind: "ok" });
    out.push({ ts: "14:02:19", agent: "policy_guard", msg: "policy.checked destructive_sql=false external_issues=approval", kind: "ok" });
    run.steps.forEach((s, i) => {
      const st = stateOf(i);
      if (st === "queued") return;
      const sec = String(18 + Math.floor(offsets.offsets[i]! / 1000)).padStart(2, "0");
      out.push({ ts: `14:02:${sec}`, agent: s.agent.split(".")[0]!, msg: `${s.agent} → ${s.title.toLowerCase()}`, kind: "ok" });
      if (s.tool) {
        const ts2 = String(18 + Math.floor((offsets.offsets[i]! + s.duration * 0.4) / 1000)).padStart(2, "0");
        const kind: "ok" | "warn" = s.tool.result.includes("fail") || s.tool.result.includes("anomaly") ? "warn" : "ok";
        out.push({ ts: `14:02:${ts2}`, agent: s.agent.split(".")[0]!, msg: `tool ${s.tool.name}(...) → ${s.tool.result}`, kind });
      }
      if (s.tests) {
        const failed = s.tests.find((t) => t.status === "fail");
        if (failed && st !== "running") {
          const ts3 = String(18 + Math.floor((offsets.offsets[i]! + s.duration * 0.7) / 1000)).padStart(2, "0");
          out.push({ ts: `14:02:${ts3}`, agent: s.agent.split(".")[0]!, msg: `✗ ${failed.name}`, kind: "fail" });
        }
      }
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tick]);

  function onOpenFailure(_id: string) {
    onNavigate("failures");
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Test run · {run.id}</h1>
          <p className="sub">
            PR #{run.pr.number} · branch <span className="mono">{run.pr.branch}</span> · started {run.startedAt}
          </p>
        </div>
        <div className="actions">
          <button
            className="btn btn-outline btn-sm"
            onClick={() => {
              setTick(0);
              setPaused(false);
            }}
          >
            <Icons.RefreshCw size={14} /> Replay
          </button>
          <button className="btn btn-default btn-sm" onClick={() => setPaused((p) => !p)}>
            {paused ? (
              <>
                <Icons.Play size={14} /> Resume
              </>
            ) : (
              <>
                <Icons.Pause size={14} /> Pause
              </>
            )}
          </button>
        </div>
      </div>

      <div className="run-progress">
        <div className="pct">
          {pct}
          <span style={{ fontSize: 14, color: "var(--sr-fg-muted)", fontWeight: 500 }}>%</span>
        </div>
        <div className="label">
          {done ? <strong>Run complete · evidence report posted</strong> : <strong>{currentStep.agent}</strong>}
          <div className="small">
            {done ? "10 agents · 21 tests · 1 product defect · risk 78" : currentStep.title}
          </div>
        </div>
        <ProgressBar pct={pct} />
        <div
          className="meta"
          style={{ fontSize: 12, color: "var(--sr-fg-muted)", fontFamily: "var(--sr-font-mono)" }}
        >
          {(tick / 1000).toFixed(1)}s / {(offsets.total / 1000).toFixed(1)}s
        </div>
      </div>

      <div className="run-context-card">
        <div className="row">
          <div className="col" style={{ flex: "1 1 360px" }}>
            <span className="lbl">Pull request</span>
            <div className="val" style={{ fontWeight: 600 }}>
              #{run.pr.number} · {run.pr.title}
            </div>
            <div className="val mono" style={{ color: "var(--sr-fg-muted)" }}>
              {run.pr.base} ← {run.pr.branch}
            </div>
          </div>
          <div className="col">
            <span className="lbl">Author</span>
            <div className="val" style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div className="avatar">{run.pr.authorAvatar}</div>
              {run.pr.author}
            </div>
          </div>
          <div className="col">
            <span className="lbl">Files</span>
            <span className="val">{run.pr.files} changed</span>
          </div>
          <div className="col">
            <span className="lbl">Diff</span>
            <span className="val mono">
              <span style={{ color: "var(--sr-success-fg)" }}>+{run.pr.additions}</span>
              {" · "}
              <span style={{ color: "var(--sr-danger-fg)" }}>−{run.pr.deletions}</span>
            </span>
          </div>
          <div className="col">
            <span className="lbl">Environment</span>
            <span className="val mono">staging</span>
          </div>
          <div className="col">
            <span className="lbl">Trigger</span>
            <span className="val mono">github.pull_request</span>
          </div>
        </div>
      </div>

      <div className="run-layout">
        <div className="card">
          <div className="card-head">
            <div>
              <div className="title">Agent timeline</div>
              <div className="desc">Vertical trace · click any step to expand evidence + tool calls.</div>
            </div>
            <div className="actions">
              <span className="badge badge-outline mono">{run.steps.length} agents</span>
            </div>
          </div>
          <div className="timeline">
            {run.steps.map((s, i) => (
              <TimelineItem
                key={s.key}
                step={s}
                state={stateOf(i)}
                expanded={!!expanded[s.key]}
                onToggle={() => setExpanded((e) => ({ ...e, [s.key]: !e[s.key] }))}
                onOpenFailure={onOpenFailure}
              />
            ))}
          </div>
        </div>

        <div className="live-panel">
          <div className="card">
            <div className="card-head">
              <div className="title">Live counters</div>
            </div>
            <div className="cost-grid">
              <div>
                <div className="k">Tests</div>
                <div className="v">
                  {aggSoFar.p}
                  <span style={{ color: "var(--sr-fg-muted)", fontSize: 13, fontWeight: 500 }}> / {aggSoFar.total || 21}</span>
                </div>
                <div className="s">{aggSoFar.f} fail</div>
              </div>
              <div>
                <div className="k">Cost</div>
                <div className="v">${aggSoFar.cost.toFixed(3)}</div>
                <div className="s">cap $5.00</div>
              </div>
              <div>
                <div className="k">Tokens in</div>
                <div className="v">{(aggSoFar.tin / 1000).toFixed(1)}k</div>
                <div className="s">/ run</div>
              </div>
              <div>
                <div className="k">Tokens out</div>
                <div className="v">{(aggSoFar.tout / 1000).toFixed(1)}k</div>
                <div className="s">/ run</div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <div className="title">Activity stream</div>
              <div className="actions">
                <span className="badge badge-info">
                  <span className="badge-dot" />live · sse
                </span>
              </div>
            </div>
            <div className="activity-stream">
              {activity
                .slice()
                .reverse()
                .map((a, i) => (
                  <div key={i} className={"row " + a.kind}>
                    <span className="ts">{a.ts}</span>
                    <span className="agent">{a.agent}</span>
                    <span className="msg" title={a.msg}>{a.msg}</span>
                  </div>
                ))}
            </div>
          </div>

          {done && (
            <div className="card">
              <div className="card-head">
                <div className="title">Outcome</div>
              </div>
              <div className="card-body">
                <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 10 }}>
                  <span className="badge badge-destructive">
                    <span className="badge-dot" />1 product defect
                  </span>
                  <RiskPill score={RISK.score} />
                </div>
                <div style={{ fontSize: 12.5, color: "var(--sr-fg-muted)", lineHeight: "18px", marginBottom: 12 }}>
                  Quality gate set to <strong style={{ color: "var(--sr-fg)" }}>BLOCK</strong>. Recommendation requires release-mgr override.
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="btn btn-outline btn-sm" onClick={() => onNavigate("failures")}>
                    Triage detail <Icons.ArrowRight size={12} />
                  </button>
                  <button className="btn btn-default btn-sm" onClick={() => onNavigate("risk")}>
                    Risk score <Icons.ArrowRight size={12} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ───────────── Failure triage ───────────── */

function FailuresScreen(): JSX.Element {
  const f = FAILURE;
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Failure · {f.id}</h1>
          <p className="sub">
            <span className="mono">{f.testName}</span>
          </p>
        </div>
        <div className="actions">
          <button className="btn btn-outline btn-sm">
            <Icons.Eye size={14} /> View test logs
          </button>
          <button className="btn btn-default btn-sm">
            <Icons.Bug size={14} /> Create Jira ticket
          </button>
        </div>
      </div>

      <div className="classification-head">
        <div className="cls-mark">
          <Icons.Bug />
        </div>
        <div className="cls-text">
          <div className="cls-label">Classification · classified by {f.agent}</div>
          <div className="cls-name">{f.classificationLabel}</div>
          <div className="cls-desc">{f.classificationDesc}</div>
        </div>
        <div className="conf">
          <div className="v">{(f.confidence * 100).toFixed(0)}%</div>
          <div className="l">confidence</div>
        </div>
      </div>

      <div className="fail-grid">
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <div className="card-head">
              <div className="title">Suspected root cause</div>
            </div>
            <div className="card-body">{f.suspectedCause}</div>
          </div>

          <div className="card">
            <div className="card-head">
              <div>
                <div className="title">Evidence</div>
                <div className="desc">Cross-referenced from logs, traces, git, history, and DB.</div>
              </div>
            </div>
            <div className="evidence-list">
              {f.evidence.map((e, i) => (
                <div key={i} className="evidence-item">
                  <div className="ev-dot">{i + 1}</div>
                  <div className="ev-text">
                    <strong>{e.text}</strong>
                    <span className="src">source · {e.src}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <div>
                <div className="title">Suspected diff</div>
                <div className="desc">
                  <span className="mono">apps/api/payments/authorizer.py</span> · introduced in PR #4827
                </div>
              </div>
            </div>
            <pre className="diff">
              <span className="hd">@@ -132,7 +132,18 @@ class PaymentsAuthorizer:</span>
              <span className="ctx">    def authorize(self, req: AuthorizeRequest) -&gt; AuthorizeResult:</span>
              <span className="ctx">        token = self._tokens.get(req.card_token)</span>
              <span className="del">-       if token is None or token.is_expired():</span>
              <span className="del">-           return AuthorizeResult.declined(&quot;expired_token&quot;)</span>
              <span className="add">+       if token is None:</span>
              <span className="add">+           return AuthorizeResult.declined(&quot;expired_token&quot;)</span>
              <span className="add">+</span>
              <span className="add">+       # Re-tokenize when stacked discount changes amount.</span>
              <span className="add">+       if req.discount_codes and len(req.discount_codes) {">"} 1:</span>
              <span className="add">+           token = self._tokens.refresh(token)   # ← raises if expired</span>
              <span className="ctx">        charge = self._provider.charge(token, req.amount_cents)</span>
              <span className="ctx">        return AuthorizeResult.from_provider(charge)</span>
            </pre>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="card">
              <div className="card-head">
                <div className="title">Request</div>
              </div>
              <pre className="payload">{f.request}</pre>
            </div>
            <div className="card">
              <div className="card-head">
                <div className="title">Response</div>
              </div>
              <pre className="payload">
                <span className="err">{f.response}</span>
              </pre>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="card">
            <div className="card-head">
              <div className="title">Recommended action</div>
            </div>
            <div className="card-body">
              <div style={{ fontSize: 11, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--sr-fg-muted)" }}>Owner</div>
              <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{f.recommendedOwner}</div>
              <div style={{ fontSize: 11, letterSpacing: ".04em", textTransform: "uppercase", color: "var(--sr-fg-muted)", marginTop: 14 }}>
                Suggested ticket
              </div>
              <div style={{ fontSize: 13, marginTop: 4, lineHeight: "18px" }}>{f.ticketTitle}</div>
              <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
                <button className="btn btn-outline btn-sm" style={{ flex: 1 }}>Reassign</button>
                <button className="btn btn-default btn-sm" style={{ flex: 1 }}>Open ticket</button>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <div className="title">Run context</div>
            </div>
            <div className="kv-grid">
              <div className="k">Run</div><div className="v mono">run_a3f2b1c8</div>
              <div className="k">Step</div><div className="v">api_test.agent</div>
              <div className="k">Test type</div><div className="v">api · contract</div>
              <div className="k">Tool</div><div className="v mono">newman.run</div>
              <div className="k">Latency</div><div className="v mono">412 ms</div>
              <div className="k">Retries</div><div className="v mono">3 of 3</div>
              <div className="k">Env</div><div className="v mono">staging</div>
            </div>
          </div>

          <div className="card">
            <div className="card-head">
              <div className="title">Flakiness · 30d</div>
            </div>
            <div className="card-body">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: "var(--sr-fg-muted)" }}>main branch</div>
                  <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>0 / 30</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "var(--sr-fg-muted)" }}>this branch</div>
                  <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, color: "var(--sr-danger-fg)" }}>3 / 4</div>
                </div>
              </div>
              <div style={{ fontSize: 12, color: "var(--sr-fg-muted)", marginTop: 10, lineHeight: "18px" }}>
                Signature first appeared on this branch. Not a flake — a regression.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────── Risk + gate ───────────── */

function RiskScreen({ onNavigate }: { onNavigate: (r: RouteKey) => void }): JSX.Element {
  const r = RISK;
  const ARC = 2 * Math.PI * 80;
  const filled = (r.score / 100) * ARC;
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Release risk · run_a3f2b1c8</h1>
          <p className="sub">Evidence-based score from QA signals · go/no-go recommendation requires human approval.</p>
        </div>
        <div className="actions">
          <button className="btn btn-outline btn-sm">Export report</button>
        </div>
      </div>

      <div className="risk-card">
        <div className="risk-gauge">
          <svg viewBox="0 0 200 200">
            <circle cx={100} cy={100} r={80} className="gauge-bg" />
            <circle
              cx={100}
              cy={100}
              r={80}
              className={"gauge-fg stroke-" + r.level}
              strokeDasharray={`${filled} ${ARC}`}
            />
          </svg>
          <div className="center">
            <div>
              <div className={"score risk-" + r.level}>{r.score}</div>
              <div className="out">/ 100</div>
              <div className={"level risk-" + r.level}>{r.level} risk</div>
            </div>
          </div>
        </div>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span className="badge badge-destructive">
              <span className="badge-dot" />
              {r.recommendation}
            </span>
            <span className="badge badge-outline mono">21 tests · 1 fail</span>
            <span className="badge badge-outline mono">3 acs covered / 4</span>
          </div>
          <div style={{ fontSize: 13, lineHeight: "20px", color: "var(--sr-fg-muted)", marginBottom: 14 }}>
            Risk drivers ranked by points contribution. Score floors at 0; the cap-at-100 model uses a logistic on weighted evidence (see{" "}
            <a className="mono" href="#" style={{ textDecoration: "underline" }}>ADR-0017</a>).
          </div>
          <div className="risk-drivers">
            {r.drivers.map((d, i) => (
              <div key={i} className="risk-driver">
                <div>
                  <div className="driver-label">{d.label}</div>
                  <div className="driver-sub">{d.sub}</div>
                </div>
                <div className="bar-track">
                  <div className={"bar-fill " + d.severity} style={{ width: (d.pts / 30) * 100 + "%" }} />
                </div>
                <div className="pts">+{d.pts}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ height: 16 }} />

      <div className="gate">
        <div>
          <div style={{ fontSize: 11, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--sr-fg-muted)" }}>Quality gate</div>
          <div className="recommendation">Block merge · awaiting release-mgr override</div>
          <ul className="reasons" style={{ margin: "4px 0 0", padding: 0, listStyle: "none" }}>
            {r.reasonsShort.map((x, i) => (
              <li key={i} style={{ display: "flex", gap: 8, marginTop: 4 }}>
                <span style={{ color: "var(--sr-danger-fg)" }}>•</span>
                {x}
              </li>
            ))}
          </ul>
          <div className="approvers">
            <span style={{ color: "var(--sr-fg-muted)" }}>Approvers required:</span>
            <div className="av-stack">
              <div className="avatar" title="release-mgr-1">RM</div>
              <div className="avatar" title="release-mgr-2">JD</div>
              <div className="avatar" title="payments-eng-lead">EK</div>
            </div>
            <span style={{ color: "var(--sr-fg-muted)" }}>1 of 2 release-mgrs · 1 of 1 eng lead</span>
          </div>
        </div>
        <div className="actions">
          <button className="btn btn-outline" onClick={() => onNavigate("failures")}>Inspect failure</button>
          <button className="btn btn-secondary">Override</button>
          <button className="btn btn-destructive">Block merge</button>
        </div>
      </div>
    </div>
  );
}

/* ───────────── Evidence report ───────────── */

function ReportScreen(): JSX.Element {
  const r = AGENT_RUN;
  const f = FAILURE;
  const risk = RISK;
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Evidence report</h1>
          <p className="sub">Auto-generated from run_a3f2b1c8 · posted to PR #4827 as a comment.</p>
        </div>
        <div className="actions">
          <button className="btn btn-outline btn-sm">
            <Icons.Code size={14} /> Markdown
          </button>
          <button className="btn btn-outline btn-sm">
            <Icons.FileText size={14} /> HTML
          </button>
          <button className="btn btn-default btn-sm">
            <Icons.GitPullRequest size={14} /> Re-post to PR
          </button>
        </div>
      </div>

      <div className="report-page">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 8 }}>
          <div>
            <h1 className="report-h1">QA evidence — PR #{r.pr.number}</h1>
            <p className="report-sub">{r.pr.title}</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <span className="badge badge-destructive">
              <span className="badge-dot" />BLOCK MERGE
            </span>
            <div style={{ fontSize: 11, color: "var(--sr-fg-muted)", fontFamily: "var(--sr-font-mono)", marginTop: 4 }}>
              run_a3f2b1c8 · 2026-05-06 14:04
            </div>
          </div>
        </div>

        <h2>Release summary</h2>
        <p>
          1 of 21 tests failed. Failure classified as a <strong>product defect</strong> in payments authorization with 86% confidence.
          Release risk scored <strong>78 / 100 — High</strong>. Recommended decision: block merge pending fix or release-mgr override.
        </p>

        <h2>Coverage</h2>
        <div className="coverage-mini">
          <div className="cell"><div className="k">API</div><div className="v">7</div><div className="s">6 pass · 1 fail</div></div>
          <div className="cell"><div className="k">UI</div><div className="v">6</div><div className="s">6 pass</div></div>
          <div className="cell"><div className="k">DB</div><div className="v">4</div><div className="s">3 pass · 1 anomaly</div></div>
          <div className="cell"><div className="k">E2E</div><div className="v">2</div><div className="s">1 pass · 1 partial</div></div>
        </div>

        <h2>Acceptance criteria</h2>
        <ul style={{ lineHeight: "24px" }}>
          {r.pr.acceptanceCriteria.map((ac, i) => (
            <li key={i}>
              {i < 3 ? <span style={{ color: "var(--sr-success-fg)" }}>✓</span> : <span style={{ color: "var(--sr-warning-fg)" }}>?</span>} {ac}
            </li>
          ))}
        </ul>

        <h2>Failures</h2>
        <div className="card" style={{ margin: "12px 0" }}>
          <div className="card-body">
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span className="badge badge-destructive">
                <span className="badge-dot" />product_defect
              </span>
              <span className="badge badge-outline mono">conf 0.86</span>
              <span style={{ fontSize: 11, color: "var(--sr-fg-muted)", fontFamily: "var(--sr-font-mono)" }}>{f.id}</span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6 }}>{f.testName}</div>
            <p style={{ fontSize: 13, color: "var(--sr-fg-muted)", margin: 0, lineHeight: "20px" }}>{f.suspectedCause}</p>
          </div>
        </div>

        <h2>Risk drivers</h2>
        <ul style={{ lineHeight: "22px" }}>
          {risk.drivers.map((d, i) => (
            <li key={i}>
              <strong>+{d.pts}</strong> · {d.label} <span style={{ color: "var(--sr-fg-muted)" }}>· {d.sub}</span>
            </li>
          ))}
        </ul>

        <h2>Cost &amp; latency</h2>
        <div className="coverage-mini">
          <div className="cell"><div className="k">Wall time</div><div className="v">45.7s</div><div className="s">10 agents</div></div>
          <div className="cell"><div className="k">Cost</div><div className="v">$0.123</div><div className="s">cap $5.00</div></div>
          <div className="cell"><div className="k">Tokens in</div><div className="v">57.0k</div><div className="s">{" "}</div></div>
          <div className="cell"><div className="k">Tokens out</div><div className="v">8.5k</div><div className="s">{" "}</div></div>
        </div>

        <h2>Approvals required</h2>
        <ul style={{ lineHeight: "22px" }}>
          <li>Release-mgr override · risk ≥ 60 policy</li>
          <li>External issue creation · Jira (defect_triage.agent)</li>
        </ul>
      </div>
    </div>
  );
}

/* ───────────── Evals ───────────── */

function EvalsScreen(): JSX.Element {
  const groups: Record<string, typeof EVAL_METRICS> = {};
  EVAL_METRICS.forEach((m) => {
    (groups[m.agent] = groups[m.agent] ?? []).push(m);
  });
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Agent evaluations</h1>
          <p className="sub">Golden-dataset scorecards · regression gate enforced on merge.</p>
        </div>
        <div className="actions">
          <button className="btn btn-outline btn-sm">
            <Icons.RefreshCw size={14} /> Re-run nightly suite
          </button>
          <button className="btn btn-default btn-sm">Compare to last run</button>
        </div>
      </div>

      <div className="stat-row">
        <div className="stat"><div className="k">Datasets</div><div className="v">12</div><div className="s">2,840 cases total</div></div>
        <div className="stat"><div className="k">Last run</div><div className="v">237</div><div className="s">cases evaluated · 14h ago</div></div>
        <div className="stat"><div className="k">Regressions</div><div className="v" style={{ color: "var(--sr-warning-fg)" }}>2</div><div className="s">vs. last green</div></div>
        <div className="stat"><div className="k">Cost</div><div className="v">$3.48</div><div className="s">/ nightly run</div></div>
      </div>

      <div className="eval-grid">
        {Object.entries(groups).map(([agent, metrics]) => (
          <div key={agent} className="card">
            <div className="card-head">
              <div>
                <div className="title">{agent}</div>
                <div className="desc">{metrics.length} metrics tracked</div>
              </div>
              <div className="actions">
                <button className="btn btn-ghost btn-sm">
                  Detail <Icons.ArrowRight size={12} />
                </button>
              </div>
            </div>
            <div>
              {metrics.map((m, i) => (
                <div key={i} className="metric-row">
                  <div className="label">{m.metric}</div>
                  <div className="bar-track">
                    <div className={"bar-fill " + (m.color === "ok" ? "" : m.color)} style={{ width: m.value * 100 + "%" }} />
                  </div>
                  <div className="val">{m.value.toFixed(2)}</div>
                  <div className="target">{m.target}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ───────────── Approvals · Audit · Prompts · Settings ───────────── */

function ApprovalsScreen(): JSX.Element {
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Approvals queue</h1>
          <p className="sub">Human-in-the-loop gates for destructive, external, or high-cost actions.</p>
        </div>
      </div>
      <div className="card">
        <div className="card-head">
          <div>
            <div className="title">{APPROVALS.length} pending</div>
            <div className="desc">Approvals expire after 24h.</div>
          </div>
        </div>
        <div>
          {APPROVALS.map((a) => {
            const IconCmp = getIcon(a.icon);
            return (
              <div key={a.id} className="approval-row">
                <div className="icon-w">{IconCmp ? <IconCmp /> : null}</div>
                <div>
                  <div className="title" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    {a.title}
                    {a.urgency === "high" && <span className="badge badge-destructive">high urgency</span>}
                  </div>
                  <div className="sub">{a.sub}</div>
                </div>
                <div className="actions">
                  <button className="btn btn-ghost btn-sm">Reject</button>
                  <button className="btn btn-default btn-sm">Approve</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function AuditScreen(): JSX.Element {
  const headerCellStyle: CSSProperties = {
    fontSize: 11,
    letterSpacing: ".04em",
    textTransform: "uppercase",
    color: "var(--sr-fg-muted)",
  };
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Audit log</h1>
          <p className="sub">Append-only · HMAC-SHA256-signed · 7-year retention lock.</p>
        </div>
        <div className="actions">
          <button className="btn btn-outline btn-sm">Export</button>
        </div>
      </div>
      <div className="card">
        <div className="toolbar">
          <input className="input" placeholder="filter by actor or target…" style={{ flex: 1, maxWidth: 280 }} />
          <select className="select">
            <option>all actions</option>
            <option>run.started</option>
            <option>risk.scored</option>
            <option>policy.checked</option>
          </select>
          <select className="select">
            <option>last 24h</option>
            <option>last 7d</option>
            <option>last 30d</option>
          </select>
        </div>
        <div>
          <div className="audit-row" style={{ background: "hsl(210 40% 98.5%)" }}>
            <div style={headerCellStyle}>Time</div>
            <div style={headerCellStyle}>Actor</div>
            <div style={headerCellStyle}>Action</div>
            <div style={headerCellStyle}>Target</div>
            <div style={{ ...headerCellStyle, textAlign: "right" }}>HMAC</div>
          </div>
          {AUDIT_EVENTS.map((e, i) => (
            <div key={i} className="audit-row">
              <div className="ts">2026-05-06 {e.ts}</div>
              <div className="actor">{e.actor}</div>
              <div className="target">{e.action}</div>
              <div className="target">{e.target}</div>
              <div className="sig">{e.sig}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PromptsScreen(): JSX.Element {
  const prompts = [
    { id: "planner.system", v: "v3.2.1", status: "active", updated: "3d ago", model: "claude-sonnet-4" },
    { id: "api_test.system", v: "v2.7.1", status: "active", updated: "1w ago", model: "claude-haiku-4-5" },
    { id: "ui_test.system", v: "v2.4.0", status: "active", updated: "2w ago", model: "claude-sonnet-4" },
    { id: "failure_classifier.system", v: "v4.1.0", status: "candidate", updated: "1d ago", model: "claude-sonnet-4" },
    { id: "release_risk.system", v: "v1.9.3", status: "active", updated: "5d ago", model: "claude-sonnet-4" },
    { id: "report.system", v: "v2.0.1", status: "active", updated: "12d ago", model: "claude-sonnet-4" },
  ];
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Prompt registry</h1>
          <p className="sub">Versioned prompts with A/B experiments and per-workspace pins.</p>
        </div>
        <div className="actions">
          <button className="btn btn-default btn-sm">
            <Icons.Plus size={14} /> New experiment
          </button>
        </div>
      </div>
      <div className="card">
        <table className="tbl">
          <thead>
            <tr>
              <th>Prompt</th>
              <th>Version</th>
              <th>Status</th>
              <th>Default model</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {prompts.map((p) => (
              <tr key={p.id} className="clickable">
                <td className="mono">{p.id}</td>
                <td className="mono">{p.v}</td>
                <td>
                  {p.status === "active" ? (
                    <span className="badge badge-success">
                      <span className="badge-dot" />active
                    </span>
                  ) : (
                    <span className="badge badge-warning">
                      <span className="badge-dot" />candidate
                    </span>
                  )}
                </td>
                <td className="mono muted">{p.model}</td>
                <td className="muted">{p.updated}</td>
                <td className="num">
                  <Icons.ArrowRight size={12} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SettingsScreen(): JSX.Element {
  const integrations: Array<{ name: string; sub: string; status: string }> = [
    { name: "GitHub", sub: "acme/payments-service · webhook v1", status: "connected" },
    { name: "Jira", sub: "acme.atlassian.net · project WPMT", status: "connected" },
    { name: "PagerDuty", sub: "service: payments-platform", status: "connected" },
    { name: "Slack", sub: "#qa-payments · #releases", status: "connected" },
    { name: "S3", sub: "evidence bucket · acme-aqa-evidence", status: "connected" },
  ];
  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Workspace settings</h1>
          <p className="sub">Agent policies, environments, and integrations.</p>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="card">
          <div className="card-head">
            <div>
              <div className="title">Agent policy</div>
              <div className="desc">Caps and approvals enforced per run.</div>
            </div>
          </div>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field">
              <label>Max cost per run</label>
              <input className="input" defaultValue="$5.00" />
            </div>
            <div className="field">
              <label>Max runtime</label>
              <input className="input" defaultValue="30 min" />
            </div>
            <div className="field">
              <label>Default DB mode</label>
              <select className="select">
                <option>read-only</option>
                <option>read-write (gated)</option>
              </select>
            </div>
            <div className="field">
              <label>Approvals required for</label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 2 }}>
                <span className="badge badge-secondary">destructive_sql</span>
                <span className="badge badge-secondary">production_test</span>
                <span className="badge badge-secondary">external_issue</span>
                <span className="badge badge-secondary">release_readiness</span>
                <span className="badge badge-secondary">ci_pipeline_change</span>
              </div>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-head">
            <div>
              <div className="title">Integrations</div>
              <div className="desc">Configured connectors.</div>
            </div>
          </div>
          <div>
            {integrations.map((it, i) => (
              <div key={i} className="approval-row">
                <div className="icon-w">
                  <Icons.Globe />
                </div>
                <div>
                  <div className="title">{it.name}</div>
                  <div className="sub">{it.sub}</div>
                </div>
                <div className="actions">
                  <span className="badge badge-success">
                    <span className="badge-dot" />
                    {it.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────── App ───────────── */

export default function ConsoleApp(): JSX.Element {
  const [route, setRoute] = useState<RouteKey>("runs");
  const [density, setDensity] = useState<"default" | "cozy">("default");

  const ws = ACTIVE_WS;

  let screen: ReactNode;
  switch (route) {
    case "workspaces":
      screen = <WorkspacesScreen onOpen={() => setRoute("dashboard")} />;
      break;
    case "dashboard":
      screen = <DashboardScreen onNavigate={setRoute} />;
      break;
    case "runs":
      screen = <TestRunScreen onNavigate={setRoute} autoplay />;
      break;
    case "failures":
      screen = <FailuresScreen />;
      break;
    case "risk":
      screen = <RiskScreen onNavigate={setRoute} />;
      break;
    case "report":
      screen = <ReportScreen />;
      break;
    case "evals":
      screen = <EvalsScreen />;
      break;
    case "approvals":
      screen = <ApprovalsScreen />;
      break;
    case "audit":
      screen = <AuditScreen />;
      break;
    case "prompts":
      screen = <PromptsScreen />;
      break;
    case "settings":
      screen = <SettingsScreen />;
      break;
  }

  return (
    <div className="aqa-console" data-density={density}>
      <div className="app">
        <Sidebar route={route} onNavigate={setRoute} ws={ws} />
        <div>
          <Topbar crumbs={ROUTES[route]} />
          <main data-screen-label={route}>{screen}</main>
        </div>
      </div>
      <DensityToggle density={density} onChange={setDensity} />
    </div>
  );
}

function DensityToggle({
  density,
  onChange,
}: {
  density: "default" | "cozy";
  onChange: (d: "default" | "cozy") => void;
}): JSX.Element {
  return (
    <div
      style={{
        position: "fixed",
        right: 16,
        bottom: 16,
        display: "flex",
        gap: 4,
        padding: 4,
        background: "var(--sr-bg-elevated)",
        border: "1px solid var(--sr-border)",
        borderRadius: 9999,
        boxShadow: "var(--sr-shadow-md)",
        fontSize: 11,
        zIndex: 50,
      }}
    >
      {(["default", "cozy"] as const).map((d) => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className={"btn btn-sm " + (density === d ? "btn-default" : "btn-ghost")}
          style={{ height: 26, padding: "0 12px", fontSize: 11, borderRadius: 9999 }}
        >
          {d}
        </button>
      ))}
    </div>
  );
}
