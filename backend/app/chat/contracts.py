from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    model_id: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class FilingChunkRepository(Protocol):
    def full_text_candidates(self, request: Any) -> list[Any]: ...

    def vector_candidates(self, request: Any) -> list[Any]: ...


class StructuredContextProvider(Protocol):
    async def build(self, request: Any) -> Any: ...


class WebSearchProvider(Protocol):
    async def search(self, request: Any) -> Any: ...


class AnswerPlanningModel(Protocol):
    model_id: str

    async def plan(self, request: Any) -> Any: ...


class ChatQuotaRepository(Protocol):
    def reserve(self, request: Any) -> Any: ...

    def consume(self, request: Any) -> bool: ...

    def refund(self, request: Any) -> bool: ...
