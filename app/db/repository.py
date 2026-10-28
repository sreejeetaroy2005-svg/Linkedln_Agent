"""Repository for deduplication, manual handoffs and transactional send confirmations."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.db.database import init_db, local_now, transaction
from app.models import OutreachPayload, canonical_linkedin_url


class DuplicateProfileError(ValueError): ...
class DailyLimitError(ValueError): ...
class AlreadyConfirmedError(ValueError): ...


class OutreachRepository:
    def __init__(self, db_path: str | Path | None = None, max_daily_sends: int | None = None) -> None:
        self.db_path = db_path or settings.database_path
        self.max_daily_sends = settings.max_daily_sends if max_daily_sends is None else max_daily_sends
        init_db(self.db_path)

    def save_discovered(self, payload: OutreachPayload) -> tuple[dict[str, Any], bool]:
        now = local_now().isoformat()
        url = canonical_linkedin_url(payload.profile_url)
        with transaction(self.db_path, immediate=True) as conn:
            existing = conn.execute("SELECT * FROM outreach_records WHERE profile_url=?", (url,)).fetchone()
            if existing:
                return dict(existing), False
            conn.execute("""INSERT INTO outreach_records
                (profile_url,candidate_name,persona,relevance_score,headline,snippet,connection_note,follow_up_dm,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (url,payload.name,payload.detected_persona,payload.relevance_score,payload.headline,payload.snippet,payload.connection_note,payload.follow_up_dm,"discovered",now,now))
            row = conn.execute("SELECT * FROM outreach_records WHERE profile_url=?", (url,)).fetchone()
            return dict(row), True

    def handoff(self, profile_url: str, note: str, dm: str) -> dict[str, Any]:
        url = canonical_linkedin_url(profile_url)
        now = local_now().isoformat()
        with transaction(self.db_path, immediate=True) as conn:
            row = conn.execute("SELECT * FROM outreach_records WHERE profile_url=?", (url,)).fetchone()
            if not row:
                raise KeyError("Profile has not been discovered")
            if row["status"] == "contacted":
                raise DuplicateProfileError("This profile is already confirmed as contacted")
            conn.execute("UPDATE outreach_records SET connection_note=?,follow_up_dm=?,status='handoff_initiated',handoff_count=handoff_count+1,last_handoff_at=?,updated_at=? WHERE profile_url=?", (note,dm,now,now,url))
            conn.execute("INSERT INTO handoff_events(profile_url,local_day,created_at) VALUES(?,?,?)", (url,local_now().date().isoformat(),now))
            return dict(conn.execute("SELECT * FROM outreach_records WHERE profile_url=?", (url,)).fetchone())

    def confirm_sent(self, profile_url: str, connection_note: str | None = None, follow_up_dm: str | None = None) -> dict[str, Any]:
        url = canonical_linkedin_url(profile_url)
        now = local_now()
        day = now.date().isoformat()
        with transaction(self.db_path, immediate=True) as conn:
            row = conn.execute("SELECT * FROM outreach_records WHERE profile_url=?", (url,)).fetchone()
            if not row:
                raise KeyError("Profile has not been discovered")
            if row["status"] == "contacted" or conn.execute("SELECT 1 FROM confirmed_sends WHERE profile_url=? AND local_day=?",(url,day)).fetchone():
                raise AlreadyConfirmedError("Send confirmation already recorded for this profile today")
            count = conn.execute("SELECT COUNT(*) FROM confirmed_sends WHERE local_day=?",(day,)).fetchone()[0]
            if count >= self.max_daily_sends:
                raise DailyLimitError(f"Daily confirmed-send limit ({self.max_daily_sends}) reached")
            conn.execute("INSERT INTO confirmed_sends(profile_url,local_day,confirmed_at) VALUES(?,?,?)",(url,day,now.isoformat()))
            if connection_note is None and follow_up_dm is None:
                conn.execute("UPDATE outreach_records SET status='contacted',contacted_at=?,updated_at=? WHERE profile_url=?",(now.isoformat(),now.isoformat(),url))
            else:
                conn.execute("UPDATE outreach_records SET status='contacted',connection_note=?,follow_up_dm=?,contacted_at=?,updated_at=? WHERE profile_url=?",(connection_note or row["connection_note"],follow_up_dm or row["follow_up_dm"],now.isoformat(),now.isoformat(),url))
            return {"profile_url":url,"confirmed_today":count+1,"remaining":self.max_daily_sends-count-1,"confirmed_at":now.isoformat()}

    def daily_stats(self) -> dict[str, int | str]:
        day = local_now().date().isoformat()
        with transaction(self.db_path) as conn:
            sent = conn.execute("SELECT COUNT(*) FROM confirmed_sends WHERE local_day=?",(day,)).fetchone()[0]
            handoffs = conn.execute("SELECT COUNT(*) FROM handoff_events WHERE local_day=?",(day,)).fetchone()[0]
            return {"local_day": day,"confirmed_sends":sent,"remaining":max(0,self.max_daily_sends-sent),"handoffs":handoffs,"limit":self.max_daily_sends}

    def list_records(self, status: str | None = None, persona: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        clauses, params = [], []
        if status:
            clauses.append("status=?"); params.append(status)
        if persona:
            clauses.append("persona=?"); params.append(persona)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with transaction(self.db_path) as conn:
            rows = conn.execute(f"SELECT * FROM outreach_records{where} ORDER BY updated_at DESC LIMIT ?",(*params,max(1,min(limit,1000)))).fetchall()
            return [dict(row) for row in rows]

    def get_record(self, profile_url: str) -> dict[str, Any] | None:
        url = canonical_linkedin_url(profile_url)
        with transaction(self.db_path) as conn:
            row = conn.execute("SELECT * FROM outreach_records WHERE profile_url=?",(url,)).fetchone()
            return dict(row) if row else None

    def clear_history(self) -> int:
        with transaction(self.db_path, immediate=True) as conn:
            count = conn.execute("SELECT COUNT(*) FROM outreach_records").fetchone()[0]
            conn.execute("DELETE FROM confirmed_sends")
            conn.execute("DELETE FROM handoff_events")
            conn.execute("DELETE FROM outreach_records")
            return count
