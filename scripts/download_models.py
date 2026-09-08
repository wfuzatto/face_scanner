from pathlib import Path
from urllib.request import Request, urlopen

MODEL = ("face_detection_yunet_2023mar.onnx", "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx")

def main() -> None:
    root = Path(__file__).resolve().parents[1]
    model_dir = root / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    name, url = MODEL
    target = model_dir / name
    if target.exists() and target.stat().st_size > 100_000:
        print(f"Já existe: {target}")
        return
    print(f"Baixando {name}...")
    req = Request(url, headers={"User-Agent": "face-scanner/0.1"})
    with urlopen(req, timeout=120) as response:
        data = response.read()
    if data.startswith(b"version https://git-lfs.github.com/spec"):
        raise RuntimeError("GitHub devolveu ponteiro Git LFS, não o modelo real")
    target.write_bytes(data)
    print(f"OK: {len(data) / 1024 / 1024:.2f} MiB")

if __name__ == "__main__":
    main()
