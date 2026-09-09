import logging
import secrets
from pathlib import Path

import cv2
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.biometric.decision_policy import ThreeWayDecisionPolicy
from app.biometric.embedding_engine import SFaceEmbeddingEngine
from app.biometric.pipeline import BiometricPipeline
from app.biometric.similarity_engine import CosineSimilarityEngine
from app.providers.face_verification import (
    DisabledFaceVerificationProvider,
    InternalFaceVerificationProvider,
    MockFaceVerificationProvider,
    NotConfiguredFaceVerificationProvider,
)
from app.providers.liveness import DisabledLivenessProvider
from app.schemas import (
    CheckinGateInfo,
    DocumentAnalyzeResponse,
    FaceAlignmentInfo,
    FacePreviewResponse,
    FaceVerifyResponse,
    HealthResponse,
    ImageQuality,
    LivenessResult,
    NameValidation,
    PortraitInfo,
)
from app.services.document_service import DocumentService
from app.services.face_alignment import FaceAlignmentService
from app.services.face_engine import FaceDetector
from app.services.image_utils import InvalidImage, decode_image, limit_long_edge
from app.services.ocr import OCRService
from app.services.session_store import SessionStore
from app.services.temporary_face_store import TemporaryFaceStore
from app.services.verification_gate import evaluate_checkin_gate

VERSION = "0.5.0"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("face_scanner")

settings = get_settings()
ocr_service = OCRService(settings.ocr_lang, settings.tesseract_cmd)
face_detector = FaceDetector(settings.face_detector_model, settings.face_detection_threshold)
face_alignment = FaceAlignmentService()
document_service = DocumentService(
    ocr_service,
    face_detector,
    settings.name_match_threshold,
    settings.name_review_threshold,
)
sessions = SessionStore(settings.session_ttl_seconds, settings.session_db_path)
document_faces = TemporaryFaceStore(settings.session_ttl_seconds)

provider_mode = settings.face_provider_mode
provider_config_error: str | None = None
embedding_model_ready = False
thresholds_configured = False
if provider_mode == "internal":
    try:
        embedding_engine = SFaceEmbeddingEngine(
            settings.face_embedding_model_path,
            settings.face_embedding_model_version,
            settings.face_embedding_model_name,
        )
        policy = ThreeWayDecisionPolicy(settings.face_review_threshold, settings.face_match_threshold)
        face_verification_provider = InternalFaceVerificationProvider(
            BiometricPipeline(embedding_engine, CosineSimilarityEngine(), policy)
        )
        embedding_model_ready = embedding_engine.ready
        thresholds_configured = policy.calibrated
        if not policy.calibrated:
            logger.warning(
                "provider internal em homologação técnica score-only: "
                "thresholds não configurados; similaridade real será calculada, "
                "mas identity_verified permanecerá false"
            )
    except (FileNotFoundError, RuntimeError, ValueError, cv2.error) as exc:
        provider_config_error = f"provider internal indisponível: {type(exc).__name__}: {exc}"
        face_verification_provider = NotConfiguredFaceVerificationProvider(
            "internal", "Provider interno não pôde ser inicializado."
        )
        logger.error(provider_config_error)
elif provider_mode == "mock":
    if settings.app_env.strip().lower() not in {"development", "homologation", "test"}:
        provider_config_error = "provider mock é permitido somente em development/homologation/test"
        face_verification_provider = DisabledFaceVerificationProvider()
        logger.error(provider_config_error)
    else:
        try:
            face_verification_provider = MockFaceVerificationProvider(settings.face_mock_status)
            logger.warning(
                "FACE VERIFICATION EM MODO MOCK DE HOMOLOGAÇÃO: status=%s; nenhuma identidade é comparada",
                settings.face_mock_status,
            )
        except ValueError as exc:
            provider_config_error = str(exc)
            face_verification_provider = DisabledFaceVerificationProvider()
            logger.error("Configuração de provider inválida: %s", exc)
elif provider_mode == "disabled":
    face_verification_provider = DisabledFaceVerificationProvider()
else:
    provider_config_error = f"FACE_VERIFICATION_PROVIDER não suportado: {provider_mode}"
    face_verification_provider = NotConfiguredFaceVerificationProvider(
        provider_mode or "unknown", "Provider biométrico inválido na configuração."
    )
    logger.error(provider_config_error)

liveness_provider = DisabledLivenessProvider()

app = FastAPI(
    title="Face Scanner",
    version=VERSION,
    description="Validação documental e preparação de captura facial para Totem Hoteleiro/HUB",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Face-Scanner-Key"],
)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def auth(
    x_face_scanner_key: str | None = Header(default=None),
    cfg: Settings = Depends(get_settings),
) -> None:
    if cfg.api_key and not secrets.compare_digest(x_face_scanner_key or "", cfg.api_key):
        raise HTTPException(status_code=401, detail="API key inválida")


def dashboard_access(cfg: Settings = Depends(get_settings)) -> None:
    if not cfg.dashboard_unauthenticated:
        raise HTTPException(
            status_code=403,
            detail="Dashboard standalone desabilitado neste ambiente",
        )


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


def alignment_info(image, detection) -> FaceAlignmentInfo:
    if image is None or detection is None:
        return FaceAlignmentInfo()
    try:
        result = face_alignment.align(image, detection)
    except Exception as exc:
        logger.warning("preview face alignment unavailable: %s", exc)
        return FaceAlignmentInfo(success=False, message="Preview de alinhamento indisponível.")
    return FaceAlignmentInfo(
        success=result.success,
        width=result.width,
        height=result.height,
        jpeg_base64=result.jpeg_base64,
        transform=result.transform,
        message=result.message,
    )


def liveness_info(verification_id: str, raw: bytes) -> LivenessResult:
    result = liveness_provider.check(verification_id=verification_id, capture=raw)
    status = result.status if result.status in {"not_checked", "passed", "failed"} else "not_checked"
    return LivenessResult(status=status, method=result.method, note=result.message)


def gate_info(document_name_status: str, identity_verified: bool, liveness: LivenessResult) -> CheckinGateInfo:
    gate = evaluate_checkin_gate(
        document_name_status=document_name_status,
        identity_verified=identity_verified,
        liveness_status=liveness.status,
    )
    return CheckinGateInfo(allowed=gate.allowed, reasons=gate.reasons)


def attempt_fields(session, cfg: Settings) -> tuple[int, int, int]:
    max_attempts = max(1, int(cfg.face_max_attempts))
    used = max(0, int(getattr(session, "attempts", 0)))
    return used, max_attempts, max(0, max_attempts - used)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/api/v1/health", response_model=HealthResponse)
def health():
    core_ready = ocr_service.ready() and face_detector.ready
    provider_configured = (
        (provider_mode == "mock" and provider_config_error is None)
        or isinstance(face_verification_provider, InternalFaceVerificationProvider)
    )
    provider_ready = provider_mode in {"disabled", "mock"} or provider_configured
    return HealthResponse(
        status="ok" if core_ready and provider_ready and provider_config_error is None else "degraded",
        version=VERSION,
        ocr_ready=ocr_service.ready(),
        face_engine_ready=face_detector.ready,
        face_detector_model=settings.face_detector_model.exists(),
        face_recognizer_model=embedding_model_ready,
        embedding_model_ready=embedding_model_ready,
        provider_configured=provider_configured,
        thresholds_configured=thresholds_configured,
        sessions_active=sessions.count(),
    )


async def _analyze_document_impl(
    expected_name: str,
    reservation_id: str | None,
    document_type: str,
    front: UploadFile,
    back: UploadFile | None,
    cfg: Settings,
) -> DocumentAnalyzeResponse:
    request_id = secrets.token_hex(8)
    front_image, _ = await read_image(front, cfg)
    back_image = None
    if back:
        back_image, _ = await read_image(back, cfg)

    analysis = document_service.analyze(front_image, back_image, expected_name, document_type)
    can_prepare_face = bool(
        analysis.portrait_detection is not None
        and analysis.name_validation["status"] in {"match", "review"}
    )
    verification_id = (
        sessions.create(reservation_id, analysis.name_validation["status"]).id
        if can_prepare_face
        else None
    )
    detection = analysis.portrait_detection

    portrait_image = None
    if detection is not None:
        if analysis.portrait_source == "front":
            portrait_image = front_image
        elif analysis.portrait_source == "back":
            portrait_image = back_image
    # Provider preparation is independent from the optional 224x224 preview.
    if (
        verification_id
        and portrait_image is not None
        and detection is not None
        and getattr(face_verification_provider, "requires_aligned_faces", False)
    ):
        try:
            document_faces.put(
                verification_id,
                face_verification_provider.prepare_face(portrait_image, detection),
            )
        except (ValueError, RuntimeError, cv2.error) as exc:
            logger.warning("internal document preparation failed error_type=%s", type(exc).__name__)
    portrait_height = int(portrait_image.shape[0]) if portrait_image is not None else None
    portrait_width = int(portrait_image.shape[1]) if portrait_image is not None else None

    return DocumentAnalyzeResponse(
        request_id=request_id,
        verification_id=verification_id,
        reservation_id=reservation_id,
        detected_document_type=analysis.document_type,
        fields=analysis.fields,
        name_validation=NameValidation(**analysis.name_validation),
        portrait=PortraitInfo(
            found=detection is not None,
            source=analysis.portrait_source if detection else "none",
            bbox=detection.bbox if detection else None,
            detector_score=round(detection.score, 4) if detection else None,
            image_width=portrait_width,
            image_height=portrait_height,
            landmarks=detection.landmarks if detection else None,
            alignment=alignment_info(portrait_image, detection),
        ),
        can_verify_face=can_prepare_face,
        warnings=analysis.warnings,
    )


@app.post(
    "/api/v1/document/analyze",
    response_model=DocumentAnalyzeResponse,
    dependencies=[Depends(auth)],
)
async def analyze_document(
    expected_name: str = Form(min_length=2, max_length=160),
    reservation_id: str | None = Form(default=None, max_length=120),
    document_type: str = Form(default="auto"),
    front: UploadFile = File(...),
    back: UploadFile | None = File(default=None),
    cfg: Settings = Depends(get_settings),
):
    return await _analyze_document_impl(expected_name, reservation_id, document_type, front, back, cfg)


@app.post(
    "/dashboard-api/document/analyze",
    response_model=DocumentAnalyzeResponse,
    dependencies=[Depends(dashboard_access)],
    include_in_schema=False,
)
async def dashboard_analyze_document(
    expected_name: str = Form(min_length=2, max_length=160),
    reservation_id: str | None = Form(default=None, max_length=120),
    document_type: str = Form(default="auto"),
    front: UploadFile = File(...),
    back: UploadFile | None = File(default=None),
    cfg: Settings = Depends(get_settings),
):
    return await _analyze_document_impl(expected_name, reservation_id, document_type, front, back, cfg)


async def _preview_face_impl(selfie: UploadFile, cfg: Settings) -> FacePreviewResponse:
    request_id = secrets.token_hex(8)
    image, _ = await read_image(selfie, cfg)
    h, w = image.shape[:2]
    if not face_detector.ready:
        raise HTTPException(status_code=503, detail="Detector facial não configurado")

    detections = face_detector.detect(image)
    if len(detections) != 1:
        issue = "nenhum_rosto_detectado" if not detections else "mais_de_um_rosto_detectado"
        return FacePreviewResponse(
            request_id=request_id,
            face_count=len(detections),
            image_width=w,
            image_height=h,
            bbox=None,
            detector_score=None,
            landmarks=None,
            quality=ImageQuality(
                blur_score=0,
                brightness=0,
                face_ratio=0,
                acceptable=False,
                issues=[issue],
            ),
            message=(
                "Posicione um rosto dentro da área indicada."
                if not detections
                else "A captura deve conter somente uma pessoa."
            ),
        )

    detection = detections[0]
    quality = ImageQuality(
        **face_detector.quality(image, detection, cfg.min_face_ratio, cfg.min_blur_score)
    )
    return FacePreviewResponse(
        request_id=request_id,
        face_count=1,
        image_width=w,
        image_height=h,
        bbox=detection.bbox,
        detector_score=round(detection.score, 4),
        landmarks=detection.landmarks,
        quality=quality,
        message="Captura pronta." if quality.acceptable else "Ajuste a captura antes de continuar.",
    )


@app.post("/api/v1/face/preview", response_model=FacePreviewResponse, dependencies=[Depends(auth)])
async def preview_face(selfie: UploadFile = File(...), cfg: Settings = Depends(get_settings)):
    return await _preview_face_impl(selfie, cfg)


async def _verify_face_impl(verification_id: str, selfie: UploadFile, cfg: Settings) -> FaceVerifyResponse:
    request_id = secrets.token_hex(8)
    current_session = sessions.get(verification_id)
    if current_session is None:
        raise HTTPException(status_code=404, detail="Sessão inexistente ou expirada")

    attempts_used, max_attempts, attempts_remaining = attempt_fields(current_session, cfg)

    image, raw = await read_image(selfie, cfg)
    h, w = image.shape[:2]
    detections = face_detector.detect(image) if face_detector.ready else []
    if len(detections) != 1:
        issues = ["nenhum_rosto_detectado"] if not detections else ["mais_de_um_rosto_detectado"]
        return FaceVerifyResponse(
            request_id=request_id,
            verification_id=verification_id,
            status="review",
            identity_verified=False,
            retry_allowed=True,
            attempts_used=attempts_used,
            max_attempts=max_attempts,
            attempts_remaining=attempts_remaining,
            provider="not_run",
            bbox=None,
            image_width=w,
            image_height=h,
            landmarks=None,
            quality=ImageQuality(
                blur_score=0,
                brightness=0,
                face_ratio=0,
                acceptable=False,
                issues=issues,
            ),
            liveness=LivenessResult(),
            checkin_gate=gate_info(current_session.name_status, False, LivenessResult()),
            message="A captura deve conter exatamente um rosto. Refaça a foto.",
        )

    detection = detections[0]
    aligned = alignment_info(image, detection)
    quality = ImageQuality(
        **face_detector.quality(image, detection, cfg.min_face_ratio, cfg.min_blur_score)
    )
    if not quality.acceptable:
        return FaceVerifyResponse(
            request_id=request_id,
            verification_id=verification_id,
            status="review",
            identity_verified=False,
            retry_allowed=True,
            attempts_used=attempts_used,
            max_attempts=max_attempts,
            attempts_remaining=attempts_remaining,
            provider="not_run",
            bbox=detection.bbox,
            image_width=w,
            image_height=h,
            landmarks=detection.landmarks,
            alignment=aligned,
            quality=quality,
            liveness=LivenessResult(),
            checkin_gate=gate_info(current_session.name_status, False, LivenessResult()),
            message="Qualidade insuficiente. Refaça a captura.",
        )

    live_result = liveness_info(verification_id, raw)
    provider_requires_faces = getattr(face_verification_provider, "requires_aligned_faces", False)
    document_face = document_faces.get(verification_id) if provider_requires_faces else None
    live_face = None

    if provider_requires_faces and document_face is None:
        sessions.consume(verification_id)
        document_faces.consume(verification_id)
        return FaceVerifyResponse(
            request_id=request_id,
            verification_id=verification_id,
            status="not_configured",
            identity_verified=False,
            retry_allowed=False,
            attempts_used=attempts_used,
            max_attempts=max_attempts,
            attempts_remaining=attempts_remaining,
            provider=getattr(face_verification_provider, "provider", provider_mode),
            bbox=detection.bbox,
            image_width=w,
            image_height=h,
            landmarks=detection.landmarks,
            alignment=aligned,
            quality=quality,
            liveness=live_result,
            checkin_gate=gate_info(current_session.name_status, False, live_result),
            message="Face documental temporária indisponível ou expirada.",
        )

    if provider_requires_faces:
        try:
            live_face = face_verification_provider.prepare_face(image, detection)
        except (ValueError, RuntimeError, cv2.error) as exc:
            logger.warning("internal live preparation failed error_type=%s", type(exc).__name__)
            sessions.consume(verification_id)
            document_faces.consume(verification_id)
            return FaceVerifyResponse(
                request_id=request_id,
                verification_id=verification_id,
                status="not_configured",
                identity_verified=False,
                retry_allowed=False,
                attempts_used=attempts_used,
                max_attempts=max_attempts,
                attempts_remaining=attempts_remaining,
                provider=getattr(face_verification_provider, "provider", provider_mode),
                bbox=detection.bbox,
                image_width=w,
                image_height=h,
                landmarks=detection.landmarks,
                alignment=aligned,
                quality=quality,
                liveness=live_result,
                checkin_gate=gate_info(current_session.name_status, False, live_result),
                message="Não foi possível preparar a face para o modelo biométrico.",
            )

    provider_result = face_verification_provider.verify(
        verification_id=verification_id,
        selfie=raw,
        document_face=document_face,
        live_face=live_face,
    )

    allowed_statuses = {"match", "review", "mismatch", "not_configured"}
    provider_status = provider_result.status if provider_result.status in allowed_statuses else "review"
    identity_verified = bool(provider_result.identity_verified and provider_status == "match")
    if provider_status == "match" and not identity_verified:
        provider_status = "review"

    message = provider_result.message
    retry_allowed = False
    session_for_gate = current_session

    if provider_status == "not_configured":
        sessions.consume(verification_id)
        document_faces.consume(verification_id)
        message = (
            "Captura com qualidade aprovada, mas a identidade NÃO foi verificada: "
            "provider biométrico não configurado."
        )
    else:
        recorded_session, exhausted = sessions.record_attempt(verification_id, max_attempts)
        if recorded_session is None:
            raise HTTPException(status_code=409, detail="Sessão já utilizada ou expirada")

        session_for_gate = recorded_session
        attempts_used = recorded_session.attempts
        attempts_remaining = max(0, max_attempts - attempts_used)

        if identity_verified:
            if not exhausted:
                sessions.consume(verification_id)
            document_faces.consume(verification_id)
        elif provider_status in {"review", "mismatch"}:
            retry_allowed = not exhausted
            if exhausted:
                document_faces.consume(verification_id)
                message = (
                    f"{message} Limite de {max_attempts} tentativas atingido; "
                    "solicite atendimento da recepção."
                )
            else:
                message = (
                    f"{message} Tentativa {attempts_used} de {max_attempts}; "
                    f"restam {attempts_remaining}. Refaça a captura."
                )

    gate = gate_info(session_for_gate.name_status, identity_verified, live_result)
    return FaceVerifyResponse(
        request_id=request_id,
        verification_id=verification_id,
        status=provider_status,
        identity_verified=identity_verified,
        retry_allowed=retry_allowed,
        attempts_used=attempts_used,
        max_attempts=max_attempts,
        attempts_remaining=attempts_remaining,
        provider=provider_result.provider,
        similarity=provider_result.similarity,
        threshold=provider_result.match_threshold,
        review_threshold=provider_result.review_threshold,
        match_threshold=provider_result.match_threshold,
        metric=provider_result.metric,
        model=provider_result.model,
        model_version=provider_result.model_version,
        processing_ms=provider_result.processing_ms,
        embedding_document_ms=provider_result.embedding_document_ms,
        embedding_live_ms=provider_result.embedding_live_ms,
        similarity_ms=provider_result.similarity_ms,
        bbox=detection.bbox,
        image_width=w,
        image_height=h,
        landmarks=detection.landmarks,
        alignment=aligned,
        quality=quality,
        liveness=live_result,
        checkin_gate=gate,
        message=message,
    )


@app.post("/api/v1/face/verify", response_model=FaceVerifyResponse, dependencies=[Depends(auth)])
async def verify_face(
    verification_id: str = Form(min_length=12, max_length=128),
    selfie: UploadFile = File(...),
    cfg: Settings = Depends(get_settings),
):
    return await _verify_face_impl(verification_id, selfie, cfg)


@app.post(
    "/dashboard-api/face/verify",
    response_model=FaceVerifyResponse,
    dependencies=[Depends(dashboard_access)],
    include_in_schema=False,
)
async def dashboard_verify_face(
    verification_id: str = Form(min_length=12, max_length=128),
    selfie: UploadFile = File(...),
    cfg: Settings = Depends(get_settings),
):
    return await _verify_face_impl(verification_id, selfie, cfg)
