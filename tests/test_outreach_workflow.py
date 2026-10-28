from concurrent.futures import ThreadPoolExecutor
import pytest
from app.db.repository import AlreadyConfirmedError, DailyLimitError, OutreachRepository
from app.models import OutreachPayload


def payload(index):
    return OutreachPayload(name=f"Learner {index}",headline="Final Year CS Student learning AI",snippet="Student interested in Python projects",profile_url=f"https://linkedin.com/in/learner-{index}",detected_persona="Fresher",relevance_score=7,reasoning="Public evidence shows learning interest",personalization_basis="Python projects",connection_note="Hello, I noticed your Python projects. I can share a roadmap if useful.",follow_up_dm="Hello, your public text mentions Python projects. Explore https://code2careerai.com if useful, with no pressure.")


def test_dedup_handoff_not_counted_and_confirmation_single_count(tmp_path):
    repo=OutreachRepository(tmp_path/"db.sqlite3",max_daily_sends=15)
    row,created=repo.save_discovered(payload(1)); assert created
    _,created2=repo.save_discovered(payload(1)); assert not created2
    repo.handoff(row["profile_url"],payload(1).connection_note,payload(1).follow_up_dm)
    assert repo.daily_stats()["confirmed_sends"]==0
    assert repo.daily_stats()["handoffs"]==1
    repo.confirm_sent(row["profile_url"])
    with pytest.raises(AlreadyConfirmedError): repo.confirm_sent(row["profile_url"])
    assert repo.daily_stats()["confirmed_sends"]==1
    with pytest.raises(Exception): repo.handoff(row["profile_url"],"note","dm")


def test_daily_limit_is_enforced(tmp_path):
    repo=OutreachRepository(tmp_path/"db.sqlite3",max_daily_sends=2)
    urls=[]
    for i in range(3):
        record,_=repo.save_discovered(payload(i)); urls.append(record["profile_url"])
    repo.confirm_sent(urls[0]); repo.confirm_sent(urls[1])
    with pytest.raises(DailyLimitError): repo.confirm_sent(urls[2])
    assert repo.daily_stats()["remaining"]==0


def test_concurrent_confirmations_never_exceed_limit(tmp_path):
    repo=OutreachRepository(tmp_path/"db.sqlite3",max_daily_sends=15)
    urls=[]
    for i in range(20): urls.append(repo.save_discovered(payload(i))[0]["profile_url"])
    def confirm(url):
        try: repo.confirm_sent(url); return True
        except (DailyLimitError,AlreadyConfirmedError): return False
    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes=list(pool.map(confirm,urls))
    assert sum(outcomes)==15
    assert repo.daily_stats()["confirmed_sends"]==15
