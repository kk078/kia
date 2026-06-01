"""Host command execution (confirmation-gated).

KIA plans shell commands for a task (no execution), the user approves them in the UI,
and approved commands are sent to the host runner (``host_runner/runner.py``) which runs
them on the real machine. The backend never executes a command the user has not approved.
"""
