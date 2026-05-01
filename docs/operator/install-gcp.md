# Install on GCP — devops runbook

End-to-end procedure to stand up an Agentic QA Orchestrator environment on Google
Cloud Platform. Targets parity with the AWS runbook: a healthy API
pod behind an HTTPS hostname, with secrets mounted from Secret
Manager, in **< 60 minutes**.

> **Note**: native GCP Terraform modules are **not yet in the
> repo** (tracked as **TD-012** in [`docs/tech-debt.md`](../tech-debt.md)).
> Until they land, this runbook drives `gcloud` directly. The Helm
> chart is provider-agnostic and works on GKE unchanged — only the
> service-account annotation and the network-policy egress CIDRs
> differ from the AWS values file.
>
> Commands that mutate state are clearly marked **(mutates)**.

## Step 0 — Prerequisites

| Tool | Min version | Install |
|---|---|---|
| `gcloud` | latest stable | <https://cloud.google.com/sdk/docs/install> |
| `kubectl` | 1.30+ | `gcloud components install kubectl` |
| `gke-gcloud-auth-plugin` | latest | `gcloud components install gke-gcloud-auth-plugin` |
| Helm | 3.14+ | `brew install helm` |
| `git`, `make`, `openssl` | any | usually pre-installed |

You also need:

- A GCP project with billing enabled and `roles/owner` (or close).
- Quotas raised for: Compute Engine CPUs (≥ 8 in target region),
  Cloud SQL CPUs (≥ 2), Memorystore instances (≥ 1), GKE clusters
  (≥ 1), VPC networks (≥ 1).
- A registered domain + Google-managed SSL certificate (or BYO cert).
- Access to the Anthropic API key (or whichever LLM provider is configured).

Verify your identity + project before continuing:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project "${PROJECT_ID}"
gcloud config set compute/region us-central1

gcloud auth list
gcloud config get-value project
```

## Step 1 — Define environment variables

```bash
export PROJECT_ID="aqao-dev-12345"
export REGION="us-central1"
export ZONE="us-central1-a"
export ENV="dev"
export CLUSTER_NAME="aqao-${ENV}"
export NETWORK="aqao-${ENV}-vpc"
export SUBNET="aqao-${ENV}-subnet"
export DB_INSTANCE="aqao-${ENV}-pg"
export REDIS_INSTANCE="aqao-${ENV}-redis"
export EVIDENCE_BUCKET="aqao-${ENV}-evidence-${PROJECT_ID}"
export KSA_NAMESPACE="aqao"
export KSA_NAME="aqao-api"
export GSA_NAME="aqao-api"
```

## Step 2 — Enable the required APIs *(one-time per project)*

```bash
gcloud services enable \
  container.googleapis.com \
  compute.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  secretmanager.googleapis.com \
  servicenetworking.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  cloudresourcemanager.googleapis.com \
  storage.googleapis.com                                                       # (mutates)
```

## Step 3 — Create the VPC + private subnet

```bash
gcloud compute networks create "${NETWORK}" \
  --subnet-mode=custom                                                         # (mutates)

gcloud compute networks subnets create "${SUBNET}" \
  --network="${NETWORK}" \
  --region="${REGION}" \
  --range=10.42.0.0/20 \
  --secondary-range pods=10.43.0.0/16,services=10.44.0.0/20 \
  --enable-private-ip-google-access                                            # (mutates)

# Reserve a /24 for VPC peering with Cloud SQL + Memorystore.
gcloud compute addresses create google-managed-services-"${NETWORK}" \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=24 \
  --network="${NETWORK}"                                                       # (mutates)

gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-"${NETWORK}" \
  --network="${NETWORK}"                                                       # (mutates)
```

## Step 4 — Create the Cloud SQL Postgres instance

```bash
export DB_PASSWORD=$(openssl rand -base64 32)

gcloud sql instances create "${DB_INSTANCE}" \
  --database-version=POSTGRES_16 \
  --tier=db-custom-2-4096 \
  --region="${REGION}" \
  --network="projects/${PROJECT_ID}/global/networks/${NETWORK}" \
  --no-assign-ip \
  --backup-start-time=03:00 \
  --backup-location="${REGION}" \
  --enable-point-in-time-recovery \
  --retained-backups-count=7 \
  --storage-auto-increase                                                      # (mutates) ~10 min

gcloud sql users set-password postgres \
  --instance="${DB_INSTANCE}" \
  --password="${DB_PASSWORD}"                                                  # (mutates)

gcloud sql databases create aqao --instance="${DB_INSTANCE}"                # (mutates)

gcloud sql users create aqao \
  --instance="${DB_INSTANCE}" \
  --password="${DB_PASSWORD}"                                                  # (mutates)

# Capture the private IP for the API config.
export DB_PRIVATE_IP=$(gcloud sql instances describe "${DB_INSTANCE}" \
  --format='value(ipAddresses[0].ipAddress)')
echo "DB_PRIVATE_IP=${DB_PRIVATE_IP}"
```

## Step 5 — Create the Memorystore Redis instance

```bash
gcloud redis instances create "${REDIS_INSTANCE}" \
  --size=1 \
  --region="${REGION}" \
  --redis-version=redis_7_0 \
  --network="projects/${PROJECT_ID}/global/networks/${NETWORK}" \
  --connect-mode=PRIVATE_SERVICE_ACCESS \
  --tier=BASIC                                                                 # (mutates) ~5 min

export REDIS_HOST=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
  --region="${REGION}" --format='value(host)')
export REDIS_PORT=$(gcloud redis instances describe "${REDIS_INSTANCE}" \
  --region="${REGION}" --format='value(port)')
echo "REDIS_HOST=${REDIS_HOST}:${REDIS_PORT}"
```

## Step 6 — Create the evidence GCS bucket

```bash
gcloud storage buckets create "gs://${EVIDENCE_BUCKET}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  --public-access-prevention                                                   # (mutates)

gcloud storage buckets update "gs://${EVIDENCE_BUCKET}" --versioning           # (mutates)

# 90-day lifecycle on noncurrent versions to mirror the data-handling default.
cat > /tmp/lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      { "action": {"type": "Delete"}, "condition": {"isLive": false, "age": 90} }
    ]
  }
}
EOF

gcloud storage buckets update "gs://${EVIDENCE_BUCKET}" \
  --lifecycle-file=/tmp/lifecycle.json                                         # (mutates)
```

## Step 7 — Create the GKE cluster *(VPC-native + Workload Identity)*

```bash
gcloud container clusters create "${CLUSTER_NAME}" \
  --region="${REGION}" \
  --release-channel=regular \
  --network="${NETWORK}" \
  --subnetwork="${SUBNET}" \
  --enable-ip-alias \
  --cluster-secondary-range-name=pods \
  --services-secondary-range-name=services \
  --enable-private-nodes \
  --enable-master-authorized-networks \
  --master-authorized-networks=$(curl -s ifconfig.me)/32 \
  --master-ipv4-cidr=172.16.0.0/28 \
  --workload-pool="${PROJECT_ID}.svc.id.goog" \
  --enable-shielded-nodes \
  --machine-type=e2-standard-2 \
  --num-nodes=2 \
  --enable-autoscaling --min-nodes=2 --max-nodes=4 \
  --enable-network-policy                                                      # (mutates) ~7 min

gcloud container clusters get-credentials "${CLUSTER_NAME}" --region="${REGION}"

kubectl get nodes
```

## Step 8 — Create the IAM service account + Workload Identity binding

The Helm chart's pod will impersonate this Google Service Account
to read secrets and write evidence. The chart's Kubernetes
ServiceAccount gets annotated with the GSA email so GKE's Workload
Identity rewrites token requests at admission.

```bash
gcloud iam service-accounts create "${GSA_NAME}" \
  --display-name="Agentic QA Orchestrator API"                                 # (mutates)

GSA_EMAIL="${GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Read access to Secret Manager.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"                                  # (mutates)

# Read/write to the evidence bucket only (least privilege).
gcloud storage buckets add-iam-policy-binding "gs://${EVIDENCE_BUCKET}" \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/storage.objectAdmin"                                           # (mutates)

# Cloud SQL client for the Auth Proxy sidecar (Step 10).
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/cloudsql.client"                                               # (mutates)

# Allow the KSA to impersonate the GSA via Workload Identity.
gcloud iam service-accounts add-iam-policy-binding "${GSA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${KSA_NAMESPACE}/${KSA_NAME}]"  # (mutates)
```

## Step 9 — Push secrets into Secret Manager

```bash
export AUDIT_HMAC_KEY=$(openssl rand -hex 32)
export GITHUB_WEBHOOK_SECRET=$(openssl rand -hex 32)
export ANTHROPIC_API_KEY="sk-ant-…"           # from the provider console

# Use the Cloud SQL Auth Proxy host (127.0.0.1:5432) since the API talks via the proxy sidecar.
DATABASE_URL="postgresql+psycopg://aqao:${DB_PASSWORD}@127.0.0.1:5432/aqao"

create_secret() {
  local name="$1" value="$2"
  printf '%s' "${value}" | gcloud secrets create "${name}" \
    --replication-policy="automatic" --data-file=- \
  || printf '%s' "${value}" | gcloud secrets versions add "${name}" --data-file=-
}

create_secret "aqao-${ENV}-database-url"          "${DATABASE_URL}"          # (mutates)
create_secret "aqao-${ENV}-audit-hmac-key"        "${AUDIT_HMAC_KEY}"        # (mutates)
create_secret "aqao-${ENV}-anthropic-api-key"     "${ANTHROPIC_API_KEY}"     # (mutates)
create_secret "aqao-${ENV}-github-webhook-secret" "${GITHUB_WEBHOOK_SECRET}" # (mutates)
```

> **Reminder**: never log these values. The redactor (Story 0.4.3)
> scrubs them on emit; writing them to your shell history is on
> you — prefix sensitive commands with a space if your shell honours
> `HISTCONTROL=ignorespace`.

## Step 10 — Install External Secrets Operator + GCP `ClusterSecretStore`

The Helm chart references secrets by name, not value. ESO syncs them
from Secret Manager into Kubernetes secrets that the pod mounts.

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace \
  --set installCRDs=true                                                       # (mutates)

# Create a KSA dedicated to ESO with Workload Identity binding.
kubectl create namespace external-secrets-system 2>/dev/null || true
kubectl create serviceaccount external-secrets -n external-secrets-system 2>/dev/null || true

ESO_GSA_EMAIL="${GSA_EMAIL}"  # reuse — has secretAccessor

kubectl annotate serviceaccount external-secrets \
  -n external-secrets-system \
  iam.gke.io/gcp-service-account="${ESO_GSA_EMAIL}" --overwrite                # (mutates)

cat <<EOF | kubectl apply -f -                                                 # (mutates)
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: gcp-secret-manager
spec:
  provider:
    gcpsm:
      projectID: ${PROJECT_ID}
      auth:
        workloadIdentity:
          clusterLocation: ${REGION}
          clusterName: ${CLUSTER_NAME}
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets-system
EOF
```

## Step 11 — Deploy the Cloud SQL Auth Proxy as a sidecar

The Helm chart in this repo expects the API to reach Postgres via
`127.0.0.1:5432`. We add the Cloud SQL Auth Proxy as a sidecar
through a small values override:

```yaml
# values-dev.yaml — GCP dev environment overrides
serviceAccount:
  create: true
  name: aqao-api
  awsRoleArn: ""                              # AWS-only — leave empty on GCP
  annotations:
    iam.gke.io/gcp-service-account: aqao-api@${PROJECT_ID}.iam.gserviceaccount.com

ingress:
  enabled: true
  className: gce                              # GKE managed L7
  hosts:
    - host: dev.api.aqao.example.com
      paths:
        - path: /
  annotations:
    kubernetes.io/ingress.global-static-ip-name: aqao-dev-ip
    networking.gke.io/managed-certificates: aqao-dev-cert

networkPolicy:
  egress:
    postgres:
      selectors:
        - ipBlock: { cidr: ${DB_PRIVATE_IP}/32 }
    redis:
      selectors:
        - ipBlock: { cidr: ${REDIS_HOST}/32 }
    llm:
      cidrs: ["0.0.0.0/0"]                    # tighten to provider's published ranges in prod

env:
  log_level: INFO
  database_url_secret_name: aqao-${ENV}-database-url
  audit_hmac_key_secret_name: aqao-${ENV}-audit-hmac-key
  github_webhook_secret_name: aqao-${ENV}-github-webhook-secret
  anthropic_api_key_secret_name: aqao-${ENV}-anthropic-api-key

# Cloud SQL Auth Proxy sidecar — added via Helm `extraContainers` (not yet
# templated in the chart; tracked as TD-014). Until then, post-process the
# rendered deployment with the patch in `infra/helm/aqao-api/patches/gcp-sqlproxy.yaml`.
```

> The Helm chart does not yet expose `extraContainers` — until that
> lands (**TD-014**), the workaround is to render the chart, append
> the sidecar via `kubectl patch`, and apply. Procedure:

```bash
helm template aqao ./infra/helm/aqao-api \
  --namespace aqao \
  --values values-dev.yaml > /tmp/aqao.yaml

# Patch the Deployment to add the Cloud SQL Auth Proxy sidecar.
kubectl patch -f /tmp/aqao.yaml --local --type=strategic --patch "$(cat <<EOF
spec:
  template:
    spec:
      containers:
        - name: cloud-sql-proxy
          image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.13.0
          args:
            - "--structured-logs"
            - "--port=5432"
            - "${PROJECT_ID}:${REGION}:${DB_INSTANCE}"
          securityContext:
            runAsNonRoot: true
            allowPrivilegeEscalation: false
            capabilities: { drop: ["ALL"] }
          resources:
            requests: { cpu: 50m, memory: 64Mi }
            limits:   { cpu: 500m, memory: 256Mi }
EOF
)" -o yaml > /tmp/aqao-patched.yaml
```

## Step 12 — Reserve a static IP + managed certificate for ingress

```bash
gcloud compute addresses create aqao-dev-ip --global                        # (mutates)

cat <<EOF | kubectl apply -f -                                                 # (mutates)
apiVersion: networking.gke.io/v1
kind: ManagedCertificate
metadata:
  name: aqao-dev-cert
  namespace: aqao
spec:
  domains:
    - dev.api.aqao.example.com
EOF
```

Point `dev.api.aqao.example.com` (Cloud DNS or wherever you host
DNS) at the static IP from `gcloud compute addresses describe aqao-dev-ip --global`.

## Step 13 — Install Agentic QA Orchestrator via Helm

```bash
kubectl create namespace aqao                                               # (mutates)
kubectl label namespace aqao \
  pod-security.kubernetes.io/enforce=restricted                                # (mutates)

# Once TD-014 lands, this will be a single command:
# helm upgrade --install aqao ./infra/helm/aqao-api \
#   --namespace aqao --values values-dev.yaml --set image.tag=$(git rev-parse HEAD)

# For now, apply the patched manifest:
kubectl apply -n aqao -f /tmp/aqao-patched.yaml                          # (mutates)

kubectl rollout status -n aqao deployment/aqao-api --timeout=5m
```

## Step 14 — Apply migrations

```bash
kubectl exec -n aqao deployment/aqao-api -c aqao-api -- \
  uv run alembic upgrade head                                                  # (mutates)
```

## Step 15 — Smoke test

```bash
curl https://dev.api.aqao.example.com/api/v1/healthz
# {"status":"ok","version":"<sha>"}
```

The managed certificate takes ~10–30 minutes to provision the first
time. Until it's ready, `kubectl get managedcertificate -n aqao`
shows `Provisioning`; once `Active`, the curl above succeeds.

## Step 16 — Verify the SLO + audit + cost endpoints

```bash
TENANT=$(uuidgen)

curl -s https://dev.api.aqao.example.com/api/v1/audit \
  -H "X-AQAO-Tenant-Id: ${TENANT}" \
  -H "X-AQAO-Role: admin" | head

curl -s "https://dev.api.aqao.example.com/api/v1/usage/summary?workspace_id=$(uuidgen)" \
  -H "X-AQAO-Tenant-Id: ${TENANT}" \
  -H "X-AQAO-Role: admin"
```

## Step 17 — Wire monitoring

GKE writes container logs and metrics to Cloud Logging + Cloud
Monitoring by default. To use the Helm chart's Prometheus
ServiceMonitor instead:

```bash
# Install Google Managed Prometheus operator (alternative to upstream):
gcloud container clusters update "${CLUSTER_NAME}" \
  --region="${REGION}" \
  --enable-managed-prometheus                                                  # (mutates)
```

Then set `serviceMonitor.enabled=true` in `values-dev.yaml` and roll
out. Replay request samples through `aqao_api.slo.SloCalculator`
and emit one snapshot per default SLO into Cloud Monitoring custom
metrics — see [`monitoring.md`](monitoring.md).

## Step 18 — Schedule the DR drill

First Wednesday of the quarter — same as AWS. Differences for GCP:

* **Postgres PITR** — `gcloud sql backups list --instance=${DB_INSTANCE}`
  then `gcloud sql instances clone … --point-in-time=…`.
* **Evidence restore** — GCS object versioning round-trip via
  `gcloud storage objects list --include-versions` +
  `gcloud storage cp gs://…#<generation> gs://…/restored`.
* **Secret rotation** — `gcloud secrets versions add ${NAME} --data-file=-`
  followed by an API rolling restart; the External Secrets refresh
  interval (default 1 h) determines how fast pods see the new value.

Procedure lives in
[`docs/runbooks/disaster-recovery.md`](../runbooks/disaster-recovery.md);
operator-side day-2 tasks are in
[`backup-restore.md`](backup-restore.md).

## Cost line items (dev, us-central1)

| Resource | Sizing | Monthly |
|---|---|---|
| GKE control plane | regional, regular channel | $73 |
| Worker nodes | 2 × e2-standard-2 | ~$50 |
| Cloud SQL Postgres | db-custom-2-4096, 7-day backup | ~$70 |
| Memorystore Redis | BASIC, 1 GiB | ~$30 |
| GCS + Secret Manager + egress | — | ~$20 |
| **Total** | | **~$220-240/mo** |

Production (regional Memorystore STANDARD_HA, Cloud SQL HA,
3 × e2-standard-4 nodes) is roughly 4-5× this.

## Validation matrix

| Step | Status |
|---|---|
| Procedure documented | ✅ this page |
| Native Terraform modules for GCP | ⏳ deferred (TD-012) |
| Helm chart `extraContainers` for Cloud SQL Auth Proxy | ⏳ deferred (TD-014) |
| First real apply against a GCP project | ⏳ deferred (TD-013) |

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Pod stuck `CreateContainerConfigError` | ESO hasn't synced the secret yet | `kubectl get externalsecret -n aqao`; wait or force `kubectl annotate externalsecret aqao-api force-sync=$(date +%s) --overwrite` |
| `connection refused` to `127.0.0.1:5432` | Cloud SQL Auth Proxy sidecar didn't start | `kubectl logs -n aqao -l app=aqao-api -c cloud-sql-proxy`; check the GSA has `roles/cloudsql.client` |
| Ingress stays on `Provisioning` for > 30 min | DNS not pointing at the reserved IP | `gcloud compute addresses describe aqao-dev-ip --global`; update DNS A record |
| 503 from the LB during rollout | Readiness probe path mismatch | Confirm `probes.readiness.path: /api/v1/healthz` matches the API |

For deeper issues, the alert kinds in
`aqao_api.incident.RUNBOOK_INDEX` map to runbooks under
[`docs/runbooks/`](../runbooks/index.md) — same playbooks as AWS.

## Next

→ [Upgrade](upgrade.md) · [Backup & restore](backup-restore.md) ·
[Monitoring](monitoring.md)
