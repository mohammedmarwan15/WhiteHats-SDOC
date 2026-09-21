"""
Runs the full pipeline over every email in data/inbox and writes submission.json
in the exact shape the hackathon expects: one entry per email_id.
"""
import json
from pathlib import Path

from classify import classify_email
from decide import evaluate_comparison_email

ROOT = Path(__file__).parent.parent
INBOX_DIR = ROOT / "data" / "inbox"


def build_submission(verbose=False):
    submission = {}
    errors = []
    status_counts = {}

    for path in sorted(INBOX_DIR.glob("email_*.json")):
        email = json.loads(path.read_text())
        eid = email["email_id"]
        cls = classify_email(email)
        category = cls["category"]

        if category == "BL_COMPARISON":
            try:
                decision = evaluate_comparison_email(email)
            except Exception as exc:  # noqa: BLE001 -- never let one bad
                # email crash the whole 520-email run; escalate it instead.
                errors.append((eid, str(exc)))
                decision = {"status": "NEEDS_REVIEW", "review_reason": "unreadable",
                            "has_defect": False, "defect_fields": [],
                            "evidence": f"internal error: {exc}"}
            submission[eid] = {
                "category": category,
                "status": decision["status"],
                "review_reason": decision["review_reason"],
                "has_defect": decision["has_defect"],
                "defect_fields": decision["defect_fields"],
            }
        else:
            submission[eid] = {
                "category": category,
                "status": "OK",
                "review_reason": None,
                "has_defect": False,
                "defect_fields": [],
            }

        key = f"{category}/{submission[eid]['status']}"
        status_counts[key] = status_counts.get(key, 0) + 1

    if verbose:
        print("Breakdown:")
        for key in sorted(status_counts):
            print(f"  {key:35} {status_counts[key]}")
        if errors:
            print(f"\n{len(errors)} emails hit an internal error (escalated instead of crashing):")
            for eid, msg in errors[:10]:
                print(f"  {eid}: {msg}")

    return submission


if __name__ == "__main__":
    submission = build_submission(verbose=True)
    out_path = ROOT / "submission.json"
    out_path.write_text(json.dumps(submission, indent=2))
    print(f"\nWrote {out_path} ({len(submission)} emails)")