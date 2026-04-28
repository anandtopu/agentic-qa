# PRD: Agentic Software QA Platform

## Product Name

**QAForge AI — Agentic Software Quality Engineering Platform**

## 1. Executive Summary

QAForge AI is a production-ready, agentic software QA platform that orchestrates specialized AI agents to plan, execute, validate, triage, and report software testing across modern release pipelines.

The platform is designed to demonstrate practical AI engineering beyond chatbots: tool-using agents, workflow orchestration, human approval gates, CI/CD integration, test evidence generation, reliability evaluation, and enterprise-grade auditability.

## 2. Problem Statement

Software teams struggle with fragmented QA workflows:

| Problem                                          | Impact                                        |
| ------------------------------------------------ | --------------------------------------------- |
| Manual test planning is slow                     | Releases get delayed                          |
| API, UI, DB, and integration tests live in silos | Poor coverage visibility                      |
| Test failures are noisy                          | Engineers waste time triaging false positives |
| Release risk is subjective                       | Defects escape into production                |
| AI testing tools lack governance                 | Unsafe automation in CI/CD                    |
| Agent outputs are not evaluated                  | No trust in automated QA decisions            |

## 3. Product Vision

Build an autonomous but controlled QA platform where AI agents assist test engineers throughout the release lifecycle:

```text
Requirement / PR / Release Candidate
→ Test Plan Agent
→ API/UI/DB Test Agents
→ Execution Orchestrator
→ Failure Classifier
→ Defect Triage Agent
→ Release Risk Scorer
→ Human Approval Gate
→ Evidence Report
```

## 4. Target Users

### Primary Users

* QA Engineers
* SDETs
* AI Engineers
* Platform Engineers
* Release Managers

### Secondary Users

* Developers
* Engineering Managers
* Product Managers
* Compliance Reviewers

## 5. Goals

### Product Goals

* Automate test planning from requirements, PR diffs, API specs, and user stories.
* Execute API, UI, integration, and database validation tests.
* Classify failures as product defect, test issue, environment issue, flaky test, data issue, or unknown.
* Generate human-readable test evidence reports.
* Provide release risk scoring.
* Integrate with GitHub Actions.
* Measure agent reliability, false positives, latency, and cost.

### Portfolio Goals

This project should demonstrate:

* Agentic AI system design
* Tool orchestration
* Production workflow automation
* Human-in-the-loop controls
* CI/CD integration
* Evaluation framework design
* Practical QA domain expertise
* Reliability engineering mindset

## 6. Non-Goals

* Replacing all QA engineers.
* Fully autonomous production deployment approvals.
* Building a generic LLM chatbot.
* Building a commercial test management system clone.
* Supporting every test framework in v1.

## 7. Core Differentiators

1. **Specialized QA agents instead of one generic agent**
2. **Tool execution with Playwright, Newman/Postman, pytest, SQL validators**
3. **Release risk scoring based on evidence, not vibes**
4. **Human approval gates for destructive or high-risk actions**
5. **Failure classification and defect triage**
6. **Evaluation suite for agent quality**
7. **CI/CD-native execution model**
8. **Test evidence reports suitable for engineering leadership**

## 8. User Personas

## 8.1 QA Engineer

**Need:** Generate and execute meaningful test coverage faster.
**Pain:** Manual test planning and flaky failure triage consume time.
**Success:** Receives actionable test plans, failure summaries, and evidence reports.

## 8.2 Developer

**Need:** Fast feedback on PR quality.
**Pain:** CI failures are hard to interpret.
**Success:** Gets precise failure reason, affected area, logs, screenshots, and suggested fix.

## 8.3 Release Manager

**Need:** Know whether a release is safe.
**Pain:** Risk decisions are spread across test tools, Jira, GitHub, and Slack.
**Success:** Gets a release risk score with supporting evidence.

## 8.4 AI Engineering Hiring Manager

**Need:** Evaluate whether the candidate can build production AI systems.
**Signal:** Sees agent orchestration, tool calling, evaluation, security, cost tracking, and real workflow integration.

# 9. Functional Requirements

## 9.1 Project Workspace Management

### Description

Users create workspaces for applications under test.

### Requirements

Each workspace shall support:

* Application metadata
* Environment configuration
* Test suites
* API specs
* Database connection profiles
* Browser test profiles
* CI/CD integration settings
* Agent policy configuration

### Workspace Fields

```json
{
  "workspace_id": "uuid",
  "name": "Payments Platform",
  "repo_url": "https://github.com/org/payments-service",
  "default_branch": "main",
  "application_type": "web_api",
  "environments": ["dev", "staging", "prod"],
  "created_by": "user_id"
}
```

## 9.2 Requirement and Change Ingestion

### Inputs

QAForge AI shall ingest:

* User stories
* Acceptance criteria
* PR diffs
* OpenAPI specs
* Postman collections
* Database schemas
* Existing test cases
* Release notes
* Bug history
* Production incident history

### Supported Sources

* GitHub repository
* Uploaded markdown files
* OpenAPI JSON/YAML
* Postman collection JSON
* SQL schema files
* Jira export files
* Manual text input

## 9.3 Test Planning Agent

### Purpose

Generate structured test plans from requirements, code changes, API specs, and risk context.

### Responsibilities

* Identify test scope.
* Map acceptance criteria to test cases.
* Recommend API, UI, DB, integration, negative, regression, and smoke tests.
* Detect missing acceptance criteria.
* Flag ambiguous requirements.
* Estimate risk by changed module.

### Output

```json
{
  "test_plan_id": "uuid",
  "summary": "Regression plan for checkout changes",
  "coverage_areas": [
    "checkout API",
    "payment authorization",
    "order confirmation UI"
  ],
  "test_cases": [
    {
      "title": "Successful payment authorization",
      "type": "api",
      "priority": "high",
      "preconditions": ["valid customer", "active payment method"],
      "steps": ["POST /payments/authorize"],
      "expected_result": "authorization status is APPROVED",
      "automation_candidate": true
    }
  ],
  "open_questions": [
    "Should failed 3DS authentication retry automatically?"
  ]
}
```

## 9.4 API Testing Agent

### Purpose

Convert API specs and requirements into executable API tests.

### Tools

* Postman/Newman
* pytest + httpx
* OpenAPI validator
* Schemathesis optional

### Requirements

The API Testing Agent shall:

* Generate contract tests from OpenAPI specs.
* Generate positive and negative tests.
* Validate response status, schema, headers, and business rules.
* Support auth injection.
* Execute tests in CI.
* Capture request/response evidence with secrets redacted.

### Example Test Categories

* Happy path
* Authentication failure
* Authorization failure
* Invalid payload
* Boundary values
* Rate limiting
* Idempotency
* Backward compatibility
* Error schema consistency

## 9.5 UI Testing Agent

### Purpose

Generate and execute browser-based tests.

### Tools

* Playwright
* Accessibility checker
* Visual snapshot comparison optional

### Requirements

The UI Testing Agent shall:

* Generate Playwright tests from user journeys.
* Execute cross-browser smoke tests.
* Capture screenshots, videos, console logs, and network logs.
* Detect selector fragility.
* Recommend stable locator strategies.
* Validate core flows such as login, checkout, onboarding, dashboard, search, and settings.

### Evidence

For each UI failure:

* Screenshot
* Video trace
* DOM snapshot
* Browser console logs
* Network error summary
* Failing selector
* Suggested locator improvement

## 9.6 Database Validation Agent

### Purpose

Validate data correctness before and after test execution.

### Tools

* SQL validators
* pytest database fixtures
* Great Expectations optional

### Requirements

The DB Validation Agent shall:

* Validate schema constraints.
* Compare pre/post test state.
* Detect orphan records.
* Validate audit trail records.
* Verify transaction consistency.
* Run read-only SQL by default.
* Require human approval for destructive SQL.

### Supported Databases

* PostgreSQL for v1
* MySQL optional
* SQLite for local demo mode

## 9.7 Integration Testing Agent

### Purpose

Validate end-to-end workflows across services.

### Requirements

The Integration Testing Agent shall:

* Compose API, UI, and DB checks into scenario tests.
* Validate distributed workflow states.
* Correlate test evidence across systems.
* Detect partial failures.
* Verify compensating transactions.

### Example Scenario

```text
User places order
→ payment authorized
→ order record created
→ confirmation email event emitted
→ UI displays successful order
```

## 9.8 Defect Triage Agent

### Purpose

Analyze failed tests and produce actionable defect summaries.

### Inputs

* Test logs
* Stack traces
* Screenshots
* API responses
* Git diff
* Recent commits
* Database validation results
* Historical flaky test data

### Failure Classification

The platform shall classify failures as:

* Product defect
* Test automation defect
* Environment issue
* Test data issue
* Flaky test
* Dependency failure
* Configuration issue
* Unknown

### Output

```json
{
  "failure_id": "uuid",
  "classification": "product_defect",
  "confidence": 0.86,
  "suspected_root_cause": "Payment API returns 500 when card token is expired.",
  "evidence": [
    "POST /payments/authorize returned 500",
    "Stack trace points to CardTokenValidator",
    "Recent PR modified token expiry handling"
  ],
  "recommended_owner": "payments-backend-team",
  "suggested_ticket_title": "Payment authorization fails for expired card token"
}
```

## 9.9 Release Risk Scoring Agent

### Purpose

Produce a release readiness score from objective QA signals.

### Inputs

* Test pass/fail results
* Changed files and components
* Historical defect density
* Severity of failed tests
* Uncovered acceptance criteria
* Flakiness score
* Production incident history
* Code ownership
* Security-sensitive area indicators

### Risk Score

```text
0–30   Low risk
31–60  Medium risk
61–80  High risk
81–100 Critical risk
```

### Risk Explanation

The score must include:

* top risk drivers
* failed critical tests
* untested high-risk areas
* flaky test impact
* recommended go/no-go decision
* required human approvals

## 9.10 Human Approval Gates

### Required Approval Events

Human approval shall be required for:

* destructive SQL execution
* production environment tests
* creating external Jira/GitHub issues
* approving release readiness
* modifying CI pipeline files
* running high-cost eval jobs

### Approval States

```text
pending
approved
rejected
expired
cancelled
```

## 9.11 Evidence Report Generator

### Purpose

Generate executive and engineering-level test evidence.

### Report Formats

* Markdown
* HTML
* PDF optional
* GitHub PR comment
* CI artifact

### Report Sections

* Release summary
* Scope tested
* Test coverage matrix
* Pass/fail summary
* Failure classification
* Risk score
* Screenshots and logs
* API evidence
* DB validation evidence
* Agent confidence
* Cost and latency
* Human approvals
* Go/no-go recommendation

## 9.12 CI/CD Integration

### GitHub Actions Integration

The platform shall support:

* PR-triggered test planning
* Changed-file risk analysis
* API/UI/DB test execution
* Evidence artifact upload
* PR comment summary
* Quality gate enforcement

### Example Workflow

```text
Pull Request Opened
→ QAForge AI analyzes PR diff
→ Generates targeted test plan
→ Executes relevant tests
→ Classifies failures
→ Posts evidence report to PR
→ Blocks merge if critical risk
```

## 9.13 Agent Evaluation Suite

### Purpose

Measure whether agents are useful, reliable, and cost-effective.

### Evaluation Dimensions

| Dimension             | Metric                         |
| --------------------- | ------------------------------ |
| Test planning quality | acceptance criteria coverage   |
| API test quality      | valid executable test rate     |
| UI test quality       | stable selector rate           |
| Failure triage        | classification accuracy        |
| False positives       | incorrect defect rate          |
| Cost                  | cost per run                   |
| Latency               | time per workflow              |
| Human override rate   | rejected recommendations       |
| Reliability           | successful tool execution rate |

### Golden Dataset

The platform shall include synthetic and real-world-like evaluation scenarios:

* broken API response schema
* flaky UI selector
* missing DB transaction
* invalid test data
* environment outage
* authorization bug
* regression in checkout flow
* false positive test failure

## 10. Agent Architecture

## 10.1 Agent Types

```text
Planner Agent
API Test Agent
UI Test Agent
DB Validation Agent
Integration Test Agent
Failure Classifier Agent
Defect Triage Agent
Release Risk Agent
Report Agent
Policy Guard Agent
```

## 10.2 Agent Orchestration Pattern

Recommended implementation:

```text
Workflow Orchestrator
→ Agent Task Planner
→ Tool Router
→ Tool Executor
→ Evidence Store
→ Evaluator
→ Human Approval Service
→ Report Generator
```

## 10.3 Agent Guardrails

Each agent must operate under policies:

```yaml
policy:
  allow_write_operations: false
  require_approval_for:
    - destructive_sql
    - production_test_execution
    - external_ticket_creation
  redact_secrets: true
  max_cost_usd_per_run: 5.00
  max_runtime_minutes: 30
```

## 11. Platform Modules

## 11.1 Control Plane

* Workspace management
* User management
* Agent policies
* Environment configuration
* Approval workflows
* Audit logs

## 11.2 Execution Plane

* Test execution workers
* Tool runners
* Browser automation runtime
* API test runtime
* DB validation runtime

## 11.3 Intelligence Plane

* Agent orchestration
* Prompt templates
* Retrieval over repo/docs/test history
* Failure classification
* Release risk scoring

## 11.4 Evaluation Plane

* Golden datasets
* Agent scoring
* Regression tracking
* Cost and latency analytics

## 12. Data Model Overview

Core entities:

```text
tenants
users
workspaces
repositories
environments
requirements
test_plans
test_cases
test_runs
test_results
tool_invocations
agent_tasks
failure_classifications
defect_recommendations
release_risk_scores
approval_requests
evidence_artifacts
evaluation_datasets
evaluation_runs
evaluation_scores
audit_events
usage_records
```

## 13. API Surface

Recommended API groups:

```text
/api/v1/workspaces
/api/v1/repositories
/api/v1/requirements
/api/v1/test-plans
/api/v1/test-runs
/api/v1/agents/tasks
/api/v1/failures/classify
/api/v1/risk/release
/api/v1/approvals
/api/v1/reports
/api/v1/evaluations
/api/v1/audit
/api/v1/usage
```

## 14. Non-Functional Requirements

## 14.1 Reliability

* Tool execution retry with bounded attempts.
* Idempotent test run creation.
* Dead-letter queue for failed tasks.
* Durable evidence storage.
* Graceful degradation if LLM provider fails.

## 14.2 Security

* OAuth2/JWT authentication.
* RBAC for workspace access.
* Secret redaction in logs and reports.
* Read-only DB mode by default.
* Signed CI webhook verification.
* Encrypted evidence storage.
* Audit trail for all agent decisions.

## 14.3 Scalability

* Stateless API services.
* Async workers for test execution.
* Horizontally scalable browser runners.
* Queue-based execution model.
* Artifact storage in S3/GCS-compatible storage.

## 14.4 Observability

* Trace every agent step.
* Store tool inputs/outputs with redaction.
* Measure latency by workflow stage.
* Track token usage and cost.
* Dashboard for failed workflows, flaky tests, and agent quality.

## 14.5 Performance

Target v1 benchmarks:

| Capability                 | Target       |
| -------------------------- | ------------ |
| PR analysis                | < 60 seconds |
| Test plan generation       | < 90 seconds |
| API smoke execution        | < 3 minutes  |
| UI smoke execution         | < 10 minutes |
| Failure classification     | < 60 seconds |
| Evidence report generation | < 30 seconds |

## 15. System Architecture

```text
Frontend Dashboard
       ↓
API Gateway / FastAPI Backend
       ↓
Workflow Orchestrator
       ↓
Agent Runtime
       ↓
Tool Execution Layer
       ↓
Playwright / Newman / pytest / SQL Validator
       ↓
Evidence Store + Results DB
       ↓
Failure Classifier + Risk Scorer
       ↓
Human Approval Service
       ↓
Report Generator + CI/CD Feedback
```

## 16. Deployment Architecture

### Local

* Docker Compose
* PostgreSQL
* Redis
* MinIO
* Playwright container
* FastAPI backend
* React/Next.js frontend

### Cloud

* AWS ECS/EKS or GCP GKE
* PostgreSQL RDS/Cloud SQL
* Redis
* S3/GCS artifact storage
* GitHub Actions
* OpenTelemetry + Grafana

## 17. Suggested Tech Stack

### Backend

* Python
* FastAPI
* SQLAlchemy
* Alembic
* Celery or Temporal
* Redis

### Agents

* LangGraph or custom state-machine orchestration
* OpenAI/Anthropic/Gemini provider abstraction
* Pydantic structured outputs

### Testing Tools

* Playwright
* pytest
* Newman/Postman
* SQLAlchemy/psycopg
* Great Expectations optional

### Frontend

* Next.js
* React
* Tailwind
* Recharts

### Infra

* Docker
* Kubernetes
* Terraform
* GitHub Actions

## 18. MVP Scope

## MVP 1: Core Agentic QA Workflow

* Workspace creation
* Requirement ingestion
* Test planning agent
* API testing agent
* Playwright UI test execution
* Failure classification
* Markdown evidence report
* GitHub Actions integration

## MVP 2: Production-Grade Controls

* Human approval gates
* DB validation agent
* Release risk scoring
* Audit logging
* Cost tracking
* Agent evaluation dashboard

## MVP 3: Enterprise Differentiators

* Multi-tenant RBAC
* Jira/GitHub issue creation
* Historical flakiness detection
* Prompt/version registry
* Eval regression suite
* Cloud deployment

## 19. Success Metrics

| Metric                                        | Target       |
| --------------------------------------------- | ------------ |
| Generated test cases executable without edits | > 70%        |
| Failure classification accuracy               | > 80%        |
| False positive defect recommendations         | < 15%        |
| PR feedback latency                           | < 10 minutes |
| Human approval rejection rate                 | < 25%        |
| Agent tool execution success rate             | > 95%        |
| Average cost per PR analysis                  | < $1.00      |
| Evidence report completeness                  | > 90%        |

## 20. Portfolio Deliverables

To make this project stand out:

```text
GitHub repository
Architecture diagrams
Working demo video
Sample target application
Generated test plans
CI/CD run screenshots
Evidence reports
Failure classification examples
Release risk dashboard
Evaluation report
Cost/latency benchmark
Security and audit design
```

## 21. Example Demo Scenario

Use a sample e-commerce app.

```text
PR changes checkout discount logic.

QAForge AI:
1. Reads PR diff and acceptance criteria.
2. Detects affected areas: checkout API, discount validation, payment flow.
3. Generates targeted API, UI, and DB tests.
4. Executes tests.
5. Detects failed negative discount test.
6. Classifies issue as product defect.
7. Links failure to changed file.
8. Generates evidence report with API response and DB state.
9. Calculates release risk score: 78 / High.
10. Posts GitHub PR comment recommending merge block.
```

## 22. Why This Project Is High-Signal

This project proves you can build:

* Agentic workflows
* Production AI systems
* Tool-using agents
* CI/CD automation
* QA domain intelligence
* Human-in-the-loop controls
* Evaluation and observability systems
* Business-relevant engineering automation

It is far stronger than a generic AI chatbot because it solves a real engineering workflow with measurable quality, cost, and reliability outcomes.
