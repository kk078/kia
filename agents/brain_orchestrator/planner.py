"""LangGraph-based orchestrator for hierarchical planning."""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from brain_core.config import settings
from brain_core.llm import LLMRouter
from brain_core.metrics import Timer, track_agent_invocation
from brain_core.tracing import traced
from brain_core.types import AgentResponse, Context
from brain_orchestrator.world_model import WorldModel


class PlanState(TypedDict):
    """State for the planning graph."""

    goal: str
    context: Context
    subtasks: list[str]
    current_task: str
    results: list[dict[str, Any]]
    final_response: str
    iteration: int
    agent: Any  # optional ConnectorAgent for agentic execution (real tool calls)


class Orchestrator:
    """Hierarchical planner and executor using LangGraph."""

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self.llm = LLMRouter()
        self.world_model = WorldModel()
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build the LangGraph state machine."""
        workflow = StateGraph(PlanState)

        # Add nodes
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("execute", self._execute_node)
        workflow.add_node("reflect", self._reflect_node)

        # Add edges
        workflow.set_entry_point("plan")
        workflow.add_edge("plan", "execute")
        workflow.add_edge("execute", "reflect")
        workflow.add_conditional_edges(
            "reflect",
            self._should_continue,
            {
                "continue": "execute",
                "finish": END,
            },
        )

        return workflow.compile()

    async def _plan_node(self, state: PlanState) -> dict[str, Any]:
        """Decompose goal into subtasks."""
        prompt = f"""Break down this goal into 2-4 concrete subtasks.
Goal: {state["goal"]}

Return ONLY a numbered list of subtasks, one per line."""

        response = await self.llm.generate(prompt, task_type="planning")

        # Parse subtasks from response
        subtasks = [
            line.strip().lstrip("0123456789.)- ")
            for line in response.strip().split("\n")
            if line.strip() and line.strip()[0].isdigit()
        ]

        return {
            "subtasks": subtasks,
            "current_task": subtasks[0] if subtasks else "",
            "results": [],
            "iteration": 0,
        }

    async def _execute_node(self, state: PlanState) -> dict[str, Any]:
        """Execute the current subtask."""
        if not state["current_task"]:
            return {"results": state["results"]}

        prompt = f"""Execute this task and provide a clear, concise result.

Context from previous tasks:
{self._format_results(state["results"])}

Current task: {state["current_task"]}

Provide the result in a clear format."""

        # Agentic execution: if connectors are wired, let the subtask call REAL tools
        # (GitHub, web, Slack, ...) via the connector agent. Falls back to plain
        # reasoning when no agent is available or the tool loop errors.
        agent = state.get("agent")
        if agent is not None:
            try:
                response = await agent.run(prompt)
            except Exception:
                response = await self.llm.generate(prompt, task_type="research")
        else:
            response = await self.llm.generate(prompt, task_type="research")

        results = state["results"] + [
            {
                "task": state["current_task"],
                "result": response,
            }
        ]

        # Move to next subtask
        iteration = state["iteration"] + 1
        subtasks = state["subtasks"]
        current_task = subtasks[iteration] if iteration < len(subtasks) else ""

        return {
            "results": results,
            "current_task": current_task,
            "iteration": iteration,
        }

    async def _reflect_node(self, state: PlanState) -> dict[str, Any]:
        """Reflect on results and update world model."""
        # Update world model with results
        for result in state["results"][-1:]:  # Only latest
            self.world_model.update_belief(
                entity="task",
                property=result["task"],
                value=result["result"],
                source="orchestrator",
            )

        return {}

    def _should_continue(self, state: PlanState) -> str:
        """Determine if we should continue executing."""
        if state["iteration"] >= len(state["subtasks"]):
            return "finish"
        if not state["current_task"]:
            return "finish"
        return "continue"

    def _format_results(self, results: list[dict[str, Any]]) -> str:
        """Format results for context."""
        if not results:
            return "No previous results."
        formatted = []
        for r in results:
            formatted.append(f"Task: {r['task']}\nResult: {r['result']}\n")
        return "\n".join(formatted)

    @traced(name="orchestrator_run")
    async def run(self, goal: str, context: Context) -> AgentResponse:
        """Run the orchestrator on a goal."""
        success = True
        try:
            with Timer("orchestrator_execution_time", agent_type="orchestrator"):
                # Optionally bring up connectors so subtasks can take real actions.
                agent = None
                manager = None
                if settings.connectors_enabled:
                    from brain_connectors.agent import ConnectorAgent
                    from brain_connectors.client import MCPConnectorManager

                    manager = MCPConnectorManager(settings.connectors_config)
                    try:
                        await manager.connect()
                        agent = ConnectorAgent(manager)
                    except Exception:
                        agent = None

                initial_state: PlanState = {
                    "goal": goal,
                    "context": context,
                    "subtasks": [],
                    "current_task": "",
                    "results": [],
                    "final_response": "",
                    "iteration": 0,
                    "agent": agent,
                }

                try:
                    final_state = await self.graph.ainvoke(initial_state)
                finally:
                    if manager is not None:
                        await manager.close()

                # Synthesize final response
                synthesis_prompt = (
                    "Given the goal and the results of subtasks, "
                    "provide a comprehensive answer.\n\n"
                    f"Goal: {goal}\n\n"
                    f"Results:\n{self._format_results(final_state['results'])}\n\n"
                    "Provide a clear, comprehensive answer to the original goal."
                )

                # Verified synthesis (self-consistency when verify_enabled; else plain generate).
                final_response = await self.llm.generate_verified(
                    synthesis_prompt, task_type="synthesis"
                )

                return AgentResponse(
                    content=final_response,
                    confidence=0.9,
                    sources=[r["task"] for r in final_state["results"]],
                    metadata={
                        "subtasks": final_state["subtasks"],
                        "iterations": final_state["iteration"],
                    },
                )
        except Exception:
            success = False
            raise
        finally:
            track_agent_invocation("orchestrator", success=success)
