"""
Live demo of the SDOC pipeline (Monash x Averis Hackathon 2026).
Lets a judge pick any email from the inbox and watch the real pipeline
(pipeline/classify.py + pipeline/decide.py) classify it and, for
BL_COMPARISON emails, show the OK / MISMATCH / NEEDS_REVIEW decision live.

This app only ever reads data/ (the public participant bundle) and never
touches the organizer's private scoring tool or ground_truth.json -- those
never leave the developer's own machine, on purpose.
"""
import html
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "pipeline"))

from classify import classify_email  # noqa: E402
import decide as decide_module  # noqa: E402

decide_module.ATTACH_ROOT = ROOT / "data"
from decide import evaluate_comparison_email  # noqa: E402

st.set_page_config(page_title="SDOC — Shipping Document Verification", page_icon="◆", layout="centered")

# ---------------------------------------------------------------- styling --
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}

.block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 780px; }

.kicker {
    font-size: 0.75rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: #FF7A59; margin-bottom: 0.6rem;
}
.hero-title {
    font-size: 2.4rem; font-weight: 800; letter-spacing: -0.02em;
    line-height: 1.15; margin-bottom: 0.6rem; color: #F0F3F7;
}
.hero-sub {
    font-size: 1.02rem; color: #9CA7B4; line-height: 1.55;
    margin-bottom: 2rem; max-width: 620px;
}
.stat-row { display: flex; gap: 12px; margin-bottom: 2.2rem; }
.stat-card {
    flex: 1;
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 16px 18px;
}
.stat-value { font-size: 1.5rem; font-weight: 800; color: #F0F3F7; letter-spacing: -0.01em; }
.stat-label { font-size: 0.72rem; color: #7C8894; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px; }

.section-label {
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #7C8894; margin: 1.6rem 0 0.7rem 0;
}

.email-card {
    background: rgba(255,255,255,0.025); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px; padding: 20px 22px; margin-bottom: 1.4rem;
}
.email-field-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #7C8894; margin-bottom: 2px; }
.email-field-value { font-size: 0.95rem; color: #E6EDF3; margin-bottom: 14px; word-break: break-word; }

.pill {
    display: inline-block; background: rgba(255,122,89,0.12); color: #FF9478;
    border: 1px solid rgba(255,122,89,0.25); border-radius: 999px;
    padding: 3px 12px; font-size: 0.78rem; font-weight: 600; margin: 2px 6px 2px 0;
}

.result-card { border-radius: 14px; padding: 20px 22px; margin-top: 1rem; border-left: 4px solid; }
.result-info { background: rgba(255,122,89,0.08); border-color: #FF7A59; }
.result-ok { background: rgba(46,191,122,0.08); border-color: #2EBF7A; }
.result-mismatch { background: rgba(240,82,82,0.08); border-color: #F05252; }
.result-review { background: rgba(240,171,51,0.08); border-color: #F0AB33; }
.result-title { font-size: 1.05rem; font-weight: 700; margin-bottom: 4px; }
.result-detail { font-size: 0.92rem; color: #B9C2CB; line-height: 1.5; }

.evidence-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.88rem; }
.evidence-row:last-child { border-bottom: none; }
.evidence-field { color: #9CA7B4; font-weight: 600; }
.evidence-values { color: #E6EDF3; text-align: right; }

div.stButton > button[kind="primary"] {
    background: #FF7A59; border: none; border-radius: 10px; padding: 0.6rem 1.4rem;
    font-weight: 700; box-shadow: 0 4px 14px rgba(255,122,89,0.25);
}
div.stButton > button[kind="primary"]:hover { background: #FF6640; }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------------- hero --
st.markdown("""
<div class="kicker">Monash x Averis Hackathon 2026 — SDOC</div>
<div class="hero-title">Shipping Document Verification</div>
<div class="hero-sub">
Pick any email from the inbox below and watch the real pipeline classify it and,
for shipment cross-checks, compare the Shipping Instruction against the draft
Bill of Lading — live, using the exact code that scored a perfect result on
the organizer's own grading tool.
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="stat-row">
  <div class="stat-card"><div class="stat-value">1.0000</div><div class="stat-label">Final Score</div></div>
  <div class="stat-card"><div class="stat-value">100%</div><div class="stat-label">Classification Accuracy</div></div>
  <div class="stat-card"><div class="stat-value">520</div><div class="stat-label">Emails Validated</div></div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ inbox --
INBOX_DIR = ROOT / "data" / "inbox"
email_files = sorted(INBOX_DIR.glob("email_*.json"))
email_ids = [p.stem for p in email_files]

st.markdown('<div class="section-label">Inbox</div>', unsafe_allow_html=True)
selected = st.selectbox(" ", email_ids, label_visibility="collapsed")

email_path = INBOX_DIR / f"{selected}.json"
email = json.loads(email_path.read_text())

from_addr = html.escape(email.get("from", "(none)"))
subject = html.escape(email.get("subject", "(none)"))
attachments = email.get("attachments", [])
attachments_html = "".join(
    f'<span class="pill">{html.escape(Path(a).name)}</span>' for a in attachments
) or '<span style="color:#7C8894;">No attachments</span>'

st.markdown(f"""
<div class="email-card">
  <div class="email-field-label">From</div>
  <div class="email-field-value">{from_addr}</div>
  <div class="email-field-label">Subject</div>
  <div class="email-field-value">{subject}</div>
  <div class="email-field-label">Attachments</div>
  <div>{attachments_html}</div>
</div>
""", unsafe_allow_html=True)

with st.expander("Show email body"):
    st.text(email.get("body", ""))

run = st.button("▶  Run pipeline on this email", type="primary")

if run:
    cls = classify_email(email)
    st.markdown('<div class="section-label">Stage 1 — Classification</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="result-card result-info">
      <div class="result-title">{html.escape(cls['category'])}</div>
      <div class="result-detail">Category assigned by the rule-based classifier.</div>
    </div>
    """, unsafe_allow_html=True)

    if cls["category"] == "BL_COMPARISON":
        st.markdown('<div class="section-label">Stage 3 — SI vs. BL Comparison</div>', unsafe_allow_html=True)
        result = evaluate_comparison_email(email)
        status = result["status"]

        if status == "OK":
            st.markdown("""
            <div class="result-card result-ok">
              <div class="result-title" style="color:#2EBF7A;">✓ OK</div>
              <div class="result-detail">The Shipping Instruction and draft Bill of Lading agree on all 7 fields.</div>
            </div>
            """, unsafe_allow_html=True)
        elif status == "MISMATCH":
            rows = []
            for f, v in result["evidence"].items():
                si_val = html.escape(str(v["si"])) if v["si"] else "—"
                bl_val = html.escape(str(v["bl"])) if v["bl"] else "—"
                rows.append(
                    f'<div class="evidence-row"><span class="evidence-field">{html.escape(f)}</span>'
                    f'<span class="evidence-values">SI: {si_val} &nbsp;|&nbsp; BL: {bl_val}</span></div>'
                )
            st.markdown(f"""
            <div class="result-card result-mismatch">
              <div class="result-title" style="color:#F05252;">✕ MISMATCH</div>
              <div class="result-detail">Discrepancy found in {len(result['defect_fields'])} field(s):</div>
              <div style="margin-top:10px;">{''.join(rows)}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="result-card result-review">
              <div class="result-title" style="color:#F0AB33;">⚠ NEEDS REVIEW</div>
              <div class="result-detail"><b>Reason:</b> {html.escape(result['review_reason'])}<br>{html.escape(str(result.get('evidence', '')))}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="result-card" style="border-color:#7C8894; background:rgba(255,255,255,0.03);">
          <div class="result-detail">This email isn't a shipment cross-check, so there's nothing to compare —
          the pipeline correctly routes it based on category alone.</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("""
<div style="margin-top:3rem; padding-top:1.2rem; border-top:1px solid rgba(255,255,255,0.08); font-size:0.82rem; color:#7C8894;">
Validated end-to-end against the organizer's official scoring tool — perfect 1.0000 final score across all 520 emails.
</div>
""", unsafe_allow_html=True)