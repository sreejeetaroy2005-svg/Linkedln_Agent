"""HTTP API routes for discovery and human-controlled outreach."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db.repository import AlreadyConfirmedError, DailyLimitError, DuplicateProfileError, OutreachRepository
from app.models import DiscoveryRequest, HandoffRequest, QueryRequest
from app.services.discovery import DiscoveryService
from app.services.query_builder import build_queries

router = APIRouter(prefix="/api")
repo = OutreachRepository()


class ConfirmRequest(BaseModel):
    confirmed: bool = Field(..., description="Explicit user confirmation that they manually sent the message")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "code2career learner discovery", "external_calls": "only on explicit live discovery"}


@router.post("/queries")
def queries(request: QueryRequest) -> dict:
    return build_queries(request).model_dump()


@router.post("/discover")
async def discover(request: DiscoveryRequest) -> dict:
    return await DiscoveryService(repository=repo).discover(request)


@router.get("/metrics")
def metrics() -> dict:
    records = repo.list_records()
    personas = {p: sum(row["persona"] == p for row in records) for p in ("Fresher", "1-2_YOE", "Career_Switcher")}
    stats = repo.daily_stats()
    return {"total_profiles_discovered": len(records), "profiles_scored": len(records), "profiles_by_persona": personas, **stats}


@router.get("/history")
def history(status: str | None = Query(default=None, pattern="^(discovered|handoff_initiated|contacted)$"), persona: str | None = Query(default=None, pattern="^(Fresher|1-2_YOE|Career_Switcher)$"), limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    return {"records": repo.list_records(status, persona, limit)}


@router.get("/profiles/{profile_key}")
def get_profile(profile_key: str) -> dict:
    # UI uses canonical URL separately to avoid path parsing; included for simple API review by query below.
    raise HTTPException(status_code=404, detail="Use /profile?url=... endpoint")


@router.get("/profile")
def get_profile_by_url(url: str = Query(..., min_length=1)) -> dict:
    try:
        record = repo.get_record(url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not record:
        raise HTTPException(status_code=404, detail="Profile not found")
    return record


@router.post("/profiles/{profile_id:path}/handoff")
def initiate_handoff(profile_id: str, body: HandoffRequest) -> dict:
    from urllib.parse import unquote
    try:
        record = repo.handoff(unquote(profile_id), body.connection_note, body.follow_up_dm)
        return {"record": record, "message": "Handoff recorded. Review and send manually on LinkedIn; this does not count as a sent message."}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DuplicateProfileError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/profiles/{profile_id:path}/confirm-sent")
def confirm_sent(profile_id: str, body: ConfirmRequest) -> dict:
    from urllib.parse import unquote
    if not body.confirmed:
        raise HTTPException(status_code=400, detail="Explicit manual-send confirmation is required")
    try:
        result = repo.confirm_sent(unquote(profile_id))
        return {"result": result, "message": "Recorded based on your confirmation; no message was sent by this application."}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (DailyLimitError, AlreadyConfirmedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/history")
def clear_history(confirm: bool = Query(default=False)) -> dict:
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass confirm=true to permanently clear local outreach history")
    return {"deleted_records": repo.clear_history()}
