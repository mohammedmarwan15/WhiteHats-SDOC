# SDOC — Shipping Document Verification Pipeline

An automated pipeline that reads shipping-related inbox emails, classifies them, and — for emails carrying a Shipping Instruction (SI) and draft Bill of Lading (BL) for comparison — extracts key shipment fields from both documents and verifies they agree. Built for the Monash x Averis Hackathon 2026 (SDOC use case).

## The problem

A shipping documentation team receives a high volume of email daily: requests to prepare shipping instructions, invoice queries, spam, and — critically — emails asking staff to cross-check a draft Bill of Lading against the original Shipping Instruction before a shipment goes out. A single mismatched field (wrong consignee, wrong port, wrong container count) can cause customs delays, misdirected cargo, or contractual disputes. Today this cross-checking is done manually, by a person reading two documents side by side.

This pipeline automates that check end to end, while being explicit about its own limits: when it cannot confidently read or compare a document, it says so and escalates to a human, rather than silently guessing.

## What it does

1. **Classifies** every inbox email into one of five categories: `BL_COMPARISON`, `SI_REQUEST`, `INVOICE_QUERY`, `GENERAL`, or `SPAM`.
2. For `BL_COMPARISON` emails, **extracts** 7 canonical shipment fields — shipper, consignee, notify party, port of loading, port of discharge, container count, and gross weight — from both the SI and BL attachments, regardless of file format (`.txt`, `.pdf`, `.docx`, `.xlsx`) or how each document happens to label those fields.
3. **Compares** the two sets of fields, normalizing away formatting noise (case, punctuation, trailing location codes) so only genuine discrepancies are reported.
4. **Decides** a final status per email — `OK` (documents agree), `MISMATCH` (a real discrepancy, with the exact field(s) named), or `NEEDS_REVIEW` (the pipeline cannot confidently decide, with a specific reason and evidence) — and routes `NEEDS_REVIEW` cases to a human instead of guessing.

## Why rule-based, not an LLM

This pipeline is deliberately built on structured rules (regex-based classification, an alias dictionary for field-label matching, position-aware PDF parsing) rather than calling out to a language model. Three reasons:

- **No API access was provided** for this hackathon, and running a local LLM was not a realistic option in the target deployment environment.
- **Determinism and auditability.** Every decision this pipeline makes can be traced back to an exact rule or comparison — important for a system a compliance team would actually need to trust and audit, not just a black box that "usually gets it right."
- **Cost and latency at scale.** A real shipping documentation team processes a high volume of email daily. A rule-based pipeline runs in milliseconds per email with zero inference cost, which matters when weighed against calling an LLM per email at scale.

## Architecture

```
inbox email (JSON)
      │
      ▼
 classify.py ──────────────► category (BL_COMPARISON / SI_REQUEST / INVOICE_QUERY / GENERAL / SPAM)
      │
      │ (if BL_COMPARISON)
      ▼
 decide.py  (orchestrator)
      │
      ├─ find SI + BL attachments ─── missing? ──► NEEDS_REVIEW (missing_attachment)
      │
      ├─ extract_text.py  (per attachment: .txt / .pdf / .docx / .xlsx reader)
      │        │
      │        └─ unreadable / OCR-only? ────────► NEEDS_REVIEW (unreadable)
      │
      ├─ fields.py + aliases.py  (map raw labels → 7 canonical fields)
      │        │
      │        └─ wrong document type? ──────────► NEEDS_REVIEW (wrong_doc_type)
      │        └─ required field blank? ─────────► NEEDS_REVIEW (missing_value)
      │
      ▼
 compare.py  (normalize + compare each of the 7 fields)
      │
      ├─ all fields agree? ────────────────────────► OK
      └─ any field differs? ───────────────────────► MISMATCH (with exact defect_fields)
```

### Module breakdown

| File | Responsibility |
|---|---|
| `pipeline/classify.py` | Stage 1: rule-based email classification via priority-ordered regex patterns over subject, body, and attachment names. |
| `pipeline/aliases.py` | Maps every known label variant of the 7 canonical fields (e.g. "Port of Loading", "Load Port", "POL") to a single canonical field name, so differently-labeled documents can still be compared. Supports runtime learning of new label variants. |
| `pipeline/extract_text.py` | Format-specific readers for `.txt`, `.pdf` (native text + OCR fallback for scanned images), `.docx`, and `.xlsx`, all normalized to one common output shape. Includes a PDF text-corruption detector (below). |
| `pipeline/fields.py` | Turns raw extracted text/table rows into the 7 canonical fields with their values, distinguishing "found and valid," "blank," and "corrupted/unreadable." |
| `pipeline/compare.py` | Field-by-field comparison with normalization (case, whitespace, trailing location codes) so formatting differences are never mistaken for real discrepancies. |
| `pipeline/decide.py` | Stage 3 orchestrator: ties every check above together into a final OK / MISMATCH / NEEDS_REVIEW decision with human-readable evidence. |
| `pipeline/assemble.py` | Runs the full pipeline over every email in `data/inbox` and writes `submission.json`. |

## A real edge case this pipeline handles: corrupted PDF text

While testing against the organizer's private scoring tool, one email's field comparison came back wrong. Investigation traced it to the source PDF itself: two separate pieces of text (a label's tail end and the field's actual value) had been rendered by the PDF generator at literally overlapping pixel positions, producing text that no regex or alias-matching could ever parse correctly — e.g. `"Notify Party/Intermediate ConsKiTgPne CeO., LTD"` is "Consignee" and "KTP CO., LTD" interleaved character by character.

Rather than patch around this one email, `extract_text.py` reconstructs PDF text from individual character bounding-box positions and flags any pair of characters that overlap by more than a fraction of a point as corrupted — a signature that never occurs in a cleanly-rendered PDF. A corrupted field is then excluded from comparison (neither treated as a match nor a false mismatch), while the rest of the document's genuinely comparable fields are still checked normally. If corruption affects too many fields in one document to trust it at all, the whole email is escalated to `NEEDS_REVIEW` instead of guessing.

## Results (validated with the organizer's official scoring tool)

Running the full pipeline against all 520 emails in the dataset and scoring the resulting `submission.json` with the organizer-provided `score_cli.py`:

- **Stage 1 classification:** 100% accuracy, macro-F1 1.000 across all 5 categories.
- **Stage 3 comparison:** defect recall 1.000, defect precision 1.000, field-level F1 1.000.
- **Reliability (escalation):** all 20 genuinely ambiguous cases across all 4 escalation reasons (`wrong_doc_type`, `missing_attachment`, `unreadable`, `missing_value`) correctly identified, zero false escalations.
- **End-to-end (the headline metric):** 46/46 genuine defects caught with the exact defect field(s) identified.
- **Final weighted score: 1.0000**

## Setup instructions

**Requirements:** Python 3.10+, and (optionally) Tesseract OCR installed at the OS level if you want scanned-PDF support to work.

```bash
# 1. Clone the repo
git clone https://github.com/mohammedmarwan15/WhiteHats-SDOC.git
cd WhiteHats-SDOC

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1        # Windows PowerShell
# source venv/bin/activate       # macOS/Linux

# 3. Install dependencies
pip install pdfplumber python-docx openpyxl pytesseract pypdfium2 pillow

# 4. Run the pipeline over the full inbox
python pipeline\assemble.py
```

This produces `submission.json` at the project root, containing the classification and comparison decision for every email in `data/inbox`, in the exact schema the hackathon expects.

## Challenges faced

- **Same information, different labels.** SI and BL templates from different senders label the same field differently ("Port of Loading" vs "Load Port" vs "POL"). Solved with a longest-alias-first matching dictionary rather than hardcoded per-template parsing.
- **Multi-format attachments.** Fields could arrive as plain text, PDF (sometimes scanned images requiring OCR), Word tables, or Excel rows — each needed its own extraction strategy behind one common interface.
- **Deciding when NOT to decide.** The hardest part of this brief wasn't matching fields when data was clean — it was recognizing the many ways data could be *not* clean (missing attachments, wrong document types, blank fields, unreadable scans, corrupted PDF text) and routing each to a human with a clear reason rather than making a confident wrong guess.
- **A real PDF rendering defect** (see above) that required inspecting the PDF's raw character-position data to properly diagnose and fix, rather than trusting a plain text-extraction library at face value.

## Future roadmap

- Extend the alias dictionary to self-learn from human corrections on `NEEDS_REVIEW` cases, closing the loop between escalation and future accuracy.
- Add a lightweight web interface for reviewing `NEEDS_REVIEW` cases and resolving them without touching the underlying data files.
- Explore a hybrid approach where a local LLM handles only the residual cases the rule-based system cannot resolve, keeping the deterministic, auditable path as the default for the vast majority of emails.
- Add structured logging/metrics so a real documentation team could monitor classification and defect-catch rates over time in production.
