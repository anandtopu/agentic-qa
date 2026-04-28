## Summary

<!-- 1–3 bullets on the change and the why. Link the IMPLEMENTATION_PLAN story. -->

## Story / Epic

- Plan reference: `docs/IMPLEMENTATION_PLAN.md` §
- PRD reference: `AgenticQA_PRD.md` §

## Definition of Done

- [ ] CI green (lint, typecheck, tests, secrets scan, build)
- [ ] New code covered by unit tests; integration tests where needed
- [ ] Docs updated (README / ADR / runbook / OpenAPI as applicable)
- [ ] Observability: traces / metrics / structured logs emitted
- [ ] Cost & latency tracked for any new agent or tool call
- [ ] Secret-redaction test covers any new sink
- [ ] Feature-flagged if user-facing and not yet GA
- [ ] Rollback plan noted (DB / queue / artifact changes only)

## Test plan

<!-- How a reviewer can validate the change locally. -->

## Risk

<!-- Blast radius, impacted users/tenants, mitigations. -->
