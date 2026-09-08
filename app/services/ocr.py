import re
from dataclasses import dataclass
import cv2
import pytesseract
from pytesseract import Output
from app.services.image_utils import enhance_for_ocr
from app.services.name_matcher import normalize_name
from app.services.mrz import parse_td3

@dataclass
class OCRLine:
    text: str
    confidence: float

@dataclass
class OCRResult:
    text: str
    lines: list[OCRLine]
    provider: str = "tesseract"

BLOCKED_NAME_LINES = {"REPUBLICA FEDERATIVA DO BRASIL","CARTEIRA NACIONAL DE HABILITACAO","CARTEIRA DE IDENTIDADE","DOCUMENTO DE IDENTIDADE","VALIDA EM TODO O TERRITORIO NACIONAL","REGISTRO GERAL","NATIONALITY","PASSPORT","PASSAPORTE"}

class OCRService:
    def __init__(self, lang: str = "por+eng", tesseract_cmd: str = ""):
        self.lang = lang
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    def ready(self) -> bool:
        try:
            pytesseract.get_tesseract_version(); return True
        except Exception:
            return False
    def extract(self, image) -> OCRResult:
        best = None; best_score = -1.0
        for candidate in [image, enhance_for_ocr(image)]:
            result = self._extract_once(candidate)
            score = sum(max(line.confidence, 0) for line in result.lines)
            if score > best_score: best, best_score = result, score
        return best
    def _extract_once(self, image) -> OCRResult:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        data = pytesseract.image_to_data(rgb, lang=self.lang, output_type=Output.DICT, config="--psm 6")
        grouped = {}
        for i in range(len(data.get("text", []))):
            token = (data["text"][i] or "").strip()
            if not token: continue
            try: conf = float(data["conf"][i])
            except (TypeError, ValueError): conf = -1.0
            key = (int(data["block_num"][i]), int(data["par_num"][i]), int(data["line_num"][i]))
            grouped.setdefault(key, []).append((token, conf))
        lines = []
        for items in grouped.values():
            text = " ".join(token for token, _ in items).strip()
            valid_conf = [conf for _, conf in items if conf >= 0]
            avg_conf = sum(valid_conf) / len(valid_conf) if valid_conf else 0.0
            if text: lines.append(OCRLine(text=text, confidence=avg_conf))
        return OCRResult(text="\n".join(line.text for line in lines), lines=lines)
    def extract_passport_mrz(self, image) -> OCRResult:
        h, w = image.shape[:2]
        crop = image[int(h * 0.55):h, 0:w]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
        config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
        text = pytesseract.image_to_string(gray, lang="eng", config=config)
        return OCRResult(text=text, lines=[OCRLine(line.strip(), 0.0) for line in text.splitlines() if line.strip()])

def detect_document_type(text: str, requested: str = "auto") -> str:
    if requested and requested != "auto": return requested.lower()
    normalized = normalize_name(text)
    if "PASSPORT" in normalized or "PASSAPORTE" in normalized or re.search(r"P<[A-Z]{3}", text.upper()): return "passport"
    if "CARTEIRA NACIONAL DE HABILITACAO" in normalized or "DRIVER LICENSE" in normalized or "HABILITACAO" in normalized: return "cnh"
    if "CARTEIRA DE IDENTIDADE NACIONAL" in normalized or "DOCUMENTO NACIONAL DE IDENTIDADE" in normalized: return "cin"
    if "CARTEIRA DE IDENTIDADE" in normalized or "REGISTRO GERAL" in normalized: return "rg"
    return "unknown"

def _looks_like_name(value: str) -> bool:
    normalized = normalize_name(value)
    if not normalized or normalized in BLOCKED_NAME_LINES: return False
    if any(blocked in normalized for blocked in BLOCKED_NAME_LINES): return False
    tokens = normalized.split()
    if not 2 <= len(tokens) <= 8: return False
    if any(len(token) == 1 for token in tokens): return False
    if re.search(r"\d", value): return False
    return sum(ch.isalpha() for ch in value) >= max(6, int(len(value) * 0.6))

def extract_name_candidate(ocr: OCRResult, expected_name: str | None = None) -> str | None:
    lines = [line.text.strip() for line in ocr.lines if line.text.strip()]
    normalized_lines = [normalize_name(line) for line in lines]
    for idx, normalized in enumerate(normalized_lines):
        if normalized == "NOME" or normalized.endswith(" NOME") or normalized.startswith("NOME "):
            raw = lines[idx]
            same_line = re.sub(r"(?i)^.*?\bNOME\b\s*[:\-]?\s*", "", raw).strip()
            if len(normalize_name(same_line).split()) >= 2: return same_line
            if idx + 1 < len(lines) and _looks_like_name(lines[idx + 1]): return lines[idx + 1]
    if expected_name:
        from rapidfuzz import fuzz
        scored = [(fuzz.token_set_ratio(normalize_name(expected_name), normalize_name(line)), line) for line in lines if _looks_like_name(line)]
        if scored:
            score, line = max(scored, key=lambda item: item[0])
            if score >= 60: return line
    candidates = [line for line in lines if _looks_like_name(line)]
    return max(candidates, key=lambda value: len(normalize_name(value).split()), default=None)

def parse_document_fields(ocr: OCRResult, document_type: str, expected_name: str | None = None, mrz_ocr: OCRResult | None = None) -> dict:
    if document_type == "passport":
        mrz = parse_td3((mrz_ocr or ocr).text)
        if mrz:
            return {"name": mrz.name, "document_number": mrz.document_number, "nationality": mrz.nationality, "birth_date": mrz.birth_date, "mrz_valid": mrz.valid}
    return {"name": extract_name_candidate(ocr, expected_name), "document_number": None, "nationality": None, "birth_date": None, "mrz_valid": None}
