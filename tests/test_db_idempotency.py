"""
Unit tests for database repository idempotency, duplicate prevention, and disconnection handling.
Tests verify parameterized SQL clauses and conflict resolution without touching user databases.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.config import AppConfig
from src.db import DatabaseRepository


@pytest.fixture
def mock_config():
    return AppConfig(
        ingestion_mode="fixture_replay",
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="test_cricket_db",
        postgres_user="test_user",
        postgres_password="test_password"
    )


@pytest.fixture
def mock_db_connection():
    conn = MagicMock()
    conn.closed = False
    conn.__enter__.return_value = conn
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


class TestDatabaseRepositoryIdempotency:

    def test_migration_discovery_order(self, mock_config, mock_db_connection):
        """Verify migrations are discovered and ordered lexicographically."""
        sql_dir = Path(__file__).resolve().parent.parent / "sql"
        mock_conn, mock_cur = mock_db_connection

        repo = DatabaseRepository(mock_config, conn=mock_conn)
        applied = repo.apply_migrations(sql_dir)

        assert len(applied) >= 2
        assert applied[0] == "001_initial_schema.sql"
        assert applied[1] == "002_reporting_views.sql"
        assert mock_cur.execute.call_count == len(applied)
        assert mock_conn.commit.called

    def test_match_upsert_sql_has_conflict_target(self, mock_config, mock_db_connection):
        """Verify upsert_match contains ON CONFLICT (provider_match_id) DO UPDATE."""
        mock_conn, mock_cur = mock_db_connection
        mock_cur.fetchone.return_value = {"id": 1}

        repo = DatabaseRepository(mock_config, conn=mock_conn)
        repo.upsert_match({
            "provider_match_id": "test-id",
            "series_name": "Series",
            "match_name": "Match",
            "match_type": "t20",
            "competition_category": "IPL",
            "venue": "Venue",
            "match_date_utc": "2026-10-25T00:00:00Z",
            "team_a": "A",
            "team_b": "B",
            "toss_winner": None,
            "toss_choice": None,
            "match_winner": None,
            "result_status": "Scheduled",
            "is_live": False,
            "is_completed": False,
            "is_abandoned": False,
            "is_simulated": True,
        })

        executed_sql = mock_cur.execute.call_args[0][0]
        assert "ON CONFLICT (provider_match_id) DO UPDATE" in executed_sql

    def test_batting_scorecard_upsert_has_conflict_target(self, mock_config, mock_db_connection):
        """Verify upsert_batting_scorecard contains ON CONFLICT (innings_id, provider_player_id) DO UPDATE."""
        mock_conn, mock_cur = mock_db_connection

        repo = DatabaseRepository(mock_config, conn=mock_conn)
        repo.upsert_batting_scorecard(innings_id=1, batters=[{
            "match_id": 1,
            "provider_player_id": "p-1",
            "player_name": "Player 1",
            "batting_position": 1,
            "dismissal_info": "not out",
            "is_dismissed": False,
            "runs": 25,
            "balls_faced": 15,
            "fours": 3,
            "sixes": 1,
            "strike_rate": 166.67,
        }])

        executed_sql = mock_cur.execute.call_args[0][0]
        assert "ON CONFLICT (innings_id, provider_player_id) DO UPDATE" in executed_sql

    def test_ball_events_insert_prevents_duplicate_sequences(self, mock_config, mock_db_connection):
        """Verify insert_ball_events uses ON CONFLICT (innings_id, ball_sequence) DO NOTHING."""
        mock_conn, mock_cur = mock_db_connection

        repo = DatabaseRepository(mock_config, conn=mock_conn)
        repo.insert_ball_events([{
            "match_id": 1,
            "innings_id": 1,
            "over_number": 0,
            "ball_number": 1,
            "ball_sequence": 1,
            "batter_name": "B1",
            "bowler_name": "BW1",
            "non_striker_name": "B2",
            "runs_batter": 1,
            "runs_extra": 0,
            "extra_type": None,
            "total_ball_runs": 1,
            "is_wicket": False,
            "wicket_type": None,
            "player_dismissed": None,
            "commentary_text": "Good length ball",
            "is_simulated": True,
        }])

        executed_sql = mock_cur.execute.call_args[0][0]
        assert "ON CONFLICT (innings_id, ball_sequence) DO NOTHING" in executed_sql

    def test_score_snapshots_duplicate_prevention(self, mock_config, mock_db_connection):
        """Verify insert_score_snapshot uses ON CONFLICT (innings_id, overs) to prevent duplicates."""
        mock_conn, mock_cur = mock_db_connection

        repo = DatabaseRepository(mock_config, conn=mock_conn)
        repo.insert_score_snapshot({
            "match_id": 1,
            "innings_id": 1,
            "snapshot_timestamp_utc": "2026-10-25T00:00:00Z",
            "overs": 1.0,
            "runs": 8,
            "wickets": 0,
            "run_rate": 8.0,
            "striker_name": "B1",
            "non_striker_name": "B2",
            "active_bowler_name": "BW1",
        })

        executed_sql = mock_cur.execute.call_args[0][0]
        assert "ON CONFLICT (innings_id, overs) DO UPDATE" in executed_sql

    def test_connection_failure_handling(self, mock_config):
        """Verify test_connection returns False when database is unreachable."""
        repo = DatabaseRepository(mock_config, conn=None)
        repo.get_connection = MagicMock(side_effect=Exception("Database unreachable on localhost:5432"))
        assert repo.test_connection() is False
