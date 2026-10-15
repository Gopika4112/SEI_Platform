"""
CodeAtlas — UI
Multi-Agent Code Intelligence Platform
"""

import json
import random
import time
from typing import Optional

import requests
import streamlit as st
import streamlit.components.v1 as components

# ── Constants ─────────────────────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000/api"
AGENTS   = ["Planner", "Retriever", "Graph", "Answer", "Evaluator"]
AGENT_ICONS = {"Planner": "🧠", "Retriever": "🔍", "Graph": "🕸️", "Answer": "✍️", "Evaluator": "⚖️"}
AGENT_COLORS = {
    "Planner":   "#38BDF8",
    "Retriever": "#818CF8",
    "Graph":     "#10B981",
    "Answer":    "#F59E0B",
    "Evaluator": "#A78BFA",
}

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CodeAtlas — AI Code Intelligence",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif !important;
}
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; }
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0C1529; }
::-webkit-scrollbar-thumb { background: #1E293B; border-radius: 2px; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #070E1C !important;
    border-right: 1px solid rgba(255,255,255,0.05) !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }
[data-testid="stSidebar"] .stTextInput input {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 8px !important;
    color: #94A3B8 !important;
    font-size: 0.82rem !important;
}
[data-testid="stSidebar"] .stTextInput input:focus {
    border-color: rgba(56,189,248,0.4) !important;
    box-shadow: 0 0 0 2px rgba(56,189,248,0.08) !important;
}

/* ── Sidebar Logo ── */
.atlas-sidebar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 0 16px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    margin-bottom: 16px;
}
.atlas-logo-mark {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #38BDF8, #818CF8);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
}
.atlas-logo-name { font-size: 1rem; font-weight: 700; color: #F1F5F9; letter-spacing: -0.01em; }
.atlas-logo-tag  { font-size: 0.65rem; color: #334155; font-weight: 500; letter-spacing: 0.05em; text-transform: uppercase; margin-top: 1px; }

/* ── Section Label ── */
.section-label {
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #1E293B;
    margin-bottom: 8px;
    margin-top: 4px;
}

/* ── Health Grid ── */
.health-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 6px;
    margin-bottom: 4px;
}
.health-cell {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px;
    padding: 8px 4px;
    text-align: center;
    font-size: 0.68rem;
    color: #475569;
    transition: border-color 0.2s;
}
.health-svc { font-weight: 600; color: #64748B; margin-bottom: 4px; }
.health-dot { font-size: 0.78rem; }
.h-ok   { border-left: 2px solid #10B981 !important; }
.h-dead { border-left: 2px solid #EF4444 !important; }

/* ── Stat Cards (sidebar) ── */
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 10px; }
.stat-card {
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 8px;
    padding: 10px 8px;
    text-align: center;
}
.stat-val   { font-size: 1.15rem; font-weight: 700; color: #38BDF8; font-family: 'JetBrains Mono', monospace; }
.stat-label { font-size: 0.62rem; color: #334155; text-transform: uppercase; letter-spacing: 0.09em; margin-top: 2px; }

/* ── Buttons ── */
.stButton > button {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #64748B !important;
    border-radius: 8px !important;
    font-size: 0.82rem !important;
    font-weight: 500 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0.01em !important;
}
.stButton > button:hover {
    background: rgba(56,189,248,0.07) !important;
    border-color: rgba(56,189,248,0.28) !important;
    color: #38BDF8 !important;
}
/* Primary (index, danger) buttons */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #38BDF8, #818CF8) !important;
    border: none !important;
    color: #0F172A !important;
    font-weight: 600 !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid rgba(255,255,255,0.06) !important;
    gap: 0 !important;
    padding-left: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #475569 !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 10px 22px !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.18s ease !important;
}
.stTabs [aria-selected="true"] {
    color: #38BDF8 !important;
    border-bottom-color: #38BDF8 !important;
    background: rgba(56,189,248,0.04) !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #94A3B8 !important;
    background: rgba(255,255,255,0.02) !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background: transparent !important;
    padding: 1.4rem 0 0 0 !important;
}

/* ── Main Title ── */
.atlas-title {
    background: linear-gradient(135deg, #38BDF8 0%, #818CF8 55%, #A78BFA 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 800;
    font-size: 2.2rem;
    letter-spacing: -0.03em;
    line-height: 1;
    margin-bottom: 4px;
    display: inline-block;
}
.atlas-subtitle {
    color: #334155;
    font-size: 0.85rem;
    font-weight: 400;
    letter-spacing: 0.02em;
    margin-bottom: 1.2rem;
}

/* ── Answer Card Wrapper ── */
.answer-card {
    background: linear-gradient(160deg, rgba(12,21,41,0.95) 0%, rgba(7,14,28,0.98) 100%);
    border: 1px solid rgba(56,189,248,0.1);
    border-radius: 14px;
    padding: 18px 20px 14px;
    margin-bottom: 2px;
    box-shadow: 0 2px 20px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.04);
}

/* ── Badges ── */
.badge-row { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-bottom: 12px; }
.badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 11px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.03em;
    font-family: 'Inter', sans-serif;
    white-space: nowrap;
}
.badge-intent  { background: rgba(56,189,248,0.10);  color: #38BDF8; border: 1px solid rgba(56,189,248,0.22); }
.badge-green   { background: rgba(16,185,129,0.10);  color: #10B981; border: 1px solid rgba(16,185,129,0.22); }
.badge-amber   { background: rgba(245,158,11,0.10);  color: #F59E0B; border: 1px solid rgba(245,158,11,0.22); }
.badge-red     { background: rgba(239,68,68,0.10);   color: #EF4444; border: 1px solid rgba(239,68,68,0.22); }
.badge-purple  { background: rgba(167,139,250,0.10); color: #A78BFA; border: 1px solid rgba(167,139,250,0.22); }
.badge-gray    { background: rgba(100,116,139,0.10); color: #64748B; border: 1px solid rgba(100,116,139,0.18); }

/* ── Agent Trace ── */
.agent-trace {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 14px;
    padding: 8px 12px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px;
    overflow-x: auto;
}
.agent-pill {
    font-size: 0.67rem;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 10px;
    white-space: nowrap;
    letter-spacing: 0.03em;
    font-family: 'Inter', sans-serif;
}
.trace-arrow { color: #1E293B; font-size: 0.75rem; }

/* ── Eval Feedback ── */
.eval-feedback {
    font-size: 0.74rem;
    color: #475569;
    font-style: italic;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid rgba(255,255,255,0.04);
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.5;
}

/* ── Code Header ── */
.code-file-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #475569;
    background: #0C1529;
    padding: 5px 12px;
    border-radius: 6px 6px 0 0;
    border: 1px solid rgba(255,255,255,0.05);
    border-bottom: none;
}
.cite-meta {
    font-size: 0.75rem;
    color: #475569;
    margin-bottom: 2px;
    font-family: 'JetBrains Mono', monospace;
}

/* ── Progress ── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #38BDF8, #818CF8) !important;
    border-radius: 4px !important;
}
.stage-text {
    font-size: 0.75rem;
    color: #38BDF8;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 4px;
}

/* ── Chat ── */
[data-testid="stChatMessage"] { background: transparent !important; }
[data-testid="stChatInput"] textarea {
    background: rgba(10,16,32,0.8) !important;
    border: 1px solid rgba(56,189,248,0.15) !important;
    border-radius: 12px !important;
    color: #E2E8F0 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: rgba(56,189,248,0.4) !important;
    box-shadow: 0 0 0 3px rgba(56,189,248,0.06) !important;
}

/* ── Stats Tab ── */
.big-stat {
    background: linear-gradient(160deg, rgba(12,21,41,0.9) 0%, rgba(7,14,28,0.95) 100%);
    border: 1px solid rgba(56,189,248,0.1);
    border-radius: 14px;
    padding: 24px 20px;
    text-align: center;
}
.big-stat-val   { font-size: 2.5rem; font-weight: 800; font-family: 'JetBrains Mono'; letter-spacing: -0.04em; }
.big-stat-label { font-size: 0.7rem; color: #334155; text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px; }

.entity-row {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px;
    border-radius: 8px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    margin-bottom: 6px;
}
.entity-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.entity-name { font-size: 0.82rem; color: #94A3B8; font-weight: 500; flex: 1; font-family: 'JetBrains Mono'; }
.entity-count { font-size: 0.82rem; color: #475569; font-family: 'JetBrains Mono'; }
.entity-bar-wrap { flex: 2; height: 4px; background: rgba(255,255,255,0.05); border-radius: 2px; }
.entity-bar { height: 4px; border-radius: 2px; }

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.05) !important; margin: 10px 0 !important; }

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    color: #94A3B8 !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "chat_history":  [],
        "indexed_repos": {},
        "selected_repo": "",
        "active_tab":    0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── API Helpers ───────────────────────────────────────────────────────────────
def api_health() -> dict:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=4)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def api_repos() -> list:
    try:
        r = requests.get(f"{API_BASE}/repos", timeout=3)
        return r.json().get("repos", []) if r.status_code == 200 else []
    except Exception:
        return []

def api_ingest(url: str, branch: Optional[str]) -> Optional[str]:
    try:
        payload = {"github_url": url, "branch": branch or None}
        r = requests.post(f"{API_BASE}/ingest", json=payload, timeout=5)
        return r.json().get("job_id") if r.status_code == 200 else None
    except Exception:
        return None

def api_poll(job_id: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}/ingest/{job_id}", timeout=3)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def api_query(question: str, repo_id: str) -> dict:
    try:
        r = requests.post(f"{API_BASE}/query",
                          json={"question": question, "repo_id": repo_id},
                          timeout=120)
        if r.status_code == 200:
            d = r.json()
            cites = [{"file": s, "type": "Reference", "code": f"# {s}"} for s in d.get("sources", [])]
            return {
                "intent":        d.get("intent", "Unknown"),
                "eval_score":    d.get("eval_score", 0.0),
                "eval_feedback": d.get("eval_feedback", ""),
                "answer":        d.get("answer", "No response."),
                "citations":     cites,
            }
    except requests.exceptions.Timeout as e:
        print(f"Backend timeout error: {e}")
        return {
            "intent": "Error", "eval_score": 0.0,
            "eval_feedback": "Request timed out.",
            "answer": "⚠️ **Query timed out.** The multi-agent pipeline took longer than 120 seconds to respond. Please try again or check uvicorn server logs.",
            "citations": [],
        }
    except Exception as e:
        print(f"Backend connection error: {e}")
        return {
            "intent": "Error", "eval_score": 0.0,
            "eval_feedback": "Backend unreachable.",
            "answer": "⚠️ **Backend offline.** Please ensure the uvicorn API server is running on http://127.0.0.1:8000.",
            "citations": [],
        }

def api_graph(repo_id: str) -> dict:
    try:
        r = requests.get(f"{API_BASE}/graph/{repo_id}", timeout=5)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def api_delete(repo_id: str) -> bool:
    try:
        r = requests.delete(f"{API_BASE}/repo/{repo_id}", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


# (Mock data variables have been removed to connect directly to the database)


# ── D3.js Interactive Graph Builder ──────────────────────────────────────────
def build_graph_html(nodes_data: list, edges_data: list) -> str:
    nodes_json = json.dumps(nodes_data)
    edges_json = json.dumps(edges_data)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: #060D1A;
    font-family: 'Inter', -apple-system, sans-serif;
    overflow: hidden;
    height: 100vh;
    color: #E2E8F0;
}}
#container {{ display: flex; flex-direction: column; height: 100vh; }}

/* Toolbar */
#toolbar {{
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px;
    background: #0A1020;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    flex-shrink: 0; flex-wrap: wrap;
}}
.toolbar-sep {{ width: 1px; height: 18px; background: rgba(255,255,255,0.07); margin: 0 2px; }}
.t-label {{ font-size: 10px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: #1E293B; }}
.filter-chip {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 9px; border-radius: 10px;
    font-size: 10px; font-weight: 600; cursor: pointer;
    border: 1px solid; transition: opacity 0.2s;
    user-select: none; letter-spacing: 0.02em;
}}
.filter-chip.off {{ opacity: 0.22; }}
.fc-Function {{ background: rgba(59,130,246,0.15); color: #60A5FA;  border-color: rgba(59,130,246,0.3); }}
.fc-Class    {{ background: rgba(139,92,246,0.15);  color: #A78BFA; border-color: rgba(139,92,246,0.3); }}
.fc-File     {{ background: rgba(16,185,129,0.15);  color: #34D399; border-color: rgba(16,185,129,0.3); }}
.fc-Method   {{ background: rgba(6,182,212,0.15);   color: #22D3EE; border-color: rgba(6,182,212,0.3); }}
.fc-Module   {{ background: rgba(245,158,11,0.15);  color: #FCD34D; border-color: rgba(245,158,11,0.3); }}
.ec-CALLS      {{ background: rgba(59,130,246,0.1);  color: #93C5FD; border-color: rgba(59,130,246,0.2); }}
.ec-IMPORTS    {{ background: rgba(6,182,212,0.1);   color: #67E8F9; border-color: rgba(6,182,212,0.2); }}
.ec-INHERITS   {{ background: rgba(139,92,246,0.1);  color: #C4B5FD; border-color: rgba(139,92,246,0.2); }}
.ec-DEFINED_IN {{ background: rgba(100,116,139,0.08);color: #64748B; border-color: rgba(100,116,139,0.18); }}
.ec-HAS_METHOD {{ background: rgba(16,185,129,0.08); color: #6EE7B7; border-color: rgba(16,185,129,0.18); }}

#search {{
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 7px; color: #E2E8F0; font-size: 11px;
    padding: 4px 11px; outline: none; width: 170px; transition: border-color 0.2s;
}}
#search:focus {{ border-color: #38BDF8; }}
#reset, #fullscreen {{ 
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07);
    color: #475569; cursor: pointer; font-size: 10px;
    padding: 4px 10px; border-radius: 6px; transition: all 0.18s;
}}
#reset:hover, #fullscreen:hover {{ color: #E2E8F0; background: rgba(255,255,255,0.06); }}
#count {{ margin-left: auto; font-size: 10px; color: #1E293B; font-family: monospace; }}

/* Graph area */
#graph-area {{ display: flex; flex: 1; min-height: 0; }}
#svg-wrap {{ flex: 1; min-width: 0; position: relative; }}
svg {{ width: 100%; height: 100%; cursor: grab; }}
svg:active {{ cursor: grabbing; }}

/* Detail panel */
#panel {{
    width: 0; overflow: hidden;
    background: #080F1E;
    border-left: 1px solid rgba(255,255,255,0.05);
    transition: width 0.25s ease;
    flex-shrink: 0;
    position: relative;
}}
#panel.open {{ width: 240px; overflow-y: auto; }}
#panel-inner {{ padding: 14px; min-width: 240px; }}
#panel-close {{
    position: sticky; top: 0;
    float: right; background: rgba(255,255,255,0.05);
    border: none; color: #475569; cursor: pointer;
    border-radius: 50%; width: 20px; height: 20px;
    font-size: 11px; display: flex; align-items: center; justify-content: center;
    margin-bottom: 8px;
}}
#panel-close:hover {{ color: #E2E8F0; }}
.p-type-badge {{
    display: inline-block; padding: 2px 9px; border-radius: 10px;
    font-size: 10px; font-weight: 600; margin-bottom: 8px;
}}
.p-name {{ font-size: 13px; font-weight: 700; color: #F1F5F9; margin-bottom: 10px; word-break: break-all; line-height: 1.3; }}
.p-key {{ font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #1E293B; margin-bottom: 3px; margin-top: 8px; }}
.p-val {{ font-size: 11px; color: #64748B; font-family: monospace; word-break: break-all; }}
.conn-title {{ font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #1E293B; margin: 12px 0 6px; }}
.conn-item {{
    font-size: 10px; color: #475569; padding: 5px 8px;
    border-radius: 6px; background: rgba(255,255,255,0.02);
    margin-bottom: 4px; cursor: pointer;
    border: 1px solid rgba(255,255,255,0.04);
    font-family: monospace; display: flex; align-items: center; gap: 6px;
}}
.conn-item:hover {{ background: rgba(56,189,248,0.06); color: #38BDF8; }}
.conn-edge {{ font-size: 9px; color: #1E293B; flex-shrink: 0; }}

/* Tooltip */
#tip {{
    position: fixed; background: #0C1829;
    border: 1px solid rgba(255,255,255,0.08); border-radius: 8px;
    padding: 7px 11px; font-size: 11px; color: #E2E8F0;
    pointer-events: none; display: none; z-index: 999;
    max-width: 210px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    font-family: monospace; line-height: 1.5;
}}
</style>
</head>
<body>
<div id="container">
  <div id="toolbar">
    <span class="t-label">Nodes</span>
    <span class="filter-chip fc-Function" data-ntype="Function">⬤ Function</span>
    <span class="filter-chip fc-Class"    data-ntype="Class">⬤ Class</span>
    <span class="filter-chip fc-File"     data-ntype="File">⬤ File</span>
    <span class="filter-chip fc-Method"   data-ntype="Method">⬤ Method</span>
    <span class="filter-chip fc-Module"   data-ntype="Module">⬤ Module</span>
    <div class="toolbar-sep"></div>
    <span class="t-label">Edges</span>
    <span class="filter-chip ec-CALLS"      data-etype="CALLS">CALLS</span>
    <span class="filter-chip ec-IMPORTS"    data-etype="IMPORTS">IMPORTS</span>
    <span class="filter-chip ec-INHERITS"   data-etype="INHERITS">INHERITS</span>
    <span class="filter-chip ec-DEFINED_IN" data-etype="DEFINED_IN">DEFINED_IN</span>
    <span class="filter-chip ec-HAS_METHOD" data-etype="HAS_METHOD">HAS_METHOD</span>
    <div class="toolbar-sep"></div>
    <input id="search" type="text" placeholder="Search nodes...">
    <button id="reset">⟲ Reset</button>
    <button id="fullscreen">⛶ Fullscreen</button>
    <span id="count"></span>
  </div>

  <div id="graph-area">
    <div id="svg-wrap"><svg id="svg"></svg></div>
    <div id="panel">
      <div id="panel-inner">
        <button id="panel-close">✕</button>
        <div id="panel-body"></div>
      </div>
    </div>
  </div>
</div>
<div id="tip"></div>

<script>
const RAW_NODES = {nodes_json};
const RAW_EDGES = {edges_json};

const NODE_COLOR = {{
  Function:"#3B82F6", Class:"#8B5CF6", File:"#10B981",
  Method:"#06B6D4",   Module:"#F59E0B"
}};
const NODE_R = {{ Function:10, Class:13, File:14, Method:8, Module:10 }};
const EDGE_COLOR = {{
  CALLS:"#3B82F6", IMPORTS:"#06B6D4", INHERITS:"#8B5CF6",
  DEFINED_IN:"#1E293B", HAS_METHOD:"#10B981"
}};

let activeN = new Set(["Function","Class","File","Method","Module"]);
let activeE = new Set(["CALLS","IMPORTS","INHERITS","DEFINED_IN","HAS_METHOD"]);
let sim, linkSel, nodeSel, labelSel, selectedId = null;

// SVG + zoom
const svgEl  = d3.select("#svg");
const svgWrap = document.getElementById("svg-wrap");
const rootG  = svgEl.append("g");
const zoom   = d3.zoom().scaleExtent([0.15, 5])
  .on("zoom", e => rootG.attr("transform", e.transform));
svgEl.call(zoom);

// Arrow markers
const defs = svgEl.append("defs");
Object.entries(EDGE_COLOR).forEach(([t, c]) => {{
  defs.append("marker")
    .attr("id","arr-"+t).attr("viewBox","0 -4 10 8")
    .attr("refX", 22).attr("refY", 0)
    .attr("markerWidth",5).attr("markerHeight",5).attr("orient","auto")
    .append("path").attr("fill", c).attr("d","M0,-4L10,0L0,4");
}});

function getVisible() {{
  const vN  = RAW_NODES.filter(n => activeN.has(n.type));
  const ids  = new Set(vN.map(n => n.id));
  const vE  = RAW_EDGES.filter(e => {{
    const s = typeof e.source==='object'? e.source.id : e.source;
    const t = typeof e.target==='object'? e.target.id : e.target;
    return activeE.has(e.type) && ids.has(s) && ids.has(t);
  }});
  return {{ vN, vE }};
}}

function rebuild() {{
  rootG.selectAll("*").remove();
  const {{ vN, vE }} = getVisible();
  document.getElementById("count").textContent = vN.length + " nodes · " + vE.length + " edges";

  const nodes = vN.map(n => ({{...n}}));
  const edges = vE.map(e => ({{...e}}));

  sim = d3.forceSimulation(nodes)
    .force("link",   d3.forceLink(edges).id(d=>d.id).distance(115).strength(0.55))
    .force("charge", d3.forceManyBody().strength(-340))
    .force("center", d3.forceCenter(svgWrap.clientWidth/2, svgWrap.clientHeight/2))
    .force("collide",d3.forceCollide().radius(d => (NODE_R[d.type]||10)+20));

  linkSel = rootG.append("g")
    .selectAll("line").data(edges).join("line")
    .attr("stroke",        d => EDGE_COLOR[d.type]||"#1E293B")
    .attr("stroke-width",  1.4)
    .attr("stroke-opacity",0.45)
    .attr("marker-end",    d => "url(#arr-"+d.type+")");

  nodeSel = rootG.append("g")
    .selectAll("circle").data(nodes).join("circle")
    .attr("r",            d => NODE_R[d.type]||10)
    .attr("fill",         d => NODE_COLOR[d.type]||"#475569")
    .attr("fill-opacity", 0.88)
    .attr("stroke",       d => NODE_COLOR[d.type]||"#475569")
    .attr("stroke-width", 1.8)
    .attr("stroke-opacity",0.35)
    .style("cursor","pointer")
    .call(d3.drag()
      .on("start", (e,d) => {{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
      .on("drag",  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
      .on("end",   (e,d) => {{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }})
    )
    .on("mouseover", (e,d) => {{
      const tip = document.getElementById("tip");
      tip.innerHTML = "<b>"+d.label+"</b><br>"
        + "<span style='color:#475569'>"+d.type+"</span>"
        + (d.file ? "<br>"+d.file : "")
        + (d.lines? "<br>lines "+d.lines:"");
      tip.style.display="block";
    }})
    .on("mousemove", e => {{
      const tip=document.getElementById("tip");
      tip.style.left=(e.clientX+14)+"px"; tip.style.top=(e.clientY-8)+"px";
    }})
    .on("mouseout",  () => document.getElementById("tip").style.display="none")
    .on("click",     (e,d) => {{ e.stopPropagation(); selectNode(d, nodes, edges); }});

  labelSel = rootG.append("g")
    .selectAll("text").data(nodes).join("text")
    .text(d => d.label.length>16? d.label.slice(0,13)+"…":d.label)
    .attr("font-size","8.5px").attr("fill","#334155")
    .attr("text-anchor","middle")
    .attr("dy", d => (NODE_R[d.type]||10)+10)
    .attr("pointer-events","none");

  sim.on("tick", () => {{
    linkSel.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y)
           .attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
    nodeSel.attr("cx",d=>d.x).attr("cy",d=>d.y);
    labelSel.attr("x",d=>d.x).attr("y",d=>d.y);
  }});
}}

function selectNode(d, nodes, edges) {{
  selectedId = d.id;
  // Highlight neighbourhood
  const nbrs = new Set([d.id]);
  edges.forEach(e => {{
    const s=typeof e.source==='object'?e.source.id:e.source;
    const t=typeof e.target==='object'?e.target.id:e.target;
    if(s===d.id||t===d.id){{ nbrs.add(s); nbrs.add(t); }}
  }});
  nodeSel.attr("fill-opacity",  n => nbrs.has(n.id)?1.0:0.1)
         .attr("stroke-opacity",n => nbrs.has(n.id)?1.0:0.05);
  linkSel.attr("stroke-opacity",e => {{
    const s=typeof e.source==='object'?e.source.id:e.source;
    const t=typeof e.target==='object'?e.target.id:e.target;
    return(s===d.id||t===d.id)?0.9:0.04;
  }});
  labelSel.attr("fill",n=>nbrs.has(n.id)?"#94A3B8":"#0F172A");

  // Build connections list
  const conns=[];
  RAW_EDGES.forEach(e=>{{
    const s=typeof e.source==='object'?e.source.id:e.source;
    const t=typeof e.target==='object'?e.target.id:e.target;
    if(s===d.id){{const tn=RAW_NODES.find(n=>n.id===t);if(tn)conns.push({{nd:tn,type:e.type,dir:"→"}});}}
    else if(t===d.id){{const sn=RAW_NODES.find(n=>n.id===s);if(sn)conns.push({{nd:sn,type:e.type,dir:"←"}});}}
  }});
  const col=NODE_COLOR[d.type]||"#475569";
  document.getElementById("panel-body").innerHTML=`
    <span class="p-type-badge" style="background:${{col}}22;color:${{col}};border:1px solid ${{col}}44">${{d.type}}</span>
    <div class="p-name">${{d.label}}</div>
    ${{d.file?`<div class="p-key">File</div><div class="p-val">${{d.file}}</div>`:""}}
    ${{d.lines?`<div class="p-key">Lines</div><div class="p-val">${{d.lines}}</div>`:""}}
    <div class="conn-title">Connections (${{conns.length}})</div>
    ${{conns.slice(0,12).map(c=>`
      <div class="conn-item" onclick="jumpTo('${{c.nd.id}}')">
        <span class="conn-edge">${{c.dir}} ${{c.type}}</span>
        <span style="color:${{NODE_COLOR[c.nd.type]||'#64748B'}}">${{c.nd.label}}</span>
      </div>`).join("")}}
    ${{conns.length>12?`<div style="font-size:9px;color:#1E293B;margin-top:4px">+${{conns.length-12}} more</div>`:""}}
  `;
  document.getElementById("panel").classList.add("open");
}}

function jumpTo(id) {{
  const allNodes = sim.nodes();
  const n = allNodes.find(d=>d.id===id);
  if(n) {{
    selectNode(n, allNodes, []);
    svgEl.transition().duration(450).call(zoom.transform,
      d3.zoomIdentity.translate(svgWrap.clientWidth/2-n.x*1.5, svgWrap.clientHeight/2-n.y*1.5).scale(1.5));
  }}
}}

document.getElementById("panel-close").addEventListener("click", () => {{
  document.getElementById("panel").classList.remove("open");
  selectedId=null;
  if(nodeSel) {{
    nodeSel.attr("fill-opacity",0.88).attr("stroke-opacity",0.35);
    linkSel.attr("stroke-opacity",0.45);
    labelSel.attr("fill","#334155");
  }}
}});

svgEl.on("click",()=>{{
  if(selectedId) document.getElementById("panel-close").click();
}});

// Filters
document.querySelectorAll("[data-ntype]").forEach(chip=>{{
  chip.addEventListener("click",()=>{{
    const t=chip.dataset.ntype;
    if(activeN.has(t)){{ if(activeN.size>1){{activeN.delete(t);chip.classList.add("off");}} }}
    else {{ activeN.add(t); chip.classList.remove("off"); }}
    rebuild();
  }});
}});
document.querySelectorAll("[data-etype]").forEach(chip=>{{
  chip.addEventListener("click",()=>{{
    const t=chip.dataset.etype;
    if(activeE.has(t)){{activeE.delete(t);chip.classList.add("off");}}
    else {{activeE.add(t);chip.classList.remove("off");}}
    rebuild();
  }});
}});

// Search
document.getElementById("search").addEventListener("input", function(){{
  const q=this.value.toLowerCase().trim();
  if(!q){{
    if(nodeSel){{nodeSel.attr("fill-opacity",0.88).attr("stroke-opacity",0.35);}}
    if(labelSel){{labelSel.attr("fill","#334155");}}
    if(linkSel){{linkSel.attr("stroke-opacity",0.45);}}
    return;
  }}
  if(nodeSel){{
    nodeSel.attr("fill-opacity",d=>d.label.toLowerCase().includes(q)?1.0:0.08)
           .attr("stroke-opacity",d=>d.label.toLowerCase().includes(q)?1.0:0.04);
    labelSel.attr("fill",d=>d.label.toLowerCase().includes(q)?"#F1F5F9":"#0F172A");
    linkSel.attr("stroke-opacity",0.04);
  }}
}});

// Reset
document.getElementById("reset").addEventListener("click",()=>{{
  svgEl.transition().duration(380).call(zoom.transform, d3.zoomIdentity);
  document.getElementById("search").value="";
  if(nodeSel){{nodeSel.attr("fill-opacity",0.88).attr("stroke-opacity",0.35);}}
  if(labelSel){{labelSel.attr("fill","#334155");}}
  if(linkSel){{linkSel.attr("stroke-opacity",0.45);}}
}});

// Fullscreen API Integration
const container = document.getElementById("container");
const fsButton = document.getElementById("fullscreen");

fsButton.addEventListener("click", () => {{
  if (!document.fullscreenElement) {{
    container.requestFullscreen().then(() => {{
      fsButton.textContent = "✕ Exit";
    }}).catch(err => {{
      console.error("Error attempting to enable fullscreen:", err);
    }});
  }} else {{
    document.exitFullscreen().then(() => {{
      fsButton.textContent = "⛶ Fullscreen";
    }});
  }}
}});

document.addEventListener("fullscreenchange", () => {{
  if (!document.fullscreenElement) {{
    fsButton.textContent = "⛶ Fullscreen";
  }}
}});

rebuild();
</script>
</body>
</html>"""


# ── Helper: Build Badge HTML ──────────────────────────────────────────────────
def eval_badge(score: float) -> str:
    if score >= 8.0:
        cls, icon = "badge-green", "✓"
    elif score >= 6.0:
        cls, icon = "badge-amber", "~"
    else:
        cls, icon = "badge-red", "✗"
    return f'<span class="badge {cls}">{icon} Eval {score:.1f}/10</span>'

def agent_trace_html() -> str:
    pills = []
    for i, name in enumerate(AGENTS):
        col = AGENT_COLORS[name]
        icon = AGENT_ICONS[name]
        pills.append(
            f'<span class="agent-pill" style="background:{col}18;color:{col};border:1px solid {col}33">'
            f'{icon} {name}</span>'
        )
        if i < len(AGENTS) - 1:
            pills.append('<span class="trace-arrow">›</span>')
    return '<div class="agent-trace">' + "".join(pills) + '</div>'


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:

    # Logo
    st.markdown("""
    <div class="atlas-sidebar-logo">
      <div class="atlas-logo-mark">🧭</div>
      <div>
        <div class="atlas-logo-name">CodeAtlas</div>
        <div class="atlas-logo-tag">AI Code Intelligence</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Health Status ────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Infrastructure</div>', unsafe_allow_html=True)

    h = api_health()
    def hcell(svc, key):
        ok = h.get(key) == "ok"
        cls = "h-ok" if ok else "h-dead"
        dot_col = "#10B981" if ok else "#EF4444"
        txt = "● Online" if ok else "○ Offline"
        return f'<div class="health-cell {cls}"><div class="health-svc">{svc}</div><span class="health-dot" style="color:{dot_col}">{txt}</span></div>'

    if h:
        st.markdown(
            f'<div class="health-grid">{hcell("Qdrant","qdrant")}{hcell("Neo4j","neo4j")}{hcell("Groq","groq")}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown("""
        <div class="health-grid">
          <div class="health-cell h-dead"><div class="health-svc">Qdrant</div><span class="health-dot" style="color:#EF4444">○ Offline</span></div>
          <div class="health-cell h-dead"><div class="health-svc">Neo4j</div><span class="health-dot" style="color:#EF4444">○ Offline</span></div>
          <div class="health-cell h-dead"><div class="health-svc">Groq</div><span class="health-dot" style="color:#EF4444">○ Offline</span></div>
        </div>
        <div style="font-size:0.65rem;color:#EF4444;margin-top:4px">⚠ uvicorn unreachable — start the FastAPI server</div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── Index Repository ─────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Index Repository</div>', unsafe_allow_html=True)
    new_url    = st.text_input("GitHub URL", placeholder="https://github.com/owner/repo", label_visibility="collapsed")
    new_branch = st.text_input("Branch (optional)", placeholder="main", label_visibility="collapsed")

    if st.button("⚡ Index Repository", use_container_width=True):
        if new_url.strip():
            progress_bar = st.progress(0)
            stage_el     = st.empty()

            job_id = api_ingest(new_url.strip(), new_branch.strip() or None)
            if job_id:
                while True:
                    time.sleep(1.0)
                    status = api_poll(job_id)
                    if not status:
                        st.error("Lost connection to backend during ingestion.")
                        break
                    pct = status.get("progress_pct", 0)
                    msg = status.get("message", "Working...")
                    progress_bar.progress(int(pct))
                    stage_el.markdown(f'<div class="stage-text">{msg}</div>', unsafe_allow_html=True)
                    if status.get("status") == "completed":
                        st.success("Repository indexed successfully.")
                        time.sleep(1.0)
                        st.rerun()
                        break
                    elif status.get("status") == "failed":
                        st.error(status.get("message", "Ingestion failed."))
                        break
            else:
                st.error("Failed to submit ingestion job. Is uvicorn running?")
        else:
            st.warning("Paste a GitHub URL first.")

    st.divider()

    # ── Active Workspace ─────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Active Workspace</div>', unsafe_allow_html=True)

    repos_dict = {}
    for r in api_repos():
        repos_dict[r.get("name", r.get("id", "unknown"))] = {
            **r.get("stats", {}), "url": r.get("url", ""), "id": r.get("id", "")
        }

    repo_list = list(repos_dict.keys())
    if repo_list:
        if st.session_state.selected_repo not in repo_list:
            st.session_state.selected_repo = repo_list[0]

        sel = st.selectbox(
            "Repository", repo_list,
            index=repo_list.index(st.session_state.selected_repo),
            label_visibility="collapsed"
        )
        st.session_state.selected_repo = sel
        stats = repos_dict[sel]

        st.markdown(
            f'<div style="font-size:0.68rem;color:#334155;margin:4px 0 8px;font-family:monospace">'
            f'{stats.get("url","")}</div>',
            unsafe_allow_html=True
        )
        st.markdown(f"""
        <div class="stat-grid">
          <div class="stat-card"><div class="stat-val">{stats.get("files",0)}</div><div class="stat-label">Files</div></div>
          <div class="stat-card"><div class="stat-val">{stats.get("chunks",0)}</div><div class="stat-label">Chunks</div></div>
          <div class="stat-card"><div class="stat-val">{stats.get("nodes",0)}</div><div class="stat-label">Nodes</div></div>
          <div class="stat-card"><div class="stat-val">{stats.get("edges",0)}</div><div class="stat-label">Edges</div></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🗑 Clear Databases", use_container_width=True):
            rid = stats.get("id", sel)
            if api_delete(rid):
                st.success("Databases cleared.")
                st.session_state.selected_repo = ""
                time.sleep(0.8)
                st.rerun()
            else:
                st.error("Delete failed.")
    else:
        st.info("No repositories indexed yet.")


# ── MAIN AREA ─────────────────────────────────────────────────────────────────
st.markdown('<div class="atlas-title">CodeAtlas</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="atlas-subtitle">Multi-Agent Code Intelligence  ·  Semantic Vector + Structural Graph RAG</div>',
    unsafe_allow_html=True
)

if not st.session_state.selected_repo:
    st.info("🧭 No active workspace. Please enter a GitHub URL in the sidebar to index a repository and get started.")
    st.stop()

tab_chat, tab_graph, tab_stats = st.tabs(["💬  Chat", "🕸️  Graph Explorer", "📊  Repository Stats"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:

    selected_sample = None

    st.markdown('<div style="margin-bottom:4px"></div>', unsafe_allow_html=True)

    # Chat History
    chat_box = st.container()
    with chat_box:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                if msg["role"] == "user":
                    st.markdown(msg["content"])
                else:
                    score  = msg.get("eval_score", 0.0)
                    intent = msg.get("intent", "")
                    scope  = msg.get("scope", st.session_state.selected_repo)
                    fb     = msg.get("eval_feedback", "")

                    st.markdown(
                        f'<div class="answer-card">'
                        f'<div class="badge-row">'
                        f'<span class="badge badge-intent">⬡ {intent}</span>'
                        f'{eval_badge(score)}'
                        f'<span class="badge badge-purple">⌥ {scope}</span>'
                        f'</div>'
                        f'{agent_trace_html()}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    st.markdown(msg["content"])
                    if fb:
                        st.markdown(
                            f'<div class="eval-feedback">⚖️ Evaluator: {fb}</div>',
                            unsafe_allow_html=True
                        )

                    if msg.get("citations"):
                        with st.expander(f"📎 {len(msg['citations'])} Source Reference(s)", expanded=False):
                            for cite in msg["citations"]:
                                st.markdown(
                                    f'<div class="cite-meta">📂 {cite["file"]}'
                                    f'  ·  <span style="color:#1E293B">{cite.get("type","ref")}</span></div>',
                                    unsafe_allow_html=True
                                )
                                st.markdown(
                                    f'<div class="code-file-header">{cite["file"]}</div>',
                                    unsafe_allow_html=True
                                )
                                st.code(cite["code"], language="python")

    # Input
    user_input = st.chat_input("Ask about functions, call chains, dependencies, or files...")

    active_query = user_input or selected_sample
    if active_query:
        st.session_state.chat_history.append({"role": "user", "content": active_query})

        with chat_box:
            with st.chat_message("user"):
                st.markdown(active_query)

        with st.chat_message("assistant"):
            with st.spinner("Agents working..."):

                resp = api_query(active_query, st.session_state.selected_repo)

            if not resp:
                st.error("⚠️ **Query pipeline execution failed.** The backend returned an empty response. Please ensure your database services (Qdrant, Neo4j) are online, and verify your `NVIDIA_API_KEY` and `GROQ_API_KEY` are configured in your `.env` file. Inspect your uvicorn console for traceback logs.")
                st.stop()

            score  = resp["eval_score"]
            intent = resp["intent"]
            scope  = st.session_state.selected_repo
            fb     = resp.get("eval_feedback", "")

            st.markdown(
                f'<div class="answer-card">'
                f'<div class="badge-row">'
                f'<span class="badge badge-intent">⬡ {intent}</span>'
                f'{eval_badge(score)}'
                f'<span class="badge badge-purple">⌥ {scope}</span>'
                f'</div>'
                f'{agent_trace_html()}'
                f'</div>',
                unsafe_allow_html=True
            )
            st.markdown(resp["answer"])
            if fb:
                st.markdown(
                    f'<div class="eval-feedback">⚖️ Evaluator: {fb}</div>',
                    unsafe_allow_html=True
                )

            if resp.get("citations"):
                with st.expander(f"📎 {len(resp['citations'])} Source Reference(s)", expanded=False):
                    for cite in resp["citations"]:
                        st.markdown(
                            f'<div class="cite-meta">📂 {cite["file"]}'
                            f'  ·  <span style="color:#1E293B">{cite.get("type","ref")}</span></div>',
                            unsafe_allow_html=True
                        )
                        st.markdown(
                            f'<div class="code-file-header">{cite["file"]}</div>',
                            unsafe_allow_html=True
                        )
                        st.code(cite["code"], language="python")

        st.session_state.chat_history.append({
            "role":          "assistant",
            "content":       resp["answer"],
            "intent":        resp["intent"],
            "eval_score":    resp["eval_score"],
            "eval_feedback": resp.get("eval_feedback", ""),
            "scope":         st.session_state.selected_repo,
            "citations":     resp.get("citations", []),
        })
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: GRAPH EXPLORER
# ══════════════════════════════════════════════════════════════════════════════
with tab_graph:

    st.markdown(
        '<div style="font-size:0.82rem;color:#334155;margin-bottom:14px">'
        'Force-directed dependency graph of the indexed repository. '
        'Click any node to inspect its connections. Drag to rearrange. Scroll to zoom.'
        '</div>',
        unsafe_allow_html=True
    )

    # Try live graph endpoint
    graph_data = api_graph(st.session_state.selected_repo)

    if not graph_data or not graph_data.get("nodes"):
        st.info("ℹ️ Graph data not found in Neo4j for this workspace. Try indexing or check if repository is empty.")

    graph_html = build_graph_html(graph_data["nodes"], graph_data["edges"])
    components.html(graph_html, height=600, scrolling=False)

    # Legend below graph
    leg_cols = st.columns(5)
    legend = [
        ("Function", "#3B82F6"), ("Class", "#8B5CF6"), ("File", "#10B981"),
        ("Method", "#06B6D4"), ("Module", "#F59E0B"),
    ]
    for col, (lbl, clr) in zip(leg_cols, legend):
        with col:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:6px;font-size:0.72rem;color:#475569">'
                f'<span style="width:8px;height:8px;border-radius:50%;background:{clr};flex-shrink:0"></span>{lbl}</div>',
                unsafe_allow_html=True
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: REPOSITORY STATS
# ══════════════════════════════════════════════════════════════════════════════
with tab_stats:

    repo     = st.session_state.selected_repo
    stats    = {}
    for r in api_repos():
        if r.get("name") == repo or r.get("id") == repo:
            stats = r.get("stats", {})
            break
    if not stats:
        stats = {"files": 0, "chunks": 0, "nodes": 0, "edges": 0}

    st.markdown(
        f'<div style="font-size:0.78rem;color:#334155;margin-bottom:18px">'
        f'Active workspace: <span style="color:#38BDF8;font-family:monospace">{repo}</span></div>',
        unsafe_allow_html=True
    )

    # Big Stat Cards
    s1, s2, s3, s4 = st.columns(4)
    big_stats = [
        (s1, stats.get("files",  0), "Files Parsed",   "#38BDF8"),
        (s2, stats.get("chunks", 0), "Code Chunks",    "#818CF8"),
        (s3, stats.get("nodes",  0), "Graph Nodes",    "#10B981"),
        (s4, stats.get("edges",  0), "Graph Edges",    "#F59E0B"),
    ]
    for col, val, label, clr in big_stats:
        with col:
            st.markdown(
                f'<div class="big-stat">'
                f'<div class="big-stat-val" style="color:{clr}">{val:,}</div>'
                f'<div class="big-stat-label">{label}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown('<div style="margin-top:24px"></div>', unsafe_allow_html=True)

    left, right = st.columns([1, 1])

    # Entity breakdown
    with left:
        st.markdown('<div class="section-label">Node Type Distribution</div>', unsafe_allow_html=True)
        graph_data = api_graph(repo)
        nodes_list = graph_data.get("nodes", [])
        
        type_counts = {}
        for n in nodes_list:
            t = n.get("type", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
            
        entity_types = [
            ("Function", "#3B82F6"),
            ("Class",    "#8B5CF6"),
            ("Method",   "#06B6D4"),
            ("File",     "#10B981"),
            ("Module",   "#F59E0B"),
        ]
        
        entity_breakdown = []
        for etype, color in entity_types:
            count = type_counts.get(etype, 0)
            entity_breakdown.append({"type": etype, "count": count, "color": color})
            
        total = sum(e["count"] for e in entity_breakdown)
        for entity in entity_breakdown:
            pct  = entity["count"] / total if total else 0
            bar_w = f"{pct * 100:.0f}%"
            st.markdown(
                f'<div class="entity-row">'
                f'<span class="entity-dot" style="background:{entity["color"]}"></span>'
                f'<span class="entity-name">{entity["type"]}</span>'
                f'<div class="entity-bar-wrap"><div class="entity-bar" style="width:{bar_w};background:{entity["color"]}"></div></div>'
                f'<span class="entity-count">{entity["count"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    # Chat session summary
    with right:
        st.markdown('<div class="section-label">Chat Session Summary</div>', unsafe_allow_html=True)
        ai_msgs = [m for m in st.session_state.chat_history if m["role"] == "assistant"]
        q_count = len(ai_msgs)
        avg_score = (sum(m.get("eval_score", 0) for m in ai_msgs) / q_count) if q_count else 0
        intents   = list(set(m.get("intent", "") for m in ai_msgs if m.get("intent")))

        session_stats = [
            ("Queries Run",       str(q_count),               "#38BDF8"),
            ("Avg Eval Score",    f"{avg_score:.1f}/10",       "#10B981" if avg_score >= 7 else "#F59E0B"),
            ("Unique Intents",    str(len(intents)),           "#818CF8"),
            ("Current Repo",      repo.split("/")[-1] if "/" in repo else repo, "#A78BFA"),
        ]
        for label, val, clr in session_stats:
            st.markdown(
                f'<div class="entity-row">'
                f'<span class="entity-name">{label}</span>'
                f'<span class="entity-count" style="color:{clr};font-weight:600">{val}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

        if intents:
            st.markdown('<div class="section-label" style="margin-top:14px">Intents Seen</div>', unsafe_allow_html=True)
            for intent in intents[:6]:
                st.markdown(
                    f'<span class="badge badge-intent" style="margin:3px 3px 0 0">{intent}</span>',
                    unsafe_allow_html=True
                )