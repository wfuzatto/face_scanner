import logging
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.providers.face_verification import DisabledFaceVerificationProvider
from app.schemas import DocumentAnalyzeResponse, FaceVerifyResponse, HealthResponse, ImageQuality, LivenessResult, NameValidation, PortraitInfo
from app.services.document_service import DocumentService
from app.services.face_engine import FaceDetector
from app.services.image_utils import InvalidImage, decode_image, limit_long_edge
from app.services.ocr import OCRService
from app.services.session_store import SessionStore

VERSION = "0.1.0"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("face_scanner")

settings = get_settings()
ocr_service = OCRService(settings.ocr_lang, settings.tesseract_cmd)
face_detector = FaceDetector(settings.face_detector_model, settings.face_detection_threshold)
document_service = DocumentService(ocr_service, face_detector, settings.name_match_threshold, settings.name_review_threshold)
sessions = SessionStore(settings.session_ttl_seconds)
face_verification_provider = DisabledFaceVerificationProvider()

app = FastAPI(title="Face Scanner", version=VERSION, description="Validação documental e preparação de captura facial para Totem Hoteleiro/HUB")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Face-Scanner-Key"])
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def auth(x_face_scanner_key: str | None = Header(default=None), cfg: Settings = Depends(get_settings)) -> None:
    if cfg.api_key and not secrets.compare_digest(x_face_scanner_key or "", cfg.api_key):
        raise HTTPException(status_code=401, detail="API key inválida")


async def read_image(upload: UploadFile | None, cfg: Settings):
    if upload is None:
        return None
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if upload.content_type not in allowed:
        raise HTTPException(status_code=415, detail=f"Formato não suportado: {upload.content_type}")
    data = await upload.read(cfg.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > cfg.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Imagem excede o limite configurado")
    try:
        return limit_long_edge(decode_image(data)), data
    except InvalidImage as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    ready = ocr_service.ready() and face_detector.ready
    return HealthResponse(status="ok" if ready else "degraded", version=VERSION, ocr_ready=ocr_service.ready(), face_engine_ready=face_detector.ready, face_detector_model=settings.face_detector_model.exists(), face_recognizer_model=False, sessions_active=sessions.count())


@app.post("/api/v1/document/analyze", response_model=DocumentAnalyzeResponse, dependencies=[Depends(auth)])
async def analyze_document(expected_name: str = Form(min_length=2, max_length=160), reservation_id: str | None = Form(default=None, max_length=120), document_type: str = Form(default="auto"), front: UploadFile = File(...), back: UploadFile | None = File(default=None), cfg: Settings = Depends(get_settings)):
    request_id = secrets.token_hex(8)
    front_image, _ = await read_image(front, cfg)
    back_image = None
    if back:
        back_image, _ = await read_image(back, cfg)
    analysis = document_service.analyze(front_image, back_image, expected_name, document_type)
    can_prepare_face = bool(analysis.portrait_detection is not None and analysis.name_validation["status"] in {"match", "review"})
    verification_id = sessions.create(reservation_id, analysis.name_validation["status"]).id if can_prepare_face else None
    detection = analysis.portrait_detection
    return DocumentAnalyzeResponse(request_id=request_id, verification_id=verification_id, reservation_id=reservation_id, detected_document_type=analysis.document_type, fields=analysis.fields, name_validation=NameValidation(**analysis.name_validation), portrait=PortraitInfo(found=detection is not None, source=analysis.portrait_source if detection else "none", bbox=detection.bbox if detection else None, detector_score=round(detection.score, 4) if detection else None), can_verify_face=can_prepare_face, warnings=analysis.warnings)


@app.post("/api/v1/face/verify", response_model=FaceVerifyResponse, dependencies=[Depends(auth)])
async def verify_face(verification_id: str = Form(min_length=12, max_length=128), selfie: UploadFile = File(...), cfg: Settings = Depends(get_settings)):
    request_id = secrets.token_hex(8)
    item = sessions.consume(verification_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Sessão inexistente ou expirada")
    image, raw = await read_image(selfie, cfg)
    detections = face_detector.detect(image) if face_detector.ready else []
    if len(detections) != 1:
        issues = ["nenhum_rosto_detectado"] if not detections else ["mais_de_um_rosto_detectado"]
        quality = ImageQuality(blur_score=0, brightness=0, face_ratio=0, acceptable=False, issues=issues)
        return FaceVerifyResponse(request_id=request_id, verification_id=verification_id, status="mismatch", quality=quality, liveness=LivenessResult(), message="A captura deve conter exatamente um rosto.")
    quality = ImageQuality(**face_detector.quality(image, detections[0], cfg.min_face_ratio, cfg.min_blur_score))
    if not quality.acceptable:
        return FaceVerifyResponse(request_id=request_id, verification_id=verification_id, status="review", quality=quality, liveness=LivenessResult(), message="Qualidade insuficiente. Refaça a captura.")
    provider_result = face_verification_provider.verify(verification_id=verification_id, selfie=raw)
    return FaceVerifyResponse(request_id=request_id, verification_id=verification_id, status="not_configured", similarity=None, threshold=None, review_threshold=None, quality=quality, liveness=LivenessResult(), message=provider_result.message)
