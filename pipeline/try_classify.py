import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classify import classify_email

ROOT = Path(__file__).parent.parent
inbox_dir = ROOT / "data" / "inbox"

files = sorted(inbox_dir.glob("email_*.json"))[:10]
for path in files:
    email = json.loads(path.read_text())
    result = classify_email(email)
    print(f"{email['email_id']}: {result['category']:15s}  subject={email['subject']!r}")