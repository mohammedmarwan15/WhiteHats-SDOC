"""
Stage 1 -- email classification (rule-based, no AI model needed).

Sorts each email into one of: BL_COMPARISON, SI_REQUEST, INVOICE_QUERY,
GENERAL, SPAM.

Rules are checked in a fixed PRIORITY ORDER (most distinctive / least
ambiguous category first), and the first rule that matches wins.
"""
import re


def _norm(s: str) -> str:
    return (s or "").lower()


# --- SPAM -------------------------------------------------------------
SPAM_PATTERNS = [
    r"\bbitcoin\b", r"\bcrypto\b", r"guaranteed\s+\d+%", r"\bwinner\b",
    r"\byou\s*'?ve\s+won\b", r"claim\s+your\s+prize", r"\blottery\b",
    r"weird\s+trick", r"\d+%\s*off\b.*(premium|exclusive|today|week)",
    r"exclusive\s+offer", r"verify\s+(your\s+)?account\s+immediately",
    r"account\s+(will\s+be\s+)?suspended", r"storage\s+is\s+full",
    r"click\s+here\s+(now|immediately)", r"act\s+now", r"risk[- ]free",
    r"congratulations.{0,20}(selected|won)", r"unclaimed\s+(parcel|package)",
    r"pay\s+a\s+small\s+fee", r"customs\s+fee.{0,20}release",
    r"\bviagra\b", r"\bcasino\b", r"work\s+from\s+home.{0,20}\$",
    r"avoid\s+suspension", r"dear\s+valued\s+customer", r"hot\s+singles",
    r"in\s+your\s+area.{0,15}(connect|want)", r"increase\s+your\s+.*revenue",
    r"undelivered\s+messages?.{0,15}mailbox", r"confirm\s+your\s+bank\s+details",
    r"kindly\s+confirm\s+your\s+bank", r"verify\s+your\s+bank",
]

# --- GENERAL (automated / operational noise) -----------------------------
# Checked ahead of INVOICE_QUERY because this dataset's automated
# notifications literally say "Billing Process Completed", which would
# otherwise false-positive as an invoice query every time.
GENERAL_PATTERNS = [
    r"--\s*rpa\s+bot", r"automated\s+notification", r"no\s+action\s+required",
    r"_rpa_", r"berthing\s+report", r"time\s+off\s+request",
    r"update\s+summary", r"sla\s+reminder", r"holiday\s+notice",
    r"approval\s+required",
]

# --- INVOICE_QUERY ------------------------------------------------------
# Deliberately NOT a bare `\binvoice\b` -- a shipping-instruction email
# routinely lists "3 Original invoice" in its documents checklist, which
# would false-positive every single SI request otherwise.
INVOICE_PATTERNS = [
    r"\bbilling\b", r"\bmissing\s+gr\b", r"\bcancel\s+invoice\b",
    r"\blocal\s+charges\b", r"\bd\s*&\s*d\s+charges\b", r"\btotal\s+freight\b",
    r"\btelex\s+release\s+charges\b", r"\bcredit\s+note\b", r"\bdebit\s+note\b",
    r"\bpayment\b.{0,15}(due|overdue|query)", r"\bfreight\s+(invoice|charge)",
    r"\binvoice\s+(query|discrepancy|issue|amount|number|not\s+received)",
    r"\b(wrong|duplicate|missing)\s+invoice\b", r"\bregarding\s+invoice\b",
]

# --- SI_REQUEST -----------------------------------------------------------
SI_REQUEST_PATTERNS = [
    r"\bcust\s+si\b", r"\brequest\s+si\b", r"\bsi\s+needed",
    r"^\s*si\s*-", r"\bsi\s*-\s*.*direct\(", r"\bnew\s+si\b",
    r"\bshipping\s+instructions?\s+(needed|required|request)",
    r"\bplease\s+(send|prepare|issue)\s+.*\bsi\b",
]

# --- BL_COMPARISON --------------------------------------------------------
BL_COMPARISON_PATTERNS = [
    r"\brequest\s+bl\s+draft\b", r"\bto\s+confirm\s+docs\b",
    r"\bdraft\s+bl\b", r"\bamend\b.{0,20}\bbl\b", r"\bbl\s+draft\b",
    r"\bcheck\s+(the\s+)?(draft\s+)?bl\b", r"\bplease\s+check\s+(and\s+)?confirm\b",
    r"\bcompare\s+(the\s+)?(si|bl)\b",
    r"^\s*a?[a-z]{2,5}\s*-\s*[a-z ,._/]+-\s*[a-z]+\(",
]

_SPAM_RE = [re.compile(p, re.I) for p in SPAM_PATTERNS]
_GENERAL_RE = [re.compile(p, re.I) for p in GENERAL_PATTERNS]
_INVOICE_RE = [re.compile(p, re.I) for p in INVOICE_PATTERNS]
_SI_RE = [re.compile(p, re.I) for p in SI_REQUEST_PATTERNS]
_BL_RE = [re.compile(p, re.I) for p in BL_COMPARISON_PATTERNS]


def _matches_any(patterns, text) -> bool:
    return any(p.search(text) for p in patterns)


_PRIORITY = [
    ("SPAM", _SPAM_RE),
    ("GENERAL", _GENERAL_RE),
    ("INVOICE_QUERY", _INVOICE_RE),
    ("SI_REQUEST", _SI_RE),
    ("BL_COMPARISON", _BL_RE),
]


def classify_email(email: dict) -> dict:
    """Returns {"category": ..., "confidence": "rule_high"|"rule_low"}."""
    subject = _norm(email.get("subject", ""))
    body = _norm(email.get("body", ""))
    has_attachments = bool(email.get("attachments"))

    # Pass 1: subject only -- the real signal lives here.
    for category, patterns in _PRIORITY:
        if _matches_any(patterns, subject):
            return {"category": category, "confidence": "rule_high"}

    # Pass 2: fall back to the body (lower confidence).
    for category, patterns in _PRIORITY:
        if _matches_any(patterns, body):
            return {"category": category, "confidence": "rule_low"}

    # Pass 3: attachment-name fallback.
    if has_attachments:
        names = " ".join(email["attachments"]).lower()
        if "_si." in names or "_bl." in names:
            return {"category": "BL_COMPARISON", "confidence": "rule_low"}

    return {"category": "GENERAL", "confidence": "rule_low"}