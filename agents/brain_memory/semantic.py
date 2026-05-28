"""Semantic memory (knowledge graph, FalkorDB-backed)."""

from typing import Any

from falkordb import FalkorDB

from brain_core.config import settings
from brain_memory.models import Fact


class SemanticMemory:
    """Semantic memory stored in FalkorDB knowledge graph."""

    def __init__(self) -> None:
        """Initialize semantic memory with FalkorDB connection."""
        self.db = FalkorDB.from_url(settings.falkordb_url)
        self.graph = self.db.select_graph("knowledge")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure the knowledge graph schema exists."""
        # FalkorDB is schema-optional, so we just ensure indexes
        try:
            self.graph.query("CREATE INDEX FOR (n:Entity) ON (n.name)")
        except Exception:
            pass  # Index already exists

    async def store_fact(self, fact: Fact) -> str:
        """Store a fact in the knowledge graph."""
        query = """
        MERGE (s:Entity {name: $subject})
        MERGE (o:Entity {name: $object})
        CREATE (s)-[r:RELATION {
            type: $predicate,
            confidence: $confidence,
            timestamp: $timestamp
        }]->(o)
        RETURN id(r) as fact_id
        """
        result = self.graph.query(
            query,
            {
                "subject": fact.subject,
                "predicate": fact.predicate,
                "object": fact.object,
                "confidence": fact.confidence,
                "timestamp": fact.timestamp.isoformat(),
            },
        )
        return str(result.result_set[0][0]) if result.result_set else ""

    async def query_facts(
        self,
        subject: str | None = None,
        predicate: str | None = None,
        object: str | None = None,
        limit: int = 10,
    ) -> list[Fact]:
        """Query facts from the knowledge graph."""
        conditions = []
        params: dict[str, Any] = {}

        if subject:
            conditions.append("s.name = $subject")
            params["subject"] = subject
        if predicate:
            conditions.append("r.type = $predicate")
            params["predicate"] = predicate
        if object:
            conditions.append("o.name = $object")
            params["object"] = object

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
        MATCH (s:Entity)-[r:RELATION]->(o:Entity)
        WHERE {where_clause}
        RETURN s.name, r.type, o.name, r.confidence, r.timestamp
        LIMIT $limit
        """
        params["limit"] = limit

        result = self.graph.query(query, params)
        facts = []
        for row in result.result_set:
            facts.append(
                Fact(
                    subject=str(row[0]),
                    predicate=str(row[1]),
                    object=str(row[2]),
                    confidence=float(row[3]),
                )
            )
        return facts

    async def close(self) -> None:
        """Close the FalkorDB connection."""
        self.db.close()

    async def get_entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        """Get an entity from the knowledge graph."""
        query = """
        MATCH (n:Entity {type: $type, name: $id})
        RETURN n.properties
        """
        result = self.graph.query(query, {"type": entity_type, "id": entity_id})
        if result.result_set:
            return dict(result.result_set[0][0]) if result.result_set[0][0] else None
        return None

    async def store_entity(self, entity_type: str, entity_id: str, data: dict[str, Any]) -> None:
        """Store an entity in the knowledge graph."""
        query = """
        MERGE (n:Entity {type: $type, name: $id})
        SET n.properties = $data
        """
        self.graph.query(query, {"type": entity_type, "id": entity_id, "data": data})

    async def get_patterns(self) -> list[dict[str, Any]]:
        """Get behavioral patterns from the knowledge graph."""
        query = """
        MATCH (n:Entity {type: 'pattern'})
        RETURN n.properties
        LIMIT 10
        """
        result = self.graph.query(query, {})
        return [dict(row[0]) for row in result.result_set if row[0]]
