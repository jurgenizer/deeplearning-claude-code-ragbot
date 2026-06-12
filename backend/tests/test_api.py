import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

RAG_MODULE = "app.rag_system"


@pytest.fixture
def mock_rag():
    """Patch the global rag_system in app.py so no real ChromaDB or API is used."""
    mock = MagicMock()
    mock.query.return_value = (
        "This is the answer.",
        [{"label": "Source 1", "url": "https://example.com"}],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    mock.session_manager.create_session.return_value = "session_1"
    mock.session_manager.clear_session = MagicMock()
    return mock


@pytest.fixture
def client(mock_rag):
    with patch(RAG_MODULE, mock_rag):
        import app as application

        yield TestClient(application.app)


# --- POST /api/query ---


def test_query_returns_200_with_answer(client):
    response = client.post("/api/query", json={"query": "What is RAG?"})
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert "session_id" in body
    assert "sources" in body


def test_query_without_session_id_creates_one(client):
    response = client.post("/api/query", json={"query": "Hello"})
    assert response.status_code == 200
    assert response.json()["session_id"] == "session_1"


def test_query_with_session_id_uses_it(client, mock_rag):
    mock_rag.query.return_value = ("Answer.", [])
    response = client.post(
        "/api/query", json={"query": "Hi", "session_id": "session_42"}
    )
    assert response.status_code == 200
    assert response.json()["session_id"] == "session_42"
    # Ensure query was called with the provided session_id
    mock_rag.query.assert_called_once_with("Hi", "session_42")


def test_query_exception_returns_500(client, mock_rag):
    mock_rag.query.side_effect = RuntimeError("something broke")
    response = client.post("/api/query", json={"query": "fail"})
    assert response.status_code == 500


# --- GET /api/courses ---


def test_courses_endpoint_returns_stats(client):
    response = client.get("/api/courses")
    assert response.status_code == 200
    body = response.json()
    assert body["total_courses"] == 2
    assert "Course A" in body["course_titles"]


def test_courses_endpoint_exception_returns_500(client, mock_rag):
    mock_rag.get_course_analytics.side_effect = RuntimeError("analytics broken")
    response = client.get("/api/courses")
    assert response.status_code == 500


# --- DELETE /api/session/{session_id} ---


def test_delete_session_returns_200(client, mock_rag):
    response = client.delete("/api/session/session_1")
    assert response.status_code == 200
    assert response.json() == {"status": "cleared"}
    mock_rag.session_manager.clear_session.assert_called_once_with("session_1")
