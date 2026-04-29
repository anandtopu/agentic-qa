# ADR-0006: Frontend stack — Next.js 14 (App Router) + TypeScript + Tailwind + Recharts

- **Status:** Accepted
- **Date:** 2026-04-28
- **Deciders:** Tech lead
- **Consulted:** Design
- **Informed:** All eng

## Context

PRD §17 names Next.js + React + Tailwind + Recharts. The dashboard (PRD §11.1, Story 1.3.3 plan-review UI, Story 2.1.3 approval queue, cost dashboards in Story 2.5.2) is mostly:

- read-heavy lists/tables of runs, evidence, approvals;
- moderately interactive editors (test plan diff/accept-reject, policy YAML);
- charts over time-series (cost, latency, eval scores).

We need server-rendered initial loads (auth-protected dashboards), good caching of read endpoints, and a single deployment target.

## Decision

The web app is **Next.js 14 with the App Router**, **TypeScript 5**, **Tailwind CSS 3**, **Recharts** for visualisation, and **TanStack Query** for client-side data fetching with cache. Specifics:

- **Auth**: NextAuth.js with a backend-issued JWT; cookies are `httpOnly`, `Secure`, `SameSite=Lax`. SSO providers added in Phase 3 (Story 3.1.3) plug in here.
- **Server Components** for read-only dashboards; **Client Components** only where state or interactivity demands.
- **Form library**: React Hook Form + Zod; Zod schemas regenerated from `apis/openapi.yaml` so client and server validation match.
- **API client**: generated TS SDK from OpenAPI (Story 0.2.4) — no hand-written `fetch` calls in feature code.
- **Build**: Next.js standalone output, containerised; deployed in the same Helm chart as the API.
- **Workspace**: pnpm workspace; `apps/web` consumes `packages/web-shared` (TBD) for shared types.

Accessibility baseline: WCAG 2.1 AA; Radix UI primitives where possible; Storybook for component review.

## Consequences

- **Positive:** matches PRD §17; large hiring pool; strong SSR + caching story aligns with read-heavy dashboards; same Tailwind/Radix/Recharts stack scales cleanly into Phase 2/3 surfaces.
- **Negative:** App Router is the third major Next.js paradigm in five years — the team should expect occasional churn on best practices, and we'll pin a specific minor version with a quarterly upgrade ritual.
- **Neutral:** Node 20 LTS becomes a runtime dependency for builds and SSR pods; we accept polyglot operations (Python API + Node web).

## Alternatives considered

- **Plain React (Vite) SPA** — simpler build, but loses SSR caching and we'd reinvent auth-redirect dance for every page.
- **Remix** — comparable DX and arguably cleaner data loading, but smaller ecosystem and our charting/auth libraries lean Next.js.
- **SvelteKit** — strong technical merits, but a smaller hiring pool and the team's TypeScript/React mental model would not transfer.
- **Pages Router (Next.js 13 stable)** — proven, but Vercel and the wider ecosystem are clearly moving to App Router; starting on the legacy router would mean migrating mid-Phase 2.

## References

- PRD §17 (Tech stack), §11.1 (Control plane surfaces)
- Story 1.3.3, Story 2.1.3, Story 2.5.2
- ADR-0004 (LLM provider abstraction — informs streaming UI)
