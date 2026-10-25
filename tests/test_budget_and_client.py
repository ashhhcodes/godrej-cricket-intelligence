"""
Unit tests for Request Budget Manager and Resilient CricAPI Client.
Verifies quota enforcement, backoff, circuit breaking, and secret sanitization without real network calls.
"""

from unittest.mock import MagicMock, patch
import pytest
import requests
from src.config import AppConfig
from src.budget_manager import RequestBudgetManager
from src.cricapi_client import CricApiClient, QuotaExhaustedError, CircuitBreakerOpenError


class TestRequestBudgetManager:

    def test_daily_quota_limit_enforcement(self):
        """Verify that requests are blocked when approaching the daily ceiling within safety margin."""
        # Limit = 100, Margin = 10 -> Max allowed requests = 90
        manager = RequestBudgetManager(daily_limit=100, safety_margin=10)

        # First 90 requests are permitted
        for i in range(90):
            assert manager.can_make_request() is True
            manager.record_request(endpoint="test", http_status=200, credits_consumed=1)

        # 91st request MUST be blocked to protect the 10-hit safety buffer
        assert manager.can_make_request() is False
        status = manager.get_quota_status()
        assert status["effective_hits_today"] == 90
        assert status["is_exhausted"] is True
        assert status["available_hits_under_margin"] == 0
        assert status["remaining_hits_total"] == 10

    def test_provider_reported_telemetry_precedence(self):
        """Verify that provider reported hitsToday overrides local counter."""
        manager = RequestBudgetManager(daily_limit=100, safety_margin=5)
        # Local recorded 2 hits
        manager.record_request("test", 200, credits_consumed=1)
        manager.record_request("test", 200, credits_consumed=1)
        assert manager.local_hits_today == 2

        # Provider response body reports hitsToday = 80
        manager.record_request("test", 200, credits_consumed=1, hits_today=80, credits_remaining=20)
        status = manager.get_quota_status()
        assert status["provider_hits_today"] == 80
        assert status["effective_hits_today"] == 80
        assert status["remaining_hits_total"] == 20

    def test_quota_persistence_across_process_restarts(self, tmp_path):
        """Verify that recorded requests persist to disk and are restored on restart."""
        state_file = tmp_path / "test_quota_state.json"

        # Process 1: Record 45 requests
        mgr1 = RequestBudgetManager(daily_limit=100, safety_margin=10, state_file=state_file)
        for _ in range(45):
            mgr1.record_request(endpoint="match_scorecard", http_status=200, credits_consumed=1)

        assert mgr1.local_hits_today == 45
        assert state_file.exists()

        # Process 2 (simulating process restart with fresh instance pointing to same state_file)
        mgr2 = RequestBudgetManager(daily_limit=100, safety_margin=10, state_file=state_file)
        status = mgr2.get_quota_status()

        assert mgr2.local_hits_today == 45
        assert status["effective_hits_today"] == 45
        assert status["available_hits_under_margin"] == (100 - 10 - 45)  # 45 available
        assert status["is_exhausted"] is False


class TestCricApiClient:

    @pytest.fixture
    def test_config(self):
        return AppConfig(
            ingestion_mode="fixture_replay",
            allow_live_api=False,
            cricapi_key="test-secret-key-12345",
            cricapi_base_url="https://api.cricapi.com/v1",
            api_daily_quota_limit=10,
            api_safety_margin_hits=2,
            api_poll_interval_seconds=10,
        )

    def test_quota_exhausted_raises_error(self, test_config):
        """Verify client raises QuotaExhaustedError when manager blocks request."""
        mock_budget = MagicMock(spec=RequestBudgetManager)
        mock_budget.can_make_request.return_value = False

        client = CricApiClient(config=test_config, budget_manager=mock_budget)
        with pytest.raises(QuotaExhaustedError, match="Daily API quota ceiling reached"):
            client.get_current_matches()

    def test_http_429_trips_circuit_breaker(self, test_config):
        """Verify that HTTP 429 trips circuit breaker and raises QuotaExhaustedError."""
        mock_budget = MagicMock(spec=RequestBudgetManager)
        mock_budget.can_make_request.return_value = True

        mock_session = MagicMock(spec=requests.Session)
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.reason = "Too Many Requests"
        mock_resp.json.return_value = {"status": "failure", "message": "Hit Limit Exceeded"}
        mock_session.get.return_value = mock_resp

        client = CricApiClient(config=test_config, budget_manager=mock_budget, session=mock_session)

        with pytest.raises(QuotaExhaustedError, match="HTTP 429"):
            client.get_current_matches()

        # Immediate subsequent request should fail fast with CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError, match="Circuit breaker OPEN"):
            client.get_current_matches()

    def test_retry_on_500_with_eventual_success(self, test_config):
        """Verify client retries boundedly on 500 server error and succeeds on subsequent attempt."""
        mock_budget = MagicMock(spec=RequestBudgetManager)
        mock_budget.can_make_request.return_value = True

        mock_session = MagicMock(spec=requests.Session)
        
        # 1st attempt: 500 Server Error
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.reason = "Internal Server Error"
        resp_500.json.return_value = {}

        # 2nd attempt: 200 OK
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.reason = "OK"
        resp_200.json.return_value = {"status": "success", "data": [{"id": "match-1"}]}

        mock_session.get.side_effect = [resp_500, resp_200]

        client = CricApiClient(config=test_config, budget_manager=mock_budget, session=mock_session)

        with patch("time.sleep"):  # Mock sleep so test runs instantly
            result = client.get_current_matches()

        assert result["status"] == "success"
        assert mock_session.get.call_count == 2
        assert mock_budget.record_request.call_count == 2

    def test_api_key_sanitization_in_logs(self, test_config):
        """Verify URL string sanitizer strips the raw API key."""
        client = CricApiClient(config=test_config, budget_manager=MagicMock())
        raw_url = "https://api.cricapi.com/v1/currentMatches?apikey=secret_key_abcdef_12345&offset=0"
        sanitized = client._sanitize_url(raw_url)

        assert "secret_key_abcdef_12345" not in sanitized
        assert "apikey=[MASKED]" in sanitized
