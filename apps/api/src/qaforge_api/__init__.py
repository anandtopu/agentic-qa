"""QAForge AI — FastAPI backend.

Implements the Control Plane API surface defined in PRD §13. The
intelligence and execution planes live in separate packages
(`qaforge_agents`, `qaforge_tools`) and are invoked via the workflow
orchestrator (Phase 1+).
"""

__version__ = "0.0.0"
