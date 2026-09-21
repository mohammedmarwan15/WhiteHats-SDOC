"""
Field-by-field comparison, with normalization so formatting noise never gets
reported as a real discrepancy (the "same info looks different" problem, but
now on the VALUE side rather than the label side).
"""
import re

from fields import COMPARE_FIELDS

NUMERIC_FIELDS = {"container_count", "gross_weight_kg"}

# Matches a trailing UN/LOCODE-style code some renderings append after a
# port name, e.g. "PORT KLANG (WESTPORT), MALAYSIA (MYPKG)" -> the LAST
# parenthetical only, so a legitimate qualifier like "(WESTPORT)" earlier in
# the name is left alone.
_TRAILING_CODE_RE = re.compile(r"\s*\([A-Z0-9]{3,8}\)\s*$")


def normalize_name(value: str) -> str:
    v = value.upper().strip()
    v = re.sub(r"\s+", " ", v)
    v = v.rstrip(".,")
    return v


def normalize_port(value: str) -> str:
    v = value.strip()
    # a document may append a short code (from render.py: "(MYPKG)") that
    # another format of the SAME field never includes -- strip it before
    # comparing so its mere presence/absence never counts as a mismatch.
    v = _TRAILING_CODE_RE.sub("", v)
    return normalize_name(v)


def values_equal(field: str, si_entry: dict, bl_entry: dict) -> bool:
    if field in NUMERIC_FIELDS:
        return si_entry["value"] == bl_entry["value"]
    if field in ("port_of_loading", "port_of_discharge"):
        return normalize_port(si_entry["value"]) == normalize_port(bl_entry["value"])
    return normalize_name(si_entry["value"]) == normalize_name(bl_entry["value"])


def compare_fields(si_fields: dict, bl_fields: dict) -> dict:
    """Returns {field: {"match": bool, "si_value", "bl_value"}} for every one
    of the 7 fields BOTH documents actually had a usable value for. Fields
    missing OR corrupted on either side are left out here on purpose -- a
    corrupted PDF field can't be used as evidence either way, and a genuinely
    missing one is the caller's (decide.py's) job to route to
    NEEDS_REVIEW/missing_value, not silently skip or silently match."""
    result = {}
    for field in COMPARE_FIELDS:
        si_e = si_fields.get(field)
        bl_e = bl_fields.get(field)
        if (not si_e or not bl_e or si_e["blank"] or bl_e["blank"]
                or si_e.get("corrupted") or bl_e.get("corrupted")):
            continue
        result[field] = {
            "match": values_equal(field, si_e, bl_e),
            "si_value": si_e["value"] if field in NUMERIC_FIELDS else si_e["raw_value"],
            "bl_value": bl_e["value"] if field in NUMERIC_FIELDS else bl_e["raw_value"],
        }
    return result