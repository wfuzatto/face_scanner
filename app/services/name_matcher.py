import re
import unicodedata
from rapidfuzz import fuzz

STOP_WORDS = {"DA", "DAS", "DE", "DO", "DOS", "E"}

def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^A-Za-z ]+", " ", value).upper()
    return re.sub(r"\s+", " ", value).strip()

def significant_tokens(value: str) -> list[str]:
    return [t for t in normalize_name(value).split() if t not in STOP_WORDS and len(t) >= 2]

def _token_similar(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 4:
        return False
    return fuzz.ratio(a, b) >= 84

def match_name(expected: str, extracted: str | None, match_threshold: float = 88, review_threshold: float = 72) -> dict:
    expected_n = normalize_name(expected)
    extracted_n = normalize_name(extracted or "")
    if not extracted_n:
        return {"expected": expected, "extracted": extracted, "score": 0.0, "status": "not_found", "anchors_ok": False}
    score = max(fuzz.token_set_ratio(expected_n, extracted_n), fuzz.token_sort_ratio(expected_n, extracted_n))
    exp_tokens = significant_tokens(expected_n)
    got_tokens = significant_tokens(extracted_n)
    anchors_ok = False
    if exp_tokens and got_tokens:
        first_ok = any(_token_similar(exp_tokens[0], token) for token in got_tokens)
        last_ok = any(_token_similar(exp_tokens[-1], token) for token in got_tokens)
        anchors_ok = first_ok and (last_ok if len(exp_tokens) > 1 else True)
    if score >= match_threshold and anchors_ok:
        status = "match"
    elif score >= review_threshold:
        status = "review"
    else:
        status = "mismatch"
    return {"expected": expected, "extracted": extracted, "score": round(float(score), 2), "status": status, "anchors_ok": anchors_ok}
