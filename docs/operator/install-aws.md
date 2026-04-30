# Install on AWS — devops runbook

End-to-end procedure to stand up a QAForge environment on AWS.
Targets the **Story 3.6.1 AC**: `terraform apply` from a fresh AWS
account produces a working environment in **< 60 minutes**.

> Commands that mutate state are clearly marked **(mutates)**.
> Everything else is read-only and safe to run repeatedly.

## Step 0 — Prerequisites

| Tool | Min version | Install |
|---|---|---|
| AWS CLI v2 | 2.15+ | <https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html> |
| Terraform | 1.7+ | `brew install hashicorp/tap/terraform` |
| `kubectl` | 1.30+ | `brew install kubectl` |
| Helm | 3.14+ | `brew install helm` |
| `aws-vault` *or* AWS SSO | latest | `brew install aws-vault` |
| `git`, `make`, `openssl` | any | usually pre-installed |

You also need:

- An AWS account with admin (or close to it) credentials.
- A GitHub Container Registry (or ECR) image pull secret for the API image.
- A registered domain + ACM certificate for the API hostname (out of scope here).

Verify your AWS identity before continuing:

```bash
aws sts get-caller-identity
```

## Step 1 — Bootstrap the Terraform state bucket *(one-time per environment)*

```bash
export AWS_REGION=us-east-1
export PROJECT=qaforge
export ENV=dev

aws s3 mb "s3://${PROJECT}-tf-state-${ENV}" --region "${AWS_REGION}"        # (mutates)
aws s3api put-bucket-versioning \
  --bucket "${PROJECT}-tf-state-${ENV}" \
  --versioning-configuration Status=Enabled                                  # (mutates)
aws s3api put-bucket-encryption \
  --bucket "${PROJECT}-tf-state-${ENV}" \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'                                                                          # (mutates)

aws dynamodb create-table \
  --table-name "${PROJECT}-tf-locks" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${AWS_REGION}"                                                    # (mutates)
```

## Step 2 — Author your `terraform.tfvars`

Create `infra/terraform/environments/dev/terraform.tfvars`:

```hcl
project_name           = "qaforge"
environment            = "dev"
aws_region             = "us-east-1"
vpc_cidr               = "10.42.0.0/16"
eks_kubernetes_version = "1.30"
db_username            = "qaforge"
admin_principal_arn    = "arn:aws:iam::123456789012:role/Admin"
```

The DB password is generated at apply time (Step 4) — **do not** commit it.

## Step 3 — Initialize Terraform

```bash
cd infra/terraform/environments/dev

terraform init \
  -backend-config="bucket=${PROJECT}-tf-state-${ENV}" \
  -backend-config="key=qaforge/${ENV}/terraform.tfstate" \
  -backend-config="region=${AWS_REGION}" \
  -backend-config="dynamodb_table=${PROJECT}-tf-locks"
```

Verify the planned modules look right:

```bash
terraform validate
terraform fmt -check -recursive ../..
```

## Step 4 — Plan + apply *(takes ~45 min on a fresh account)*

```bash
export DB_PASSWORD=$(openssl rand -base64 32)

terraform plan \
  -var="db_password=${DB_PASSWORD}" \
  -out=plan.bin

terraform apply plan.bin                                                      # (mutates) ~45 min
```

Capture the outputs you'll need for the Helm install:

```bash
terraform output -raw cluster_name              # → qaforge-dev
terraform output -raw cluster_endpoint
terraform output -raw api_iam_role_arn          # → IRSA role for the pod
terraform output -raw evidence_bucket_name
terraform output -raw redis_primary_endpoint
terraform output -raw rds_endpoint
```

## Step 5 — Persist the runtime secrets to Secrets Manager

The `secrets` Terraform module pre-creates the entries; populate them now:

```bash
export AUDIT_HMAC_KEY=$(openssl rand -hex 32)
export ANTHROPIC_API_KEY="sk-ant-…"          # from the provider console
export GITHUB_WEBHOOK_SECRET=$(openssl rand -hex 32)

aws secretsmanager put-secret-value \
  --secret-id "qaforge/${ENV}/database_url" \
  --secret-string "postgresql+psycopg://qaforge:${DB_PASSWORD}@$(terraform output -raw rds_endpoint)/qaforge"  # (mutates)

aws secretsmanager put-secret-value \
  --secret-id "qaforge/${ENV}/audit_hmac_key" \
  --secret-string "${AUDIT_HMAC_KEY}"                                          # (mutates)

aws secretsmanager put-secret-value \
  --secret-id "qaforge/${ENV}/anthropic_api_key" \
  --secret-string "${ANTHROPIC_API_KEY}"                                       # (mutates)

aws secretsmanager put-secret-value \
  --secret-id "qaforge/${ENV}/github_webhook_secret" \
  --secret-string "${GITHUB_WEBHOOK_SECRET}"                                   # (mutates)
```

> **Reminder**: never log these values. The redactor (Story 0.4.3)
> scrubs them on emit, but writing them to your shell history is on
> you — prefix sensitive commands with a space if your shell honours
> `HISTCONTROL=ignorespace`.

## Step 6 — Configure `kubectl`

```bash
aws eks update-kubeconfig \
  --name "$(terraform output -raw cluster_name)" \
  --region "${AWS_REGION}"

kubectl get nodes                                # expect 2 Ready nodes for dev
```

## Step 7 — Install External Secrets Operator *(one-time per cluster)*

The Helm chart references secrets by name, not value. ESO syncs them from
Secrets Manager into Kubernetes secrets the pod can mount.

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace \
  --set installCRDs=true                                                       # (mutates)
```

Apply a `ClusterSecretStore` pointing at AWS Secrets Manager (use the
IRSA role from Step 4 outputs):

```bash
cat <<EOF | kubectl apply -f -                                                # (mutates)
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: ${AWS_REGION}
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets-system
EOF
```

## Step 8 — Author `values-dev.yaml` for the Helm chart

```yaml
# values-dev.yaml — AWS dev environment overrides
serviceAccount:
  awsRoleArn: <api_iam_role_arn from Step 4>

ingress:
  enabled: true
  className: alb
  hosts:
    - host: dev.api.qaforge.example.com
      paths:
        - path: /
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:…:certificate/…

networkPolicy:
  egress:
    postgres:
      selectors:
        - ipBlock: { cidr: 10.42.32.0/24 }   # RDS subnet CIDR from VPC module
    redis:
      selectors:
        - ipBlock: { cidr: 10.42.16.0/20 }   # private subnets
    llm:
      cidrs: ["35.231.0.0/16"]               # Anthropic API egress range

env:
  log_level: INFO
  database_url_secret_name: qaforge/dev/database_url
  audit_hmac_key_secret_name: qaforge/dev/audit_hmac_key
  github_webhook_secret_name: qaforge/dev/github_webhook_secret
  anthropic_api_key_secret_name: qaforge/dev/anthropic_api_key
```

## Step 9 — Install the AWS Load Balancer Controller *(one-time per cluster)*

Required for `ingress.className: alb` above:

```bash
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName="$(terraform output -raw cluster_name)" \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller                       # (mutates)
```

The IAM role + service-account binding for ALB controller is created by
the `eks` Terraform module.

## Step 10 — Install QAForge via Helm

```bash
kubectl create namespace qaforge                                               # (mutates)
kubectl label namespace qaforge \
  pod-security.kubernetes.io/enforce=restricted                                # (mutates)

helm upgrade --install qaforge ./infra/helm/qaforge-api \
  --namespace qaforge \
  --values values-dev.yaml \
  --set image.tag="$(git rev-parse HEAD)"                                      # (mutates) ~3 min

kubectl rollout status -n qaforge deployment/qaforge-api --timeout=5m
```

## Step 11 — Apply migrations

```bash
kubectl exec -n qaforge deployment/qaforge-api -- \
  uv run alembic upgrade head                                                  # (mutates)
```

## Step 12 — Smoke test

```bash
curl https://dev.api.qaforge.example.com/api/v1/healthz
# {"status":"ok","version":"<sha>"}
```

If you get TLS errors: confirm the ACM certificate ARN in
`values-dev.yaml`, and that DNS for `dev.api.qaforge.example.com`
points at the ALB hostname (`kubectl get ingress -n qaforge`).

## Step 13 — Verify the SLO + audit + cost endpoints

```bash
TENANT=$(uuidgen)                                # use the seed tenant id in real envs
USER=$(uuidgen)

curl -s https://dev.api.qaforge.example.com/api/v1/audit \
  -H "X-QAForge-Tenant-Id: ${TENANT}" \
  -H "X-QAForge-User-Id: ${USER}" \
  -H "X-QAForge-Role: admin" | head

curl -s "https://dev.api.qaforge.example.com/api/v1/usage/summary?workspace_id=$(uuidgen)" \
  -H "X-QAForge-Tenant-Id: ${TENANT}" \
  -H "X-QAForge-Role: admin"
```

## Step 14 — Wire monitoring

* Enable the chart's `serviceMonitor.enabled=true` once the
  prometheus-operator is installed.
* Replay request samples through `qaforge_api.slo.SloCalculator` and
  emit one snapshot per default SLO into your Grafana / CloudWatch
  backend — see [`monitoring.md`](monitoring.md).
* Hook the alert kinds from `qaforge_api.incident.RUNBOOK_INDEX`
  into your pager (PagerDuty / Opsgenie); each kind already maps to
  a runbook under `docs/runbooks/`.

## Step 15 — Schedule the DR drill

First Wednesday of the quarter. Procedure lives in
[`docs/runbooks/disaster-recovery.md`](../runbooks/disaster-recovery.md);
operator-side day-2 tasks are in
[`backup-restore.md`](backup-restore.md).

## Cost line items (dev, us-east-1)

| Resource | Sizing | Monthly |
|---|---|---|
| EKS control plane | n/a | $73 |
| Worker nodes | 2 × t3.medium | ~$60 |
| RDS Postgres | db.t4g.medium, 7-day backup | ~$60 |
| ElastiCache Redis | cache.t4g.micro, single AZ | ~$13 |
| NAT gateway + S3 + Secrets Manager | — | ~$35 |
| **Total** | | **~$240/mo** |

Production (multi-AZ Redis, Postgres MAZ, 3 × m6i.large nodes) is
roughly 4-5× this. Cost levers documented in
[`infra/terraform/README.md`](../../infra/terraform/README.md).

## Validation matrix

| Step | Status |
|---|---|
| Procedure documented | ✅ Story 5.2 |
| Terraform `validate` smoke | ✅ via `make tf-validate` |
| First real `terraform apply` against an AWS account | ⏳ deferred (TD-013) |
| Pen-test pass on the deployed cluster | ⏳ deferred (Story 3.6.2) |

## Troubleshooting

See [`troubleshooting.md`](troubleshooting.md) for the standard
"pod won't start / 502 from the ALB / migrations fail" flowchart.
For incident-grade issues, the alert kind should map to a runbook
under [`docs/runbooks/`](../runbooks/index.md).

## Next

→ [Upgrade](upgrade.md) · [Backup & restore](backup-restore.md) ·
[Monitoring](monitoring.md)
