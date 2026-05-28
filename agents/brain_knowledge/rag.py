"""RAG (Retrieval-Augmented Generation) engine."""

from brain_core.llm import LLMRouter
from brain_knowledge.retriever import ContextRetriever


class RAGEngine:
    """Retrieval-Augmented Generation engine."""

    def __init__(self) -> None:
        """Initialize the RAG engine."""
        self.retriever = ContextRetriever()
        self.llm = LLMRouter()

    async def query(self, question: str, model: str | None = None) -> str:
        """Answer a question using RAG."""
        # Retrieve relevant context
        chunks = await self.retriever.retrieve_context(question, top_k=5)
        context = "\n\n".join([chunk.content for chunk in chunks])

        # Build prompt with context
        system_prompt = (
            "You are a helpful assistant. Use the following context to answer questions:\n\n"
            + context
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
        return content
