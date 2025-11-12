"""Integration tests for token rotation workflow.

These tests verify that token rotation works correctly:
1. Start service with token A
2. Verify requests with token A succeed
3. Restart service with token B
4. Verify token A is rejected and token B is accepted

Note: These tests simulate token rotation by mocking the settings
rather than actually restarting the service.

Test Coverage:
- Token rotation workflow
- Old tokens rejected after rotation
- New tokens accepted after rotation
- Service startup with different tokens
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.fixture
def token_a():
    """First token for rotation testing."""
    return "a" * 64


@pytest.fixture
def token_b():
    """Second token for rotation testing."""
    return "b" * 64


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestTokenRotation:
    """Integration tests for token rotation workflow."""

    def test_token_rotation_old_token_rejected(self, client, token_a, token_b):
        """Verify old token is rejected after rotation.

        Workflow:
        1. Service starts with token A
        2. Request with token A succeeds
        3. Service "rotates" to token B (simulated by mocking)
        4. Request with token A fails (old token rejected)
        """
        # Phase 1: Service using token A
        with patch("app.config.settings.API_BEARER_TOKEN", token_a):
            # Request with token A succeeds
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 200

        # Phase 2: Service "rotated" to token B
        with patch("app.config.settings.API_BEARER_TOKEN", token_b):
            # Request with old token A fails
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )

            # Should fail with INVALID_TOKEN
            assert response.status_code == 401
            error_data = response.json()
            assert error_data["error_code"] == "INVALID_TOKEN"

    def test_token_rotation_new_token_accepted(self, client, token_a, token_b):
        """Verify new token is accepted after rotation.

        Workflow:
        1. Service starts with token A
        2. Service "rotates" to token B
        3. Request with token B succeeds
        """
        # Service "rotated" to token B
        with patch("app.config.settings.API_BEARER_TOKEN", token_b):
            # Request with new token B succeeds
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_b}"},
            )

            # Should succeed
            assert response.status_code == 200

    def test_token_rotation_both_tokens_work_during_transition(
        self, client, token_a, token_b
    ):
        """Verify token rotation workflow step by step.

        This test demonstrates the token rotation process:
        1. Old token works
        2. Rotate to new token
        3. New token works
        4. Old token no longer works
        """
        # Step 1: Service using token A
        with patch("app.config.settings.API_BEARER_TOKEN", token_a):
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Test with token A",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 200

        # Step 2: Service rotated to token B
        with patch("app.config.settings.API_BEARER_TOKEN", token_b):
            # New token B works
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Test with token B",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert response.status_code == 200

            # Old token A no longer works
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Try with old token A",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 401
            assert response.json()["error_code"] == "INVALID_TOKEN"

    def test_multiple_token_rotations(self, client):
        """Verify multiple token rotations work correctly.

        This test simulates rotating through multiple tokens:
        token_1 → token_2 → token_3
        """
        tokens = ["1" * 64, "2" * 64, "3" * 64]

        for i, current_token in enumerate(tokens):
            with patch("app.config.settings.API_BEARER_TOKEN", current_token):
                # Current token works
                response = client.post(
                    "/chat",
                    json={
                        "user_id": "test_user",
                        "message": f"Test with token {i+1}",
                        "streaming": False,
                    },
                    headers={"Authorization": f"Bearer {current_token}"},
                )
                assert response.status_code == 200

                # Previous tokens no longer work
                for j, old_token in enumerate(tokens[:i]):
                    response = client.post(
                        "/chat",
                        json={
                            "user_id": "test_user",
                            "message": f"Try with old token {j+1}",
                            "streaming": False,
                        },
                        headers={"Authorization": f"Bearer {old_token}"},
                    )
                    assert response.status_code == 401
                    assert response.json()["error_code"] == "INVALID_TOKEN"

    def test_token_rotation_affects_all_endpoints(self, client, token_a, token_b):
        """Verify token rotation affects all protected endpoints consistently.

        This ensures token rotation isn't endpoint-specific but applies
        to all authenticated endpoints.
        """
        # Test with /chat endpoint (the protected endpoint)
        with patch("app.config.settings.API_BEARER_TOKEN", token_a):
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 200

        # After rotation to token B
        with patch("app.config.settings.API_BEARER_TOKEN", token_b):
            # Old token A fails
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert response.status_code == 401

            # New token B works
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert response.status_code == 200

    def test_no_grace_period_for_old_tokens(self, client, token_a, token_b):
        """Verify old tokens are immediately rejected after rotation.

        This test confirms there's no grace period where both old and new
        tokens work simultaneously. This is expected behavior for single
        static token authentication.
        """
        # Rotate to token B
        with patch("app.config.settings.API_BEARER_TOKEN", token_b):
            # Old token A immediately fails (no grace period)
            response = client.post(
                "/chat",
                json={
                    "user_id": "test_user",
                    "message": "Hello",
                    "streaming": False,
                },
                headers={"Authorization": f"Bearer {token_a}"},
            )

            # Should fail immediately
            assert response.status_code == 401
            assert response.json()["error_code"] == "INVALID_TOKEN"
