# Privacidade e segurança

Este módulo manipula documentos de identidade e capturas faciais. Em produção, aplique a política jurídica/LGPD definida para a operação do hotel.

## Implementado
- processamento em memória;
- nenhuma foto persistida por padrão;
- sessão curta e de uso único;
- API key opcional;
- limite de tamanho e formatos de upload;
- OCR e logs sem persistência de imagens.

## Antes de produção
- usar HTTPS/TLS ou rede local isolada;
- definir base legal, transparência e retenção;
- evitar documentos, OCR integral e imagens em logs;
- limitar acesso administrativo;
- calibrar qualidade de captura nas câmeras reais;
- homologar o provider biométrico e a política de prova de vida separadamente.

A versão deste repositório não implementa comparação biométrica de identidade. O endpoint facial valida presença/qualidade e termina no provider `disabled` até uma integração aprovada ser configurada.
