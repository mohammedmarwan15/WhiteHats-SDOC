import json
from pathlib import Path

from decide import evaluate_comparison_email
from classify import classify_email

ROOT = Path(__file__).parent.parent
INBOX_DIR = ROOT / "data" / "inbox"

count = 0
for path in sorted(INBOX_DIR.glob("email_*.json")):
    email = json.loads(path.read_text())
    cls = classify_email(email)
    if cls["category"] != "BL_COMPARISON":
        continue

    result = evaluate_comparison_email(email)
    print(f"{email['email_id']:12} {result['status']:13} "
          f"reason={result['review_reason']}  defects={result['defect_fields']}")

    count += 1
    if count >= 15:
        break