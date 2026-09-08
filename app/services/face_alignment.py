from __future__ import annotations

import base64
from dataclasses import dataclass

import cv2
import numpy as np

from app.services.face_engine import FaceDetection


@dataclass
class FaceAlignmentResult:
    success: bool
    width: int
    height: int
    jpeg_base64: str | None
    transform: list[list[float]] | None
    message: str


class FaceAlignmentService:
    """Alinha uma face a partir dos cinco landmarks do YuNet.

    Este serviço apenas normaliza geometria/enquadramento. Ele não gera embedding,
    não calcula similaridade e não toma decisão de identidade.
    """

    def __init__(self, output_size: int = 224, jpeg_quality: int = 90):
        self.output_size = max(96, int(output_size))
        self.jpeg_quality = max(60, min(int(jpeg_quality), 100))

    def _target_points(self) -> np.ndarray:
        s = float(self.output_size)
        return np.array(
            [
                [0.32 * s, 0.38 * s],
                [0.68 * s, 0.38 * s],
                [0.50 * s, 0.56 * s],
                [0.38 * s, 0.73 * s],
                [0.62 * s, 0.73 * s],
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _source_points(detection: FaceDetection) -> np.ndarray:
        lm = detection.landmarks
        return np.array(
            [
                lm["eye_left"],
                lm["eye_right"],
                lm["nose"],
                lm["mouth_left"],
                lm["mouth_right"],
            ],
            dtype=np.float32,
        )

    def align(self, image: np.ndarray, detection: FaceDetection) -> FaceAlignmentResult:
        if image is None or image.size == 0:
            return FaceAlignmentResult(False, self.output_size, self.output_size, None, None, "Imagem vazia.")

        source = self._source_points(detection)
        target = self._target_points()
        if not np.isfinite(source).all():
            return FaceAlignmentResult(False, self.output_size, self.output_size, None, None, "Landmarks inválidos.")

        matrix, inliers = cv2.estimateAffinePartial2D(
            source,
            target,
            method=cv2.LMEDS,
        )
        if matrix is None:
            return FaceAlignmentResult(
                False,
                self.output_size,
                self.output_size,
                None,
                None,
                "Não foi possível calcular a transformação de alinhamento.",
            )

        aligned = cv2.warpAffine(
            image,
            matrix,
            (self.output_size, self.output_size),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        ok, encoded = cv2.imencode(
            ".jpg",
            aligned,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
        )
        if not ok:
            return FaceAlignmentResult(False, self.output_size, self.output_size, None, None, "Falha ao gerar preview alinhado.")

        return FaceAlignmentResult(
            success=True,
            width=self.output_size,
            height=self.output_size,
            jpeg_base64=base64.b64encode(encoded.tobytes()).decode("ascii"),
            transform=[[round(float(value), 6) for value in row] for row in matrix.tolist()],
            message="Face alinhada para inspeção de homologação.",
        )
