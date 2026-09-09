from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from .contracts import EmbeddingOutput


class SFaceEmbeddingEngine:
    """Provided OpenCV SFace engine, including its model-specific alignment."""

    input_size = (112, 112)
    embedding_dimension = 128

    def __init__(self, model_path: str | Path, model_version: str = "2021dec", model_name: str = "OpenCV SFace") -> None:
        self.model_path = Path(model_path)
        self.model_version = model_version
        self.model_name = model_name
        if not self.model_path.is_file():
            raise FileNotFoundError(f"embedding model not found: {self.model_path}")
        if not hasattr(cv2, "FaceRecognizerSF"):
            raise RuntimeError("installed OpenCV does not provide FaceRecognizerSF")
        self._recognizer = cv2.FaceRecognizerSF.create(str(self.model_path), "", 0, 0)

    @property
    def ready(self) -> bool:
        return self.model_path.is_file()

    def align_crop(self, image: np.ndarray, face_box: np.ndarray) -> np.ndarray:
        if not isinstance(image, np.ndarray) or image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("image must have shape (height, width, 3)")
        if image.size == 0 or not np.isfinite(image).all():
            raise ValueError("image must be non-empty and finite")
        face_box = np.asarray(face_box, dtype=np.float32).reshape(-1)
        # OpenCV FaceRecognizerSF requires bbox + five landmark pairs + score.
        if face_box.size != 15 or not np.isfinite(face_box).all():
            raise ValueError("face_box must be the complete 15-value FaceDetectorYN result")
        aligned = np.asarray(self._recognizer.alignCrop(image, face_box), dtype=image.dtype)
        if aligned.shape != (self.input_size[1], self.input_size[0], 3):
            raise ValueError("SFace alignCrop returned an unexpected shape")
        return aligned.copy()

    def embed(self, aligned_face: np.ndarray) -> EmbeddingOutput:
        if not isinstance(aligned_face, np.ndarray) or aligned_face.shape != (112, 112, 3):
            raise ValueError("SFace input must have shape (112, 112, 3)")
        if not np.issubdtype(aligned_face.dtype, np.number) or not np.isfinite(aligned_face).all():
            raise ValueError("aligned_face must contain finite numeric values")
        vector = np.asarray(self._recognizer.feature(aligned_face), dtype=np.float32).reshape(-1)
        if vector.size != self.embedding_dimension or not np.isfinite(vector).all():
            raise ValueError("embedding output has invalid dimension or values")
        norm = float(np.linalg.norm(vector.astype(np.float64)))
        if not math.isfinite(norm) or norm == 0:
            raise ValueError("embedding output has invalid norm")
        return EmbeddingOutput(vector=(vector / np.float32(norm)).astype(np.float32, copy=True), model=self.model_name, model_version=self.model_version)
