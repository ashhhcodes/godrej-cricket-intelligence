"""
Adaptive ingestion scheduler.
Coordinates the background loop across both 'fixture_replay' and 'live' modes,
manages quota pacing, and tracks pipeline health telemetry.
"""

import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from src.config import AppConfig
from src.cricapi_client import CricApiClient, QuotaExhaustedError
from src.budget_manager import RequestBudgetManager
from src.db import DatabaseRepository
from src.replay_engine import FixtureReplayEngine
from src.normalizer import normalize_match_info, normalize_match_state, normalize_scorecard
from src.logger import setup_logger

logger = setup_logger("scheduler")


class IngestionScheduler:
    """
    Orchestrates the ingestion loop for live polling or fixture replay.
    """

    def __init__(
        self,
        config: AppConfig,
        db: DatabaseRepository,
        budget_manager: RequestBudgetManager,
        api_client: Optional[CricApiClient] = None,
        replay_engine: Optional[FixtureReplayEngine] = None,
    ):
        self.config = config
        self.db = db
        self.budget_manager = budget_manager
        self.api_client = api_client
        self.replay_engine = replay_engine

        self.is_running = False
        self.total_cycles_completed = 0
        self.last_successful_ingestion_utc: Optional[datetime] = None
        self.stale_data_threshold = timedelta(minutes=10)
        self.current_match_id_fk: Optional[int] = None
        self.current_provider_match_id: Optional[str] = None

    def start(self, max_cycles: Optional[int] = None) -> None:
        """
        Starts the continuous ingestion loop.
        Can run for a bounded number of cycles (for testing) or indefinitely.
        """
        self.is_running = True
        logger.info(f"Starting Ingestion Engine in mode='{self.config.ingestion_mode}'")

        if self.config.ingestion_mode == "fixture_replay":
            if self.replay_engine is None:
                raise ValueError("Replay engine is required for fixture_replay mode.")
            self.replay_engine.initialize_replay()

        while self.is_running:
            cycle_start = time.time()
            try:
                if self.config.ingestion_mode == "fixture_replay":
                    self._run_replay_cycle()
                elif self.config.ingestion_mode == "live":
                    self._run_live_cycle()

                self.total_cycles_completed += 1
                self.last_successful_ingestion_utc = datetime.now(timezone.utc)

            except QuotaExhaustedError as qe:
                logger.error(f"Quota Exhausted: {qe}. Halting live requests. Switching to replay fallback.")
                if self.replay_engine:
                    self.config.ingestion_mode = "fixture_replay"
                    self.replay_engine.initialize_replay()
                else:
                    self.is_running = False
                    break

            except Exception as e:
                logger.error(f"Error during ingestion cycle {self.total_cycles_completed + 1}: {e}", exc_info=True)

            if max_cycles is not None and self.total_cycles_completed >= max_cycles:
                logger.info(f"Reached requested max_cycles={max_cycles}. Stopping scheduler.")
                self.is_running = False
                break

            # Sleep pacing
            sleep_duration = (
                self.config.simulation_speed_seconds
                if self.config.ingestion_mode == "fixture_replay"
                else self.config.api_poll_interval_seconds
            )
            elapsed = time.time() - cycle_start
            wait_time = max(0.1, sleep_duration - elapsed)
            time.sleep(wait_time)

    def stop(self) -> None:
        """Signals the scheduler to stop gracefully."""
        logger.info("Graceful shutdown signal received. Halting ingestion loop.")
        self.is_running = False

    def _run_replay_cycle(self) -> None:
        """Executes a single delivery step in replay mode."""
        if self.replay_engine is None:
            return
        result = self.replay_engine.step_delivery()
        if result.get("is_finished"):
            logger.info("Replay match completed. Resetting for continuous looping.")
            self.replay_engine.initialize_replay()

    def _run_live_cycle(self) -> None:
        """Executes a live API polling cycle adhering to daily budget."""
        if not self.api_client:
            raise ValueError("CricApiClient is required for live ingestion mode.")

        # 1. Match Discovery (if no active match tracked)
        if not self.current_provider_match_id:
            logger.info("Discovering active fixtures via /currentMatches...")
            curr_matches_resp = self.api_client.get_current_matches(offset=0)
            matches_data = curr_matches_resp.get("data", [])

            if not matches_data:
                logger.warning("No matches returned from /currentMatches feed.")
                return

            # Target specific match or pick first live match
            selected = None
            if self.config.target_match_id:
                for m in matches_data:
                    if m.get("id") == self.config.target_match_id:
                        selected = m
                        break
            if not selected:
                selected = matches_data[0]

            self.current_provider_match_id = selected.get("id")
            normalized_match = normalize_match_info(selected, is_simulated=False)
            self.current_match_id_fk = self.db.upsert_match(normalized_match)
            logger.info(f"Tracked match: {selected.get('name')} (id={self.current_match_id_fk})")

        # 2. Fetch Granular Match Scorecard
        logger.info(f"Polling scorecard for match {self.current_provider_match_id} via /match_scorecard...")
        scorecard_resp = self.api_client.get_match_scorecard(self.current_provider_match_id)
        
        # 3. Normalize & Upsert
        normalized_match = normalize_match_info(scorecard_resp, is_simulated=False)
        self.current_match_id_fk = self.db.upsert_match(normalized_match)

        normalized_state = normalize_match_state(
            scorecard_resp,
            match_id_fk=self.current_match_id_fk,
            is_live=normalized_match["is_live"]
        )
        self.db.upsert_match_state(normalized_state)

        innings_list, batting_list, bowling_list = normalize_scorecard(
            scorecard_resp,
            match_id_fk=self.current_match_id_fk
        )

        for inn in innings_list:
            innings_id = self.db.upsert_innings(inn)
            # Filter batters and bowlers for this specific innings number
            inn_batters = [b for b in batting_list if b["innings_number"] == inn["innings_number"]]
            inn_bowlers = [bw for bw in bowling_list if bw["innings_number"] == inn["innings_number"]]
            self.db.upsert_batting_scorecard(innings_id, inn_batters)
            self.db.upsert_bowling_scorecard(innings_id, inn_bowlers)

        # 4. Take Snapshot
        if normalized_state["current_runs"] is not None and normalized_state["current_overs"] is not None:
            snapshot = {
                "match_id": self.current_match_id_fk,
                "innings_id": innings_list[-1]["match_id"] if innings_list else self.current_match_id_fk,
                "snapshot_timestamp_utc": datetime.now(timezone.utc),
                "overs": normalized_state["current_overs"],
                "runs": normalized_state["current_runs"],
                "wickets": normalized_state["current_wickets"] or 0,
                "run_rate": normalized_state["current_run_rate"],
                "striker_name": None,
                "non_striker_name": None,
                "active_bowler_name": None,
            }
            # Look up actual innings_id
            if innings_list:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id FROM innings WHERE match_id = %s AND innings_number = %s;",
                            (self.current_match_id_fk, normalized_state["current_innings_number"] or 1)
                        )
                        row = cur.fetchone()
                        if row:
                            snapshot["innings_id"] = row["id"]
                            self.db.insert_score_snapshot(snapshot)

        # 5. Check if match has concluded
        if normalized_match["is_completed"] or normalized_match["is_abandoned"]:
            logger.info(f"Match {self.current_provider_match_id} completed. Resetting tracked match.")
            self.current_provider_match_id = None
            self.current_match_id_fk = None

    def get_health_status(self) -> Dict[str, Any]:
        """Returns health telemetry and stale data assessment."""
        now = datetime.now(timezone.utc)
        is_stale = False
        seconds_since_last = None

        if self.last_successful_ingestion_utc:
            delta = now - self.last_successful_ingestion_utc
            seconds_since_last = int(delta.total_seconds())
            is_stale = delta > self.stale_data_threshold

        return {
            "is_running": self.is_running,
            "mode": self.config.ingestion_mode,
            "total_cycles_completed": self.total_cycles_completed,
            "last_successful_ingestion_utc": self.last_successful_ingestion_utc.isoformat() if self.last_successful_ingestion_utc else None,
            "seconds_since_last_ingestion": seconds_since_last,
            "is_stale": is_stale,
            "quota_status": self.budget_manager.get_quota_status(),
        }
