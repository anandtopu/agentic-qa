# Generated test plans

Three real planner outputs, each demonstrating a different angle.
The plans are produced by `qaforge_agents.planner.PlannerAgent`
against the sample requirements; format follows PRD §9.3.

## Plan 1 — checkout discount regression

**Source requirement** (excerpt):

> As a buyer, I should be able to apply at most one valid discount
> at checkout. Negative discounts must be rejected with HTTP 422.

**Output** (truncated to keep this page readable):

```json
{
  "plan_version": "1.0",
  "agent_name": "planner",
  "test_cases": [
    {
      "id": "tc-001",
      "name": "valid_percentage_discount_applied",
      "type": "api",
      "priority": "high",
      "preconditions": ["user with cart total $100", "discount=PROMO10"],
      "steps": [
        "POST /cart/discount with {code: PROMO10}",
        "GET /cart"
      ],
      "expected": "cart total = $90; discount.code=PROMO10",
      "negative": false
    },
    {
      "id": "tc-002",
      "name": "negative_discount_rejected",
      "type": "api",
      "priority": "critical",
      "preconditions": ["user with cart total $100"],
      "steps": [
        "POST /cart/discount with {code: NEG, value: -10}"
      ],
      "expected": "HTTP 422 with errors[].field=value",
      "negative": true
    }
  ]
}
```

The plan includes 4 cases total — 2 API + 1 UI + 1 DB invariant.

## Plan 2 — auth middleware refactor

A diff-only change with no requirement update — the planner derives
the test plan from the diff alone (Story 1.2.1 PR-diff parser).
Demonstrates the planner's ability to **detect risk areas** when
the requirement is silent.

Top cases produced:

* `auth_required_endpoints_return_401_without_token`
* `auth_required_endpoints_return_403_without_role`
* `expired_token_returns_401_with_retry_after`
* `revoked_token_returns_401`
* `cors_preflight_unaffected`

## Plan 3 — payment provider swap

Demonstrates **negative-test prioritisation**. The planner notices
the swap is a security-sensitive area (PRD §9.9 input) and weights
the negative cases higher — 60% of the generated cases are negative
or boundary tests.

```text
Generated 15 test cases:
  - 9 negative (declined card, expired card, 3DS failure, idempotency
    conflict, double-charge prevention, refund-of-refund, currency
    mismatch, amount > balance, fraud-block fall-through)
  - 6 happy-path (single charge, partial refund, refund full, etc.)
```

## Reading the plans

Each plan is consumed by:

1. **API tester agent** — produces a `pytest+httpx` file (Story
   1.4.1) AST-validated before it leaves the agent.
2. **UI tester agent** — produces Playwright TS (Story 1.5.1).
3. **DB validator agent** — produces read-only SELECTs against the
   schema (Story 2.2.1).

The runner orchestrates them through the workflow graph; failures
flow into the classifier (Story 1.7); the report renderer
(Story 1.8) ties everything together.
