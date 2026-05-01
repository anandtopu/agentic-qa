"""UI Testing Agent — Story 1.5.

Generates Playwright TS specs from UI test cases. Output is heuristic-
validated for the obvious classes of breakage (missing imports, brace
imbalance, Python-style identifiers); a real ``tsc --noEmit`` /
``playwright test --list`` round-trip is the next stage and lives in
the Playwright runner (Story 1.5.2).
"""

from aqao_agents.ui_tester.agent import (
    UiTesterAgent,
    UiTesterInput,
    UiTesterOutput,
)
from aqao_agents.ui_tester.schema import (
    GeneratedUiTest,
    GeneratedUiTestSpec,
)
from aqao_agents.ui_tester.selector_analysis import (
    FragilityFinding,
    FragilityReport,
    analyse_selectors,
)
from aqao_agents.ui_tester.ts_validator import GeneratedSpecInvalid

__all__ = [
    "FragilityFinding",
    "FragilityReport",
    "GeneratedSpecInvalid",
    "GeneratedUiTest",
    "GeneratedUiTestSpec",
    "UiTesterAgent",
    "UiTesterInput",
    "UiTesterOutput",
    "analyse_selectors",
]
