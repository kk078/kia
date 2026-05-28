"""n8n API client for workflow management."""

from typing import Any

import httpx

from brain_core.config import settings


class N8NClient:
    """Client for n8n workflow automation platform."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize n8n client.

        Args:
            base_url: n8n instance URL (default: from settings)
            api_key: n8n API key (default: from settings)
        """
        self.base_url = base_url or settings.n8n_url
        self.api_key = api_key or settings.n8n_api_key
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"X-N8N-API-KEY": self.api_key} if self.api_key else {},
            timeout=30.0,
        )

    async def list_workflows(self) -> list[dict[str, Any]]:
        """List all workflows.

        Returns:
            List of workflow dicts
        """
        try:
            response = await self.client.get("/api/v1/workflows")
            response.raise_for_status()
            data: list[dict[str, Any]] = response.json().get("data", [])
            return data
        except httpx.HTTPError:
            return []

    async def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Get a specific workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow dict or None
        """
        try:
            response = await self.client.get(f"/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPError:
            return None

    async def execute_workflow(
        self, workflow_id: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a workflow.

        Args:
            workflow_id: Workflow ID
            data: Input data for the workflow

        Returns:
            Execution result dict
        """
        try:
            payload = {"data": data or {}}
            response = await self.client.post(
                f"/api/v1/workflows/{workflow_id}/run",
                json=payload,
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPError as e:
            return {"error": str(e), "workflow_id": workflow_id}

    async def create_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """Create a new workflow.

        Args:
            workflow: Workflow definition dict

        Returns:
            Created workflow dict
        """
        try:
            response = await self.client.post("/api/v1/workflows", json=workflow)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPError as e:
            return {"error": str(e)}

    async def update_workflow(self, workflow_id: str, workflow: dict[str, Any]) -> dict[str, Any]:
        """Update an existing workflow.

        Args:
            workflow_id: Workflow ID
            workflow: Updated workflow definition

        Returns:
            Updated workflow dict
        """
        try:
            response = await self.client.put(
                f"/api/v1/workflows/{workflow_id}",
                json=workflow,
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPError as e:
            return {"error": str(e)}

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            response = await self.client.delete(f"/api/v1/workflows/{workflow_id}")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def activate_workflow(self, workflow_id: str) -> bool:
        """Activate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if activated, False otherwise
        """
        try:
            response = await self.client.post(f"/api/v1/workflows/{workflow_id}/activate")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def deactivate_workflow(self, workflow_id: str) -> bool:
        """Deactivate a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deactivated, False otherwise
        """
        try:
            response = await self.client.post(f"/api/v1/workflows/{workflow_id}/deactivate")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
