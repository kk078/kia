"""Knowledge graph operations using FalkorDB."""

from falkordb import FalkorDB

from brain_core.config import settings
from brain_knowledge.models import Entity, Relation


class KnowledgeGraph:
    """Knowledge graph operations for entity and relation management."""

    def __init__(self) -> None:
        """Initialize the knowledge graph."""
        self.db = FalkorDB.from_url(settings.falkordb_url)
        self.graph = self.db.select_graph("knowledge")

    async def add_entity(self, entity: Entity) -> str:
        """Add an entity to the knowledge graph."""
        query = """
        MERGE (e:Entity {name: $name})
        SET e.type = $type, e.properties = $properties
        RETURN id(e) as entity_id
        """
        result = self.graph.query(
            query,
            {
                "name": entity.name,
                "type": entity.type,
                "properties": entity.properties,
            },
        )
        return str(result.result_set[0][0]) if result.result_set else ""

    async def add_relation(self, relation: Relation) -> str:
        """Add a relation between entities."""
        query = """
        MATCH (s:Entity {name: $source})
        MATCH (t:Entity {name: $target})
        CREATE (s)-[r:RELATION {type: $type, properties: $properties}]->(t)
        RETURN id(r) as relation_id
        """
        result = self.graph.query(
            query,
            {
                "source": relation.source_id,
                "target": relation.target_id,
                "type": relation.type,
                "properties": relation.properties,
            },
        )
        return str(result.result_set[0][0]) if result.result_set else ""

    async def query_entities(
        self,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """Query entities from the knowledge graph."""
        if entity_type:
            query = """
            MATCH (e:Entity {type: $type})
            RETURN e.name, e.type, e.properties
            LIMIT $limit
            """
            result = self.graph.query(query, {"type": entity_type, "limit": limit})
        else:
            query = """
            MATCH (e:Entity)
            RETURN e.name, e.type, e.properties
            LIMIT $limit
            """
            result = self.graph.query(query, {"limit": limit})

        entities = []
        for row in result.result_set:
            entities.append(
                Entity(
                    name=str(row[0]),
                    type=str(row[1]),
                    properties=dict(row[2]) if row[2] else {},
                )
            )
        return entities

    async def close(self) -> None:
        """Close the FalkorDB connection."""
        self.db.close()
