"""File watcher for proactive file monitoring."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class FileWatcherHandler(FileSystemEventHandler):
    """Handler for file system events."""

    def __init__(self, callback: Callable[..., Any], event_loop: asyncio.AbstractEventLoop) -> None:
        """Initialize the handler.

        Args:
            callback: Async callback function
            event_loop: Event loop to run callback in
        """
        self.callback = callback
        self.event_loop = event_loop

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event."""
        if event.is_directory:
            return

        # Run callback in event loop
        asyncio.run_coroutine_threadsafe(
            self.callback(
                event_type=event.event_type,
                src_path=event.src_path,
                dest_path=getattr(event, "dest_path", None),
            ),
            self.event_loop,
        )


class FileWatcher:
    """Watcher for file system changes."""

    def __init__(self) -> None:
        """Initialize the file watcher."""
        self.observer = Observer()
        self.watches: dict[str, Any] = {}

    async def watch(
        self,
        path: str,
        callback: Callable[..., Any],
        recursive: bool = True,
        patterns: list[str] | None = None,
    ) -> str:
        """Watch a directory for changes.

        Args:
            path: Directory path to watch
            callback: Async callback(event_type, src_path, dest_path)
            recursive: Watch subdirectories
            patterns: File patterns to watch (e.g., ["*.py", "*.md"])

        Returns:
            Watch ID
        """
        path_obj = Path(path).resolve()
        if not path_obj.exists():
            raise ValueError(f"Path does not exist: {path}")

        loop = asyncio.get_event_loop()
        handler = FileWatcherHandler(callback, loop)

        watch = self.observer.schedule(handler, str(path_obj), recursive=recursive)
        watch_id = f"watch_{len(self.watches)}"
        self.watches[watch_id] = watch

        if not self.observer.is_alive():
            self.observer.start()

        return watch_id

    def unwatch(self, watch_id: str) -> bool:
        """Stop watching a directory.

        Args:
            watch_id: Watch identifier

        Returns:
            True if stopped, False if not found
        """
        watch = self.watches.get(watch_id)
        if watch:
            self.observer.unschedule(watch)
            del self.watches[watch_id]
            return True
        return False

    def stop(self) -> None:
        """Stop all watchers."""
        self.observer.stop()
        self.observer.join()
        self.watches.clear()

    def list_watches(self) -> list[dict[str, Any]]:
        """List all active watches.

        Returns:
            List of watch info dicts
        """
        return [
            {
                "id": watch_id,
                "path": str(watch.path),
            }
            for watch_id, watch in self.watches.items()
        ]
