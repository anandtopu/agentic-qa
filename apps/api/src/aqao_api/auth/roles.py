"""Role enum — Story 3.1.2.

Lifted out of ``permissions.py`` so ``context.py`` can import the type
without the back-reference cycle that breaks Pydantic / OpenAPI
schema resolution. Five workspace roles, lowest privilege first:

    viewer < approver / engineer < admin < owner

The ordering above is informal — the real privilege check is the
explicit :data:`PERMISSION_MATRIX` in ``permissions.py``, not a
hierarchy comparison.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    ENGINEER = "engineer"
    APPROVER = "approver"
    VIEWER = "viewer"


__all__ = ["Role"]
