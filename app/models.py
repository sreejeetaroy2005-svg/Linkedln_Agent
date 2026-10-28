"""Validated models shared across API, services, and persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, field_validator, ConfigDict

Persona = Literal["Fresher", "1-2_YOE", "Career_Switcher"]
Bucket = Literal["A", "B", "C"]


def canonical_linkedin_url(value: str) -> str:
    """Accept only public LinkedIn person profile URLs and normalize tracking/trailing slash."""
    raw = value.strip()
    if not raw or len(raw) > 2048:
        raise ValueError("Invalid profile URL")
    if "://" not in raw:
        raw = "https://" + raw
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme.lower() != "https" or host not in {"linkedin.com", "www.linkedin.com"}:
        raise ValueError("Profile URL must use linkedin.com")
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) != 2 or segments[0].lower() != "in" or not segments[1].replace("-", "").replace("_", "").isalnum():
        raise ValueError("URL must identify a LinkedIn /in/ profile")
    return urlunsplit(("https", "www.linkedin.com", f"/in/{segments[1]}", "", ""))


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=160)
    headline: str = Field(default="", max_length=500)
    snippet: str = Field(default="", max_length=3000)
    profile_url: str
    source: str = Field(default="public_search", max_length=80)

    @field_validator("profile_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return canonical_linkedin_url(value)


class OutreachPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=160)
    headline: str = Field(default="", max_length=500)
    snippet: str = Field(default="", max_length=3000)
    profile_url: str
    detected_persona: Persona
    relevance_score: int = Field(ge=1, le=10)
    reasoning: str = Field(min_length=1, max_length=1000)
    personalization_basis: str = Field(min_length=1, max_length=500)
    connection_note: str = Field(min_length=1, max_length=299)
    follow_up_dm: str = Field(min_length=1, max_length=2000)
    uncertain: bool = False
    is_demo: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @field_validator("profile_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return canonical_linkedin_url(value)

    @field_validator("connection_note")
    @classmethod
    def note_under_300(cls, value: str) -> str:
        if len(value) >= 300:
            raise ValueError("Connection note must be under 300 characters")
        return value.strip()

    @field_validator("follow_up_dm")
    @classmethod
    def dm_under_100_words(cls, value: str) -> str:
        if len(value.split()) >= 100:
            raise ValueError("Follow-up DM must be under 100 words")
        return value.strip()


class QueryRequest(BaseModel):
    buckets: list[Bucket] = Field(default_factory=lambda: ["A", "B", "C"], min_length=1, max_length=3)
    keyword: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=100)


class QueryResponse(BaseModel):
    queries: list[str]
    bucket_descriptions: dict[str, str]


class DiscoveryRequest(QueryRequest):
    offline: bool = True
    max_results_per_bucket: int = Field(default=10, ge=1, le=30)


class HandoffRequest(BaseModel):
    connection_note: str = Field(min_length=1, max_length=299)
    follow_up_dm: str = Field(min_length=1, max_length=2000)

    @field_validator("connection_note")
    @classmethod
    def note_limit(cls, value: str) -> str:
        if len(value) >= 300:
            raise ValueError("Connection note must be under 300 characters")
        return value

    @field_validator("follow_up_dm")
    @classmethod
    def dm_limit(cls, value: str) -> str:
        if len(value.split()) >= 100:
            raise ValueError("Follow-up DM must be under 100 words")
        return value
