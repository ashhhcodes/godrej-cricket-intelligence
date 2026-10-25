"""
Daily Request-Budget Manager.
Enforces the 100-hit daily API ceiling, tracks request consumption across all
discovery and scorecard endpoints, and prevents quota exhaustion.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from src.logger import setup_logger

logger = setup_logger("budget_manager")


class RequestBudgetManager:
    """
    Thread-safe quota tracker maintaining local and provider-reported credit state.
    Supports persistent disk state to survive process restarts.
    """

    def __init__(
        self,
        daily_limit: int = 100,
        safety_margin: int = 10,
        state_file: Optional[Path] = None
    ):
        self.daily_limit = daily_limit
        self.safety_margin = safety_margin
        self.state_file = Path(state_file) if state_file else None
        self._lock = threading.Lock()
        
        self.local_hits_today = 0
        self.provider_hits_today: Optional[int] = None
        self.provider_credits_remaining: Optional[int] = None
        self.last_request_timestamp_utc: Optional[datetime] = None
        self.current_day_utc: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if self.state_file and self.state_file.exists():
            self._load_state()

    def _load_state(self) -> None:
        """Restores quota state from disk if recorded today."""
        if not self.state_file or not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("day_utc") == self.current_day_utc:
                self.local_hits_today = data.get("local_hits_today", 0)
                self.provider_hits_today = data.get("provider_hits_today")
                self.provider_credits_remaining = data.get("provider_credits_remaining")
                last_req = data.get("last_request_utc")
                if last_req:
                    try:
                        self.last_request_timestamp_utc = datetime.fromisoformat(last_req)
                    except ValueError:
                        pass
                logger.info(
                    f"Restored persisted quota state for {self.current_day_utc}: "
                    f"local_hits={self.local_hits_today}, provider_hits={self.provider_hits_today}"
                )
        except Exception as e:
            logger.warning(f"Could not load persisted quota state from {self.state_file}: {e}")

    def _save_state(self) -> None:
        """Persists current quota state to disk."""
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "day_utc": self.current_day_utc,
                "local_hits_today": self.local_hits_today,
                "provider_hits_today": self.provider_hits_today,
                "provider_credits_remaining": self.provider_credits_remaining,
                "daily_limit": self.daily_limit,
                "safety_margin": self.safety_margin,
                "last_request_utc": self.last_request_timestamp_utc.isoformat() if self.last_request_timestamp_utc else None,
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save quota state to {self.state_file}: {e}")

    def _check_and_reset_day(self) -> None:
        """
        Resets local counters at midnight UTC.
        """
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today_utc != self.current_day_utc:
            logger.info(f"UTC day rollover detected: {self.current_day_utc} -> {today_utc}. Resetting quota.")
            self.local_hits_today = 0
            self.provider_hits_today = None
            self.provider_credits_remaining = None
            self.current_day_utc = today_utc
            self._save_state()

    def can_make_request(self, estimated_cost: int = 1) -> bool:
        """
        Determines whether an outbound API request is permitted within the safety buffer.
        """
        with self._lock:
            self._check_and_reset_day()
            
            # Prioritize provider-reported hits if available, otherwise use local tracker
            effective_hits = self.provider_hits_today if self.provider_hits_today is not None else self.local_hits_today
            effective_ceiling = self.daily_limit - self.safety_margin

            if (effective_hits + estimated_cost) > effective_ceiling:
                logger.warning(
                    f"Outbound API request BLOCKED: Quota ceiling reached. "
                    f"Effective Hits={effective_hits}, Cost={estimated_cost}, "
                    f"Ceiling={effective_ceiling} (Daily Limit={self.daily_limit}, Margin={self.safety_margin})"
                )
                return False
            return True

    def record_request(
        self,
        endpoint: str,
        http_status: int,
        credits_consumed: int = 1,
        hits_today: Optional[int] = None,
        hits_limit: Optional[int] = None,
        credits_remaining: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        match_id: Optional[str] = None,
        status_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records an executed HTTP request and updates quota telemetry.
        """
        with self._lock:
            self._check_and_reset_day()
            self.local_hits_today += credits_consumed
            self.last_request_timestamp_utc = datetime.now(timezone.utc)

            if hits_today is not None:
                self.provider_hits_today = hits_today
            if credits_remaining is not None:
                self.provider_credits_remaining = credits_remaining
            if hits_limit is not None:
                self.daily_limit = hits_limit

            telemetry = {
                "timestamp_utc": self.last_request_timestamp_utc,
                "endpoint": endpoint,
                "http_status": http_status,
                "credits_consumed": credits_consumed,
                "hits_today": self.provider_hits_today if self.provider_hits_today is not None else self.local_hits_today,
                "hits_limit": self.daily_limit,
                "credits_remaining": self.provider_credits_remaining,
                "response_time_ms": response_time_ms,
                "match_id_queried": match_id,
                "status_message": status_message,
            }

            logger.debug(
                f"API Request Logged: [{endpoint}] HTTP {http_status} | "
                f"Consumed: {credits_consumed} | Total Today: {telemetry['hits_today']}/{self.daily_limit}"
            )
            self._save_state()
            return telemetry

    def get_quota_status(self) -> Dict[str, Any]:
        """
        Returns snapshot of current quota metrics.
        """
        with self._lock:
            self._check_and_reset_day()
            effective_hits = self.provider_hits_today if self.provider_hits_today is not None else self.local_hits_today
            remaining = max(0, self.daily_limit - effective_hits)
            available_under_margin = max(0, self.daily_limit - self.safety_margin - effective_hits)

            return {
                "day_utc": self.current_day_utc,
                "effective_hits_today": effective_hits,
                "local_hits_today": self.local_hits_today,
                "provider_hits_today": self.provider_hits_today,
                "daily_limit": self.daily_limit,
                "safety_margin": self.safety_margin,
                "remaining_hits_total": remaining,
                "available_hits_under_margin": available_under_margin,
                "is_exhausted": available_under_margin <= 0,
                "last_request_utc": self.last_request_timestamp_utc.isoformat() if self.last_request_timestamp_utc else None,
            }
