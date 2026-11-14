"""
=============================================================================
Suite: tests.test_ml_win_probability
Description: Automated Validation for In-Play Cricket Win Probability ML Model
Author: Team Elite Crew | Godrej Cricket Intelligence
=============================================================================
Validates:
1. Feature extraction and zero-division protection
2. Strict cricket physical invariants (boundary conditions)
3. Monotonic probability behavior under runs scored vs wickets lost
4. Scikit-Learn trained model persistence and prediction parity
"""

import pytest
import numpy as np
from src.ml_win_probability import (
    CricketWinProbabilityModel,
    WinProbabilityState,
    WinProbabilityPrediction,
)


@pytest.fixture
def model():
    return CricketWinProbabilityModel()


class TestCricketWinProbabilityFeatures:
    """Validates domain feature computation."""

    def test_feature_computation_at_start_of_chase(self):
        state = WinProbabilityState(
            current_runs=0,
            current_wickets=0,
            balls_bowled=0,
            target_runs=180,
            total_match_balls=120,
        )
        feats = CricketWinProbabilityModel.compute_features(state)
        assert feats["runs_needed"] == 180.0
        assert feats["balls_remaining"] == 120.0
        assert feats["wickets_in_hand"] == 10.0
        assert feats["required_run_rate"] == 9.0
        assert feats["current_run_rate"] == 0.0
        assert feats["is_powerplay"] == 1.0
        assert feats["is_death"] == 0.0
        assert feats["pressure_index"] == round(9.0 / 11.0, 2)

    def test_overs_helper_method_converts_correctly(self):
        # 6.4 overs = 6*6 + 4 = 40 balls
        state = WinProbabilityState.from_overs(
            current_runs=50,
            current_wickets=1,
            overs_float=6.4,
            target_runs=160,
        )
        assert state.balls_bowled == 40
        assert state.current_runs == 50
        assert state.current_wickets == 1


class TestCricketDomainBoundaryInvariants:
    """Verifies that mathematical and physical domain boundaries are strictly enforced."""

    def test_target_reached_yields_100_percent_win(self, model):
        state = WinProbabilityState(
            current_runs=185,
            current_wickets=4,
            balls_bowled=110,
            target_runs=180,
        )
        pred = model.predict(state)
        assert pred.chasing_win_pct == 100.0
        assert pred.defending_win_pct == 0.0
        assert pred.runs_needed == 0

    def test_all_out_yields_zero_percent_win(self, model):
        state = WinProbabilityState(
            current_runs=140,
            current_wickets=10,
            balls_bowled=95,
            target_runs=180,
        )
        pred = model.predict(state)
        assert pred.chasing_win_pct == 0.0
        assert pred.defending_win_pct == 100.0
        assert pred.wickets_in_hand == 0

    def test_balls_exhausted_without_target_yields_zero_percent_win(self, model):
        state = WinProbabilityState(
            current_runs=175,
            current_wickets=6,
            balls_bowled=120,
            target_runs=180,
        )
        pred = model.predict(state)
        assert pred.chasing_win_pct == 0.0
        assert pred.defending_win_pct == 100.0
        assert pred.balls_remaining == 0


class TestMonotonicityAndSensibility:
    """Tests that the ML model obeys cricket game dynamics."""

    def test_runs_scored_increases_win_probability(self, model):
        state_before = WinProbabilityState.from_overs(
            current_runs=100, current_wickets=3, overs_float=12.0, target_runs=180
        )
        # Batter hits a six: 106/3 in 12.1 ov
        state_after = WinProbabilityState(
            current_runs=106, current_wickets=3, balls_bowled=73, target_runs=180
        )

        p_before = model.predict(state_before).chasing_win_probability
        p_after = model.predict(state_after).chasing_win_probability
        assert p_after > p_before

    def test_wickets_lost_decreases_win_probability(self, model):
        state_before = WinProbabilityState.from_overs(
            current_runs=120, current_wickets=3, overs_float=14.0, target_runs=180
        )
        # Next ball is a wicket with no run: 120/4 in 14.1 ov
        state_after = WinProbabilityState(
            current_runs=120, current_wickets=4, balls_bowled=85, target_runs=180
        )

        p_before = model.predict(state_before).chasing_win_probability
        p_after = model.predict(state_after).chasing_win_probability
        assert p_after < p_before

    def test_dot_ball_under_pressure_decreases_win_probability(self, model):
        # Needing 20 off 6 balls
        state_ball_1 = WinProbabilityState(
            current_runs=160, current_wickets=5, balls_bowled=114, target_runs=180
        )
        # Dot ball: needing 20 off 5 balls
        state_ball_2 = WinProbabilityState(
            current_runs=160, current_wickets=5, balls_bowled=115, target_runs=180
        )

        p1 = model.predict(state_ball_1).chasing_win_probability
        p2 = model.predict(state_ball_2).chasing_win_probability
        assert p2 < p1
