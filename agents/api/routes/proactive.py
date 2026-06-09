"""Proactive behavior API: scheduled prompts and file watching that feed memory.

This wires the (previously library-only) brain_proactive package into the
runtime. Two proactive primitives are exposed:

- Scheduled prompts: run an LLM prompt on an interval or cron schedule and
  store each result as an episodic memory (source ``proactive:<job_id>``), so
  KIA accumulates context without being asked.
- File watches: record file-change events under a directory as episodic
  memories, so "what changed recently" is answerable from memory.

Schedules and watches are in-process and not persisted across restarts; the
status endpoint is the source of truth for what is currently active.
"""

from functools import partial
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from brain_core.persona import KIA_SYSTEM
from brain_proactive.scheduler import TaskScheduler
from brain_proactive.watcher import FileWatcher

router = APIRouter(prefix="/api/v1/proactive", tags=["proactive"])

_scheduler: TaskScheduler | None = None
_watcher: FileWatcher | None = None


def _get_scheduler() -> TaskScheduler:
    """Lazily create + start the process-wide scheduler (needs a running loop)."""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
        _scheduler.start()
    return _scheduler


def _get_watcher() -> FileWatcher:
    """Lazily create the process-wide file watcher."""
    global _watcher
    if _watcher is None:
        _watcher = FileWatcher()
    return _watcher


def shutdown_proactive() -> None:
    """Stop scheduler + watcher (app shutdown hook). Safe to call when idle.

    Must run on the loop the scheduler started on — main.py registers this as
    a shutdown event handler, which guarantees that in both uvicorn and tests.
    """
    global _scheduler, _watcher
    if _scheduler is not None:
        _scheduler.stop()
        _scheduler = None
    if _watcher is not None:
        _watcher.stop()
        _watcher = None


async def _store_episode(content: str, context: dict[str, Any]) -> None:
    """Persist one proactive observation to episodic memory."""
    from brain_memory.memory_native import make_episodic_memory
    from brain_memory.models import Episode

    em = make_episodic_memory()
    try:
        await em.store_episode(Episode(content=content, context=context))
    finally:
        await em.close()


async def run_prompt_job(job_id: str, prompt: str, task_type: str = "simple") -> None:
    """Execute one scheduled prompt and store the result as an episode.

    Never raises: a failing provider must not kill the scheduler loop.
    """
    try:
        from brain_core.fallback import resilient_generate
        from brain_core.llm import LLMRouter

        text, model_used = await resilient_generate(
            LLMRouter(), prompt, task_type=task_type, system=KIA_SYSTEM
        )
        await _store_episode(
            text,
            {"source": f"proactive:{job_id}", "prompt": prompt, "model": model_used},
        )
    except Exception as e:  # noqa: BLE001 - scheduler jobs must be crash-proof
        print(f"[proactive] job {job_id} failed: {type(e).__name__}: {e}")


async def on_file_event(
    event_type: str, src_path: str, dest_path: str | None = None, **_: Any
) -> None:
    """Record a file-system change as an episodic memory. Never raises."""
    try:
        desc = f"File {event_type}: {src_path}" + (f" -> {dest_path}" if dest_path else "")
        await _store_episode(
            desc,
            {"source": "proactive:watch", "event": event_type, "path": src_path},
        )
    except Exception as e:  # noqa: BLE001 - watcher callbacks must be crash-proof
        print(f"[proactive] watch event failed: {type(e).__name__}: {e}")


class ScheduledPrompt(BaseModel):
    """A prompt KIA runs on a schedule. Exactly one of every_minutes/cron."""

    job_id: str
    prompt: str
    task_type: str = "simple"
    every_minutes: int | None = None
    cron: str | None = None  # "minute hour day month day_of_week"


class WatchRequest(BaseModel):
    """Directory to watch; file events become episodic memories."""

    path: str
    recursive: bool = True


@router.get("/status")
async def proactive_status() -> dict[str, Any]:
    """Current scheduled tasks and active watches (in-process state)."""
    tasks = _scheduler.list_tasks() if _scheduler else []
    watches = _watcher.list_watches() if _watcher else []
    return {
        "scheduler_running": _scheduler is not None,
        "tasks": tasks,
        "watches": watches,
    }


@router.post("/tasks")
async def schedule_prompt(body: ScheduledPrompt) -> dict[str, Any]:
    """Schedule a recurring prompt. Results land in episodic memory."""
    if (body.every_minutes is None) == (body.cron is None):
        raise HTTPException(status_code=422, detail="Provide exactly one of every_minutes or cron")
    if body.every_minutes is not None and body.every_minutes < 1:
        raise HTTPException(status_code=422, detail="every_minutes must be >= 1")

    scheduler = _get_scheduler()
    # partial() instead of scheduler kwargs: the scheduler's own job_id parameter
    # would collide with the job function's job_id argument.
    job = partial(run_prompt_job, body.job_id, body.prompt, body.task_type)
    if body.every_minutes is not None:
        scheduler.add_interval_task(body.job_id, job, minutes=body.every_minutes)
    else:
        try:
            scheduler.add_cron_task(body.job_id, job, cron_expression=body.cron or "")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    info = scheduler.get_task_info(body.job_id)
    return {"status": "scheduled", "task": info}


@router.delete("/tasks/{job_id}")
async def remove_task(job_id: str) -> dict[str, str]:
    """Remove a scheduled prompt."""
    if _scheduler is None or not _scheduler.remove_task(job_id):
        raise HTTPException(status_code=404, detail="task not found")
    return {"status": "removed", "job_id": job_id}


@router.post("/watch")
async def watch_directory(body: WatchRequest) -> dict[str, str]:
    """Watch a directory; file changes are recorded to episodic memory."""
    try:
        watch_id = await _get_watcher().watch(body.path, on_file_event, body.recursive)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "watching", "watch_id": watch_id, "path": body.path}


@router.delete("/watch/{watch_id}")
async def unwatch_directory(watch_id: str) -> dict[str, str]:
    """Stop watching a directory."""
    if _watcher is None or not _watcher.unwatch(watch_id):
        raise HTTPException(status_code=404, detail="watch not found")
    return {"status": "unwatched", "watch_id": watch_id}
