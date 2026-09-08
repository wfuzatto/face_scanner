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
    landmarks: dict[str, list[float]]


class FaceDetector:
    """Detecta presença/localização e landmarks de face, sem identificar pessoas."""

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
            self._detector = cv2.FaceDetectorYN.create(
                str(self.detector_model),
                "",
                (320, 320),
                self.detection_threshold,
                0.3,
                5000,
            )
            self._load_error = None
        except Exception as exc:
            self._detector = None
            self._load_error = f"Falha ao carregar detector facial: {exc}"

    @staticmethod
    def _landmarks_from_yunet(row: np.ndarray) -> dict[str, list[float]]:
        """Normaliza os cinco pontos retornados pelo YuNet por posição na imagem.

        O detector fornece dois olhos, ponta do nariz e dois cantos da boca.
        Ordenamos olhos e boca pelo eixo X para não depender da convenção
        esquerda/direita do modelo e facilitar alinhamento/visualização.
        """
        raw = np.asarray(row[4:14], dtype=np.float32).reshape(5, 2)
        eyes = sorted((raw[0], raw[1]), key=lambda point: float(point[0]))
        mouth = sorted((raw[3], raw[4]), key=lambda point: float(point[0]))
        nose = raw[2]
        return {
            "eye_left": [round(float(eyes[0][0]), 2), round(float(eyes[0][1]), 2)],
            "eye_right": [round(float(eyes[1][0]), 2), round(float(eyes[1][1]), 2)],
            "nose": [round(float(nose[0]), 2), round(float(nose[1]), 2)],
            "mouth_left": [round(float(mouth[0][0]), 2), round(float(mouth[0][1]), 2)],
            "mouth_right": [round(float(mouth[1][0]), 2), round(float(mouth[1][1]), 2)],
        }

    def detect(self, image: np.ndarray) -> list[FaceDetection]:
        if not self.ready:
            return []
        h, w = image.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(image)
        if faces is None:
            return []

        image_area = float(max(w * h, 1))
        detections: list[FaceDetection] = []
        for row in faces:
            x = max(0, int(row[0]))
            y = max(0, int(row[1]))
            fw = max(0, min(int(row[2]), w - x))
            fh = max(0, min(int(row[3]), h - y))
            detections.append(
                FaceDetection(
                    bbox=[x, y, fw, fh],
                    score=float(row[-1]),
                    face_ratio=float((fw * fh) / image_area),
                    landmarks=self._landmarks_from_yunet(row),
                )
            )
        return sorted(detections, key=lambda d: d.bbox[2] * d.bbox[3], reverse=True)

    def quality(
        self,
        image: np.ndarray,
        detection: FaceDetection,
        min_face_ratio: float,
        min_blur_score: float,
    ) -> dict:
        blur = blur_score(image)
        bright = brightness(image)
        issues: list[str] = []
        if detection.face_ratio < min_face_ratio:
            issues.append("rosto_muito_pequeno")
        if blur < min_blur_score:
            issues.append("imagem_desfocada")
        if bright < 35:
            issues.append("imagem_escura")
        elif bright > 225:
            issues.append("imagem_clara_demais")
        return {
            "blur_score": round(blur, 2),
            "brightness": round(bright, 2),
            "face_ratio": round(detection.face_ratio, 4),
            "acceptable": not issues,
            "issues": issues,
        }
