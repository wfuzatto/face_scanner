from typing import Literal
from pydantic import BaseModel, Field

NameStatus = Literal["match", "review", "mismatch", "not_found"]
FaceStatus = Literal["match", "review", "mismatch", "not_configured"]


class NameValidation(BaseModel):
    expected: str
    extracted: str | None = None
    score: float = Field(ge=0, le=100)
    status: NameStatus
    anchors_ok: bool = False


class PortraitInfo(BaseModel):
    found: bool
    source: Literal["front", "back", "none"] = "none"
    bbox: list[int] | None = None
    detector_score: float | None = None


class DocumentFields(BaseModel):
    name: str | None = None
    document_number: str | None = None
    nationality: str | None = None
    birth_date: str | None = None
    mrz_valid: bool | None = None


class DocumentAnalyzeResponse(BaseModel):
    request_id: str
    verification_id: str | None = None
    reservation_id: str | None = None
    detected_document_type: str
    fields: DocumentFields
    name_validation: NameValidation
    portrait: PortraitInfo
    can_verify_face: bool
    warnings: list[str] = []


class ImageQuality(BaseModel):
    blur_score: float
    brightness: float
    face_ratio: float
    acceptable: bool
    issues: list[str] = []


class FacePreviewResponse(BaseModel):
    """Pré-checagem de captura; não identifica a pessoa e não consome sessão."""

    request_id: str
    face_count: int = Field(ge=0)
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    bbox: list[int] | None = None
    detector_score: float | None = None
    quality: ImageQuality
    message: str


class LivenessResult(BaseModel):
    status: Literal["not_checked", "passed", "failed"] = "not_checked"
    method: str = "none"
    note: str = "Esta versão não executa PAD/liveness anti-spoofing certificado."


class FaceVerifyResponse(BaseModel):
    request_id: str
    verification_id: str
    status: FaceStatus
    identity_verified: bool = False
    provider: str = "not_run"
    similarity: float | None = None
    threshold: float | None = None
    review_threshold: float | None = None
    quality: ImageQuality
    liveness: LivenessResult = LivenessResult()
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    ocr_ready: bool
    face_engine_ready: bool
    face_detector_model: bool
    face_recognizer_model: bool
    sessions_active: int
