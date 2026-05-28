"""Task scheduler for proactive behavior."""

from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


class TaskScheduler:
    """Scheduler for proactive tasks."""

    def __init__(self) -> None:
        """Initialize the task scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.jobs: dict[str, Any] = {}

    def start(self) -> None:
        """Start the scheduler."""
        self.scheduler.start()

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown()

    def add_interval_task(
        self,
        job_id: str,
        func: Callable[..., Any],
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        **kwargs: Any,
    ) -> str:
        """Add a task that runs at regular intervals.

        Args:
            job_id: Unique job identifier
            func: Async function to execute
            seconds: Interval in seconds
            minutes: Interval in minutes
            hours: Interval in hours
            **kwargs: Additional arguments passed to func

        Returns:
            Job ID
        """
        trigger = IntervalTrigger(seconds=seconds, minutes=minutes, hours=hours)
        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs,
            replace_existing=True,
        )
        self.jobs[job_id] = job
        return job_id

    def add_cron_task(
        self,
        job_id: str,
        func: Callable[..., Any],
        cron_expression: str,
        **kwargs: Any,
    ) -> str:
        """Add a task with cron-style scheduling.

        Args:
            job_id: Unique job identifier
            func: Async function to execute
            cron_expression: Cron expression (e.g., "0 */2 * * *")
            **kwargs: Additional arguments passed to func

        Returns:
            Job ID
        """
        # Parse cron expression: minute hour day month day_of_week
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 parts")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            kwargs=kwargs,
            replace_existing=True,
        )
        self.jobs[job_id] = job
        return job_id

    def remove_task(self, job_id: str) -> bool:
        """Remove a scheduled task.

        Args:
            job_id: Job identifier

        Returns:
            True if removed, False if not found
        """
        if job_id in self.jobs:
            self.scheduler.remove_job(job_id)
            del self.jobs[job_id]
            return True
        return False

    def get_task_info(self, job_id: str) -> dict[str, Any] | None:
        """Get information about a scheduled task.

        Args:
            job_id: Job identifier

        Returns:
            Task info dict or None
        """
        job = self.jobs.get(job_id)
        if not job:
            return None

        return {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        """List all scheduled tasks."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": (
                    job.next_run_time.isoformat()
                    if hasattr(job, "next_run_time") and job.next_run_time
                    else None
                ),
                "trigger": str(job.trigger),
            }
            for job in self.jobs.values()
        ]
