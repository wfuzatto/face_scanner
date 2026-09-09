# face_scanner

Módulo desacoplado de validação documental e facial para o Totem Hoteleiro/HUB.

## Produção

O `face_scanner` é um **microserviço Python/FastAPI em Docker**. Em produção ele é iniciado pelo repositório pai `hub_core`. Dentro da rede Docker o Totem chama `http://face-scanner:8091`.

A API de integração `/api/v1/*` continua protegida por `X-Face-Scanner-Key` quando `API_KEY` está configurada.

XAMPP não faz parte do deploy de produção deste módulo.

## O que já funciona
- upload de passaporte, CNH, RG ou CIN;
- OCR local com Tesseract;
- parser MRZ TD3 de passaporte com check digits;
- extração de candidato a nome;
- comparação do nome extraído com o nome da reserva, com normalização de acentos e fuzzy matching;
- detecção/localização facial com OpenCV YuNet;
- webcam no dashboard de teste;
- validação de presença de uma face e qualidade de captura (tamanho, desfoque e iluminação);
- sessão curta, persistente entre restarts e de uso único;
- pipeline biométrico interno com OpenCV SFace, embeddings normalizados e similaridade cosseno;
- política de decisão em três níveis com thresholds fornecidos externamente/homologados;
- provider biométrico plugável (`disabled`, `mock` para homologação de interface e `internal` para SFace);
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
  ├─ detecção/alinhamento -> OpenCV YuNet
  ├─ embedding facial     -> OpenCV SFace
  ├─ similaridade         -> cosseno
  ├─ qualidade da selfie  -> blur / iluminação / enquadramento
  └─ decisão biométrica   -> thresholds externos homologados
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

## Teste standalone com HTTPS

**O navegador deve acessar este módulo sempre por HTTPS.** A câmera (`getUserMedia`) depende de contexto seguro; por isso o HTTP standalone nunca deve ser usado diretamente pelo navegador.

Use somente o launcher:

```bash
git pull --ff-only origin main
chmod +x scripts/*.sh
./scripts/start_standalone_https.sh
```

O launcher:

1. remove apenas instâncias antigas conhecidas do Face Scanner standalone;
2. executa `docker compose down` somente deste projeto;
3. procura automaticamente uma porta local livre entre `18092` e `18120`;
4. publica o FastAPI somente em `127.0.0.1`;
5. sobe/recria o container;
6. aguarda o healthcheck;
7. atualiza somente o bloco gerenciado do Face Scanner no Caddy existente;
8. valida e recarrega o Caddy;
9. informa a URL HTTPS final.

Exemplo:

```text
https://192.168.51.135:8445
        ↓
Caddy do host
        ↓
http://127.0.0.1:18092   (ou outra porta livre escolhida automaticamente)
        ↓
Face Scanner Docker :8091
```

O arquivo `.standalone-runtime.env` registra a porta local escolhida no último start e não contém API keys.

Configurações opcionais:

```text
STANDALONE_PORT_START=18092
STANDALONE_PORT_END=18120
STANDALONE_HTTPS_HOST=192.168.51.135
STANDALONE_HTTPS_PORT=8445
```

O certificado é emitido pelo `tls internal` do Caddy existente. O dispositivo que abrir o dashboard deve confiar na CA local desse Caddy para que o navegador considere a origem segura sem erro de certificado.

> O modo standalone sem autenticação do dashboard é somente para desenvolvimento/homologação em rede controlada. A API `/api/v1/*` continua usando `API_KEY` normalmente.

## Produção via HUB Core

No stack integrado o Compose deste repositório não é usado. O `hub_core` constrói o Dockerfile diretamente, mantém `DASHBOARD_UNAUTHENTICATED=false` e controla rede, persistência e healthcheck.

O fluxo oficial é realizado a partir de `hub_core`:

```bash
cd /home/luisnasc/hub_core
bash scripts/update_docker.sh
```

## Integração
Veja `docs/TOTEM_INTEGRATION.md` e `integrations/node/faceScannerClient.js`.

## Estado do provider biométrico

O provider interno SFace está implementado. Para operação real, ele depende do modelo SFace carregado e de thresholds definidos/homologados externamente. O modo `mock` continua restrito à homologação da interface e não deve ser confundido com validação real de identidade.

## Testes
O núcleo possui testes de MRZ, normalização/validação de nomes, sessão de uso único, embedding SFace e integração do provider biométrico.
