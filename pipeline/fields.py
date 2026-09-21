"""
Turns a read_attachment() result into the 7 canonical shipment fields, each
carrying the evidence (which raw label matched, what the raw text said) that
a NEEDS_REVIEW escalation or a debugging session would want later.

Output shape, one entry per field we managed to find:

    {
        "shipper": {"raw_label": "Shipper/Exporter", "raw_value": "APRIL FAR EAST (M) SDN BHD"},
        "container_count": {"raw_label": "No. of Containers", "raw_value": "1 x 40'HC", "value": 1},
        ...
    }

Fields not found simply aren't in the dict -- the comparison stage treats a
missing field as "missing_value" territory, not a silent 0/blank.
"""
import re

from aliases import FIELD_ALIASES, resolve_label, find_label_in_line
from extract_text import CORRUPTION_MARKER

COMPARE_FIELDS = list(FIELD_ALIASES.keys())


def _clean_value(raw: str) -> str:
    v = raw.strip()
    # drop a trailing continuation like " | 77 ROBINSON ROAD..." some xlsx
    # cells pack address into the same cell separated by " | "
    v = v.split(" | ")[0].strip()
    # docx table cells keep the entity name on the first line and the
    # address on subsequent lines (joined with \n) -- only the name is one
    # of the 7 canonical fields, so drop everything after the first line.
    v = v.split("\n")[0].strip()
    return v


def _parse_int(raw: str):
    """Pull the first integer out of strings like '6 x 40'HC' or
    '131,322 KG' or '21,577'. Returns None if nothing numeric is found."""
    digits = re.search(r"[\d,]+", raw)
    if not digits:
        return None
    cleaned = digits.group(0).replace(",", "")
    if not cleaned.isdigit():
        return None
    return int(cleaned)


_BLANK_MARKERS = {"", "???", "_______", "tba", "n/a", "na", "-", "--", "pending"}


def _is_blank(raw: str) -> bool:
    return raw.strip().lower().strip("_") in _BLANK_MARKERS or not raw.strip()


def extract_fields(read_result: dict) -> dict:
    """read_result is whatever extract_text.read_attachment() returned for
    ONE attachment. Returns {field_name: {"raw_label", "raw_value", "value", "blank"}}."""
    found = {}

    if read_result["kind"] == "pairs":
        for raw_label, raw_value in read_result["pairs"]:
            field = resolve_label(raw_label)
            if field is None or field not in FIELD_ALIASES:
                continue
            _record(found, field, raw_label, raw_value)
        # docx keeps a paragraph-text backup for anything not in a table row
        # (this template's B/L NUMBER line lives outside the table, but that
        # isn't one of the 7 compared fields, so we don't need it here).

    elif read_result["kind"] == "text":
        for line in read_result["text"].splitlines():
            line = line.strip()
            if not line:
                continue
            # Strategy A: "Label: value" -- the common txt/OCR shape.
            if ":" in line:
                label_part, _, value_part = line.partition(":")
                field = resolve_label(label_part)
                if field and field in FIELD_ALIASES:
                    _record(found, field, label_part.strip(), value_part.strip())
                    continue
            # Strategy B: label and value share one line with no delimiter
            # (the PDF layout: "Shipper APRIL FINE PAPER TRADING").
            match = find_label_in_line(line)
            if match:
                field, alias, _start, end = match
                if field in FIELD_ALIASES:
                    value_part = line[end:].strip(" :-")
                    if value_part:
                        _record(found, field, alias, value_part)

    return found


def _record(found: dict, field: str, raw_label: str, raw_value: str):
    # A corrupted value is a DIFFERENT problem than a blank one: blank means
    # "the document genuinely has nothing here" (a real missing_value case
    # to escalate); corrupted means "the PDF's text is scrambled and cannot
    # be trusted at all" -- we simply can't use it for comparison one way or
    # the other, so it's excluded from compare.py's matching rather than
    # treated as a fact about the document.
    if CORRUPTION_MARKER in raw_label or CORRUPTION_MARKER in raw_value:
        entry = {"raw_label": raw_label, "raw_value": "<unreadable: corrupted PDF text>",
                  "corrupted": True, "blank": False, "value": None}
        if field not in found:
            found[field] = entry
        return

    raw_value = _clean_value(raw_value)
    entry = {
        "raw_label": raw_label,
        "raw_value": raw_value,
        "blank": _is_blank(raw_value),
    }
    if field in ("container_count", "gross_weight_kg"):
        entry["value"] = None if entry["blank"] else _parse_int(raw_value)
        if entry["value"] is None and not entry["blank"]:
            entry["blank"] = True  # couldn't parse a number -> treat as missing
    else:
        entry["value"] = None if entry["blank"] else raw_value

    # If we already found this field from an earlier, more specific alias
    # match, don't overwrite with a weaker/duplicate hit -- first confident
    # match wins (fields already checked longest-alias-first upstream).
    if field not in found:
        found[field] = entry