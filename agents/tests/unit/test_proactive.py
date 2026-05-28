"""Tests for proactive engine components."""

from typing import Any

import pytest

from brain_proactive.scheduler import TaskScheduler
from brain_proactive.trigger import EventTrigger
from brain_proactive.watcher import FileWatcher


class TestTaskScheduler:
    """Test TaskScheduler functionality."""

    @pytest.fixture
    def scheduler(self) -> TaskScheduler:
        """Create a scheduler instance."""
        return TaskScheduler()

    @pytest.mark.asyncio
    async def test_add_interval_task(self, scheduler: TaskScheduler) -> None:
        """Test adding an interval task."""
        call_count = 0

        async def test_task() -> None:
            nonlocal call_count
            call_count += 1

        job_id = scheduler.add_interval_task(
            job_id="test_interval",
            func=test_task,
            seconds=1,
        )

        assert job_id == "test_interval"
        assert "test_interval" in scheduler.jobs

    @pytest.mark.asyncio
    async def test_add_cron_task(self, scheduler: TaskScheduler) -> None:
        """Test adding a cron task."""

        async def test_task() -> None:
            pass

        job_id = scheduler.add_cron_task(
            job_id="test_cron",
            func=test_task,
            cron_expression="0 * * * *",
        )

        assert job_id == "test_cron"
        assert "test_cron" in scheduler.jobs

    @pytest.mark.asyncio
    async def test_remove_task(self, scheduler: TaskScheduler) -> None:
        """Test removing a task."""

        async def test_task() -> None:
            pass

        scheduler.add_interval_task("test_remove", test_task, seconds=10)
        assert "test_remove" in scheduler.jobs

        removed = scheduler.remove_task("test_remove")
        assert removed is True
        assert "test_remove" not in scheduler.jobs

    @pytest.mark.asyncio
    async def test_list_tasks(self, scheduler: TaskScheduler) -> None:
        """Test listing tasks."""

        async def test_task() -> None:
            pass

        scheduler.add_interval_task("task1", test_task, seconds=10)
        scheduler.add_interval_task("task2", test_task, seconds=20)

        tasks = scheduler.list_tasks()
        assert len(tasks) == 2
        assert any(t["id"] == "task1" for t in tasks)
        assert any(t["id"] == "task2" for t in tasks)


class TestEventTrigger:
    """Test EventTrigger functionality."""

    @pytest.fixture
    def trigger(self) -> EventTrigger:
        """Create a trigger instance."""
        return EventTrigger()

    @pytest.mark.asyncio
    async def test_on_and_emit(self, trigger: EventTrigger) -> None:
        """Test registering and emitting events."""
        received_data: list[dict[str, Any]] = []

        async def handler(data: dict[str, Any]) -> None:
            received_data.append(data)

        trigger.on("test_event", handler)

        await trigger.emit("test_event", {"key": "value"})

        assert len(received_data) == 1
        assert received_data[0] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, trigger: EventTrigger) -> None:
        """Test multiple handlers for same event."""
        call_count = 0

        async def handler1(data: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1

        async def handler2(data: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1

        trigger.on("multi_event", handler1)
        trigger.on("multi_event", handler2)

        await trigger.emit("multi_event", {})

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_off_handler(self, trigger: EventTrigger) -> None:
        """Test removing a handler."""
        call_count = 0

        async def handler(data: dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1

        trigger.on("off_test", handler)
        await trigger.emit("off_test", {})
        assert call_count == 1

        trigger.off("off_test", handler)
        await trigger.emit("off_test", {})
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_get_history(self, trigger: EventTrigger) -> None:
        """Test event history."""

        async def handler(data: dict[str, Any]) -> None:
            pass

        trigger.on("history_test", handler)
        await trigger.emit("history_test", {"event": 1})
        await trigger.emit("history_test", {"event": 2})

        history = trigger.get_history()
        assert len(history) == 2
        assert history[0]["data"] == {"event": 1}
        assert history[1]["data"] == {"event": 2}


class TestFileWatcher:
    """Test FileWatcher functionality."""

    @pytest.fixture
    def watcher(self) -> FileWatcher:
        """Create a watcher instance."""
        return FileWatcher()

    def test_watcher_initialization(self, watcher: FileWatcher) -> None:
        """Test watcher initializes correctly."""
        assert watcher.observer is not None
        assert len(watcher.watches) == 0

    def test_list_watches_empty(self, watcher: FileWatcher) -> None:
        """Test listing watches when empty."""
        watches = watcher.list_watches()
        assert watches == []
