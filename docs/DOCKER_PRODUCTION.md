# Docker de produção

O `face_scanner` é um módulo do stack `wfuzatto/hub_core`.

Em produção:

```text
Internet -> HTTPS :443 -> gateway -> face-scanner:8091
```

A porta `8091` é a porta interna do serviço. O `docker-compose.yml` deste repositório é apenas para teste standalone. No ambiente integrado, publicação adicional de homologação é controlada pelo `hub_core`.

## Segurança e reprodutibilidade

- container roda com usuário não-root;
- `no-new-privileges` no Compose;
- imagens/documentos não são persistidos quando `DEBUG_STORE_IMAGES=false`;
- API key é injetada por ambiente;
- healthcheck é obrigatório;
- modelos YuNet e SFace são preparados no **build**, não na primeira requisição;
- versões dos modelos são fixadas e validadas antes de entrar na imagem;
- somente os metadados temporários das sessões são persistidos em SQLite para sobreviver a restart do container.

O banco temporário de sessões contém identificador, timestamps, reserva e status da validação. Imagens/documentos não são persistidos quando o modo de debug está desabilitado.

## Pipeline facial

O pipeline integrado usa:

```text
YuNet -> alinhamento -> SFace -> normalização -> similaridade cosseno -> política de decisão
```

Os thresholds de decisão são parâmetros externos e devem ser definidos/homologados no ambiente; o serviço não deve inventá-los nem recalibrá-los automaticamente em produção.

## Persistência no HUB Core

O volume lógico `face_scanner_data` aponta para o volume externo de produção:

```text
hub_core_face_scanner_data
```

## GPU

O stack base funciona em CPU. O arquivo `docker-compose.gpu.yml` standalone e o override do `hub_core` podem liberar GPU NVIDIA quando o host possuir NVIDIA Container Toolkit.

A simples liberação da GPU não transforma automaticamente Tesseract/OpenCV em pipelines CUDA. Qualquer aceleração futura deve manter fallback compatível e ser homologada separadamente.
