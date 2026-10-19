"""#1089: a test run cannot reach api.openai.com, whatever the developer's .env holds.

`app.config` loads `apps/backend/.env` without override, so a developer's `OPENAI_API_KEY`
used to reach every AI service the suite built, and the route tests spent real calls and
failed on the answer (`model_used == 'gpt-4o-mini'`, not `'fallback'`). CI has no `.env`,
so it passed there. `tests/conftest.py` pins the key to nothing before any app import, as
it does the AWS settings (#878): every service then builds without a client and takes its
rule-based path. A test that wants a client injects its own (`vars(service)["client"]`).
"""
import os

from app.services.ai_chat import AIChatService, ai_chat_service
from app.services.ai_orchestration_service import (
    AIOrchestrationService,
    ai_orchestration_service,
)
from app.services.dataset_summarization import (
    DatasetSummarizationService,
    dataset_summarization_service,
)
from app.services.error_analysis_service import (
    ErrorAnalysisService,
    error_analysis_service,
)
from app.services.evaluation_explanation_service import (
    EvaluationExplanationService,
    evaluation_explanation_service,
)
from app.services.feature_engineering_service import get_openai_client
from app.utils.ai_issue_analyzer import AIIssueAnalyzer

SERVICES = (
    AIChatService,
    AIOrchestrationService,
    DatasetSummarizationService,
    ErrorAnalysisService,
    EvaluationExplanationService,
    AIIssueAnalyzer,
)
SINGLETONS = (
    ai_chat_service,
    ai_orchestration_service,
    dataset_summarization_service,
    error_analysis_service,
    evaluation_explanation_service,
)


def test_the_suite_carries_no_openai_key():
    assert os.environ["OPENAI_API_KEY"] == ""


def test_a_dotenv_file_cannot_put_a_key_back(tmp_path):
    """`app.config` loads `.env` without override, so a variable the suite has set,
    even to nothing, is not replaced."""
    from dotenv import load_dotenv

    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-a-real-looking-key\n")

    load_dotenv(dotenv_path=env_file)

    assert os.environ["OPENAI_API_KEY"] == ""


def test_no_service_the_suite_builds_holds_a_client():
    for service in SERVICES:
        assert service().client is None, service.__name__
    for singleton in SINGLETONS:
        assert singleton.client is None, type(singleton).__name__
    assert get_openai_client() is None


def test_the_startup_summary_client_stays_unset():
    """`app/main.py` initializes `ai_summary`'s module-global client at startup."""
    from app.utils import ai_summary

    ai_summary.initialize_openai_client()

    assert ai_summary.client is None
