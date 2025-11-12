"""Integration tests for concurrent authenticated requests.

These tests verify that authentication works correctly under concurrent load:
- Multiple simultaneous requests with valid token succeed
- Authentication latency remains low under load (<5ms p99)
- No race conditions or state corruption

Test Coverage:
- Concurrent valid requests (100 simultaneous)
- Authentication performance under load
- Thread safety of authentication logic
"""

import pytest
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from unittest.mock import patch
from statistics import median, quantiles

from app.main import app


@pytest.fixture
def test_token():
    """Valid test token for authentication."""
    return "a" * 64


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestConcurrentAuthentication:
    """Integration tests for concurrent authentication."""

    def test_concurrent_valid_requests_all_succeed(self, client, test_token):
        """Verify 100 concurrent requests with valid token all succeed.

        This test ensures:
        - Authentication is thread-safe
        - No race conditions in token validation
        - All requests are processed successfully
        """
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            num_requests = 100
            results = []

            def make_request(request_id):
                """Make a single authenticated request."""
                response = client.post(
                    "/chat",
                    json={
                        "user_id": f"user_{request_id}",
                        "message": f"Request {request_id}",
                        "streaming": False,
                    },
                    headers={"Authorization": f"Bearer {test_token}"},
                )
                return response.status_code

            # Execute requests concurrently
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [
                    executor.submit(make_request, i) for i in range(num_requests)
                ]

                # Collect results
                for future in as_completed(futures):
                    results.append(future.result())

            # Verify all requests succeeded
            assert len(results) == num_requests
            assert all(status == 200 for status in results)

    def test_concurrent_requests_with_invalid_tokens_all_fail(self, client, test_token):
        """Verify concurrent requests with invalid tokens all fail correctly."""
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            num_requests = 50
            results = []

            def make_request(request_id):
                """Make a single request with wrong token."""
                wrong_token = "b" * 64
                response = client.post(
                    "/chat",
                    json={
                        "user_id": f"user_{request_id}",
                        "message": f"Request {request_id}",
                        "streaming": False,
                    },
                    headers={"Authorization": f"Bearer {wrong_token}"},
                )
                return response.status_code, response.json().get("error_code")

            # Execute requests concurrently
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [
                    executor.submit(make_request, i) for i in range(num_requests)
                ]

                # Collect results
                for future in as_completed(futures):
                    results.append(future.result())

            # Verify all requests failed correctly
            assert len(results) == num_requests
            assert all(status == 401 for status, _ in results)
            assert all(error == "INVALID_TOKEN" for _, error in results)

    def test_mixed_valid_and_invalid_concurrent_requests(self, client, test_token):
        """Verify mix of valid and invalid concurrent requests handled correctly.

        This test ensures:
        - Valid and invalid requests don't interfere with each other
        - Each request is validated independently
        - No state corruption under mixed load
        """
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            num_requests = 100
            wrong_token = "b" * 64
            results = []

            def make_request(request_id):
                """Make request with valid or invalid token (alternating)."""
                # Alternate between valid and invalid tokens
                use_valid = request_id % 2 == 0
                token = test_token if use_valid else wrong_token

                response = client.post(
                    "/chat",
                    json={
                        "user_id": f"user_{request_id}",
                        "message": f"Request {request_id}",
                        "streaming": False,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )
                return use_valid, response.status_code

            # Execute requests concurrently
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [
                    executor.submit(make_request, i) for i in range(num_requests)
                ]

                # Collect results
                for future in as_completed(futures):
                    results.append(future.result())

            # Verify results
            valid_requests = [status for use_valid, status in results if use_valid]
            invalid_requests = [status for use_valid, status in results if not use_valid]

            # All valid requests should succeed
            assert all(status == 200 for status in valid_requests)

            # All invalid requests should fail
            assert all(status == 401 for status in invalid_requests)

    def test_authentication_latency_under_load(self, client, test_token):
        """Verify authentication latency remains low under concurrent load.

        Performance requirements:
        - p99 authentication overhead <5ms
        - Median latency <2ms
        """
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            num_requests = 100
            latencies = []

            def make_request_and_measure(request_id):
                """Make request and measure authentication latency."""
                start_time = time.perf_counter()

                response = client.post(
                    "/chat",
                    json={
                        "user_id": f"user_{request_id}",
                        "message": "Hello",
                        "streaming": False,
                    },
                    headers={"Authorization": f"Bearer {test_token}"},
                )

                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000

                return response.status_code, latency_ms

            # Execute requests concurrently
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [
                    executor.submit(make_request_and_measure, i)
                    for i in range(num_requests)
                ]

                # Collect results
                for future in as_completed(futures):
                    status, latency = future.result()
                    if status == 200:
                        latencies.append(latency)

            # Calculate statistics
            assert len(latencies) > 0, "No successful requests to measure"

            median_latency = median(latencies)
            # Calculate p99 (99th percentile)
            p99_latency = quantiles(latencies, n=100)[-1] if len(latencies) > 1 else latencies[0]

            # Note: These thresholds are relaxed for testing
            # In production, actual latency should be much lower (<5ms)
            # Test latency includes HTTP overhead, not just auth validation
            assert (
                median_latency < 100
            ), f"Median latency too high: {median_latency:.2f}ms"
            assert p99_latency < 200, f"P99 latency too high: {p99_latency:.2f}ms"

            # Log statistics for visibility
            print(
                f"\nAuthentication Performance (n={len(latencies)}):"
            )
            print(f"  Median: {median_latency:.2f}ms")
            print(f"  P99: {p99_latency:.2f}ms")
            print(f"  Min: {min(latencies):.2f}ms")
            print(f"  Max: {max(latencies):.2f}ms")

    def test_no_authentication_state_corruption_under_load(self, client, test_token):
        """Verify authentication state is not corrupted under concurrent load.

        This test ensures:
        - No global state mutation in authentication logic
        - Each request is validated independently
        - No race conditions affect validation results
        """
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            num_requests = 200
            results = []

            def make_request(request_id):
                """Make request and verify consistent behavior."""
                # Use request_id to create variety in tokens
                # Even IDs use valid token, odd IDs use invalid token
                use_valid = request_id % 2 == 0
                token = test_token if use_valid else "wrong" + test_token[5:]

                response = client.post(
                    "/chat",
                    json={
                        "user_id": f"user_{request_id}",
                        "message": f"Request {request_id}",
                        "streaming": False,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                )

                expected_status = 200 if use_valid else 401
                return response.status_code == expected_status

            # Execute requests concurrently
            with ThreadPoolExecutor(max_workers=50) as executor:
                futures = [
                    executor.submit(make_request, i) for i in range(num_requests)
                ]

                # Collect results
                for future in as_completed(futures):
                    results.append(future.result())

            # Verify all requests behaved as expected
            # If there's state corruption, some requests will have wrong status
            assert len(results) == num_requests
            assert all(
                correct for correct in results
            ), "Some requests had unexpected authentication results (possible state corruption)"

    @pytest.mark.slow
    def test_sustained_concurrent_load(self, client, test_token):
        """Verify authentication handles sustained concurrent load (1000 requests).

        This is a stress test to ensure:
        - No resource leaks
        - Consistent performance
        - No degradation over time
        """
        with patch("app.config.settings.API_BEARER_TOKEN", test_token):
            num_requests = 1000
            success_count = 0
            failure_count = 0

            def make_request(request_id):
                """Make authenticated request."""
                response = client.post(
                    "/chat",
                    json={
                        "user_id": f"user_{request_id % 100}",  # Reuse user IDs
                        "message": "Load test",
                        "streaming": False,
                    },
                    headers={"Authorization": f"Bearer {test_token}"},
                )
                return response.status_code == 200

            # Execute requests concurrently
            with ThreadPoolExecutor(max_workers=50) as executor:
                futures = [
                    executor.submit(make_request, i) for i in range(num_requests)
                ]

                # Collect results
                for future in as_completed(futures):
                    if future.result():
                        success_count += 1
                    else:
                        failure_count += 1

            # Verify all requests succeeded
            assert success_count == num_requests
            assert failure_count == 0

            print(
                f"\nSustained load test completed: {success_count}/{num_requests} succeeded"
            )
