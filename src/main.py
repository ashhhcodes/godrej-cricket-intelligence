"""
Command-Line Interface (CLI) Entrypoint for Godrej Cricket Intelligence.
Supports schema migration execution, deterministic replay simulation,
live CricAPI ingestion, and connection diagnostics with graceful shutdown handling.
"""

import argparse
import signal
import sys
from pathlib import Path

# Ensure project root is in sys.path when invoked directly as python src/main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, AppConfig
from src.logger import setup_logger
from src.db import DatabaseRepository
from src.budget_manager import RequestBudgetManager
from src.cricapi_client import CricApiClient
from src.replay_engine import FixtureReplayEngine
from src.scheduler import IngestionScheduler

logger = setup_logger("main")


def handle_signals(scheduler: IngestionScheduler):
    """Binds OS interrupt signals to stop the scheduler gracefully."""
    def _sig_handler(signum, frame):
        logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)


def cmd_migrate(config: AppConfig) -> None:
    """Executes database schema migrations and analytical views."""
    logger.info("Executing database migrations...")
    db = DatabaseRepository(config)
    sql_dir = Path(__file__).resolve().parent.parent / "sql"
    try:
        applied = db.apply_migrations(sql_dir)
        logger.info(f"Successfully applied migrations: {applied}")
    except Exception as e:
        logger.error(f"Migration execution failed: {e}")
        sys.exit(1)
    finally:
        db.close()


def cmd_test_connection(config: AppConfig) -> None:
    """Tests PostgreSQL database connectivity."""
    logger.info("Testing PostgreSQL connection...")
    db = DatabaseRepository(config)
    try:
        success = db.test_connection()
        if success:
            logger.info("PostgreSQL database connection verified successfully!")
        else:
            logger.error("Database connection failed. Please check your credentials in .env.")
            sys.exit(1)
    finally:
        db.close()


def cmd_run(config: AppConfig, mode: str, max_cycles: int = None) -> None:
    """Initializes and runs the ingestion engine."""
    if mode == "live":
        if not config.allow_live_api:
            logger.error(
                "Security Enforcement: Live API ingestion requires explicit opt-in via ALLOW_LIVE_API=true in .env."
            )
            sys.exit(1)
        if not config.cricapi_key or config.cricapi_key.startswith("your_"):
            logger.error(
                "Configuration Error: Valid CRICAPI_KEY must be provided in .env to run in live mode."
            )
            sys.exit(1)

    config.ingestion_mode = mode
    logger.info(f"Launching Ingestion Service in '{mode}' mode...")
    logger.info(f"Active configuration: {config.safe_summary()}")

    db = DatabaseRepository(config)
    quota_file = Path("logs/quota_state.json")
    budget_mgr = RequestBudgetManager(
        daily_limit=config.api_daily_quota_limit,
        safety_margin=config.api_safety_margin_hits,
        state_file=quota_file
    )

    api_client = None
    if mode == "live":
        api_client = CricApiClient(config, budget_mgr)

    fixture_path = Path(config.fixture_path)
    replay_engine = FixtureReplayEngine(fixture_path, db)

    scheduler = IngestionScheduler(
        config=config,
        db=db,
        budget_manager=budget_mgr,
        api_client=api_client,
        replay_engine=replay_engine
    )

    handle_signals(scheduler)
    try:
        scheduler.start(max_cycles=max_cycles)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Godrej Cricket Intelligence — Ingestion Service & Data Pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", help="Operational commands")

    # migrate
    subparsers.add_parser("migrate", help="Apply versioned SQL schema migrations and reporting views")

    # test-connection
    subparsers.add_parser("test-connection", help="Verify PostgreSQL connection")

    # replay
    replay_parser = subparsers.add_parser("replay", help="Run deterministic fixture replay simulation (default)")
    replay_parser.add_argument("--cycles", type=int, default=None, help="Limit number of simulation ticks")

    # live
    live_parser = subparsers.add_parser("live", help="Run live CricAPI ingestion (requires ALLOW_LIVE_API=true)")
    live_parser.add_argument("--cycles", type=int, default=None, help="Limit number of polling cycles")

    # status
    subparsers.add_parser("status", help="Display quota telemetry and configuration status")

    args = parser.parse_args()

    try:
        config = load_config()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    if args.command == "migrate":
        cmd_migrate(config)
    elif args.command == "test-connection":
        cmd_test_connection(config)
    elif args.command == "replay":
        cmd_run(config, mode="fixture_replay", max_cycles=args.cycles)
    elif args.command == "live":
        cmd_run(config, mode="live", max_cycles=args.cycles)
    elif args.command == "status":
        logger.info(f"Configuration: {config.safe_summary()}")
        budget_mgr = RequestBudgetManager(
            daily_limit=config.api_daily_quota_limit,
            safety_margin=config.api_safety_margin_hits,
            state_file=Path("logs/quota_state.json")
        )
        logger.info(f"Quota Status: {budget_mgr.get_quota_status()}")
    else:
        # Default behavior: run replay if no command provided
        logger.info("No command specified. Defaulting to 'replay' mode...")
        cmd_run(config, mode="fixture_replay")


if __name__ == "__main__":
    main()
