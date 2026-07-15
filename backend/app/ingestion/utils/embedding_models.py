
from langchain.embeddings import CacheBackedEmbeddings

from app.core.ai_clients import create_embedding_model
from app.init_db import logger


class CacheBackedEmbeddingsExtended(CacheBackedEmbeddings):
    def embed_query(self, text: str) -> list[float]:
        """
        Embed query text.

        Extended to support caching

        Args:
            text: The text to embed.

        Returns:
            The embedding for the given text.
        """
        vectors: list[list[float] | None] = self.document_embedding_store.mget(
            [text]
        )
        text_embeddings = vectors[0]

        if text_embeddings is None:
            text_embeddings = self.underlying_embeddings.embed_query(text)
            self.document_embedding_store.mset(
                list(zip([text], [text_embeddings], strict=True))
            )

        return text_embeddings


def get_embedding_model() -> CacheBackedEmbeddings:
    """
    Get the embedding model from the embedding model type.
    """

    underlying_embeddings = create_embedding_model()

    # embedder = CacheBackedEmbeddingsExtended(underlying_embeddings)

    logger.info(f"Loaded embedding model: {underlying_embeddings.model}")

    # store = get_redis_store()
    # embedder = CacheBackedEmbeddingsExtended.from_bytes_store(
    #     underlying_embeddings, store, namespace=underlying_embeddings.model
    # )
    return underlying_embeddings
