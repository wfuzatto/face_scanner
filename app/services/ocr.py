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


BLOCKED_NAME_LINES = {
    "REPUBLICA FEDERATIVA DO BRASIL",
    "CARTEIRA NACIONAL DE HABILITACAO",
    "CARTEIRA DE IDENTIDADE",
    "DOCUMENTO DE IDENTIDADE",
    "VALIDA EM TODO O TERRITORIO NACIONAL",
    "REGISTRO GERAL",
    "NATIONALITY",
    "PASSPORT",
    "PASSAPORTE",
}

NON_NAME_FIELD_PHRASES = {
    "NOME E SOBRENOME",
    "DATA LOCAL E UF DE NASCIMENTO",
    "DATA EMISSAO",
    "VALIDADE",
    "DOC IDENTIDADE",
    "ORG EMISSOR",
    "N REGISTRO",
    "CAT HAB",
    "NACIONALIDADE",
    "FILIACAO",
    "ASSINATURA DO PORTADOR",
    "OBSERVACOES",
}

# Partículas legítimas que podem aparecer isoladas em nomes brasileiros.
SINGLE_LETTER_NAME_PARTICLES = {"A", "D", "E", "O"}


class OCRService:
    def __init__(self, lang: str = "por+eng", tesseract_cmd: str = ""):
        self.lang = lang
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def ready(self) -> bool:
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract(self, image) -> OCRResult:
        """OCR geral conservador: imagem original + CLAHE, ambos em PSM 6.

        A escolha é feita somente pela confiança do Tesseract. O nome esperado da
        reserva nunca participa desta etapa para não enviesar a leitura.
        """
        best = None
        best_score = -1.0
        for candidate in [image, enhance_for_ocr(image)]:
            result = self._extract_once(candidate, psm=6)
            score = sum(max(line.confidence, 0) for line in result.lines)
            if score > best_score:
                best, best_score = result, score
        return best or OCRResult(text="", lines=[])

    def extract_cnh_top(self, image) -> OCRResult:
        """OCR direcionado ao topo da CNH, onde ficam tipo e nome do titular."""
        h, w = image.shape[:2]
        regions = [
            image[int(h * 0.07) : int(h * 0.31), int(w * 0.06) : int(w * 0.95)],
            image[int(h * 0.11) : int(h * 0.22), int(w * 0.12) : int(w * 0.86)],
        ]

        best = None
        best_score = -1.0
        for region in regions:
            if region.size == 0:
                continue
            for candidate in [region, enhance_for_ocr(region)]:
                enlarged = cv2.resize(
                    candidate,
                    None,
                    fx=3.0,
                    fy=3.0,
                    interpolation=cv2.INTER_CUBIC,
                )
                result = self._extract_once(enlarged, psm=6)
                normalized = normalize_name(result.text)
                score = sum(max(line.confidence, 0) for line in result.lines)
                if "HABILITACAO" in normalized or "DRIVER LICENSE" in normalized:
                    score += 250
                if "NOME E SOBRENOME" in normalized:
                    score += 350
                if extract_cnh_name_candidate(result):
                    score += 500
                if score > best_score:
                    best, best_score = result, score

        return best or OCRResult(text="", lines=[])

    def _extract_once(self, image, psm: int = 6) -> OCRResult:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        data = pytesseract.image_to_data(
            rgb,
            lang=self.lang,
            output_type=Output.DICT,
            config=f"--psm {psm}",
        )
        grouped = {}
        order = {}
        for i in range(len(data.get("text", []))):
            token = (data["text"][i] or "").strip()
            if not token:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1.0
            key = (
                int(data["block_num"][i]),
                int(data["par_num"][i]),
                int(data["line_num"][i]),
            )
            grouped.setdefault(key, []).append((token, conf))
            top = int(data.get("top", [0] * len(data["text"]))[i] or 0)
            left = int(data.get("left", [0] * len(data["text"]))[i] or 0)
            order.setdefault(key, (top, left))

        lines = []
        for key in sorted(grouped, key=lambda item: order.get(item, (0, 0))):
            items = grouped[key]
            text = " ".join(token for token, _ in items).strip()
            valid_conf = [conf for _, conf in items if conf >= 0]
            avg_conf = sum(valid_conf) / len(valid_conf) if valid_conf else 0.0
            if text:
                lines.append(OCRLine(text=text, confidence=avg_conf))
        return OCRResult(text="\n".join(line.text for line in lines), lines=lines)

    def extract_passport_mrz(self, image) -> OCRResult:
        h, w = image.shape[:2]
        crop = image[int(h * 0.55) : h, 0:w]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)
        config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
        text = pytesseract.image_to_string(gray, lang="eng", config=config)
        return OCRResult(
            text=text,
            lines=[OCRLine(line.strip(), 0.0) for line in text.splitlines() if line.strip()],
        )


def detect_document_type(text: str, requested: str = "auto") -> str:
    if requested and requested != "auto":
        return requested.lower()
    normalized = normalize_name(text)
    if (
        "PASSPORT" in normalized
        or "PASSAPORTE" in normalized
        or re.search(r"P<[A-Z]{3}", text.upper())
    ):
        return "passport"
    if (
        "CARTEIRA NACIONAL DE HABILITACAO" in normalized
        or "DRIVER LICENSE" in normalized
        or "HABILITACAO" in normalized
        or "PERMISSAO DE CONDUCAO" in normalized
    ):
        return "cnh"
    if (
        "CARTEIRA DE IDENTIDADE NACIONAL" in normalized
        or "DOCUMENTO NACIONAL DE IDENTIDADE" in normalized
    ):
        return "cin"
    if "CARTEIRA DE IDENTIDADE" in normalized or "REGISTRO GERAL" in normalized:
        return "rg"
    return "unknown"


def _looks_like_name(value: str) -> bool:
    normalized = normalize_name(value)
    if not normalized or normalized in BLOCKED_NAME_LINES:
        return False
    if any(blocked in normalized for blocked in BLOCKED_NAME_LINES):
        return False
    if any(phrase in normalized for phrase in NON_NAME_FIELD_PHRASES):
        return False
    tokens = normalized.split()
    if not 2 <= len(tokens) <= 8:
        return False
    if any(
        len(token) == 1 and token not in SINGLE_LETTER_NAME_PARTICLES
        for token in tokens
    ):
        return False
    if re.search(r"\d", value):
        return False
    return sum(ch.isalpha() for ch in value) >= max(6, int(len(value) * 0.6))


def _clean_cnh_name_value(value: str) -> str | None:
    """Isola o valor do nome quando o Tesseract cola campos vizinhos na linha.

    Exemplo real observado:
    ``| NOME SOCIAL TESTE CENTO E DEZ | | 24/05/2022 |``
    vira ``NOME SOCIAL TESTE CENTO E DEZ``.
    """
    candidate = str(value or "").strip(" |:-\t")
    if not candidate:
        return None

    # Recorta campos numéricos que aparecem à direita da caixa do nome.
    candidate = re.split(r"\|\s*\d", candidate, maxsplit=1)[0]
    candidate = re.split(
        r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
        candidate,
        maxsplit=1,
    )[0]
    candidate = re.split(
        r"(?i)\b(?:CPF|DATA|NASCIMENTO|VALIDADE|FILIACAO|DOC(?:UMENTO)?|IDENTIDADE|CATEGORIA|CAT\.?\s*HAB)\b",
        candidate,
        maxsplit=1,
    )[0]
    candidate = candidate.strip(" |:-.,;\t")

    # Alguns OCRs prefixam um caractere isolado antes da borda da caixa, como
    # ``p | NOME ...``. Se NOME aparece logo no início, descartamos esse ruído.
    nome_match = re.search(r"(?i)\bNOME\b", candidate)
    if nome_match and nome_match.start() <= 6:
        prefix = candidate[: nome_match.start()]
        if not any(ch.isalpha() for ch in prefix) or len(prefix.strip(" |:-")) <= 1:
            candidate = candidate[nome_match.start() :]

    candidate = candidate.strip(" |:-.,;\t")
    return candidate if _looks_like_name(candidate) else None


def extract_cnh_name_candidate(ocr: OCRResult) -> str | None:
    """Extrai o nome da faixa superior da CNH sem usar o nome da reserva."""
    lines = [line for line in ocr.lines if line.text.strip()]
    normalized = [normalize_name(line.text) for line in lines]

    # Prioridade: valor logo abaixo do rótulo NOME E SOBRENOME.
    for idx, text in enumerate(normalized):
        if "NOME E SOBRENOME" not in text:
            continue
        for offset in (1, 2, 3):
            pos = idx + offset
            if pos < len(lines):
                cleaned = _clean_cnh_name_value(lines[pos].text)
                if cleaned:
                    return cleaned

    # Fallback para rótulo NOME isolado.
    for idx, text in enumerate(normalized):
        if text == "NOME" or text.endswith(" NOME"):
            for offset in (1, 2):
                pos = idx + offset
                if pos < len(lines):
                    cleaned = _clean_cnh_name_value(lines[pos].text)
                    if cleaned:
                        return cleaned

    # Sem rótulo confiável, escolhe a melhor linha plausível dentro da faixa.
    candidates = []
    for line in lines:
        cleaned = _clean_cnh_name_value(line.text)
        if cleaned:
            token_count = len(normalize_name(cleaned).split())
            candidates.append((line.confidence + min(token_count, 6) * 2.0, cleaned))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def extract_name_candidate(ocr: OCRResult, expected_name: str | None = None) -> str | None:
    lines = [line.text.strip() for line in ocr.lines if line.text.strip()]
    normalized_lines = [normalize_name(line) for line in lines]

    for idx, normalized in enumerate(normalized_lines):
        if "NOME E SOBRENOME" in normalized:
            for offset in (1, 2):
                candidate_idx = idx + offset
                if candidate_idx < len(lines):
                    cleaned = _clean_cnh_name_value(lines[candidate_idx])
                    if cleaned:
                        return cleaned
        if normalized == "NOME" or normalized.endswith(" NOME"):
            if idx + 1 < len(lines):
                cleaned = _clean_cnh_name_value(lines[idx + 1])
                if cleaned:
                    return cleaned

    if expected_name:
        from rapidfuzz import fuzz

        scored = [
            (
                fuzz.token_set_ratio(normalize_name(expected_name), normalize_name(line)),
                line,
            )
            for line in lines
            if _looks_like_name(line)
        ]
        if scored:
            score, line = max(scored, key=lambda item: item[0])
            if score >= 60:
                return line

    candidates = [line for line in lines if _looks_like_name(line)]
    return max(
        candidates,
        key=lambda value: len(normalize_name(value).split()),
        default=None,
    )


def parse_document_fields(
    ocr: OCRResult,
    document_type: str,
    expected_name: str | None = None,
    mrz_ocr: OCRResult | None = None,
) -> dict:
    if document_type == "passport":
        mrz = parse_td3((mrz_ocr or ocr).text)
        if mrz:
            return {
                "name": mrz.name,
                "document_number": mrz.document_number,
                "nationality": mrz.nationality,
                "birth_date": mrz.birth_date,
                "mrz_valid": mrz.valid,
            }
    return {
        "name": extract_name_candidate(ocr, expected_name),
        "document_number": None,
        "nationality": None,
        "birth_date": None,
        "mrz_valid": None,
    }
