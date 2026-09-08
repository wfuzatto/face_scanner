# Handoff do motor biométrico

O Face Scanner já prepara o fluxo sem tomar decisão de identidade.

## Já implementado neste repositório

- YuNet para detecção/localização facial.
- Cinco landmarks por face: olhos, nariz e cantos da boca.
- Alinhamento geométrico para uma prévia quadrada padronizada.
- Qualidade: nitidez, brilho, proporção da face e quantidade de rostos.
- Sessões temporárias e consumo único.
- Contratos isolados em `app/biometric/contracts.py`.
- Estados do provider: `match`, `review`, `mismatch`, `not_configured`.
- `identity_verified` fail-closed.
- Contrato separado para liveness/PAD.
- Helpers para FAR/FRR a partir de resultados já rotulados.
- Gate de check-in automático fail-closed.

## Implementação que deve ser fornecida separadamente

Preencher uma implementação concreta para os contratos:

- `EmbeddingEngine.embed(aligned_face)`
- `SimilarityEngine.compare(document, live)`
- `DecisionPolicy.decide(similarity)`

O componente externo deverá fornecer, para cada tentativa, um resultado final compatível com:

```json
{
  "status": "match|review|mismatch",
  "identity_verified": false,
  "similarity": null,
  "threshold": null,
  "review_threshold": null,
  "model": "...",
  "model_version": "..."
}
```

`identity_verified` só pode ser `true` quando `status == "match"`.

## Regras de integração

1. Não alterar YuNet, OCR, reserva ou captura para encaixar o motor.
2. O motor deve receber apenas a face já preparada para sua etapa.
3. Não persistir embeddings por padrão.
4. Não registrar imagens, embeddings ou nomes completos em logs.
5. Provider indisponível, timeout ou resposta inválida deve resultar em fail-closed.
6. Manter três estados: `mismatch`, `review`, `match`.
7. Liveness é independente da comparação facial.
8. Check-in automático só pode ser liberado quando documento, identidade e liveness estiverem explicitamente aprovados.

## Homologação

Antes de produção, gerar resultados rotulados fora deste repositório e alimentar os helpers de `app/metrics/classification.py` para medir:

- true accept
- true reject
- false accept
- false reject
- FAR
- FRR

Os thresholds finais devem ser calibrados e homologados para o modelo e cenário reais antes de habilitar check-in automático.
