"""Secret redaction for logs, evidence, and reports.

Mandated by PRD §14.2 (Security) and Story 0.4.3. Apply at every sink that
persists or surfaces text: log handler, evidence writer, report renderer.
"""

from qaforge_redaction.redactor import REDACTED, Redactor, default_redactor, redact

__all__ = ["REDACTED", "Redactor", "default_redactor", "redact"]
