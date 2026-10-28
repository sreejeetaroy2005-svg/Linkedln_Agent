import pytest
from app.models import SearchResult
from app.services.llm_service import LLMError, LLMService

PROFILE=SearchResult(name="Demo Learner",headline="Final Year CS Student learning AI",snippet="Working on a Python project",profile_url="https://linkedin.com/in/demo-learner",source="test")


def test_offline_scoring_is_deterministic_and_validated():
    service=LLMService(api_key="")
    first=service.score(PROFILE,offline=True)
    second=service.score(PROFILE,offline=True)
    assert first.model_dump(exclude={"created_at"})==second.model_dump(exclude={"created_at"})
    assert first.is_demo and first.detected_persona=="Fresher"
    assert len(first.connection_note)<300 and len(first.follow_up_dm.split())<100


def test_missing_llm_credentials_fails_without_fabricating():
    with pytest.raises(LLMError,match="not configured"):
        LLMService(api_key="").score(PROFILE,offline=False)
