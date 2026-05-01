"""External-system integrations.

Each integration exposes a Protocol so the API and tests can inject a
stub. Real clients live behind feature-flagged factories so a missing
credential is a clear startup error, not a 500 at request time.
"""
