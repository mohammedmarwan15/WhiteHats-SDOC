"""
The Stage-3 orchestrator: for one BL_COMPARISON email, decides between
OK / MISMATCH / NEEDS_REVIEW, in that priority order --

    can't even attempt it confidently?  -> NEEDS_REVIEW (with a reason + evidence)
    attempted, all 7 fields agree?      -> OK
    attempted, >=1 field differs?       -> MISMATCH (with the exact fields)

This is the "ask for help instead of guessing" capability from the brief: every
NEEDS_REVIEW comes with `evidence`, a short human-readable explanation of what
went wrong and where to look, not just a bare status code.
"""
from pathlib import Path

from extract_text import read_attachment
from fields import extract_fields, COMPARE_FIELDS
from compare import compare_fields

ATTACH_ROOT = Path(__file__).parent.parent / "data"

# Body phrasing that distinguishes "please prepare a BL that doesn't exist
# yet" (normal, nothing to compare, not an error) from "we expected to
# compare today but something's missing" (a genuine escalation). Learned by
# reading the real body text of both groups side by side -- see the dev
# notes -- not hardcoded per email.
_FUTURE_REQUEST_PHRASES = [
    "assist to send the draft bl", "please send the draft bl",
    "please prepare the draft bl", "kindly send the draft bl",
]
_MISSING_ADMISSION_PHRASES = [
    "dropped", "still missing", "not attached", "not been attached",
    "no attachment", "missing attachment",
]

# A document that isn't really an SI/BL at all announces itself; check for
# the obvious tells AND fall back to "did we find almost none of the 7
# fields at all", which generalizes beyond these exact three doc types.
_WRONG_DOC_KEYWORDS = [
    "commercial invoice", "packing list", "certificate of origin",
    "not a shipping instruction", "not an si or bl", "packing list only",
]


def _find_attachment(attachments, suffix_marker):
    for a in attachments:
        name = Path(a).name.upper()
        if suffix_marker in name:
            return ATTACH_ROOT / a
    return None


def _looks_like_wrong_doc(read_result: dict, found_fields: dict) -> bool:
    text = (read_result.get("text") or "").lower()
    if any(kw in text for kw in _WRONG_DOC_KEYWORDS):
        return True
    # a real SI/BL always carries at least the port + weight fields; a
    # commercial invoice / packing list / certificate of origin structurally
    # never does.
    core = {"port_of_loading", "port_of_discharge", "container_count", "gross_weight_kg"}
    return len(core & found_fields.keys()) == 0


def evaluate_comparison_email(email: dict) -> dict:
    attachments = email.get("attachments", [])
    body = (email.get("body") or "").lower()

    si_path = _find_attachment(attachments, "_SI.")
    bl_path = _find_attachment(attachments, "_BL.")

    # --- missing attachment ------------------------------------------------
    if bl_path is None:
        admits_missing = any(p in body for p in _MISSING_ADMISSION_PHRASES)
        is_future_request = any(p in body for p in _FUTURE_REQUEST_PHRASES)
        if admits_missing and not is_future_request:
            reason = "no attachments at all" if si_path is None else "SI present, BL still missing"
            return _needs_review("missing_attachment",
                                  f"No draft BL to compare against ({reason}); "
                                  f"the email itself says so.")
        # normal "please prepare a BL that doesn't exist yet" request --
        # nothing to compare, and that's expected, not an error.
        return _ok()

    if si_path is None:
        return _needs_review("missing_attachment",
                              "BL attachment present but no SI to compare it against.")

    # --- read both attachments ----------------------------------------------
    si_read = read_attachment(si_path)
    bl_read = read_attachment(bl_path)

    if si_read["kind"] == "unreadable":
        return _needs_review("unreadable", f"SI attachment could not be read: {si_read['error']}")
    if bl_read["kind"] == "unreadable":
        return _needs_review("unreadable", f"BL attachment could not be read: {bl_read['error']}")

    # OCR text is inherently lower-confidence than a native text layer --
    # per the brief, a scanned document should go to a human, not be quietly
    # trusted just because OCR produced *something*.
    if si_read.get("method") == "ocr" or bl_read.get("method") == "ocr":
        which = "SI" if si_read.get("method") == "ocr" else "BL"
        return _needs_review("unreadable",
                              f"{which} attachment is an image-only scan; OCR text is "
                              f"not reliable enough to compare without a human check.")

    si_fields = extract_fields(si_read)
    bl_fields = extract_fields(bl_read)

    # --- widespread corruption -------------------------------------------------
    # One scrambled field is excluded from comparison (handled in compare.py)
    # rather than blocking the whole email -- a single PDF rendering glitch
    # shouldn't hide a real defect elsewhere in the same document. But if
    # MULTIPLE fields on one side are scrambled, that's no longer "one odd
    # field", it's a document we can't trust at all -- escalate instead of
    # comparing on whatever's left.
    n_corrupt_si = sum(1 for f in si_fields.values() if f.get("corrupted"))
    n_corrupt_bl = sum(1 for f in bl_fields.values() if f.get("corrupted"))
    if n_corrupt_si >= 2 or n_corrupt_bl >= 2:
        return _needs_review("unreadable",
                              f"Too many fields show PDF text corruption to trust a "
                              f"comparison (SI: {n_corrupt_si}, BL: {n_corrupt_bl} affected).")

    # --- wrong document type -------------------------------------------------
    if _looks_like_wrong_doc(bl_read, bl_fields):
        return _needs_review("wrong_doc_type",
                              "The 'BL' attachment doesn't look like a Bill of Lading "
                              "(missing port/weight fields, or an explicit different-doc header).")
    if _looks_like_wrong_doc(si_read, si_fields):
        return _needs_review("wrong_doc_type",
                              "The 'SI' attachment doesn't look like a Shipping Instruction.")

    # --- missing values --------------------------------------------------------
    missing = []
    for field in COMPARE_FIELDS:
        si_e = si_fields.get(field)
        bl_e = bl_fields.get(field)
        if not si_e or si_e["blank"]:
            missing.append(f"{field} (SI)")
        if not bl_e or bl_e["blank"]:
            missing.append(f"{field} (BL)")
    if missing:
        return _needs_review("missing_value",
                              "Required field(s) blank or unreadable, not a real "
                              "discrepancy: " + ", ".join(missing))

    # --- everything present -- do the actual comparison -----------------------
    comparison = compare_fields(si_fields, bl_fields)
    defect_fields = sorted(f for f, r in comparison.items() if not r["match"])

    if defect_fields:
        return {
            "status": "MISMATCH",
            "review_reason": None,
            "has_defect": True,
            "defect_fields": defect_fields,
            "evidence": {f: {"si": comparison[f]["si_value"], "bl": comparison[f]["bl_value"]}
                         for f in defect_fields},
        }
    return _ok()


def _ok():
    return {"status": "OK", "review_reason": None, "has_defect": False,
            "defect_fields": [], "evidence": None}


def _needs_review(reason, explanation):
    return {"status": "NEEDS_REVIEW", "review_reason": reason, "has_defect": False,
            "defect_fields": [], "evidence": explanation}