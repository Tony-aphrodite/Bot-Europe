"""
Task scheduler for automated execution
"""

from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .logger import setup_logger

logger = setup_logger(__name__)


class TaskScheduler:
    """
    Manages scheduled execution of bot tasks.
    """

    def __init__(self, timezone: str = "Europe/Madrid"):
        """
        Initialize task scheduler.

        Args:
            timezone: Timezone for scheduling
        """
        self.timezone = timezone
        self.scheduler = BackgroundScheduler(timezone=timezone)
        self._jobs = {}

    def add_daily_task(
        self,
        task_id: str,
        func: Callable,
        hour: int = 9,
        minute: int = 0,
        **kwargs,
    ) -> str:
        """
        Add a daily scheduled task.

        Args:
            task_id: Unique identifier for the task
            func: Function to execute
            hour: Hour to run (0-23)
            minute: Minute to run (0-59)
            **kwargs: Additional arguments to pass to the function

        Returns:
            Job ID
        """
        trigger = CronTrigger(hour=hour, minute=minute, timezone=self.timezone)

        job = self.scheduler.add_job(
            func,
            trigger=trigger,
            id=task_id,
            name=task_id,
            kwargs=kwargs,
            replace_existing=True,
        )

        self._jobs[task_id] = job
        logger.info(f"Scheduled daily task '{task_id}' at {hour:02d}:{minute:02d}")
        return job.id

    def add_interval_task(
        self,
        task_id: str,
        func: Callable,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        **kwargs,
    ) -> str:
        """
        Add an interval-based task.

        Args:
            task_id: Unique identifier for the task
            func: Function to execute
            hours: Interval hours
            minutes: Interval minutes
            seconds: Interval seconds
            **kwargs: Additional arguments to pass to the function

        Returns:
            Job ID
        """
        job = self.scheduler.add_job(
            func,
            "interval",
            id=task_id,
            name=task_id,
            hours=hours,
            minutes=minutes,
            seconds=seconds,
            kwargs=kwargs,
            replace_existing=True,
        )

        self._jobs[task_id] = job
        logger.info(
            f"Scheduled interval task '{task_id}' every {hours}h {minutes}m {seconds}s"
        )
        return job.id

    def add_one_time_task(
        self,
        task_id: str,
        func: Callable,
        run_date: datetime,
        **kwargs,
    ) -> str:
        """
        Add a one-time scheduled task.

        Args:
            task_id: Unique identifier for the task
            func: Function to execute
            run_date: Date and time to run
            **kwargs: Additional arguments to pass to the function

        Returns:
            Job ID
        """
        job = self.scheduler.add_job(
            func,
            "date",
            id=task_id,
            name=task_id,
            run_date=run_date,
            kwargs=kwargs,
            replace_existing=True,
        )

        self._jobs[task_id] = job
        logger.info(f"Scheduled one-time task '{task_id}' at {run_date}")
        return job.id

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a scheduled task.

        Args:
            task_id: Task identifier to remove

        Returns:
            True if removed successfully
        """
        try:
            self.scheduler.remove_job(task_id)
            self._jobs.pop(task_id, None)
            logger.info(f"Removed task: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove task {task_id}: {e}")
            return False

    def get_task_info(self, task_id: str) -> Optional[dict]:
        """
        Get information about a scheduled task.

        Args:
            task_id: Task identifier

        Returns:
            Task information dict or None
        """
        job = self._jobs.get(task_id)
        if not job:
            return None

        return {
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time,
            "trigger": str(job.trigger),
        }

    def list_tasks(self) -> list:
        """
        List all scheduled tasks.

        Returns:
            List of task information dicts
        """
        return [self.get_task_info(task_id) for task_id in self._jobs.keys()]

    def start(self) -> None:
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def pause(self) -> None:
        """Pause all jobs."""
        self.scheduler.pause()
        logger.info("Scheduler paused")

    def resume(self) -> None:
        """Resume all jobs."""
        self.scheduler.resume()
        logger.info("Scheduler resumed")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
