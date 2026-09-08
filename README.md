# face_scanner

Módulo desacoplado de validação documental e preparação da captura facial para o projeto Totem Hoteleiro/HUB.

## O que já funciona
- upload de passaporte, CNH, RG ou CIN;
- OCR local com Tesseract;
- parser MRZ TD3 de passaporte com check digits;
- extração de candidato a nome;
- comparação do nome extraído com o nome da reserva, com normalização de acentos e fuzzy matching;
- detecção/localização de retrato no documento com OpenCV YuNet, sem identificação de pessoas;
- webcam no dashboard de teste;
- validação de presença de uma face e qualidade de captura (tamanho, desfoque e iluminação);
- sessão curta e de uso único;
- provider biométrico plugável, desativado por padrão;
- cliente Node 20 pronto para incorporação no `totem_autoatendimento`;
- Docker, healthcheck, OpenAPI e testes.

## Arquitetura
```text
Totem / HUB (Node/Electron)
        | HTTP multipart
        v
face_scanner (FastAPI :8091)
  ├─ OCR / documento      -> Tesseract
  ├─ passaporte           -> MRZ TD3 + check digits
  ├─ nome da reserva      -> fuzzy matching com âncoras
  ├─ retrato/presença     -> OpenCV YuNet
  ├─ qualidade da selfie  -> blur / iluminação / enquadramento
  └─ biometria            -> provider plugável (disabled por padrão)
```

## Endpoints
- `GET /api/v1/health`
- `POST /api/v1/document/analyze`
- `POST /api/v1/face/verify`
- `GET /docs`
- `GET /` dashboard de teste

## Instalação Ubuntu
```bash
git clone https://github.com/wfuzatto/face_scanner.git
cd face_scanner
sudo apt update
sudo apt install -y python3-venv tesseract-ocr tesseract-ocr-por tesseract-ocr-eng
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python scripts/download_models.py
uvicorn app.main:app --host 0.0.0.0 --port 8091
```

Abra `http://127.0.0.1:8091`.

## Docker
```bash
cp .env.example .env
docker compose up -d --build
```

## Integração
Veja `docs/TOTEM_INTEGRATION.md` e `integrations/node/faceScannerClient.js`.

## Estado do provider biométrico
A infraestrutura está pronta para receber um provider externo/homologado, mas este repositório não implementa o algoritmo de comparação de identidade por face. O provider padrão retorna `not_configured`.

## Testes
O núcleo foi validado com testes de MRZ, normalização/validação de nomes e sessão de uso único.
