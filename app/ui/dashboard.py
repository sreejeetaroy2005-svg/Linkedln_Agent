"""Streamlit dashboard for responsible learner discovery and manual outreach."""
from __future__ import annotations

import html
from urllib.parse import quote

import requests
import streamlit as st

from app.config import settings
from app.models import DiscoveryRequest, QueryRequest
from app.services.query_builder import build_queries
from app.db.repository import OutreachRepository

st.set_page_config(page_title="code2career · Learner Discovery", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
API_BASE = st.sidebar.text_input("API service URL", "http://127.0.0.1:8000", help="Run the FastAPI service in another terminal.").rstrip("/")
repo = OutreachRepository()
st.markdown("""
<style>
:root {--ink:#14213d;--muted:#64748b;--blue:#365cf5;--mint:#dbf7ed;--paper:#f6f8fc}
html, body, [class*="css"] {font-family:'DM Sans',sans-serif;color:var(--ink)}
.stApp {background:linear-gradient(135deg,#f7f9ff 0%,#f1f7fa 100%)}
.block-container {max-width:1280px;padding-top:2rem;padding-bottom:3rem}
h1,h2,h3 {font-family:'Manrope',sans-serif;letter-spacing:-.035em;color:var(--ink)}
.hero {padding:1.6rem 1.8rem;background:linear-gradient(120deg,#14213d 0%,#234379 70%,#365cf5 100%);border-radius:20px;color:white;margin:0 0 1.5rem;box-shadow:0 18px 50px #1e3a8a22}
.hero h1 {color:white;margin:0;font-size:2rem}.hero p {color:#d8e6ff;margin:.45rem 0 0}.eyebrow {text-transform:uppercase;letter-spacing:.13em;font-size:.7rem;font-weight:700;color:#8be2c2}
.metric-card {background:white;border:1px solid #e5eaf3;border-radius:16px;padding:1.1rem 1.25rem;box-shadow:0 7px 24px #2538580b;min-height:112px}
.metric-label {font-size:.8rem;color:#64748b;font-weight:600}.metric-value {font-family:'Manrope';font-size:1.8rem;font-weight:800;color:#14213d;margin-top:.28rem}.metric-hint {font-size:.75rem;color:#7b8799;margin-top:.15rem}
.candidate {border:1px solid #e3eaf3;border-radius:16px;padding:1.15rem 1.3rem;background:#fff;margin:.5rem 0 1rem;box-shadow:0 8px 24px #2438580a}
.candidate h3 {margin:0;font-size:1.13rem}.muted {color:#68778d;font-size:.89rem}.pill {display:inline-block;background:#eaf0ff;color:#3553ad;padding:4px 10px;border-radius:999px;font-size:.73rem;font-weight:700;margin:6px 4px 0 0}.demo {padding:.75rem 1rem;background:#fff8df;color:#694d00;border:1px solid #f4dfa1;border-radius:10px;font-size:.86rem}
button[kind="primary"] {border-radius:10px}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="eyebrow">Technical Buddy · Growth Engineering</div><h1>Find learners. Offer useful next steps.</h1><p>Discover public search results, prepare thoughtful outreach, and keep every send human-controlled.</p></div>', unsafe_allow_html=True)

if "profiles" not in st.session_state: st.session_state.profiles = []
if "last_errors" not in st.session_state: st.session_state.last_errors = []

def api_get(path: str, params: dict | None = None):
    response = requests.get(f"{API_BASE}{path}", params=params, timeout=8)
    response.raise_for_status()
    return response.json()

def api_post(path: str, body: dict):
    response = requests.post(f"{API_BASE}{path}", json=body, timeout=45)
    if response.status_code >= 400:
        detail = response.json().get("detail", "Request failed")
        raise ValueError(str(detail))
    return response.json()

def metric(label: str, value: str, hint: str):
    st.markdown(f'<div class="metric-card"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-hint">{hint}</div></div>', unsafe_allow_html=True)

try:
    metrics = api_get("/api/metrics")
    api_online = True
except Exception:
    metrics = {"total_profiles_discovered": len(st.session_state.profiles), "profiles_scored": len(st.session_state.profiles), "profiles_by_persona": {}, "confirmed_sends": 0, "remaining": 15, "handoffs": 0}
    api_online = False
if not api_online:
    st.warning("API is not reachable. Start it with `uvicorn app.main:app --reload` in a separate terminal.")

m1,m2,m3,m4,m5=st.columns(5)
with m1: metric("Profiles discovered", str(metrics.get("total_profiles_discovered",0)), "Saved locally")
with m2: metric("Profiles scored", str(metrics.get("profiles_scored",0)), "Public evidence only")
with m3: metric("Freshers", str(metrics.get("profiles_by_persona",{}).get("Fresher",0)), "Persona matches")
with m4: metric("Confirmed sends today", str(metrics.get("confirmed_sends",0)), f"{metrics.get('handoffs',0)} handoffs do not count")
with m5: metric("Daily allowance left", str(metrics.get("remaining",15)), f"of {metrics.get('limit',15)} confirmed sends")

st.markdown("### Discovery")
with st.container(border=True):
    left,right=st.columns([1.15,1])
    with left:
        selected=st.multiselect("Learner buckets",["A · Students & freshers","B · Early career · 1–2 YOE","C · Career switchers"],default=["A · Students & freshers","B · Early career · 1–2 YOE","C · Career switchers"],key="bucket_select")
        bucket_codes=[x[0] for x in selected]
        keyword=st.text_input("Optional keyword",placeholder="e.g. machine learning, Python, LLM")
        location=st.text_input("Optional location",placeholder="e.g. Toronto, Canada")
    with right:
        offline=st.toggle("Offline demo mode",value=settings.offline_mode_default,key="offline_toggle",help="Uses synthetic profiles and deterministic demo scoring. Makes no external search or LLM calls.")
        st.caption("Live mode uses the configured public search provider and LLM; it never visits LinkedIn profile pages.")
        if st.button("Build search queries",use_container_width=True):
            try:
                queries=build_queries(QueryRequest(buckets=bucket_codes or ["A"],keyword=keyword,location=location))
                st.session_state.generated_queries=queries.queries
            except Exception as exc: st.error(str(exc))
        if st.button("Run discovery",type="primary",use_container_width=True,disabled=not api_online):
            try:
                with st.spinner("Searching public results and preparing profiles…"):
                    response=api_post("/api/discover",DiscoveryRequest(buckets=bucket_codes or ["A"],keyword=keyword,location=location,offline=offline).model_dump())
                st.session_state.profiles=response["profiles"]
                st.session_state.last_errors=response["errors"]
                st.session_state.generated_queries=response["queries"]
                st.session_state.offline_results=offline
                st.success(f"Added {response['discovered_count']} new profiles · {response['duplicate_count']} already in history.")
            except Exception as exc: st.error(f"Discovery failed: {exc}")
    for query in st.session_state.get("generated_queries",[]): st.code(query,language="text")
    if st.session_state.get("offline_results"):
        st.markdown('<div class="demo">DEMO DATA — these learner profiles are fictional; offline scoring is deterministic and not an AI model result.</div>',unsafe_allow_html=True)
    for error in st.session_state.last_errors: st.warning(error)

st.markdown("### Discovery results")
if not st.session_state.profiles:
    st.info("Choose buckets and run discovery to see candidates. Previous activity is available in History.")
for i, profile in enumerate(st.session_state.profiles):
    url=profile["profile_url"]
    st.markdown(f'<div class="candidate"><h3>{html.escape(profile["name"])}</h3><div class="muted">{html.escape(profile.get("headline", ""))}</div><span class="pill">{html.escape(profile["detected_persona"].replace("_"," "))}</span><span class="pill">Relevance {profile["relevance_score"]}/10</span><div class="muted" style="margin-top:10px">{html.escape(profile.get("reasoning", ""))}</div><p>{html.escape(profile.get("snippet", ""))}</p><a href="{html.escape(url,quote=True)}" target="_blank" rel="noopener noreferrer">Open public LinkedIn profile ↗</a></div>',unsafe_allow_html=True)
    with st.expander(f"Edit outreach · {profile['name']}",expanded=True):
        note_key=f"note_{url}"; dm_key=f"dm_{url}"
        if note_key not in st.session_state: st.session_state[note_key]=profile["connection_note"]
        if dm_key not in st.session_state: st.session_state[dm_key]=profile["follow_up_dm"]
        note=st.text_area("Connection note",key=note_key,height=95,max_chars=299)
        st.caption(f"{len(note)}/299 characters")
        dm=st.text_area("Follow-up DM",key=dm_key,height=145)
        st.caption(f"{len(dm.split())}/99 words")
        copy_text=html.escape(note,quote=True)
        st.markdown(f'<button onclick="navigator.clipboard.writeText(\'{copy_text}\')" style="border:1px solid #d3ddec;border-radius:8px;padding:7px 12px;background:white;cursor:pointer">Copy connection note</button>',unsafe_allow_html=True)
        cols=st.columns([1,1,2])
        with cols[0]:
            if st.button("Record handoff",key=f"handoff_{i}",disabled=not api_online):
                try:
                    api_post(f"/api/profiles/{quote(url,safe='')}/handoff",{"connection_note":note,"follow_up_dm":dm})
                    st.success("Handoff recorded. Review and send manually; this does not count toward today's send limit.")
                except Exception as exc: st.error(str(exc))
        with cols[1]:
            confirm=st.checkbox("I manually sent this message",key=f"confirm_checkbox_{i}")
            if st.button("Confirm sent",key=f"confirm_{i}",disabled=not (api_online and confirm and metrics.get("remaining",0)>0)):
                try:
                    result=api_post(f"/api/profiles/{quote(url,safe='')}/confirm-sent",{"confirmed":True})
                    st.success(f"Confirmation recorded. Remaining today: {result['result']['remaining']}")
                    st.rerun()
                except Exception as exc: st.error(str(exc))
        with cols[2]: st.caption("This app never sends messages or automates LinkedIn. Confirm only after manual sending.")

st.markdown("### History")
hcol1,hcol2,hcol3=st.columns([1,1,1])
with hcol1: status_filter=st.selectbox("Contact status",["All","discovered","handoff_initiated","contacted"])
with hcol2: persona_filter=st.selectbox("Persona",["All","Fresher","1-2_YOE","Career_Switcher"])
with hcol3: st.write(""); st.write("")
if api_online:
    try:
        params={}
        if status_filter!="All": params["status"]=status_filter
        if persona_filter!="All": params["persona"]=persona_filter
        records=api_get("/api/history",params).get("records",[])
        if records:
            st.dataframe([{ "Name":r["candidate_name"],"Persona":r["persona"],"Status":r["status"],"Handoffs":r["handoff_count"],"Updated":r["updated_at"],"Profile":r["profile_url"]} for r in records],use_container_width=True,hide_index=True)
            with st.expander("Review saved outreach messages"):
                for r in records:
                    st.markdown(f"**{r['candidate_name']} · {r['status']}**")
                    st.text_area("Saved note",r["connection_note"],key=f"history_note_{r['profile_url']}",disabled=True)
                    st.text_area("Saved DM",r["follow_up_dm"],key=f"history_dm_{r['profile_url']}",disabled=True)
        else: st.caption("No history matches those filters.")
    except Exception as exc: st.warning(f"History unavailable: {exc}")
with st.expander("Clear local history"):
    st.warning("This permanently clears the local SQLite outreach records and send confirmations.")
    if st.button("Clear all local history",disabled=not api_online):
        try:
            result=requests.delete(f"{API_BASE}/api/history",params={"confirm":"true"},timeout=8); result.raise_for_status()
            st.session_state.profiles=[]; st.success(f"Cleared {result.json()['deleted_records']} records."); st.rerun()
        except Exception as exc: st.error(f"Could not clear history: {exc}")

st.caption("Responsible use: public search result data can be stale or incomplete. Verify it before outreach. External search follows provider terms; no LinkedIn scraping, credentials, cookies, or automated messages are used.")
