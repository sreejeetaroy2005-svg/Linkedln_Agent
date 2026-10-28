import pytest
from pydantic import ValidationError
from app.models import OutreachPayload, SearchResult


def sample(**updates):
    body = dict(name="Test Learner", headline="Student learning Python", snippet="Interested in AI projects", profile_url="https://linkedin.com/in/test-learner/?trk=foo", detected_persona="Fresher", relevance_score=7, reasoning="Observed student and AI interest", personalization_basis="learning Python", connection_note="Hello, I noticed your Python learning. I can share a project roadmap if useful.", follow_up_dm="Hello, your public headline mentions Python. Explore https://code2careerai.com if helpful, with no pressure.")
    body.update(updates)
    return body


def test_urls_canonicalize_and_reject_other_domains():
    assert SearchResult(name="N",profile_url="https://linkedin.com/in/someone/",source="x").profile_url == "https://www.linkedin.com/in/someone"
    with pytest.raises(ValidationError): SearchResult(name="N",profile_url="https://evil.test/in/a",source="x")
    with pytest.raises(ValidationError): SearchResult(name="N",profile_url="https://linkedin.com/company/acme",source="x")


def test_payload_limits_persona_and_score_validated():
    payload=OutreachPayload(**sample())
    assert len(payload.connection_note)<300
    assert len(payload.follow_up_dm.split())<100
    for change in ({"detected_persona":"Executive"},{"relevance_score":11},{"connection_note":"x"*300},{"follow_up_dm":" ".join(["word"]*100)}):
        with pytest.raises(ValidationError): OutreachPayload(**sample(**change))
