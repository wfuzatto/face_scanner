import re
from dataclasses import dataclass

_WEIGHTS = (7, 3, 1)

def _char_value(ch: str) -> int:
    if ch == "<": return 0
    if ch.isdigit(): return int(ch)
    if "A" <= ch <= "Z": return ord(ch) - ord("A") + 10
    return 0

def check_digit(value: str) -> str:
    total = sum(_char_value(ch) * _WEIGHTS[i % 3] for i, ch in enumerate(value))
    return str(total % 10)

def _clean_line(line: str) -> str:
    return re.sub(r"[^A-Z0-9<]", "", line.upper())

def find_td3_lines(text: str) -> tuple[str, str] | None:
    lines = [_clean_line(line) for line in text.splitlines()]
    candidates = [line for line in lines if len(line) >= 40 and "<" in line]
    for i, line in enumerate(candidates):
        if line.startswith("P<") and i + 1 < len(candidates):
            return line[:44].ljust(44, "<"), candidates[i + 1][:44].ljust(44, "<")
    return None

@dataclass
class MRZResult:
    name: str | None
    document_number: str | None
    nationality: str | None
    birth_date: str | None
    valid: bool

def parse_td3(text: str) -> MRZResult | None:
    found = find_td3_lines(text)
    if not found: return None
    line1, line2 = found
    raw_name = line1[5:44]
    parts = raw_name.split("<<", 1)
    surname = parts[0].replace("<", " ").strip()
    given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
    name = " ".join(part for part in [given, surname] if part).strip() or None
    doc_number_raw = line2[0:9]
    doc_number = doc_number_raw.replace("<", "").strip() or None
    nationality = line2[10:13].replace("<", "").strip() or None
    birth_date = line2[13:19] if line2[13:19].isdigit() else None
    checks = []
    if line2[9].isdigit(): checks.append(check_digit(doc_number_raw) == line2[9])
    if line2[19].isdigit(): checks.append(check_digit(line2[13:19]) == line2[19])
    if line2[27].isdigit(): checks.append(check_digit(line2[21:27]) == line2[27])
    return MRZResult(name=name, document_number=doc_number, nationality=nationality, birth_date=birth_date, valid=bool(checks) and all(checks))
