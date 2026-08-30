"""Article clustering: groups near-duplicate articles (same event, different
sources) into clusters so one story = one opportunity with corroboration.

Design notes (Phase 2):
- Every article still gets stored; duplicates share `article_cluster_id` and
  corroboration is derived in SQL via COUNT(*). No stored counters, no skipped
  rows (see IMPLEMENTATION_PLAN.md v1.1 corrections).
- The sentence-transformer model is lazy-loaded: importing this module is cheap
  and clustering can be disabled via `settings.clustering_enabled` without
  paying the torch/model cost.
- Embeddings are cached per title within the process to avoid recomputation
  during a scrape run.
"""

import hashlib
import logging
from typing import Dict, List, Optional

import numpy as np
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class ArticleClusterer:
    def __init__(self, similarity_threshold: float = 0.6, fuzzy_prefilter: float = 0.4):
        # similarity_threshold calibrated 2026-08-04 against all-MiniLM-L6-v2:
        # same-event titles scored 0.56-0.84, different events <= 0.23.
        # 0.6 keeps a >2x margin over the worst different-event pair.
        self.similarity_threshold = similarity_threshold
        self.fuzzy_prefilter = fuzzy_prefilter
        self._model = None
        self._embedding_cache: Dict[str, np.ndarray] = {}

    @property
    def model(self):
        """Lazy-load the embedding model on first use (~80MB download once)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformer model 'all-MiniLM-L6-v2' (first use downloads ~80MB)...")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Embedding model loaded")
        return self._model

    def encode(self, title: str) -> np.ndarray:
        """Return the (cached) embedding for a title."""
        if title not in self._embedding_cache:
            self._embedding_cache[title] = self.model.encode(title)
        return self._embedding_cache[title]

    def fuzzy_match(self, title1: str, title2: str) -> float:
        """Cheap string similarity (0.0-1.0), used as a pre-filter."""
        return fuzz.ratio(title1.lower(), title2.lower()) / 100.0

    def compute_similarity(self, title1: str, title2: str) -> float:
        """Cosine similarity between two title embeddings (0.0-1.0)."""
        emb1, emb2 = self.encode(title1), self.encode(title2)
        denom = np.linalg.norm(emb1) * np.linalg.norm(emb2)
        if denom == 0:
            return 0.0
        return float(np.dot(emb1, emb2) / denom)

    def find_cluster(self, new_title: str, existing_articles: List[dict]) -> Optional[str]:
        """Find the cluster a new article belongs to.

        Args:
            new_title: Title of the new article.
            existing_articles: Recent articles as dicts with at least
                'id', 'title', and optionally 'article_cluster_id'.

        Returns:
            The best-matching article's cluster id (falling back to its row id
            as a string), or None if no article clears the similarity threshold.
        """
        best_cluster = None
        best_score = 0.0
        new_embedding = None

        for article in existing_articles:
            title = article.get("title") or ""
            if not title:
                continue

            # Pre-filter: skip pairs that can't plausibly be the same event
            if self.fuzzy_match(new_title, title) < self.fuzzy_prefilter:
                continue

            if new_embedding is None:
                new_embedding = self.encode(new_title)

            other = self.encode(title)
            denom = np.linalg.norm(new_embedding) * np.linalg.norm(other)
            similarity = float(np.dot(new_embedding, other) / denom) if denom else 0.0

            if similarity >= self.similarity_threshold and similarity > best_score:
                best_score = similarity
                best_cluster = article.get("article_cluster_id") or str(article.get("id"))

        if best_cluster:
            logger.debug(f"Cluster match ({best_score:.2f}): {new_title[:50]}")
        return best_cluster

    @staticmethod
    def new_cluster_id(title: str) -> str:
        """Deterministic cluster id for a new cluster."""
        return hashlib.md5(title.encode()).hexdigest()[:12]


clusterer = ArticleClusterer()
