# Agentic QA Orchestrator — Terraform

Infrastructure-as-code for one Agentic QA Orchestrator environment (dev / staging /
prod) on AWS. Each `environments/*/` directory is a Terraform root
that composes the per-resource modules under `modules/`.

## Layout

```
infra/terraform/
├── modules/
│   ├── vpc/            VPC + public/private subnets + NAT
│   ├── eks/            EKS cluster + managed node group + IRSA
│   ├── rds/            Postgres 16 RDS with PITR
│   ├── redis/          ElastiCache Redis (single-AZ in dev, MAZ in prod)
│   ├── s3-evidence/    S3 bucket for evidence artifacts (versioned)
│   ├── secrets/        Secrets Manager entries (HMAC keys, DB password)
│   └── iam/            IAM roles for service accounts (IRSA bindings)
├── environments/
│   ├── dev/            Smallest viable footprint
│   └── prod/           HA + PITR + cross-AZ
└── README.md           ← you are here
```

## Acceptance criteria

Story 3.6.1 AC: `terraform apply` from a fresh AWS account produces
a working environment in **< 60 minutes**. The dev environment is
sized for that target; prod has more nodes + multi-AZ Redis and
takes ~75 min on a typical AWS region.

## Per-environment apply walkthrough

```bash
cd infra/terraform/environments/dev

# 1. Configure backend (one-time per environment)
terraform init \
  -backend-config="bucket=aqao-tf-state-dev" \
  -backend-config="key=aqao/dev/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=aqao-tf-locks"

# 2. Plan
terraform plan -var-file=terraform.tfvars -out=plan.bin

# 3. Apply (gated)
terraform apply plan.bin
```

### Required variables (terraform.tfvars)

```hcl
project_name        = "aqao"
environment         = "dev"
aws_region          = "us-east-1"
vpc_cidr            = "10.42.0.0/16"
eks_kubernetes_version = "1.30"
db_password         = "..."   # or fetch from Secrets Manager
db_username         = "aqao"
admin_principal_arn = "arn:aws:iam::123456789012:role/Admin"
```

Use `aws-vault` or AWS SSO; never bake creds into tfvars.

## Validation matrix (deferred)

Real `terraform apply` against a fresh AWS account is **deferred per
agreed Phase-3 cuts** until credentials and a billable account are
provisioned. The Story 3.6.1 surface is the modules + composition;
the operational dry-run is the `terraform validate` smoke covered by
`make tf-validate` (CI integration deferred).

## Cost shape (dev environment, us-east-1, May 2026)

| Resource              | Monthly       |
|-----------------------|---------------|
| EKS control plane     | $73           |
| 2 × t3.medium nodes   | ~$60          |
| RDS db.t4g.medium     | ~$60          |
| Redis cache.t4g.micro | ~$13          |
| NAT + S3 + secrets    | ~$35          |
| **Total**             | **~$240/mo**  |

Production is roughly 3-5× this depending on node count and Redis
sizing.
