import numpy as np
import pytest

from app.biometric.embedding_engine import SFaceEmbeddingEngine


class Recognizer:
    def feature(self, _):
        return np.ones(128, dtype=np.float32)


def engine():
    item = SFaceEmbeddingEngine.__new__(SFaceEmbeddingEngine)
    item.model_name, item.model_version, item._recognizer = "test", "test", Recognizer()
    return item


def test_sface_requires_full_yunet_record_and_returns_model_geometry():
    item = engine()
    received = []
    item._recognizer.alignCrop = lambda image, box: (received.append(box.copy()) or np.zeros((112, 112, 3), dtype=np.uint8))
    full = np.array([10, 20, 80, 90, 30, 45, 65, 45, 48, 62, 35, 84, 62, 84, .99], dtype=np.float32)
    assert item.align_crop(np.zeros((200, 200, 3), dtype=np.uint8), full).shape == (112, 112, 3)
    assert received[0].shape == (15,)
    with pytest.raises(ValueError, match="15-value"):
        item.align_crop(np.zeros((200, 200, 3), dtype=np.uint8), full[:4])


def test_sface_embedding_has_exact_input_and_output_format():
    result = engine().embed(np.ones((112, 112, 3), dtype=np.uint8))
    assert result.vector.dtype == np.float32
    assert result.vector.shape == (128,)
    assert np.linalg.norm(result.vector) == pytest.approx(1.0)
