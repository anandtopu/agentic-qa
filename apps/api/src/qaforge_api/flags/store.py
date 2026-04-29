"""In-memory flag store.

Phase 0 ships this single backend. Phase 3 will add a DB-backed store
behind the same Protocol so admin-UI edits persist across restarts.
"""

from __future__ import annotations

import json

from qaforge_api.flags.types import FlagDefinition


class InMemoryFlagStore:
    def __init__(self, definitions: list[FlagDefinition] | None = None) -> None:
        self._flags: dict[str, FlagDefinition] = {d.name: d for d in (definitions or [])}

    def get(self, name: str) -> FlagDefinition | None:
        return self._flags.get(name)

    def upsert(self, definition: FlagDefinition) -> None:
        self._flags[definition.name] = definition

    def all_flags(self) -> list[FlagDefinition]:
        return list(self._flags.values())

    @classmethod
    def from_env_json(cls, raw: str | None) -> InMemoryFlagStore:
        """Build a store from a JSON string of ``{name: bool | def}``.

        Accepts two shapes for ergonomics:

        * ``{"my_flag": true}`` — shorthand for ``{name, default: bool}``.
        * ``{"my_flag": {"default": true, "rules": [...]}}`` — full form.
        """
        if not raw:
            return cls()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("QAFORGE_FEATURE_FLAGS must be a JSON object")

        definitions: list[FlagDefinition] = []
        for name, value in payload.items():
            if isinstance(value, bool):
                definitions.append(FlagDefinition(name=name, default=value))
            elif isinstance(value, dict):
                definitions.append(FlagDefinition(name=name, **value))
            else:
                raise ValueError(f"flag {name!r} must be bool or object, not {type(value)!r}")
        return cls(definitions)
