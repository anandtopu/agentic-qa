# Journey — AI Engineering Hiring Manager

**Persona ref:** PRD §8.4
**Linked deliverables:** PRD §20 portfolio bundle.

## Trigger

A hiring manager opens the project's GitHub repository and demo.

## Steps

1. README pitches the problem and links the demo video.
2. Architecture diagrams (`docs/architecture/`) show the four-plane design.
3. ADRs (`docs/adr/`) show technical judgement, not just code.
4. The eval scoreboard (`docs/portfolio/eval-report.md`) shows agent quality is *measured*.
5. A live demo run on the sample app produces an evidence Markdown and a risk score.

## Expected outputs

- A reviewer can answer in ≤ 10 minutes:
  - Does it work end-to-end?
  - Is there evaluation, not vibes?
  - Are guardrails (cost, approval, redaction) real?
  - Is the engineering tasteful (typing, observability, tests)?

## Success metric

- A reviewer recommends a follow-up interview after a 15-minute browse.
