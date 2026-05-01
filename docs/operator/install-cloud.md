# Install (cloud)

Pick your provider:

* **[AWS](install-aws.md)** — Terraform modules at
  [`infra/terraform/`](../../infra/terraform/) (Story 3.6.1) provision
  VPC + EKS + RDS + ElastiCache + S3 + Secrets Manager + IRSA. The
  hardened Helm chart at [`infra/helm/aqao-api/`](../../infra/helm/aqao-api/)
  (Story 3.6.2) deploys the API on top.
* **[GCP](install-gcp.md)** — Terraform modules for GCP are not yet
  in the repo (tracked as **TD-012** in
  [`docs/tech-debt.md`](../tech-debt.md)). The runbook drives
  `gcloud` directly to provision GKE + Cloud SQL + Memorystore +
  GCS + Secret Manager + Workload Identity, then deploys the same
  Helm chart with a GKE-flavoured values file.

Whichever you pick, the post-install steps are shared — see
[After install (shared)](#after-install-shared) below.

## What you're deploying

| Plane | Component | AWS resource | GCP resource |
|---|---|---|---|
| Control | FastAPI API | EKS pod (Helm) | GKE pod (Helm) |
| Storage — relational | Postgres 16 + RLS | RDS Postgres | Cloud SQL Postgres |
| Storage — cache / queue | Redis 7 | ElastiCache | Memorystore Redis |
| Storage — evidence | S3-compatible bucket | S3 (versioned) | GCS (versioned) |
| Secrets | HMAC keys, DB password, provider keys | Secrets Manager | Secret Manager |
| Identity | Pod → cloud APIs | IRSA (OIDC) | Workload Identity |
| DNS + TLS | API hostname | Route53 + ACM | Cloud DNS + Google-managed cert |

The Helm chart is **provider-agnostic** — only the
`serviceAccount.awsRoleArn` annotation (AWS) vs the Workload
Identity annotation (GCP) and the network-policy egress CIDRs
differ between the two `values-<env>.yaml` files.

## Acceptance criteria

* **Story 3.6.1 (AWS)**: `terraform apply` from a fresh AWS account
  produces a working environment in **< 60 minutes**. Real apply is
  deferred per agreed Phase-3 cuts; the procedure is the AWS guide.
* **Story 3.6.2 (Helm)**: hardened Helm chart with HPA, PDB, network
  policies, Pod Security Standards "restricted". Verified at
  `helm template` time by `apps/api/tests/test_helm_chart_smoke.py`.
* **GCP path**: target parity with the AWS runbook. Real apply
  also deferred; provisioning script lives in the GCP guide.

## After install (shared)

Both runbooks land you at the same milestone — a healthy API pod
behind an HTTPS hostname, with secrets mounted from the cloud
secret store. From there:

1. **Apply database migrations** (one-time per release):
   ```bash
   kubectl exec -n aqao deployment/aqao-api -- \
     uv run alembic upgrade head     # (mutates)
   ```
2. **Smoke**:
   ```bash
   curl https://<api-hostname>/api/v1/healthz
   # {"status":"ok","version":"<sha>"}
   ```
3. **Seed a demo workspace** if this is a brand-new cluster
   (`make seed` against the cluster's API hostname — see
   [user/getting-started.md](../user/getting-started.md)).
4. **Wire monitoring** — see [`monitoring.md`](monitoring.md). The
   Helm chart ships an opt-in `ServiceMonitor` for prometheus-operator;
   the SLOs from `aqao_api.slo.DEFAULT_SLOS` are what to alert on.
5. **Schedule the DR drill** — see
   [`backup-restore.md`](backup-restore.md) and the
   [disaster-recovery runbook](../runbooks/disaster-recovery.md).
6. **Set up upgrade discipline** — see [`upgrade.md`](upgrade.md).

## Cost shape (rough, May 2026)

| Tier | AWS | GCP |
|---|---|---|
| Dev (single AZ, t3.medium / e2-standard-2) | ~$240/mo | ~$220/mo |
| Prod (multi-AZ, m6i.large / e2-standard-4) | ~$1.2K/mo | ~$1.1K/mo |

See the per-provider runbooks for the line-item breakdown.

## Next

→ [AWS step-by-step](install-aws.md) · [GCP step-by-step](install-gcp.md)
