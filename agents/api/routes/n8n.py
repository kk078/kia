"""n8n workflow API: expose the brain_n8n bridge over REST.

Thin pass-through to the n8n instance configured via N8N_URL / N8N_API_KEY.
The client already degrades gracefully (empty lists / error dicts) when n8n
is unreachable, so these endpoints never take the API down with them.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from brain_n8n.client import N8NClient

router = APIRouter(prefix="/api/v1/n8n", tags=["n8n"])


class WorkflowRun(BaseModel):
    """Input payload for a workflow execution."""

    data: dict[str, Any] = {}


@router.get("/workflows")
async def list_workflows() -> dict[str, Any]:
    """List workflows known to the configured n8n instance."""
    client = N8NClient()
    try:
        workflows = await client.list_workflows()
        return {"workflows": workflows, "count": len(workflows)}
    finally:
        await client.close()


@router.post("/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, body: WorkflowRun) -> dict[str, Any]:
    """Execute a workflow with the given input data."""
    client = N8NClient()
    try:
        result = await client.execute_workflow(workflow_id, body.data)
        if "error" in result:
            raise HTTPException(status_code=502, detail=result["error"])
        return result
    finally:
        await client.close()


@router.post("/workflows/{workflow_id}/activate")
async def activate_workflow(workflow_id: str) -> dict[str, str]:
    """Activate a workflow."""
    client = N8NClient()
    try:
        if not await client.activate_workflow(workflow_id):
            raise HTTPException(status_code=502, detail="activation failed")
        return {"status": "activated", "workflow_id": workflow_id}
    finally:
        await client.close()


@router.post("/workflows/{workflow_id}/deactivate")
async def deactivate_workflow(workflow_id: str) -> dict[str, str]:
    """Deactivate a workflow."""
    client = N8NClient()
    try:
        if not await client.deactivate_workflow(workflow_id):
            raise HTTPException(status_code=502, detail="deactivation failed")
        return {"status": "deactivated", "workflow_id": workflow_id}
    finally:
        await client.close()
