# Sample target application

The demo runs against `examples/checkout-demo/` — a tiny e-commerce
checkout API that ships with deliberately-buggy paths so QAForge has
something real to find.

## Layout

```text
examples/checkout-demo/
├── app/                 # FastAPI service
│   ├── main.py          # /cart, /checkout, /discount endpoints
│   ├── discount.py      # buggy: accepts negative discounts
│   └── models.py
├── tests/               # the deliberate bugs surface here
├── openapi.yaml         # consumed by the API tester agent
├── docker-compose.yml   # spins up Postgres + the API
└── README.md
```

## The shape of the bugs

Two bugs are seeded:

1. **Negative-discount acceptance** in `discount.py`. The PRD §21
   demo exploits this: a PR "lowers" the minimum-cart-for-free-ship
   threshold from $50 to $0, and a regression slips past in the
   discount validator.
2. **Race condition** on inventory decrement when two carts check
   out simultaneously — surfaces as flaky failures in the
   integration suite (which Story 3.3.2's classifier downgrades to
   `flaky_test` after the 14-day flip-rate exceeds 0.30).

Each bug exists to demonstrate one classifier category:

* Bug 1 → `product_defect` (high-confidence heuristic + LLM agree).
* Bug 2 → `flaky_test` (Story 3.3.2 override, despite the 5xx
  surface).

## Why this app

The PRD §21 scenario was chosen because:

* It's small enough to fit in a 90-second demo.
* It exercises three of QAForge's tool runners (Newman API, pytest,
  Playwright UI).
* It has a "destructive SQL" path (`DELETE FROM expired_carts`)
  that demonstrates Epic 2.1 + 2.2's approval gate.

## Status

The app folder is **scaffolded as part of Story 5.4** — the
top-level `README.md`, the `openapi.yaml`, and the test layout exist
under `examples/checkout-demo/`. The runtime app code is filled in
when a hosted cluster is ready (Story 5.5 onboarding); the
deliverable here is the *spec* the demo runs against.
