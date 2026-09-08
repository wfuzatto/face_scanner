# Docker de produção

O `face_scanner` é um módulo do stack `wfuzatto/hub_hotelaria`.

Em produção:

```text
Internet -> HTTPS :443 -> gateway -> face-scanner:8091
```

A porta `8091` não deve ser publicada no host. O `docker-compose.yml` deste repositório é apenas para teste standalone e faz bind em `127.0.0.1`.

## Segurança e reprodutibilidade

- container roda com usuário não-root;
- `no-new-privileges` no Compose;
- imagens/documentos não são persistidos quando `DEBUG_STORE_IMAGES=false`;
- API key é injetada por ambiente;
- healthcheck é obrigatório;
- o modelo YuNet é baixado no **build**, não na primeira requisição;
- versão do modelo é fixada por commit do OpenCV Zoo e validada por SHA-256 antes de entrar na imagem.

Assim, uma indisponibilidade externa depois que a imagem foi construída não impede o serviço de iniciar.

## GPU

O stack base é CPU-safe. O arquivo `docker-compose.gpu.yml` libera a GPU NVIDIA ao container quando o host possuir NVIDIA Container Toolkit.

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

A simples liberação da GPU não muda o Tesseract atual para GPU. Providers futuros de OCR/visão acelerada deverão detectar CUDA e manter fallback CPU para não transformar a GPU em ponto único de falha.
