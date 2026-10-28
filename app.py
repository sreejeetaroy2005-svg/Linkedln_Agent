"""Single-process Streamlit MVP for safe learner discovery and manual outreach."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import streamlit as st

from app.config import ROOT, settings
from app.db.repository import AlreadyConfirmedError, DailyLimitError, OutreachRepository
from app.models import DiscoveryRequest, OutreachPayload, QueryRequest, SearchResult, canonical_linkedin_url
from app.services.llm_service import LLMError, LLMService
from app.services.query_builder import BUCKET_DESCRIPTIONS, build_queries
from app.services.search_provider import create_search_provider

MAX_DAILY_SENDS = 15
BUCKET_TO_PERSONA = {"A": "Fresher", "B": "1-2_YOE", "C": "Career_Switcher"}
repo = OutreachRepository(max_daily_sends=MAX_DAILY_SENDS)

st.set_page_config(page_title="code2career_ai · Learner discovery", page_icon="🧭", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');
.stApp {background:#f5f7fb;color:#17243d}.block-container {max-width:1120px;padding-top:2rem}
h1,h2,h3 {font-family:Manrope,sans-serif;letter-spacing:-.03em}
.hero {padding:1.5rem 1.8rem;margin-bottom:1rem;border-radius:18px;background:linear-gradient(120deg,#17243d,#3154a4);color:white}
.hero h1 {color:white;margin:0}.hero p {color:#dce7ff;margin:.4rem 0 0}.candidate {padding:1rem 1.2rem;border:1px solid #e2e8f0;border-radius:14px;background:white;margin:.6rem 0}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>code2career_ai · Learner Discovery</h1><p>Discover public search results, prepare thoughtful messages, and keep outreach human-controlled.</p></div>', unsafe_allow_html=True)
st.caption("Synthetic offline profiles are fictional. This app never scrapes LinkedIn or sends messages.")


def _offline_profiles(buckets: list[str], keyword: str) -> list[SearchResult]:
    path = ROOT / "data" / "mock_profiles.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    needle = keyword.strip().casefold()
    results = []
    for row in rows:
        if row.get("bucket") not in buckets:
            continue
        evidence = f"{row.get('headline', '')} {row.get('snippet', '')}".casefold()
        if needle and needle not in evidence:
            continue
        results.append(SearchResult(name=row["name"], headline=row.get("headline", ""), snippet=row.get("snippet", ""), profile_url=row["url"], source="offline_demo"))
    return results


def _discover(buckets: list[str], keyword: str, location: str, offline: bool) -> tuple[list[dict], list[str], list[str]]:
    request = QueryRequest(buckets=buckets, keyword=keyword, location=location)
    query_response = build_queries(request)
    if offline:
        raw_profiles = _offline_profiles(buckets, keyword)
    else:
        provider = create_search_provider(offline=False)
        raw_profiles = []
        for query in query_response.queries:
            raw_profiles.extend(asyncio.run(provider.search(query, max_results=10)))
    llm = LLMService()
    unique: dict[str, SearchResult] = {}
    for profile in raw_profiles:
        unique[canonical_linkedin_url(profile.profile_url)] = profile
    profiles, errors = [], []
    for profile in unique.values():
        try:
            # Offline mode is guaranteed deterministic. With no model key, the same
            # deterministic demo generator is used and its output is visibly labeled.
            payload = llm.score(profile, offline=offline or not bool(settings.openai_api_key))
            record, inserted = repo.save_discovered(payload)
            if inserted:
                profiles.append(payload.model_dump())
            elif record.get("status") != "contacted":
                errors.append(f"Already in local history; skipped duplicate: {profile.name}")
            else:
                errors.append(f"Already confirmed as contacted; skipped: {profile.name}")
        except Exception as exc:
            errors.append(f"Could not prepare {profile.name}: {exc}")
    return profiles, query_response.queries, errors


stats = repo.daily_stats()
metric_cols = st.columns(3)
metric_cols[0].metric("Confirmed sends today", stats["confirmed_sends"])
metric_cols[1].metric("Daily allowance remaining", stats["remaining"])
metric_cols[2].metric("Manual handoffs today", stats["handoffs"], help="Handoffs do not count as confirmed sends.")

discover_tab, history_tab = st.tabs(["Discover learners", "Outreach history"])
with discover_tab:
    st.subheader("Search configuration")
    selected = st.multiselect(
        "Persona buckets", ["Fresher", "1-2_YOE", "Career_Switcher"],
        default=["Fresher", "1-2_YOE", "Career_Switcher"],
        help="Choose one or more groups to include in the public search queries.",
    )
    code_by_persona = {value: key for key, value in BUCKET_TO_PERSONA.items()}
    buckets = [code_by_persona[value] for value in selected]
    keyword_col, location_col = st.columns(2)
    keyword = keyword_col.text_input("Optional keyword", placeholder="Python, machine learning, LLM")
    location = location_col.text_input("Optional location", placeholder="Toronto, Canada")
    offline = st.toggle("Offline demo mode", value=True, help="Uses fictional local profiles and deterministic drafts. No external API calls are made.")
    if not offline and not settings.serper_api_key:
        st.warning("Live search requires SERPER_API_KEY in your environment. Offline mode works without credentials.")
    if st.button("Generate queries and discover profiles", type="primary", disabled=not buckets):
        try:
            with st.spinner("Preparing search results and outreach drafts…"):
                profiles, queries, errors = _discover(buckets, keyword, location, offline)
            st.session_state["profiles"] = profiles
            st.session_state["queries"] = queries
            st.session_state["discovery_errors"] = errors
            st.session_state["offline_results"] = offline
        except Exception as exc:
            st.error(f"Discovery could not run: {exc}")
    if st.session_state.get("queries"):
        with st.expander("Generated Boolean X-Ray queries", expanded=True):
            for query in st.session_state["queries"]:
                st.code(query, language="text")
    if st.session_state.get("offline_results"):
        st.info("OFFLINE DEMO — fictional profiles and deterministic sample scoring; no external search or LLM calls.")
    for error in st.session_state.get("discovery_errors", []):
        st.warning(error)

    profiles = st.session_state.get("profiles", [])
    persona_filter = st.multiselect("Filter displayed candidates", ["Fresher", "1-2_YOE", "Career_Switcher"], default=["Fresher", "1-2_YOE", "Career_Switcher"], key="result_persona_filter")
    matching = [profile for profile in profiles if profile["detected_persona"] in persona_filter]
    if not matching:
        st.caption("Run discovery to prepare new profiles. Previously processed candidates are listed in Outreach history.")
    for index, profile in enumerate(matching):
        url = canonical_linkedin_url(profile["profile_url"])
        record = repo.get_record(url)
        if record and record["status"] == "contacted":
            st.caption(f"{profile['name']} is already confirmed as contacted and is not available for another outreach.")
            continue
        with st.container(border=True):
            st.subheader(profile["name"])
            st.write(profile.get("headline", ""))
            st.caption(profile.get("snippet", ""))
            persona_col, score_col = st.columns([1, 4])
            persona_col.markdown(f"**{profile['detected_persona'].replace('_', ' ')}**")
            score_col.markdown(f"**Relevance {profile['relevance_score']}/10** · {profile['reasoning']}")
            if profile.get("uncertain"):
                st.caption("Persona inference is uncertain because the public evidence is limited.")
            st.link_button("Open public LinkedIn profile", url)
            note_key, dm_key = f"note_{url}", f"dm_{url}"
            note = st.text_area("Connection note", profile["connection_note"], max_chars=299, key=note_key)
            st.caption(f"{len(note)} / 299 characters")
            dm = st.text_area("Follow-up DM", profile["follow_up_dm"], key=dm_key, height=120)
            st.caption(f"{len(dm.split())} / 99 words")
            st.caption("Copyable drafts (use the code block copy control):")
            st.code(note, language=None)
            st.code(dm, language=None)
            if profile.get("is_demo"):
                st.caption("DEMO DRAFT — synthetic; not generated by an AI service and not sent.")
            if st.button("Mark as manually sent", key=f"confirm_{index}", disabled=stats["remaining"] <= 0):
                try:
                    OutreachPayload.model_validate({**profile, "connection_note": note, "follow_up_dm": dm})
                    repo.confirm_sent(url, connection_note=note, follow_up_dm=dm)
                    st.success("Manual-send confirmation recorded. This application did not send the message.")
                    st.rerun()
                except (DailyLimitError, AlreadyConfirmedError, ValueError) as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Could not record confirmation: {exc}")

with history_tab:
    st.subheader("Previously processed profiles")
    records = repo.list_records(limit=500)
    if records:
        st.dataframe([
            {"Name": row["candidate_name"], "Persona": row["persona"], "Status": row["status"], "Handoffs": row["handoff_count"], "Updated": row["updated_at"], "Profile": row["profile_url"]}
            for row in records
        ], use_container_width=True, hide_index=True)
        for row in records:
            with st.expander(f"{row['candidate_name']} · {row['status']}"):
                st.text_area("Saved connection note", row["connection_note"], key=f"history_note_{row['profile_url']}", disabled=True)
                st.text_area("Saved follow-up DM", row["follow_up_dm"], key=f"history_dm_{row['profile_url']}", disabled=True)
    else:
        st.info("No outreach history yet. Viewing a profile or copying a draft does not count as a send.")
    with st.expander("Clear local history"):
        st.warning("This permanently removes saved profiles, handoffs, and send confirmations from the local database.")
        if st.button("Clear all history"):
            deleted = repo.clear_history()
            st.session_state["profiles"] = []
            st.success(f"Cleared {deleted} saved profiles.")
            st.rerun()

st.caption("Responsible use: results from public search can be stale or inaccurate. Verify all evidence. No LinkedIn scraping, credentials, cookies, automated requests, or automated messages are used.")
