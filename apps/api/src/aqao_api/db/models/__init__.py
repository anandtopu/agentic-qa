"""ORM model registry.

Every model module must be imported here so Alembic autogeneration can
see it via ``Base.metadata``. Order does not matter; SQLAlchemy resolves
foreign-key references at metadata-create time.
"""

from __future__ import annotations

from aqao_api.db.models.agent_feedback import AgentFeedback, FeedbackRating
from aqao_api.db.models.approval_request import (
    ApprovalEventType,
    ApprovalRequest,
    ApprovalState,
    is_terminal,
)
from aqao_api.db.models.audit_event import AuditEvent
from aqao_api.db.models.environment import WorkspaceEnvironment
from aqao_api.db.models.external_issue import (
    ExternalIssue,
    IssueProvider,
    IssueStatus,
    is_terminal_status,
)
from aqao_api.db.models.failure_classification import (
    ClassifiedBy,
    FailureCategory,
    FailureClassification,
)
from aqao_api.db.models.flakiness_observation import FlakinessObservation
from aqao_api.db.models.model_registry import (
    ModelDecision,
    ModelLifecycleStatus,
    ModelRegistryEntry,
)
from aqao_api.db.models.policy import WorkspacePolicy
from aqao_api.db.models.prompt_pin import PromptPin
from aqao_api.db.models.repository import Repository
from aqao_api.db.models.requirement import (
    Requirement,
    RequirementStatus,
    RequirementType,
)
from aqao_api.db.models.tenant import Tenant
from aqao_api.db.models.test_plan import (
    TestCase,
    TestCasePriority,
    TestCaseType,
    TestPlan,
    TestPlanStatus,
)
from aqao_api.db.models.test_run import (
    AgentTask,
    AgentTaskState,
    EvidenceArtifact,
    TestRun,
    TestRunState,
)
from aqao_api.db.models.usage_record import UsageRecordRow
from aqao_api.db.models.user import User
from aqao_api.db.models.workspace import ApplicationType, Workspace

__all__ = [
    "AgentFeedback",
    "AgentTask",
    "AgentTaskState",
    "ApplicationType",
    "ApprovalEventType",
    "ApprovalRequest",
    "ApprovalState",
    "AuditEvent",
    "ClassifiedBy",
    "EvidenceArtifact",
    "ExternalIssue",
    "FailureCategory",
    "FailureClassification",
    "FeedbackRating",
    "FlakinessObservation",
    "IssueProvider",
    "IssueStatus",
    "ModelDecision",
    "ModelLifecycleStatus",
    "ModelRegistryEntry",
    "PromptPin",
    "Repository",
    "Requirement",
    "RequirementStatus",
    "RequirementType",
    "Tenant",
    "TestCase",
    "TestCasePriority",
    "TestCaseType",
    "TestPlan",
    "TestPlanStatus",
    "TestRun",
    "TestRunState",
    "UsageRecordRow",
    "User",
    "Workspace",
    "WorkspaceEnvironment",
    "WorkspacePolicy",
    "is_terminal",
    "is_terminal_status",
]
