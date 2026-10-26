# ==========================================
# CINEVERSE  |  Movie booking app (Streamlit)
# ==========================================
import re
import io
import html
import base64
import mimetypes
import sqlite3
import smtplib
import textwrap
from pathlib import Path
from contextlib import closing
from datetime import datetime, date, timedelta
from email.message import EmailMessage

import streamlit as st
import streamlit.components.v1 as components

# ---------- CONFIG ----------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "movies.db")
POSTER_DIR = BASE_DIR / "posters"          # Leo.jpg, Vikram.png ...
LOGO_DIR = BASE_DIR / "logos"              # cineverse.png = site logo, optional theatre logos
POSTER_EXTS = (".jpg", ".jpeg", ".png", ".webp")
LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")

SEAT_ROWS = ["A", "B", "C", "D"]
SEATS_PER_SIDE = 3                         # 3 seats | aisle | 3 seats
ALL_SEATS = [f"{r}{i}" for r in SEAT_ROWS for i in range(1, SEATS_PER_SIDE * 2 + 1)]
DATE_WINDOW = 7                            # days ahead that can be booked
MAX_CHAT_SEATS = 10

# Locations -> theatres. Edit / add freely.
THEATRES = {
    "Anna Nagar": ["CINEVERSE Anna Nagar Grand", "CINEVERSE Anna Nagar Prime"],
    "T. Nagar": ["CINEVERSE Panagal Park", "CINEVERSE T. Nagar Luxe"],
    "Velachery": ["CINEVERSE Velachery Mall", "CINEVERSE Velachery Max"],
}
LOCATIONS = list(THEATRES)
THEATRE_LOCATION = {t: loc for loc, ts in THEATRES.items() for t in ts}
ALL_THEATRES = list(THEATRE_LOCATION)

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
          "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


# ---------- BASIC HELPERS ----------
def _slug(text):
    return re.sub(r"[^a-z0-9]+", "", str(text).lower())


def find_image(folder, name, exts):
    if not folder.is_dir():
        return None
    key = _slug(name)
    for f in folder.iterdir():
        if f.suffix.lower() in exts and _slug(f.stem) == key:
            return f
    return None


BRAND_LOGO = find_image(LOGO_DIR, "cineverse", LOGO_EXTS)

st.set_page_config(
    page_title="CINEVERSE | Book Your Show",
    page_icon=str(BRAND_LOGO) if BRAND_LOGO else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- LOGOS & ICONS (inline SVG, no emoji) ----------
CINEVERSE_MARK = ('<svg width="36" height="36" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">'
                  '<defs><linearGradient id="cvg" x1="0" y1="0" x2="1" y2="1">'
                  '<stop offset="0" stop-color="#c41e3a"/><stop offset="1" stop-color="#6b0f20"/>'
                  '</linearGradient></defs>'
                  '<rect width="40" height="40" rx="11" fill="url(#cvg)"/>'
                  '<circle cx="20" cy="20" r="11.5" fill="none" stroke="#fff" stroke-width="2.4"/>'
                  '<circle cx="20" cy="20" r="3.2" fill="#fff"/>'
                  '<circle cx="20" cy="12.2" r="2.4" fill="#fff"/><circle cx="20" cy="27.8" r="2.4" fill="#fff"/>'
                  '<circle cx="12.2" cy="20" r="2.4" fill="#fff"/><circle cx="27.8" cy="20" r="2.4" fill="#fff"/>'
                  '</svg>')

GOOGLE_G_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
                '<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>'
                '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>'
                '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>'
                '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>'
                '</svg>')

TICKET_ICON_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" '
                   'stroke="#ffffff" stroke-width="2" stroke-linejoin="round">'
                   '<path d="M3 9a2 2 0 0 0 0 6v3a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-3a2 2 0 0 1 0-6V6a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1z"/>'
                   '<line x1="15" y1="6" x2="15" y2="18" stroke-dasharray="2 2"/></svg>')


def svg_uri(svg):
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


@st.cache_data(show_spinner=False)
def _file_to_data_uri(path_str, mtime):
    mime = mimetypes.guess_type(path_str)[0] or "image/jpeg"
    data = base64.b64encode(Path(path_str).read_bytes()).decode()
    return f"data:{mime};base64,{data}"


def file_uri(path):
    return _file_to_data_uri(str(path), path.stat().st_mtime)


def brand_mark_html(css_class="brand-img"):
    if BRAND_LOGO:
        return f'<img src="{file_uri(BRAND_LOGO)}" alt="CINEVERSE logo" class="{css_class}">'
    return CINEVERSE_MARK


def esc(value):
    return html.escape(str(value))


def inr(value):
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return f"₹{value}"


def sum_row(label, value):
    return f'<div class="sum-row"><span>{esc(label)}</span><span>{esc(value)}</span></div>'


def today_date():
    return datetime.now().date()


def date_options():
    t = today_date()
    return [t + timedelta(days=i) for i in range(DATE_WINDOW)]


def date_label(d):
    t = today_date()
    if d == t:
        return f"Today, {d.day} {d:%b}"
    if d == t + timedelta(days=1):
        return f"Tomorrow, {d.day} {d:%b}"
    return f"{d:%a}, {d.day} {d:%b}"


def date_long(d):
    return f"{d:%a}, {d.day} {d:%b %Y}"


def venue_card_html(theatre):
    short = theatre.replace("CINEVERSE ", "")
    logo_file = find_image(LOGO_DIR, short, LOGO_EXTS)
    logo = (f'<img src="{file_uri(logo_file)}" alt="{esc(short)} logo">'
            if logo_file else CINEVERSE_MARK)
    return (f'<div class="venue"><div class="venue-logo">{logo}</div>'
            f'<div><div class="venue-name">{esc(theatre)}</div>'
            f'<div class="venue-loc">{esc(THEATRE_LOCATION[theatre])}, Chennai</div></div></div>')


# ==========================================
# GOOGLE LOGIN GATE
# ==========================================
LOGIN_CSS = """
<style>
.stApp {
    background: radial-gradient(ellipse at top, #25234a 0%, #10101d 48%, #080810 100%);
}
.welcome {
    min-height: 68vh; display: flex; flex-direction: column; justify-content: center;
    align-items: center; text-align: center; padding: 35px 15px;
}
.brand {
    display: flex; align-items: center; gap: 12px; font-size: 14px; letter-spacing: 6px;
    color: #d6d3ff; font-weight: 700; margin-bottom: 25px;
}
.brand-img { width: 40px; height: 40px; border-radius: 11px; }
.hero { font-size: clamp(38px, 7vw, 68px); font-weight: 850; line-height: 1.1; color: white; margin-bottom: 18px; }
.hero span {
    background: linear-gradient(90deg, #aaa4ff, #f1b7ff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.subtitle { color: #c1bfd4; font-size: 17px; max-width: 440px; line-height: 1.7; margin-bottom: 32px; }
.st-key-google_login button {
    min-height: 52px; border-radius: 14px; font-weight: 700;
    border: 1px solid #ffffff; background: #ffffff; color: #1a1a2e;
    display: flex; align-items: center; justify-content: center;
}
.st-key-google_login button:hover { border-color: #aaa4ff; color: #1a1a2e; transform: translateY(-2px); }
.st-key-google_login button::before {
    content: ""; display: inline-block; width: 20px; height: 20px; margin-right: 10px;
    background: url("__GOOGLE__") center / contain no-repeat;
}
</style>
"""

if not st.user.is_logged_in:
    st.markdown(LOGIN_CSS.replace("__GOOGLE__", svg_uri(GOOGLE_G_SVG)), unsafe_allow_html=True)
    st.markdown(
        '<div class="welcome">'
        f'<div class="brand">{brand_mark_html()}<span>CINEVERSE</span></div>'
        '<div class="hero">Your Next Movie.<br><span>Your Next Experience.</span></div>'
        '<div class="subtitle">Discover movies, choose your seats, and book your perfect '
        'cinema experience, all in one place.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.button("Continue with Google", key="google_login",
                  use_container_width=True, on_click=st.login)
        st.caption("Secure sign-in | Your cinema experience starts here")
    st.stop()

google_name = st.user.get("name", "Movie Lover")
google_email = st.user.get("email", "")
google_picture = st.user.get("picture", "")

# ---------- COMPACT PROFILE ----------
st.markdown("""
<style>
.profile-name { font-size: 14px; font-weight: 700; color: #ffffff; }
.profile-email { font-size: 11px; color: #c7c5df; }
div[data-testid="stPopover"] > button {
    border: 1px solid #38325f; border-radius: 14px; background: #211d3c; color: white; padding: 8px 12px;
}
div[data-testid="stPopover"] > button:hover { border-color: #8d7cff; color: white; }
</style>
""", unsafe_allow_html=True)

_, profile_col = st.columns([5, 1.6])
with profile_col:
    with st.popover(google_name, use_container_width=True):
        if google_picture:
            st.image(google_picture, width=65)
        st.markdown(f"**{google_name}**")
        st.caption(google_email)
        st.divider()
        if st.button("Logout", key="cineverse_profile_logout", use_container_width=True):
            st.logout()

# ==========================================
# STYLES
# ==========================================
APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    color-scheme: light;
    --bg: #f7f5f2; --card: #ffffff; --ink: #1a1a2e; --muted: #5f5f73; --line: #e2ddd5;
    --brand: #c41e3a; --brand-dark: #a3162f; --brand-soft: #fdf1f3;
}
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ---------- Base ---------- */
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg); color: var(--ink); color-scheme: light; }
.block-container { max-width: 1240px; padding-top: 1rem; padding-bottom: 4rem; }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp label, .stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stMarkdownContainer"] p { color: var(--ink); }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p { color: var(--muted); }
hr { border-color: var(--line); margin: 28px 0; }

/* ---------- Inputs: white box + dark text ---------- */
[data-testid="stTextInputRootElement"],
[data-testid="stTextInputRootElement"] > div,
[data-testid="stNumberInputContainer"],
[data-testid="stNumberInputContainer"] > div,
div[data-baseweb="input"], div[data-baseweb="base-input"],
div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {
    background: #ffffff !important; background-color: #ffffff !important;
}
[data-testid="stTextInputRootElement"],
[data-testid="stNumberInputContainer"],
div[data-baseweb="input"], div[data-baseweb="select"] > div {
    border: 1.5px solid #cfc9bf !important; border-radius: 12px !important; overflow: hidden;
}
[data-testid="stTextInputRootElement"]:focus-within,
[data-testid="stNumberInputContainer"]:focus-within,
div[data-baseweb="input"]:focus-within {
    border-color: var(--brand) !important; box-shadow: 0 0 0 3px rgba(196,30,58,.12);
}
.stApp input, .stApp textarea,
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {
    background: #ffffff !important; color: #111111 !important;
    -webkit-text-fill-color: #111111 !important; caret-color: var(--brand); font-weight: 500;
}
.stApp input::placeholder, .stApp textarea::placeholder {
    color: #7b7b8c !important; -webkit-text-fill-color: #7b7b8c !important; opacity: 1;
}
[data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"],
[data-testid="stNumberInput"] button {
    background: #f1ede7 !important; color: #111111 !important; border: none !important;
    border-left: 1px solid #e2ddd5 !important; border-radius: 0 !important; min-height: 0 !important;
}
[data-testid="stNumberInputStepUp"]:hover, [data-testid="stNumberInputStepDown"]:hover,
[data-testid="stNumberInput"] button:hover { background: #e6e0d7 !important; color: var(--brand) !important; }
[data-testid="stNumberInput"] button svg, [data-testid="stNumberInput"] button svg * {
    fill: #111111 !important; color: #111111 !important; stroke: none;
}
div[data-baseweb="popover"] ul, div[data-baseweb="popover"] li,
div[data-baseweb="menu"], ul[role="listbox"], li[role="option"] {
    background: #ffffff !important; color: #111111 !important;
}
li[role="option"]:hover { background: var(--brand-soft) !important; }
div[data-baseweb="select"] span, div[data-baseweb="select"] div { color: #111111 !important; }

/* alerts */
div[data-testid="stAlert"] {
    background: #ffffff !important; border: 1px solid var(--line);
    border-left: 4px solid var(--brand); border-radius: 14px;
}
div[data-testid="stAlert"] *, div[data-testid="stAlert"] p { color: var(--ink) !important; }
div[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }

/* ---------- Nav ---------- */
.nav { display:flex; align-items:center; justify-content:space-between;
       padding: 10px 0 18px 0; margin-bottom: 18px; border-bottom: 1px solid var(--line); }
.logo { display:flex; align-items:center; gap:10px; font-size: 24px; font-weight: 800;
        letter-spacing: 1px; color: var(--ink); }
.logo span { color: var(--brand); }
.logo .brand-img { width: 36px; height: 36px; border-radius: 10px; }
.pill { font-size: 11px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase;
        color: var(--brand); background: var(--brand-soft); padding: 6px 12px; border-radius: 99px; }

/* ---------- Hero ---------- */
.st-key-hero { background: linear-gradient(150deg, #ffffff 0%, #fdf3f4 100%);
               border: 1px solid var(--line); border-radius: 24px; padding: 34px 34px 22px 34px;
               margin-bottom: 30px; }
.eyebrow { color: var(--brand); font-size: 11px; font-weight: 700; letter-spacing: 2.5px;
           text-transform: uppercase; margin-bottom: 8px; }
.headline { font-size: clamp(30px, 4vw, 46px); line-height: 1.1; font-weight: 800;
            letter-spacing: -1.4px; color: var(--ink); margin-bottom: 10px; }
.sub { color: var(--muted); font-size: 15px; line-height: 1.6; max-width: 540px; margin-bottom: 18px; }

/* ---------- Section headers ---------- */
.sec-title { font-size: 20px; font-weight: 800; letter-spacing: -.4px; color: var(--ink); margin: 6px 0 2px 0; }
.sec-sub { font-size: 13px; color: var(--muted); margin-bottom: 14px; }

/* ---------- Buttons ---------- */
.stApp button[kind="secondary"], .stApp button[data-testid="stBaseButton-secondary"] {
    background: #ffffff; color: #111111; border: 1.5px solid #cfc9bf;
    border-radius: 12px; font-weight: 600; min-height: 42px; transition: all .15s ease; }
.stApp button[kind="secondary"]:hover, .stApp button[data-testid="stBaseButton-secondary"]:hover {
    border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }
.stApp button[kind="primary"], .stApp button[data-testid="stBaseButton-primary"] {
    background: var(--brand); color: #ffffff; border: 1.5px solid var(--brand);
    border-radius: 12px; font-weight: 700; min-height: 42px; transition: all .15s ease; }
.stApp button[kind="primary"]:hover, .stApp button[data-testid="stBaseButton-primary"]:hover {
    background: var(--brand-dark); border-color: var(--brand-dark); color: #ffffff; }
.stApp button:disabled { opacity: 1; background: #e9e4dd !important; color: #6b645b !important;
    border-color: #d9d3ca !important; cursor: not-allowed; }
.stApp button p { color: inherit !important; }

/* ---------- Movie cards ---------- */
[class*="st-key-mcard_"] { background: var(--card); border: 1.5px solid var(--line);
    border-radius: 20px; padding: 0 0 14px 0; overflow: hidden; transition: all .2s ease; }
[class*="st-key-mcard_"]:hover { box-shadow: 0 10px 28px rgba(26,26,46,.10); transform: translateY(-2px); }
[class*="st-key-mcard_sel_"] { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(196,30,58,.12); }
[class*="st-key-mcard_"] > div { gap: .6rem; }
[class*="st-key-mcard_"] .stButton { padding: 0 14px; }
.poster { position: relative; aspect-ratio: 4 / 5; overflow: hidden; background: #d9d3ca; }
.poster img { width: 100%; height: 100%; object-fit: cover; object-position: top; display: block; }
.poster-fallback { display:flex; align-items:center; justify-content:center; padding: 18px; text-align:center; }
.poster-title { color:#ffffff; font-size: 28px; font-weight: 800; letter-spacing: -.6px; line-height: 1.1;
    text-shadow: 0 4px 16px rgba(0,0,0,.35); }
.poster-lang { position:absolute; top:12px; left:12px; z-index: 2; font-size: 10px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase; color:#ffffff; background: rgba(0,0,0,.6);
    padding: 5px 10px; border-radius: 99px; }
.mc-body { padding: 0 16px; }
.mc-name { font-size: 17px; font-weight: 800; color: var(--ink); letter-spacing: -.3px; }
.mc-price { font-size: 14px; font-weight: 700; color: var(--brand); margin-top: 2px; }
.mc-price small { color: var(--muted); font-weight: 500; font-size: 11px; }

/* ---------- Venue card (theatre + logo) ---------- */
.venue { display:flex; align-items:center; gap:14px; background:#ffffff; border:1px solid var(--line);
         border-radius:16px; padding:12px 16px; margin-top:6px; }
.venue-logo { width:48px; height:48px; flex:none; border-radius:12px; background:#ffffff;
              display:flex; align-items:center; justify-content:center; overflow:hidden; }
.venue-logo img { width:100%; height:100%; object-fit:contain; }
.venue-name { font-weight:700; color:var(--ink); font-size:15px; }
.venue-loc { font-size:12px; color:var(--muted); margin-top:2px; }

/* ---------- Stepper ---------- */
.steps { display:flex; align-items:center; margin: 26px 0 22px 0; flex-wrap: wrap; gap: 4px 0; }
.step { display:flex; align-items:center; gap:8px; }
.step-num { width:28px; height:28px; border-radius:50%; display:flex; align-items:center;
    justify-content:center; font-size:12px; font-weight:700; background:#e2ddd5; color:#5f5f73; }
.step-label { font-size:13px; font-weight:600; color:#5f5f73; }
.step.active .step-num { background: var(--brand); color:#ffffff; }
.step.active .step-label { color: var(--ink); }
.step.done .step-num { background: var(--ink); color:#ffffff; }
.step.done .step-label { color: var(--ink); }
.step-line { width:44px; height:2px; background:#e2ddd5; margin:0 10px; }
.step-line.done { background: var(--ink); }

/* ---------- Panels ---------- */
.st-key-details, .st-key-seatmap, .st-key-summary, .st-key-review, .st-key-concierge, .st-key-where {
    background: var(--card); border: 1px solid var(--line); border-radius: 20px; padding: 22px; }
.st-key-review { border-color: var(--brand); background: #fffafb; }

/* ---------- Seat map ---------- */
.screen { text-align:center; font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
    color: var(--muted); margin-bottom: 6px; }
.screen-bar { height: 4px; background: linear-gradient(90deg, transparent, var(--brand), transparent);
    border-radius: 50%; margin: 0 12% 22px 12%; opacity:.8; }
.row-label { font-size: 12px; font-weight: 700; color: var(--muted); text-align:center; padding-top: 11px; }
.st-key-seatmap button { min-height: 40px; padding: 0; border-radius: 9px; font-size: 13px; }
.st-key-seatmap button:disabled { text-decoration: line-through; }
.legend { display:flex; gap:18px; justify-content:center; flex-wrap: wrap; margin-top: 14px; font-size: 12px; color: var(--muted); }
.legend i { display:inline-block; width:12px; height:12px; border-radius:4px; margin-right:6px; vertical-align:-2px; }

/* ---------- Summary / receipt ---------- */
.sum-title { font-size: 16px; font-weight: 800; color: var(--ink); margin-bottom: 14px; }
.sum-row { display:flex; justify-content:space-between; gap:12px; margin-bottom: 11px; font-size: 13px; }
.sum-row span:first-child { color: var(--muted); }
.sum-row span:last-child { color: var(--ink); font-weight: 600; text-align:right; }
.sum-div { border-top: 1px dashed #cfc9bf; margin: 14px 0; }
.sum-total-label { font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: var(--muted); }
.sum-total { font-size: 30px; font-weight: 800; color: var(--brand); letter-spacing: -1px; }
.ticket { background: #ffffff; border: 1.5px dashed #cfc9bf; border-radius: 20px; overflow: hidden; margin-bottom: 22px; }
.ticket-head { background: var(--ink); color:#ffffff; padding: 14px 20px; display:flex;
    justify-content:space-between; align-items:center; font-weight:700; }
.ticket-head b { letter-spacing: 2px; color: #ff9aaa; }
.ticket-body { padding: 18px 20px 6px 20px; }
.ticket-note { padding: 0 20px 16px 20px; font-size: 12px; color: var(--muted); }

/* ---------- Chat ---------- */
div[data-testid="stChatMessage"] { background:#faf8f5; border:1px solid var(--line);
    border-radius: 16px; padding: 12px 14px; }
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li { color: var(--ink) !important; }
.cv-footer { text-align:center; color:#6f6f80; font-size:12px; padding: 28px 0 6px 0; }

/* ---------- Floating 3D tickets button ---------- */
.st-key-ticket_fab { position: fixed; right: 16px; top: 46%; z-index: 9999; width: auto !important;
    animation: fabfloat 3.2s ease-in-out infinite; }
.st-key-ticket_fab button {
    height: 58px; min-height: 58px; min-width: 156px; padding: 0 22px 0 18px; border-radius: 18px;
    display: flex; align-items: center; justify-content: center; gap: 10px;
    border: 1px solid rgba(255,255,255,.35) !important;
    background: linear-gradient(180deg, #e0364f 0%, #c41e3a 55%, #9a1530 100%) !important;
    box-shadow: 0 7px 0 #6e0f22, 0 16px 28px rgba(110,15,34,.42),
                inset 0 2px 0 rgba(255,255,255,.35), inset 0 -3px 0 rgba(0,0,0,.2);
    transform: perspective(500px) rotateX(10deg);
    transition: transform .12s ease, box-shadow .12s ease;
}
.st-key-ticket_fab button::before {
    content: ""; width: 24px; height: 24px; flex: none;
    background: url("__TICKET__") center / contain no-repeat;
    filter: drop-shadow(0 2px 2px rgba(0,0,0,.25));
}
.st-key-ticket_fab button p { color: #ffffff !important; margin: 0; font-size: 15px; font-weight: 800; letter-spacing: .3px; }
.st-key-ticket_fab button:hover {
    transform: perspective(500px) rotateX(0deg) translateY(-3px);
    box-shadow: 0 10px 0 #6e0f22, 0 22px 34px rgba(110,15,34,.5),
                inset 0 2px 0 rgba(255,255,255,.4), inset 0 -3px 0 rgba(0,0,0,.2);
    border-color: rgba(255,255,255,.6) !important;
}
.st-key-ticket_fab button:active {
    transform: perspective(500px) rotateX(14deg) translateY(5px);
    box-shadow: 0 2px 0 #6e0f22, 0 6px 12px rgba(110,15,34,.35), inset 0 3px 6px rgba(0,0,0,.25);
}
@keyframes fabfloat { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-4px); } }

@media (max-width: 768px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .st-key-hero { padding: 22px 18px 14px 18px; }
    .step-line { width: 20px; }
    .st-key-ticket_fab { top: auto; bottom: 18px; right: 12px; }
    .st-key-ticket_fab button { min-width: 0; height: 52px; min-height: 52px; padding: 0 16px; }
}
"""
st.markdown("<style>" + APP_CSS.replace("__TICKET__", svg_uri(TICKET_ICON_SVG)) + "</style>",
            unsafe_allow_html=True)


# ==========================================
# DATABASE
# ==========================================
def init_bookings_table():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                movie_name TEXT NOT NULL,
                show_time TEXT NOT NULL,
                ticket_count INTEGER NOT NULL,
                selected_seats TEXT NOT NULL,
                total_price REAL NOT NULL,
                booking_status TEXT NOT NULL DEFAULT 'CONFIRMED',
                customer_email TEXT DEFAULT '',
                booked_at TEXT DEFAULT ''
            )
        """)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()}
        for col, ddl in [("customer_email", "TEXT DEFAULT ''"),
                         ("booked_at", "TEXT DEFAULT ''"),
                         ("show_date", "TEXT DEFAULT ''"),
                         ("theatre", "TEXT DEFAULT ''"),
                         ("location", "TEXT DEFAULT ''")]:
            if col not in cols:
                conn.execute(f"ALTER TABLE bookings ADD COLUMN {col} {ddl}")
        conn.commit()


@st.cache_data
def load_data():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        movies_rows = conn.execute("SELECT name, language, price FROM movies").fetchall()
        showtimes = conn.execute("SELECT movie_name, show_time FROM showtimes").fetchall()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(movies)").fetchall()]
        posters = {}
        if "poster" in cols:
            posters = dict(conn.execute("SELECT name, poster FROM movies").fetchall())
    return movies_rows, showtimes, posters


def _parse_seats(rows):
    taken = set()
    for (seat_text,) in rows:
        if seat_text:
            taken.update(s.strip() for s in seat_text.split(",") if s.strip())
    return taken


BOOKED_SQL = """
    SELECT selected_seats FROM bookings
    WHERE movie_name = ? AND show_date = ? AND theatre = ? AND show_time = ?
      AND booking_status = 'CONFIRMED'
"""


def fetch_booked_seats(movie, show_date, theatre, showtime):
    if not all([movie, show_date, theatre, showtime]):
        return set()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        rows = conn.execute(BOOKED_SQL, (movie, show_date, theatre, showtime)).fetchall()
    return _parse_seats(rows)


def create_booking(customer, email, movie, location, theatre, show_date, showtime, seats, total_price):
    """Atomic insert. Returns (booking_id, clashing_seats)."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(BOOKED_SQL, (movie, show_date, theatre, showtime)).fetchall()
        clashes = _parse_seats(rows).intersection(seats)
        if clashes:
            conn.rollback()
            return None, sorted(clashes)
        cursor = conn.execute("""
            INSERT INTO bookings
            (customer_name, movie_name, show_time, ticket_count, selected_seats, total_price,
             booking_status, customer_email, booked_at, show_date, theatre, location)
            VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?)
        """, (customer, movie, showtime, len(seats), ", ".join(seats), total_price,
              (email or "").strip(), datetime.now().strftime("%d %b %Y, %I:%M %p"),
              show_date, theatre, location))
        conn.commit()
        return cursor.lastrowid, []
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


try:
    init_bookings_table()
    movies, all_showtimes, poster_db = load_data()
except sqlite3.Error as e:
    st.error(f"Could not read {DB_PATH}: {e}")
    st.stop()

if not movies:
    st.error("No movies found. Please check your database.")
    st.stop()

movie_names = [m[0] for m in movies]
price_by_movie = {m[0]: m[2] for m in movies}
movie_pos = {m[0]: i for i, m in enumerate(movies)}


def times_for_movie(name):
    return list(dict.fromkeys(t for m, t in all_showtimes if m == name))


def _time_of(text):
    n = norm_time(text)
    if not n:
        return None
    try:
        return datetime.strptime(n, "%I:%M%p").time()
    except ValueError:
        return None


def available_times(movie, date_iso=None):
    """Showtimes for a movie; on today's date, shows that already started are hidden."""
    times = times_for_movie(movie)
    if not date_iso or date.fromisoformat(date_iso) != today_date():
        return times
    now = datetime.now().time()
    out = []
    for t in times:
        tt = _time_of(t)
        if tt is None or tt > now:
            out.append(t)
    return out


def show_key(movie, theatre, show_date, showtime):
    return (movie, theatre, show_date, showtime)


# ==========================================
# PARSING (used by the chat agent)
# ==========================================
_TIME_RE = re.compile(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*([ap])\.?m\b", re.I)


def norm_time(text):
    """'2.00PM', '2:00 pm', '2 PM' -> '2:00pm'. None if no time."""
    m = _TIME_RE.search(str(text))
    if not m:
        return None
    return f"{int(m.group(1))}:{int(m.group(2) or 0):02d}{m.group(3).lower()}m"


def find_movie(message):
    low = message.lower()
    hits = [n for n in movie_names if re.search(rf"\b{re.escape(n.lower())}\b", low)]
    return max(hits, key=len) if hits else None


def find_showtime(movie, message):
    if not movie:
        return None
    low = message.lower()
    wanted = {norm_time(m.group(0)) for m in _TIME_RE.finditer(message)}
    for t in times_for_movie(movie):
        if str(t).lower() in low or norm_time(t) in wanted:
            return t
    return None


def find_theatre(message):
    s = _slug(message)
    for t in sorted(ALL_THEATRES, key=len, reverse=True):
        short = _slug(t.replace("CINEVERSE ", ""))
        if short and short in s:
            return t
    return None


def find_location(message):
    s = _slug(message)
    for loc in sorted(LOCATIONS, key=len, reverse=True):
        if _slug(loc) in s:
            return loc
    return None


def find_date(message):
    """Returns a date inside the bookable window, or None."""
    low = message.lower()
    today = today_date()
    window = date_options()

    if re.search(r"\b(today|indru|inru|innaiku)\b", low):
        return today
    if re.search(r"\b(tomorrow|naalaiku|naalaikku|naalai)\b", low):
        return today + timedelta(days=1)
    for d in window:
        for name in {d.strftime("%a").lower(), d.strftime("%A").lower()}:
            if re.search(rf"\b{name}\b", low):
                return d

    m = (re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", low)
         or re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s*(\d{1,2})\b", low))
    if m:
        g = m.groups()
        if g[0].isdigit():
            day, mon = int(g[0]), g[1]
        else:
            mon, day = g[0], int(g[1])
        try:
            cand = date(today.year, MONTHS[mon], day)
            if cand < today:
                cand = date(today.year + 1, MONTHS[mon], day)
        except ValueError:
            return None
        return cand if cand in window else None
    return None


def parse_booking_request(message):
    movie = find_movie(message)
    theatre = find_theatre(message)
    location = None if theatre else find_location(message)
    seats = list(dict.fromkeys(s.upper() for s in re.findall(r"\b([A-Da-d][1-6])\b", message)))
    return {
        "movie": movie,
        "theatre": theatre,
        "location": location,
        "date": find_date(message),
        "showtime": find_showtime(movie, message),
        "seats": seats,
    }


# ==========================================
# STATE + CALLBACKS
# ==========================================
def reset_flow():
    st.session_state["selected_seats"] = []
    st.session_state["show_booking_confirmation"] = False
    st.session_state.pop("last_confirmation", None)
    st.session_state.pop("seat_warning", None)


def select_movie(name):
    st.session_state["selected_movie"] = name
    st.session_state["selected_showtime"] = None
    reset_flow()


def select_showtime(t):
    st.session_state["selected_showtime"] = t
    reset_flow()


def toggle_seat(seat_name):
    seats = st.session_state["selected_seats"]
    st.session_state.pop("last_confirmation", None)
    st.session_state["show_booking_confirmation"] = False
    limit = st.session_state.get("tickets", 2)
    if seat_name in seats:
        seats.remove(seat_name)
    elif len(seats) < limit:
        seats.append(seat_name)
    else:
        st.session_state["seat_warning"] = (
            f"You can only select {limit} seat(s). Increase the ticket count or deselect a seat."
        )


def cancel_review():
    st.session_state["show_booking_confirmation"] = False


st.session_state.setdefault("selected_seats", [])
st.session_state.setdefault("show_booking_confirmation", False)
st.session_state.setdefault("selected_movie", movie_names[0])
st.session_state.setdefault("selected_showtime", None)

if st.session_state["selected_movie"] not in movie_names:
    select_movie(movie_names[0])
selected_movie = st.session_state["selected_movie"]
selected_price = price_by_movie[selected_movie]


# ==========================================
# NAV + HERO + SEARCH
# ==========================================
st.markdown(
    f'<div class="nav"><div class="logo">{brand_mark_html()}<div>CINE<span>VERSE</span></div></div>'
    '<div class="pill">Demo booking</div></div>',
    unsafe_allow_html=True,
)

with st.container(key="hero"):
    st.markdown(
        '<div class="eyebrow">Search-led discovery</div>'
        '<div class="headline">Find your next<br>cinema moment.</div>'
        '<div class="sub">Search by movie or language, pick a location and date, choose a show, '
        'select your seats and you are done.</div>',
        unsafe_allow_html=True,
    )
    search_text = st.text_input(
        "Search movies",
        placeholder="Search for a movie or language (e.g. Leo, Tamil)...",
        label_visibility="collapsed",
        key="search_input",
    )
query = search_text.lower().strip()


# ==========================================
# MOVIE CARDS
# ==========================================
GRADIENTS = [
    "linear-gradient(160deg,#c41e3a,#5c0d1d)",
    "linear-gradient(160deg,#1f3a5f,#0b1a2e)",
    "linear-gradient(160deg,#d97706,#6b3008)",
    "linear-gradient(160deg,#0f766e,#08332f)",
    "linear-gradient(160deg,#6d28d9,#27095c)",
    "linear-gradient(160deg,#be185d,#4a0620)",
]


def _poster_src(name, db_value=None):
    if db_value:
        v = str(db_value).strip()
        if v.lower().startswith(("http://", "https://", "data:")):
            return v
        p = Path(v)
        if not p.is_absolute():
            p = BASE_DIR / p
        if p.is_file():
            return file_uri(p)
    found = find_image(POSTER_DIR, name, POSTER_EXTS)
    return file_uri(found) if found else None


def poster_html(name, lang, pos):
    src = _poster_src(name, poster_db.get(name))
    badge = f'<span class="poster-lang">{esc(lang)}</span>'
    if src:
        return (f'<div class="poster"><img src="{esc(src)}" alt="{esc(name)} poster" '
                f'loading="lazy">{badge}</div>'), True
    return (f'<div class="poster poster-fallback" style="background:{GRADIENTS[pos % len(GRADIENTS)]}">'
            f'{badge}<span class="poster-title">{esc(name)}</span></div>'), False


st.markdown('<div class="sec-title">Now Showing</div>'
            '<div class="sec-sub">Select a movie to see its locations, dates and showtimes.</div>',
            unsafe_allow_html=True)

visible = [m for m in movies
           if not query or query in str(m[0]).lower() or query in str(m[1]).lower()]

if not visible:
    st.info("No movies match your search. Try a different name.")
else:
    missing_posters = []
    PER_ROW = 4
    for start in range(0, len(visible), PER_ROW):
        cols = st.columns(PER_ROW)
        for offset, (name, lang, price) in enumerate(visible[start:start + PER_ROW]):
            is_sel = name == selected_movie
            pos = movie_pos[name]
            card_poster, found = poster_html(name, lang, pos)
            if not found:
                missing_posters.append(name)
            with cols[offset]:
                with st.container(key=f"mcard_{'sel_' if is_sel else ''}{pos}"):
                    st.markdown(
                        card_poster
                        + f'<div class="mc-body"><div class="mc-name">{esc(name)}</div>'
                          f'<div class="mc-price">{inr(price)} <small>/ ticket</small></div></div>',
                        unsafe_allow_html=True,
                    )
                    st.button(
                        "Selected" if is_sel else "Select",
                        key=f"pick_{pos}",
                        use_container_width=True,
                        type="primary" if is_sel else "secondary",
                        on_click=select_movie,
                        args=(name,),
                    )
    if missing_posters:
        st.caption(
            "Add poster images to the posters folder named after the movie "
            f"(e.g. {missing_posters[0]}.jpg) to replace the placeholder cards."
        )


# ==========================================
# WHERE & WHEN  (location, theatre, date)
# ==========================================
st.markdown('<div class="sec-title" style="margin-top:26px;">Where and when</div>'
            '<div class="sec-sub">Choose a location, a theatre and a date.</div>',
            unsafe_allow_html=True)

with st.container(key="where"):
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c1:
        selected_location = st.selectbox("Location", LOCATIONS, key="loc_name")
    with c2:
        selected_theatre = st.selectbox("Theatre", THEATRES[selected_location],
                                        key=f"theatre_{selected_location}")
    with c3:
        day_idx = st.selectbox("Date", list(range(DATE_WINDOW)),
                               format_func=lambda i: date_label(date_options()[i]),
                               key="date_idx")
    selected_date = date_options()[day_idx]
    st.markdown(venue_card_html(selected_theatre), unsafe_allow_html=True)

selected_date_iso = selected_date.isoformat()


# ==========================================
# SHOWTIMES
# ==========================================
st.markdown(
    f'<div class="sec-title" style="margin-top:26px;">Showtimes | {esc(selected_movie)}</div>'
    f'<div class="sec-sub">{esc(date_long(selected_date))} at {esc(selected_theatre)}</div>',
    unsafe_allow_html=True,
)

movie_times = available_times(selected_movie, selected_date_iso)
if st.session_state["selected_showtime"] not in movie_times:
    st.session_state["selected_showtime"] = movie_times[0] if movie_times else None
selected_showtime = st.session_state["selected_showtime"]

if not movie_times:
    st.warning("No more showtimes for this movie on the selected date. Try another date.")
else:
    PER_TIME_ROW = 6
    for start in range(0, len(movie_times), PER_TIME_ROW):
        cols = st.columns(PER_TIME_ROW)
        for offset, t in enumerate(movie_times[start:start + PER_TIME_ROW]):
            with cols[offset]:
                st.button(
                    str(t),
                    key=f"time_{start + offset}",
                    use_container_width=True,
                    type="primary" if t == selected_showtime else "secondary",
                    on_click=select_showtime,
                    args=(t,),
                )

# Seats belong to one specific show; if the show changes, clear the seat selection
current_sig = show_key(selected_movie, selected_theatre, selected_date_iso, selected_showtime)
if st.session_state.get("show_sig") != current_sig:
    st.session_state["show_sig"] = current_sig
    st.session_state["selected_seats"] = []
    st.session_state["show_booking_confirmation"] = False


# ==========================================
# BOOKING FLOW
# ==========================================
def stepper_html(step):
    def item(n, label):
        cls = "active" if step == n else "done" if step > n else ""
        return (f'<div class="step {cls}"><div class="step-num">{n}</div>'
                f'<div class="step-label">{label}</div></div>')

    def line(n):
        return f'<div class="step-line {"done" if step > n else ""}"></div>'

    return ('<div class="steps">' + item(1, "Choose show") + line(1)
            + item(2, "Pick seats") + line(2) + item(3, "Review and confirm") + "</div>")


receipt = st.session_state.get("last_confirmation")

if not selected_showtime:
    st.markdown(stepper_html(1), unsafe_allow_html=True)
    st.info("No shows available for this movie on the selected date. Try another date or theatre.")
else:
    stepper_slot = st.empty()

    if receipt:
        rows = (sum_row("Customer", receipt["customer"]) + sum_row("Movie", receipt["movie"])
                + sum_row("Theatre", receipt["theatre"]) + sum_row("Date", receipt["date_label"])
                + sum_row("Showtime", receipt["showtime"])
                + sum_row("Seats", ", ".join(receipt["seats"]))
                + sum_row("Total", inr(receipt["total"])))
        st.markdown(
            f'<div class="ticket"><div class="ticket-head"><span>Booking confirmed</span>'
            f'<b>BK{receipt["id"]:05d}</b></div><div class="ticket-body">{rows}</div>'
            f'<div class="ticket-note">Demo booking only. No real ticket or payment is generated.</div></div>',
            unsafe_allow_html=True,
        )

    left, right = st.columns([1.5, 0.9], gap="large")

    # ----- Left: details + seat map -----
    with left:
        with st.container(key="details"):
            c1, c2 = st.columns([2, 1])
            with c1:
                customer_name = st.text_input("Your name", placeholder="Enter your full name",
                                              key="cust_name")
            with c2:
                tickets = st.number_input("Tickets", min_value=1, max_value=10,
                                          value=2, step=1, key="tickets")

        st.write("")

        booked_seats = fetch_booked_seats(selected_movie, selected_date_iso,
                                          selected_theatre, selected_showtime)
        current_sel = st.session_state["selected_seats"]
        cleaned = [s for s in current_sel if s in ALL_SEATS and s not in booked_seats][:tickets]
        if cleaned != current_sel:
            st.session_state["selected_seats"] = cleaned
            st.session_state["show_booking_confirmation"] = False
        selected_seats = st.session_state["selected_seats"]

        with st.container(key="seatmap"):
            st.markdown('<div class="screen">Screen this way</div><div class="screen-bar"></div>',
                        unsafe_allow_html=True)
            for row in SEAT_ROWS:
                cols = st.columns([0.45] + [1] * SEATS_PER_SIDE + [0.4] + [1] * SEATS_PER_SIDE)
                cols[0].markdown(f'<div class="row-label">{row}</div>', unsafe_allow_html=True)
                seat_cols = cols[1:1 + SEATS_PER_SIDE] + cols[2 + SEATS_PER_SIDE:]
                for i, col in enumerate(seat_cols, start=1):
                    seat = f"{row}{i}"
                    with col:
                        if seat in booked_seats:
                            st.button("X", key=f"seat_{seat}", use_container_width=True,
                                      disabled=True, help="Already booked")
                        else:
                            is_sel = seat in selected_seats
                            st.button(seat, key=f"seat_{seat}", use_container_width=True,
                                      type="primary" if is_sel else "secondary",
                                      on_click=toggle_seat, args=(seat,))
            free = len(ALL_SEATS) - len(booked_seats)
            st.markdown(
                '<div class="legend">'
                '<span><i style="background:#fff;border:1.5px solid #cfc9bf"></i>Available</span>'
                '<span><i style="background:#c41e3a"></i>Selected</span>'
                '<span><i style="background:#e9e4dd"></i>Booked</span>'
                f'<span>{free} seats left</span></div>',
                unsafe_allow_html=True,
            )

        if "seat_warning" in st.session_state:
            st.warning(st.session_state.pop("seat_warning"))

    # ----- Right: order summary -----
    total = selected_price * tickets
    current_details = {
        "name": customer_name.strip(),
        "movie": selected_movie,
        "location": selected_location,
        "theatre": selected_theatre,
        "date": selected_date_iso,
        "date_label": date_long(selected_date),
        "showtime": selected_showtime,
        "tickets": int(tickets),
        "seats": sorted(selected_seats),
        "total": total,
    }
    missing_seats = int(tickets) - len(selected_seats)
    ready = bool(customer_name.strip()) and missing_seats == 0

    with right:
        with st.container(key="summary"):
            st.markdown(
                '<div class="sum-title">Your order</div>'
                + sum_row("Movie", selected_movie)
                + sum_row("Theatre", selected_theatre)
                + sum_row("Date", date_long(selected_date))
                + sum_row("Showtime", selected_showtime)
                + sum_row("Tickets", tickets)
                + sum_row("Seats", ", ".join(sorted(selected_seats)) or "None yet")
                + '<div class="sum-div"></div>'
                '<div class="sum-total-label">Total</div>'
                f'<div class="sum-total">{inr(total)}</div>',
                unsafe_allow_html=True,
            )
            review_clicked = st.button("Review order", key="review_btn",
                                       use_container_width=True, type="primary",
                                       disabled=not ready)
            if not customer_name.strip():
                st.caption("Enter your name to continue.")
            elif missing_seats > 0:
                st.caption(f"Select {missing_seats} more seat(s).")

        if review_clicked:
            st.session_state["booking_details"] = current_details
            st.session_state["show_booking_confirmation"] = True
            st.session_state.pop("last_confirmation", None)
            st.rerun()

    # ----- Review & confirm -----
    details = st.session_state.get("booking_details")
    review_open = st.session_state["show_booking_confirmation"] and details == current_details

    if review_open:
        st.write("")
        with st.container(key="review"):
            st.markdown(
                '<div class="sum-title">Review and confirm</div>'
                + sum_row("Customer", details["name"])
                + sum_row("Movie", details["movie"])
                + sum_row("Theatre", f'{details["theatre"]}, {details["location"]}')
                + sum_row("Date", details["date_label"])
                + sum_row("Showtime", details["showtime"])
                + sum_row("Seats", ", ".join(details["seats"]))
                + sum_row("Total", inr(details["total"])),
                unsafe_allow_html=True,
            )
            b1, b2 = st.columns([2, 1])
            with b1:
                confirm_clicked = st.button("Confirm booking", key="confirm_btn",
                                            use_container_width=True, type="primary")
            with b2:
                st.button("Edit", key="edit_btn", use_container_width=True, on_click=cancel_review)

        if confirm_clicked:
            try:
                booking_id, clashes = create_booking(
                    details["name"], google_email, details["movie"], details["location"],
                    details["theatre"], details["date"], details["showtime"],
                    details["seats"], details["total"],
                )
            except sqlite3.Error as e:
                st.error(f"Could not save your booking: {e}")
            else:
                if clashes:
                    st.session_state["selected_seats"] = [
                        s for s in details["seats"] if s not in clashes
                    ]
                    st.session_state["show_booking_confirmation"] = False
                    st.session_state["seat_warning"] = (
                        f"Seat(s) {', '.join(clashes)} were just booked by someone else. "
                        "Please pick replacements."
                    )
                    st.rerun()
                st.session_state["last_confirmation"] = {
                    "id": booking_id,
                    "customer": details["name"],
                    "movie": details["movie"],
                    "theatre": f'{details["theatre"]}, {details["location"]}',
                    "date_label": details["date_label"],
                    "showtime": details["showtime"],
                    "seats": details["seats"],
                    "total": details["total"],
                }
                st.session_state["selected_seats"] = []
                st.session_state["show_booking_confirmation"] = False
                st.rerun()

    step = 3 if review_open else 2
    if receipt:
        step = 4
    stepper_slot.markdown(stepper_html(step), unsafe_allow_html=True)


# ==========================================
# AI CONCIERGE
# ==========================================

# ---------- Listing helpers ----------
def theatres_list_md(location=None):
    locs = [location] if location in THEATRES else LOCATIONS
    return "\n\n".join(f"**{loc}**\n" + "\n".join(f"- {t}" for t in THEATRES[loc]) for loc in locs)


def dates_list_md():
    return "\n".join(f"- {date_label(d)}" for d in date_options())


# ---------- Ticket: text, PNG, 3D HTML, email ----------
def ticket_text(t):
    return (
        "==============================\n"
        "        CINEVERSE E-TICKET\n"
        "==============================\n"
        f"Booking ID : BK{t['id']:05d}\n"
        f"Customer   : {t['customer']}\n"
        f"Movie      : {t['movie']}\n"
        f"Theatre    : {t['theatre']}, {t['location']}\n"
        f"Date       : {t['date_label']}\n"
        f"Showtime   : {t['showtime']}\n"
        f"Seats      : {', '.join(t['seats'])}\n"
        f"Total      : {inr(t['total'])}\n"
        f"Booked on  : {t['booked_at']}\n"
        "------------------------------\n"
        "Demo booking only - no real ticket or payment.\n"
    )


def poster_bytes(movie):
    src = _poster_src(movie, poster_db.get(movie))
    if not src:
        return None
    try:
        if src.startswith("data:"):
            return base64.b64decode(src.split(",", 1)[1])
        import requests
        r = requests.get(src, timeout=8)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def _font(size, bold=False):
    from PIL import ImageFont
    names = (["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "Helvetica-Bold.ttf"]
             if bold else
             ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "Helvetica.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def build_ticket_png(t):
    from PIL import Image, ImageDraw, ImageOps

    W, H, PW = 1200, 560, 380
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(26 + 24 * k), int(26 + 6 * k), int(46 + 18 * k)))

    poster = None
    raw = poster_bytes(t["movie"])
    if raw:
        try:
            poster = ImageOps.fit(Image.open(io.BytesIO(raw)).convert("RGB"),
                                  (PW, H), centering=(0.5, 0.0))
        except Exception:
            poster = None
    if poster is None:
        poster = Image.new("RGB", (PW, H), (196, 30, 58))
        pd = ImageDraw.Draw(poster)
        title_font = _font(44, True)
        y = H // 2 - 60
        for line in textwrap.wrap(t["movie"], 12)[:3]:
            w = pd.textlength(line, font=title_font)
            pd.text(((PW - w) / 2, y), line, font=title_font, fill="white")
            y += 58
    img.paste(poster, (0, 0))

    for y in range(0, H, 18):
        d.line([(PW, y), (PW, y + 9)], fill=(255, 255, 255), width=2)

    x0 = PW + 50
    maxw = W - x0 - 50

    def fit(text, size, bold=True):
        f = _font(size, bold)
        while d.textlength(text, font=f) > maxw and size > 22:
            size -= 2
            f = _font(size, bold)
        return f

    d.text((x0, 34), "CINEVERSE  |  E-TICKET", font=_font(22, True), fill=(255, 154, 170))
    d.text((x0, 72), t["movie"], font=fit(t["movie"], 58), fill="white")

    def field(x, y, label, value, size=30):
        d.text((x, y), label, font=_font(17, True), fill=(160, 160, 190))
        d.text((x, y + 24), str(value), font=_font(size, True), fill="white")

    mid = x0 + maxw // 2
    field(x0, 150, "DATE", t["date_label"])
    field(mid, 150, "SHOWTIME", t["showtime"])
    field(x0, 235, "THEATRE", t["theatre"] + ", " + t["location"], 26)
    field(x0, 320, "NAME", t["customer"][:22], 26)
    field(mid, 320, "SEATS", ", ".join(t["seats"]), 26)
    field(x0, 405, "TOTAL", f"Rs. {float(t['total']):,.0f}", 26)

    bx, by = x0, 470
    seed = t["id"] * 7919
    for i in range(46):
        w = 2 + ((seed >> (i % 16)) + i * 3) % 4
        d.rectangle([bx, by, bx + w, by + 50], fill="white")
        bx += w + 3 + (i % 3)
        if bx > W - 330:
            break
    d.text((W - 300, 468), f"BK{t['id']:05d}", font=_font(34, True), fill=(255, 154, 170))
    d.text((W - 300, 512), t["booked_at"], font=_font(16), fill=(160, 160, 190))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


_TICKET_3D = """
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:transparent;font-family:'Inter','Segoe UI',Arial,sans-serif}
body{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;gap:14px}
.float{animation:float 4s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
.scene{perspective:1200px;width:min(560px,94vw);height:330px}
.tilt{width:100%;height:100%;transform-style:preserve-3d;transition:transform .12s ease-out}
.tilt.rest{transition:transform .5s ease}
.card{position:relative;width:100%;height:100%;transform-style:preserve-3d;transition:transform .7s cubic-bezier(.2,.8,.2,1);cursor:pointer}
.card.flip{transform:rotateY(180deg)}
.face{position:absolute;inset:0;border-radius:18px;overflow:hidden;backface-visibility:hidden;-webkit-backface-visibility:hidden;
  background:linear-gradient(135deg,#1a1a2e,#32203f);color:#fff;box-shadow:0 24px 50px rgba(26,26,46,.35),0 0 0 1px rgba(255,255,255,.08) inset}
.back{transform:rotateY(180deg)}
.shine{position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at var(--mx,50%) var(--my,50%),rgba(255,255,255,.28),transparent 55%)}
.front{display:flex}
.poster{width:36%;flex:none;position:relative;background:linear-gradient(160deg,#c41e3a,#5c0d1d);display:flex;align-items:center;justify-content:center;text-align:center;padding:10px}
.poster img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top}
.poster span{font-weight:800;font-size:24px;line-height:1.1;text-shadow:0 4px 14px rgba(0,0,0,.4)}
.perf{width:0;border-left:2px dashed rgba(255,255,255,.55)}
.info{flex:1;padding:16px 18px;display:flex;flex-direction:column;min-width:0}
.brand{font-size:11px;letter-spacing:3px;color:#ff9aaa;font-weight:700}
.title{font-size:23px;font-weight:800;letter-spacing:-.5px;margin:4px 0 10px;line-height:1.1;word-break:break-word}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 10px}
.span{grid-column:span 2}
.l{font-size:9.5px;letter-spacing:1.5px;color:#a0a0be;font-weight:700}
.v{font-size:15px;font-weight:700;margin-top:2px;word-break:break-word}
.id{margin-top:auto;font-size:12px;color:#ff9aaa;font-weight:700;letter-spacing:2px}
.back{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:20px;text-align:center}
.bar{width:78%;height:78px;border-radius:4px;
  background:repeating-linear-gradient(90deg,#fff 0 3px,transparent 3px 5px,#fff 5px 6px,transparent 6px 10px,#fff 10px 14px,transparent 14px 16px)}
.big{font-size:30px;font-weight:800;letter-spacing:3px;color:#ff9aaa}
.small{font-size:12px;color:#c9c9de;line-height:1.6}
.hint{font-size:12px;color:#7a7a8c}
</style>

<div class="float"><div class="scene">
 <div class="tilt rest" id="tilt">
  <div class="card" id="card">
   <div class="face front">
     <div class="poster">__POSTER__</div>
     <div class="perf"></div>
     <div class="info">
       <div class="brand">CINEVERSE | E-TICKET</div>
       <div class="title">__MOVIE__</div>
       <div class="grid">
         <div><div class="l">DATE</div><div class="v">__DATE__</div></div>
         <div><div class="l">SHOWTIME</div><div class="v">__TIME__</div></div>
         <div class="span"><div class="l">THEATRE</div><div class="v">__THEATRE__</div></div>
         <div><div class="l">NAME</div><div class="v">__NAME__</div></div>
         <div><div class="l">TOTAL</div><div class="v">__TOTAL__</div></div>
         <div class="span"><div class="l">SEATS</div><div class="v">__SEATS__</div></div>
       </div>
       <div class="id">__ID__</div>
     </div>
     <div class="shine"></div>
   </div>
   <div class="face back">
     <div class="big">__ID__</div>
     <div class="bar"></div>
     <div class="small">__MOVIE__<br>__DATE__ | __TIME__<br>__THEATRE__<br>Seats: __SEATS__<br>Show this ticket at the counter</div>
     <div class="shine"></div>
   </div>
  </div>
 </div>
</div></div>
<div class="hint">Move over the ticket to tilt it | Tap to flip</div>

<script>
const tilt=document.getElementById('tilt'), card=document.getElementById('card');
function move(x,y){
  const r=tilt.getBoundingClientRect();
  const px=(x-r.left)/r.width-.5, py=(y-r.top)/r.height-.5;
  tilt.classList.remove('rest');
  tilt.style.transform='rotateY('+(px*24)+'deg) rotateX('+(-py*24)+'deg)';
  tilt.style.setProperty('--mx',((px+.5)*100)+'%');
  tilt.style.setProperty('--my',((py+.5)*100)+'%');
}
function rest(){tilt.classList.add('rest');tilt.style.transform='rotateY(0) rotateX(0)';}
document.addEventListener('mousemove',e=>move(e.clientX,e.clientY));
document.addEventListener('mouseleave',rest);
document.addEventListener('touchmove',e=>{const t=e.touches[0];move(t.clientX,t.clientY);},{passive:true});
document.addEventListener('touchend',rest);
card.addEventListener('click',()=>card.classList.toggle('flip'));
</script>
"""


def ticket_3d_html(t):
    src = _poster_src(t["movie"], poster_db.get(t["movie"]))
    poster = (f'<img src="{esc(src)}" alt="poster">' if src
              else f'<span>{esc(t["movie"])}</span>')
    html_out = _TICKET_3D
    for key, val in {
        "__POSTER__": poster,
        "__MOVIE__": esc(t["movie"]),
        "__DATE__": esc(t["date_label"]),
        "__TIME__": esc(t["showtime"]),
        "__THEATRE__": esc(f'{t["theatre"]}, {t["location"]}'),
        "__SEATS__": esc(", ".join(t["seats"])),
        "__NAME__": esc(t["customer"]),
        "__TOTAL__": esc(inr(t["total"])),
        "__ID__": f"BK{t['id']:05d}",
    }.items():
        html_out = html_out.replace(key, val)
    return html_out


def send_ticket_email(to_addr, t):
    """Emails the ticket (PNG attached). Needs [smtp] in .streamlit/secrets.toml."""
    if not to_addr:
        return False
    try:
        cfg = st.secrets["smtp"]
        msg = EmailMessage()
        msg["Subject"] = f"Your CINEVERSE ticket - BK{t['id']:05d}"
        msg["From"] = cfg["user"]
        msg["To"] = to_addr
        msg.set_content(
            f"Hi {t['customer']},\n\nYour booking is confirmed! Your ticket image is attached.\n\n"
            + ticket_text(t)
        )
        if t.get("png"):
            msg.add_attachment(t["png"], maintype="image", subtype="png",
                               filename=f"CINEVERSE_BK{t['id']:05d}.png")
        with smtplib.SMTP_SSL(cfg["host"], int(cfg.get("port", 465))) as server:
            server.login(cfg["user"], cfg["password"])
            server.send_message(msg)
        return True
    except Exception:
        return False


def _date_label_from_iso(iso):
    try:
        return date_long(date.fromisoformat(iso))
    except (TypeError, ValueError):
        return "-"


def load_user_tickets():
    """All CONFIRMED bookings of the logged-in Google account, newest first."""
    if not google_email:
        return []
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            rows = conn.execute(
                """
                SELECT id, customer_name, movie_name, theatre, location, show_date,
                       show_time, selected_seats, total_price, COALESCE(booked_at, '')
                FROM bookings
                WHERE LOWER(customer_email) = LOWER(?) AND booking_status = 'CONFIRMED'
                ORDER BY id DESC
                """,
                (google_email,),
            ).fetchall()
    except sqlite3.Error:
        return []
    return [
        {
            "id": r[0], "customer": r[1], "movie": r[2],
            "theatre": r[3] or "-", "location": r[4] or "-",
            "date_label": _date_label_from_iso(r[5]), "showtime": r[6],
            "seats": [s.strip() for s in str(r[7]).split(",") if s.strip()],
            "total": r[8], "booked_at": r[9] or "-",
        }
        for r in rows
    ]


def get_ticket_png(t):
    cache = st.session_state.setdefault("png_cache", {})
    if t["id"] not in cache:
        try:
            cache[t["id"]] = build_ticket_png(t)
        except Exception:
            cache[t["id"]] = None
    return cache[t["id"]]


# ---------- Chat booking: confirm / cancel ----------
def _say(text):
    st.session_state["cineverse_chat_history"].append({"role": "assistant", "content": text})


def confirm_pending_booking():
    p = st.session_state.pop("pending_booking", None)
    if not p:
        return
    seats = sorted(p["seats"])
    show_date = p["show_date"]
    try:
        booking_id, clashes = create_booking(
            google_name, google_email, p["movie_name"], p["location"], p["theatre"],
            show_date, p["showtime"], seats, p["total_price"],
        )
    except sqlite3.Error as e:
        _say(f"Sorry, I could not save your booking: {e}")
        return

    if clashes:
        _say(f"Seat(s) **{', '.join(clashes)}** were just booked by someone else. "
             "No ticket was booked. Please choose different seats.")
        return

    ticket = {
        "id": booking_id,
        "customer": google_name,
        "movie": p["movie_name"],
        "theatre": p["theatre"],
        "location": p["location"],
        "date_label": _date_label_from_iso(show_date),
        "showtime": p["showtime"],
        "seats": seats,
        "total": p["total_price"],
        "booked_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "png": None,
    }
    ticket["png"] = get_ticket_png(ticket)
    emailed = send_ticket_email(google_email, ticket)
    if emailed:
        st.session_state.setdefault("emailed_ids", set()).add(booking_id)
    st.session_state["selected_seats"] = []

    msg = (f"**Booking confirmed!** (BK{booking_id:05d})\n\n"
           f"Movie: **{ticket['movie']}**\n\n"
           f"Theatre: {ticket['theatre']}, {ticket['location']}\n\n"
           f"Date: {ticket['date_label']} | Showtime: {ticket['showtime']}\n\n"
           f"Seats: {', '.join(seats)} | Total: {inr(ticket['total'])}\n\n"
           "Use the **My Tickets** button on the right to view and download your ticket.")
    if emailed:
        msg += f"\n\nTicket sent to **{google_email}**."
    _say(msg)


def cancel_pending_booking():
    st.session_state.pop("pending_booking", None)
    st.session_state.pop("booking_draft", None)
    _say("Okay, booking cancelled. No ticket has been booked.")


# ---------- Info questions (no booking) ----------
def route_ai_tool(user_message):
    message = user_message.lower().strip()
    movie_name = find_movie(message)
    date_obj = find_date(message)
    location = find_location(message)

    if re.search(r"\b(theatres?|theaters?|cinemas?|locations?|venues?|where)\b", message):
        return {"tool": "list_theatres", "result": location}
    if re.search(r"\b(dates?|which day|what day)\b", message):
        return {"tool": "list_dates", "result": None}
    if "movie" in message and any(w in message for w in ["available", "list", "show me", "all"]):
        return {"tool": "search_movies", "result": None}
    if any(w in message for w in ["compare", "cheapest", "cheap", "lowest price"]):
        return {"tool": "compare_prices", "result": None}
    if "showtime" in message or "show time" in message or "timing" in message:
        return {"tool": "search_showtimes", "result": {"movie": movie_name, "date": date_obj}}
    if "how much" in message or "total" in message or "tickets" in message:
        ticket_count = next((int(w) for w in message.split() if w.isdigit()), None)
        if movie_name and ticket_count is not None:
            return {"tool": "calculate_booking_total",
                    "result": {"movie": movie_name, "count": ticket_count}}
    if ("price" in message or "cost" in message) and movie_name:
        return {"tool": "get_ticket_price", "result": movie_name}
    return {"tool": None, "result": None}


def format_agent_response(resp):
    tool, result = resp["tool"], resp["result"]

    if tool == "list_theatres":
        return ("**CINEVERSE theatres**\n\n" + theatres_list_md(result)
                + "\n\nTo book, type: *Book Leo at CINEVERSE Velachery Mall, tomorrow, 2:00 PM, A1 and A2*")

    if tool == "list_dates":
        return "**Dates you can book (next 7 days)**\n\n" + dates_list_md()

    if tool == "search_movies":
        lines = ["**Movies currently showing**\n"]
        lines += [f"- **{m[0]}**: {m[1]}, {inr(m[2])} per ticket" for m in movies]
        lines.append("\nTo book, type: *Book Leo at CINEVERSE Anna Nagar Grand, tomorrow, 2:00 PM, A1 and A2*")
        return "\n".join(lines)

    if tool == "compare_prices":
        lines = ["**Ticket prices (lowest first)**\n"]
        lines += [f"- **{m[0]}**: {inr(m[2])}" for m in sorted(movies, key=lambda r: r[2])]
        return "\n".join(lines)

    if tool == "search_showtimes":
        movie, d = result["movie"], result["date"]
        d_iso = d.isoformat() if d else None
        blocks = []
        for m in ([movie] if movie else movie_names):
            times = available_times(m, d_iso)
            if times:
                blocks.append(f"**{m}**\n" + "\n".join(f"- {t}" for t in times))
        if not blocks:
            return "Sorry, no shows are left for that day."
        head = f"**Showtimes on {date_long(d)}**" if d else "**Available showtimes**"
        return head + "\n\n" + "\n\n".join(blocks)

    if tool == "calculate_booking_total":
        price = price_by_movie.get(result["movie"])
        if price is None:
            return "Sorry, I could not calculate that."
        total = float(price) * result["count"]
        return (f"**{result['movie']}**: booking summary\n\n"
                f"Tickets: {result['count']}\n\n"
                f"Price per ticket: {inr(price)}\n\n"
                f"**Total: {inr(total)}**\n\n"
                "Want me to book it? Tell me the theatre, date, showtime and seats.")

    if tool == "get_ticket_price":
        return (f"**{result}**: {inr(price_by_movie[result])} per ticket\n\n"
                "Want to see the showtimes or book tickets?")

    return ""


# ---------- Booking conversation (multi-step) ----------
YES_WORDS = {"yes", "y", "ok", "okay", "confirm", "confirmed", "sure", "yep", "aama", "sari", "seri"}
NO_WORDS = {"no", "n", "cancel", "nope", "venam", "vendam"}
EMPTY_DRAFT = {"movie": None, "location": None, "theatre": None,
               "date": None, "showtime": None, "seats": []}


def handle_booking_message(prompt):
    """Returns a reply if this message belongs to a booking flow, else None."""
    low = prompt.lower().strip()
    pending = st.session_state.get("pending_booking")
    draft = st.session_state.get("booking_draft")

    if pending:
        word = re.sub(r"[^a-z ]", "", low).strip()
        if word in YES_WORDS:
            confirm_pending_booking()
            return ""
        if word in NO_WORDS:
            cancel_pending_booking()
            return ""

    if draft and re.search(r"\bcancel\b", low):
        st.session_state.pop("booking_draft", None)
        return "Okay, I have dropped that booking request."

    wants_booking = bool(re.search(r"\b(book|reserve|booking)\b", low))
    p = parse_booking_request(prompt)
    has_info = any([p["movie"], p["theatre"], p["location"], p["date"], p["showtime"], p["seats"]])
    if not (wants_booking or (draft and has_info)):
        return None

    d = dict(draft or EMPTY_DRAFT)
    d["seats"] = list(d["seats"])

    if p["movie"] and p["movie"] != d["movie"]:
        d["movie"], d["showtime"] = p["movie"], None
    if p["theatre"]:
        d["theatre"], d["location"] = p["theatre"], THEATRE_LOCATION[p["theatre"]]
    elif p["location"] and p["location"] != d["location"]:
        d["location"], d["theatre"] = p["location"], None
    if p["date"]:
        d["date"] = p["date"].isoformat()
    if p["showtime"]:
        d["showtime"] = p["showtime"]
    if p["seats"]:
        d["seats"] = p["seats"]

    def save(reply):
        st.session_state["booking_draft"] = d
        return reply

    if not d["movie"]:
        return save("Sure! Which movie would you like to book?")

    if not d["theatre"]:
        if d["location"]:
            opts = "\n".join(f"- {t}" for t in THEATRES[d["location"]])
            return save(f"Which theatre in **{d['location']}**?\n\n{opts}")
        return save("Which theatre would you like?\n\n" + theatres_list_md())

    if not d["date"]:
        return save(f"Which date for **{d['movie']}** at **{d['theatre']}**?\n\n" + dates_list_md())

    d_date = date.fromisoformat(d["date"])
    times = available_times(d["movie"], d["date"])
    if not times:
        d["date"] = None
        return save("No shows are left for that date. Please choose another date.\n\n" + dates_list_md())

    if d["showtime"] not in times:
        prefix = f"**{d['showtime']}** is not available on that date.\n\n" if d["showtime"] else ""
        d["showtime"] = None
        return save(f"{prefix}Which showtime for **{d['movie']}** on {date_long(d_date)}?\n\n"
                    + "\n".join(f"- {t}" for t in times))

    booked = fetch_booked_seats(d["movie"], d["date"], d["theatre"], d["showtime"])
    if not d["seats"]:
        free = [s for s in ALL_SEATS if s not in booked]
        return save(f"Which seats for **{d['movie']}** at **{d['showtime']}**?\n\n"
                    f"Available: {', '.join(free) if free else 'none, sold out'}")

    bad = [s for s in d["seats"] if s in booked or s not in ALL_SEATS]
    if bad:
        d["seats"] = []
        free = [s for s in ALL_SEATS if s not in booked]
        return save(f"Seat(s) **{', '.join(bad)}** are not available.\n\n"
                    f"Available: {', '.join(free) if free else 'none, sold out'}\n\n"
                    "Please pick other seats.")
    if len(d["seats"]) > MAX_CHAT_SEATS:
        d["seats"] = []
        return save(f"You can book up to {MAX_CHAT_SEATS} seats at a time. Please choose fewer seats.")

    price = price_by_movie.get(d["movie"])
    if price is None:
        return save("Sorry, I could not find the ticket price for that movie.")

    total = float(price) * len(d["seats"])
    st.session_state["pending_booking"] = {
        "movie_name": d["movie"], "location": d["location"], "theatre": d["theatre"],
        "show_date": d["date"], "showtime": d["showtime"], "seats": d["seats"],
        "ticket_count": len(d["seats"]), "total_price": total,
    }
    st.session_state.pop("booking_draft", None)
    return (
        "**Please confirm your booking**\n\n"
        f"Movie: **{d['movie']}**\n\n"
        f"Theatre: {d['theatre']}, {d['location']}\n\n"
        f"Date: {date_long(d_date)}\n\n"
        f"Showtime: {d['showtime']}\n\n"
        f"Seats: {', '.join(d['seats'])}\n\n"
        f"Tickets: {len(d['seats'])}\n\n"
        f"Total: **{inr(total)}**\n\n"
        f"Name: {google_name}\n\n"
        "Press **Confirm Booking** below (or type *yes*), or **Cancel**."
    )


# ---------- LLM fallback (Ollama) ----------
def cineverse_reply(user_message):
    import requests

    movie_catalogue = "\n".join(f"- {n}: Language={l}, Ticket price=Rs.{p}" for n, l, p in movies)
    showtime_catalogue = "\n".join(f"- {m}: {t}" for m, t in all_showtimes)
    theatre_catalogue = "\n".join(f"- {loc}: " + ", ".join(ts) for loc, ts in THEATRES.items())
    try:
        messages = [
            {"role": "system", "content": (
                "You are CINEVERSE, a friendly movie booking assistant. "
                "Answer clearly and briefly. Use only the supplied catalogue for facts. "
                "Never invent movies, prices, showtimes, theatres, seat availability or bookings. "
                "If information is missing, say you do not know. Never claim a booking was made. "
                "To book, the user should type for example: "
                "'Book Leo at CINEVERSE Anna Nagar Grand, tomorrow, 2:00 PM, A1 and A2'."
                "\n\nMOVIE CATALOGUE:\n" + movie_catalogue
                + "\n\nSHOWTIMES (same at every theatre, for the next 7 days):\n" + showtime_catalogue
                + "\n\nTHEATRES BY LOCATION:\n" + theatre_catalogue)},
            {"role": "user", "content": user_message},
        ]
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={"model": "llama3.2:1b", "messages": messages, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.RequestException:
        return ("I am unable to connect to the local AI model right now. "
                "Please check that Ollama is running and try again.")
    except (KeyError, ValueError):
        return "I am having trouble answering that. Please try again."


# ---------- Chat entry point ----------
WELCOME = {"role": "assistant",
           "content": "Hi! I can show movies, prices, theatres, dates and showtimes, and **book tickets for you**.\n\n"
                      "Try: *Book Leo at CINEVERSE Anna Nagar Grand, tomorrow, 2:00 PM, A1 and A2*"}
st.session_state.setdefault("cineverse_chat_history", [WELCOME])


def ask_concierge(prompt):
    prompt = (prompt or "").strip()
    if not prompt:
        return
    hist = st.session_state["cineverse_chat_history"]
    hist.append({"role": "user", "content": prompt})

    reply = handle_booking_message(prompt)
    if reply is None:
        resp = route_ai_tool(prompt)
        reply = format_agent_response(resp) if resp["tool"] else cineverse_reply(prompt)

    if reply:
        hist.append({"role": "assistant", "content": reply})


def submit_chat():
    ask_concierge(st.session_state.get("cv_chat_text", ""))


def clear_chat():
    st.session_state["cineverse_chat_history"] = [WELCOME]
    st.session_state.pop("pending_booking", None)
    st.session_state.pop("booking_draft", None)


# ==========================================
# TICKET DIALOG
# ==========================================
@st.dialog("Your CINEVERSE Ticket", width="large")
def show_ticket_dialog():
    tickets = load_user_tickets()
    if not tickets:
        st.info("You have not booked any tickets yet. Book a show and it will appear here.")
        return

    idx = 0
    if len(tickets) > 1:
        labels = [f"BK{t['id']:05d} | {t['movie']} | {t['date_label']} {t['showtime']}" for t in tickets]
        idx = st.selectbox("Your tickets (newest first)", range(len(tickets)),
                           format_func=lambda i: labels[i])
    t = tickets[idx]

    components.html(ticket_3d_html(t), height=460)

    png = get_ticket_png(t)
    if png:
        st.download_button("Download ticket (PNG)", data=png,
                           file_name=f"CINEVERSE_BK{t['id']:05d}.png", mime="image/png",
                           use_container_width=True, type="primary", key=f"dl_{t['id']}")
    else:
        st.download_button("Download ticket (text)", data=ticket_text(t),
                           file_name=f"CINEVERSE_BK{t['id']:05d}.txt", mime="text/plain",
                           use_container_width=True, key=f"dltxt_{t['id']}")

    st.caption(f"Booked on {t['booked_at']}")
    if t["id"] in st.session_state.get("emailed_ids", set()):
        st.caption(f"Ticket emailed to {google_email}")


# ==========================================
# CONCIERGE UI
# ==========================================
st.write("")
with st.container(key="concierge"):
    st.markdown('<div class="sec-title">Ask the Concierge</div>'
                '<div class="sec-sub">Ask about movies, theatres, dates, prices and showtimes, '
                'or tell me what to book.</div>',
                unsafe_allow_html=True)

    quick = [("All movies", "Show me all movies"),
             ("Theatres", "Show me theatres"),
             ("Compare prices", "Compare ticket prices"),
             ("Showtimes", f"Show me {selected_movie} showtimes")]
    for col, (label, text) in zip(st.columns(4), quick):
        with col:
            st.button(label, key=f"quick_{label}", use_container_width=True,
                      on_click=ask_concierge, args=(text,))

    with st.container(height=320):
        for msg in st.session_state["cineverse_chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    pending = st.session_state.get("pending_booking")
    if pending:
        st.markdown(
            f"**Pending:** {pending['movie_name']} | {pending['theatre']} | "
            f"{date_long(date.fromisoformat(pending['show_date']))} | {pending['showtime']} | "
            f"{', '.join(pending['seats'])} | {inr(pending['total_price'])}"
        )
        c1, c2 = st.columns(2)
        with c1:
            st.button("Confirm Booking", key="confirm_booking",
                      use_container_width=True, type="primary",
                      on_click=confirm_pending_booking)
        with c2:
            st.button("Cancel", key="cancel_booking",
                      use_container_width=True, on_click=cancel_pending_booking)

    with st.form("chat_form", clear_on_submit=True):
        f1, f2 = st.columns([5, 1])
        with f1:
            st.text_input("Message",
                          placeholder="e.g. Book Leo at Anna Nagar Grand, tomorrow, 2:00 PM, A1 and A2",
                          label_visibility="collapsed", key="cv_chat_text")
        with f2:
            st.form_submit_button("Ask", use_container_width=True,
                                  type="primary", on_click=submit_chat)

    st.button("Clear chat", key="clear_chat", on_click=clear_chat)


# ---------- Floating 3D "My Tickets" button ----------
_ticket_count = len(load_user_tickets())
with st.container(key="ticket_fab"):
    if st.button(f"My Tickets ({_ticket_count})", key="open_ticket"):
        show_ticket_dialog()

st.markdown('<div class="cv-footer">CINEVERSE | Movie Booking Demo | Built with Python and Streamlit</div>',
            unsafe_allow_html=True)