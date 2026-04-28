# Journey — QA Engineer

**Persona ref:** PRD §8.1
**Linked success metrics:** PRD §19 — generated test cases executable ≥ 70%, classification accuracy ≥ 80%

## Trigger

A QA engineer wants to expand coverage on a feature about to ship.

## Steps

1. Open workspace → upload acceptance criteria (Markdown) or paste user story.
2. Trigger Test Plan generation; review in the diff UI; accept / edit cases.
3. Promote accepted cases into the API and UI test suites.
4. Run the suite against staging.
5. For each failure, the Triage tab shows classification, evidence, and a suggested ticket title.

## Expected outputs

- Structured test plan with ≥ 1 case per acceptance criterion.
- Open questions surfaced where AC are ambiguous.
- Evidence Markdown for any failed case (screenshot, trace link, request/response, DB diff).

## Success metric

- Median time from "I have a story" to "tests are running" ≤ 15 minutes.
- ≥ 70% of generated cases run without manual edits.
