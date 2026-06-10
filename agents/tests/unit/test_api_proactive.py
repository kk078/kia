"""Tests for the proactive API (scheduled prompts, file watches) and n8n routes."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes import proactive


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Lifespan-aware client: one event loop for all requests in a test, and the
    app shutdown hook stops the scheduler/watcher on that same loop."""
    with TestClient(app) as c:
        yield c
    # shutdown_proactive ran on context exit; globals are already reset.
    assert proactive._scheduler is None
    assert proactive._watcher is None


class TestScheduledPrompts:
    """Scheduling, listing, and removing proactive prompt jobs."""

    def test_status_empty_initially(self, client: TestClient) -> None:
        data = client.get("/api/v1/proactive/status").json()
        assert data["tasks"] == []
        assert data["watches"] == []

    def test_schedule_interval_task(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/proactive/tasks",
            json={"job_id": "digest", "prompt": "Summarize today", "every_minutes": 30},
        )
        assert response.status_code == 200
        task = response.json()["task"]
        assert task["id"] == "digest"
        assert task["next_run"] is not None

        status = client.get("/api/v1/proactive/status").json()
        assert status["scheduler_running"] is True
        assert [t["id"] for t in status["tasks"]] == ["digest"]

    def test_schedule_cron_task(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/proactive/tasks",
            json={"job_id": "morning", "prompt": "Daily brief", "cron": "0 8 * * *"},
        )
        assert response.status_code == 200
        assert response.json()["task"]["id"] == "morning"

    def test_requires_exactly_one_schedule(self, client: TestClient) -> None:
        neither = client.post("/api/v1/proactive/tasks", json={"job_id": "x", "prompt": "p"})
        both = client.post(
            "/api/v1/proactive/tasks",
            json={"job_id": "x", "prompt": "p", "every_minutes": 5, "cron": "* * * * *"},
        )
        assert neither.status_code == 422
        assert both.status_code == 422

    def test_invalid_cron_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/proactive/tasks",
            json={"job_id": "bad", "prompt": "p", "cron": "not a cron"},
        )
        assert response.status_code == 422

    def test_remove_task(self, client: TestClient) -> None:
        client.post(
            "/api/v1/proactive/tasks",
            json={"job_id": "tmp", "prompt": "p", "every_minutes": 5},
        )
        assert client.delete("/api/v1/proactive/tasks/tmp").status_code == 200
        assert client.delete("/api/v1/proactive/tasks/tmp").status_code == 404


class TestPromptJobExecution:
    """The job body: generate -> store to episodic memory, crash-proof."""

    @pytest.mark.asyncio
    async def test_job_stores_episode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stored: list[tuple[str, dict[str, Any]]] = []

        async def fake_generate(*args: Any, **kwargs: Any) -> tuple[str, str]:
            return "the answer", "test-model"

        async def fake_store(content: str, context: dict[str, Any]) -> None:
            stored.append((content, context))

        monkeypatch.setattr("brain_core.fallback.resilient_generate", fake_generate)
        monkeypatch.setattr(proactive, "_store_episode", fake_store)

        await proactive.run_prompt_job("job1", "what's new?")

        assert stored == [
            (
                "the answer",
                {"source": "proactive:job1", "prompt": "what's new?", "model": "test-model"},
            )
        ]

    @pytest.mark.asyncio
    async def test_job_swallows_provider_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def boom(*args: Any, **kwargs: Any) -> tuple[str, str]:
            raise RuntimeError("provider down")

        monkeypatch.setattr("brain_core.fallback.resilient_generate", boom)
        await proactive.run_prompt_job("job2", "p")  # must not raise

    @pytest.mark.asyncio
    async def test_file_event_stores_episode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stored: list[tuple[str, dict[str, Any]]] = []

        async def fake_store(content: str, context: dict[str, Any]) -> None:
            stored.append((content, context))

        monkeypatch.setattr(proactive, "_store_episode", fake_store)
        await proactive.on_file_event("modified", "C:/dev/x.py")

        assert stored[0][0] == "File modified: C:/dev/x.py"
        assert stored[0][1]["source"] == "proactive:watch"


class TestWatches:
    """Directory watch lifecycle."""

    def test_watch_and_unwatch(self, client: TestClient, tmp_path: Path) -> None:
        response = client.post("/api/v1/proactive/watch", json={"path": str(tmp_path)})
        assert response.status_code == 200
        watch_id = response.json()["watch_id"]

        status = client.get("/api/v1/proactive/status").json()
        assert len(status["watches"]) == 1

        assert client.delete(f"/api/v1/proactive/watch/{watch_id}").status_code == 200
        assert client.delete(f"/api/v1/proactive/watch/{watch_id}").status_code == 404

    def test_watch_missing_path_404(self, client: TestClient) -> None:
        response = client.post("/api/v1/proactive/watch", json={"path": "C:/does/not/exist-xyz"})
        assert response.status_code == 404


class TestN8NRoutes:
    """n8n bridge endpoints (client mocked)."""

    def test_list_workflows(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_list(self: Any) -> list[dict[str, Any]]:
            return [{"id": "1", "name": "wf"}]

        monkeypatch.setattr("brain_n8n.client.N8NClient.list_workflows", fake_list)
        data = client.get("/api/v1/n8n/workflows").json()
        assert data["count"] == 1
        assert data["workflows"][0]["name"] == "wf"

    def test_run_workflow(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_run(self: Any, wid: str, data: dict[str, Any]) -> dict[str, Any]:
            return {"executionId": "e1", "workflow_id": wid}

        monkeypatch.setattr("brain_n8n.client.N8NClient.execute_workflow", fake_run)
        response = client.post("/api/v1/n8n/workflows/1/run", json={"data": {"k": "v"}})
        assert response.status_code == 200
        assert response.json()["executionId"] == "e1"

    def test_run_workflow_error_is_502(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_run(self: Any, wid: str, data: dict[str, Any]) -> dict[str, Any]:
            return {"error": "connection refused", "workflow_id": wid}

        monkeypatch.setattr("brain_n8n.client.N8NClient.execute_workflow", fake_run)
        response = client.post("/api/v1/n8n/workflows/1/run", json={"data": {}})
        assert response.status_code == 502
