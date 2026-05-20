# aqao-api Helm chart — Story 3.6.2

Hardened to the [Pod Security Standards "restricted" profile][pss].
The chart is intentionally opinionated: every security primitive is on
by default and turning one off requires an explicit override.

[pss]: https://kubernetes.io/docs/concepts/security/pod-security-standards/

## What's enforced

| Primitive | Default | Where to look |
|---|---|---|
| `runAsNonRoot` + non-zero UID | ✅ | `values.yaml` `podSecurityContext` |
| `readOnlyRootFilesystem` | ✅ | `containerSecurityContext` |
| `seccompProfile=RuntimeDefault` | ✅ | `podSecurityContext.seccompProfile` |
| `allowPrivilegeEscalation=false` | ✅ | `containerSecurityContext` |
| Drop ALL capabilities | ✅ | `containerSecurityContext.capabilities.drop` |
| HPA (CPU-based, 2-6 replicas) | ✅ | `autoscaling` |
| PDB minAvailable=1 | ✅ | `podDisruptionBudget` |
| NetworkPolicy (deny-by-default + allowlist) | ✅ | `networkPolicy` |
| Pod anti-affinity across AZs | ✅ (preferred) | `affinity.preferredAntiAffinity` |
| Liveness + readiness + startup probes | ✅ | `probes` |
| IRSA service-account binding | opt-in | `serviceAccount.awsRoleArn` |

## Install

```bash
helm upgrade --install aqao ./infra/helm/aqao-api \
  --namespace aqao --create-namespace \
  --values values-prod.yaml \
  --set image.tag=0.1.0
```

A minimal `values-prod.yaml` looks like:

```yaml
serviceAccount:
  awsRoleArn: arn:aws:iam::123456789012:role/aqao-prod-api
ingress:
  enabled: true
  className: alb
  hosts:
    - host: api.aqao.example.com
      paths:
        - path: /
networkPolicy:
  egress:
    postgres:
      selectors:
        - ipBlock:
            cidr: 10.42.32.0/24       # RDS subnets
    redis:
      selectors:
        - ipBlock:
            cidr: 10.42.16.0/20       # private subnets where ElastiCache lives
    llm:
      cidrs:
        - 35.231.0.0/16               # Anthropic API published range (example)
autoscaling:
  minReplicas: 4
  maxReplicas: 16
  targetCPUUtilizationPercentage: 60
```

## Sidecars and extra volumes

`extraContainers` and `extraVolumes` are rendered verbatim into the pod
spec (after the `api` container / `tmp` volume). This is the supported
way to add a sidecar — notably the **GCP Cloud SQL Auth Proxy** — inline
in a values overlay instead of a post-render `kubectl patch`:

```yaml
extraContainers:
  - name: cloud-sql-proxy
    image: gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.13.0
    args: ["--structured-logs", "--port=5432", "PROJECT:REGION:INSTANCE"]
    securityContext:            # keep sidecars PSS-"restricted" too
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities: { drop: ["ALL"] }
    resources:
      requests: { cpu: 50m, memory: 64Mi }
      limits:   { cpu: 500m, memory: 256Mi }
```

The full GCP walkthrough is in
[`docs/operator/install-gcp.md`](../../../docs/operator/install-gcp.md).
Both fields default to `[]`, so they are inert unless set.

## Acceptance criteria

Story 3.6.2 AC: pen-test pass clean. The defaults satisfy the PSS
"restricted" profile; running `kubectl label namespace aqao
pod-security.kubernetes.io/enforce=restricted` after install will keep
admission strict on subsequent upgrades.

## Validation matrix (deferred)

- `helm lint .` — passes.
- `helm template . | kubeconform -strict -summary` — passes.
- Real cluster install + `kube-bench` / `polaris` audit — deferred per
  agreed Phase-3 cuts until a real cluster (Story 3.6.1 apply) exists.
