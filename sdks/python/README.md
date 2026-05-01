# aqao-sdk

Python SDK for Agentic QA Orchestrator. Thin client over the REST surface
documented at [`apis/openapi.yaml`](../../apis/openapi.yaml).

## Install

```bash
pip install aqao-sdk    # PyPI publish deferred; use a path install today:
pip install -e sdks/python
```

## Usage

```python
from aqao_sdk import AQAOClient

client = AQAOClient(
    base_url="https://api.aqao.ai",
    token="...",
    tenant_id="...",
    role="engineer",
)

run = client.test_runs.create(
    workspace_id="ws-1",
    repository="my-org/my-app",
    pull_number=42,
    head_sha="0" * 40,
)
```

See [`docs/api/python.md`](../../docs/api/python.md) for the full
walk-through, error hierarchy, and async variant.
