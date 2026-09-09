# Handoff do motor biométrico

O Face Scanner 0.4.0 mantém o fluxo documental e de captura pronto para integração com um provider biométrico externo/homologado, sem confirmar identidade por conta própria.

## Já implementado

- YuNet para detecção/localização facial.
- Cinco landmarks por face: olhos, nariz e cantos da boca.
- Alinhamento geométrico para prévia de homologação.
- Qualidade: nitidez, brilho, proporção da face e quantidade de rostos.
- Sessões temporárias com consumo único após a etapa de qualidade.
- `retry_allowed=true` apenas quando a captura pode ser refeita sem consumir a sessão.
- Contrato de provider em `app/providers/face_verification.py`.
- Estados: `match`, `review`, `mismatch`, `not_configured`.
- `identity_verified` fail-closed.
- Metadados opcionais de provider/modelo/métrica/tempos na resposta.
- Liveness/PAD separado e ainda `not_checked`.
- Gate de check-in automático fail-closed.

## Provider

O provider padrão é `DisabledFaceVerificationProvider`, portanto a captura pode ser homologada sem que o sistema afirme identidade.

Uma implementação externa deve respeitar `FaceVerificationProvider.verify(...)` e retornar `FaceVerificationResult`.

`identity_verified` só pode ser verdadeiro quando o status retornado for `match`. O Face Scanner normaliza qualquer inconsistência para fail-closed.

`match_threshold` é o nome canônico do limite de match. O campo `threshold` permanece apenas como alias de compatibilidade.

## Retry e sessão

- nenhum rosto, mais de um rosto ou qualidade insuficiente: `status=review`, `retry_allowed=true`, sessão preservada;
- qualquer resultado recebido do provider: `retry_allowed=false`, sessão consumida;
- uma sessão consumida não pode ser reutilizada.

## Privacidade

Por padrão, não persistir imagens, faces alinhadas ou embeddings para implementar o provider. Não registrar imagens/base64/embeddings em logs.

## Produção

Liveness é independente da verificação do provider. O check-in automático permanece bloqueado enquanto `liveness.status != passed`, mesmo que um provider externo retorne match.
