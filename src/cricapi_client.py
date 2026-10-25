"""
Resilient CricAPI HTTP client.
Enforces daily budget checks, timeouts, bounded exponential backoff,
circuit breaking on HTTP 429, and complete credential masking.
"""

import time
from typing import Dict, Any, Optional
import requests
from src.config import AppConfig
from src.budget_manager import RequestBudgetManager
from src.logger import setup_logger

logger = setup_logger("cricapi_client")


class QuotaExhaustedError(Exception):
    """Raised when the daily API request budget ceiling is reached."""
    pass


class CircuitBreakerOpenError(Exception):
    """Raised when the client circuit breaker is open due to consecutive failures."""
    pass


class CricApiClient:
    """
    HTTP client for CricketData.org / CricAPI v1 REST endpoints.
    """

    def __init__(
        self,
        config: AppConfig,
        budget_manager: RequestBudgetManager,
        session: Optional[requests.Session] = None
    ):
        self.config = config
        self.budget_manager = budget_manager
        self.session = session or requests.Session()
        self.base_url = config.cricapi_base_url.rstrip("/")
        self.timeout_seconds = 10.0
        
        # Circuit breaker state
        self.consecutive_failures = 0
        self.failure_threshold = 3
        self.circuit_open_until = 0.0

    def _sanitize_url(self, url: str) -> str:
        """Removes the raw apikey query parameter for safe logging."""
        import re
        return re.sub(r"(apikey=)[^&\s]+", r"\1[MASKED]", url)

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, match_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a budget-checked GET request with exponential backoff.
        """
        # 1. Circuit breaker check
        now = time.time()
        if now < self.circuit_open_until:
            cooldown_left = int(self.circuit_open_until - now)
            raise CircuitBreakerOpenError(
                f"Circuit breaker OPEN due to consecutive failures. Cooling down for {cooldown_left}s."
            )

        # 2. Daily budget verification
        if not self.budget_manager.can_make_request(estimated_cost=1):
            raise QuotaExhaustedError("Daily API quota ceiling reached. Request aborted to protect budget.")

        # 3. Parameter construction
        full_params = {"apikey": self.config.cricapi_key}
        if params:
            full_params.update(params)

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        sanitized_url = self._sanitize_url(f"{url}?endpoint={endpoint}")

        # 4. Bounded retry loop with exponential backoff
        max_retries = 3
        backoff_delay = 1.5

        for attempt in range(1, max_retries + 1):
            start_time = time.time()
            try:
                logger.info(f"Issuing API request to {sanitized_url} (attempt {attempt}/{max_retries})")
                response = self.session.get(url, params=full_params, timeout=self.timeout_seconds)
                response_time_ms = int((time.time() - start_time) * 1000)

                # Extract provider telemetry if available in JSON body
                hits_today = None
                hits_limit = None
                credits_remaining = None
                data = {}

                try:
                    data = response.json()
                    info = data.get("info", {})
                    hits_today = info.get("hitsToday")
                    hits_limit = info.get("hitsLimit")
                    credits_remaining = info.get("credits")
                except Exception:
                    pass

                # Record request telemetry in budget manager
                self.budget_manager.record_request(
                    endpoint=endpoint,
                    http_status=response.status_code,
                    credits_consumed=1,
                    hits_today=hits_today,
                    hits_limit=hits_limit,
                    credits_remaining=credits_remaining,
                    response_time_ms=response_time_ms,
                    match_id=match_id,
                    status_message=response.reason
                )

                # HTTP 429: Rate limited / Quota Depleted
                if response.status_code == 429:
                    logger.error("Received HTTP 429 (Too Many Requests). Tripping circuit breaker for 300s.")
                    self.circuit_open_until = time.time() + 300
                    raise QuotaExhaustedError("Provider returned HTTP 429: Rate limit or daily quota exhausted.")

                # HTTP 5xx: Server side error - retry with backoff
                if 500 <= response.status_code < 600:
                    logger.warning(f"Provider returned HTTP {response.status_code} on attempt {attempt}.")
                    if attempt < max_retries:
                        time.sleep(backoff_delay)
                        backoff_delay *= 2
                        continue
                    response.raise_for_status()

                # HTTP 4xx: Client error (non-retryable)
                if 400 <= response.status_code < 500:
                    logger.error(f"Provider returned client error HTTP {response.status_code}: {response.text}")
                    response.raise_for_status()

                # Success
                self.consecutive_failures = 0
                return data

            except (requests.ConnectionError, requests.Timeout) as net_err:
                response_time_ms = int((time.time() - start_time) * 1000)
                logger.warning(f"Network error contacting CricAPI (attempt {attempt}/{max_retries}): {net_err}")
                self.budget_manager.record_request(
                    endpoint=endpoint,
                    http_status=0,
                    credits_consumed=1,
                    response_time_ms=response_time_ms,
                    match_id=match_id,
                    status_message=str(net_err)
                )

                if attempt < max_retries:
                    time.sleep(backoff_delay)
                    backoff_delay *= 2
                else:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= self.failure_threshold:
                        logger.error(f"Consecutive failure threshold ({self.failure_threshold}) reached. Opening circuit breaker for 120s.")
                        self.circuit_open_until = time.time() + 120
                    raise

        raise requests.RequestException(f"Failed to fetch data from {endpoint} after {max_retries} retries.")

    def get_current_matches(self, offset: int = 0) -> Dict[str, Any]:
        """Fetches list of live, upcoming, and recent matches."""
        return self._request("currentMatches", params={"offset": offset})

    def get_match_info(self, match_id: str) -> Dict[str, Any]:
        """Fetches detailed match metadata, venue, toss, and rosters."""
        return self._request("match_info", params={"id": match_id}, match_id=match_id)

    def get_match_scorecard(self, match_id: str) -> Dict[str, Any]:
        """Fetches granular innings scorecards (batting, bowling, extras)."""
        return self._request("match_scorecard", params={"id": match_id}, match_id=match_id)
