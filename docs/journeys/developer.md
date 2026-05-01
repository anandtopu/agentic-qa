# Journey — Developer

**Persona ref:** PRD §8.2
**Linked success metric:** PRD §19 — PR feedback latency < 10 minutes.

## Trigger

A developer opens a pull request.

## Steps

1. PR opened → GitHub webhook hits Agentic QA Orchestrator.
2. Agentic QA Orchestrator analyses diff, generates a targeted test plan, runs API/UI/DB tests, classifies failures.
3. A single PR comment summarises: risk badge, top failures with evidence links, recommended action.
4. If the risk gate is breached, the merge is blocked.
5. Developer clicks the evidence link; reviews trace, request/response, and suggested fix.

## Expected outputs

- One PR comment, updated in place across pushes.
- Direct links to the trace viewer, screenshots, and DB diffs.
- Suggested fix sketch where the classifier confidence is high.

## Success metric

- PR feedback in ≤ 10 minutes after push.
- False-positive defect rate < 15% (PRD §19).
