import base64
from datetime import datetime
import hmac
import html as html_lib
import inspect
import io
import json
import os

import math

import pandas as pd
import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.utils import ImageReader
from reportlab.platypus import HRFlowable, Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

# #####################################################################
# #####################################################################
#
#   NOVALINK PRICE BOOK  -  YOUR WHOLESALE PRICES LIVE HERE
#
#   To change a price: edit the number, save, commit to GitHub.
#   The app updates itself within a minute or so. Every screen, the
#   customer quote PDF, the Novalink partner order and the profit
#   page all read from these values - nothing else needs touching.
#
#   Rules:  - numbers only, no £ sign or commas   (e.g. 9.50  not £9.50)
#           - keep the full stop for pence          (e.g. 4.00)
#           - don't delete the commas at the ends of lines inside [ ] or { }
#
#   Existing PDFs already sent out are NOT changed - only new quotes.
#   If a floor goes UP above a reseller's saved sell price, their sell
#   price is automatically lifted to the new floor.
#
# #####################################################################

# ---- Hosted user licences ------------------------------------------
LICENCE_COST_PER_USER_MONTH = 8.00     # what the reseller pays you, per user per month (their minimum sell price)

# ---- One-off charges -----------------------------------------------
SETUP_COST_PER_USER = 3.00             # user setup & provisioning, per user (their minimum sell price)
BASIC_BUILD_COST = 55.00               # "Basic system build" - flat fee (their minimum sell price)

# ---- Advanced system deployment (fixed - resellers can't change it) --
ADVANCED_DEPLOYMENT_TIERS = [
    # (up to this many users, price)
    (5, 250.00),                        # 1-5 users
    (10, 500.00),                       # 6-10 users
]
ADVANCED_PRICE_PER_EXTRA_BAND = 750.00  # above the last tier: this price per band...
ADVANCED_EXTRA_BAND_SIZE = 10           # ...of this many users (11-20 = £750, 21-30 = £1,500 ...)

# ---- Hardware (price per unit) -------------------------------------
# These override any other hardware price in the app. A product not
# listed here keeps its existing price.
HARDWARE_PRICES = {
    "v67": 342.00,        # Fanvil Executive V67
    "v66pro": 198.00,     # Fanvil Premium V66 Pro
    "v62pro": 98.00,      # Fanvil Essential V62 Pro
    "w620w": 149.00,      # Linkvil Rugged W620W
    "t73w": 78.00,        # Yealink T73W
    "t74w": 115.00,       # Yealink T74W
    "t85w": 125.00,       # Yealink T85W
    "t87w": 165.00,       # Yealink T87W
    "t88w_pro": 235.00,   # Yealink T88W Pro
    "w74p": 87.00,        # Yealink W74P
    "ax83h": 95.00,       # Yealink AX83H
    "ax86r": 119.00,      # Yealink AX86R
    "uh36_mono": 42.00,   # Yealink UH36 Mono Headset UC
    "psu_10w": 14.00,     # Yealink 10W PSU
}

# ---- Terms ---------------------------------------------------------
VAT_RATE = 0.20                         # 0.20 = 20%
CONTRACT_MONTHS = 36                    # minimum term shown on every quote & used for profit maths
QUOTE_VALID_DAYS = 30                   # "Quotation valid for ... days"

# #####################################################################
#   END OF PRICE BOOK - you shouldn't need to edit anything below here
# #####################################################################
VAT_PCT = f"{VAT_RATE * 100:g}%"


# ==========================================
# 1. PAGE CONFIGURATION & BRAND
# ==========================================
# All files are found next to app.py, so the app works even when it lives in a
# sub-folder of the repo (Streamlit Cloud runs from the repo root).
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def asset(path):
    """Absolute path for a file stored alongside app.py (falls back to the repo root)."""
    if not path or os.path.isabs(path):
        return path
    here = os.path.join(BASE_DIR, path)
    return here if os.path.exists(here) or not os.path.exists(path) else path


BRAND_ICON_FILE = "refynit_icon.png"      # orange hexagon "R" (favicon / login)
BRAND_LOGO_FILE = "refynit_logo.png"      # light wordmark for the dark app
BRAND_LOGO_PDF_FILE = "refynit_logo_dark.png"  # dark wordmark for the white PDF

st.set_page_config(
    page_title="Refyn-IT Telecoms · Quotation",
    page_icon=asset(BRAND_ICON_FILE) if os.path.exists(asset(BRAND_ICON_FILE)) else "📞",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_NAME = "Refyn-IT Telecoms"
APP_TAGLINE = "Telephony quotation"
POWERED_BY = "Novalink"
QUOTE_PREFIX = "RIT"

# ==========================================
# 2. DESIGN SYSTEM (shared with Prospect Engine)
# ==========================================
APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --bg: #0B0C10;
  --surface: #14161C;
  --surface-2: #1A1D24;
  --surface-3: #232730;
  --border: rgba(212, 217, 223, 0.11);
  --border-strong: rgba(212, 217, 223, 0.22);
  --text: #EEF0F3;
  --muted: #9CA3AE;
  --faint: #646B76;
  --accent: #EA5624;
  --accent-2: #FF9A5A;
  --accent-soft: rgba(234, 86, 36, 0.14);
  --good: #34D399;
  --warn: #FBBF24;
  --risk: #FB923C;
  --bad: #F87171;
  --radius: 14px;
  --grad: linear-gradient(135deg, #EA5624 0%, #FF9A5A 100%);
}

html, body, [class*="css"], .stApp, button, input, textarea, select {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}
.stApp {
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(255, 154, 90, 0.07), transparent 60%),
    radial-gradient(900px 500px at 10% -20%, rgba(234, 86, 36, 0.10), transparent 60%),
    var(--bg);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display: none; }
footer { visibility: hidden; }
.block-container { padding-top: 1.6rem !important; padding-bottom: 3rem !important; max-width: 1500px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #101217 0%, #0B0C10 100%);
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
  background: linear-gradient(180deg, rgba(28, 31, 38, 0.88) 0%, rgba(20, 22, 28, 0.88) 100%);
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
  background: var(--grad) !important; border: none !important; color: #0B0C10 !important;
  box-shadow: 0 8px 24px -10px rgba(234, 86, 36, 0.8);
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  filter: brightness(1.08); color: #0B0C10 !important;
}
.stButton > button[kind="primary"] p, [data-testid="stBaseButton-primary"] p, .stFormSubmitButton > button p { color: #0B0C10 !important; font-weight: 700 !important; }

.stLinkButton a, [data-testid^="stBaseLinkButton"] {
  border-radius: 10px !important; font-weight: 700 !important; padding: 0.55rem 1.1rem !important;
}
[data-testid="stBaseLinkButton-primary"], .stLinkButton a[kind="primary"] {
  background: var(--grad) !important; border: none !important; color: #0B0C10 !important;
  box-shadow: 0 8px 24px -10px rgba(234, 86, 36, 0.8);
}
[data-testid="stBaseLinkButton-primary"] p, .stLinkButton a[kind="primary"] p { color: #0B0C10 !important; font-weight: 700 !important; }
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
.pe-step.active .num { background: var(--grad); border: none; color: #0B0C10; }
.pe-step-sep { width: 14px; height: 1px; background: var(--border-strong); }

.pe-section { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.pe-section .badge { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center;
  background: var(--accent-soft); color: var(--accent); font-weight: 800; font-size: 0.85rem; border: 1px solid rgba(234,86,36,.3); }
.pe-section .t { font-size: 1.08rem; font-weight: 700; color: var(--text); line-height: 1.2; }
.pe-section .s { font-size: 0.82rem; color: var(--muted); margin-top: 2px; }

.pe-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.pe-chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 0.76rem;
  font-weight: 600; background: var(--surface-3); color: var(--text); border: 1px solid var(--border); white-space: nowrap; }
.pe-chip.accent { background: var(--accent-soft); color: #FFB38F; border-color: rgba(234,86,36,.3); }
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
  border: 1px solid rgba(234,86,36,.35); border-radius: 12px; padding: 12px 14px; margin: 14px 0 10px 0; }
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
  background: var(--grad); color: #0B0C10; flex-shrink: 0; }
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

.pe-hook { background: linear-gradient(135deg, rgba(234,86,36,.12), rgba(255,154,90,.06)); border: 1px solid rgba(234,86,36,.28);
  border-radius: 12px; padding: 14px 16px; }
.pe-hook .h { font-size: 0.7rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #FFB38F; }
.pe-hook .t { font-weight: 700; color: var(--text); margin: 4px 0 10px 0; }
.pe-hook ul { margin: 0; padding-left: 0; list-style: none; }
.pe-hook li { font-size: 0.85rem; color: var(--text); padding: 4px 0 4px 24px; position: relative; }
.pe-hook li::before { content: ""; position: absolute; left: 4px; top: 10px; width: 8px; height: 8px; border-radius: 50%; background: var(--grad); }

/* Sidebar components */
.pe-brand { display: flex; align-items: center; gap: 12px; padding: 4px 0 18px 0; border-bottom: 1px solid var(--border); margin-bottom: 16px; }
.pe-logo { width: 40px; height: 40px; border-radius: 12px; background: var(--grad); display: grid; place-items: center; color: #0B0C10;
  box-shadow: 0 10px 24px -10px rgba(234,86,36,.9); }
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

/* ---------- Refyn-IT brand ---------- */
.rit-brandrow { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; }
.rit-logo { display: block; width: auto; }
.rit-logo-text { font-weight: 800; font-style: italic; font-size: 1.6rem; letter-spacing: .02em; color: #D4D9DF; }
.rit-logo-text span { color: var(--accent); }
.rit-powered { display: inline-flex; align-items: center; gap: 8px; font-size: 0.74rem; font-weight: 600; color: var(--muted);
  background: var(--surface); border: 1px solid var(--border); border-radius: 999px; padding: 5px 12px 5px 5px; white-space: nowrap; }
.rit-powered .pb { background: var(--grad); color: #0B0C10; font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
  font-size: 0.66rem; padding: 3px 9px; border-radius: 999px; }
.rit-powered b { color: var(--text); font-weight: 700; }
.rit-powered .sep { display: none; }
.rit-login-logo { display: flex; justify-content: center; margin-bottom: 18px; }
.pe-login-head .s .rit-powered { margin: 6px 0 4px 0; }
.pe-title { font-style: italic; }
.pe-title span { padding-right: 4px; }
.pe-section .badge { font-style: italic; }
</style>
"""

NOVALINK_CSS = """
<style>
/* Hide Streamlit chrome for a clean, customer-facing look */
#MainMenu {visibility: hidden;}
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {display: none;}
.block-container { max-width: 1440px; }

.st-key-card-users, .st-key-card-hardware, .st-key-card-details, .st-key-card-summary,
.st-key-card-cv-head, .st-key-card-cv-monthly, .st-key-card-cv-oneoff, .st-key-card-deploy,
.st-key-card-admin, .st-key-card-admin-login, .st-key-card-cv-setup, .st-key-card-admin-tariff, .st-key-card-admin-profit, .st-key-card-admin-order {
  background: linear-gradient(180deg, rgba(28, 31, 38, 0.88) 0%, rgba(20, 22, 28, 0.88) 100%);
  border: 1px solid var(--border) !important;
  border-radius: var(--radius);
  padding: 22px 22px 18px 22px;
  box-shadow: 0 1px 0 rgba(255,255,255,0.03) inset, 0 20px 40px -24px rgba(0,0,0,0.6);
  margin-bottom: 18px;
}
.st-key-card-summary { border-color: rgba(234,86,36,.35) !important; }
[data-testid="stColumn"]:has(.st-key-card-summary), [data-testid="column"]:has(.st-key-card-summary) {
  position: sticky; top: 1rem; align-self: flex-start; }

/* Licence feature panel */
.nl-licence { position: relative; border-radius: 14px; padding: 20px; overflow: hidden;
  background: linear-gradient(135deg, rgba(234,86,36,.16), rgba(255,154,90,.07));
  border: 1px solid rgba(234,86,36,.35); }
.nl-licence .top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.nl-licence .name { font-size: 1.15rem; font-weight: 800; color: var(--text); letter-spacing: -0.02em; }
.nl-licence .sub { font-size: 0.82rem; color: var(--muted); margin-top: 4px; }
.nl-price { background: var(--grad); color: #0B0C10; font-weight: 800; font-size: 0.9rem; padding: 6px 12px;
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
[class*="st-key-prod-"]:hover { border-color: rgba(234,86,36,.45) !important; transform: translateY(-2px);
  box-shadow: 0 16px 30px -20px rgba(0,0,0,.8); }
[class*="st-key-prod-on-"] { border-color: rgba(255,154,90,.55) !important; box-shadow: 0 0 0 1px rgba(255,154,90,.25), 0 16px 30px -20px rgba(255,154,90,.35); }
.nl-prod-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.nl-prod-price { font-weight: 800; font-size: 1.05rem; color: var(--text); letter-spacing: -0.02em; }
.nl-stage { height: 140px; margin: 12px 0 10px 0; border-radius: 12px; display: grid; place-items: center; overflow: hidden;
  background: radial-gradient(120% 90% at 50% 20%, #FFFFFF 0%, #EEF0F3 70%, #E2E5EA 100%); }
.nl-stage img { max-height: 124px; max-width: 88%; object-fit: contain; filter: drop-shadow(0 8px 10px rgba(15,23,42,.18)); }
.nl-stage .ph { color: #94A3B8; display: grid; place-items: center; gap: 6px; font-size: 0.72rem; }
.nl-prod-name { font-weight: 700; font-size: 0.92rem; color: var(--text); line-height: 1.25; min-height: 2.4em; }
.nl-prod-desc { font-size: 0.74rem; color: var(--muted); line-height: 1.35; margin-top: 4px; min-height: 3.1em;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.nl-qty { text-align: center; font-weight: 800; font-size: 1.05rem; color: var(--text); background: var(--surface-2);
  border: 1px solid var(--border-strong); border-radius: 10px; padding: 7px 0; }
.nl-qty.on { border-color: rgba(255,154,90,.6); color: var(--accent-2); }
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
.nl-total.hero { background: linear-gradient(135deg, rgba(234,86,36,.18), rgba(255,154,90,.08)); border-color: rgba(234,86,36,.4); }
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
.nl-table .thumb { width: 44px; height: 44px; border-radius: 10px; background: #F1F2F4; display: grid; place-items: center; overflow: hidden; }
.nl-table .thumb img { max-width: 38px; max-height: 38px; object-fit: contain; }
.nl-table tr.sub td { border-bottom: none; padding-top: 8px; padding-bottom: 4px; color: var(--muted); }
.nl-table tr.grand td { border-top: 1px solid var(--border-strong); font-weight: 800; font-size: 1rem; padding-top: 12px; }
.nl-table tr.grand td.num { background: var(--grad) !important; -webkit-background-clip: text !important; background-clip: text !important; color: transparent; }
.nl-note { margin-top: 14px; font-size: 0.82rem; color: var(--muted); border: 1px dashed var(--border-strong); border-radius: 12px; padding: 12px 14px; }

/* Deployment option cards */
[class*="st-key-dep-"] { background: var(--surface); border: 1px solid var(--border) !important; border-radius: 14px;
  padding: 16px 16px 14px 16px; height: 100%; transition: border-color .15s ease, box-shadow .15s ease; }
[class*="st-key-dep-off-"]:hover { border-color: rgba(234,86,36,.45) !important; }
[class*="st-key-dep-on-"] { border-color: rgba(234,86,36,.7) !important;
  background: linear-gradient(135deg, rgba(234,86,36,.14), rgba(255,154,90,.05)) !important;
  box-shadow: 0 0 0 1px rgba(234,86,36,.3), 0 16px 30px -20px rgba(234,86,36,.45); }
.rit-dep-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.rit-dep-name { font-weight: 800; font-size: 1rem; color: var(--text); letter-spacing: -0.01em; }
.rit-dep-price { font-weight: 800; font-size: 1.15rem; color: var(--text); white-space: nowrap; }
[class*="st-key-dep-on-"] .rit-dep-price { color: var(--accent-2); }
.rit-dep-desc { font-size: 0.8rem; color: var(--muted); margin-top: 6px; line-height: 1.4; min-height: 2.3em; }
[class*="st-key-dep-on-"] .stButton > button:disabled { background: var(--grad) !important; color: #0B0C10 !important; opacity: 1 !important; border: none !important; }
[class*="st-key-dep-on-"] .stButton > button:disabled p { color: #0B0C10 !important; font-weight: 700 !important; }

/* Admin */
.rit-admin-h { font-size: 0.7rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--accent-2);
  margin: 14px 0 6px 0; padding-top: 12px; border-top: 1px solid var(--border); }
.rit-floor { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: var(--muted); background: var(--surface);
  border: 1px dashed var(--border-strong); border-radius: 10px; padding: 10px 12px; margin-bottom: 16px; }
.rit-floor svg { color: var(--accent); flex-shrink: 0; }
.rit-admin-note { font-size: 0.84rem; color: var(--muted); margin-bottom: 8px; }
.st-key-card-admin-login { margin-top: 6vh; }
.rit-admin-bar { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: var(--muted); padding: 9px 0; }
.rit-admin-bar svg { color: var(--accent); }
.rit-deal { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; font-size: 0.9rem; color: var(--text); }
.rit-deal span:last-child { color: var(--muted); font-size: 0.82rem; }
.rit-pkpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }
@media (max-width: 1100px) { .rit-pkpis { grid-template-columns: 1fr 1fr; } }
.rit-hero-kpi { background: linear-gradient(135deg, rgba(52,211,153,.12), rgba(52,211,153,.03)) !important; border-color: rgba(52,211,153,.35) !important; }
.rit-hero-kpi .v { color: var(--good) !important; }
.rit-p.pos { color: var(--good); font-weight: 700; }
.rit-p.zero { color: var(--faint); }
.nl-table tr.grp td { font-size: 0.68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--accent-2);
  padding: 14px 12px 6px 12px; border-bottom: 1px solid var(--border); }

/* Build sheet */
.st-key-card-deploy [data-testid="stExpander"] { margin-top: 16px; }
.st-key-card-deploy [data-testid="stExpander"] summary p { color: var(--text) !important; font-weight: 700 !important; }
.st-key-card-deploy [data-testid="stExpander"] details { border-color: rgba(234,86,36,.35) !important; }
.rit-bs-intro { font-size: 0.82rem; color: var(--muted); margin-bottom: 6px; line-height: 1.45; }
.rit-bs-read { display: flex; align-items: flex-start; gap: 8px; font-size: 0.84rem; color: var(--text); background: var(--surface-2);
  border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px; margin: 2px 0 12px 0; }
.rit-bs-read svg { color: var(--good); flex-shrink: 0; margin-top: 2px; }
.rit-bs-status { margin: 14px 0 10px 0; padding-top: 12px; border-top: 1px solid var(--border); }
.rit-bs-status .h { font-size: 0.72rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; color: var(--accent-2); margin-bottom: 8px; }
.rit-cv-setup { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (max-width: 900px) { .rit-cv-setup { grid-template-columns: 1fr; } }
.rit-cv-setup .big { font-size: 1.05rem; font-weight: 800; color: var(--text); }
.rit-cv-setup .sm { font-size: 0.8rem; color: var(--muted); margin-top: 4px; line-height: 1.45; }
.rit-cv-opt { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-top: 1px solid var(--border); font-size: 0.86rem; }
.rit-cv-opt .key { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; font-weight: 800;
  background: var(--grad); color: #0B0C10; flex-shrink: 0; }
.rit-cv-opt .o { font-weight: 700; color: var(--text); min-width: 110px; }
.rit-cv-opt .w { color: var(--muted); }
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


@st.cache_data
def brand_img_uri(path):
    path = asset(path)
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("utf-8")
    return None


def brand_logo_html(height=34, cls="rit-logo") -> str:
    uri = brand_img_uri(BRAND_LOGO_FILE)
    if uri:
        return f'<img class="{cls}" src="{uri}" alt="Refyn-IT" style="height:{height}px">'
    return f'<span class="{cls}-text">REFYN<span>IT</span></span>'


def powered_by_html() -> str:
    return f'<span class="rit-powered"><span class="pb">Telecoms</span><span class="sep"></span>powered by <b>{POWERED_BY}</b></span>'


def hero_html(active_step: int) -> str:
    steps = ["Users", "Deployment", "Hardware", "Details"]
    parts = []
    for i, label in enumerate(steps, start=1):
        state = "done" if i < active_step else "active" if i == active_step else ""
        num = icon("check", 12, 3) if state == "done" else str(i)
        parts.append(f'<div class="pe-step {state}"><span class="num">{num}</span>{label}</div>')
    stepper = '<div class="pe-step-sep"></div>'.join(parts)
    return (
        '<div class="pe-hero"><div>'
        f'<div class="rit-brandrow">{brand_logo_html(40)}{powered_by_html()}</div>'
        f'<div class="pe-eyebrow"><span class="dot"></span>Hosted cloud telephony · {esc(datetime.now().strftime("%d %B %Y"))}</div>'
        '<div class="pe-title">Telephony, <span>refined.</span></div>'
        '<div class="pe-sub">Combine cloud user licences, deployment and desk, cordless and headset hardware.'
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
            f'<div class="pe-login-head"><div class="rit-login-logo">{brand_logo_html(46)}</div>'
            f'<div class="t">Telecoms quotation portal</div>'
            f'<div class="s">{powered_by_html()}</div>'
            '<div class="s">Authorised Refyn-IT staff only. Enter your access key to continue.</div></div>'
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
    image_path = asset(image_path)
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
CATALOGUE_FILE = asset("catalogue.json")

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


def _apply_price_book(products):
    out = []
    for p in products:
        p = dict(p)
        if p.get("id") in HARDWARE_PRICES:
            p["price"] = float(HARDWARE_PRICES[p["id"]])
        out.append(p)
    return out


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
                return _apply_price_book(products)
        except (json.JSONDecodeError, OSError):
            pass
    return _apply_price_book(_FALLBACK_PRODUCTS)


PRODUCTS = load_products()

# ==========================================
# 6. RESELLER PRICING (floors set by Novalink, sell prices set by Refyn-IT)
# ==========================================
# Floors are Novalink's price to the reseller. The admin panel can only raise
# these, never go below them - enforced here, whatever the saved file says.
FLOOR_LICENCE_MONTHLY = float(LICENCE_COST_PER_USER_MONTH)   # set in the PRICE BOOK at the top
FLOOR_SETUP_PER_USER = float(SETUP_COST_PER_USER)
FLOOR_BASIC_DEPLOYMENT = float(BASIC_BUILD_COST)

DEPLOY_BASIC = "basic"
DEPLOY_ADVANCED = "advanced"
DEPLOYMENT_LABELS = {
    DEPLOY_BASIC: "Basic system build",
    DEPLOY_ADVANCED: "Advanced system deployment",
}
DEPLOYMENT_DESCS = {
    DEPLOY_BASIC: "Device activation & remote configuration · customer self-installation",
    DEPLOY_ADVANCED: "Fully managed deployment · system design, build, installation & go-live support",
}

SETTINGS_NAME = "pricing_settings.json"
SETTINGS_FILE = os.path.join(BASE_DIR, SETTINGS_NAME)
QUOTES_FILE = os.path.join(BASE_DIR, "quotes.csv")
DEFAULT_SETTINGS = {
    "licence_monthly": FLOOR_LICENCE_MONTHLY,
    "setup_per_user": FLOOR_SETUP_PER_USER,
    "basic_deployment": FLOOR_BASIC_DEPLOYMENT,
    "default_deployment": DEPLOY_BASIC,
    "company_name": "Refyn-IT",
    "company_email": "",
    "company_phone": "",
    "updated": "",
}


def advanced_deployment_price(users: int) -> float:
    """Locked Novalink tariff (not editable by the reseller).
    Tiers and band pricing are set in the PRICE BOOK at the top of this file."""
    users = int(users or 0)
    if users <= 0:
        return 0.0
    for cap, price in ADVANCED_DEPLOYMENT_TIERS:
        if users <= cap:
            return float(price)
    last_cap = ADVANCED_DEPLOYMENT_TIERS[-1][0]
    return float(ADVANCED_PRICE_PER_EXTRA_BAND) * math.ceil((users - last_cap) / ADVANCED_EXTRA_BAND_SIZE)


def sanitise_settings(raw: dict) -> dict:
    s = {**DEFAULT_SETTINGS, **(raw or {})}

    def num(key, floor):
        try:
            v = float(s.get(key, floor))
        except (TypeError, ValueError):
            v = floor
        return round(max(floor, v), 2)

    s["licence_monthly"] = num("licence_monthly", FLOOR_LICENCE_MONTHLY)
    s["setup_per_user"] = num("setup_per_user", FLOOR_SETUP_PER_USER)
    s["basic_deployment"] = num("basic_deployment", FLOOR_BASIC_DEPLOYMENT)
    if s.get("default_deployment") not in DEPLOYMENT_LABELS:
        s["default_deployment"] = DEPLOY_BASIC
    for k in ("company_name", "company_email", "company_phone", "updated"):
        s[k] = str(s.get(k) or "")
    return {k: s[k] for k in DEFAULT_SETTINGS}


# ---- Persistence -------------------------------------------------------
# Streamlit Community Cloud wipes local files when the app reboots or sleeps,
# so if GITHUB_TOKEN + GITHUB_REPO are in Secrets, settings are also committed
# to the repo and survive restarts. Without them, a local file is used.
def _secret(key, default=""):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _gh_config():
    token, repo = _secret("GITHUB_TOKEN"), _secret("GITHUB_REPO")
    if token and repo:
        return {"token": token, "repo": repo, "branch": _secret("GITHUB_BRANCH", "main"),
                "path": _secret("GITHUB_SETTINGS_PATH", SETTINGS_NAME)}
    return None


def _gh_headers(cfg):
    return {"Authorization": f"Bearer {cfg['token']}", "Accept": "application/vnd.github+json"}


def _gh_read(cfg):
    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
    r = requests.get(url, headers=_gh_headers(cfg), params={"ref": cfg["branch"]}, timeout=10)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    body = r.json()
    return json.loads(base64.b64decode(body["content"]).decode("utf-8")), body["sha"]


@st.cache_data(ttl=300, show_spinner=False)
def load_settings() -> dict:
    cfg = _gh_config()
    if cfg:
        try:
            data, _ = _gh_read(cfg)
            if data:
                return sanitise_settings(data)
        except Exception:
            pass  # fall back to local file
    if os.path.isfile(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return sanitise_settings(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return sanitise_settings({})


def save_settings(new_settings: dict):
    """Returns (ok, message)."""
    clean = sanitise_settings({**new_settings, "updated": datetime.now().strftime("%d %b %Y, %H:%M")})
    payload = json.dumps(clean, indent=2)
    try:
        with open(SETTINGS_FILE, "w") as f:
            f.write(payload)
    except OSError:
        pass
    cfg = _gh_config()
    msg = "Saved."
    if cfg:
        try:
            _, sha = _gh_read(cfg)
            body = {"message": "Update reseller pricing settings", "branch": cfg["branch"],
                    "content": base64.b64encode(payload.encode("utf-8")).decode("utf-8")}
            if sha:
                body["sha"] = sha
            url = f"https://api.github.com/repos/{cfg['repo']}/contents/{cfg['path']}"
            r = requests.put(url, headers=_gh_headers(cfg), json=body, timeout=15)
            r.raise_for_status()
            msg = "Saved permanently."
        except Exception as exc:
            load_settings.clear()
            return False, f"Saved for now, but couldn't write to GitHub ({exc}). Prices may reset when the app restarts."
    else:
        msg = "Saved. Note: without GitHub storage configured, prices reset if the app restarts."
    load_settings.clear()
    return True, msg


SETTINGS = load_settings()
LICENCE_MONTHLY_RATE = SETTINGS["licence_monthly"]
SETUP_FEE_PER_USER = SETTINGS["setup_per_user"]
BASIC_DEPLOYMENT_FEE = SETTINGS["basic_deployment"]

# ==========================================
# 7. SESSION STATE & QUOTE MATHS
# ==========================================
if "deployment" not in st.session_state:
    st.session_state.deployment = SETTINGS["default_deployment"]
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


def total_setup_fee(users=None):
    users = st.session_state.get("num_licences", 0) if users is None else users
    return float(users) * SETUP_FEE_PER_USER if users > 0 else 0.0


def deployment_fee(option=None, users=None):
    """Deployment only applies when there are users on the system."""
    users = st.session_state.get("num_licences", 0) if users is None else users
    option = option or st.session_state.get("deployment", DEPLOY_BASIC)
    if users <= 0:
        return 0.0
    if option == DEPLOY_ADVANCED:
        return advanced_deployment_price(users)
    return BASIC_DEPLOYMENT_FEE


def total_one_off():
    return total_setup_fee() + deployment_fee() + total_hardware_capex()


def reseller_margin(users, option):
    """Refyn-IT's margin over the Novalink floors (admin eyes only)."""
    if users <= 0:
        return {"monthly": 0.0, "one_off": 0.0}
    monthly = (LICENCE_MONTHLY_RATE - FLOOR_LICENCE_MONTHLY) * users
    one_off = (SETUP_FEE_PER_USER - FLOOR_SETUP_PER_USER) * users
    if option == DEPLOY_BASIC:
        one_off += BASIC_DEPLOYMENT_FEE - FLOOR_BASIC_DEPLOYMENT
    return {"monthly": monthly, "one_off": one_off}




def novalink_deployment_cost(option, users):
    """What Novalink charges the reseller for deployment (floor / locked tariff)."""
    if users <= 0:
        return 0.0
    if option == DEPLOY_ADVANCED:
        return advanced_deployment_price(users)
    return FLOOR_BASIC_DEPLOYMENT


def cost_sell_lines(users, option, hw_items):
    """Every line on the deal with Novalink cost vs Refyn-IT sell price.
    kind = 'monthly' or 'one_off'. Hardware is supplied at catalogue price (no uplift yet)."""
    lines = []
    if users > 0:
        lines.append({"kind": "monthly", "name": "Hosted VoIP cloud user licence",
                      "desc": "Per user, per month",
                      "qty": users, "cost_unit": FLOOR_LICENCE_MONTHLY, "sell_unit": LICENCE_MONTHLY_RATE})
        lines.append({"kind": "one_off", "name": "User setup & provisioning",
                      "desc": "Per user, one-off",
                      "qty": users, "cost_unit": FLOOR_SETUP_PER_USER, "sell_unit": SETUP_FEE_PER_USER})
        lines.append({"kind": "one_off", "name": DEPLOYMENT_LABELS[option],
                      "desc": DEPLOYMENT_DESCS[option],
                      "qty": 1, "cost_unit": novalink_deployment_cost(option, users),
                      "sell_unit": deployment_fee(option, users)})
    for itm in hw_items:
        lines.append({"kind": "one_off", "name": itm["name"], "desc": itm.get("desc", ""),
                      "qty": itm["qty"], "cost_unit": itm["price"], "sell_unit": itm["price"]})
    for ln in lines:
        ln["cost_total"] = ln["cost_unit"] * ln["qty"]
        ln["sell_total"] = ln["sell_unit"] * ln["qty"]
        ln["profit"] = ln["sell_total"] - ln["cost_total"]
    return lines


def profit_summary(lines):
    def tot(kind, field):
        return sum(ln[field] for ln in lines if ln["kind"] == kind)
    s = {
        "monthly_cost": tot("monthly", "cost_total"), "monthly_sell": tot("monthly", "sell_total"),
        "oneoff_cost": tot("one_off", "cost_total"), "oneoff_sell": tot("one_off", "sell_total"),
    }
    s["monthly_profit"] = s["monthly_sell"] - s["monthly_cost"]
    s["annual_profit"] = s["monthly_profit"] * 12
    s["contract_recurring_profit"] = s["monthly_profit"] * CONTRACT_MONTHS
    s["oneoff_profit"] = s["oneoff_sell"] - s["oneoff_cost"]
    s["contract_total_profit"] = s["contract_recurring_profit"] + s["oneoff_profit"]
    s["contract_revenue"] = s["monthly_sell"] * CONTRACT_MONTHS + s["oneoff_sell"]
    s["contract_cost"] = s["monthly_cost"] * CONTRACT_MONTHS + s["oneoff_cost"]
    s["margin_pct"] = (s["contract_total_profit"] / s["contract_revenue"] * 100) if s["contract_revenue"] else 0.0
    return s


# ==========================================
# 8. PDF QUOTATION (ReportLab, A4)
# ==========================================
def generate_partner_order_pdf(order_meta, partner, end_customer, lines, build_sheet=None, n_users=0):
    """Novalink -> Refyn-IT wholesale order. Shows ONLY Novalink prices - never the reseller's sell prices."""
    partner_plain = str(partner.get("company", ""))
    partner = {k: esc(v) for k, v in partner.items()}
    end_customer = {k: esc(v) for k, v in end_customer.items()}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=27, leftMargin=27, topMargin=30, bottomMargin=40,
                            title=f"Novalink partner order {order_meta['ref']}", author=POWERED_BY)
    styles = getSampleStyleSheet()
    c_primary = colors.HexColor("#0F5A73")   # Novalink teal
    c_slate = colors.HexColor("#475569")
    c_dark = colors.HexColor("#0F172A")
    c_bg = colors.HexColor("#F4F8FA")
    c_border = colors.HexColor("#CBD5E1")

    title_style = ParagraphStyle("T", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=c_primary)
    sub_style = ParagraphStyle("S", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=12, textColor=c_slate)
    meta_style = ParagraphStyle("M", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=12, textColor=c_slate, alignment=2)
    sec_head = ParagraphStyle("H", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=c_primary)
    th_style = ParagraphStyle("TH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.white)
    td_style = ParagraphStyle("TD", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=c_dark)
    td_bold = ParagraphStyle("TDB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11.5, textColor=c_dark)
    note_style = ParagraphStyle("N", parent=styles["Normal"], fontName="Helvetica", fontSize=7.8, leading=11, textColor=c_slate)

    story = []
    hdr = Table([[
        [Paragraph("NOVALINK", title_style),
         Paragraph("<b>Partner Order &amp; Wholesale Quotation</b><br/>Hosted cloud telephony · partner pricing", sub_style)],
        Paragraph(
            f"<b>Order Ref:</b> {order_meta['ref']}<br/>"
            f"<b>Partner Quote Ref:</b> {order_meta['customer_ref']}<br/>"
            f"<b>Date:</b> {order_meta['date']}<br/>"
            f"<b>Term:</b> {CONTRACT_MONTHS} Months Minimum", meta_style),
    ]], colWidths=[330, 210])
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    story += [hdr, Spacer(1, 8), HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceAfter=10)]

    addr = f"Site: {end_customer['delivery']}<br/>" if end_customer.get("delivery") and end_customer["delivery"] != "N/A" else ""
    parties = Table([
        [Paragraph("<b>SUPPLIER</b>", td_bold), Paragraph("<b>PARTNER (BILL TO)</b>", td_bold), Paragraph("<b>END CUSTOMER (PROVISION FOR)</b>", td_bold)],
        [Paragraph(f"<b>{POWERED_BY}</b><br/>Hosted telephony platform", td_style),
         Paragraph(f"<b>{partner['company']}</b><br/>{partner['name']}<br/>{partner['email']}<br/>{partner['phone']}", td_style),
         Paragraph(f"<b>{end_customer['company']}</b><br/>Contact: {end_customer['name']}<br/>{addr}", td_style)],
    ], colWidths=[150, 195, 195])
    parties.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_bg), ("BOX", (0, 0), (-1, -1), 1, c_border),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [parties, Spacer(1, 10)]

    def section(title, kind, per_month):
        rows = [[Paragraph("Item / Description", th_style), Paragraph("Qty", th_style),
                 Paragraph("Partner Price (Ex VAT)", th_style), Paragraph("Line Total (Ex VAT)", th_style)]]
        sel = [ln for ln in lines if ln["kind"] == kind]
        suffix = " / mo" if per_month else ""
        for ln in sel:
            rows.append([
                Paragraph(f"<b>{esc(ln['name'])}</b><br/><font color='#64748B' size=7>{esc(ln['desc'])}</font>", td_style),
                Paragraph(str(ln["qty"]), td_style),
                Paragraph(f"£{ln['cost_unit']:,.2f}{suffix}", td_style),
                Paragraph(f"£{ln['cost_total']:,.2f}{suffix}", td_bold),
            ])
        total = sum(ln["cost_total"] for ln in sel)
        rows += [
            [Paragraph("<b>Total (Ex VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{total:,.2f}{suffix}</b>", td_bold)],
            [Paragraph(f"VAT @ {VAT_PCT}", td_style), "", "", Paragraph(f"£{total * VAT_RATE:,.2f}{suffix}", td_style)],
            [Paragraph("<b>Total (Inc VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{total * (1 + VAT_RATE):,.2f}{suffix}</b>", td_bold)],
        ]
        t = Table(rows, colWidths=[290, 50, 100, 100])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), c_primary), ("BOX", (0, 0), (-1, -1), 1, c_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border), ("BACKGROUND", (0, -3), (-1, -3), c_bg),
            ("BACKGROUND", (0, -1), (-1, -1), c_bg),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ]))
        story.extend([Paragraph(title, sec_head), Spacer(1, 4), t, Spacer(1, 10)])
        return total

    m_total = section("1. Monthly Recurring Charges (billed to partner)", "monthly", True)
    o_total = section("2. One-Off Charges (billed to partner)", "one_off", False)

    summ = Table([[Paragraph("<b>PARTNER COMMITMENT</b>", td_bold), Paragraph(
        f"<b>Monthly:</b> £{m_total:,.2f} Ex VAT (£{m_total * (1 + VAT_RATE):,.2f} Inc VAT)<br/>"
        f"<b>One-off:</b> £{o_total:,.2f} Ex VAT (£{o_total * (1 + VAT_RATE):,.2f} Inc VAT)<br/>"
        f"<b>Month 1 payable to {POWERED_BY}:</b> <b>£{m_total + o_total:,.2f} Ex VAT "
        f"(£{(m_total + o_total) * (1 + VAT_RATE):,.2f} Inc VAT)</b><br/>"
        f"<b>{CONTRACT_MONTHS}-month contract value:</b> £{m_total * CONTRACT_MONTHS + o_total:,.2f} Ex VAT", td_style)]],
        colWidths=[170, 370])
    summ.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), c_bg), ("BOX", (0, 0), (-1, -1), 1.5, c_primary),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [summ, Spacer(1, 10)]

    story.append(Paragraph(
        "<b>Partner terms:</b> Prices shown are Novalink partner (wholesale) prices and are payable by the partner "
        f"regardless of the price agreed with the end customer. Licences are subject to a {CONTRACT_MONTHS}-month minimum term. "
        "Hardware is supplied at partner catalogue price. This document is an order summary, not a VAT invoice — "
        "Novalink will issue a VAT invoice on acceptance.", note_style))
    story.append(Spacer(1, 10))
    sign = Table([
        [Paragraph("<b>PARTNER AUTHORISATION:</b>", td_bold), Paragraph("<b>DATE:</b> ________________________", td_style)],
        [Paragraph("Signature: _________________________________", td_style), Paragraph("Print Name: _____________________", td_style)],
    ], colWidths=[330, 210])
    sign.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, c_border), ("BACKGROUND", (0, 0), (-1, -1), c_bg),
                              ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                              ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    story.append(sign)

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#8A9099"))
        canvas.drawString(27, 18, f"{POWERED_BY} partner order · {partner_plain} · confidential")
        canvas.drawRightString(A4[0] - 27, 18, f"Page {d.page}")
        canvas.restoreState()

    if build_sheet:
        story.append(PageBreak())
        story.append(Paragraph("Appendix · System build sheet", title_style))
        story.append(Paragraph("Programming details captured by the partner with the customer.", sub_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=c_primary, spaceAfter=8, spaceBefore=6))
        story += build_sheet_flowables(build_sheet, build_sheet_parties(), c_primary, c_primary, n_users, sign_off=False)

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer.getvalue()


def _pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#8A9099"))
    canvas.drawString(27, 18, f"{APP_NAME} · hosted telephony powered by {POWERED_BY}")
    canvas.drawRightString(A4[0] - 27, 18, f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#EA5624"))
    canvas.setLineWidth(2)
    canvas.line(27, 28, 60, 28)
    canvas.restoreState()


def generate_quotation_pdf(quote_meta, reseller, customer, num_users, hw_items, deployment_option):
    # Escape typed text so names like "Smith & Co" or "<Ltd>" can't break the PDF layout
    reseller = {k: esc(v) for k, v in reseller.items()}
    customer = {k: esc(v) for k, v in customer.items()}
    hw_items = [{**i, "name": esc(i["name"]), "desc": esc(i["desc"])} for i in hw_items]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=27, leftMargin=27, topMargin=28, bottomMargin=40,
                            title=f"{APP_NAME} quotation {quote_meta['ref']}", author=APP_NAME)
    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#EA5624")   # Refyn-IT orange
    c_head = colors.HexColor("#1F232A")      # graphite table headers
    c_slate = colors.HexColor("#475569")
    c_dark = colors.HexColor("#0F172A")
    c_bg = colors.HexColor("#F7F7F8")
    c_border = colors.HexColor("#D4D9DF")
    c_warning_bg = colors.HexColor("#FFF6F1")
    c_warning_border = colors.HexColor("#EA5624")
    c_warning_text = colors.HexColor("#7A2E12")

    title_style = ParagraphStyle("DocTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=c_dark)
    sub_style = ParagraphStyle("DocSub", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=11, textColor=c_slate)
    meta_style = ParagraphStyle("MetaText", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=12, textColor=c_slate, alignment=2)
    sec_head = ParagraphStyle("SectionHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=c_primary)
    th_style = ParagraphStyle("TH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=colors.white)
    td_style = ParagraphStyle("TD", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11.5, textColor=c_dark)
    td_bold = ParagraphStyle("TDB", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=11.5, textColor=c_dark)

    story = []

    # Header: logo + title | metadata
    left_cell = []
    pdf_logo = asset(BRAND_LOGO_PDF_FILE)
    if os.path.exists(pdf_logo):
        iw, ih = ImageReader(pdf_logo).getSize()
        logo_w = 170
        left_cell.append(RLImage(pdf_logo, width=logo_w, height=logo_w * ih / iw, hAlign="LEFT"))
        left_cell.append(Spacer(1, 6))
    left_cell.append(Paragraph("Telecoms Quotation", title_style))
    left_cell.append(Paragraph(f"Hosted cloud telephony · powered by <b>{POWERED_BY}</b>", sub_style))
    hdr = Table(
        [[
            left_cell,
            Paragraph(
                f"<b>Reference:</b> {quote_meta['ref']}<br/>"
                f"<b>Date:</b> {quote_meta['date']}<br/>"
                f"<b>Contract Term:</b> <b>{CONTRACT_MONTHS} Months Minimum</b><br/>"
                f"<b>Valid for:</b> {QUOTE_VALID_DAYS} days",
                meta_style,
            ),
        ]],
        colWidths=[350, 190],
    )
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
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
        [Paragraph("<b>YOUR REFYN-IT CONTACT</b>", td_bold), Paragraph("<b>PROPOSED CUSTOMER</b>", td_bold)],
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
            Paragraph(f"£{LICENCE_MONTHLY_RATE:,.2f} / mo", td_style),
            Paragraph(f"£{mrc_total:,.2f} / mo", td_bold),
        ],
        [Paragraph("<b>Total Ongoing Monthly Costs (Ex VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{mrc_total:,.2f} / mo</b>", td_bold)],
        [Paragraph(f"VAT @ {VAT_PCT}", td_style), "", "", Paragraph(f"£{mrc_vat:,.2f} / mo", td_style)],
        [Paragraph("<b>Total Ongoing Monthly Costs (Inc VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{mrc_inc_vat:,.2f} / mo</b>", td_bold)],
    ]
    t_mrc = Table(mrc_data, colWidths=[290, 50, 100, 100])
    t_mrc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_head),
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

    setup_total = num_users * SETUP_FEE_PER_USER if num_users > 0 else 0.0
    deploy_total = deployment_fee(deployment_option, num_users)
    hw_total = sum(i["line_total"] for i in hw_items)
    one_off_grand_total = setup_total + deploy_total + hw_total
    one_off_vat = one_off_grand_total * VAT_RATE
    one_off_inc_vat = one_off_grand_total + one_off_vat

    upfront_data = [
        [Paragraph("Item / Description", th_style), Paragraph("Qty", th_style),
         Paragraph("Unit Price (Ex VAT)", th_style), Paragraph("Line Total (Ex VAT)", th_style)],
    ]
    if num_users > 0:
        upfront_data.append([
            Paragraph(
                "<b>User Setup &amp; Provisioning</b><br/>"
                "<font color='#64748B' size=7>Extension setup, user provisioning &amp; licence activation.</font>",
                td_style,
            ),
            Paragraph(str(num_users), td_style),
            Paragraph(f"£{SETUP_FEE_PER_USER:,.2f}", td_style),
            Paragraph(f"£{setup_total:,.2f}", td_bold),
        ])
        upfront_data.append([
            Paragraph(
                f"<b>{DEPLOYMENT_LABELS[deployment_option]}</b><br/>"
                f"<font color='#64748B' size=7>{esc(DEPLOYMENT_DESCS[deployment_option])}.</font>",
                td_style,
            ),
            Paragraph("1", td_style),
            Paragraph(f"£{deploy_total:,.2f}", td_style),
            Paragraph(f"£{deploy_total:,.2f}", td_bold),
        ])
    for itm in hw_items:
        upfront_data.append([
            Paragraph(f"<b>{itm['name']}</b><br/><font color='#64748B' size=7>{itm['desc']}</font>", td_style),
            Paragraph(str(itm["qty"]), td_style),
            Paragraph(f"£{itm['price']:,.2f}", td_style),
            Paragraph(f"£{itm['line_total']:,.2f}", td_bold),
        ])
    upfront_data.append([Paragraph("<b>Total One-Off Upfront Costs (Ex VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{one_off_grand_total:,.2f}</b>", td_bold)])
    upfront_data.append([Paragraph(f"VAT @ {VAT_PCT}", td_style), "", "", Paragraph(f"£{one_off_vat:,.2f}", td_style)])
    upfront_data.append([Paragraph("<b>Total One-Off Upfront Costs (Inc VAT)</b>", td_bold), "", "", Paragraph(f"<b>£{one_off_inc_vat:,.2f}</b>", td_bold)])

    t_upfront = Table(upfront_data, colWidths=[290, 50, 100, 100])
    t_upfront.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_head),
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
            f"<b>Ongoing Monthly Costs:</b> £{mrc_total:,.2f} Ex VAT (£{mrc_inc_vat:,.2f} Inc VAT / mo)<br/>"
            f"<b>Total One-Off Upfront Costs:</b> £{one_off_grand_total:,.2f} Ex VAT (£{one_off_inc_vat:,.2f} Inc VAT)<br/>"
            f"<b>Total Month 1 Investment:</b> <b>£{first_month_ex:,.2f} Ex VAT (£{first_month_inc:,.2f} Inc VAT)</b>",
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
        f"All hosted user licences quoted herein are strictly subject to a <b>minimum {CONTRACT_MONTHS}-month agreement term</b>. "
        f"In the event of early termination or cancellation of services prior to the expiry of the initial {CONTRACT_MONTHS}-month term, "
        "<b>early termination charges will be applicable and payable in full</b> for all outstanding monthly licence fees "
        "remaining across the unexpired portion of the agreement.<br/>"
        f"<b>Commercial Notes:</b> Quotation valid for {QUOTE_VALID_DAYS} calendar days."
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

    doc.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================
# 8b. SYSTEM SETUP ("BUILD SHEET") - programming details for the install team
# ==========================================
import re as _re

BS_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
BS_TIMES = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)] + ["23:59"]
BS_HOURS_PRESETS = {
    "Mon–Fri 09:00–17:00": (5, "09:00", "17:00"),
    "Mon–Fri 08:30–17:30": (5, "08:30", "17:30"),
    "Mon–Fri 08:00–18:00": (5, "08:00", "18:00"),
    "Mon–Sat 09:00–17:00": (6, "09:00", "17:00"),
    "Open 24/7": (7, "00:00", "23:59"),
    "Custom hours": None,
}
BS_OOH_ACTIONS = [
    "Closed message, then voicemail",
    "Closed message, then hang up",
    "Divert to a mobile / other number",
    "Ring as normal (no out-of-hours)",
]
BS_AUDIO = ["Text-to-speech from the scripts below", "Customer will supply audio files", "Professional voiceover (quote separately)"]
BS_RING_STYLES = ["All at once", "In order (hunt)", "Longest idle first", "Round robin"]
BS_NO_ANSWER = ["Voicemail", "Overflow to another group", "Overflow to a mobile / number", "Keep queuing", "Back to main menu"]
BS_NO_INPUT = ["Repeat menu once, then go to option 1", "Repeat menu once, then voicemail", "Go straight to option 1", "Hang up"]
BS_NUMBERS = ["Port existing number(s)", "New number(s)", "Port existing + add new"]
BS_CLI = ["Company main number", "Each user's direct dial", "Withheld"]
BS_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
BS_SOFTPHONE = "Softphone / app only"
_EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

BS_DEFAULT_WELCOME = "Thank you for calling [Company name]."
BS_DEFAULT_GDPR = ("Please note that calls may be recorded for training and quality purposes. "
                   "To find out how we use your personal data, please see the privacy notice on our website.")
BS_DEFAULT_CLOSED = ("Thank you for calling. Our office is currently closed. Please leave a message after the tone "
                     "and we'll call you back on the next working day.")


def _bs_init():
    ss = st.session_state
    defaults = {
        "bs_hours_preset": "Mon–Fri 09:00–17:00", "bs_bank_hols": True,
        "bs_ooh_action": BS_OOH_ACTIONS[0], "bs_ooh_divert": "", "bs_closed_text": BS_DEFAULT_CLOSED,
        "bs_welcome_on": True, "bs_welcome_text": BS_DEFAULT_WELCOME,
        "bs_gdpr_on": True, "bs_gdpr_text": BS_DEFAULT_GDPR, "bs_audio": BS_AUDIO[0],
        "bs_ivr_on": True, "bs_no_input": BS_NO_INPUT[0],
        "bs_vm_email": "", "bs_numbers": BS_NUMBERS[0], "bs_main_number": "", "bs_provider": "",
        "bs_port_postcode": "", "bs_cli": BS_CLI[0], "bs_notes": "", "bs_users_ver": 0,
    }
    for k, v in defaults.items():
        if k not in ss:
            ss[k] = v
    if "bs_hours_base" not in ss:
        ss.bs_hours_base = pd.DataFrame([
            {"Day": d, "Open": i < 5, "From": "09:00", "To": "17:00"} for i, d in enumerate(BS_DAYS)])
    if "bs_flow_base" not in ss:
        ss.bs_flow_base = pd.DataFrame([
            {"Key": "1", "Option": "Sales", "Who rings": "", "Ring style": "All at once", "Ring (secs)": 20,
             "If no answer": "Voicemail", "Then / voicemail email": ""},
            {"Key": "2", "Option": "Accounts", "Who rings": "", "Ring style": "All at once", "Ring (secs)": 20,
             "If no answer": "Voicemail", "Then / voicemail email": ""},
        ])
    if "bs_direct_base" not in ss:
        ss.bs_direct_base = pd.DataFrame([
            {"Who rings": "", "Ring style": "All at once", "Ring (secs)": 20,
             "If no answer": "Voicemail", "Then / voicemail email": ""}])


def _bs_user_rows(n, existing):
    rows = existing.to_dict("records") if existing is not None else []
    rows = rows[:n]
    for i in range(len(rows), n):
        rows.append({"First name": "", "Last name": "", "Email": "", "Extension": str(201 + i),
                     "Device": BS_SOFTPHONE, "Mobile app": True, "Voicemail to email": True, "Direct dial (DDI)": ""})
    return pd.DataFrame(rows, columns=["First name", "Last name", "Email", "Extension", "Device",
                                       "Mobile app", "Voicemail to email", "Direct dial (DDI)"])


def _clean_df(df):
    if df is None:
        return []
    out = []
    for r in df.to_dict("records"):
        out.append({k: ("" if (v is None or (isinstance(v, float) and math.isnan(v))) else v) for k, v in r.items()})
    return out


def bs_hours_rows():
    ss = st.session_state
    preset = BS_HOURS_PRESETS.get(ss.get("bs_hours_preset"))
    if preset:
        n_days, a, b = preset
        return [{"Day": d, "Open": i < n_days, "From": a, "To": b} for i, d in enumerate(BS_DAYS)]
    return _clean_df(ss.get("bs_hours_latest", ss.get("bs_hours_base")))


def bs_hours_summary(rows):
    open_rows = [r for r in rows if r.get("Open")]
    if not open_rows:
        return "Closed all week"
    if len(open_rows) == 7 and all(r["From"] == "00:00" and r["To"] == "23:59" for r in open_rows):
        return "Open 24/7"
    groups = []
    for r in open_rows:
        t = f'{r["From"]}–{r["To"]}'
        if groups and groups[-1][2] == t and BS_DAYS.index(r["Day"]) == BS_DAYS.index(groups[-1][1]) + 1:
            groups[-1][1] = r["Day"]
        else:
            groups.append([r["Day"], r["Day"], t])
    return ", ".join((f"{a[:3]}–{b[:3]}" if a != b else a[:3]) + f" {t}" for a, b, t in groups)


def bs_menu_script(flow):
    parts = [f'For {r["Option"]}, press {r["Key"]}.' for r in flow if r.get("Option") and r.get("Key")]
    return " ".join(parts)


def build_sheet_data():
    ss = st.session_state
    ivr = bool(ss.get("bs_ivr_on"))
    flow_df = ss.get("bs_flow_latest", ss.get("bs_flow_base")) if ivr else ss.get("bs_direct_latest", ss.get("bs_direct_base"))
    flow = [r for r in _clean_df(flow_df) if any(str(v).strip() for k, v in r.items() if k not in ("Ring (secs)",))]
    if ivr:
        flow = sorted(flow, key=lambda r: BS_KEYS.index(str(r.get("Key"))) if str(r.get("Key")) in BS_KEYS else 99)
    users = _clean_df(ss.get("bs_users_latest"))
    return {
        "hours_preset": ss.get("bs_hours_preset"), "hours": bs_hours_rows(), "bank_hols": ss.get("bs_bank_hols"),
        "ooh_action": ss.get("bs_ooh_action"), "ooh_divert": ss.get("bs_ooh_divert", ""),
        "closed_text": ss.get("bs_closed_text", ""),
        "welcome_on": ss.get("bs_welcome_on"), "welcome_text": ss.get("bs_welcome_text", ""),
        "gdpr_on": ss.get("bs_gdpr_on"), "gdpr_text": ss.get("bs_gdpr_text", ""), "audio": ss.get("bs_audio"),
        "ivr_on": ivr, "no_input": ss.get("bs_no_input"), "flow": flow, "menu_script": bs_menu_script(flow) if ivr else "",
        "users": users, "vm_email": ss.get("bs_vm_email", ""),
        "numbers": ss.get("bs_numbers"), "main_number": ss.get("bs_main_number", ""),
        "provider": ss.get("bs_provider", ""), "port_postcode": ss.get("bs_port_postcode", ""),
        "cli": ss.get("bs_cli"), "notes": ss.get("bs_notes", ""),
    }


def build_sheet_checks(bs, n_users):
    """(label, ok) list the install team needs before they can build."""
    porting = bs["numbers"] != "New number(s)"
    uses_vm = any("Voicemail" in str(r.get("If no answer", "")) for r in bs["flow"]) or "voicemail" in (bs["ooh_action"] or "")
    users = bs["users"]
    checks = [
        ("Opening hours", any(r.get("Open") for r in bs["hours"])),
        ("Welcome message", (not bs["welcome_on"]) or (bs["welcome_text"].strip() and "[Company name]" not in bs["welcome_text"])),
        ("Call routing: who answers each option", bool(bs["flow"]) and all(str(r.get("Who rings", "")).strip() for r in bs["flow"])
         and (not bs["ivr_on"] or all(str(r.get("Option", "")).strip() for r in bs["flow"]))),
        (f"User names ({n_users})", n_users > 0 and len(users) == n_users
         and all(str(u.get("First name", "")).strip() for u in users)),
        ("User email addresses", n_users > 0 and len(users) == n_users
         and all(_EMAIL_RE.match(str(u.get("Email", "")).strip()) for u in users)),
        ("Number details" + (" (porting)" if porting else ""), (not porting) or (bool(bs["main_number"].strip()) and bool(bs["provider"].strip()))),
    ]
    if bs["ooh_action"] == BS_OOH_ACTIONS[2]:
        checks.insert(1, ("Out-of-hours divert number", bool(bs["ooh_divert"].strip())))
    if uses_vm:
        checks.insert(-1, ("Main voicemail email", bool(_EMAIL_RE.match(bs["vm_email"].strip()))))
    return checks


def render_build_sheet_form():
    """The 'System setup details' drop-down inside the Deployment card."""
    _bs_init()
    ss = st.session_state
    n_users = int(ss.get("num_licences", 0))
    with st.expander("System setup details  ·  IVR, opening hours, call routing, users & voicemail", expanded=False):
        render_html('<div class="rit-bs-intro">Fill this in with your customer. It becomes the <b>build sheet</b> our '
                    'engineers programme the system from. Anything left blank can be finished later.</div>')
        t_hours, t_calls, t_users, t_vm = st.tabs(["1 · Hours", "2 · Greeting & menu", "3 · Users", "4 · Voicemail & numbers"])

        # ---- 1. Hours ----
        with t_hours:
            h1, h2 = st.columns([1.4, 1])
            with h1:
                st.selectbox("Opening hours", list(BS_HOURS_PRESETS.keys()), key="bs_hours_preset")
            with h2:
                st.checkbox("Closed on UK bank holidays", key="bs_bank_hols")
            if ss.bs_hours_preset == "Custom hours":
                ss.bs_hours_latest = st.data_editor(
                    ss.bs_hours_base, key="bs_hours_ed", hide_index=True, num_rows="fixed", **FULL_WIDTH,
                    column_config={
                        "Day": st.column_config.TextColumn(disabled=True),
                        "Open": st.column_config.CheckboxColumn(),
                        "From": st.column_config.SelectboxColumn(options=BS_TIMES, required=True),
                        "To": st.column_config.SelectboxColumn(options=BS_TIMES, required=True),
                    })
            else:
                render_html(f'<div class="rit-bs-read">{icon("check", 13, 3)}{esc(bs_hours_summary(bs_hours_rows()))}</div>')
            o1, o2 = st.columns([1.4, 1])
            with o1:
                st.selectbox("Out of hours, calls should…", BS_OOH_ACTIONS, key="bs_ooh_action")
            with o2:
                if ss.bs_ooh_action == BS_OOH_ACTIONS[2]:
                    st.text_input("Divert to number", key="bs_ooh_divert", placeholder="e.g. 07700 900123")
            if ss.bs_ooh_action in BS_OOH_ACTIONS[:2]:
                st.text_area("Closed message", key="bs_closed_text", height=80)

        # ---- 2. Greeting & menu ----
        with t_calls:
            g1, g2 = st.columns(2)
            with g1:
                st.checkbox("Play a welcome message", key="bs_welcome_on")
            with g2:
                st.checkbox("Play a call-recording / GDPR notice", key="bs_gdpr_on")
            if ss.bs_welcome_on:
                st.text_input("Welcome message", key="bs_welcome_text")
            if ss.bs_gdpr_on:
                st.text_area("Recording / GDPR notice", key="bs_gdpr_text", height=72)
            st.selectbox("How are the messages recorded?", BS_AUDIO, key="bs_audio")
            render_html('<div class="rit-admin-h">Call routing (in hours)</div>')
            st.toggle("Use a menu — “press 1 for sales, 2 for accounts…”", key="bs_ivr_on")
            common = {
                "Who rings": st.column_config.TextColumn("Who rings", help="Names or extensions, e.g. Jo, Sam, 203",
                                                         width="medium"),
                "Ring style": st.column_config.SelectboxColumn("Ring style", options=BS_RING_STYLES, required=True),
                "Ring (secs)": st.column_config.NumberColumn("Ring (secs)", min_value=5, max_value=120, step=5),
                "If no answer": st.column_config.SelectboxColumn("If no answer", options=BS_NO_ANSWER, required=True),
                "Then / voicemail email": st.column_config.TextColumn(
                    "Then… / voicemail email", help="Overflow group or number, or the email voicemails go to"),
            }
            if ss.bs_ivr_on:
                ss.bs_flow_latest = st.data_editor(
                    ss.bs_flow_base, key="bs_flow_ed", hide_index=True, num_rows="dynamic", **FULL_WIDTH,
                    column_config={
                        "Key": st.column_config.SelectboxColumn("Key", options=BS_KEYS, required=True, width="small"),
                        "Option": st.column_config.TextColumn("Option", help="e.g. Sales, Accounts, Support"),
                        **common,
                    })
                script = bs_menu_script(build_sheet_data()["flow"])
                if script:
                    render_html(f'<div class="rit-bs-read">{icon("phone", 13)}<span><b>Menu will say:</b> “{esc(script)}”</span></div>')
                st.selectbox("If the caller doesn't press anything", BS_NO_INPUT, key="bs_no_input")
            else:
                ss.bs_direct_latest = st.data_editor(
                    ss.bs_direct_base, key="bs_direct_ed", hide_index=True, num_rows="fixed", **FULL_WIDTH,
                    column_config=common)
            st.caption("Add a row per menu option. Use the ＋ at the bottom of the table for more options.")

        # ---- 3. Users ----
        with t_users:
            if n_users == 0:
                render_html('<div class="nl-empty">Set the number of users in step 01 and a row appears here for each one.</div>')
            else:
                current = ss.get("bs_users_latest")
                if current is None or len(current) != n_users:
                    ss.bs_users_base = _bs_user_rows(n_users, current)
                    ss.bs_users_ver += 1
                devices = [BS_SOFTPHONE] + [i["name"] for i in basket_items()] + ["Customer's own device"]
                ss.bs_users_latest = st.data_editor(
                    ss.bs_users_base, key=f"bs_users_ed_{ss.bs_users_ver}", hide_index=True, num_rows="fixed", **FULL_WIDTH,
                    column_config={
                        "Email": st.column_config.TextColumn("Email", help="Login & voicemail-to-email address"),
                        "Extension": st.column_config.TextColumn("Ext.", width="small"),
                        "Device": st.column_config.SelectboxColumn("Device", options=devices, required=True),
                        "Mobile app": st.column_config.CheckboxColumn("App", width="small"),
                        "Voicemail to email": st.column_config.CheckboxColumn("VM → email", width="small"),
                        "Direct dial (DDI)": st.column_config.TextColumn("Direct dial", help="Optional direct number"),
                    })
                st.caption(f"One row per licence ({n_users}). Changing the number of users adds or removes rows.")

        # ---- 4. Voicemail & numbers ----
        with t_vm:
            v1, v2 = st.columns(2)
            with v1:
                st.text_input("Main / shared voicemail goes to (email)", key="bs_vm_email", placeholder="e.g. office@customer.co.uk")
            with v2:
                st.selectbox("Outgoing caller ID", BS_CLI, key="bs_cli")
            n1, n2 = st.columns(2)
            with n1:
                st.selectbox("Phone numbers", BS_NUMBERS, key="bs_numbers")
            with n2:
                st.text_input("Main number" + (" to port" if ss.bs_numbers != "New number(s)" else " (if known)"),
                              key="bs_main_number", placeholder="e.g. 01234 567890")
            if ss.bs_numbers != "New number(s)":
                p1, p2 = st.columns(2)
                with p1:
                    st.text_input("Current phone provider", key="bs_provider", placeholder="e.g. BT")
                with p2:
                    st.text_input("Postcode the numbers are billed to", key="bs_port_postcode")
            st.text_area("Anything else our engineers should know?", key="bs_notes", height=72,
                         placeholder="e.g. hold music, call queue announcements, specific user ringing rules")

        # ---- Status + download ----
        bs = build_sheet_data()
        checks = build_sheet_checks(bs, n_users)
        done = sum(1 for _, ok in checks if ok)
        chips = "".join(chip(("✓ " if ok else "○ ") + lbl, "good" if ok else "muted") for lbl, ok in checks)
        render_html(f'<div class="rit-bs-status"><div class="h">Build sheet {done}/{len(checks)} complete</div>'
                    f'<div class="pe-chips">{chips}</div></div>')
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Prepare build sheet PDF", key="bs_make", **FULL_WIDTH):
                ss.bs_pdf = generate_build_sheet_pdf(bs, build_sheet_parties())
        with b2:
            if ss.get("bs_pdf"):
                st.download_button("Download build sheet PDF", data=ss.bs_pdf, key="bs_dl", mime="application/pdf",
                                   file_name=f"Build-sheet-{build_sheet_parties()['ref']}.pdf", type="primary", **FULL_WIDTH)
    return done, len(checks)


def build_sheet_parties():
    d = st.session_state.get("active_quote_details")
    if d:
        return {"ref": d["meta"]["ref"], "customer": d["customer"]["company"], "contact": d["customer"]["name"],
                "site": d["customer"].get("delivery", ""), "reseller": d["reseller"]["company"],
                "reseller_contact": d["reseller"]["name"]}
    return {"ref": "DRAFT", "customer": "", "contact": "", "site": "", "reseller": SETTINGS.get("company_name", ""),
            "reseller_contact": ""}


def build_sheet_flowables(bs, parties, c_primary, c_head, n_users, sign_off=True):
    styles = getSampleStyleSheet()
    c_dark, c_bg, c_border, c_slate = (colors.HexColor("#0F172A"), colors.HexColor("#F7F7F8"),
                                       colors.HexColor("#D4D9DF"), colors.HexColor("#475569"))
    sec = ParagraphStyle("BSH", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                         textColor=c_primary, spaceBefore=8, spaceAfter=4)
    td = ParagraphStyle("BSTD", parent=styles["Normal"], fontName="Helvetica", fontSize=8.3, leading=11, textColor=c_dark)
    tdb = ParagraphStyle("BSTDB", parent=td, fontName="Helvetica-Bold")
    th = ParagraphStyle("BSTH", parent=td, fontName="Helvetica-Bold", textColor=colors.white)
    miss = "<font color='#B45309'><i>To confirm</i></font>"

    def v(x):
        x = str(x if x is not None else "").strip()
        return esc(x) if x else miss

    def grid(rows, widths, header=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [("BOX", (0, 0), (-1, -1), 0.8, c_border), ("INNERGRID", (0, 0), (-1, -1), 0.4, c_border),
                 ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 6)]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), c_head))
        t.setStyle(TableStyle(style))
        return t

    def kv(pairs):
        rows = [[Paragraph(f"<b>{esc(k)}</b>", td), Paragraph(val, td)] for k, val in pairs]
        t = grid(rows, [150, 390], header=False)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), c_bg)]))
        return t

    out = []
    out.append(kv([
        ("Customer", v(parties["customer"])), ("Contact", v(parties["contact"])),
        ("Site", v(parties["site"] if parties["site"] != "N/A" else "")),
        ("Partner", f'{v(parties["reseller"])} · {v(parties["reseller_contact"])}'),
        ("Users / licences", str(n_users)), ("Quote ref", esc(parties["ref"])),
    ]))

    out.append(Paragraph("1. Opening hours", sec))
    hrs = [[Paragraph(x, th) for x in ("Day", "Open?", "From", "To")]]
    for r in bs["hours"]:
        o = bool(r.get("Open"))
        hrs.append([Paragraph(esc(r["Day"]), td), Paragraph("Open" if o else "Closed", tdb if o else td),
                    Paragraph(esc(r["From"]) if o else "—", td), Paragraph(esc(r["To"]) if o else "—", td)])
    out.append(grid(hrs, [150, 130, 130, 130]))
    ooh = esc(bs["ooh_action"] or "")
    if bs["ooh_action"] == BS_OOH_ACTIONS[2]:
        ooh += f" → {v(bs['ooh_divert'])}"
    pairs = [("Bank holidays", "Closed" if bs["bank_hols"] else "Normal hours"), ("Out of hours", ooh)]
    if bs["ooh_action"] in BS_OOH_ACTIONS[:2]:
        pairs.append(("Closed message", v(bs["closed_text"])))
    out.append(Spacer(1, 4))
    out.append(kv(pairs))

    out.append(Paragraph("2. Greeting, recording notice &amp; menu", sec))
    pairs = [("Welcome message", v(bs["welcome_text"]) if bs["welcome_on"] else "None"),
             ("Recording / GDPR notice", v(bs["gdpr_text"]) if bs["gdpr_on"] else "None"),
             ("Recordings", esc(bs["audio"] or ""))]
    if bs["ivr_on"]:
        pairs += [("Menu message", v(bs["menu_script"])), ("No key pressed", esc(bs["no_input"] or ""))]
    else:
        pairs.append(("Menu", "No menu — calls ring straight through"))
    out.append(kv(pairs))
    out.append(Spacer(1, 4))
    head = (["Key", "Option"] if bs["ivr_on"] else []) + ["Who rings", "Ring style", "Ring", "If no answer", "Then / VM email"]
    rows = [[Paragraph(x, th) for x in head]]
    for r in bs["flow"] or [{}]:
        secs = r.get("Ring (secs)")
        cells = ([Paragraph(v(r.get("Key")), tdb), Paragraph(v(r.get("Option")), tdb)] if bs["ivr_on"] else []) + [
            Paragraph(v(r.get("Who rings")), td), Paragraph(v(r.get("Ring style")), td),
            Paragraph(f"{int(secs)}s" if str(secs).replace(".0", "").isdigit() else miss, td),
            Paragraph(v(r.get("If no answer")), td), Paragraph(esc(str(r.get("Then / voicemail email", "") or "—")), td)]
        rows.append(cells)
    widths = [32, 70, 120, 72, 36, 90, 120] if bs["ivr_on"] else [150, 80, 40, 110, 160]
    out.append(grid(rows, widths))

    out.append(Paragraph("3. Users", sec))
    urows = [[Paragraph(x, th) for x in ("Name", "Email", "Ext.", "Device", "App", "VM mail", "Direct dial")]]
    for u in bs["users"] or []:
        name = f'{u.get("First name", "")} {u.get("Last name", "")}'.strip()
        urows.append([Paragraph(v(name), tdb), Paragraph(v(u.get("Email")), td), Paragraph(v(u.get("Extension")), td),
                      Paragraph(v(u.get("Device")), td), Paragraph("Yes" if u.get("Mobile app") else "No", td),
                      Paragraph("Yes" if u.get("Voicemail to email") else "No", td),
                      Paragraph(esc(str(u.get("Direct dial (DDI)", "") or "—")), td)])
    if len(urows) == 1:
        urows.append([Paragraph(miss, td)] + [""] * 6)
    out.append(grid(urows, [95, 145, 34, 110, 30, 50, 76]))

    out.append(Paragraph("4. Voicemail &amp; numbers", sec))
    pairs = [("Main voicemail to", v(bs["vm_email"])), ("Outgoing caller ID", esc(bs["cli"] or "")),
             ("Numbers", esc(bs["numbers"] or "")), ("Main number", v(bs["main_number"]))]
    if bs["numbers"] != "New number(s)":
        pairs += [("Current provider", v(bs["provider"])), ("Billing postcode", v(bs["port_postcode"]))]
    pairs.append(("Notes", esc(bs["notes"]) if bs["notes"].strip() else "—"))
    out.append(kv(pairs))

    if sign_off:
        out.append(Spacer(1, 10))
        out.append(Paragraph("<font size=7.5 color='#475569'>By signing, the customer confirms these details are correct. "
                             "Changes after the system is built may be chargeable.</font>", td))
        out.append(Spacer(1, 4))
        s = grid([[Paragraph("<b>Customer signature:</b> ______________________________", td),
                   Paragraph("<b>Date:</b> ____________________", td)]], [340, 200], header=False)
        s.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), c_bg), ("TOPPADDING", (0, 0), (-1, -1), 8),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        out.append(s)
    return out


def generate_build_sheet_pdf(bs, parties):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=27, leftMargin=27, topMargin=28, bottomMargin=40,
                            title=f"Build sheet {parties['ref']}", author=APP_NAME)
    styles = getSampleStyleSheet()
    story = []
    left = []
    logo = asset(BRAND_LOGO_PDF_FILE)
    if os.path.exists(logo):
        iw, ih = ImageReader(logo).getSize()
        left.append(RLImage(logo, width=150, height=150 * ih / iw, hAlign="LEFT"))
        left.append(Spacer(1, 6))
    left.append(Paragraph("System Build Sheet", ParagraphStyle("t", parent=styles["Normal"], fontName="Helvetica-Bold",
                                                                fontSize=15, leading=19)))
    left.append(Paragraph(f"Programming details · powered by <b>{POWERED_BY}</b>",
                          ParagraphStyle("s", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#475569"))))
    hdr = Table([[left, Paragraph(f"<b>Ref:</b> {esc(parties['ref'])}<br/><b>Date:</b> {datetime.now().strftime('%d %B %Y')}",
                                  ParagraphStyle("m", parent=styles["Normal"], fontSize=8.5, leading=12, alignment=2))]],
                colWidths=[350, 190])
    hdr.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    story += [hdr, Spacer(1, 6), HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#EA5624"), spaceAfter=8)]
    story += build_sheet_flowables(bs, parties, colors.HexColor("#EA5624"), colors.HexColor("#1F232A"),
                                   int(st.session_state.get("num_licences", 0)))
    doc.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    return buffer.getvalue()


def users_csv(bs):
    return pd.DataFrame(bs["users"]).to_csv(index=False).encode("utf-8")


# ==========================================
# 9. PAGE
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
    return (st.session_state.get("num_licences", 0), st.session_state.get("deployment"),
            LICENCE_MONTHLY_RATE, SETUP_FEE_PER_USER, BASIC_DEPLOYMENT_FEE,
            tuple(sorted(st.session_state.basket.items())))


def product_image_html(product, max_h=124):
    uri = get_base64_image(product.get("image"))
    if uri:
        return f'<img src="{uri}" alt="{esc(product["name"])}" style="max-height:{max_h}px">'
    return f'<div class="ph">{icon("image", 26, 1.6)}<span>Image not found</span></div>'


def advanced_band_label(users: int) -> str:
    prev = 0
    for cap, _ in ADVANCED_DEPLOYMENT_TIERS:
        if users <= cap:
            return f"{prev + 1}–{cap} users"
        prev = cap
    band = ADVANCED_EXTRA_BAND_SIZE
    top = prev + band * math.ceil((users - prev) / band)
    return f"{top - band + 1}–{top} users"


def advanced_bands(extra=4):
    """(from, to) user bands for the tariff table: the fixed tiers + a few extra bands."""
    out, prev = [], 0
    for cap, _ in ADVANCED_DEPLOYMENT_TIERS:
        out.append((prev + 1, cap))
        prev = cap
    for _ in range(extra):
        out.append((prev + 1, prev + ADVANCED_EXTRA_BAND_SIZE))
        prev += ADVANCED_EXTRA_BAND_SIZE
    return out


hero_slot = st.empty()
tab_builder, tab_customer_view, tab_admin = st.tabs(["Build quotation", "Customer view", "Admin · pricing"])

# ---------------- TAB 1: BUILD QUOTATION ----------------
with tab_builder:
    left, right = st.columns([1.72, 1], gap="large")

    with left:
        # ===== 01 · Users =====
        with st.container(key="card-users"):
            section_header("01", "Hosted user licences", f"Ongoing monthly · {CONTRACT_MONTHS}-month minimum term")
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
                    f'<div class="nl-activation">{icon("zap", 14)}<span>One-off user setup &amp; provisioning:'
                    f' <b>{money(SETUP_FEE_PER_USER)} per user</b>, billed in month 1</span></div></div>'
                )
            with u2:
                st.number_input("Number of users", min_value=0, max_value=500, step=1, key="num_licences")
                users = st.session_state.num_licences
                mrc = float(users) * LICENCE_MONTHLY_RATE
                setup = total_setup_fee(users)
                render_html(
                    '<div class="nl-mini">'
                    f'<div><div class="l">Monthly</div><div class="v">{money(mrc)}</div><div class="s">{money(mrc * (1 + VAT_RATE))} inc VAT</div></div>'
                    f'<div><div class="l">User setup</div><div class="v">{money(setup)}</div><div class="s">one-off, ex VAT</div></div>'
                    "</div>"
                )

        # ===== 02 · Deployment =====
        with st.container(key="card-deploy"):
            section_header("02", "Deployment", "One-off · choose how the system goes live")
            users = st.session_state.num_licences
            basic_price = BASIC_DEPLOYMENT_FEE
            adv_price = advanced_deployment_price(max(users, 1))
            opts = [DEPLOY_BASIC, DEPLOY_ADVANCED]
            d1, d2 = st.columns(2, gap="medium")
            for col, opt in zip((d1, d2), opts):
                selected = st.session_state.deployment == opt
                with col:
                    with st.container(key=f"dep-{'on' if selected else 'off'}-{opt}"):
                        if opt == DEPLOY_BASIC:
                            price_txt = money(basic_price)
                            meta = [chip("Flat fee", "muted"), chip("Self-install", "muted")]
                        else:
                            price_txt = money(adv_price)
                            meta = [chip(advanced_band_label(max(users, 1)), "accent"), chip("Fully managed", "muted")]
                        render_html(
                            f'<div class="rit-dep-top"><div class="rit-dep-name">{esc(DEPLOYMENT_LABELS[opt])}</div>'
                            f'<div class="rit-dep-price">{price_txt}</div></div>'
                            f'<div class="rit-dep-desc">{esc(DEPLOYMENT_DESCS[opt])}</div>'
                            f'<div class="pe-chips" style="margin:10px 0 12px 0">{"".join(meta)}</div>'
                        )
                        st.button("Selected" if selected else "Choose this option", key=f"pick_{opt}",
                                  type="primary" if selected else "secondary", disabled=selected,
                                  on_click=lambda o=opt: st.session_state.update(deployment=o), **FULL_WIDTH)
            if users == 0:
                render_html(f'<div class="pe-hint">{icon("alert", 14)}<span>Deployment is added once you set the number of users.'
                            f' Advanced pricing shown is for {advanced_band_label(1)}.</span></div>')
            render_build_sheet_form()

        # ===== 03 · Hardware =====
        with st.container(key="card-hardware"):
            section_header("03", "Handsets, headsets & hardware", "Optional · one-off upfront · tap + to add")
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

        # ===== 04 · Details & PDF =====
        with st.container(key="card-details"):
            section_header("04", "Quote details & PDF", "Who it's from, who it's for, and where it's going")
            with st.form(key="telephony_quote_form", border=False):
                col_r, col_c = st.columns(2, gap="large")
                with col_r:
                    render_html(f'<div class="nl-form-h">{icon("building", 16)}Your company</div>')
                    r_company = st.text_input("Company name *", value=SETTINGS["company_name"], placeholder="e.g. Refyn-IT")
                    r_contact = st.text_input("Your name / account manager *", placeholder="e.g. John Doe")
                    r_email = st.text_input("Your email *", value=SETTINGS["company_email"], placeholder="e.g. sales@refyn-it.co.uk")
                    r_phone = st.text_input("Your phone", value=SETTINGS["company_phone"], placeholder="e.g. 0330 123 4567")
                with col_c:
                    render_html(f'<div class="nl-form-h">{icon("user", 16)}Proposed customer</div>')
                    c_company = st.text_input("Customer company *", placeholder="e.g. Apex Logistics Ltd")
                    c_contact = st.text_input("Customer contact *", placeholder="e.g. Sarah Jenkins")
                    c_email = st.text_input("Customer email *", placeholder="e.g. sarah@apexlogistics.co.uk")
                    c_phone = st.text_input("Customer phone", placeholder="e.g. 0161 123 4567")
                render_html(f'<div class="nl-form-h" style="margin-top:10px">{icon("truck", 16)}Delivery / site address'
                            ' <span style="color:var(--faint);font-weight:500">(optional for initial quotes)</span></div>')
                a1, a2, a3 = st.columns([2, 1, 1])
                with a1:
                    del_addr1 = st.text_input("Address line 1", placeholder="Building name or street")
                with a2:
                    del_city = st.text_input("Town / city", placeholder="Town / city")
                with a3:
                    del_postcode = st.text_input("Postcode", placeholder="Postcode")
                generate_submitted = st.form_submit_button("Save quotation & generate PDF", type="primary", **FULL_WIDTH)

            if generate_submitted:
                current_h_items = basket_items()
                if not r_company or not r_contact or not r_email:
                    st.error("Please complete your company details (company, name and email).")
                elif not c_company or not c_contact or not c_email:
                    st.error("Please fill in the customer's company, contact name and email.")
                elif st.session_state.num_licences == 0 and not current_h_items:
                    st.error("Add at least one user licence or a piece of hardware before generating a quote.")
                else:
                    quote_ref = f"{QUOTE_PREFIX}-{datetime.now().strftime('%y%m%d%H%M')}"
                    quote_date = datetime.now().strftime("%d %B %Y")
                    addr_parts = [p.strip() for p in [del_addr1, del_city, del_postcode] if p.strip()]
                    full_delivery = ", ".join(addr_parts) if addr_parts else "N/A"
                    reseller_info = {"company": r_company, "name": r_contact, "email": r_email, "phone": r_phone}
                    customer_info = {"company": c_company, "name": c_contact, "email": c_email, "phone": c_phone,
                                     "delivery": full_delivery}
                    quote_meta = {"ref": quote_ref, "date": quote_date}
                    dep_opt = st.session_state.deployment

                    pdf_bytes = generate_quotation_pdf(quote_meta, reseller_info, customer_info,
                                                       st.session_state.num_licences, current_h_items, dep_opt)
                    st.session_state.active_quote_pdf = pdf_bytes
                    st.session_state.active_quote_ref = quote_ref
                    st.session_state.active_quote_sig = quote_signature()
                    st.session_state.active_quote_customer = c_company
                    st.session_state.active_quote_details = {
                        "meta": quote_meta, "reseller": reseller_info, "customer": customer_info,
                    }
                    st.session_state.pop("partner_order_pdf", None)

                    hw_summary = ("; ".join(f"{i['name']} x{i['qty']}" for i in current_h_items)
                                  if current_h_items else "No Hardware (App/Licences Only)")
                    one_off_combined = total_one_off()
                    margin = reseller_margin(st.session_state.num_licences, dep_opt)
                    _ps = profit_summary(cost_sell_lines(st.session_state.num_licences, dep_opt, current_h_items))
                    record = {
                        "Quote Ref": [quote_ref], "Date": [quote_date], "Brand": [APP_NAME],
                        "Reseller": [r_company], "Account Manager": [r_contact],
                        "Customer Company": [c_company], "Customer Contact": [c_contact],
                        "Customer Email": [c_email], "Licences": [st.session_state.num_licences],
                        "Licence Rate (£)": [f"{LICENCE_MONTHLY_RATE:.2f}"],
                        "Ongoing Monthly Costs Ex VAT (£)": [f"{total_monthly_licences():.2f}"],
                        "Ongoing Monthly Costs Inc VAT (£)": [f"{total_monthly_licences() * (1 + VAT_RATE):.2f}"],
                        "User Setup Ex VAT (£)": [f"{total_setup_fee():.2f}"],
                        "Deployment Option": [DEPLOYMENT_LABELS[dep_opt]],
                        "Deployment Ex VAT (£)": [f"{deployment_fee():.2f}"],
                        "Hardware Total Ex VAT (£)": [f"{total_hardware_capex():.2f}"],
                        "Total One-Off Costs Ex VAT (£)": [f"{one_off_combined:.2f}"],
                        "Total One-Off Costs Inc VAT (£)": [f"{one_off_combined * (1 + VAT_RATE):.2f}"],
                        "Reseller Margin Monthly (£)": [f"{margin['monthly']:.2f}"],
                        "Reseller Margin One-Off (£)": [f"{margin['one_off']:.2f}"],
                        "Novalink Monthly Cost (£)": [f"{_ps['monthly_cost']:.2f}"],
                        "Novalink One-Off Cost (£)": [f"{_ps['oneoff_cost']:.2f}"],
                        f"Contract Profit {CONTRACT_MONTHS}m (£)": [f"{_ps['contract_total_profit']:.2f}"],
                        "Hardware Summary": [hw_summary], "Delivery Address": [full_delivery],
                    }
                    df = pd.DataFrame(record)
                    if not os.path.isfile(QUOTES_FILE):
                        df.to_csv(QUOTES_FILE, index=False)
                    else:
                        df.to_csv(QUOTES_FILE, mode="a", header=False, index=False)
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
            one_off_ex = total_one_off()
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
                    f'<div class="nl-line"><span class="n">User setup &amp; provisioning<small>× {users}</small></span>'
                    f'<span class="p">{money(total_setup_fee())}</span></div>'
                    f'<div class="nl-line"><span class="n">{esc(DEPLOYMENT_LABELS[st.session_state.deployment])}</span>'
                    f'<span class="p">{money(deployment_fee())}</span></div>'
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
                f'<div class="nl-term">{icon("alert", 14)}<span>Licences are on a <b>{CONTRACT_MONTHS}-month minimum term</b>.'
                f' Early termination charges apply. Quote valid for {QUOTE_VALID_DAYS} days.</span></div>'
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
                st.caption("Fill in step 04 to generate the official PDF.")

# ---------------- TAB 2: CUSTOMER VIEW ----------------
with tab_customer_view:
    users = st.session_state.get("num_licences", 0)
    mrc_ex = total_monthly_licences()
    mrc_vat = mrc_ex * VAT_RATE
    setup_ex = total_setup_fee()
    dep_ex = deployment_fee()
    dep_opt = st.session_state.deployment
    hw_ex = total_hardware_capex()
    one_off_ex = setup_ex + dep_ex + hw_ex
    one_off_vat = one_off_ex * VAT_RATE
    month1_ex = mrc_ex + one_off_ex
    items = basket_items()
    for_whom = st.session_state.get("active_quote_customer")

    _, mid, _ = st.columns([0.06, 1, 0.06])
    with mid:
        with st.container(key="card-cv-head"):
            render_html(
                f'<div class="rit-brandrow">{brand_logo_html(34)}{powered_by_html()}</div>'
                '<div class="nl-prop"><div>'
                '<div class="k">Proposal' + (f" · prepared for {esc(for_whom)}" if for_whom else "") + '</div>'
                '<div class="t">Your cloud <span>telephony solution</span></div>'
                '<div class="s">Unified communications for every user, on desk, laptop and mobile.</div></div>'
                f'<div>{chip(datetime.now().strftime("%d %B %Y"), "accent")}</div></div>'
                '<div class="nl-kpis">'
                f'<div class="nl-kpi" style="--c:#EA5624"><div class="l">Ongoing monthly</div><div class="v">{money(mrc_ex)} <small>ex VAT</small></div><div class="i">{money(mrc_ex + mrc_vat)} / mo inc VAT</div></div>'
                f'<div class="nl-kpi" style="--c:#D4D9DF"><div class="l">One-off upfront</div><div class="v">{money(one_off_ex)} <small>ex VAT</small></div><div class="i">{money(one_off_ex + one_off_vat)} inc VAT</div></div>'
                f'<div class="nl-kpi" style="--c:#34D399"><div class="l">Month 1 investment</div><div class="v">{money(month1_ex)} <small>ex VAT</small></div><div class="i">{money(month1_ex * (1 + VAT_RATE))} inc VAT</div></div>'
                "</div>"
            )

        with st.container(key="card-cv-monthly"):
            section_header("1", "Ongoing monthly costs", f"Per user, per month · {CONTRACT_MONTHS}-month minimum term")
            if users > 0:
                render_html(
                    '<table class="nl-table"><thead><tr><th>Service</th><th class="num">Users</th>'
                    '<th class="num">Unit (ex VAT)</th><th class="num">Monthly (ex VAT)</th></tr></thead><tbody>'
                    '<tr><td><b>Hosted VoIP cloud user licence</b><div class="desc">Apps, softphone, call recording,'
                    ' auto-attendant &amp; inclusive UK calls</div></td>'
                    f'<td class="num">{users}</td><td class="num">{money(LICENCE_MONTHLY_RATE)}</td><td class="num"><b>{money(mrc_ex)}</b></td></tr>'
                    f'<tr class="sub"><td colspan="3">Subtotal (ex VAT)</td><td class="num">{money(mrc_ex)}</td></tr>'
                    f'<tr class="sub"><td colspan="3">VAT @ {VAT_PCT}</td><td class="num">{money(mrc_vat)}</td></tr>'
                    f'<tr class="grand"><td colspan="3">Total monthly (inc VAT)</td><td class="num">{money(mrc_ex + mrc_vat)} / mo</td></tr>'
                    "</tbody></table>"
                )
            else:
                render_html('<div class="nl-empty">No user licences selected yet.</div>')

        _bs_cv = build_sheet_data() if "bs_hours_preset" in st.session_state else None
        if _bs_cv and users > 0:
            with st.container(key="card-cv-setup"):
                section_header("✓", "How your system will work", "Summary of your setup · confirm with your account manager")
                _named = [u for u in _bs_cv["users"] if str(u.get("First name", "")).strip()]
                if _bs_cv["ivr_on"] and _bs_cv["flow"]:
                    _route = "".join(
                        f'<div class="rit-cv-opt"><span class="key">{esc(r.get("Key", ""))}</span>'
                        f'<span class="o">{esc(r.get("Option", "") or "—")}</span>'
                        f'<span class="w">rings {esc(r.get("Who rings", "") or "to confirm")}, then {esc(str(r.get("If no answer", "")).lower())}</span></div>'
                        for r in _bs_cv["flow"])
                else:
                    _f = (_bs_cv["flow"] or [{}])[0]
                    _route = (f'<div class="rit-cv-opt"><span class="key">☎</span><span class="o">All calls</span>'
                              f'<span class="w">ring {esc(_f.get("Who rings", "") or "to confirm")}, then {esc(str(_f.get("If no answer", "")).lower())}</span></div>')
                render_html(
                    '<div class="rit-cv-setup">'
                    f'<div class="pe-panel"><div class="h">Opening hours</div><div class="big">{esc(bs_hours_summary(_bs_cv["hours"]))}</div>'
                    f'<div class="sm">Out of hours: {esc(_bs_cv["ooh_action"] or "")}</div></div>'
                    f'<div class="pe-panel"><div class="h">Callers hear</div><div class="sm">'
                    + (f'“{esc(_bs_cv["welcome_text"])}”<br>' if _bs_cv["welcome_on"] else "")
                    + ("Call-recording / GDPR notice<br>" if _bs_cv["gdpr_on"] else "")
                    + (f'“{esc(_bs_cv["menu_script"])}”' if _bs_cv["ivr_on"] and _bs_cv["menu_script"] else "")
                    + '</div></div>'
                    f'<div class="pe-panel"><div class="h">Users set up</div><div class="big">{len(_named)} of {users}</div>'
                    f'<div class="sm">{esc(", ".join((str(u.get("First name", "")) + " " + str(u.get("Last name", ""))).strip() for u in _named[:6]))}'
                    + (" …" if len(_named) > 6 else "") + '</div></div>'
                    '</div>'
                    f'<div class="nl-lines-h">Call routing</div>{_route}'
                )

        with st.container(key="card-cv-oneoff"):
            section_header("2", "One-off upfront costs", "Setup, deployment and hardware, billed once")
            rows = ""
            if users > 0:
                rows += (
                    '<tr><td><div style="display:flex;gap:12px;align-items:center"><div class="thumb">'
                    f'<span style="color:#EA5624">{icon("zap", 18)}</span></div><div><b>User setup &amp; provisioning</b>'
                    '<div class="desc">Extension setup, user provisioning and licence activation</div></div></div></td>'
                    f'<td class="num">{users}</td><td class="num">{money(SETUP_FEE_PER_USER)}</td><td class="num"><b>{money(setup_ex)}</b></td></tr>'
                    '<tr><td><div style="display:flex;gap:12px;align-items:center"><div class="thumb">'
                    f'<span style="color:#EA5624">{icon("truck", 18)}</span></div><div><b>{esc(DEPLOYMENT_LABELS[dep_opt])}</b>'
                    f'<div class="desc">{esc(DEPLOYMENT_DESCS[dep_opt])}</div></div></div></td>'
                    f'<td class="num">1</td><td class="num">{money(dep_ex)}</td><td class="num"><b>{money(dep_ex)}</b></td></tr>'
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
            if not rows:
                render_html('<div class="nl-empty">No one-off items yet.</div>')
            else:
                render_html(
                    '<table class="nl-table"><thead><tr><th>Item</th><th class="num">Qty</th>'
                    '<th class="num">Unit (ex VAT)</th><th class="num">Total (ex VAT)</th></tr></thead><tbody>'
                    + rows
                    + f'<tr class="sub"><td colspan="3">Subtotal (ex VAT)</td><td class="num">{money(one_off_ex)}</td></tr>'
                    f'<tr class="sub"><td colspan="3">VAT @ {VAT_PCT}</td><td class="num">{money(one_off_vat)}</td></tr>'
                    f'<tr class="grand"><td colspan="3">Total one-off (inc VAT)</td><td class="num">{money(one_off_ex + one_off_vat)}</td></tr>'
                    "</tbody></table>"
                )
            render_html(
                f'<div class="nl-note"><b>Commercial notes:</b> Quotation valid for {QUOTE_VALID_DAYS} calendar days.'
                f' User licences are subject to a {CONTRACT_MONTHS}-month minimum term. {esc(APP_NAME)} hosted telephony is powered by {esc(POWERED_BY)}.</div>'
            )

# ---------------- TAB 3: ADMIN · PRICING ----------------
with tab_admin:
    admin_pw = _secret("ADMIN_PASSWORD")
    _, amid, _ = st.columns([0.06, 1, 0.06])
    with amid:
        if not admin_pw:
            st.error("ADMIN_PASSWORD isn't set in Streamlit Secrets, so pricing admin is locked.")
        elif not st.session_state.get("admin_ok"):
            _, lc, _ = st.columns([1, 1.2, 1])
            with lc:
                with st.container(key="card-admin-login"):
                    render_html(f'<div class="nl-form-h">{icon("lock", 16)}Admin access</div>'
                                '<div class="rit-admin-note">Pricing changes are restricted. Enter the admin password.</div>')
                    with st.form("admin_login", border=False):
                        a_try = st.text_input("Admin password", type="password")
                        a_sub = st.form_submit_button("Unlock pricing", type="primary", **FULL_WIDTH)
                    if a_sub:
                        if hmac.compare_digest(a_try.encode("utf-8"), str(admin_pw).encode("utf-8")):
                            st.session_state.admin_ok = True
                            st.rerun()
                        else:
                            st.error("Incorrect admin password.")
        else:
            lk1, lk2 = st.columns([5, 1])
            with lk1:
                render_html(f'<div class="rit-admin-bar">{icon("lock", 14)}<span>Admin area · internal to '
                            f'{esc(SETTINGS["company_name"] or "Refyn-IT")} — never shown to customers</span></div>')
            with lk2:
                if st.button("Lock admin", key="admin_lock", **FULL_WIDTH):
                    st.session_state.admin_ok = False
                    st.rerun()

            sub_profit, sub_order, sub_pricing = st.tabs(["Profit", "Novalink order", "Pricing settings"])

            a_users = st.session_state.get("num_licences", 0)
            a_dep = st.session_state.deployment
            a_items = basket_items()
            a_lines = cost_sell_lines(a_users, a_dep, a_items)
            ps = profit_summary(a_lines)
            details = st.session_state.get("active_quote_details")

            # ===== PROFIT =====
            with sub_profit:
                with st.container(key="card-admin-profit"):
                    section_header("£", "Your profit on this deal",
                                   f"Your sell price minus what you pay {POWERED_BY} · {CONTRACT_MONTHS}-month contract")
                    if not a_lines:
                        render_html('<div class="nl-empty">Build a quote first (users, deployment, hardware) and your profit appears here.</div>')
                    else:
                        who = details["customer"]["company"] if details else "the current quote"
                        render_html(
                            f'<div class="rit-deal">{chip("Deal", "muted")}<b>{esc(who)}</b>'
                            f'<span>{a_users} users · {esc(DEPLOYMENT_LABELS[a_dep])}</span></div>'
                            '<div class="rit-pkpis">'
                            f'<div class="nl-kpi" style="--c:#EA5624"><div class="l">Monthly profit</div><div class="v">{money(ps["monthly_profit"])}</div>'
                            f'<div class="i">{money(ps["monthly_sell"])} billed − {money(ps["monthly_cost"])} to {POWERED_BY}</div></div>'
                            f'<div class="nl-kpi" style="--c:#FF9A5A"><div class="l">Annual profit</div><div class="v">{money(ps["annual_profit"])}</div>'
                            '<div class="i">Recurring, 12 months</div></div>'
                            f'<div class="nl-kpi" style="--c:#D4D9DF"><div class="l">One-off profit</div><div class="v">{money(ps["oneoff_profit"])}</div>'
                            '<div class="i">Setup, deployment &amp; hardware</div></div>'
                            f'<div class="nl-kpi rit-hero-kpi" style="--c:#34D399"><div class="l">{CONTRACT_MONTHS}-month contract profit</div>'
                            f'<div class="v">{money(ps["contract_total_profit"])}</div>'
                            f'<div class="i">{money(ps["contract_recurring_profit"])} recurring + {money(ps["oneoff_profit"])} one-off'
                            f' · {ps["margin_pct"]:.1f}% margin</div></div>'
                            '</div>'
                        )
                        rows = ""
                        for kind, label in (("monthly", "Monthly recurring"), ("one_off", "One-off")):
                            sel = [ln for ln in a_lines if ln["kind"] == kind]
                            if not sel:
                                continue
                            rows += f'<tr class="grp"><td colspan="5">{label}</td></tr>'
                            for ln in sel:
                                pcls = "pos" if ln["profit"] > 0 else "zero"
                                rows += (
                                    f'<tr><td><b>{esc(ln["name"])}</b></td><td class="num">{ln["qty"]}</td>'
                                    f'<td class="num">{money(ln["cost_unit"])}</td><td class="num">{money(ln["sell_unit"])}</td>'
                                    f'<td class="num"><span class="rit-p {pcls}">{money(ln["profit"])}</span></td></tr>'
                                )
                        render_html(
                            '<table class="nl-table"><thead><tr><th>Line</th><th class="num">Qty</th>'
                            f'<th class="num">You pay {POWERED_BY}</th><th class="num">You charge</th><th class="num">Profit</th></tr></thead>'
                            f'<tbody>{rows}'
                            f'<tr class="sub"><td colspan="4">Contract revenue ({CONTRACT_MONTHS} months, ex VAT)</td><td class="num">{money(ps["contract_revenue"])}</td></tr>'
                            f'<tr class="sub"><td colspan="4">Paid to {POWERED_BY} ({CONTRACT_MONTHS} months, ex VAT)</td><td class="num">{money(ps["contract_cost"])}</td></tr>'
                            f'<tr class="grand"><td colspan="4">Contract profit (ex VAT)</td><td class="num">{money(ps["contract_total_profit"])}</td></tr>'
                            '</tbody></table>'
                            '<div class="nl-note">Hardware is currently supplied at catalogue price, so it carries no profit. '
                            'Advanced system deployment is a fixed Novalink price, so it also carries no profit. '
                            'Raise your licence, setup or Basic build prices under <b>Pricing settings</b> to grow your margin.</div>'
                        )

            # ===== NOVALINK ORDER =====
            with sub_order:
                with st.container(key="card-admin-order"):
                    section_header("⇄", f"{POWERED_BY} partner order",
                                   f"What you pay {POWERED_BY} for this deal · your sell prices are never included")
                    if not a_lines:
                        render_html('<div class="nl-empty">Build a quote first, then create the partner order here.</div>')
                    else:
                        render_html(
                            '<div class="nl-kpis" style="margin-top:0">'
                            f'<div class="nl-kpi" style="--c:#38BDF8"><div class="l">Monthly to {POWERED_BY}</div><div class="v">{money(ps["monthly_cost"])}</div>'
                            f'<div class="i">{money(ps["monthly_cost"] * (1 + VAT_RATE))} inc VAT</div></div>'
                            f'<div class="nl-kpi" style="--c:#38BDF8"><div class="l">One-off to {POWERED_BY}</div><div class="v">{money(ps["oneoff_cost"])}</div>'
                            f'<div class="i">{money(ps["oneoff_cost"] * (1 + VAT_RATE))} inc VAT</div></div>'
                            f'<div class="nl-kpi" style="--c:#38BDF8"><div class="l">Month 1 payable</div><div class="v">{money(ps["monthly_cost"] + ps["oneoff_cost"])}</div>'
                            f'<div class="i">{money((ps["monthly_cost"] + ps["oneoff_cost"]) * (1 + VAT_RATE))} inc VAT</div></div>'
                            '</div>'
                        )
                        orow = "".join(
                            f'<tr><td><b>{esc(ln["name"])}</b><div class="desc">{esc(ln["desc"])}</div></td>'
                            f'<td class="num">{ln["qty"]}</td><td class="num">{money(ln["cost_unit"])}{" / mo" if ln["kind"] == "monthly" else ""}</td>'
                            f'<td class="num"><b>{money(ln["cost_total"])}{" / mo" if ln["kind"] == "monthly" else ""}</b></td></tr>'
                            for ln in a_lines
                        )
                        render_html(
                            '<table class="nl-table" style="margin-top:14px !important"><thead><tr><th>Item</th><th class="num">Qty</th>'
                            '<th class="num">Partner price</th><th class="num">Total (ex VAT)</th></tr></thead>'
                            f'<tbody>{orow}</tbody></table>'
                        )
                        if not details:
                            render_html(f'<div class="pe-hint">{icon("alert", 14)}<span>Generate the customer quote first '
                                        '(Build quotation → step 04). The partner order uses the same customer and reference.</span></div>')
                        else:
                            if st.session_state.get("active_quote_sig") != quote_signature():
                                st.warning("The quote has changed since the customer PDF was made. "
                                           "Regenerate the customer quote first so both documents match.")
                            else:
                                if st.button(f"Create {POWERED_BY} partner order PDF", type="primary",
                                             key="mk_partner", **FULL_WIDTH):
                                    cref = details["meta"]["ref"]
                                    order_meta = {"ref": cref.replace(QUOTE_PREFIX, "NLP", 1), "customer_ref": cref,
                                                  "date": datetime.now().strftime("%d %B %Y")}
                                    st.session_state.partner_order_pdf = generate_partner_order_pdf(
                                        order_meta, details["reseller"], details["customer"], a_lines,
                                        build_sheet=build_sheet_data(), n_users=a_users)
                                    st.session_state.partner_order_ref = order_meta["ref"]
                                if st.session_state.get("partner_order_pdf"):
                                    st.download_button(
                                        f"Download {st.session_state.partner_order_ref}.pdf",
                                        data=st.session_state.partner_order_pdf,
                                        file_name=f"{st.session_state.partner_order_ref}.pdf",
                                        mime="application/pdf", key="dl_partner", **FULL_WIDTH)
                                    st.caption(f"Send this to {POWERED_BY} to place the order. It shows only partner prices "
                                               "and the end customer's name and site, with the system build sheet attached.")
                                    _bs_now = build_sheet_data()
                                    _chk = build_sheet_checks(_bs_now, a_users)
                                    _missing = [lbl for lbl, ok in _chk if not ok]
                                    if _missing:
                                        st.info("Build sheet still to complete: " + ", ".join(_missing) +
                                                " (Build quotation → 02 Deployment → System setup details).")
                                    if _bs_now["users"]:
                                        st.download_button("Download users list (CSV)", data=users_csv(_bs_now),
                                                           file_name=f"{st.session_state.partner_order_ref}-users.csv",
                                                           mime="text/csv", key="dl_users_csv", **FULL_WIDTH)

            # ===== PRICING SETTINGS =====
            with sub_pricing:
                with st.container(key="card-admin"):
                    section_header("⚙", "Pricing & quote settings",
                                   "Your sell prices. Floors are set by Novalink — you can go up, never below.")
                    storage = "GitHub (permanent)" if _gh_config() else "Local file (resets on app restart)"
                    render_html(
                        '<div class="pe-chips" style="margin-bottom:14px">'
                        + chip(f"Storage: {storage}", "good" if _gh_config() else "warn")
                        + (chip(f"Last saved {SETTINGS['updated']}", "muted") if SETTINGS["updated"] else "")
                        + "</div>"
                    )

                    _v = SETTINGS["updated"] or "0"
                    with st.form("admin_pricing", border=False):
                        render_html('<div class="rit-admin-h">Monthly</div>')
                        p1, p2 = st.columns([1, 1.4], gap="large")
                        with p1:
                            new_lic = st.number_input("Licence sell price (£ / user / month)", min_value=FLOOR_LICENCE_MONTHLY,
                                                      value=float(LICENCE_MONTHLY_RATE), step=0.50, format="%.2f", key=f"adm_lic_{_v}")
                        with p2:
                            render_html(f'<div class="rit-floor">{icon("lock", 13)}Floor {money(FLOOR_LICENCE_MONTHLY)} / user / month.'
                                        ' Everything above is your margin.</div>')

                        render_html('<div class="rit-admin-h">One-off</div>')
                        p3, p4 = st.columns([1, 1.4], gap="large")
                        with p3:
                            new_setup = st.number_input("User setup fee (£ / user, one-off)", min_value=FLOOR_SETUP_PER_USER,
                                                        value=float(SETUP_FEE_PER_USER), step=1.00, format="%.2f", key=f"adm_setup_{_v}")
                        with p4:
                            render_html(f'<div class="rit-floor">{icon("lock", 13)}Floor {money(FLOOR_SETUP_PER_USER)} per user.'
                                        ' New quotes default to your saved price.</div>')
                        p5, p6 = st.columns([1, 1.4], gap="large")
                        with p5:
                            new_basic = st.number_input("Basic system build (£, one-off)", min_value=FLOOR_BASIC_DEPLOYMENT,
                                                        value=float(BASIC_DEPLOYMENT_FEE), step=5.00, format="%.2f", key=f"adm_basic_{_v}")
                        with p6:
                            render_html(f'<div class="rit-floor">{icon("lock", 13)}Floor {money(FLOOR_BASIC_DEPLOYMENT)}.'
                                        ' Device activation, self-installation.</div>')

                        new_default = st.radio("Default deployment on new quotes", [DEPLOY_BASIC, DEPLOY_ADVANCED],
                                               index=0 if SETTINGS["default_deployment"] == DEPLOY_BASIC else 1,
                                               format_func=lambda o: DEPLOYMENT_LABELS[o], horizontal=True)

                        render_html('<div class="rit-admin-h">Quote defaults</div>')
                        q1, q2, q3 = st.columns(3)
                        with q1:
                            new_cname = st.text_input("Company name on quotes", value=SETTINGS["company_name"])
                        with q2:
                            new_cemail = st.text_input("Default sales email", value=SETTINGS["company_email"])
                        with q3:
                            new_cphone = st.text_input("Default sales phone", value=SETTINGS["company_phone"])

                        save = st.form_submit_button("Save pricing", type="primary", **FULL_WIDTH)

                    if save:
                        ok, msg = save_settings({
                            "licence_monthly": new_lic, "setup_per_user": new_setup, "basic_deployment": new_basic,
                            "default_deployment": new_default, "company_name": new_cname,
                            "company_email": new_cemail, "company_phone": new_cphone,
                        })
                        st.session_state.admin_flash = ("success" if ok else "warning", msg)
                        st.rerun()
                    flash = st.session_state.pop("admin_flash", None)
                    if flash:
                        getattr(st, flash[0])(flash[1])

                # Advanced tariff (locked) + margin preview
                with st.container(key="card-admin-tariff"):
                    section_header("🔒", "Advanced system deployment", "Fixed Novalink tariff · not editable")
                    bands = advanced_bands()
                    trows = "".join(
                        f'<tr><td>{a}–{b} users</td><td class="num"><b>{money(advanced_deployment_price(b))}</b></td></tr>'
                        for a, b in bands
                    )
                    render_html(
                        '<table class="nl-table"><thead><tr><th>Users on system</th><th class="num">Price (ex VAT)</th></tr></thead>'
                        f'<tbody>{trows}<tr class="sub"><td colspan="2">…then +{money(ADVANCED_PRICE_PER_EXTRA_BAND)} for each further band of {ADVANCED_EXTRA_BAND_SIZE} users.</td></tr></tbody></table>'
                    )

# ---------------- Hero (rendered last so the stepper reflects this run) ----------------
if st.session_state.get("num_licences", 0) == 0 and not st.session_state.basket:
    _step = 1
elif "active_quote_pdf" in st.session_state and st.session_state.get("active_quote_sig") == quote_signature():
    _step = 5
elif st.session_state.basket:
    _step = 4
else:
    _step = 3
render_html(hero_html(_step), target=hero_slot)
