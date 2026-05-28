"""Predictive layer for anticipating user needs."""

from datetime import datetime
from typing import Any

from brain_core.llm import LLMRouter
from brain_memory.store import MemoryStore


class PredictiveEngine:
    """Predict user needs and suggest actions."""

    def __init__(self, memory_store: MemoryStore) -> None:
        """Initialize predictive engine.

        Args:
            memory_store: Memory store for accessing user history
        """
        self.memory = memory_store
        self.llm = LLMRouter()

    async def predict_next_action(self, context: dict[str, Any]) -> dict[str, Any]:
        """Predict what the user might want to do next.

        Args:
            context: Current context (recent actions, time, etc.)

        Returns:
            Dict with predictions and confidence scores
        """
        # Get recent activity from memory
        recent_episodes = await self.memory.episodic.retrieve_recent(limit=10)

        # Build prediction prompt
        activity_summary = "\n".join([f"- {ep.content[:100]}" for ep in recent_episodes])

        prompt = f"""Based on the user's recent activity:
{activity_summary}

Current time: {context.get("current_time", datetime.now().isoformat())}
Current context: {context.get("context", "unknown")}

Predict 3 likely next actions the user might want to take, with confidence scores (0-1).
Format: action|confidence"""

        response = await self.llm.generate(prompt, task_type="planning")

        # Parse predictions
        predictions = []
        for line in response.strip().split("\n"):
            if "|" in line:
                parts = line.split("|")
                if len(parts) == 2:
                    try:
                        predictions.append(
                            {
                                "action": parts[0].strip(),
                                "confidence": float(parts[1].strip()),
                            }
                        )
                    except ValueError:
                        continue

        return {
            "predictions": predictions[:3],
            "context": context,
            "based_on_episodes": len(recent_episodes),
        }

    async def suggest_proactive_actions(self) -> list[dict[str, Any]]:
        """Suggest proactive actions based on patterns.

        Returns:
            List of suggested actions with reasons
        """
        # Get user patterns from semantic memory
        patterns = await self.memory.semantic.get_patterns()

        suggestions = []
        for pattern in patterns[:5]:
            suggestion = {
                "action": pattern.get("suggested_action", ""),
                "reason": pattern.get("reason", ""),
                "confidence": pattern.get("confidence", 0.5),
                "trigger": pattern.get("trigger", ""),
            }
            suggestions.append(suggestion)

        return suggestions

    async def detect_anomalies(self) -> list[dict[str, Any]]:
        """Detect anomalies in user behavior.

        Returns:
            List of detected anomalies
        """
        recent = await self.memory.episodic.retrieve_recent(limit=50)

        if len(recent) < 5:
            return []

        # Simple anomaly detection: look for unusual patterns
        anomalies = []

        # Check for gaps in activity
        timestamps = [ep.timestamp for ep in recent if hasattr(ep, "timestamp")]
        if len(timestamps) >= 2:
            gaps = []
            for i in range(len(timestamps) - 1):
                gap = (timestamps[i + 1] - timestamps[i]).total_seconds()
                gaps.append(gap)

            avg_gap = sum(gaps) / len(gaps)
            for i, gap in enumerate(gaps):
                if gap > avg_gap * 3:  # 3x average gap
                    anomalies.append(
                        {
                            "type": "activity_gap",
                            "description": f"Unusual gap in activity: {gap / 3600:.1f} hours",
                            "timestamp": timestamps[i + 1].isoformat(),
                            "severity": "low",
                        }
                    )

        return anomalies
