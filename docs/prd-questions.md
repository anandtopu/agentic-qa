# PRD Open Questions Log

Append-only. Resolve a question by editing it in place with the resolution
and an ADR / scope-baseline link; never delete.

| # | Section | Question | Severity | Owner | Status | Resolution |
|---|---|---|---|---|---|---|
| Q-001 | §9.6 | Is destructive SQL ever permitted *with* approval, or always blocked? | P0 | Eng + Security | Open | — |
| Q-002 | §9.7 | Are the integration "scenarios" co-located with API/UI test definitions or a separate object? | P1 | Eng | Open | — |
| Q-003 | §9.9 | What weights does the v1 risk rubric use? Are they per-workspace tunable? | P0 | ML eng | Open | — |
| Q-004 | §9.10 | Approval expiry default and per-event override — values? | P1 | Product | Open | — |
| Q-005 | §9.13 | Where do "real-world-like" eval scenarios come from at MVP-2? Synthetic only or sourced from a partner? | P1 | Product | Open | — |
| Q-006 | §10.3 | Does `max_cost_usd_per_run` count human-approval-time spend or only agent spend? | P1 | Eng + Product | Open | — |
| Q-007 | §11.1 | Is "user management" SCIM-required at MVP-3, or local-only acceptable? | P2 | Product | Open | — |
| Q-008 | §13 | API versioning policy: URL-path (`/v1`) confirmed; is breaking-change cadence committed? | P1 | Tech lead | Open | — |
| Q-009 | §14.5 | Are perf targets P50, P95, or P99? PRD reads ambiguous. | P0 | Tech lead | Open | — |
| Q-010 | §17 | LangGraph vs. custom — pinned in ADR-0002 or revisit after Phase-1 spike? | P0 | Tech lead | Open | — |

## Severity

- **P0** — must resolve before the section is implemented.
- **P1** — must resolve within the implementing phase.
- **P2** — can defer to a later phase.
