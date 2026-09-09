# Handoff do motor biométrico

O Face Scanner 0.5.0 contém a integração local do provider interno fornecido,
mantendo `disabled` como padrão e fail-closed quando o modelo ou a política não
estiverem prontos.

## Já implementado

- YuNet para detecção/localização facial.
- Cinco landmarks por face: olhos, nariz e cantos da boca.
- `FaceAlignmentService` para prévia/UI e `SFaceEmbeddingEngine` com
  `FaceRecognizerSF.alignCrop()` para o modelo.
- Qualidade: nitidez, brilho, proporção da face e quantidade de rostos.
- Sessões temporárias com consumo único após a etapa de qualidade.
- `retry_allowed=true` apenas quando a captura pode ser refeita sem consumir a sessão.
- `BiometricPipeline` e `InternalFaceVerificationProvider`.
- Estados: `match`, `review`, `mismatch`, `not_configured`.
- `identity_verified` fail-closed.
- Metadados opcionais de provider/modelo/métrica/tempos na resposta.
- Liveness/PAD separado e ainda `not_checked`.
- Gate de check-in automático fail-closed.

## Provider

O provider padrão é `DisabledFaceVerificationProvider`. `internal` requer o
modelo SFace e thresholds externos válidos; `mock` continua exclusivamente de
homologação da interface.

Uma implementação externa deve respeitar `FaceVerificationProvider.verify(...)` e retornar `FaceVerificationResult`.

`identity_verified` só pode ser verdadeiro quando o status retornado for
`match`. Thresholds não são calibrados nem escolhidos por este repositório.

`match_threshold` é o nome canônico do limite de match. O campo `threshold` permanece apenas como alias de compatibilidade.

## Retry e sessão

- nenhum rosto, mais de um rosto ou qualidade insuficiente: `status=review`, `retry_allowed=true`, sessão preservada;
- qualquer resultado recebido do provider: `retry_allowed=false`, sessão consumida;
- uma sessão consumida não pode ser reutilizada.

## Privacidade

Por padrão, não persistir imagens, faces alinhadas ou embeddings para implementar o provider. Não registrar imagens/base64/embeddings em logs.

## Produção

Liveness é independente da verificação do provider. O check-in automático permanece bloqueado enquanto `liveness.status != passed`, mesmo que um provider externo retorne match.
