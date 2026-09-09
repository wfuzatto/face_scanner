import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

# Modelo fixado por commit do OpenCV Zoo e validado pelo SHA-256 do objeto Git LFS.
# Isso evita que um build futuro receba silenciosamente um modelo diferente.
MODEL_NAME = "face_detection_yunet_2023mar.onnx"
OPENCV_ZOO_COMMIT = "47534e27c9851bb1128ccc0102f1145e27f23f98"
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
MODEL_SIZE = 232589
MODEL_URLS = (
    f"https://github.com/opencv/opencv_zoo/raw/{OPENCV_ZOO_COMMIT}/models/face_detection_yunet/{MODEL_NAME}",
    f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{OPENCV_ZOO_COMMIT}/models/face_detection_yunet/{MODEL_NAME}",
)
EMBEDDING_MODEL_NAME = "face_recognition_sface_2021dec.onnx"
EMBEDDING_MODEL_SHA256 = "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
EMBEDDING_MODEL_SIZE = 38696353
EMBEDDING_MODEL_URLS = (
    f"https://github.com/opencv/opencv_zoo/raw/{OPENCV_ZOO_COMMIT}/models/face_recognition_sface/{EMBEDDING_MODEL_NAME}",
    f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{OPENCV_ZOO_COMMIT}/models/face_recognition_sface/{EMBEDDING_MODEL_NAME}",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_model(data: bytes) -> bool:
    return len(data) == MODEL_SIZE and sha256_bytes(data) == MODEL_SHA256


def valid_embedding_model(data: bytes) -> bool:
    return len(data) == EMBEDDING_MODEL_SIZE and sha256_bytes(data) == EMBEDDING_MODEL_SHA256


def download(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "face-scanner/0.2"})
    with urlopen(req, timeout=120) as response:
        return response.read()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    model_dir = root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    embedding_target = model_dir / EMBEDDING_MODEL_NAME
    if not embedding_target.exists() or not valid_embedding_model(embedding_target.read_bytes()):
        last_error: Exception | None = None
        for url in EMBEDDING_MODEL_URLS:
            try:
                data = download(url)
                if data.startswith(b"version https://git-lfs.github.com/spec") or not valid_embedding_model(data):
                    raise RuntimeError("modelo SFace inválido")
                tmp = embedding_target.with_suffix(embedding_target.suffix + ".tmp")
                tmp.write_bytes(data)
                tmp.replace(embedding_target)
                break
            except Exception as exc:
                last_error = exc
        else:
            raise RuntimeError(f"Não foi possível obter o modelo SFace validado: {last_error}")
    target = model_dir / MODEL_NAME

    if target.exists():
        current = target.read_bytes()
        if valid_model(current):
            print(f"Modelo validado: {target}")
            return
        print("Modelo local inválido ou diferente; será baixado novamente.")

    last_error: Exception | None = None
    for url in MODEL_URLS:
        try:
            print(f"Baixando {MODEL_NAME} de fonte fixada...")
            data = download(url)
            if data.startswith(b"version https://git-lfs.github.com/spec"):
                raise RuntimeError("fonte devolveu ponteiro Git LFS, não o modelo")
            if not valid_model(data):
                raise RuntimeError(
                    f"integridade inválida: size={len(data)} sha256={sha256_bytes(data)}"
                )

            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
            print(f"OK: {len(data) / 1024:.1f} KiB | sha256={MODEL_SHA256}")
            return
        except Exception as exc:  # tenta a segunda origem antes de abortar o build
            last_error = exc
            print(f"Falha em {url}: {exc}")

    raise RuntimeError(f"Não foi possível obter o modelo YuNet validado: {last_error}")


if __name__ == "__main__":
    main()
