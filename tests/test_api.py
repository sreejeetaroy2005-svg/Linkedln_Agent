import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api import routes


@pytest.fixture
def client(tmp_path,monkeypatch):
    from app.db.repository import OutreachRepository
    monkeypatch.setattr(routes,"repo",OutreachRepository(tmp_path/"api.sqlite3",max_daily_sends=15))
    return TestClient(app)


def test_health_and_query_api(client):
    assert client.get("/api/health").status_code==200
    response=client.post("/api/queries",json={"buckets":["A","C"],"keyword":"Python"})
    assert response.status_code==200 and len(response.json()["queries"])==2
    assert client.post("/api/queries",json={"buckets":["Z"]}).status_code==422


def test_offline_discover_and_confirmation_requires_explicit_user_action(client):
    found=client.post("/api/discover",json={"buckets":["A"],"offline":True})
    assert found.status_code==200 and found.json()["discovered_count"]>0
    profile=found.json()["profiles"][0]
    url=profile["profile_url"]
    from urllib.parse import quote
    path=f"/api/profiles/{quote(url,safe='')}"
    assert client.post(path+"/confirm-sent",json={"confirmed":False}).status_code==400
    handoff=client.post(path+"/handoff",json={"connection_note":profile["connection_note"],"follow_up_dm":profile["follow_up_dm"]})
    assert handoff.status_code==200
    assert client.get("/api/metrics").json()["confirmed_sends"]==0
    assert client.post(path+"/confirm-sent",json={"confirmed":True}).status_code==200
