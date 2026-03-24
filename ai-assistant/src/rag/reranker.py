"""Cross-encoder reranking for retrieved documents.

After the initial hybrid retrieval returns candidate nodes, a cross-encoder
scores each (query, document) pair independently, producing a more accurate
relevance estimate than bi-encoder similarity alone.  This module wraps a
lightweight cross-encoder from the ``sentence-transformers`` library so the
reranking step can be toggled on or off via configuration.
"""

import logging
from typing import Optional

from llama_index.core.schema import NodeWithScore

logger = logging.getLogger(__name__)

# Default model — small enough for CPU inference with <200 ms latency on
# typical product-description passages.
DEFAULT_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class CrossEncoderReranker:
    """Reranks a list of ``NodeWithScore`` using a cross-encoder model.

    The model is lazy-loaded on the first call to :meth:`rerank` so that
    import time stays fast and tests can mock the heavy dependency.
    """

    def __init__(self, model_name: Optional[str] = None, top_n: int = 5):
        self.model_name = model_name or DEFAULT_MODEL_NAME
        self.top_n = top_n
        self._model = None

    def _load_model(self):
        """Load the cross-encoder model on first use."""
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info("Loaded cross-encoder model: %s", self.model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed — reranking will "
                "fall back to score-based sorting.  Install with: "
                "pip install sentence-transformers"
            )
        except Exception as exc:
            logger.error("Failed to load cross-encoder model: %s", exc)

    def rerank(
        self,
        query: str,
        nodes: list[NodeWithScore],
        top_n: Optional[int] = None,
    ) -> list[NodeWithScore]:
        """Rerank *nodes* by cross-encoder relevance to *query*.

        Parameters
        ----------
        query:
            The original user query.
        nodes:
            Candidate nodes from the first-stage retriever.
        top_n:
            How many nodes to keep after reranking.  Falls back to the
            instance default (``self.top_n``) when ``None``.

        Returns
        -------
        list[NodeWithScore]
            The *top_n* most relevant nodes, sorted by descending
            cross-encoder score.
        """
        if not nodes:
            return nodes

        k = top_n or self.top_n
        self._load_model()

        if self._model is None:
            # Graceful fallback: sort by existing score and truncate.
            logger.debug("No cross-encoder available; using original scores")
            sorted_nodes = sorted(nodes, key=lambda n: n.score or 0.0, reverse=True)
            return sorted_nodes[:k]

        # Build (query, passage) pairs for scoring.
        texts = [
            self._node_text(node) for node in nodes
        ]
        pairs = [[query, text] for text in texts]

        scores = self._model.predict(pairs)

        # Attach the new score and sort.
        scored = []
        for node, ce_score in zip(nodes, scores):
            reranked = NodeWithScore(
                node=node.node,
                score=float(ce_score),
            )
            scored.append(reranked)

        scored.sort(key=lambda n: n.score, reverse=True)
        result = scored[:k]

        logger.info(
            "Reranked %d → %d nodes  (top score: %.4f, bottom: %.4f)",
            len(nodes),
            len(result),
            result[0].score if result else 0.0,
            result[-1].score if result else 0.0,
        )
        return result

    @staticmethod
    def _node_text(node: NodeWithScore) -> str:
        """Extract plain text from a node, handling different node types."""
        inner = node.node
        if hasattr(inner, "text"):
            return inner.text
        if hasattr(inner, "get_content"):
            return inner.get_content()
        return str(inner)
