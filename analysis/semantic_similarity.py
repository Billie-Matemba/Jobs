"""
Semantic similarity service for curriculum-to-job matching.

Uses Sentence-BERT when available, with a Word2Vec fallback so analysis can
still run in lightweight environments.
"""

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from django.conf import settings

from .nlp_pipeline import compute_similarity, document_vector, train_word2vec

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    semantic_score: float
    skill_score: float
    final_score: float


class SemanticSimilarityService:
    def __init__(self, corpus: Iterable[str], progress_callback=None):
        self.model_name = getattr(settings, "SEMANTIC_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
        self.semantic_weight = float(getattr(settings, "SEMANTIC_SCORE_WEIGHT", 0.75))
        self.skill_weight = float(getattr(settings, "SKILL_SCORE_WEIGHT", 0.25))
        self.top_module_count = int(getattr(settings, "TOP_MODULE_MATCH_COUNT", 3))
        self.backend = "word2vec"
        self.model = None
        self._progress_callback = progress_callback
        documents = [text for text in corpus if text and text.strip()]

        self._load_sentence_transformer()
        if self.model is None:
            self._report("Sentence transformer unavailable. Falling back to Word2Vec scoring.")
            self.model = train_word2vec(documents)

    def _report(self, message: str) -> None:
        if self._progress_callback:
            self._progress_callback(message)

    def _load_sentence_transformer(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            logger.info("sentence-transformers is not installed; using Word2Vec fallback.")
            return

        try:
            self._report(f"Loading semantic model {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            self.backend = "sentence-transformers"
        except Exception as exc:
            logger.warning("Could not load sentence transformer model: %s", exc, exc_info=True)
            self.model = None

    def vectorize(self, text: str) -> np.ndarray:
        if self.backend == "sentence-transformers":
            return np.asarray(self.model.encode(text or "", normalize_embeddings=True), dtype=float)
        return document_vector(self.model, text or "")

    def similarity(self, left: np.ndarray, right: np.ndarray) -> float:
        score = compute_similarity(left, right)
        return max(0.0, min(1.0, score))

    def course_job_semantic_score(self, module_vectors: Sequence[np.ndarray], job_vector: np.ndarray) -> float:
        scores = sorted(
            (self.similarity(module_vector, job_vector) for module_vector in module_vectors),
            reverse=True,
        )
        if not scores:
            return 0.0
        top_scores = scores[:max(1, self.top_module_count)]
        return float(np.mean(top_scores))

    def skill_coverage_score(self, matched_skills: Sequence[str], job_skills: Sequence[str]) -> float:
        if not job_skills:
            return 0.0
        return len(set(matched_skills)) / max(1, len(set(job_skills)))

    def final_score(self, semantic_score: float, matched_skills: Sequence[str], job_skills: Sequence[str]) -> ScoreBreakdown:
        skill_score = self.skill_coverage_score(matched_skills, job_skills)
        total_weight = max(0.01, self.semantic_weight + self.skill_weight)
        final = ((self.semantic_weight * semantic_score) + (self.skill_weight * skill_score)) / total_weight
        return ScoreBreakdown(
            semantic_score=max(0.0, min(1.0, semantic_score)),
            skill_score=max(0.0, min(1.0, skill_score)),
            final_score=max(0.0, min(1.0, final)),
        )
