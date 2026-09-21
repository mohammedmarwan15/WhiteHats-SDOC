import json
from pathlib import Path

from extract_text import read_attachment
from fields import extract_fields
from compare import compare_fields

ATTACH_DIR = Path(__file__).parent.parent / "data" / "attachments"

si_file = ATTACH_DIR / "email_001_SI.txt"
bl_file = ATTACH_DIR / "email_001_BL.txt"

si_fields = extract_fields(read_attachment(si_file))
bl_fields = extract_fields(read_attachment(bl_file))

result = compare_fields(si_fields, bl_fields)

for field, r in result.items():
    status = "MATCH" if r["match"] else "MISMATCH"
    print(f"{field:20} {status:9} si={r['si_value']!r}  bl={r['bl_value']!r}")