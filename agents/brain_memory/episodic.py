"""Episodic memory (timestamped events, Weaviate-backed)."""

from datetime import datetime
from typing import Any

import weaviate
from weaviate.classes.init import AdditionalConfig

from brain_core.config import settings
from brain_memory.models import Episode


class EpisodicMemory:
    """Long-term episodic memory stored in Weaviate."""

    def __init__(self) -> None:
        """Initialize episodic memory with Weaviate connection."""
        # Parse URL: http://localhost:8081 -> host=localhost, port=8081
        url = settings.weaviate_url.replace("http://", "").replace("https://", "")
        if ":" in url:
            host, port_str = url.split(":", 1)
            port = int(port_str)
        else:
            host = url
            port = 8080

        self.client = weaviate.connect_to_local(
            host=host,
            port=port,
            additional_config=AdditionalConfig(),
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Ensure the Episodes collection exists."""
        if not self.client.collections.exists("Episodes"):
            self.client.collections.create(
                name="Episodes",
                description="Timestamped episodic memories",
            )

    async def store_episode(self, episode: Episode) -> str:
        """Store an episode in episodic memory."""
        collection = self.client.collections.get("Episodes")

        # Build properties, only include non-empty dicts
        properties: dict[str, Any] = {
            "content": episode.content,
            "timestamp": episode.timestamp.isoformat(),
        }
        if episode.context:
            properties["context"] = episode.context
        if episode.metadata:
            properties["metadata"] = episode.metadata

        result = collection.data.insert(
            properties=properties,
            vector=episode.embedding if episode.embedding else None,
        )
        return str(result)

    async def retrieve_episodes(
        self,
        query: str,
        limit: int = 10,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> list[Episode]:
        """Retrieve episodes matching a query using BM25 keyword search."""
        collection = self.client.collections.get("Episodes")
        response = collection.query.bm25(
            query=query,
            limit=limit,
        )
        episodes = []
        for obj in response.objects:
            props = obj.properties
            episodes.append(
                Episode(
                    id=str(obj.uuid),
                    content=str(props.get("content", "")),
                    timestamp=datetime.fromisoformat(
                        str(props.get("timestamp", datetime.utcnow().isoformat()))
                    ),
                    context=dict(props.get("context", {})),  # type: ignore[arg-type]
                    metadata=dict(props.get("metadata", {})),  # type: ignore[arg-type]
                )
            )
        return episodes

    async def close(self) -> None:
        """Close the Weaviate connection."""
        self.client.close()

    async def retrieve_recent(self, limit: int = 10) -> list[Episode]:
        """Retrieve the most recent episodes."""
        return await self.retrieve_episodes("", limit=limit)
