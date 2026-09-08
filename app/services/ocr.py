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

FIELD_WORDS = {
    "NOME",
    "SOCIAL",
    "CPF",
    "FILIACAO",
    "NASCIMENTO",
    "NASC",
    "VALIDADE",
    "EMISSAO",
    "EXPEDICAO",
    "IDENTIDADE",
    "REGISTRO",
    "HABILITACAO",
    "CATEGORIA",
    "ASSINATURA",
    "PORTADOR",
    "LOCAL",
    "DATA",
    "DOC",
    "DOCUMENTO",
    "OBSERVACOES",
    "OBSERVACAO",
    "PERMISSAO",
}

NAME_LABEL_RE = re.compile(
    r"(?i)\b(?:NOME\s+E\s+SOBRENOME|NOME\s+COMPLETO|NOME)\b\s*[:\-]?\s*"
)


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

    def extract(self, image, expected_name: str | None = None) -> OCRResult:
        """Executa mais de uma segmentação e escolhe a leitura mais útil.

        CNH/CIN/RG têm muitos campos pequenos e layouts diferentes. PSM 6 funciona
        bem em blocos; PSM 11 costuma recuperar melhor textos esparsos. Quando o
        nome esperado da reserva existe, ele é usado apenas para escolher a melhor
        leitura OCR, nunca para fabricar um nome que não tenha sido reconhecido.
        """
        candidates: list[OCRResult] = []
        for image_candidate in [image, enhance_for_ocr(image)]:
            for psm in (6, 11):
                candidates.append(self._extract_once(image_candidate, psm=psm))

        def score(result: OCRResult) -> float:
            base = sum(max(line.confidence, 0) for line in result.lines)
            if expected_name:
                similarity = _best_expected_similarity(result, expected_name)
                # O nome da reserva ajuda a selecionar entre leituras reais do
                # Tesseract, mas não cria conteúdo inexistente.
                base += similarity * 12.0
            return base

        return max(candidates, key=score, default=OCRResult(text="", lines=[]))

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
    tokens = normalized.split()
    if not 2 <= len(tokens) <= 8:
        return False
    if any(len(token) == 1 for token in tokens):
        return False
    if re.search(r"\d", value):
        return False
    if sum(token in FIELD_WORDS for token in tokens) >= 2:
        return False
    return sum(ch.isalpha() for ch in value) >= max(6, int(len(value) * 0.6))


def _candidate_fragments(line: str, expected_name: str | None = None) -> list[str]:
    """Gera trechos plausíveis sem aceitar datas/campos vizinhos como nome."""
    fragments: list[str] = []
    stripped = line.strip()
    if _looks_like_name(stripped):
        fragments.append(stripped)

    # Texto depois do rótulo NOME, apenas se continuar parecendo um nome.
    match = NAME_LABEL_RE.search(stripped)
    if match:
        after = stripped[match.end() :].strip(" :-")
        # Corta quando outro campo conhecido começa na mesma linha.
        after = re.split(
            r"(?i)\b(?:CPF|DATA|NASCIMENTO|VALIDADE|FILIACAO|DOC(?:UMENTO)?|IDENTIDADE|CATEGORIA|CAT\.?\s*HAB)\b",
            after,
            maxsplit=1,
        )[0].strip(" :-")
        if _looks_like_name(after):
            fragments.append(after)

    # Em OCR de documento é comum rótulo e vários campos caírem na mesma linha.
    # Avalia janelas contíguas de palavras, mas somente trechos que isoladamente
    # têm formato de nome. Isso evita o bug "NOME SOCIAL ... 24/05/2022".
    if expected_name:
        tokens = re.findall(r"[A-Za-zÀ-ÿ]+", stripped)
        wanted = max(2, len(normalize_name(expected_name).split()))
        min_size = max(2, wanted - 1)
        max_size = min(7, wanted + 2)
        for size in range(min_size, max_size + 1):
            for start in range(0, max(0, len(tokens) - size + 1)):
                fragment = " ".join(tokens[start : start + size])
                if _looks_like_name(fragment):
                    fragments.append(fragment)

    # Preserva ordem removendo duplicatas normalizadas.
    unique: list[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        key = normalize_name(fragment)
        if key and key not in seen:
            seen.add(key)
            unique.append(fragment)
    return unique


def _best_expected_similarity(ocr: OCRResult, expected_name: str) -> float:
    from rapidfuzz import fuzz

    expected = normalize_name(expected_name)
    best = 0.0
    for line in ocr.lines:
        for fragment in _candidate_fragments(line.text, expected_name):
            candidate = normalize_name(fragment)
            best = max(
                best,
                float(fuzz.token_set_ratio(expected, candidate)),
                float(fuzz.token_sort_ratio(expected, candidate)),
            )
    return best


def extract_name_candidate(
    ocr: OCRResult, expected_name: str | None = None
) -> str | None:
    lines = [line.text.strip() for line in ocr.lines if line.text.strip()]

    # Se sabemos o nome da reserva, priorizamos um trecho efetivamente lido pelo
    # OCR que seja compatível. Não retornamos simplesmente o rótulo NOME + lixo.
    if expected_name:
        from rapidfuzz import fuzz

        expected = normalize_name(expected_name)
        scored: list[tuple[float, str]] = []
        for line in lines:
            for fragment in _candidate_fragments(line, expected_name):
                normalized = normalize_name(fragment)
                score = max(
                    fuzz.token_set_ratio(expected, normalized),
                    fuzz.token_sort_ratio(expected, normalized),
                )
                scored.append((float(score), fragment))
        if scored:
            best_score, best_fragment = max(scored, key=lambda item: item[0])
            if best_score >= 60:
                return best_fragment

    normalized_lines = [normalize_name(line) for line in lines]
    for idx, normalized in enumerate(normalized_lines):
        if "NOME" not in normalized:
            continue

        raw = lines[idx]
        match = NAME_LABEL_RE.search(raw)
        if match:
            same_line = raw[match.end() :].strip(" :-")
            same_line = re.split(
                r"(?i)\b(?:CPF|DATA|NASCIMENTO|VALIDADE|FILIACAO|DOC(?:UMENTO)?|IDENTIDADE|CATEGORIA|CAT\.?\s*HAB)\b",
                same_line,
                maxsplit=1,
            )[0].strip(" :-")
            # Correção do bug: antes qualquer texto com >=2 tokens era aceito.
            if _looks_like_name(same_line):
                return same_line

        # Procura algumas linhas seguintes porque PSM 11 pode separar o rótulo
        # do valor e inserir uma linha curta intermediária.
        for offset in (1, 2):
            candidate_idx = idx + offset
            if candidate_idx < len(lines) and _looks_like_name(lines[candidate_idx]):
                return lines[candidate_idx]

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
