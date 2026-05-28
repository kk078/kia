"""Tests for n8n workflow bridge."""

import pytest

from brain_n8n.client import N8NClient
from brain_n8n.workflow import WorkflowBuilder


class TestN8NClient:
    """Test n8n client functionality."""

    @pytest.fixture
    def client(self) -> N8NClient:
        """Create n8n client instance."""
        return N8NClient(base_url="http://localhost:5678", api_key="test_key")

    @pytest.mark.asyncio
    async def test_client_initialization(self, client: N8NClient) -> None:
        """Test client initializes correctly."""
        assert client.base_url == "http://localhost:5678"
        assert client.api_key == "test_key"

    @pytest.mark.asyncio
    async def test_list_workflows_connection_error(self, client: N8NClient) -> None:
        """Test listing workflows with connection error."""
        workflows = await client.list_workflows()
        assert workflows == []

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, client: N8NClient) -> None:
        """Test getting non-existent workflow."""
        workflow = await client.get_workflow("nonexistent_id")
        assert workflow is None

    @pytest.mark.asyncio
    async def test_close_client(self, client: N8NClient) -> None:
        """Test closing client."""
        await client.close()


class TestWorkflowBuilder:
    """Test workflow builder functionality."""

    def test_create_empty_workflow(self) -> None:
        """Test creating an empty workflow."""
        builder = WorkflowBuilder("Test Workflow")
        workflow = builder.build()

        assert workflow["name"] == "Test Workflow"
        assert workflow["nodes"] == []
        assert workflow["connections"] == {}
        assert workflow["active"] is False

    def test_add_node(self) -> None:
        """Test adding a node."""
        builder = WorkflowBuilder("Test")
        builder.add_node(
            node_type="n8n-nodes-base.httpRequest",
            name="HTTP Request",
            parameters={"url": "https://example.com"},
        )

        workflow = builder.build()
        assert len(workflow["nodes"]) == 1
        assert workflow["nodes"][0]["name"] == "HTTP Request"

    def test_add_webhook_trigger(self) -> None:
        """Test adding webhook trigger."""
        builder = WorkflowBuilder("Test")
        builder.add_webhook_trigger(path="test-webhook", method="POST")

        workflow = builder.build()
        assert len(workflow["nodes"]) == 1
        assert workflow["nodes"][0]["type"] == "n8n-nodes-base.webhook"

    def test_add_http_request(self) -> None:
        """Test adding HTTP request node."""
        builder = WorkflowBuilder("Test")
        builder.add_http_request(
            name="API Call",
            url="https://api.example.com/data",
            method="POST",
        )

        workflow = builder.build()
        assert len(workflow["nodes"]) == 1
        assert workflow["nodes"][0]["parameters"]["url"] == "https://api.example.com/data"

    def test_add_code_node(self) -> None:
        """Test adding code node."""
        builder = WorkflowBuilder("Test")
        builder.add_code_node(
            name="Process Data",
            code="return items;",
            language="javaScript",
        )

        workflow = builder.build()
        assert len(workflow["nodes"]) == 1
        assert workflow["nodes"][0]["parameters"]["jsCode"] == "return items;"

    def test_connect_nodes(self) -> None:
        """Test connecting nodes."""
        builder = WorkflowBuilder("Test")
        builder.add_webhook_trigger()
        builder.add_http_request(name="HTTP", url="https://example.com")
        builder.connect("Webhook", "HTTP")

        workflow = builder.build()
        assert "Webhook" in workflow["connections"]
        assert len(workflow["connections"]["Webhook"]["main"][0]) == 1

    def test_create_simple_webhook_workflow(self) -> None:
        """Test creating simple webhook workflow."""
        workflow = WorkflowBuilder.create_simple_webhook_workflow(
            name="Simple Workflow",
            webhook_path="simple",
            target_url="https://api.example.com/webhook",
        )

        assert workflow["name"] == "Simple Workflow"
        assert len(workflow["nodes"]) == 2
        assert "Webhook" in workflow["connections"]

    def test_chaining(self) -> None:
        """Test method chaining."""
        builder = WorkflowBuilder("Chain Test")
        result = (
            builder.add_webhook_trigger()
            .add_http_request(name="HTTP", url="https://example.com")
            .connect("Webhook", "HTTP")
        )

        assert result is builder
        workflow = builder.build()
        assert len(workflow["nodes"]) == 2
