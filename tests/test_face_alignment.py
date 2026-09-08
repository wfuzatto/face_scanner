import base64

import numpy as np

from app.services.face_alignment import FaceAlignmentService
from app.services.face_engine import FaceDetection, FaceDetector


def test_yunet_landmarks_are_normalized_left_to_right():
    row = np.array(
        [10, 20, 80, 100, 70, 45, 30, 44, 50, 60, 68, 78, 34, 79, 0.99],
        dtype=np.float32,
    )
    landmarks = FaceDetector._landmarks_from_yunet(row)
    assert landmarks["eye_left"][0] < landmarks["eye_right"][0]
    assert landmarks["mouth_left"][0] < landmarks["mouth_right"][0]
    assert landmarks["nose"] == [50.0, 60.0]


def test_alignment_returns_ephemeral_jpeg_preview():
    image = np.zeros((240, 240, 3), dtype=np.uint8)
    image[40:210, 40:200] = 180
    detection = FaceDetection(
        bbox=[40, 40, 160, 170],
        score=0.99,
        face_ratio=0.47,
        landmarks={
            "eye_left": [85.0, 100.0],
            "eye_right": [155.0, 98.0],
            "nose": [120.0, 132.0],
            "mouth_left": [95.0, 160.0],
            "mouth_right": [148.0, 159.0],
        },
    )
    result = FaceAlignmentService(output_size=160).align(image, detection)
    assert result.success is True
    assert result.width == 160
    assert result.height == 160
    assert result.transform is not None
    assert result.jpeg_base64 is not None
    decoded = base64.b64decode(result.jpeg_base64)
    assert decoded[:2] == b"\xff\xd8"
