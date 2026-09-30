import base64
from datetime import datetime
import hmac
import html as html_lib
import inspect
import io
import json
import os

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Novalink · Telephony Quotation",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_NAME = "Novalink"
APP_TAGLINE = "Telephony quotation"

# ==========================================
# 2. DESIGN SYSTEM (shared with Prospect Engine)
# ==========================================
APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --bg: #0A0E1A;
  --surface: #111827;
  --surface-2: #161F33;
  --surface-3: #1C2740;
  --border: rgba(148, 163, 184, 0.14);
  --border-strong: rgba(148, 163, 184, 0.26);
  --text: #E7EAF3;
  --muted: #8C98B0;
  --faint: #5E6A82;
  --accent: #7C83FF;
  --accent-2: #38D6F5;
  --accent-soft: rgba(124, 131, 255, 0.14);
  --good: #34D399;
  --warn: #FBBF24;
  --risk: #FB923C;
  --bad: #F87171;
  --radius: 14px;
  --grad: linear-gradient(135deg, #7C83FF 0%, #38D6F5 100%);
}

html, body, [class*="css"], .stApp, button, input, textarea, select {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}
.stApp {
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(56, 214, 245, 0.07), transparent 60%),
    radial-gradient(900px 500px at 10% -20%, rgba(124, 131, 255, 0.10), transparent 60%),
    var(--bg);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
footer { visibility: hidden; }
.block-container { padding-top: 1.6rem !important; padding-bottom: 3rem !important; max-width: 1500px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0D1322 0%, #0A0E1A 100%);
  border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarContent"] { padding-top: 0.6rem; }
[data-testid="stSidebarUserContent"] { padding-top: 1rem; }

/* ---------- Typography ---------- */
h1, h2, h3, h4 { color: var(--text); letter-spacing: -0.02em; }
p, li, label, .stMarkdown { color: var(--text); }
[data-testid="stCaptionContainer"], .stCaption { color: var(--muted) !important; }
[data-testid="stWidgetLabel"] p {
  font-size: 0.76rem !important; font-weight: 600 !important; color: var(--muted) !important;
  text-transform: uppercase; letter-spacing: 0.06em;
}

/* ---------- Cards (bordered containers) ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]),
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--radius) !important;
}
.st-key-card-queue { margin-top: 18px; }
.st-key-card-left, .st-key-card-select, .st-key-card-right, .st-key-card-login, .st-key-card-queue {
  background: linear-gradient(180deg, rgba(22, 31, 51, 0.85) 0%, rgba(17, 24, 39, 0.85) 100%);
  border: 1px solid var(--border) !important;
  border-radius: var(--radius);
  padding: 22px 22px 18px 22px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset, 0 20px 40px -24px rgba(0,0,0,0.6);
}

/* ---------- Inputs ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
  background: var(--surface) !important;
  border: 1px solid var(--border-strong) !important;
  border-radius: 10px !important;
  transition: border-color .15s ease, box-shadow .15s ease;
}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea { color: var(--text) !important; }
[data-baseweb="input"] > div, [data-baseweb="base-input"] { background: transparent !important; }
textarea { font-family: 'Inter', sans-serif !important; font-size: 0.9rem !important; line-height: 1.55 !important; }

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 10px !important; font-weight: 600 !important; padding: 0.55rem 1.1rem !important;
  border: 1px solid var(--border-strong) !important; background: var(--surface-2) !important;
  color: var(--text) !important; transition: all .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--accent) !important; color: #fff !important; transform: translateY(-1px);
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"], .stFormSubmitButton > button,
[data-testid="stBaseButton-primary"] {
  background: var(--grad) !important; border: none !important; color: #0A0E1A !important;
  box-shadow: 0 8px 24px -10px rgba(124, 131, 255, 0.8);
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  filter: brightness(1.08); color: #0A0E1A !important;
}
.stButton > button[kind="primary"] p, [data-testid="stBaseButton-primary"] p, .stFormSubmitButton > button p { color: #0A0E1A !important; font-weight: 700 !important; }

.stLinkButton a, [data-testid^="stBaseLinkButton"] {
  border-radius: 10px !important; font-weight: 700 !important; padding: 0.55rem 1.1rem !important;
}
[data-testid="stBaseLinkButton-primary"], .stLinkButton a[kind="primary"] {
  background: var(--grad) !important; border: none !important; color: #0A0E1A !important;
  box-shadow: 0 8px 24px -10px rgba(124, 131, 255, 0.8);
}
[data-testid="stBaseLinkButton-primary"] p, .stLinkButton a[kind="primary"] p { color: #0A0E1A !important; font-weight: 700 !important; }
[data-testid="stBaseLinkButton-primary"]:hover { filter: brightness(1.08); }

/* ---------- Tabs ---------- */
[data-testid="stTabs"] [role="tablist"], [data-baseweb="tab-list"] {
  gap: 4px; background: var(--surface); padding: 4px; border-radius: 12px; border: 1px solid var(--border);
}
[data-testid="stTabs"] [role="tab"], [data-baseweb="tab"] {
  border-radius: 9px !important; padding: 8px 16px !important; height: auto !important;
  color: var(--muted) !important; background: transparent !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"], [data-baseweb="tab"][aria-selected="true"] { background: var(--surface-3) !important; color: var(--text) !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"], [data-testid="stTabs"] .react-aria-SelectionIndicator { display: none !important; }
[data-testid="stTabs"] [role="tab"] p { font-weight: 600; font-size: 0.86rem; }
[data-testid="stTabs"] [role="tablist"] { width: fit-content; margin-bottom: 6px; }

/* ---------- Table, expanders, alerts ---------- */
[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
[data-testid="stExpander"] details { background: var(--surface); border: 1px solid var(--border) !important; border-radius: 12px !important; }
[data-testid="stExpander"] summary p { font-size: 0.85rem; color: var(--muted); font-weight: 600; }
[data-testid="stAlert"] { border-radius: 12px !important; border: 1px solid var(--border) !important; }
[data-testid="stCode"] pre, .stCode pre { background: var(--surface) !important; border: 1px solid var(--border); border-radius: 12px; }
hr { border-color: var(--border) !important; }

/* ================= Custom components ================= */
.pe-hero { display: flex; align-items: center; justify-content: space-between; gap: 24px; flex-wrap: wrap;
  padding: 6px 2px 22px 2px; margin-bottom: 18px; border-bottom: 1px solid var(--border); }
.pe-eyebrow { display: inline-flex; align-items: center; gap: 8px; font-size: 0.72rem; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent-2); margin-bottom: 8px; }
.pe-eyebrow .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--good); box-shadow: 0 0 0 4px rgba(52,211,153,.15); }
.pe-title { font-size: 2.05rem; font-weight: 800; letter-spacing: -0.035em; line-height: 1.1; margin: 0; color: var(--text); }
.pe-title span { background: var(--grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.pe-sub { color: var(--muted); font-size: 0.95rem; margin-top: 8px; max-width: 620px; }

.pe-stepper { display: flex; align-items: center; gap: 6px; background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px; padding: 6px; }
.pe-step { display: flex; align-items: center; gap: 8px; padding: 7px 14px 7px 7px; border-radius: 999px;
  font-size: 0.82rem; font-weight: 600; color: var(--faint); white-space: nowrap; }
.pe-step .num { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; font-size: 0.72rem;
  font-weight: 700; border: 1px solid var(--border-strong); color: var(--faint); }
.pe-step.done { color: var(--muted); }
.pe-step.done .num { background: rgba(52,211,153,.14); border-color: rgba(52,211,153,.45); color: var(--good); }
.pe-step.active { background: var(--surface-3); color: var(--text); }
.pe-step.active .num { background: var(--grad); border: none; color: #0A0E1A; }
.pe-step-sep { width: 14px; height: 1px; background: var(--border-strong); }

.pe-section { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.pe-section .badge { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
  background: var(--accent-soft); color: var(--accent); font-weight: 800; font-size: 0.85rem; border: 1px solid rgba(124,131,255,.3); }
.pe-section .t { font-size: 1.08rem; font-weight: 700; color: var(--text); line-height: 1.2; }
.pe-section .s { font-size: 0.82rem; color: var(--muted); margin-top: 2px; }

.pe-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.pe-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 0.76rem;
  font-weight: 600; background: var(--surface-3); color: var(--text); border: 1px solid var(--border); white-space: nowrap; }
.pe-chip.accent { background: var(--accent-soft); color: #B9BDFF; border-color: rgba(124,131,255,.3); }
.pe-chip.good { background: rgba(52,211,153,.12); color: var(--good); border-color: rgba(52,211,153,.3); }
.pe-chip.warn { background: rgba(251,191,36,.12); color: var(--warn); border-color: rgba(251,191,36,.3); }
.pe-chip.risk { background: rgba(251,146,60,.12); color: var(--risk); border-color: rgba(251,146,60,.3); }
.pe-chip.bad { background: rgba(248,113,113,.12); color: var(--bad); border-color: rgba(248,113,113,.3); }
.pe-chip.muted { background: transparent; color: var(--muted); }

.pe-vertical { display: flex; gap: 14px; align-items: flex-start; background: var(--surface); border: 1px dashed var(--border-strong);
  border-radius: 12px; padding: 12px 14px; margin: 2px 0 14px 0; }
.pe-vertical .lbl { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); margin-bottom: 6px; }

.pe-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 4px 0 14px 0; }
.pe-kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
.pe-kpi .v { font-size: 1.35rem; font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.pe-kpi .l { font-size: 0.72rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }

.pe-selected { display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--accent-soft);
  border: 1px solid rgba(124,131,255,.35); border-radius: 12px; padding: 12px 14px; margin: 14px 0 10px 0; }
.pe-selected .n { font-weight: 700; color: var(--text); }
.pe-selected .m { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }
.pe-hint { display: flex; align-items: center; gap: 10px; color: var(--muted); font-size: 0.86rem; background: var(--surface);
  border: 1px dashed var(--border-strong); border-radius: 12px; padding: 12px 14px; margin-top: 12px; }

.pe-empty { text-align: center; padding: 48px 24px 40px 24px; }
.pe-empty .t { font-size: 1.1rem; font-weight: 700; color: var(--text); margin-top: 14px; }
.pe-empty .s { font-size: 0.88rem; color: var(--muted); margin: 6px auto 20px auto; max-width: 360px; line-height: 1.5; }
.pe-empty ol { text-align: left; display: inline-block; margin: 0 auto; padding: 0; list-style: none; counter-reset: s; }
.pe-empty li { counter-increment: s; color: var(--muted); font-size: 0.86rem; margin: 8px 0; display: flex; align-items: center; gap: 10px; }
.pe-empty li::before { content: counter(s); width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
  background: var(--surface-3); border: 1px solid var(--border-strong); font-size: 0.72rem; font-weight: 700; color: var(--text); }

.pe-firm { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
.pe-firm .name { font-size: 1.35rem; font-weight: 800; letter-spacing: -0.025em; color: var(--text); line-height: 1.2; }
.pe-firm .meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.pe-firm .blurb { color: var(--muted); font-size: 0.86rem; line-height: 1.5; margin-top: 10px; font-style: italic; }

.pe-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
@media (max-width: 1100px) { .pe-grid2 { grid-template-columns: 1fr; } .pe-kpis { grid-template-columns: 1fr 1fr 1fr; } }
.pe-panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-bottom: 10px; }
.pe-cols { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: 0 18px; }
@media (max-width: 1250px) { .pe-cols { grid-template-columns: 1fr; } }
.pe-hook { margin-bottom: 10px; }
.pe-panel .h { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); margin-bottom: 10px; }

.pe-contact { display: flex; align-items: center; gap: 12px; }
.pe-avatar { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; font-weight: 800; font-size: 0.95rem;
  background: var(--grad); color: #0A0E1A; flex-shrink: 0; }
.pe-contact .n { font-weight: 700; font-size: 1.02rem; color: var(--text); }
.pe-contact .r { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }

.pe-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-top: 1px solid var(--border); font-size: 0.86rem; }
.pe-row:first-of-type { border-top: none; }
.pe-row svg { color: var(--accent-2); flex-shrink: 0; }
.pe-row a, .pe-row span { color: var(--text) !important; text-decoration: none; overflow-wrap: anywhere; }
.pe-row .tag { color: var(--faint) !important; white-space: nowrap; }
.pe-row a.trunc { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; overflow-wrap: normal; }
.pe-row a:hover { color: var(--accent-2) !important; }
.pe-row .tag { margin-left: auto; font-size: 0.68rem; color: var(--faint); font-weight: 600; text-transform: uppercase; letter-spacing: .05em; }
.pe-none { color: var(--faint); font-size: 0.84rem; font-style: italic; }

.pe-officer { display: flex; justify-content: space-between; gap: 8px; padding: 6px 0; border-top: 1px solid var(--border); font-size: 0.84rem; }
.pe-officer:first-of-type { border-top: none; }
.pe-officer .who { color: var(--text); font-weight: 600; }
.pe-officer .since { color: var(--faint); font-size: 0.76rem; white-space: nowrap; }

.pe-hook { background: linear-gradient(135deg, rgba(124,131,255,.12), rgba(56,214,245,.06)); border: 1px solid rgba(124,131,255,.28);
  border-radius: 12px; padding: 14px 16px; }
.pe-hook .h { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #B9BDFF; }
.pe-hook .t { font-weight: 700; color: var(--text); margin: 4px 0 10px 0; }
.pe-hook ul { margin: 0; padding-left: 0; list-style: none; }
.pe-hook li { font-size: 0.85rem; color: var(--text); padding: 4px 0 4px 24px; position: relative; }
.pe-hook li::before { content: ""; position: absolute; left: 4px; top: 10px; width: 8px; height: 8px; border-radius: 50%; background: var(--grad); }

/* Sidebar components */
.pe-brand { display: flex; align-items: center; gap: 12px; padding: 4px 0 18px 0; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.pe-logo { width: 40px; height: 40px; border-radius: 12px; background: var(--grad); display: grid; place-items: center; color: #0A0E1A;
  box-shadow: 0 10px 24px -10px rgba(124,131,255,.9); }
.pe-brand .n { font-weight: 800; font-size: 1.05rem; color: var(--text); letter-spacing: -0.02em; }
.pe-brand .s { font-size: 0.75rem; color: var(--muted); }
.pe-side-h { font-size: 0.68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--faint); margin: 18px 0 8px 0; }
.pe-status { display: flex; align-items: center; justify-content: space-between; font-size: 0.84rem; color: var(--text); padding: 7px 0; }
.pe-status .st { display: inline-flex; align-items: center; gap: 6px; font-size: 0.76rem; font-weight: 600; }
.pe-status .st.ok { color: var(--good); } .pe-status .st.off { color: var(--bad); } .pe-status .st.idle { color: var(--muted); }
.pe-status .st::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pe-stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.pe-stat { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px; text-align: center; }
.pe-stat .v { font-weight: 800; font-size: 1.1rem; color: var(--text); }
.pe-stat .l { font-size: 0.64rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 600; margin-top: 2px; }

/* Login */
.pe-login-head { text-align: center; margin: 8vh 0 22px 0; }
.pe-login-head .pe-logo { width: 54px; height: 54px; margin: 0 auto 16px auto; border-radius: 16px; }
.pe-login-head .t { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; color: var(--text); }
.pe-login-head .s { color: var(--muted); font-size: 0.92rem; margin-top: 6px; }
</style>
"""

NOVALINK_CSS = """
<style>
/* Hide Streamlit chrome for a clean, customer-facing look */
#MainMenu {visibility: hidden;}
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {display: none;}
.block-container { max-width: 1440px; }

.st-key-card-users, .st-key-card-hardware, .st-key-card-details, .st-key-card-summary,
.st-key-card-cv-head, .st-key-card-cv-monthly, .st-key-card-cv-oneoff {
  background: linear-gradient(180deg, rgba(22, 31, 51, 0.85) 0%, rgba(17, 24, 39, 0.85) 100%);
  border: 1px solid var(--border) !important;
  border-radius: var(--radius);
  padding: 22px 22px 18px 22px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset, 0 20px 40px -24px rgba(0,0,0,0.6);
  margin-bottom: 18px;
}
.st-key-card-summary { border-color: rgba(124,131,255,.35) !important; }
[data-testid="stColumn"]:has(.st-key-card-summary), [data-testid="column"]:has(.st-key-card-summary) {
  position: sticky; top: 1rem; align-self: flex-start; }

/* Licence feature panel */
.nl-licence { position: relative; border-radius: 14px; padding: 20px; overflow: hidden;
  background: linear-gradient(135deg, rgba(124,131,255,.16), rgba(56,214,245,.07));
  border: 1px solid rgba(124,131,255,.35); }
.nl-licence .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.nl-licence .name { font-size: 1.15rem; font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.nl-licence .sub { font-size: 0.82rem; color: var(--muted); margin-top: 4px; }
.nl-price { background: var(--grad); color: #0A0E1A; font-weight: 800; font-size: 0.9rem; padding: 6px 12px;
  border-radius: 999px; white-space: nowrap; }
.nl-price small { font-weight: 600; font-size: 0.72rem; opacity: .8; }
.nl-feats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; margin: 16px 0 14px 0; }
.nl-feat { display: flex; align-items: center; gap: 9px; font-size: 0.86rem; color: var(--text); }
.nl-feat .ck { width: 20px; height: 20px; border-radius: 6px; display: grid; place-items: center; flex-shrink: 0;
  background: rgba(52,211,153,.14); color: var(--good); border: 1px solid rgba(52,211,153,.35); }
.nl-activation { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: var(--muted);
  border-top: 1px solid var(--border); padding-top: 12px; }
.nl-activation b { color: var(--text); }

/* Mini stat */
.nl-mini { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
.nl-mini > div { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; }
.nl-mini .v { font-size: 1.25rem; font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.nl-mini .l { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
.nl-mini .s { font-size: 0.75rem; color: var(--faint); margin-top: 2px; }

/* Product cards */
[class*="st-key-prod-"] {
  background: var(--surface); border: 1px solid var(--border) !important; border-radius: 14px;
  padding: 14px 14px 12px 14px; transition: border-color .15s ease, transform .15s ease, box-shadow .15s ease;
  height: 100%;
}
[class*="st-key-prod-"]:hover { border-color: rgba(124,131,255,.45) !important; transform: translateY(-2px);
  box-shadow: 0 16px 30px -20px rgba(0,0,0,.8); }
[class*="st-key-prod-on-"] { border-color: rgba(56,214,245,.55) !important; box-shadow: 0 0 0 1px rgba(56,214,245,.25), 0 16px 30px -20px rgba(56,214,245,.35); }
.nl-prod-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.nl-prod-price { font-weight: 800; font-size: 1.05rem; color: var(--text); letter-spacing: -0.02em; }
.nl-stage { height: 140px; margin: 12px 0 10px 0; border-radius: 12px; display: grid; place-items: center; overflow: hidden;
  background: radial-gradient(120% 90% at 50% 20%, #FFFFFF 0%, #EEF1F8 70%, #E3E8F2 100%); }
.nl-stage img { max-height: 124px; max-width: 88%; object-fit: contain; filter: drop-shadow(0 8px 10px rgba(15,23,42,.18)); }
.nl-stage .ph { color: #94A3B8; display: grid; place-items: center; gap: 6px; font-size: 0.72rem; }
.nl-prod-name { font-weight: 700; font-size: 0.92rem; color: var(--text); line-height: 1.25; min-height: 2.4em; }
.nl-prod-desc { font-size: 0.74rem; color: var(--muted); line-height: 1.35; margin-top: 4px; min-height: 3.1em;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.nl-qty { text-align: center; font-weight: 800; font-size: 1.05rem; color: var(--text); background: var(--surface-2);
  border: 1px solid var(--border-strong); border-radius: 10px; padding: 7px 0; }
.nl-qty.on { border-color: rgba(56,214,245,.6); color: var(--accent-2); }
.nl-sub { text-align: center; font-size: 0.74rem; margin-top: 8px; color: var(--faint); }
.nl-sub.on { color: var(--accent-2); font-weight: 600; }
[class*="st-key-prod-"] .stButton > button { padding: 0.3rem 0 !important; min-height: 38px; font-size: 1.05rem !important; }

/* Category filter (segmented control / radio) */
[data-testid="stButtonGroup"] button, div[role="radiogroup"] label { border-radius: 999px !important; }

/* Live summary */
.nl-sum-h { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.nl-sum-h .t { font-weight: 800; font-size: 1.05rem; color: var(--text); }
.nl-live { display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 700; color: var(--good);
  text-transform: uppercase; letter-spacing: .08em; }
.nl-live::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--good); box-shadow: 0 0 0 4px rgba(52,211,153,.15); }
.nl-total { border-radius: 12px; padding: 12px 14px; margin-bottom: 8px; background: var(--surface); border: 1px solid var(--border); }
.nl-total .l { font-size: 0.7rem; color: var(--muted); font-weight: 700; text-transform: uppercase; letter-spacing: .07em; }
.nl-total .v { font-size: 1.5rem; font-weight: 800; color: var(--text); letter-spacing: -0.03em; line-height: 1.2; margin-top: 2px; }
.nl-total .v small { font-size: 0.78rem; font-weight: 600; color: var(--muted); letter-spacing: 0; }
.nl-total .i { font-size: 0.78rem; color: var(--faint); margin-top: 1px; }
.nl-total.hero { background: linear-gradient(135deg, rgba(124,131,255,.18), rgba(56,214,245,.08)); border-color: rgba(124,131,255,.4); }
.nl-total.hero .v { background: var(--grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.nl-lines-h { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); margin: 14px 0 6px 0; }
.nl-line { display: flex; justify-content: space-between; gap: 10px; font-size: 0.84rem; padding: 7px 0; border-top: 1px solid var(--border); }
.nl-line .n { color: var(--text); }
.nl-line .n small { color: var(--faint); margin-left: 4px; }
.nl-line .p { color: var(--text); font-weight: 600; white-space: nowrap; }
.nl-empty { font-size: 0.82rem; color: var(--faint); font-style: italic; padding: 6px 0; }
.nl-term { display: flex; gap: 8px; align-items: flex-start; font-size: 0.75rem; color: var(--muted); margin-top: 12px;
  background: rgba(251,191,36,.07); border: 1px solid rgba(251,191,36,.25); border-radius: 10px; padding: 10px 12px; line-height: 1.4; }
.nl-term svg { color: var(--warn); flex-shrink: 0; margin-top: 1px; }
.st-key-card-summary [data-testid="stCaptionContainer"] { margin-top: 8px; }
.nl-line.nb { border-top: none; }
[class*="st-key-sumline-"] { border-top: 1px solid var(--border); gap: 0 !important; }
[class*="st-key-sumline-"] [data-testid="stHorizontalBlock"] { gap: 6px !important; }
[class*="st-key-sumline-"] .stButton button {
  padding: 0 !important; min-height: 26px !important; height: 26px; width: 26px; font-size: 0.72rem !important;
  background: transparent !important; border: 1px solid transparent !important; color: var(--faint) !important; }
[class*="st-key-sumline-"] .stButton button:hover { border-color: rgba(248,113,113,.5) !important; color: var(--bad) !important; transform: none; }
[class*="st-key-sumline-"] .stButton { display: flex; justify-content: flex-end; padding-top: 7px; }

/* Form */
[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }
.nl-form-h { display: flex; align-items: center; gap: 8px; font-weight: 700; font-size: 0.92rem; color: var(--text); margin: 4px 0 6px 0; }
.nl-form-h svg { color: var(--accent-2); }

/* Customer view */
.nl-prop { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; flex-wrap: wrap; }
.nl-prop .k { font-size: 0.72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--accent-2); }
.nl-prop .t { font-size: 1.9rem; font-weight: 800; letter-spacing: -0.035em; color: var(--text); margin-top: 6px; line-height: 1.1; }
.nl-prop .t span { background: var(--grad); -webkit-background-clip: text; background-clip: text; color: transparent; }
.nl-prop .s { color: var(--muted); font-size: 0.92rem; margin-top: 6px; }
.nl-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 20px; }
@media (max-width: 900px) { .nl-kpis { grid-template-columns: 1fr; } .nl-feats { grid-template-columns: 1fr; } }
.nl-kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 16px 18px; border-top: 2px solid var(--c, var(--accent)); }
.nl-kpi .l { font-size: 0.72rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.nl-kpi .v { font-size: 1.8rem; font-weight: 800; letter-spacing: -0.03em; color: var(--text); margin-top: 6px; line-height: 1.1; }
.nl-kpi .v small { font-size: 0.8rem; color: var(--muted); font-weight: 600; letter-spacing: 0; }
.nl-kpi .i { font-size: 0.82rem; color: var(--faint); margin-top: 4px; }
.nl-table { width: 100%; border-collapse: separate !important; border-spacing: 0; font-size: 0.88rem; border: none !important; margin: 0 !important; }
.nl-table th, .nl-table td { border-left: none !important; border-right: none !important; border-top: none !important; }
.nl-table th { text-align: left; font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); padding: 10px 12px; border-bottom: 1px solid var(--border-strong); background: transparent !important; }
.nl-table td { padding: 12px; border-bottom: 1px solid var(--border); color: var(--text); vertical-align: middle; background: transparent !important; }
.nl-table td.num, .nl-table th.num { text-align: right; white-space: nowrap; }
.nl-table .desc { color: var(--muted); font-size: 0.76rem; margin-top: 2px; }
.nl-table .thumb { width: 44px; height: 44px; border-radius: 10px; background: #F1F4FA; display: grid; place-items: center; overflow: hidden; }
.nl-table .thumb img { max-width: 38px; max-height: 38px; object-fit: contain; }
.nl-table tr.sub td { border-bottom: none; padding-top: 8px; padding-bottom: 4px; color: var(--muted); }
.nl-table tr.grand td { border-top: 1px solid var(--border-strong); font-weight: 800; font-size: 1rem; padding-top: 12px; }
.nl-table tr.grand td.num { background: var(--grad) !important; -webkit-background-clip: text !important; background-clip: text !important; color: transparent; }
.nl-note { margin-top: 14px; font-size: 0.82rem; color: var(--muted); border: 1px dashed var(--border-strong); border-radius: 12px; padding: 12px 14px; }
</style>
"""

_ICON_PATHS = {
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "building": '<path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/><path d="M9 9v.01M9 12v.01M9 15v.01M9 18v.01"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "truck": '<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
    "alert": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "image": '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
}


def icon(name: str, size: int = 16, stroke: float = 2) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor"'
        f' stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{_ICON_PATHS[name]}</svg>'
    )


def esc(value) -> str:
    return html_lib.escape(str(value if value is not None else ""), quote=True)


def render_html(markup: str, target=None) -> None:
    """Renders HTML via markdown. Lines are flattened so markdown never treats indentation as code."""
    flat = "".join(line.strip() for line in markup.splitlines())
    (target or st).markdown(flat, unsafe_allow_html=True)


def inject_css() -> None:
    st.markdown(APP_CSS + NOVALINK_CSS, unsafe_allow_html=True)


def chip(text: str, tone: str = "") -> str:
    return f'<span class="pe-chip {tone}">{esc(text)}</span>'


def section_header(num: str, title: str, subtitle: str = "") -> None:
    render_html(
        f'<div class="pe-section"><div class="badge">{num}</div><div>'
        f'<div class="t">{esc(title)}</div>'
        + (f'<div class="s">{esc(subtitle)}</div>' if subtitle else "")
        + "</div></div>"
    )


def _full_width_kwargs():
    try:
        if "width" in inspect.signature(st.button).parameters:
            return {"width": "stretch"}
    except (TypeError, ValueError):
        pass
    return {"use_container_width": True}


FULL_WIDTH = _full_width_kwargs()


def columns(spec, **kwargs):
    try:
        return st.columns(spec, vertical_alignment="bottom", **kwargs)
    except TypeError:
        return st.columns(spec, **kwargs)


def money(v: float) -> str:
    return f"£{v:,.2f}"


def hero_html(active_step: int) -> str:
    steps = ["Users", "Hardware", "Details", "PDF"]
    parts = []
    for i, label in enumerate(steps, start=1):
        state = "done" if i < active_step else "active" if i == active_step else ""
        num = icon("check", 12, 3) if state == "done" else str(i)
        parts.append(f'<div class="pe-step {state}"><span class="num">{num}</span>{label}</div>')
    stepper = '<div class="pe-step-sep"></div>'.join(parts)
    return (
        '<div class="pe-hero"><div>'
        f'<div class="pe-eyebrow"><span class="dot"></span>Hosted cloud telephony · {esc(datetime.now().strftime("%d %B %Y"))}</div>'
        '<div class="pe-title">Novalink Telephony <span>Quotation</span></div>'
        '<div class="pe-sub">Combine cloud user licences with desk, cordless and headset hardware.'
        ' Totals update live, and the official PDF is one click away.</div>'
        f'</div><div class="pe-stepper">{stepper}</div></div>'
    )


# ==========================================
# 3. AUTHENTICATION GATE (fails closed)
# ==========================================
def check_password() -> bool:
    if st.session_state.get("authenticated", False):
        return True
    try:
        configured_password = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        configured_password = ""

    _, mid, _ = st.columns([1, 1.25, 1])
    with mid:
        render_html(
            f'<div class="pe-login-head"><div class="pe-logo">{icon("phone", 24, 2.2)}</div>'
            f'<div class="t">{APP_NAME} Quotation</div>'
            '<div class="s">Reseller access only. Enter your access key to continue.</div></div>'
        )
        if not configured_password:
            st.error("APP_PASSWORD isn't set in Streamlit Secrets, so access is locked. Add it under App settings → Secrets.")
            return False
        with st.container(key="card-login"):
            with st.form("login_form", border=False):
                attempt = st.text_input("Access password", type="password", placeholder="Enter your access key")
                submitted = st.form_submit_button("Unlock portal", type="primary", **FULL_WIDTH)
            if submitted:
                if hmac.compare_digest(attempt.encode("utf-8"), str(configured_password).encode("utf-8")):
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("Incorrect password. Please try again.")
    return False


inject_css()
if not check_password():
    st.stop()


# ==========================================
# 4. IMAGES
# ==========================================
@st.cache_data
def get_base64_image(image_path):
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode("utf-8")
            ext = os.path.splitext(image_path)[1].lower().replace(".", "")
            if ext == "jpg":
                ext = "jpeg"
            return f"data:image/{ext};base64,{encoded}"
    return None


# ==========================================
# 5. HARDWARE & ACCESSORIES CATALOGUE
# ==========================================
LICENCE_MONTHLY_RATE = 9.00
ACTIVATION_FEE_PER_USER = 25.00
VAT_RATE = 0.20
CATALOGUE_FILE = "catalogue.json"

_FALLBACK_PRODUCTS = [
    # --- Fanvil Core Series ---
    {"id": "v67", "category": "Fanvil Phones", "tag": "Flagship Touch", "name": "Fanvil Executive V67",
     "desc": "7-inch adjustable touch screen with HD video, built-in Wi-Fi & Bluetooth", "image": "Fanvil V67.webp", "price": 189.00},
    {"id": "v66pro", "category": "Fanvil Phones", "tag": "Executive Audio", "name": "Fanvil Premium V66 Pro",
     "desc": "Multi-line executive audio console with dual-screen colour display and Gigabit PoE", "image": "V66 Pro.webp", "price": 129.00},
    {"id": "v62pro", "category": "Fanvil Phones", "tag": "Standard Desk", "name": "Fanvil Essential V62 Pro",
     "desc": "High-durability office desktop phone with 6 SIP lines and crystal-clear HD audio", "image": "Fanvil V62 Pro.png", "price": 89.00},
    {"id": "w620w", "category": "Cordless DECT", "tag": "Rugged Cordless", "name": "Linkvil Rugged W620W",
     "desc": "IP67 waterproof & drop-proof wireless roaming handset with 15h talk time", "image": "Linkvil W620W Rugged.png", "price": 149.00},
    # --- Yealink T-Series Prime Desk Phones ---
    {"id": "t73w", "category": "Yealink Phones", "tag": "Smart Business", "name": "Yealink T73W",
     "desc": "Entry-level executive IP desk phone with dual-band Wi-Fi and Bluetooth", "image": "Yealink T73W.png", "price": 78.00},
    {"id": "t74w", "category": "Yealink Phones", "tag": "Colour Executive", "name": "Yealink T74W",
     "desc": "High-performance business phone with colour screen and integrated wireless", "image": "Yealink T74W.png", "price": 111.00},
    {"id": "t85w", "category": "Yealink Phones", "tag": "Gigabit Console", "name": "Yealink T85W",
     "desc": "Advanced desktop console with colour display, Optima HD voice & USB expansion", "image": "Yealink T85W.png", "price": 115.00},
    {"id": "t87w", "category": "Yealink Phones", "tag": "Executive Touch", "name": "Yealink T87W",
     "desc": "Large touchscreen IP phone engineered for managers and knowledge workers", "image": "Yealink T87W.png", "price": 155.00},
    {"id": "t88w_pro", "category": "Yealink Phones", "tag": "Flagship Touch Pro", "name": "Yealink T88W Pro",
     "desc": "Premium smart media touch console with ultra-fast UI and full video support", "image": "Yealink T88W Pro.png", "price": 225.00},
    # --- Yealink Cordless DECT & Roaming ---
    {"id": "w74p", "category": "Cordless DECT", "tag": "DECT Package", "name": "Yealink W74P",
     "desc": "High-performance DECT cordless phone system including base station & handset", "image": "Yealink W74P.png", "price": 87.00},
    {"id": "ax83h", "category": "Cordless DECT", "tag": "Commercial DECT", "name": "Yealink AX83H",
     "desc": "Slim, modern cordless business handset for active office environments", "image": "Yealink AX83H.png", "price": 75.00},
    {"id": "ax86r", "category": "Cordless DECT", "tag": "Rugged DECT", "name": "Yealink AX86R",
     "desc": "Heavy-duty shockproof and water-resistant rugged handset for site roaming", "image": "Yealink AX86R.png", "price": 113.00},
    # --- Headsets & Accessories ---
    {"id": "uh36_mono", "category": "Headsets & Accessories", "tag": "UC Headset", "name": "Yealink UH36 Mono Headset UC",
     "desc": "Noise-cancelling professional USB/3.5mm wired mono headset with inline controller", "image": "Yealink UH36 Mono Headset UC.png", "price": 42.00},
    {"id": "psu_10w", "category": "Headsets & Accessories", "tag": "Power Supply", "name": "Yealink 10W PSU",
     "desc": "Official UK 10W mains power adapter for non-PoE network deployments", "image": "Yealink 10W PSU.png", "price": 11.00},
]


@st.cache_data(ttl=60)
def load_products():
    if os.path.isfile(CATALOGUE_FILE):
        try:
            with open(CATALOGUE_FILE, "r") as f:
                data = json.load(f)
            products = data.get("products", [])
            if products:
                for p in products:
                    if "tag" not in p or "category" not in p:
                        match = next((fb for fb in _FALLBACK_PRODUCTS if fb["id"] == p.get("id")), None)
                        if match:
                            p["tag"] = match["tag"]
                            p["category"] = match.get("category", "Hardware")
                return products
        except (json.JSONDecodeError, OSError):
            pass
    return _FALLBACK_PRODUCTS


PRODUCTS = load_products()

# ==========================================
# 6. SESSION STATE & PRICING
# ==========================================
if "basket" not in st.session_state:
    st.session_state.basket = {}
if "num_licences" not in st.session_state:
    st.session_state.num_licences = 0


def update_qty(product_id, delta):
    current = st.session_state.basket.get(product_id, 0)
    new_val = max(0, current + delta)
    if new_val > 0:
        st.session_state.basket[product_id] = new_val
    else:
        st.session_state.basket.pop(product_id, None)


def remove_from_basket(product_id):
    st.session_state.basket.pop(product_id, None)


def basket_items():
    items = []
    for pid, qty in st.session_state.basket.items():
        prod = next((p for p in PRODUCTS if p["id"] == pid), None)
        if prod and qty > 0:
            items.append({**prod, "qty": qty, "line_total": prod["price"] * qty})
    return items


def total_hardware_capex():
    return sum(item["line_total"] for item in basket_items())


def total_monthly_licences():
    users = st.session_state.get("num_licences", 0)
    return float(users) * LICENCE_MONTHLY_RATE if users > 0 else 0.0


def total_activation_fee():
    users = st.session_state.get("num_licences", 0)
    return float(users) * ACTIVATION_FEE_PER_USER if users > 0 else 0.0


# ==========================================
# 7. PDF QUOTATION (ReportLab, A4)
# ==========================================
def generate_quotation_pdf(quote_meta, reseller, customer, num_users, hw_items):
    # Escape typed text so names like "Smith & Co" or "<Ltd>" can't break the PDF layout
    reseller = {k: esc(v) for k, v in reseller.items()}
    customer = {k: esc(v) for k, v in customer.items()}
    hw_items = [{**i, "name": esc(i["name"]), "desc": esc(i["desc"])} for i in hw_items]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,  # UK standard (was US Letter)
        rightMargin=27,
        leftMargin=27,
        topMargin=32,
        bottomMargin=32,
    )
    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#0F5A73")
    c_slate = colors.HexColor("#475569")
    c_dark = colors.HexColor("#0F172A")
    c_bg = colors.HexColor("#F8FAFC")
    c_border = colors.HexColor("#CBD5E1")
    c_warning_bg = colors.HexColor("#FFFBEB")
    c_warning_border = colors.HexColor("#F59E0B")
    c_warning_text = colors.HexColor("#92400E")

    title_style = ParagraphStyle("DocTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=c_primary)
    meta_style = ParagraphStyle("MetaText", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=12, textColor=c_slate)
    sec_head = ParagraphStyle("SectionHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=c_primary)
    th_style = ParagraphStyle("TH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.white)
    td_style = ParagraphStyle("TD", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=c_dark)
    td_bold = ParagraphStyle("TDB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11.5, textColor=c_dark)

    story = []

    # Title & Metadata
    hdr = Table(
        [[
            Paragraph("<b>Novalink Telephony Quotation</b>", title_style),
            Paragraph(
                f"<b>Reference:</b> {quote_meta['ref']}<br/>"
                f"<b>Date:</b> {quote_meta['date']}<br/>"
                f"<b>Contract Term:</b> <b>24 Months Minimum</b>",
                meta_style,
            ),
        ]],
        colWidths=[350, 190],
    )
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story.append(hdr)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceAfter=10, spaceBefore=0))

    # Provider & Customer Panels
    addr_line = (
        f"Site/Delivery: {customer['delivery']}<br/>"
        if customer["delivery"] and customer["delivery"] != "N/A"
        else ""
    )
    parties = [
        [Paragraph("<b>SERVICE PROVIDER / PARTNER</b>", td_bold), Paragraph("<b>PROPOSED CUSTOMER</b>", td_bold)],
        [
            Paragraph(
                f"<b>{reseller['company']}</b><br/>"
                f"Account Manager: {reseller['name']}<br/>"
                f"Email: {reseller['email']}<br/>"
                f"Telephone: {reseller['phone']}",
                td_style,
            ),
            Paragraph(
                f"<b>{customer['company']}</b><br/>"
                f"Contact Name: {customer['name']}<br/>"
                f"Email: {customer['email']}<br/>"
                f"Telephone: {customer['phone']}<br/>"
                f"{addr_line}",
                td_style,
            ),
        ],
    ]
    t_party = Table(parties, colWidths=[270, 270])
    t_party.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_bg),
        ("BOX", (0, 0), (-1, -1), 1, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_party)
    story.append(Spacer(1, 10))

    # 1. Ongoing Monthly Costs Table
    story.append(Paragraph("1. Ongoing Monthly Costs", sec_head))
    story.append(Spacer(1, 4))
    mrc_total = num_users * LICENCE_MONTHLY_RATE if num_users > 0 else 0.0
    mrc_vat = mrc_total * VAT_RATE
    mrc_inc_vat = mrc_total + mrc_vat

    mrc_data = [
        [Paragraph("Description", th_style), Paragraph("Users", th_style),
         Paragraph("Unit Price (Ex VAT)", th_style), Paragraph("Monthly Total (Ex VAT)", th_style)],
        [
            Paragraph(
                "<b>Hosted VoIP Cloud User Licence</b><br/>"
                "<font color='#64748B' size=7>Includes PC/Mac softphone, iOS/Android mobile apps, cloud call recording, auto-attendant &amp; inclusive UK landline/mobile calls.</font>",
                td_style,
            ),
            Paragraph(str(num_users), td_style),
            Paragraph(f"£{LICENCE_MONTHLY_RATE:.2f} / mo", td_style),
            Paragraph(f"£{mrc_total:.2f} / mo", td_bold),
        ],
        [Paragraph("<b>Total Ongoing Monthly Costs (Ex VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{mrc_total:.2f} / mo</b>", td_bold)],
        [Paragraph("VAT @ 20%", td_style), "", "", Paragraph(f"£{mrc_vat:.2f} / mo", td_style)],
        [Paragraph("<b>Total Ongoing Monthly Costs (Inc VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{mrc_inc_vat:.2f} / mo</b>", td_bold)],
    ]
    t_mrc = Table(mrc_data, colWidths=[290, 50, 100, 100])
    t_mrc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("BOX", (0, 0), (-1, -1), 1, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
        ("BACKGROUND", (0, 2), (-1, 2), c_bg),
        ("BACKGROUND", (0, 4), (-1, 4), c_bg),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    story.append(t_mrc)
    story.append(Spacer(1, 10))

    # 2. One-Off Upfront Costs Table
    story.append(Paragraph("2. One-Off Upfront Costs", sec_head))
    story.append(Spacer(1, 4))

    activation_total = num_users * ACTIVATION_FEE_PER_USER if num_users > 0 else 0.0
    hw_total = sum(i["line_total"] for i in hw_items)
    one_off_grand_total = activation_total + hw_total
    one_off_vat = one_off_grand_total * VAT_RATE
    one_off_inc_vat = one_off_grand_total + one_off_vat

    upfront_data = [
        [Paragraph("Item / Description", th_style), Paragraph("Qty", th_style),
         Paragraph("Unit Price (Ex VAT)", th_style), Paragraph("Line Total (Ex VAT)", th_style)],
        [
            Paragraph(
                "<b>Initial User Setup &amp; Activation</b><br/>"
                "<font color='#64748B' size=7>System configuration, extension setup, user provisioning &amp; portal deployment.</font>",
                td_style,
            ),
            Paragraph(str(num_users), td_style),
            Paragraph(f"£{ACTIVATION_FEE_PER_USER:.2f}", td_style),
            Paragraph(f"£{activation_total:.2f}", td_bold),
        ],
    ]
    for itm in hw_items:
        upfront_data.append([
            Paragraph(f"<b>{itm['name']}</b><br/><font color='#64748B' size=7>{itm['desc']}</font>", td_style),
            Paragraph(str(itm["qty"]), td_style),
            Paragraph(f"£{itm['price']:.2f}", td_style),
            Paragraph(f"£{itm['line_total']:.2f}", td_bold),
        ])
    upfront_data.append([Paragraph("<b>Total One-Off Upfront Costs (Ex VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{one_off_grand_total:.2f}</b>", td_bold)])
    upfront_data.append([Paragraph("VAT @ 20%", td_style), "", "", Paragraph(f"£{one_off_vat:.2f}", td_style)])
    upfront_data.append([Paragraph("<b>Total One-Off Upfront Costs (Inc VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{one_off_inc_vat:.2f}</b>", td_bold)])

    t_upfront = Table(upfront_data, colWidths=[290, 50, 100, 100])
    t_upfront.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
        ("BOX", (0, 0), (-1, -1), 1, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
        ("BACKGROUND", (0, -3), (-1, -3), c_bg),
        ("BACKGROUND", (0, -1), (-1, -1), c_bg),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
    ]))
    story.append(t_upfront)
    story.append(Spacer(1, 10))

    # Summary Box
    first_month_ex = mrc_total + one_off_grand_total
    first_month_inc = mrc_inc_vat + one_off_inc_vat
    summary_data = [[
        Paragraph("<b>FINANCIAL SUMMARY</b>", td_bold),
        Paragraph(
            f"<b>Ongoing Monthly Costs:</b> £{mrc_total:.2f} Ex VAT (£{mrc_inc_vat:.2f} Inc VAT / mo)<br/>"
            f"<b>Total One-Off Upfront Costs:</b> £{one_off_grand_total:.2f} Ex VAT (£{one_off_inc_vat:.2f} Inc VAT)<br/>"
            f"<b>Total Month 1 Investment:</b> <b>£{first_month_ex:.2f} Ex VAT (£{first_month_inc:.2f} Inc VAT)</b>",
            td_style,
        ),
    ]]
    t_sum = Table(summary_data, colWidths=[180, 360])
    t_sum.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_bg),
        ("BOX", (0, 0), (-1, -1), 1.5, c_primary),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_sum)
    story.append(Spacer(1, 10))

    # Contract Termination Clause Box
    clause_text = (
        "<b>IMPORTANT CONTRACTUAL COMMITMENT &amp; TERMINATION TERMS:</b><br/>"
        "All hosted user licences quoted herein are strictly subject to a <b>minimum 36-month agreement term</b>. "
        "In the event of early termination or cancellation of services prior to the expiry of the initial 36-month term, "
        "<b>early termination charges will be applicable and payable in full</b> for all outstanding monthly licence fees "
        "remaining across the unexpired portion of the agreement.<br/>"
        "<b>Commercial Notes:</b> Quotation valid for 30 calendar days."
    )
    clause_para = Paragraph(clause_text, ParagraphStyle(
        "ContractClause", parent=styles["Normal"], fontName="Helvetica", fontSize=7.8, leading=11, textColor=c_warning_text))
    t_clause = Table([[clause_para]], colWidths=[540])
    t_clause.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_warning_bg),
        ("BOX", (0, 0), (-1, -1), 1.2, c_warning_border),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_clause)
    story.append(Spacer(1, 10))

    # Customer Sign-Off Box
    sign_data = [
        [Paragraph("<b>CUSTOMER ACCEPTANCE &amp; AUTHORISATION:</b>", td_bold), Paragraph("<b>DATE:</b> ___________________________", td_style)],
        [Paragraph("Authorised Signature: _________________________________", td_style), Paragraph("Print Name: __________________________", td_style)],
    ]
    t_sign = Table(sign_data, colWidths=[330, 210])
    t_sign.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, c_border),
        ("BACKGROUND", (0, 0), (-1, -1), c_bg),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t_sign)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# 8. PAGE
# ==========================================
LICENCE_FEATURES = [
    "Mobile app (iOS / Android)",
    "Cloud call recording",
    "Desktop PC softphone",
    "Auto-attendant & IVR",
    "Voicemail-to-email",
    "Inclusive UK landline & mobile calls",
]
CATEGORIES = ["All hardware", "Yealink Phones", "Fanvil Phones", "Cordless DECT", "Headsets & Accessories"]


def quote_signature():
    return (st.session_state.get("num_licences", 0), tuple(sorted(st.session_state.basket.items())))


def product_image_html(product, max_h=124):
    uri = get_base64_image(product.get("image"))
    if uri:
        return f'<img src="{uri}" alt="{esc(product["name"])}" style="max-height:{max_h}px">'
    return f'<div class="ph">{icon("image", 26, 1.6)}<span>Image not found</span></div>'


hero_slot = st.empty()
tab_builder, tab_customer_view = st.tabs(["Build quotation", "Customer view"])

# ---------------- TAB 1: BUILD QUOTATION ----------------
with tab_builder:
    left, right = st.columns([1.72, 1], gap="large")

    with left:
        # ===== 01 · Users =====
        with st.container(key="card-users"):
            section_header("01", "Hosted user licences", "Ongoing monthly · 36-month minimum term")
            u1, u2 = st.columns([1.35, 1], gap="medium")
            with u1:
                feats = "".join(
                    f'<div class="nl-feat"><span class="ck">{icon("check", 12, 3)}</span>{esc(f)}</div>'
                    for f in LICENCE_FEATURES
                )
                render_html(
                    '<div class="nl-licence"><div class="top"><div>'
                    '<div class="name">Hosted Cloud User Licence</div>'
                    '<div class="sub">A complete unified-communications seat, enterprise features included.</div></div>'
                    f'<div class="nl-price">{money(LICENCE_MONTHLY_RATE)} <small>/ user / mo</small></div></div>'
                    f'<div class="nl-feats">{feats}</div>'
                    f'<div class="nl-activation">{icon("zap", 14)}<span>One-off activation &amp; provisioning:'
                    f' <b>{money(ACTIVATION_FEE_PER_USER)} per user</b>, billed in month 1</span></div></div>'
                )
            with u2:
                st.number_input("Number of users", min_value=0, max_value=500, step=1, key="num_licences")
                users = st.session_state.num_licences
                mrc = float(users) * LICENCE_MONTHLY_RATE
                act = float(users) * ACTIVATION_FEE_PER_USER
                render_html(
                    '<div class="nl-mini">'
                    f'<div><div class="l">Monthly</div><div class="v">{money(mrc)}</div><div class="s">{money(mrc * (1 + VAT_RATE))} inc VAT</div></div>'
                    f'<div><div class="l">Activation</div><div class="v">{money(act)}</div><div class="s">one-off, ex VAT</div></div>'
                    "</div>"
                )

        # ===== 02 · Hardware =====
        with st.container(key="card-hardware"):
            section_header("02", "Handsets, headsets & hardware", "Optional · one-off upfront · tap + to add")
            if hasattr(st, "segmented_control"):
                chosen = st.segmented_control("Category", CATEGORIES, default="All hardware",
                                              key="hw_cat", label_visibility="collapsed")
            else:
                chosen = st.radio("Category", CATEGORIES, horizontal=True, key="hw_cat", label_visibility="collapsed")
            chosen = chosen or "All hardware"
            shown = PRODUCTS if chosen == "All hardware" else [p for p in PRODUCTS if p.get("category") == chosen]

            per_row = 3
            for start in range(0, len(shown), per_row):
                cols = st.columns(per_row, gap="small")
                for col, product in zip(cols, shown[start:start + per_row]):
                    pid = product["id"]
                    qty = st.session_state.basket.get(pid, 0)
                    with col:
                        with st.container(key=f"prod-{'on' if qty else 'off'}-{pid}"):
                            render_html(
                                f'<div class="nl-prod-top">{chip(product.get("tag", "Hardware"), "accent")}'
                                f'<span class="nl-prod-price">{money(product["price"])}</span></div>'
                                f'<div class="nl-stage">{product_image_html(product)}</div>'
                                f'<div class="nl-prod-name">{esc(product["name"])}</div>'
                                f'<div class="nl-prod-desc">{esc(product["desc"])}</div>'
                            )
                            s1, s2, s3 = st.columns([1, 1.3, 1], gap="small")
                            with s1:
                                st.button("−", key=f"minus_{pid}", on_click=update_qty, args=(pid, -1),
                                          disabled=qty == 0, **FULL_WIDTH)
                            with s2:
                                render_html(f'<div class="nl-qty {"on" if qty else ""}">{qty}</div>')
                            with s3:
                                st.button("+", key=f"plus_{pid}", on_click=update_qty, args=(pid, 1), **FULL_WIDTH)
                            render_html(
                                f'<div class="nl-sub on">{money(qty * product["price"])} ex VAT</div>' if qty
                                else '<div class="nl-sub">Not in quote</div>'
                            )

        # ===== 03 · Details & PDF =====
        with st.container(key="card-details"):
            section_header("03", "Quote details & PDF", "Who it's from, who it's for, and where it's going")
            with st.form(key="telephony_quote_form", border=False):
                col_r, col_c = st.columns(2, gap="large")
                with col_r:
                    render_html(f'<div class="nl-form-h">{icon("building", 16)}Your company (service provider)</div>')
                    r_company = st.text_input("Company / reseller name *", placeholder="e.g. Acme Communications Ltd")
                    r_contact = st.text_input("Your name / account manager *", placeholder="e.g. John Doe")
                    r_email = st.text_input("Your email *", placeholder="e.g. sales@acmecomms.co.uk")
                    r_phone = st.text_input("Your phone", placeholder="e.g. 0330 123 4567")
                with col_c:
                    render_html(f'<div class="nl-form-h">{icon("user", 16)}Proposed customer</div>')
                    c_company = st.text_input("Customer company *", placeholder="e.g. Apex Logistics Ltd")
                    c_contact = st.text_input("Customer contact *", placeholder="e.g. Sarah Jenkins")
                    c_email = st.text_input("Customer email *", placeholder="e.g. sarah@apexlogistics.co.uk")
                    c_phone = st.text_input("Customer phone", placeholder="e.g. 0161 123 4567")
                render_html(f'<div class="nl-form-h" style="margin-top:10px">{icon("truck", 16)}Delivery / site address'
                            ' <span style="color:var(--faint);font-weight:500">(optional for initial quotes)</span></div>')
                d1, d2, d3 = st.columns([2, 1, 1])
                with d1:
                    del_addr1 = st.text_input("Address line 1", placeholder="Building name or street")
                with d2:
                    del_city = st.text_input("Town / city", placeholder="Town / city")
                with d3:
                    del_postcode = st.text_input("Postcode", placeholder="Postcode")
                generate_submitted = st.form_submit_button("Save quotation & generate PDF", type="primary", **FULL_WIDTH)

            if generate_submitted:
                current_h_items = basket_items()
                if not r_company or not r_contact or not r_email:
                    st.error("Please complete your service provider details (company, name and email).")
                elif not c_company or not c_contact or not c_email:
                    st.error("Please fill in the customer's company, contact name and email.")
                elif st.session_state.num_licences == 0 and not current_h_items:
                    st.error("Add at least one user licence or a piece of hardware before generating a quote.")
                else:
                    quote_ref = f"NL-{datetime.now().strftime('%y%m%d%H%M')}"
                    quote_date = datetime.now().strftime("%d %B %Y")
                    addr_parts = [p.strip() for p in [del_addr1, del_city, del_postcode] if p.strip()]
                    full_delivery = ", ".join(addr_parts) if addr_parts else "N/A"
                    reseller_info = {"company": r_company, "name": r_contact, "email": r_email, "phone": r_phone}
                    customer_info = {"company": c_company, "name": c_contact, "email": c_email, "phone": c_phone,
                                     "delivery": full_delivery}
                    quote_meta = {"ref": quote_ref, "date": quote_date}

                    pdf_bytes = generate_quotation_pdf(quote_meta, reseller_info, customer_info,
                                                       st.session_state.num_licences, current_h_items)
                    st.session_state.active_quote_pdf = pdf_bytes
                    st.session_state.active_quote_ref = quote_ref
                    st.session_state.active_quote_sig = quote_signature()
                    st.session_state.active_quote_customer = c_company

                    hw_summary = ("; ".join(f"{i['name']} x{i['qty']}" for i in current_h_items)
                                  if current_h_items else "No Hardware (App/Licences Only)")
                    one_off_combined = total_activation_fee() + total_hardware_capex()
                    record = {
                        "Quote Ref": [quote_ref], "Date": [quote_date], "Brand": ["Novalink Telephony"],
                        "Reseller": [r_company], "Customer Company": [c_company], "Customer Contact": [c_contact],
                        "Customer Email": [c_email], "Licences": [st.session_state.num_licences],
                        "Ongoing Monthly Costs Ex VAT (£)": [f"{total_monthly_licences():.2f}"],
                        "Ongoing Monthly Costs Inc VAT (£)": [f"{total_monthly_licences() * (1 + VAT_RATE):.2f}"],
                        "Activation Fee Ex VAT (£)": [f"{total_activation_fee():.2f}"],
                        "Hardware Total Ex VAT (£)": [f"{total_hardware_capex():.2f}"],
                        "Total One-Off Costs Ex VAT (£)": [f"{one_off_combined:.2f}"],
                        "Total One-Off Costs Inc VAT (£)": [f"{one_off_combined * (1 + VAT_RATE):.2f}"],
                        "Hardware Summary": [hw_summary], "Delivery Address": [full_delivery],
                    }
                    df = pd.DataFrame(record)
                    if not os.path.isfile("quotes.csv"):
                        df.to_csv("quotes.csv", index=False)
                    else:
                        df.to_csv("quotes.csv", mode="a", header=False, index=False)
                    st.success(f"Quotation {quote_ref} generated for {c_company}.")

            if "active_quote_pdf" in st.session_state:
                if st.session_state.get("active_quote_sig") != quote_signature():
                    st.warning("The quote has changed since this PDF was made. Generate it again to include the changes.")
                st.download_button(
                    label=f"Download {st.session_state.active_quote_ref}.pdf",
                    data=st.session_state.active_quote_pdf,
                    file_name=f"{st.session_state.active_quote_ref}.pdf",
                    mime="application/pdf",
                    key="dl_main",
                    **FULL_WIDTH,
                )

    # ===== Live quote summary (sticky) =====
    with right:
        with st.container(key="card-summary"):
            users = st.session_state.num_licences
            mrc_ex = total_monthly_licences()
            one_off_ex = total_activation_fee() + total_hardware_capex()
            month1_ex = mrc_ex + one_off_ex
            render_html(
                '<div class="nl-sum-h"><div class="t">Live quote</div><span class="nl-live">Updating</span></div>'
                f'<div class="nl-total"><div class="l">Ongoing monthly</div><div class="v">{money(mrc_ex)} <small>/ mo ex VAT</small></div>'
                f'<div class="i">{money(mrc_ex * (1 + VAT_RATE))} / mo inc VAT</div></div>'
                f'<div class="nl-total"><div class="l">One-off upfront</div><div class="v">{money(one_off_ex)} <small>ex VAT</small></div>'
                f'<div class="i">{money(one_off_ex * (1 + VAT_RATE))} inc VAT</div></div>'
                f'<div class="nl-total hero"><div class="l">Month 1 investment</div><div class="v">{money(month1_ex)}</div>'
                f'<div class="i">{money(month1_ex * (1 + VAT_RATE))} inc VAT</div></div>'
                '<div class="nl-lines-h">In this quote</div>'
            )
            items = basket_items()
            if users == 0 and not items:
                render_html('<div class="nl-empty">Nothing added yet. Set the number of users to get started.</div>')
            if users > 0:
                render_html(
                    f'<div class="nl-line"><span class="n">Cloud user licence<small>× {users}</small></span>'
                    f'<span class="p">{money(mrc_ex)}/mo</span></div>'
                    f'<div class="nl-line"><span class="n">Activation &amp; setup<small>× {users}</small></span>'
                    f'<span class="p">{money(total_activation_fee())}</span></div>'
                )
            for item in items:
                with st.container(key=f"sumline-{item['id']}"):
                    try:
                        l1, l2 = st.columns([6, 1], vertical_alignment="center", gap="small")
                    except TypeError:
                        l1, l2 = st.columns([6, 1], gap="small")
                    with l1:
                        render_html(
                            f'<div class="nl-line nb"><span class="n">{esc(item["name"])}<small>× {item["qty"]}</small></span>'
                            f'<span class="p">{money(item["line_total"])}</span></div>'
                        )
                    with l2:
                        st.button("✕", key=f"del_{item['id']}", on_click=remove_from_basket, args=(item["id"],),
                                  help=f"Remove {item['name']}")
            render_html(
                f'<div class="nl-term">{icon("alert", 14)}<span>Licences are on a <b>36-month minimum term</b>.'
                ' Early termination charges apply. Quote valid for 30 days.</span></div>'
            )
            if "active_quote_pdf" in st.session_state and st.session_state.get("active_quote_sig") == quote_signature():
                st.download_button(
                    label=f"Download {st.session_state.active_quote_ref}.pdf",
                    data=st.session_state.active_quote_pdf,
                    file_name=f"{st.session_state.active_quote_ref}.pdf",
                    mime="application/pdf",
                    type="primary",
                    key="dl_side",
                    **FULL_WIDTH,
                )
            else:
                st.caption("Fill in step 03 to generate the official PDF.")

# ---------------- TAB 2: CUSTOMER VIEW ----------------
with tab_customer_view:
    users = st.session_state.get("num_licences", 0)
    mrc_ex = total_monthly_licences()
    mrc_vat = mrc_ex * VAT_RATE
    act_ex = total_activation_fee()
    hw_ex = total_hardware_capex()
    one_off_ex = act_ex + hw_ex
    one_off_vat = one_off_ex * VAT_RATE
    month1_ex = mrc_ex + one_off_ex
    items = basket_items()
    for_whom = st.session_state.get("active_quote_customer")

    _, mid, _ = st.columns([0.06, 1, 0.06])
    with mid:
        with st.container(key="card-cv-head"):
            render_html(
                '<div class="nl-prop"><div>'
                '<div class="k">Proposal' + (f" · prepared for {esc(for_whom)}" if for_whom else "") + '</div>'
                '<div class="t">Your cloud <span>telephony solution</span></div>'
                '<div class="s">Unified communications for every user, on desk, laptop and mobile.</div></div>'
                f'<div>{chip(datetime.now().strftime("%d %B %Y"), "accent")}</div></div>'
                '<div class="nl-kpis">'
                f'<div class="nl-kpi" style="--c:#7C83FF"><div class="l">Ongoing monthly</div><div class="v">{money(mrc_ex)} <small>ex VAT</small></div><div class="i">{money(mrc_ex + mrc_vat)} / mo inc VAT</div></div>'
                f'<div class="nl-kpi" style="--c:#38D6F5"><div class="l">One-off upfront</div><div class="v">{money(one_off_ex)} <small>ex VAT</small></div><div class="i">{money(one_off_ex + one_off_vat)} inc VAT</div></div>'
                f'<div class="nl-kpi" style="--c:#34D399"><div class="l">Month 1 investment</div><div class="v">{money(month1_ex)} <small>ex VAT</small></div><div class="i">{money(month1_ex * (1 + VAT_RATE))} inc VAT</div></div>'
                "</div>"
            )

        with st.container(key="card-cv-monthly"):
            section_header("1", "Ongoing monthly costs", "Per user, per month · 36-month minimum term")
            if users > 0:
                render_html(
                    '<table class="nl-table"><thead><tr><th>Service</th><th class="num">Users</th>'
                    '<th class="num">Unit (ex VAT)</th><th class="num">Monthly (ex VAT)</th></tr></thead><tbody>'
                    '<tr><td><b>Hosted VoIP cloud user licence</b><div class="desc">Apps, softphone, call recording,'
                    ' auto-attendant &amp; inclusive UK calls</div></td>'
                    f'<td class="num">{users}</td><td class="num">{money(LICENCE_MONTHLY_RATE)}</td><td class="num"><b>{money(mrc_ex)}</b></td></tr>'
                    f'<tr class="sub"><td colspan="3">Subtotal (ex VAT)</td><td class="num">{money(mrc_ex)}</td></tr>'
                    f'<tr class="sub"><td colspan="3">VAT @ 20%</td><td class="num">{money(mrc_vat)}</td></tr>'
                    f'<tr class="grand"><td colspan="3">Total monthly (inc VAT)</td><td class="num">{money(mrc_ex + mrc_vat)} / mo</td></tr>'
                    "</tbody></table>"
                )
            else:
                render_html('<div class="nl-empty">No user licences selected yet.</div>')

        with st.container(key="card-cv-oneoff"):
            section_header("2", "One-off upfront costs", "Activation and hardware, billed once")
            rows = (
                '<tr><td><div style="display:flex;gap:12px;align-items:center"><div class="thumb">'
                f'<span style="color:#7C83FF">{icon("zap", 18)}</span></div><div><b>User setup &amp; activation</b>'
                '<div class="desc">Provisioning, portal setup and licence deployment</div></div></div></td>'
                f'<td class="num">{users}</td><td class="num">{money(ACTIVATION_FEE_PER_USER)}</td><td class="num"><b>{money(act_ex)}</b></td></tr>'
            )
            for item in items:
                uri = get_base64_image(item.get("image"))
                thumb = f'<img src="{uri}" alt="">' if uri else f'<span style="color:#94A3B8">{icon("phone", 18)}</span>'
                rows += (
                    f'<tr><td><div style="display:flex;gap:12px;align-items:center"><div class="thumb">{thumb}</div>'
                    f'<div><b>{esc(item["name"])}</b><div class="desc">{esc(item.get("tag", ""))} · {esc(item["desc"])}</div></div></div></td>'
                    f'<td class="num">{item["qty"]}</td><td class="num">{money(item["price"])}</td>'
                    f'<td class="num"><b>{money(item["line_total"])}</b></td></tr>'
                )
            render_html(
                '<table class="nl-table"><thead><tr><th>Item</th><th class="num">Qty</th>'
                '<th class="num">Unit (ex VAT)</th><th class="num">Total (ex VAT)</th></tr></thead><tbody>'
                + rows
                + f'<tr class="sub"><td colspan="3">Subtotal (ex VAT)</td><td class="num">{money(one_off_ex)}</td></tr>'
                f'<tr class="sub"><td colspan="3">VAT @ 20%</td><td class="num">{money(one_off_vat)}</td></tr>'
                f'<tr class="grand"><td colspan="3">Total one-off (inc VAT)</td><td class="num">{money(one_off_ex + one_off_vat)}</td></tr>'
                "</tbody></table>"
                '<div class="nl-note"><b>Commercial notes:</b> Quotation valid for 30 calendar days.'
                ' User licences are subject to a 36-month minimum term.</div>'
            )

# ---------------- Hero (rendered last so the stepper reflects this run) ----------------
if st.session_state.get("num_licences", 0) == 0 and not st.session_state.basket:
    _step = 1
elif "active_quote_pdf" in st.session_state and st.session_state.get("active_quote_sig") == quote_signature():
    _step = 5
elif st.session_state.basket:
    _step = 3
else:
    _step = 2
render_html(hero_html(_step), target=hero_slot)
