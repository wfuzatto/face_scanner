# face_scanner

Módulo desacoplado de validação documental e preparação da captura facial para o projeto Totem Hoteleiro/HUB.

## Produção

O `face_scanner` é um **microserviço Python/FastAPI em Docker**. Em produção ele é iniciado pelo repositório pai `hub_hotelaria` e **não publica a porta 8091 no host**. Dentro da rede Docker o Totem chama `http://face-scanner:8091`.

A API de integração `/api/v1/*` continua protegida por `X-Face-Scanner-Key` quando `API_KEY` está configurada.

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

Integração protegida:
- `GET /api/v1/health`
- `POST /api/v1/document/analyze`
- `POST /api/v1/face/verify`

Dashboard standalone:
- `GET /`
- `POST /dashboard-api/document/analyze`
- `POST /dashboard-api/face/verify`

Os endpoints `/dashboard-api/*` só funcionam quando `DASHBOARD_UNAUTHENTICATED=true`. O `docker-compose.yml` standalone ativa isso explicitamente para teste. A chave da API nunca é enviada ao JavaScript do navegador.

## Teste standalone com Docker

No servidor de teste:

```bash
git pull --ff-only origin main
docker compose down
docker compose up -d --build
```

Por padrão o standalone publica:

```text
0.0.0.0:8092 -> container:8091
```

Portanto, em uma máquina da mesma rede, acesse:

```text
http://IP_DO_SERVIDOR:8092
```

Exemplo no servidor `192.168.51.135`:

```text
http://192.168.51.135:8092
```

A porta `8091` do host não é usada pelo standalone. Ela pode continuar pertencendo a outro serviço, enquanto o Face Scanner mantém `8091` somente dentro do próprio container.

Para restringir o standalone ao próprio servidor, defina no `.env`:

```text
STANDALONE_BIND=127.0.0.1
```

Para escolher outra porta de teste:

```text
STANDALONE_PORT=8092
```

> O modo standalone sem autenticação do dashboard é somente para desenvolvimento/homologação em rede controlada. A API `/api/v1/*` continua usando `API_KEY` normalmente.

## Produção via HUB

No stack integrado o Compose deste repositório não é usado. O `hub_hotelaria` constrói o Dockerfile diretamente, deixa `DASHBOARD_UNAUTHENTICATED=false` e mantém o Face Scanner apenas na rede Docker privada.

O fluxo oficial é realizado a partir de `hub_hotelaria`.

## Integração
Veja `docs/TOTEM_INTEGRATION.md` e `integrations/node/faceScannerClient.js`.

## Estado do provider biométrico
A infraestrutura está pronta para receber um provider externo/homologado, mas este repositório não implementa o algoritmo de comparação de identidade por face. O provider padrão retorna `not_configured`.

## Testes
O núcleo possui testes de MRZ, normalização/validação de nomes e sessão de uso único.
