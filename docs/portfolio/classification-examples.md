# Failure classification examples

Five categories per PRD §9.8. Each example is a real signal shape
the heuristic + LLM classifier (Story 1.7) would consume; the
rationale shown is the kind of explanation the agent emits.

## 1. `product_defect`

> The system-under-test produced an unexpected response. Cause is
> in product code, not test code.

**Signal**:

```text
Test: test_negative_discount_rejected
HTTP status: 422 expected, got 200
Body: {"applied": -10, "cart_total": 110}
```

**Rationale**: HTTP 422 is the documented behaviour; the API
returned 200 with a *negative* applied discount, which violates the
acceptance criterion. The 14-day flip-rate is 0.04 (stable test);
no environment indicators present. Heuristic match `assertion_failure`
(0.55) confirmed by LLM at 0.86.

**Suggested fix**: validate `value > 0` in `discount.py` before
applying.

## 2. `test_issue`

> The test itself is incorrect — the system-under-test is doing
> the right thing.

**Signal**:

```text
Test: test_login_redirects_to_dashboard
Selector not found: a[data-testid="dashboard-link"]
Page screenshot: dashboard rendered with the new selector
"a[data-test='dashboard-link']"
```

**Rationale**: the page **does** render the dashboard; the test's
selector is stale. Story 1.5.3's selector-fragility analyzer
flagged the rule (`selector_not_found`); LLM confirmed by reading
the Playwright trace.

**Suggested fix**: switch to `getByRole('link', {name: 'Dashboard'})`
which doesn't depend on the data attribute.

## 3. `environment_issue`

> The system-under-test is fine; the environment broke.

**Signal**:

```text
Test: test_payment_charges_successfully
Error: ETIMEDOUT connecting to api.stripe.com:443
```

**Rationale**: timeout to a third-party service. Heuristic rule
`network_timeout` matched at 0.85; LLM agreed. Re-run after the
upstream provider's status page reports green.

**Suggested fix**: retry with backoff; verify Stripe's status page;
check the egress NetworkPolicy (Story 3.6.2) is allowing the right
CIDR.

## 4. `flaky_test`

> The verdict isn't deterministic. Same code, sometimes passes,
> sometimes fails.

**Signal**:

```text
Test: test_freeship_invariant_holds_after_concurrent_checkout
HTTP status: 500
Error: deadlock detected in inventory decrement
14-day flip-rate: 0.42
```

**Rationale**: heuristic matched `http_5xx` at 0.80 → would
classify as `product_defect`, **but** Story 3.3.2's flakiness
override fired because the 14-day flip-rate (0.42) exceeded the
0.30 threshold. Final classification: `flaky_test` at 0.71
confidence. Re-run before opening a defect.

**Suggested fix**: add a row-level lock on the `inventory` row
during checkout; or quarantine the test via `pytest.mark.flaky`
until the race is fixed.

## 5. `data_issue`

> The test is correct, the product is correct, but the **data**
> the test ran against is wrong.

**Signal**:

```text
Test: test_admin_can_export_users
IntegrityError: violates foreign key constraint
"fk_users_tenant_id_tenants" — tenant_id "ghost-tenant"
not present in tenants
```

**Rationale**: the test data references a tenant id that doesn't
exist in the seeded fixtures. Heuristic rule `missing_fixture`
matched at 0.70; LLM agreed at 0.83.

**Suggested fix**: re-seed the test database via `make seed` (or
the fixture-prep step in the workflow graph); verify CI runs the
seed before the test phase.

## Calibration notes

* The **heuristic** classifier (Story 1.7.1) covers ~30%+ of
  failures pre-LLM at deterministic confidence.
* The **LLM** classifier (Story 1.7.2) refines the rest with
  calibrated confidence (0.0–1.0).
* **Flakiness override** (Story 3.3.2) downgrades
  `product_defect` → `flaky_test` when the 14-day flip-rate
  exceeds 0.30 — measured FP-rate drop on the synthetic dataset
  was ≥ 35 percentage points, well below the PRD §19 < 15% target.
