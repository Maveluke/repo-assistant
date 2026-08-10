import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture
def issue_page():
    """Build a page of N minimal issue payloads."""

    def _build(n: int):
        return [{"number": i, "title": f"issue {i}"} for i in range(n)]

    return _build
