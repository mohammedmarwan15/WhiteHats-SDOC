import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract_text import read_attachment
from fields import extract_fields

ROOT = Path(__file__).parent.parent
attach_dir = ROOT / "data" / "attachments"

# grab the first .txt SI/BL pair we find, just to prove it works
si_files = sorted(attach_dir.glob("*_SI.txt"))[:1]
for si_path in si_files:
    bl_path = Path(str(si_path).replace("_SI.txt", "_BL.txt"))
    for p in [si_path, bl_path]:
        result = read_attachment(p)
        fields = extract_fields(result)
        print(f"=== {p.name} ===")
        for field, entry in fields.items():
            print(f"  {field:20s} value={entry['value']!r}")
        print()