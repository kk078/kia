"""n8n workflow bridge for automation integration."""

from brain_n8n.client import N8NClient
from brain_n8n.workflow import WorkflowBuilder

__all__ = [
    "N8NClient",
    "WorkflowBuilder",
]
