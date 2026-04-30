"""Domain services.

The router layer is thin — translation between HTTP and Python — and
delegates state changes to services here. Services accept a Session and
a RequestContext, never the FastAPI Request object, so they are usable
from background workers and scripts as well as from API handlers.
"""

from qaforge_api.services.access_review import (
    AccessReviewEntry,
    AccessReviewService,
    AccessReviewSnapshot,
)
from qaforge_api.services.agent_feedback import (
    AgentFeedbackService,
    AgentReviewSlice,
    ConversionOutcome,
    FeedbackNotConvertibleError,
    WeeklyReview,
)
from qaforge_api.services.api_test_generation import (
    ApiTestGenerationOutput,
    ApiTestGenerationService,
    NoOpenApiRequirementError,
)
from qaforge_api.services.audit import AuditService
from qaforge_api.services.environment import EnvironmentService
from qaforge_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ServiceError,
)
from qaforge_api.services.evidence_report import (
    EvidenceReportService,
    GeneratedReport,
)
from qaforge_api.services.failure_classification import (
    FailureClassificationOutput,
    FailureClassificationService,
)
from qaforge_api.services.model_lifecycle import (
    AwaitingDecisionRow,
    InvalidLifecycleTransitionError,
    ModelLifecycleService,
)
from qaforge_api.services.policy import PolicyService
from qaforge_api.services.repository import RepositoryLinkFailed, RepositoryService
from qaforge_api.services.requirement import RequirementService
from qaforge_api.services.retention import (
    ClassSweepResult,
    RetentionClass,
    RetentionConfigurationError,
    RetentionSweepService,
    SweepReport,
)
from qaforge_api.services.test_plan import TestPlanService
from qaforge_api.services.test_run import (
    TestRunService,
    TestRunStartOutput,
    default_pr_analysis_graph,
    new_idempotency_key,
)
from qaforge_api.services.ui_test_generation import (
    NoUiCasesError,
    UiTestGenerationOutput,
    UiTestGenerationService,
)
from qaforge_api.services.workspace import WorkspaceService

__all__ = [
    "AccessReviewEntry",
    "AccessReviewService",
    "AccessReviewSnapshot",
    "AgentFeedbackService",
    "AgentReviewSlice",
    "ApiTestGenerationOutput",
    "ApiTestGenerationService",
    "AuditService",
    "AwaitingDecisionRow",
    "ClassSweepResult",
    "ConversionOutcome",
    "DuplicateResourceError",
    "EnvironmentService",
    "EvidenceReportService",
    "FailureClassificationOutput",
    "FailureClassificationService",
    "FeedbackNotConvertibleError",
    "GeneratedReport",
    "InvalidLifecycleTransitionError",
    "ModelLifecycleService",
    "NoOpenApiRequirementError",
    "NoUiCasesError",
    "PolicyService",
    "RepositoryLinkFailed",
    "RepositoryService",
    "RequirementService",
    "ResourceNotFoundError",
    "RetentionClass",
    "RetentionConfigurationError",
    "RetentionSweepService",
    "ServiceError",
    "SweepReport",
    "TestPlanService",
    "TestRunService",
    "TestRunStartOutput",
    "UiTestGenerationOutput",
    "UiTestGenerationService",
    "WeeklyReview",
    "WorkspaceService",
    "default_pr_analysis_graph",
    "new_idempotency_key",
]
