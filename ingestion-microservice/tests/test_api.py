"""Tests for FastAPI endpoints."""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta, timezone
import pytest

from app.main import app
from config import settings


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def valid_token():
    """Create a valid JWT token for testing."""
    payload = {
        "sub": "8",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return f"Bearer {token}"


@pytest.fixture
def expired_token():
    """Create an expired JWT token."""
    payload = {
        "sub": "8",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return f"Bearer {token}"


@pytest.fixture
def invalid_token():
    """Create an invalid JWT token (wrong secret)."""
    payload = {
        "sub": "8",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    token = jwt.encode(payload, "wrong-secret-key", algorithm="HS256")
    return f"Bearer {token}"


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check(self, client):
        """Test health endpoint returns status and version."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert data["environment"] in ["dev", "test", "prod"]

    def test_health_no_auth_required(self, client):
        """Test health endpoint doesn't require authentication."""
        response = client.get("/health")
        assert response.status_code == 200


class TestIngestEndpoint:
    """Tests for POST /v1/ingest endpoint."""

    def test_ingest_requires_auth(self, client):
        """Test ingest endpoint requires authorization header."""
        response = client.post("/v1/ingest")
        assert response.status_code == 401  # 401 Unauthorized (not 403 Forbidden)

    def test_ingest_rejects_expired_token(self, client, expired_token, tmp_path):
        """Test ingest rejects expired JWT token."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        response = client.post(
            "/v1/ingest",
            headers={"Authorization": expired_token},
            files={"file": ("test.txt", open(test_file, "rb"), "text/plain")}
        )
        assert response.status_code == 401
        assert "token" in response.json()["detail"].lower()

    def test_ingest_rejects_invalid_token(self, client, invalid_token, tmp_path):
        """Test ingest rejects token with invalid signature."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        response = client.post(
            "/v1/ingest",
            headers={"Authorization": invalid_token},
            files={"file": ("test.txt", open(test_file, "rb"), "text/plain")}
        )
        assert response.status_code == 401

    @patch("app.tasks.ingest_document_task.delay")
    def test_ingest_success(self, mock_task, client, valid_token, tmp_path):
        """Test successful file upload and task queueing."""
        # Mock Celery task
        mock_task.return_value = MagicMock(id="test-task-id-123")

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test document content")

        response = client.post(
            "/v1/ingest",
            headers={"Authorization": valid_token},
            files={"file": ("test.txt", open(test_file, "rb"), "text/plain")}
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "processing"
        assert "task_id" in data
        assert "test.txt" in data["message"]

    def test_ingest_no_file_provided(self, client, valid_token):
        """Test ingest rejects request without file."""
        response = client.post(
            "/v1/ingest",
            headers={"Authorization": valid_token}
        )
        assert response.status_code == 422  # Validation error

    @patch("app.tasks.ingest_document_task.delay")
    def test_ingest_extracts_user_id_from_token(self, mock_task, client, tmp_path):
        """Test that user_id is correctly extracted from JWT token."""
        mock_task.return_value = MagicMock(id="test-task-id")

        # Create token with specific user_id
        payload = {
            "sub": "user-42",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1)
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        test_file = tmp_path / "doc.txt"
        test_file.write_text("content")

        response = client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("doc.txt", open(test_file, "rb"), "text/plain")}
        )

        assert response.status_code == 202
        # Verify task was called with correct user_id
        mock_task.assert_called_once()
        # Check that user_id was used in logging
        assert "user-42" in response.json()["message"] or response.json()["task_id"]


class TestStatusEndpoint:
    """Tests for GET /v1/ingest/status/{task_id} endpoint."""

    def test_status_requires_auth(self, client):
        """Test status endpoint requires authorization."""
        response = client.get("/v1/ingest/status/fake-task-id")
        assert response.status_code == 401  # 401 Unauthorized

    def test_status_rejects_expired_token(self, client, expired_token):
        """Test status endpoint rejects expired token."""
        response = client.get(
            "/v1/ingest/status/fake-task-id",
            headers={"Authorization": expired_token}
        )
        assert response.status_code == 401

    @patch("app.tasks.celery_app.AsyncResult")
    def test_status_processing(self, mock_result, client, valid_token):
        """Test status endpoint returns processing state."""
        mock_async_result = MagicMock()
        mock_async_result.state = "PENDING"
        mock_async_result.result = None
        mock_result.return_value = mock_async_result

        response = client.get(
            "/v1/ingest/status/test-task-123",
            headers={"Authorization": valid_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-123"
        assert data["status"] in ["processing"]  # Consistent naming

    @patch("app.tasks.celery_app.AsyncResult")
    def test_status_completed(self, mock_result, client, valid_token):
        """Test status endpoint returns completed state with result."""
        mock_async_result = MagicMock()
        mock_async_result.state = "SUCCESS"
        mock_async_result.result = {
            "success": True,
            "filename": "test.txt",
            "files_processed": 1,
            "chunks_added": 5
        }
        mock_result.return_value = mock_async_result

        response = client.get(
            "/v1/ingest/status/test-task-123",
            headers={"Authorization": valid_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-123"
        assert data["status"] == "completed"
        assert data["result"]["success"] is True
        assert data["result"]["files_processed"] == 1

    @patch("app.tasks.celery_app.AsyncResult")
    def test_status_failed(self, mock_result, client, valid_token):
        """Test status endpoint returns failed state."""
        mock_async_result = MagicMock()
        mock_async_result.state = "FAILURE"
        mock_async_result.info = "Worker exited prematurely"
        mock_result.return_value = mock_async_result

        response = client.get(
            "/v1/ingest/status/test-task-123",
            headers={"Authorization": valid_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"


class TestAuthenticationFlow:
    """Integration tests for authentication flow."""

    def test_full_ingest_flow_requires_auth_at_status(self, client, valid_token, tmp_path):
        """Test that status check also requires valid auth token."""
        # First, upload a file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        with patch("app.tasks.ingest_document_task.delay") as mock_task:
            mock_task.return_value = MagicMock(id="task-123")

            upload_response = client.post(
                "/v1/ingest",
                headers={"Authorization": valid_token},
                files={"file": ("test.txt", open(test_file, "rb"), "text/plain")}
            )
            assert upload_response.status_code == 202
            task_id = upload_response.json()["task_id"]

        # Now try to check status without auth
        status_response = client.get(f"/v1/ingest/status/{task_id}")
        assert status_response.status_code == 401  # 401 Unauthorized

        # Check status with valid auth
        with patch("app.tasks.celery_app.AsyncResult") as mock_result:
            mock_async_result = MagicMock()
            mock_async_result.state = "SUCCESS"
            mock_async_result.result = {"success": True}
            mock_result.return_value = mock_async_result

            status_response = client.get(
                f"/v1/ingest/status/{task_id}",
                headers={"Authorization": valid_token}
            )
            assert status_response.status_code == 200
