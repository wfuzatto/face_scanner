# Integração com o Totem Hoteleiro / HUB

O `face_scanner` roda como serviço separado. O projeto pai não precisa importar OpenCV, Tesseract ou modelos de visão.

## Fluxo
1. O Totem obtém a reserva e o nome oficial do hóspede.
2. O hóspede envia/fotografa o documento.
3. O Totem chama `POST /api/v1/document/analyze`.
4. O módulo faz OCR, detecta o tipo do documento, tenta extrair o nome, compara com o nome da reserva e localiza a área de retrato do documento.
5. Se a etapa puder continuar, a resposta retorna `verification_id` de curta duração.
6. O Totem abre a webcam e envia a captura para `POST /api/v1/face/verify`.
7. A versão deste repositório valida presença/qualidade da captura e entrega a chamada a um provider biométrico plugável. O provider padrão é `disabled`.

## Node 20
Há um cliente pronto em `integrations/node/faceScannerClient.js`, usando `fetch`, `FormData` e `Blob` nativos do Node 20.

## Configuração sugerida
```env
FACE_SCANNER_URL=http://127.0.0.1:8091
FACE_SCANNER_API_KEY=trocar-em-producao
FACE_SCANNER_ENABLED=true
```

O Totem deve tratar o serviço como provider e ter fallback configurável para atendimento humano quando o módulo ou o provider biométrico estiver indisponível.
