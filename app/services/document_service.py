from dataclasses import dataclass

from app.services.face_engine import FaceDetection, FaceDetector
from app.services.name_matcher import match_name
from app.services.ocr import (
    OCRService,
    detect_document_type,
    extract_cnh_name_candidate,
    parse_document_fields,
)


@dataclass
class DocumentAnalysis:
    document_type: str
    fields: dict
    name_validation: dict
    portrait_detection: FaceDetection | None
    portrait_source: str
    warnings: list[str]


class DocumentService:
    def __init__(
        self,
        ocr: OCRService,
        face: FaceDetector,
        name_match_threshold: float,
        name_review_threshold: float,
    ):
        self.ocr = ocr
        self.face = face
        self.name_match_threshold = name_match_threshold
        self.name_review_threshold = name_review_threshold

    def analyze(
        self,
        front,
        back,
        expected_name: str,
        requested_type: str = "auto",
    ) -> DocumentAnalysis:
        warnings = []

        # OCR geral sem qualquer influência do nome da reserva.
        front_ocr = self.ocr.extract(front)
        back_ocr = self.ocr.extract(back) if back is not None else None

        # Para CNH/auto, lê também apenas a faixa superior. Essa leitura é usada
        # tanto para reconhecer o tipo quanto para extrair o nome do titular com
        # menos interferência do restante do documento.
        cnh_top_ocr = None
        if requested_type in {"auto", "cnh"}:
            cnh_top_ocr = self.ocr.extract_cnh_top(front)

        merged_text = front_ocr.text
        if cnh_top_ocr is not None:
            merged_text += "\n" + cnh_top_ocr.text
        if back_ocr is not None:
            merged_text += "\n" + back_ocr.text

        document_type = detect_document_type(merged_text, requested_type)

        mrz_ocr = (
            self.ocr.extract_passport_mrz(front)
            if document_type == "passport"
            else None
        )
        fields = parse_document_fields(
            front_ocr,
            document_type,
            expected_name,
            mrz_ocr=mrz_ocr,
        )

        # CNH: o nome lido na faixa superior tem prioridade sobre o OCR geral.
        if document_type == "cnh":
            if cnh_top_ocr is None:
                cnh_top_ocr = self.ocr.extract_cnh_top(front)
            cnh_name = extract_cnh_name_candidate(cnh_top_ocr)
            if cnh_name:
                fields["name"] = cnh_name
            else:
                warnings.append("cnh_name_region_not_found")

        if not fields.get("name") and back_ocr is not None:
            back_fields = parse_document_fields(
                back_ocr,
                document_type,
                expected_name,
            )
            if back_fields.get("name"):
                fields["name"] = back_fields["name"]

        name_validation = match_name(
            expected_name,
            fields.get("name"),
            self.name_match_threshold,
            self.name_review_threshold,
        )

        portrait_detection = None
        portrait_source = "none"
        if self.face.ready:
            front_faces = self.face.detect(front)
            if front_faces:
                portrait_detection, portrait_source = front_faces[0], "front"
            elif back is not None:
                back_faces = self.face.detect(back)
                if back_faces:
                    portrait_detection, portrait_source = back_faces[0], "back"
        else:
            warnings.append("face_detector_not_configured")

        if not fields.get("name"):
            warnings.append("document_name_not_found")
        if portrait_detection is None:
            warnings.append("document_portrait_not_found")
        if document_type == "unknown":
            warnings.append("document_type_not_detected")
        if document_type == "passport" and fields.get("mrz_valid") is False:
            warnings.append("passport_mrz_check_digit_failed")

        return DocumentAnalysis(
            document_type,
            fields,
            name_validation,
            portrait_detection,
            portrait_source,
            warnings,
        )
