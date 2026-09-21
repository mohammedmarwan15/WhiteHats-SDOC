"""
Field-alias dictionary -- the answer to "the same information can look
different" (Port of Loading vs Load Port vs POL).

Each of the 7 compared fields maps to every label variant we know it can
appear under. Matching is longest-alias-first so a specific variant like
"Port of Loading (POL)" is preferred over the shorter "Port of Loading"
when both would technically match.
"""
import re

FIELD_ALIASES = {
    "shipper": [
        "Shipper/Exporter", "Shipper (Principal or Seller)", "Shipper Name",
        "Shipper",
    ],
    "consignee": [
        "Consignee (Non-Negotiable)", "To the Order of", "Ultimate Consignee",
        "Consignee",
    ],
    "notify_party": [
        "Notify Party/Intermediate Consignee", "Notify Party", "Notify",
    ],
    "port_of_loading": [
        "Port of Loading (POL)", "Port of Loading", "Load Port",
        "Loading Port", "POL",
    ],
    "port_of_discharge": [
        "Port of Discharge (POD)", "Port of Discharge", "Discharge Port",
        "Port of Delivery", "POD",
    ],
    "container_count": [
        "No. of Containers or Packages", "Total Containers",
        "No. of Containers", "Number of Containers", "Container Count",
        "Total No. of Containers",
    ],
    "gross_weight_kg": [
        "Gross Weight毛重(KGS)", "Gross Weight (KG)", "Gross Wt (kgs)",
        "Total Gross Weight", "Gross Weight", "Gross Wt", "Total Weight",
    ],
}

CONTEXT_LABELS = {
    "vessel": ["Export Carrier (vessel, voyage)", "Ocean Vessel", "Vessel Name", "Vessel"],
    "voyage": ["Voyage No.", "Voy. No", "Voy.", "Voyage"],
    "commodity": ["Kinds of Packages; Description of Goods", "Description of Goods",
                  "Commodity", "Description"],
    "booking": ["Booking Reference", "Booking No.", "Booking Ref"],
    "bl_no": ["Bill of Lading No.", "B/L NUMBER", "B/L No.", "BL No."],
}

ALL_FIELDS = {**FIELD_ALIASES, **CONTEXT_LABELS}


def _norm_label(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[():/,.]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def register_alias(field: str, new_label: str):
    """Teach the dictionary a new label variant at runtime."""
    table = FIELD_ALIASES if field in FIELD_ALIASES else CONTEXT_LABELS
    table.setdefault(field, [])
    if new_label not in table[field]:
        table[field].insert(0, new_label)
        ALL_FIELDS[field] = table[field]


def _build_index():
    index = []
    for field, aliases in ALL_FIELDS.items():
        for alias in aliases:
            index.append((_norm_label(alias), field, alias))
    index.sort(key=lambda t: -len(t[0]))
    return index


def resolve_label(raw_label: str):
    """Map a raw label string (e.g. 'Load Port', 'GROSS WEIGHT',
    'Shipper (发货人)') to a canonical field name, or None."""
    norm = _norm_label(raw_label)
    if not norm:
        return None
    index = _build_index()
    for norm_alias, field, _orig in index:
        if norm == norm_alias:
            return field
    for norm_alias, field, _orig in index:
        if norm.startswith(norm_alias + " ") or norm == norm_alias:
            return field
    return None


def find_label_in_line(line: str):
    """For text lines where label and value share one line with no
    delimiter (e.g. a PDF: 'Shipper APRIL FINE PAPER TRADING')."""
    norm_line = _norm_label(line)
    best = None
    for norm_alias, field, orig in _build_index():
        idx = norm_line.find(norm_alias)
        if idx == -1:
            continue
        if idx != 0 and norm_line[idx - 1] != " ":
            continue
        if best is None or len(norm_alias) > len(best[1]):
            best = (field, norm_alias, idx, idx + len(norm_alias))
    if best is None:
        return None
    field, norm_alias, _start, _end = best
    for norm_alias2, f2, orig in _build_index():
        if f2 != field or norm_alias2 != norm_alias:
            continue
        m = re.search(re.escape(orig), line, re.I)
        if m:
            return field, orig, m.start(), m.end()
    return None