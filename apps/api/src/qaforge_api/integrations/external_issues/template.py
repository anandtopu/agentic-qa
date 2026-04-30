"""Templated issue bodies — Story 3.2.1.

Jinja2 (StrictUndefined) renders a defect classification into a
provider-flavoured body. Per-cuts: we don't try to round-trip the
final HTML/ADF Jira representation, just produce Markdown that Jira
and GitHub both accept verbatim.

The default templates live here as constants so a workspace can
override them later (Phase 4) without touching the service.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined

_env = Environment(undefined=StrictUndefined, autoescape=False)  # noqa: S701 - Markdown body, not HTML


DEFAULT_JIRA_TEMPLATE = """\
*QAForge AI defect report*

*Test:* {{ test_name or signal_id }}
*Category:* {{ category }} (confidence {{ confidence }})
*Test run:* {{ test_run_id }}

h3. What happened

{{ reasoning }}

{% if suggested_fix %}h3. Suggested next step

{{ suggested_fix }}
{% endif %}{% if error_message %}h3. Error message

{code}
{{ error_message }}
{code}
{% endif %}{% if labels %}*Labels:* {{ labels | join(", ") }}
{% endif %}_QAForge correlation: {{ signal_id }}_
"""

DEFAULT_GITHUB_TEMPLATE = """\
**QAForge AI defect report**

- **Test:** `{{ test_name or signal_id }}`
- **Category:** `{{ category }}` (confidence {{ confidence }})
- **Test run:** `{{ test_run_id }}`

### What happened

{{ reasoning }}

{% if suggested_fix %}### Suggested next step

{{ suggested_fix }}
{% endif %}{% if error_message %}### Error message

```
{{ error_message }}
```
{% endif %}{% if line_anchor -%}
*Code reference:* `{{ line_anchor.file_path }}:{{ line_anchor.line }}`
{% endif %}{% if labels %}*Labels:* {{ labels | join(", ") }}
{% endif %}<sub>QAForge correlation: `{{ signal_id }}`</sub>
"""


def render_issue_body(template: str, **context: Any) -> str:
    """Render an issue body template against the given context.

    Strict undefined: a missing variable in the template raises so a
    typo in a workspace's custom template fails loud rather than
    silently posting an empty Jira ticket.
    """
    rendered = _env.from_string(template).render(**context)
    return rendered.strip() + "\n"


__all__ = [
    "DEFAULT_GITHUB_TEMPLATE",
    "DEFAULT_JIRA_TEMPLATE",
    "render_issue_body",
]
