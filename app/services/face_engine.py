from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from app.services.image_utils import blur_score, brightness

@dataclass
class FaceDetection:
    bbox: list[int]
    score: float
    face_ratio: float

class FaceDetector:
    """Detecta presença/localização de face. Não identifica pessoas e não compara identidades."""
    def __init__(self, detector_model: Path, detection_threshold: float = 0.85):
        self.detector_model = Path(detector_model)
        self.detection_threshold = detection_threshold
        self._detector = None
        self._load_error: str | None = None
        self._try_load()
    @property
    def ready(self) -> bool:
        return self._detector is not None
    @property
    def load_error(self) -> str | None:
        return self._load_error
    def _try_load(self) -> None:
        if not self.detector_model.exists():
            self._load_error = "Modelo de detecção facial não encontrado. Execute scripts/download_models.py"
            return
        try:
            self._detector = cv2.FaceDetectorYN.create(str(self.detector_model), "", (320, 320), self.detection_threshold, 0.3, 5000)
            self._load_error = None
        except Exception as exc:
            self._detector = None
            self._load_error = f"Falha ao carregar detector facial: {exc}"
    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        if not self.ready:
            return []
        h, w = image.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(image)
        if faces is None:
            return []
        image_area = float(max(w * h, 1))
        detections = []
        for row in faces:
            x, y, fw, fh = [int(max(0, v)) for v in row[:4]]
            detections.append(FaceDetection(bbox=[x, y, fw, fh], score=float(row[-1]), face_ratio=float((fw * fh) / image_area)))
        return sorted(detections, key=lambda d: d.bbox[2] * d.bbox[3], reverse=True)
    def quality(self, image: np.ndarray, detection: FaceDetection, min_face_ratio: float, min_blur_score: float) -> dict:
        blur = blur_score(image)
        bright = brightness(image)
        issues: list[str] = []
        if detection.face_ratio < min_face_ratio: issues.append("rosto_muito_pequeno")
        if blur < min_blur_score: issues.append("imagem_desfocada")
        if bright < 35: issues.append("imagem_escura")
        elif bright > 225: issues.append("imagem_clara_demais")
        return {"blur_score": round(blur, 2), "brightness": round(bright, 2), "face_ratio": round(detection.face_ratio, 4), "acceptable": not issues, "issues": issues}
