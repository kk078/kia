"""Tests for FastAPI gateway."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


class TestAPIGateway:
    """Test FastAPI gateway endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_health_check(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    def test_get_status(self, client: TestClient) -> None:
        """Test status endpoint."""
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "environment" in data
        assert "services" in data

    def test_llm_route_endpoint(self, client: TestClient) -> None:
        """Test LLM route endpoint."""
        response = client.get("/api/v1/llm/route?task_type=planning")
        assert response.status_code == 200
        data = response.json()
        assert "task_type" in data
        assert "model" in data
