"""Pytest configuration and fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis client for unit tests."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def mock_weaviate() -> MagicMock:
    """Mock Weaviate client for unit tests."""
    client = MagicMock()
    collection = MagicMock()
    client.collections.get.return_value = collection
    return client


@pytest.fixture
def mock_falkordb() -> MagicMock:
    """Mock FalkorDB client for unit tests."""
    db = MagicMock()
    graph = MagicMock()
    db.select_graph.return_value = graph
    return db


@pytest.fixture
def mock_memory_store() -> AsyncMock:
    """Mock MemoryStore for unit tests."""
    store = AsyncMock()
    store.episodic = AsyncMock()
    store.episodic.retrieve_recent = AsyncMock(return_value=[])
    store.semantic = AsyncMock()
    store.semantic.get_entity = AsyncMock(return_value=None)
    store.semantic.store_entity = AsyncMock()
    store.semantic.get_patterns = AsyncMock(return_value=[])
    return store
