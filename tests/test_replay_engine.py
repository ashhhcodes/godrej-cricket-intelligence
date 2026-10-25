"""
Unit tests for deterministic fixture replay engine.
Validates sequential state progression, simulation provenance (is_simulated=TRUE),
and replay restartability without needing a live database.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.replay_engine import FixtureReplayEngine
from src.db import DatabaseRepository

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "cricsheet_t20_match.json"


@pytest.fixture
def mock_db():
    db = MagicMock(spec=DatabaseRepository)
    db.upsert_match.return_value = 101
    db.upsert_innings.return_value = 201
    return db


class TestFixtureReplayEngine:

    def test_replay_initialization(self, mock_db):
        """Verify match record initialized with is_simulated=TRUE and status='In Progress'."""
        engine = FixtureReplayEngine(FIXTURE_PATH, mock_db)
        match_id = engine.initialize_replay()

        assert match_id == 101
        assert engine.match_db_id == 101
        assert mock_db.upsert_match.called

        match_args = mock_db.upsert_match.call_args[0][0]
        assert match_args["is_simulated"] is True, "Provenance flag is_simulated MUST be True for replay"
        assert match_args["is_live"] is True
        assert match_args["is_completed"] is False
        assert "Gujarat Titans" in match_args["team_a"] or "Gujarat Titans" in match_args["team_b"]

    def test_delivery_step_progression(self, mock_db):
        """Verify sequential ball delivery step calculations and database updates."""
        engine = FixtureReplayEngine(FIXTURE_PATH, mock_db)
        engine.initialize_replay()

        # Step 1: Over 0, Ball 1 (WP Saha 0 runs)
        step1 = engine.step_delivery()
        assert step1["status"] == "in_progress"
        assert step1["runs"] == 0
        assert step1["overs"] == 0.1
        assert step1["batter"] == "WP Saha"
        assert step1["bowler"] == "DL Chahar"

        # Verify ball event inserted with is_simulated = True
        assert mock_db.insert_ball_events.called
        ball_event = mock_db.insert_ball_events.call_args[0][0][0]
        assert ball_event["is_simulated"] is True
        assert ball_event["ball_sequence"] == 1
        assert ball_event["runs_batter"] == 0

        # Step 2: Over 0, Ball 2 (WP Saha 4 runs)
        step2 = engine.step_delivery()
        assert step2["runs"] == 4
        assert step2["overs"] == 0.2

        # Verify match_state updated
        assert mock_db.upsert_match_state.called
        latest_state = mock_db.upsert_match_state.call_args[0][0]
        assert latest_state["current_runs"] == 4
        assert latest_state["current_overs"] == 0.2

    def test_wicket_handling_in_replay(self, mock_db):
        """Advance simulation to over 2 ball 5 where Shubman Gill is stumped."""
        engine = FixtureReplayEngine(FIXTURE_PATH, mock_db)
        engine.initialize_replay()

        # Over 0: 6 balls
        # Over 1: 7 balls (includes 1 wide)
        # Over 2: 5 balls -> ball 5 is the wicket
        total_steps = 6 + 7 + 5
        for _ in range(total_steps):
            result = engine.step_delivery()

        assert result["wickets"] == 1
        # Check that Shubman Gill is marked dismissed
        batters_call = mock_db.upsert_batting_scorecard.call_args[0][1]
        gill = [b for b in batters_call if b["player_name"] == "Shubman Gill"][0]
        assert gill["is_dismissed"] is True
        assert "stumped" in gill["dismissal_info"]

    def test_replay_restartability(self, mock_db):
        """Verify that replay can be cleanly restarted, resetting counters to 0."""
        engine = FixtureReplayEngine(FIXTURE_PATH, mock_db)
        engine.initialize_replay()

        # Advance 5 balls
        for _ in range(5):
            engine.step_delivery()
        assert engine.scores[0]["legal_balls"] == 5

        # Re-initialize
        engine.initialize_replay()
        assert engine.current_inning_idx == 0
        assert engine.current_over_idx == 0
        assert engine.current_ball_idx == 0
        assert engine.scores[0]["legal_balls"] == 0
        assert engine.scores[0]["runs"] == 0
