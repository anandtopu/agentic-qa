"""Credential broker — Story 1.4.3.

Tool runners never read ``os.environ`` directly for sensitive values.
They go through a broker that:

1. Resolves a workspace+environment+key to a value.
2. Registers the value with the redactor for the lifetime of the run so
   it's stripped from logs / evidence even if a tool prints it.
3. Returns the value as a :class:`SecretBundle` so callers see the
   typed wrapping.
"""

from aqao_tools.credentials.broker import (
    CredentialBroker,
    InMemoryCredentialBroker,
    SecretBundle,
)

__all__ = ["CredentialBroker", "InMemoryCredentialBroker", "SecretBundle"]
