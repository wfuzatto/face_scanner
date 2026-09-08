# face_scanner

Módulo desacoplado de validação documental e preparação da captura facial para o projeto Totem Hoteleiro/HUB.

## Produção

O `face_scanner` é um **microserviço Python/FastAPI em Docker**. Em produção ele é iniciado pelo repositório pai `hub_hotelaria` e **não publica a porta 8091 no host**. O gateway HTTPS do HUB é o único ponto público em `80/443`; dentro da rede Docker o Totem chama `http://face-scanner:8091`.

XAMPP não faz parte do deploy de produção deste módulo.

## O que já funciona
- upload de passaporte, CNH, RG ou CIN;
- OCR local com Tesseract;
- parser MRZ TD3 de passaporte com check digits;
- extração de candidato a nome;
- comparação do nome extraído com o nome da reserva, com normalização de acentos e fuzzy matching;
- detecção/localização de retrato no documento com OpenCV YuNet, sem identificação de pessoas;
- webcam no dashboard de teste;
- validação de presença de uma face e qualidade de captura (tamanho, desfoque e iluminação);
- sessão curta, persistente entre restarts e de uso único;
- provider biométrico plugável, desativado por padrão;
- cliente Node 22 pronto para incorporação no `totem_autoatendimento`;
- Docker, healthcheck, OpenAPI e testes.

## Arquitetura
```text
Totem / HUB
        | rede Docker privada
        v
face_scanner (FastAPI :8091 interno)
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

## Desenvolvimento standalone com Docker

```bash
cp .env.example .env
docker compose up -d --build
```

O `docker-compose.yml` standalone vincula a porta apenas ao loopback do host:

```text
127.0.0.1:8091 -> container:8091
```

Isso serve para desenvolvimento/testes. No stack do HUB nem esse bind existe.

## Produção via HUB

Não suba este repositório separadamente no servidor. O fluxo oficial é realizado a partir de `hub_hotelaria`:

```bash
cd hub_hotelaria
./scripts/update.sh
```

ou, quando o host utiliza o override NVIDIA:

```bash
./scripts/update.sh --gpu
```

## Integração
Veja `docs/TOTEM_INTEGRATION.md` e `integrations/node/faceScannerClient.js`.

## Estado do provider biométrico
A infraestrutura está pronta para receber um provider externo/homologado, mas este repositório não implementa o algoritmo de comparação de identidade por face. O provider padrão retorna `not_configured`.

## Testes
O núcleo possui testes de MRZ, normalização/validação de nomes e sessão de uso único.
