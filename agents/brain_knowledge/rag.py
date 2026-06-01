"""RAG (Retrieval-Augmented Generation) engine with response caching."""

from brain_core.cache import ResponseCache, cache_key
from brain_core.config import settings
from brain_core.llm import LLMRouter
from brain_core.security import sanitize_untrusted
from brain_knowledge.retriever import ContextRetriever


class RAGEngine:
    """Retrieval-Augmented Generation engine."""

    def __init__(self) -> None:
        """Initialize the RAG engine."""
        self.retriever = ContextRetriever()
        self.llm = LLMRouter()
        self.cache = ResponseCache()

    async def query(self, question: str, model: str | None = None) -> str:
        """Answer a question using RAG (cached by question+model)."""
        key = cache_key("rag", question, model or "")
        cached = await self.cache.get(key)
        if cached is not None:
            return cached

        # Retrieve relevant context, then sanitize each chunk (untrusted content).
        # Higher top_k: embedded Chroma is vector-only (no BM25 hybrid), so a wider
        # recall window ensures keyword-specific records (e.g. a city name) are included.
        chunks = await self.retriever.retrieve_context(question, top_k=settings.rag_top_k)
        # Sanitize each chunk (strips any injected instructions) but present the result as
        # Kiran's OWN trusted knowledge base — not "untrusted data", which made the small
        # local model refuse to answer from its own records.
        context = "\n\n".join(sanitize_untrusted(chunk.content).clean_text for chunk in chunks)

        system_prompt = (
            "You are KIA (Kiran's Intelligence Architecture), Kiran's personal assistant. "
            "Below are records from Kiran's OWN trusted knowledge base. Treat them as "
            "accurate and answer the question directly from them: find the record(s) that "
            "match (e.g. by city, name, or field) and quote the specific values such as "
            "company name, address, email, and phone. If truly none of the records match, "
            "say you don't have that indexed yet.\n\n"
            "=== KIRAN'S KNOWLEDGE BASE ===\n" + context + "\n=== END ==="
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        # Generate response
        response = await self.llm.complete(
            model=model or self.llm.route("research"),
            messages=messages,
        )

        content: str = response.choices[0].message.content
        await self.cache.set(key, content)
        return content
