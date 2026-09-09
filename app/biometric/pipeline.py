from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .contracts import DecisionPolicy, EmbeddingEngine, SimilarityEngine


@dataclass(frozen=True)
class BiometricPipelineResult:
    status: str
    identity_verified: bool
    similarity: float
    match_threshold: float | None
    review_threshold: float | None
    metric: str
    model: str
    model_version: str
    embedding_document_ms: float
    embedding_live_ms: float
    similarity_ms: float
    total_ms: float


class BiometricPipeline:
    def __init__(self, embedding_engine: EmbeddingEngine, similarity_engine: SimilarityEngine, decision_policy: DecisionPolicy) -> None:
        self.embedding_engine = embedding_engine
        self.similarity_engine = similarity_engine
        self.decision_policy = decision_policy

    def compare(self, document_face, live_face) -> BiometricPipelineResult:
        started = perf_counter()
        tick = perf_counter(); document = self.embedding_engine.embed(document_face); document_ms = (perf_counter() - tick) * 1000
        tick = perf_counter(); live = self.embedding_engine.embed(live_face); live_ms = (perf_counter() - tick) * 1000
        tick = perf_counter(); similarity = self.similarity_engine.compare(document.vector, live.vector); similarity_ms = (perf_counter() - tick) * 1000
        if not getattr(self.decision_policy, "calibrated", True):
            return BiometricPipelineResult("not_configured", False, float(similarity), None, None, getattr(self.similarity_engine, "metric", "cosine_similarity"), document.model, document.model_version, document_ms, live_ms, similarity_ms, (perf_counter() - started) * 1000)
        decision = self.decision_policy.decide(similarity)
        return BiometricPipelineResult(decision.status, decision.status == "match", float(similarity), decision.match_threshold, decision.review_threshold, getattr(self.similarity_engine, "metric", "cosine_similarity"), document.model, document.model_version, document_ms, live_ms, similarity_ms, (perf_counter() - started) * 1000)
