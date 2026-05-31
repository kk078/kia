"""MCP (Model Context Protocol) server for Secondary Brain."""

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from brain_core.llm import LLMRouter
from brain_core.router import TaskRouter
from brain_core.types import Context
from brain_knowledge.rag import RAGEngine
from brain_memory.episodic import EpisodicMemory
from brain_memory.models import Episode, Fact
from brain_memory.semantic import SemanticMemory
from brain_orchestrator.planner import Orchestrator

server = Server("secondary-brain")


@server.list_tools()  # type: ignore
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="memory_store_episode",
            description="Store an episode in episodic memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Episode content"},
                    "context": {
                        "type": "object",
                        "description": "Episode context metadata",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="memory_retrieve_episodes",
            description="Retrieve episodes from episodic memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="memory_store_fact",
            description="Store a fact in semantic memory (knowledge graph)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "predicate": {"type": "string"},
                    "object": {"type": "string"},
                    "confidence": {"type": "number", "default": 1.0},
                },
                "required": ["subject", "predicate", "object"],
            },
        ),
        Tool(
            name="memory_query_facts",
            description="Query facts from semantic memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "predicate": {"type": "string"},
                    "object": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
            },
        ),
        Tool(
            name="knowledge_query",
            description="Answer a question using RAG (Retrieval-Augmented Generation)",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to answer"},
                    "model": {"type": "string", "description": "Optional model override"},
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="orchestrator_run",
            description="Run the orchestrator to plan and execute a complex goal",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Goal to achieve"},
                    "session_id": {
                        "type": "string",
                        "description": "Session ID",
                        "default": "default",
                    },
                },
                "required": ["goal"],
            },
        ),
        Tool(
            name="llm_generate",
            description="Generate text using LLM",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Prompt text"},
                    "task_type": {
                        "type": "string",
                        "description": "Task type for routing",
                        "default": "simple",
                    },
                    "model": {"type": "string", "description": "Optional model override"},
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="router_classify",
            description="Classify a task to determine the best framework",
            inputSchema={
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description"},
                },
                "required": ["task"],
            },
        ),
    ]


@server.call_tool()  # type: ignore
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "memory_store_episode":
            em = EpisodicMemory()
            episode = Episode(
                content=arguments["content"],
                context=arguments.get("context", {}),
            )
            episode_id = await em.store_episode(episode)
            await em.close()
            return [TextContent(type="text", text=f"Stored episode: {episode_id}")]

        elif name == "memory_retrieve_episodes":
            em = EpisodicMemory()
            episodes = await em.retrieve_episodes(arguments["query"], arguments.get("limit", 10))
            await em.close()
            results = [f"- {ep.content[:100]}... (ID: {ep.id})" for ep in episodes]
            return [TextContent(type="text", text="\n".join(results))]

        elif name == "memory_store_fact":
            sm = SemanticMemory()
            fact = Fact(
                subject=arguments["subject"],
                predicate=arguments["predicate"],
                object=arguments["object"],
                confidence=arguments.get("confidence", 1.0),
            )
            fact_id = await sm.store_fact(fact)
            await sm.close()
            return [TextContent(type="text", text=f"Stored fact: {fact_id}")]

        elif name == "memory_query_facts":
            sm = SemanticMemory()
            facts = await sm.query_facts(
                subject=arguments.get("subject"),
                predicate=arguments.get("predicate"),
                object=arguments.get("object"),
                limit=arguments.get("limit", 10),
            )
            await sm.close()
            results = [
                f"- {f.subject} {f.predicate} {f.object} (confidence: {f.confidence})"
                for f in facts
            ]
            return [TextContent(type="text", text="\n".join(results) or "No facts found")]

        elif name == "knowledge_query":
            rag = RAGEngine()
            answer = await rag.query(arguments["question"], arguments.get("model"))
            return [TextContent(type="text", text=answer)]

        elif name == "orchestrator_run":
            orchestrator = Orchestrator()
            context = Context(session_id=arguments.get("session_id", "default"))
            orch_response = await orchestrator.run(arguments["goal"], context)
            return [TextContent(type="text", text=orch_response.content)]

        elif name == "llm_generate":
            llm = LLMRouter()
            llm_response = await llm.generate(
                arguments["prompt"],
                arguments.get("task_type", "simple"),
                arguments.get("model"),
            )
            return [TextContent(type="text", text=llm_response)]

        elif name == "router_classify":
            router = TaskRouter()
            classification = router.classify_task(arguments["task"])
            info = router.get_framework_info(classification["framework"])
            result = (
                f"Framework: {classification['framework']} ({info.get('name', '')})\n"
                f"Complexity: {classification['complexity']}\n"
                f"Reasoning: {classification['reasoning']}\n"
                f"Best for: {info.get('best_for', '')}"
            )
            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
