"""SEI Platform - Software Engineering Intelligence (light, earthy edition).

Layout: a plain masthead with text navigation, a one-line repository summary,
then one view at a time. The Assistant view is a transcript with a margin of
notes beside it. No sidebar.
"""

import html
import json
import time

import requests
import streamlit as st
import streamlit.components.v1 as components

API_BASE = "http://127.0.0.1:8000/api"
APP_NAME = "SEI Platform"

VIEWS = ["Assistant", "Graph", "Insights", "Repositories"]

AGENT_STEPS = [
    ("Planner", "works out what is really being asked."),
    ("Retriever", "pulls the most relevant code chunks."),
    ("Graph", "follows calls, imports and inheritance."),
    ("Answer", "writes a reply from that evidence."),
    ("Evaluator", "scores the reply and notes any gaps."),
]

NODE_COLORS = {
    "Function": "#3F5E3A",
    "Class": "#C28A2C",
    "File": "#9A5B3A",
    "Method": "#86A265",
    "Module": "#7A6F52",
}
EDGE_COLORS = {
    "CALLS": "#3F5E3A",
    "IMPORTS": "#C28A2C",
    "INHERITS": "#9A5B3A",
    "DEFINED_IN": "#B9AF93",
    "HAS_METHOD": "#86A265",
}

SUGGESTIONS = [
    "Where does the application start?",
    "How does the main workflow run?",
    "Which functions depend on the core class?",
    "How do the main modules relate to each other?",
]

MAX_GRAPH_NODES = 800

st.set_page_config(
    page_title=f"{APP_NAME} | Software Engineering Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def safe(value):
    return html.escape(str(value if value is not None else ""))


def md(markup):
    """st.markdown for HTML. Strips indentation and blank lines so Markdown
    can never mistake the markup for a code block."""
    flat = " ".join(line.strip() for line in markup.strip().splitlines() if line.strip())
    st.markdown(flat, unsafe_allow_html=True)


# ---------------------------------------------------------
# Look: beige paper, forest green ink, ochre rules. Flat, square, no icons.
# ---------------------------------------------------------

md("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,500;0,6..72,600;0,6..72,700;1,6..72,400&family=Public+Sans:wght@400;500;600&display=swap');
:root {
    --paper: #F3EDE0;
    --sheet: #FAF6EC;
    --sand: #E9E0CB;
    --ink: #26301F;
    --muted: #6B705C;
    --rule: #CFC6AE;
    --green: #3F5E3A;
    --moss: #86A265;
    --ochre: #B7791F;
    --clay: #9A5B3A;
}
html, body, .stApp { color-scheme: light; font-family: 'Public Sans', sans-serif; color: var(--ink); }
.stApp { background: var(--paper); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], #MainMenu, footer { display: none !important; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.block-container { max-width: 1240px; padding-top: 1.4rem; padding-bottom: 4rem; }

/* ---------- text ---------- */
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] strong, [data-testid="stMarkdownContainer"] em,
[data-testid="stWidgetLabel"] p, [data-testid="stCheckbox"] label p, label { color: var(--ink) !important; }
h1, h2, h3, h4, [data-testid="stHeading"] *, [data-testid="stMarkdownContainer"] h1, [data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3, [data-testid="stMarkdownContainer"] h4 {
    font-family: 'Newsreader', Georgia, serif !important; font-weight: 600 !important; color: var(--ink) !important; letter-spacing: -0.01em;
}
[data-testid="stHeading"] h3 { font-size: 27px; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }
a { color: var(--green) !important; }
[data-testid="stMarkdownContainer"] code, pre, pre code { background: var(--sand) !important; color: var(--ink) !important; border-radius: 2px; }
pre { border: 1px solid var(--rule); }

/* ---------- buttons ---------- */
.stButton > button {
    background: var(--sheet) !important; border: 1px solid var(--rule) !important; border-radius: 2px !important;
    color: var(--ink) !important; font-weight: 500 !important; text-align: left; box-shadow: none !important;
}
.stButton > button p { color: var(--ink) !important; }
.stButton > button:hover { border-color: var(--green) !important; background: var(--sand) !important; }
.stButton > button:disabled { opacity: .5; }
.stButton > button[kind="primary"], .stButton > button[data-testid="stBaseButton-primary"] {
    background: var(--green) !important; border-color: var(--green) !important; text-align: center;
}
.stButton > button[kind="primary"] p, .stButton > button[data-testid="stBaseButton-primary"] p { color: #F6F1E3 !important; }

/* ---------- inputs ---------- */
.stTextInput input, .stTextArea textarea {
    background: var(--sheet) !important; border: 1px solid var(--rule) !important; border-radius: 2px !important;
    color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important; box-shadow: none !important;
}
.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--green) !important; }
.stTextInput input::placeholder { color: #9A957F !important; -webkit-text-fill-color: #9A957F !important; }
[data-baseweb="select"] > div { background: var(--sheet) !important; border: 1px solid var(--rule) !important; border-radius: 2px !important; }
[data-baseweb="select"] *, [data-baseweb="select"] input { color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important; }
[data-baseweb="select"] svg { fill: var(--muted) !important; }
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="menu"], [data-baseweb="popover"] ul { background: var(--sheet) !important; border-radius: 2px; }
[data-baseweb="popover"] li, [data-baseweb="popover"] li * { color: var(--ink) !important; background: transparent !important; }
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] { background: var(--sand) !important; }

/* ---------- navigation: plain text links with an ochre underline ---------- */
[data-testid="stRadio"] { margin-top: 18px; }
[data-testid="stRadio"] [role="radiogroup"] { display: flex; flex-wrap: wrap; gap: 26px; background: none; border: none; padding: 0; }
[data-testid="stRadio"] label { padding: 4px 0 5px; margin: 0 !important; cursor: pointer; border-bottom: 3px solid transparent; }
[data-testid="stRadio"] label > div:first-child { display: none; }
[data-testid="stRadio"] label p { color: var(--muted) !important; font-weight: 500; font-size: 16px; }
[data-testid="stRadio"] label:hover p { color: var(--ink) !important; }
[data-testid="stRadio"] label:has(input:checked) { border-bottom-color: var(--ochre); }
[data-testid="stRadio"] label:has(input:checked) p { color: var(--ink) !important; font-weight: 600; }

/* ---------- other native widgets ---------- */
[data-testid="stChatInput"] { background: var(--sheet) !important; border: 1px solid var(--rule) !important; border-radius: 2px !important; }
[data-testid="stChatInput"] textarea { background: transparent !important; color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important; }
[data-testid="stChatInput"] textarea::placeholder { color: #9A957F !important; -webkit-text-fill-color: #9A957F !important; }
[data-testid="stBottom"] > div { background: transparent !important; }
[data-testid="stExpander"] { background: var(--sheet); border: 1px solid var(--rule) !important; border-radius: 2px; }
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { color: var(--ink) !important; }
[data-testid="stSpinner"] *, [data-testid="stSpinner"] p { color: var(--muted) !important; }
[data-testid="stAlert"] { background: var(--sand) !important; border: 1px solid var(--rule); border-radius: 2px; }
[data-testid="stAlert"] * { color: var(--ink) !important; }
[data-testid="stProgress"] > div > div { background: var(--sand) !important; }
[data-testid="stProgress"] > div > div > div > div { background: var(--green) !important; }

/* ---------- masthead ---------- */
.mast-name { font: 700 30px 'Newsreader', Georgia, serif; color: var(--ink); line-height: 1.05; letter-spacing: -0.02em; }
.mast-sub { font-size: 13px; color: var(--muted); margin-top: 3px; }
.svc-row { display: flex; gap: 16px; justify-content: flex-end; flex-wrap: wrap; padding-top: 22px; font-size: 13px; color: var(--ink); }
.svc { display: inline-flex; align-items: center; gap: 6px; }
.sq { display: inline-block; width: 8px; height: 8px; background: var(--green); }
.sq.off, .sq.bad { background: var(--clay); }
.sq.ok { background: var(--ochre); }
.svc.off { color: var(--clay); }
.double-rule { border-top: 1px solid var(--ink); border-bottom: 1px solid var(--ink); height: 4px; margin: 10px 0 18px; }
.summary { font: 400 17px 'Newsreader', Georgia, serif; color: var(--ink); margin: 0; padding-top: 4px; line-height: 1.5; }
.summary b { font-weight: 700; }

/* ---------- transcript ---------- */
.lede { font: italic 400 18px 'Newsreader', Georgia, serif; color: var(--muted); margin: 6px 0 10px; }
.turn { border-top: 1px solid var(--rule); margin-top: 22px; padding-top: 7px; }
.who { font: 600 12.5px 'Public Sans', sans-serif; letter-spacing: 0.04em; text-transform: uppercase; }
.turn.you .who { color: var(--ochre); }
.turn.sei .who { color: var(--green); }
.turn-meta { font-size: 13px; color: var(--muted); margin: 4px 0 6px; display: flex; align-items: center; gap: 7px; }

/* ---------- margin notes ---------- */
.notes-title { font: 600 18px 'Newsreader', Georgia, serif; color: var(--ink); border-top: 2px solid var(--ink); padding-top: 8px; margin-bottom: 6px; }
.dl-row { display: flex; justify-content: space-between; gap: 14px; padding: 8px 0; border-bottom: 1px solid var(--rule); font-size: 14px; color: var(--ink); }
.dl-row span:first-child { color: var(--muted); }
.dl-row b { font-weight: 600; text-align: right; }
.score-line { height: 4px; background: var(--sand); margin: 10px 0 4px; }
.score-line div { height: 4px; }
.note-text { font-size: 14px; line-height: 1.55; color: var(--ink); margin: 10px 0 0; }
.srcs { margin: 6px 0 0; padding-left: 20px; font-size: 13px; color: var(--ink); }
.srcs li { padding: 3px 0; overflow-wrap: anywhere; color: var(--green) !important; }
.sub-title { font: 600 14px 'Public Sans', sans-serif; color: var(--ink); margin: 18px 0 2px; }
.steps { margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.6; }
.steps li { color: var(--ink) !important; }
.empty-note { font-size: 14px; color: var(--muted); line-height: 1.55; margin: 10px 0 0; }

/* ---------- sections, tables, bars ---------- */
.sect { border-top: 2px solid var(--ink); padding-top: 8px; margin-bottom: 18px; }
.sect h4 { margin: 0 0 6px; font-size: 19px; }
.sect .sub { font-size: 14px; color: var(--muted); margin: 0; }
.kv { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px solid var(--rule); font-size: 14.5px; color: var(--ink); }
.kv span:first-child { color: var(--muted); }
.kv b { font: 700 16px 'Newsreader', Georgia, serif; }
.bar-row { display: flex; align-items: center; gap: 12px; margin: 10px 0; }
.bar-label { width: 96px; font-size: 14px; color: var(--ink); overflow: hidden; text-overflow: ellipsis; }
.bar-track { flex: 1; height: 6px; background: var(--sand); }
.bar-fill { height: 6px; }
.bar-count { min-width: 50px; text-align: right; font: 600 15px 'Newsreader', Georgia, serif; color: var(--ink); }
.tbl-head { font-size: 13px; color: var(--muted); border-bottom: 2px solid var(--ink); padding-bottom: 6px; }
.cell { font-size: 14.5px; color: var(--ink); padding-top: 8px; overflow-wrap: anywhere; }
.cell.num { font-family: 'Newsreader', Georgia, serif; font-weight: 600; font-size: 16px; }
.cell.url { color: var(--muted); font-size: 13px; }
.cell b { font-weight: 700; }
.row-rule { border-top: 1px solid var(--rule); margin: 6px 0 0; }

/* ---------- first run ---------- */
.intro { max-width: 680px; margin: 1.8rem 0 1.4rem; }
.intro h1 { font: 700 40px 'Newsreader', Georgia, serif; line-height: 1.12; margin: 0 0 12px; color: var(--ink) !important; letter-spacing: -0.02em; }
.intro p { font-size: 17px; line-height: 1.6; color: var(--ink) !important; }

@media (max-width: 850px) {
    .svc-row { justify-content: flex-start; padding-top: 4px; }
    .intro h1 { font-size: 30px; }
}
</style>
""")


# ---------------------------------------------------------
# API layer
# ---------------------------------------------------------

def api_get(path, timeout=8):
    try:
        response = requests.get(f"{API_BASE}{path}", timeout=timeout)
        if response.ok:
            return response.json()
    except (requests.RequestException, ValueError):
        pass
    return {}


@st.cache_data(ttl=15, show_spinner=False)
def cached_health():
    return api_get("/health", timeout=4)


@st.cache_data(ttl=30, show_spinner=False)
def cached_graph(repo_id):
    return api_get(f"/graph/{repo_id}", timeout=15)


def api_repos():
    data = api_get("/repos", timeout=5)
    return data.get("repos", []) if isinstance(data, dict) else []


def api_ingest(url, branch):
    try:
        response = requests.post(
            f"{API_BASE}/ingest",
            json={"github_url": url, "branch": branch or None},
            timeout=15,
        )
        if response.ok:
            return response.json().get("job_id")
    except (requests.RequestException, ValueError):
        pass
    return None


def api_delete(repo_id):
    try:
        return requests.delete(f"{API_BASE}/repo/{repo_id}", timeout=10).ok
    except requests.RequestException:
        return False


def _failed(intent, answer, feedback=""):
    return {"intent": intent, "eval_score": 0.0, "eval_feedback": feedback, "answer": answer, "sources": []}


def api_query(question, repo_id):
    """Always returns a dict, even on failure."""
    try:
        response = requests.post(
            f"{API_BASE}/query",
            json={"question": question, "repo_id": repo_id},
            timeout=120,
        )
    except requests.Timeout:
        return _failed(
            "Timeout",
            "**The query timed out.** The agent pipeline took longer than 120 seconds. "
            "Try again, or check the uvicorn logs.",
            "Request exceeded 120 seconds.",
        )
    except requests.RequestException:
        return _failed(
            "Connection error",
            f"**Backend unreachable.** Make sure the API server is running at {API_BASE}.",
            "Backend unreachable.",
        )

    if not response.ok:
        return _failed(
            "Error",
            f"**API error {response.status_code}.** {response.text[:600]}",
            "The backend returned an error. Check Qdrant, Neo4j and your API keys.",
        )

    try:
        data = response.json()
    except ValueError:
        return _failed("Error", "The backend returned a response that was not valid JSON.")

    sources = []
    for source in data.get("sources", []) or []:
        sources.append(source.get("file", str(source)) if isinstance(source, dict) else str(source))

    try:
        score = float(data.get("eval_score") or 0)
    except (TypeError, ValueError):
        score = 0.0

    return {
        "intent": data.get("intent", "Unknown"),
        "eval_score": score,
        "eval_feedback": data.get("eval_feedback", ""),
        "answer": data.get("answer", "No answer returned."),
        "sources": sources,
    }


# ---------------------------------------------------------
# Graph (D3), light and printed-map in feel
# ---------------------------------------------------------

def normalize_graph(nodes, edges):
    """Unique string ids, a type on every node and edge, no dangling edges."""
    clean_nodes, ids = [], set()
    for index, node in enumerate(nodes or []):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or node.get("name") or node.get("label") or index)
        if node_id in ids:
            continue
        ids.add(node_id)
        clean_nodes.append({
            "id": node_id,
            "label": str(node.get("label") or node.get("name") or node_id),
            "type": str(node.get("type") or "Other"),
            "file": str(node.get("file") or ""),
            "lines": str(node.get("lines") or ""),
        })

    clean_edges = []
    for edge in edges or []:
        if not isinstance(edge, dict):
            continue
        source = edge.get("source", edge.get("from"))
        target = edge.get("target", edge.get("to"))
        if source is None or target is None:
            continue
        source, target = str(source), str(target)
        if source in ids and target in ids:
            clean_edges.append({
                "source": source,
                "target": target,
                "type": str(edge.get("type") or edge.get("label") or edge.get("relationship") or "RELATED"),
            })
    return clean_nodes, clean_edges


GRAPH_TEMPLATE = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
:root { --paper:#F3EDE0; --sheet:#FAF6EC; --sand:#E9E0CB; --ink:#26301F; --muted:#6B705C; --rule:#CFC6AE; --green:#3F5E3A; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; background: var(--sheet); color: var(--ink); font-family: 'Public Sans', Arial, sans-serif; overflow: hidden; }
#container { display: flex; flex-direction: column; height: 100%; border: 1px solid var(--rule); background: var(--sheet); }
#toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 9px 12px; background: var(--paper); border-bottom: 1px solid var(--rule); }
.group { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; }
.t-label { font-size: 12px; color: var(--muted); }
.sep { width: 1px; height: 18px; background: var(--rule); }
.chip { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; cursor: pointer; user-select: none; color: var(--ink); }
.chip i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: var(--c); }
.chip i.ln { width: 14px; height: 3px; border-radius: 0; }
.chip.off { opacity: 0.35; text-decoration: line-through; }
input, button { background: var(--sheet); color: var(--ink); border: 1px solid var(--rule); border-radius: 2px; padding: 5px 10px; font-size: 12.5px; font-family: inherit; }
input::placeholder { color: #9A957F; }
button { cursor: pointer; }
button:hover, input:focus { border-color: var(--green); outline: none; }
#count { margin-left: auto; font-size: 12px; color: var(--muted); }
#area { display: flex; flex: 1; min-height: 0; }
#wrap { flex: 1; min-width: 0; position: relative; }
svg { width: 100%; height: 100%; display: block; cursor: grab; }
svg:active { cursor: grabbing; }
#panel { width: 0; overflow: hidden; background: var(--paper); border-left: 1px solid var(--rule); transition: width 0.2s; }
#panel.open { width: 270px; overflow-y: auto; }
#pbody { padding: 14px; width: 270px; }
#pclose { float: right; width: 22px; height: 22px; padding: 0; line-height: 18px; text-align: center; }
.badge { display: inline-block; font-size: 12px; font-weight: 600; margin-bottom: 6px; }
.pname { font: 600 17px Georgia, serif; margin-bottom: 8px; word-break: break-all; line-height: 1.3; }
.pkey { font-size: 12px; color: var(--muted); margin: 12px 0 3px; }
.pval { font-size: 12.5px; color: var(--ink); font-family: monospace; word-break: break-all; }
.conn { font-size: 12.5px; padding: 6px 0; border-bottom: 1px solid var(--rule); cursor: pointer; display: flex; gap: 8px; align-items: baseline; }
.conn:hover span:last-child { text-decoration: underline; }
.ce { font-size: 11px; color: var(--muted); flex-shrink: 0; }
#tip { position: fixed; display: none; pointer-events: none; z-index: 99; max-width: 230px; background: var(--sheet); border: 1px solid var(--ink); padding: 6px 9px; font-size: 12px; line-height: 1.5; }
#hint { position: absolute; left: 12px; bottom: 8px; font-size: 11.5px; color: var(--muted); pointer-events: none; }
</style>
</head>
<body>
<div id="container">
  <div id="toolbar">
    <div class="group"><span class="t-label">Nodes</span><span id="ntypes" class="group"></span></div>
    <div class="sep"></div>
    <div class="group"><span class="t-label">Edges</span><span id="etypes" class="group"></span></div>
    <div class="sep"></div>
    <input id="search" type="text" placeholder="Find a symbol">
    <button id="reset">Reset view</button>
    <button id="fullscreen">Fullscreen</button>
    <span id="count"></span>
  </div>
  <div id="area">
    <div id="wrap"><svg id="svg"></svg><div id="hint">Click a node to see what it touches. Click empty space to clear.</div></div>
    <div id="panel"><div id="pbody"></div></div>
  </div>
</div>
<div id="tip"></div>
<script>
const RAW_NODES = __NODES__;
const RAW_EDGES = __EDGES__;
const NODE_COLOR = __NODE_COLORS__;
const EDGE_COLOR = __EDGE_COLORS__;
const NODE_R = { Function: 8, Class: 11, File: 12, Method: 6, Module: 9 };
const FALLBACK = "#8C8566";
const nColor = t => NODE_COLOR[t] || FALLBACK;
const eColor = t => EDGE_COLOR[t] || "#B9AF93";
const nR = t => NODE_R[t] || 8;
const eid = x => (typeof x === "object" ? x.id : x);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const byId = new Map(RAW_NODES.map(n => [n.id, n]));

const NTYPES = [...new Set(RAW_NODES.map(n => n.type))].sort();
const ETYPES = [...new Set(RAW_EDGES.map(e => e.type))].sort();
const activeN = new Set(NTYPES);
const activeE = new Set(ETYPES);
let sim = null, linkSel = null, nodeSel = null, labelSel = null;
let curNodes = [], curEdges = [], selectedId = null;

const svg = d3.select("#svg");
const wrap = document.getElementById("wrap");
const root = svg.append("g");
const zoom = d3.zoom().scaleExtent([0.1, 5]).on("zoom", e => {
  root.attr("transform", e.transform);
  if (labelSel) labelSel.attr("display", (curNodes.length <= 150 || e.transform.k > 1.6) ? null : "none");
});
svg.call(zoom);

const defs = svg.append("defs");
const eIdx = {};
ETYPES.forEach((t, i) => {
  eIdx[t] = i;
  defs.append("marker").attr("id", "arr" + i).attr("viewBox", "0 -4 10 8").attr("refX", 19).attr("refY", 0)
    .attr("markerWidth", 5).attr("markerHeight", 5).attr("orient", "auto")
    .append("path").attr("d", "M0,-4L10,0L0,4").attr("fill", eColor(t));
});

function makeChips(boxId, types, set, colorFn, shape) {
  const box = document.getElementById(boxId);
  types.forEach(t => {
    const c = document.createElement("span");
    c.className = "chip";
    c.style.setProperty("--c", colorFn(t));
    c.innerHTML = '<i class="' + shape + '"></i>' + esc(t);
    c.onclick = () => {
      if (set.has(t)) { if (set.size > 1) { set.delete(t); c.classList.add("off"); } }
      else { set.add(t); c.classList.remove("off"); }
      rebuild();
    };
    box.appendChild(c);
  });
}
makeChips("ntypes", NTYPES, activeN, nColor, "dot");
makeChips("etypes", ETYPES, activeE, eColor, "ln");

function neighbours(id) {
  const s = new Set([id]);
  curEdges.forEach(e => {
    const a = eid(e.source), b = eid(e.target);
    if (a === id) s.add(b);
    if (b === id) s.add(a);
  });
  return s;
}

function paint() {
  if (!nodeSel) return;
  const q = document.getElementById("search").value.toLowerCase().trim();
  const nb = selectedId ? neighbours(selectedId) : null;
  const on = d => (!q || d.label.toLowerCase().includes(q)) && (!nb || nb.has(d.id));
  nodeSel.attr("fill-opacity", d => on(d) ? 1 : 0.14).attr("stroke-opacity", d => on(d) ? 1 : 0.2);
  labelSel.attr("opacity", d => on(d) ? 1 : 0.12);
  linkSel.attr("stroke-opacity", e => {
    if (selectedId) return (eid(e.source) === selectedId || eid(e.target) === selectedId) ? 0.95 : 0.08;
    return q ? 0.1 : 0.6;
  });
}

function closePanel() {
  document.getElementById("panel").classList.remove("open");
  selectedId = null;
  paint();
}

function showPanel(d) {
  const conns = [];
  curEdges.forEach(e => {
    const a = eid(e.source), b = eid(e.target);
    if (a === d.id) conns.push({ id: b, type: e.type, dir: "to" });
    else if (b === d.id) conns.push({ id: a, type: e.type, dir: "from" });
  });
  const col = nColor(d.type);
  const rows = conns.slice(0, 15).map(c => {
    const n = byId.get(c.id);
    if (!n) return "";
    return '<div class="conn" data-id="' + esc(c.id) + '"><span class="ce">' + c.dir + " " + esc(c.type) +
      '</span><span style="color:' + nColor(n.type) + '">' + esc(n.label) + "</span></div>";
  }).join("");
  document.getElementById("pbody").innerHTML =
    '<button id="pclose">x</button>' +
    '<span class="badge" style="color:' + col + '">' + esc(d.type) + "</span>" +
    '<div class="pname">' + esc(d.label) + "</div>" +
    (d.file ? '<div class="pkey">File</div><div class="pval">' + esc(d.file) + "</div>" : "") +
    (d.lines ? '<div class="pkey">Lines</div><div class="pval">' + esc(d.lines) + "</div>" : "") +
    '<div class="pkey">Connections (' + conns.length + ")</div>" + rows +
    (conns.length > 15 ? '<div class="pkey">and ' + (conns.length - 15) + " more</div>" : "");
  document.getElementById("pclose").onclick = closePanel;
  document.getElementById("panel").classList.add("open");
}

function selectNode(d) {
  selectedId = d.id;
  paint();
  showPanel(d);
}

document.getElementById("pbody").addEventListener("click", ev => {
  const item = ev.target.closest(".conn");
  if (!item) return;
  const n = curNodes.find(x => x.id === item.dataset.id);
  if (!n) return;
  selectNode(n);
  const w = wrap.clientWidth, h = wrap.clientHeight;
  svg.transition().duration(450).call(zoom.transform, d3.zoomIdentity.translate(w / 2 - n.x * 1.5, h / 2 - n.y * 1.5).scale(1.5));
});

function rebuild() {
  root.selectAll("*").remove();
  if (sim) sim.stop();
  const ids = new Set(RAW_NODES.filter(n => activeN.has(n.type)).map(n => n.id));
  const nodes = RAW_NODES.filter(n => ids.has(n.id)).map(n => ({ ...n }));
  const edges = RAW_EDGES.filter(e => activeE.has(e.type) && ids.has(e.source) && ids.has(e.target)).map(e => ({ ...e }));
  curNodes = nodes; curEdges = edges;
  if (selectedId && !ids.has(selectedId)) closePanel();
  document.getElementById("count").textContent = nodes.length + " nodes, " + edges.length + " edges";

  sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(edges).id(d => d.id).distance(105).strength(0.55))
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(wrap.clientWidth / 2, wrap.clientHeight / 2))
    .force("collide", d3.forceCollide().radius(d => nR(d.type) + 16));

  linkSel = root.append("g").selectAll("line").data(edges).join("line")
    .attr("stroke", d => eColor(d.type)).attr("stroke-width", 1.2).attr("stroke-opacity", 0.6)
    .attr("marker-end", d => "url(#arr" + eIdx[d.type] + ")");

  nodeSel = root.append("g").selectAll("circle").data(nodes).join("circle")
    .attr("r", d => nR(d.type)).attr("fill", d => nColor(d.type))
    .attr("stroke", "#FAF6EC").attr("stroke-width", 1.5).style("cursor", "pointer")
    .call(d3.drag()
      .on("start", (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on("end", (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }))
    .on("mouseover", (e, d) => {
      const tip = document.getElementById("tip");
      tip.innerHTML = "<b>" + esc(d.label) + '</b><br><span style="color:#6B705C">' + esc(d.type) + "</span>" +
        (d.file ? "<br>" + esc(d.file) : "") + (d.lines ? "<br>lines " + esc(d.lines) : "");
      tip.style.display = "block";
    })
    .on("mousemove", e => { const t = document.getElementById("tip"); t.style.left = (e.clientX + 14) + "px"; t.style.top = (e.clientY - 8) + "px"; })
    .on("mouseout", () => { document.getElementById("tip").style.display = "none"; })
    .on("click", (e, d) => { e.stopPropagation(); selectNode(d); });

  labelSel = root.append("g").selectAll("text").data(nodes).join("text")
    .text(d => d.label.length > 18 ? d.label.slice(0, 15) + "..." : d.label)
    .attr("font-size", 9.5).attr("fill", "#3A4232").attr("text-anchor", "middle")
    .attr("dy", d => nR(d.type) + 12).style("pointer-events", "none");
  if (nodes.length > 150) labelSel.attr("display", "none");

  sim.on("tick", () => {
    linkSel.attr("x1", d => d.source.x).attr("y1", d => d.source.y).attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    nodeSel.attr("cx", d => d.x).attr("cy", d => d.y);
    labelSel.attr("x", d => d.x).attr("y", d => d.y);
  });
  paint();
}

svg.on("click", () => { if (selectedId) closePanel(); });
document.getElementById("search").addEventListener("input", paint);
document.getElementById("reset").addEventListener("click", () => {
  document.getElementById("search").value = "";
  closePanel();
  svg.transition().duration(350).call(zoom.transform, d3.zoomIdentity);
});

const fsBtn = document.getElementById("fullscreen");
fsBtn.addEventListener("click", () => {
  const box = document.getElementById("container");
  try {
    if (!document.fullscreenElement) box.requestFullscreen(); else document.exitFullscreen();
  } catch (err) { console.error(err); }
});
document.addEventListener("fullscreenchange", () => { fsBtn.textContent = document.fullscreenElement ? "Exit fullscreen" : "Fullscreen"; });

rebuild();
</script>
</body>
</html>
"""


def render_graph(nodes, edges, height=640):
    # "<\/" stops a stray "</script>" inside a label from closing the script tag.
    page = (
        GRAPH_TEMPLATE
        .replace("__NODES__", json.dumps(nodes).replace("</", "<\\/"))
        .replace("__EDGES__", json.dumps(edges).replace("</", "<\\/"))
        .replace("__NODE_COLORS__", json.dumps(NODE_COLORS))
        .replace("__EDGE_COLORS__", json.dumps(EDGE_COLORS))
    )
    components.html(page, height=height, scrolling=False)


# ---------------------------------------------------------
# Building blocks
# ---------------------------------------------------------

def score_level(score):
    if score >= 8:
        return "good"
    if score >= 5:
        return "ok"
    return "bad"


SCORE_COLOR = {"good": "#3F5E3A", "ok": "#B7791F", "bad": "#9A5B3A"}


def render_ingest_form(prefix):
    col_url, col_branch = st.columns([3, 1])
    github_url = col_url.text_input("GitHub URL", key=f"{prefix}_url", placeholder="https://github.com/owner/repo")
    branch = col_branch.text_input("Branch (optional)", key=f"{prefix}_branch", placeholder="main")

    if not st.button("Index repository", type="primary", key=f"{prefix}_go"):
        return
    if not github_url.strip():
        st.warning("Enter a GitHub URL first.")
        return

    job_id = api_ingest(github_url.strip(), branch.strip())
    if not job_id:
        st.error("Could not start indexing. Is the API server running?")
        return

    progress = st.progress(0, text="Preparing repository...")
    message = st.empty()
    for _ in range(600):
        time.sleep(1)
        status = api_get(f"/ingest/{job_id}", timeout=5)
        if not status:
            message.error("Lost connection to the backend while indexing.")
            return
        pct = max(0, min(100, int(status.get("progress_pct", 0) or 0)))
        progress.progress(pct, text=f"Indexing: {pct}%")
        message.caption(status.get("message", "Working..."))

        if status.get("status") == "completed":
            st.success("Repository indexed. Loading your workspace...")
            cached_health.clear()
            cached_graph.clear()
            time.sleep(0.6)
            st.rerun()
        if status.get("status") == "failed":
            st.error(status.get("message", "Indexing failed."))
            return
    message.warning("Indexing is taking longer than expected. Check the API server logs.")


def render_turn(msg):
    if msg["role"] == "user":
        md('<div class="turn you"><span class="who">You</span></div>')
        st.markdown(msg["content"])
        return

    score = msg.get("eval_score", 0.0)
    md('<div class="turn sei"><span class="who">SEI</span></div>')
    st.markdown(msg["content"])
    md(
        f'<div class="turn-meta"><span class="sq {score_level(score)}"></span>'
        f'{safe(msg.get("intent", "Unknown"))}. Scored {score:.1f} out of 10.</div>'
    )


def render_notes(last):
    if not last:
        md(
            '<div class="notes-title">Notes on the latest answer</div>'
            '<p class="empty-note">Once you ask something, the intent, the evaluator\'s score and '
            "comments, and the files the answer drew on are listed here.</p>"
        )
        return

    score = last.get("eval_score", 0.0)
    color = SCORE_COLOR[score_level(score)]
    parts = [
        '<div class="notes-title">Notes on the latest answer</div>',
        f'<div class="dl-row"><span>Intent</span><b>{safe(last.get("intent", "Unknown"))}</b></div>',
        f'<div class="dl-row"><span>Quality</span><b>{score:.1f} out of 10</b></div>',
        f'<div class="score-line"><div style="width:{min(score, 10) * 10:.0f}%;background:{color}"></div></div>',
    ]
    if last.get("eval_feedback"):
        parts.append(f'<p class="note-text">{safe(last["eval_feedback"])}</p>')
    sources = last.get("sources", [])
    if sources:
        items = "".join(f"<li>{safe(s)}</li>" for s in sources)
        parts.append(f'<div class="sub-title">Files used ({len(sources)})</div><ol class="srcs">{items}</ol>')
    md("".join(parts))


def render_bars(counts, palette, fallback="#8C8566"):
    total = sum(counts.values())
    out = ""
    for label, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        color = palette.get(label, fallback)
        out += (
            f'<div class="bar-row"><div class="bar-label">{safe(label)}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{100 * count / total:.1f}%;background:{color}"></div></div>'
            f'<div class="bar-count">{count:,}</div></div>'
        )
    return out


def kv_rows(rows):
    return "".join(f'<div class="kv"><span>{safe(a)}</span><b>{safe(b)}</b></div>' for a, b in rows)


# ---------------------------------------------------------
# State and data
# ---------------------------------------------------------

if "chats" not in st.session_state:
    st.session_state.chats = {}  # one conversation per repository

repo_map = {}
for repo in api_repos():
    name = repo.get("name") or repo.get("id") or "Unknown repository"
    repo_map[name] = {**(repo.get("stats") or {}), "id": repo.get("id", ""), "url": repo.get("url", "")}
repo_names = list(repo_map.keys())


def open_repo(name):
    st.session_state.active_repo = name


# ---------------------------------------------------------
# Masthead
# ---------------------------------------------------------

mast_left, mast_nav, mast_status = st.columns([1.5, 2.4, 1.7], gap="medium")

with mast_left:
    md(f"""
    <div class="mast-name">{APP_NAME}</div>
    <div class="mast-sub">Software engineering intelligence</div>
    """)

with mast_nav:
    st.radio("View", VIEWS, key="view", horizontal=True, label_visibility="collapsed")

with mast_status:
    health = cached_health()
    if health:
        items = ""
        for label, key in [("Qdrant", "qdrant"), ("Neo4j", "neo4j"), ("Groq", "groq")]:
            ok = health.get(key) == "ok"
            items += (
                f'<span class="svc {"" if ok else "off"}"><span class="sq {"" if ok else "off"}"></span>'
                f'{label}{"" if ok else " offline"}</span>'
            )
        md(f'<div class="svc-row">{items}</div>')
    else:
        md(
            '<div class="svc-row"><span class="svc off"><span class="sq off"></span>'
            "The API is not responding. Start the backend.</span></div>"
        )

md('<div class="double-rule"></div>')


# ---------------------------------------------------------
# First run
# ---------------------------------------------------------

if not repo_names:
    md(f"""
    <div class="intro">
      <h1>Index a repository to begin.</h1>
      <p>Paste the address of a public GitHub repository. {APP_NAME} reads the code, maps how its parts
      depend on each other, and then answers your questions using what it found.</p>
    </div>
    """)
    render_ingest_form("first")
    st.stop()


# ---------------------------------------------------------
# Repository line
# ---------------------------------------------------------

if st.session_state.get("active_repo") not in repo_names:
    st.session_state.active_repo = repo_names[0]

line_select, line_summary = st.columns([1.2, 3], gap="medium")
with line_select:
    st.selectbox("Repository", repo_names, key="active_repo", label_visibility="collapsed")

active_repo = st.session_state.active_repo
record = repo_map[active_repo]
# NOTE: the repository *name* is what the backend has been receiving for
# /query and /graph. If your API expects the id, use record["id"] here.
repo_key = active_repo
chat = st.session_state.chats.setdefault(active_repo, [])


def n_of(key):
    return int(record.get(key, 0) or 0)


with line_summary:
    md(
        f'<p class="summary"><b>{n_of("files"):,}</b> files were split into <b>{n_of("chunks"):,}</b> '
        f'chunks. The graph holds <b>{n_of("nodes"):,}</b> nodes and <b>{n_of("edges"):,}</b> relationships.</p>'
    )

st.write("")
view = st.session_state.view


# ---------------------------------------------------------
# Assistant: transcript on the left, notes in the margin
# ---------------------------------------------------------

if view == "Assistant":
    chat_col, notes_col = st.columns([2.1, 1], gap="large")

    with chat_col:
        st.subheader("Ask about the code")
        st.caption("Every answer is scored out of ten by an evaluator, and the files it drew on are listed beside it.")

        clicked = None
        if not chat:
            md('<p class="lede">Nothing has been asked yet. A few places to start:</p>')
            for i, suggestion in enumerate(SUGGESTIONS):
                if st.button(suggestion, key=f"sug_{i}", use_container_width=True):
                    clicked = suggestion

        for msg in chat:
            render_turn(msg)

        question = st.chat_input("Type a question about this repository") or clicked
        if question:
            chat.append({"role": "user", "content": question})
            with st.spinner("Working through the five agents..."):
                result = api_query(question, repo_key)
            chat.append({"role": "assistant", "content": result["answer"], **{
                k: result[k] for k in ("intent", "eval_score", "eval_feedback", "sources")
            }})
            st.rerun()

    with notes_col:
        render_notes(next((m for m in reversed(chat) if m["role"] == "assistant"), None))
        with st.expander("How an answer is made"):
            steps = "".join(f"<li><b>{name}</b> {desc}</li>" for name, desc in AGENT_STEPS)
            md(f'<ol class="steps">{steps}</ol>')
        if st.button("Clear this conversation", use_container_width=True, disabled=not chat):
            st.session_state.chats[active_repo] = []
            st.rerun()


# ---------------------------------------------------------
# Graph
# ---------------------------------------------------------

elif view == "Graph":
    st.subheader("How the code connects")
    st.caption("Switch node and edge types on and off, find a symbol, drag to rearrange, scroll to zoom.")

    graph_raw = cached_graph(repo_key) or {}
    nodes, edges = normalize_graph(graph_raw.get("nodes"), graph_raw.get("edges"))

    if not nodes:
        st.info(
            "No graph nodes came back for this repository. Check that indexing finished "
            "and that the graph endpoint returns nodes for it."
        )
    else:
        if len(nodes) > MAX_GRAPH_NODES:
            keep = {n["id"] for n in nodes[:MAX_GRAPH_NODES]}
            st.caption(f"Showing the first {MAX_GRAPH_NODES} of {len(nodes):,} nodes to keep the graph responsive.")
            nodes = nodes[:MAX_GRAPH_NODES]
            edges = [e for e in edges if e["source"] in keep and e["target"] in keep]
        render_graph(nodes, edges)


# ---------------------------------------------------------
# Insights
# ---------------------------------------------------------

elif view == "Insights":
    st.subheader("Insights")

    graph_raw = cached_graph(repo_key) or {}
    nodes, edges = normalize_graph(graph_raw.get("nodes"), graph_raw.get("edges"))

    node_counts, edge_counts = {}, {}
    for n in nodes:
        node_counts[n["type"]] = node_counts.get(n["type"], 0) + 1
    for e in edges:
        edge_counts[e["type"]] = edge_counts.get(e["type"], 0) + 1

    answers = [m for m in chat if m["role"] == "assistant"]
    scores = [m.get("eval_score", 0.0) for m in answers]
    average = sum(scores) / len(scores) if scores else 0.0
    intents = len({m.get("intent", "") for m in answers if m.get("intent")})

    left, right = st.columns(2, gap="large")
    with left:
        md(
            '<div class="sect"><h4>The repository</h4>'
            + kv_rows([
                ("Files parsed", f'{n_of("files"):,}'),
                ("Code chunks", f'{n_of("chunks"):,}'),
                ("Graph nodes", f'{n_of("nodes"):,}'),
                ("Graph edges", f'{n_of("edges"):,}'),
            ])
            + "</div>"
        )
    with right:
        md(
            '<div class="sect"><h4>This conversation</h4>'
            + kv_rows([
                ("Questions answered", len(answers)),
                ("Average quality", f"{average:.1f} out of 10"),
                ("Different intents", intents),
            ])
            + "</div>"
        )

    left, right = st.columns(2, gap="large")
    with left:
        body = render_bars(node_counts, NODE_COLORS) if node_counts else '<p class="sub">No graph data yet.</p>'
        md(f'<div class="sect"><h4>What the code is made of</h4>{body}</div>')
    with right:
        body = render_bars(edge_counts, EDGE_COLORS) if edge_counts else '<p class="sub">No graph data yet.</p>'
        md(f'<div class="sect"><h4>How the parts relate</h4>{body}</div>')

    if scores:
        recent = list(enumerate(scores, 1))[-10:]
        rows = "".join(
            f'<div class="bar-row"><div class="bar-label">Question {i}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{min(s, 10) * 10:.0f}%;background:{SCORE_COLOR[score_level(s)]}"></div></div>'
            f'<div class="bar-count">{s:.1f}</div></div>'
            for i, s in recent
        )
    else:
        rows = '<p class="sub">Ask a question and each answer\'s score will be charted here.</p>'
    md(f'<div class="sect"><h4>How each answer scored</h4>{rows}</div>')


# ---------------------------------------------------------
# Repositories
# ---------------------------------------------------------

else:
    st.subheader("Add a repository")
    st.caption("Public GitHub repositories only. Large projects can take a few minutes to index.")
    render_ingest_form("add")

    st.write("")
    st.subheader("Indexed repositories")

    widths = [2.1, 3, 0.9, 0.9, 0.9, 0.9, 1.3]
    heads = ["Name", "Address", "Files", "Chunks", "Nodes", "Edges", ""]
    for col, head in zip(st.columns(widths), heads):
        col.markdown(f'<div class="tbl-head">{head}</div>', unsafe_allow_html=True)

    for name, info in repo_map.items():
        active = name == active_repo
        cols = st.columns(widths)
        cols[0].markdown(f'<div class="cell"><b>{safe(name)}</b></div>', unsafe_allow_html=True)
        cols[1].markdown(f'<div class="cell url">{safe(info.get("url", ""))}</div>', unsafe_allow_html=True)
        for col, key in zip(cols[2:6], ["files", "chunks", "nodes", "edges"]):
            col.markdown(f'<div class="cell num">{int(info.get(key, 0) or 0):,}</div>', unsafe_allow_html=True)
        cols[6].button(
            "In use" if active else "Open",
            key=f"open_{name}",
            on_click=open_repo,
            args=(name,),
            disabled=active,
            use_container_width=True,
        )
        md('<div class="row-rule"></div>')

    st.write("")
    with st.expander(f"Remove {active_repo}"):
        st.caption("Deletes this repository's vectors and graph data. This cannot be undone.")
        confirm = st.checkbox("I understand", key=f"confirm_{active_repo}")
        if st.button("Delete repository data", disabled=not confirm):
            if api_delete(record.get("id") or active_repo):
                st.session_state.chats.pop(active_repo, None)
                cached_graph.clear()
                st.success("Repository data deleted.")
                time.sleep(0.8)
                st.rerun()
            else:
                st.error("Delete failed. Check the API server logs.")