"""Domain services.

The router layer is thin — translation between HTTP and Python — and
delegates state changes to services here. Services accept a Session and
a RequestContext, never the FastAPI Request object, so they are usable
from background workers and scripts as well as from API handlers.
"""

from aqao_api.services.access_review import (
    AccessReviewEntry,
    AccessReviewService,
    AccessReviewSnapshot,
)
from aqao_api.services.agent_feedback import (
    AgentFeedbackService,
    AgentReviewSlice,
    ConversionOutcome,
    FeedbackNotConvertibleError,
    WeeklyReview,
)
from aqao_api.services.api_test_generation import (
    ApiTestGenerationOutput,
    ApiTestGenerationService,
    NoOpenApiRequirementError,
)
from aqao_api.services.audit import AuditService
from aqao_api.services.environment import EnvironmentService
from aqao_api.services.errors import (
    DuplicateResourceError,
    ResourceNotFoundError,
    ServiceError,
)
from aqao_api.services.evidence_report import (
    EvidenceReportService,
    GeneratedReport,
)
from aqao_api.services.failure_classification import (
    FailureClassificationOutput,
    FailureClassificationService,
)
from aqao_api.services.model_lifecycle import (
    AwaitingDecisionRow,
    InvalidLifecycleTransitionError,
    ModelLifecycleService,
)
from aqao_api.services.policy import PolicyService
from aqao_api.services.repository import RepositoryLinkFailed, RepositoryService
from aqao_api.services.requirement import RequirementService
from aqao_api.services.retention import (
    ClassSweepResult,
    RetentionClass,
    RetentionConfigurationError,
    RetentionSweepService,
    SweepReport,
    load_active_retention_overrides,
)
from aqao_api.services.test_plan import TestPlanService
from aqao_api.services.test_run import (
    TestRunService,
    TestRunStartOutput,
    default_pr_analysis_graph,
    new_idempotency_key,
)
from aqao_api.services.ui_test_generation import (
    NoUiCasesError,
    UiTestGenerationOutput,
    UiTestGenerationService,
)
from aqao_api.services.workspace import WorkspaceService

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
    "load_active_retention_overrides",
    "new_idempotency_key",
]
