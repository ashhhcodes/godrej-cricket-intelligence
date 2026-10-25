"""
Calculation-Parity & Domain Math Tests for Power BI Semantic Model.
Project: Godrej Cricket Intelligence

These tests verify calculation parity between Python domain logic, PostgreSQL analytical
reporting views, and Power BI DAX measure specifications. They validate mathematical
equivalence, cricket notation conversion, and strict NULL vs. zero semantics.

NOTE: These tests confirm mathematical and algorithmic parity across data layers.
They validate that SQL views and DAX specifications yield identical outputs, but they
do not replace opening and visually verifying Power BI Desktop directly against PostgreSQL.
"""

import math
from typing import Optional, List, Tuple
import pytest
from src.config import load_config
from src.db import DatabaseRepository


# =====================================================================
# 1. PURE PYTHON PARITY LOGIC (Mirroring DAX Measure Formulations)
# =====================================================================

def dax_overs_to_balls(overs_list: List[float]) -> int:
    """Mirrors DAX [Total Bowling Balls] measure: SUMX(overs_bowled -> balls)."""
    total_balls = 0
    for ov in overs_list:
        comp_overs = int(ov)
        ball_remainder = round((ov - comp_overs) * 10)
        total_balls += (comp_overs * 6) + ball_remainder
    return total_balls


def dax_balls_to_overs_display(total_balls: Optional[int]) -> str:
    """Mirrors DAX [Overs Display] measure: formats balls to 'Overs.Balls' string."""
    if total_balls is None or total_balls == 0:
        return "0.0"
    comp_overs = total_balls // 6
    rem_balls = total_balls % 6
    return f"{comp_overs}.{rem_balls}"


def dax_decimal_overs(total_balls: int) -> float:
    """Mirrors DAX [Decimal Overs Bowled] measure: balls / 6.0."""
    return total_balls / 6.0


def dax_batting_strike_rate(runs: int, balls_faced: int) -> Optional[float]:
    """Mirrors DAX [Batting Strike Rate] measure: strict NULL if balls=0."""
    if balls_faced == 0:
        return None
    return round((runs * 100.0) / balls_faced, 2)


def dax_boundary_runs(fours: int, sixes: int) -> int:
    """Mirrors DAX [Boundary Runs] measure: (4s * 4) + (6s * 6)."""
    return (fours * 4) + (sixes * 6)


def dax_boundary_run_percentage(runs: int, fours: int, sixes: int) -> float:
    """Mirrors DAX [Boundary Run %] measure: boundary_runs / runs (0.0 if runs=0)."""
    if runs == 0:
        return 0.0
    b_runs = dax_boundary_runs(fours, sixes)
    return round((b_runs / runs) * 100.0, 2)


def dax_bowling_economy(runs_conceded: int, total_balls: int) -> Optional[float]:
    """Mirrors DAX [Bowling Economy Rate] measure: runs / decimal_overs (NULL if balls=0)."""
    if total_balls == 0:
        return None
    dec_overs = dax_decimal_overs(total_balls)
    return round(runs_conceded / dec_overs, 2)


def dax_bowling_average(runs_conceded: int, wickets: int) -> Optional[float]:
    """Mirrors DAX [Bowling Average] measure: runs / wickets (NULL if wickets=0)."""
    if wickets == 0:
        return None
    return round(runs_conceded / wickets, 2)


def dax_bowling_strike_rate(total_balls: int, wickets: int) -> Optional[float]:
    """Mirrors DAX [Bowling Strike Rate] measure: balls / wickets (NULL if wickets=0)."""
    if wickets == 0:
        return None
    return round(total_balls / wickets, 2)


def dax_data_provenance_banner(matches: List[dict]) -> str:
    """Mirrors DAX [Data Provenance Banner] measure across single and multiple matches."""
    if not matches:
        return "● NO FIXTURE SELECTED"

    if len(matches) > 1:
        sim_count = sum(1 for m in matches if m.get("is_simulated"))
        if sim_count == len(matches):
            return "● DEMO / SIMULATED DATA (OFFLINE REPLAY)"
        elif sim_count == 0:
            return "● OFFICIAL LIVE SOURCE (MULTIPLE MATCHES)"
        else:
            return "▲ MIXED DATA PROVENANCE (SELECT SINGLE FIXTURE)"

    # Single match evaluation
    m = matches[0]
    if m.get("is_simulated") is None:
        return "● PROVENANCE UNKNOWN"
    if m.get("is_simulated"):
        return "● DEMO / SIMULATED DATA (OFFLINE REPLAY)"
    if m.get("is_live"):
        return "● OFFICIAL LIVE SOURCE (CRICKETDATA.ORG - IN PLAY)"
    if m.get("is_completed"):
        return "● OFFICIAL LIVE SOURCE (CRICKETDATA.ORG - COMPLETED)"
    if m.get("is_abandoned"):
        return "● OFFICIAL LIVE SOURCE (MATCH ABANDONED)"
    return "● OFFICIAL LIVE SOURCE (SCHEDULED)"


# =====================================================================
# 2. UNIT TESTS: CRICKET OVERS & DELIVERY COUNTING PARITY
# =====================================================================

class TestCricketOversMathParity:
    """Validates that cricket overs notation is never treated as a decimal."""

    def test_single_spell_overs_to_balls(self):
        # 0.0 overs = 0 balls
        assert dax_overs_to_balls([0.0]) == 0
        # 0.5 overs = 5 balls
        assert dax_overs_to_balls([0.5]) == 5
        # 1.0 overs = 6 balls
        assert dax_overs_to_balls([1.0]) == 6
        # 2.4 overs = 16 balls
        assert dax_overs_to_balls([2.4]) == 16
        # 19.5 overs = 119 balls (19 * 6 + 5 = 119)
        assert dax_overs_to_balls([19.5]) == 119
        # 20.0 overs = 120 balls
        assert dax_overs_to_balls([20.0]) == 120

    def test_multi_spell_overs_addition_vs_naive_decimal_trap(self):
        """
        Critical test: 2.4 overs (16 balls) + 3.5 overs (23 balls) = 39 balls = 6.3 overs.
        Naive decimal addition would be 2.4 + 3.5 = 5.9 (completely invalid in cricket).
        """
        spells = [2.4, 3.5]
        total_balls = dax_overs_to_balls(spells)
        assert total_balls == 39  # 16 + 23 = 39 balls
        display = dax_balls_to_overs_display(total_balls)
        assert display == "6.3"  # 39 balls = 6 overs and 3 balls (NOT 5.9!)

    def test_decimal_overs_for_rate_formulas(self):
        # 19.5 notation is 119 balls -> 19.8333... decimal overs (NOT 19.5)
        total_balls = dax_overs_to_balls([19.5])
        dec_ov = dax_decimal_overs(total_balls)
        assert math.isclose(dec_ov, 19.833333333333332, rel_tol=1e-5)
        assert dec_ov != 19.5

    def test_balls_to_overs_display_edge_cases(self):
        assert dax_balls_to_overs_display(None) == "0.0"
        assert dax_balls_to_overs_display(0) == "0.0"
        assert dax_balls_to_overs_display(1) == "0.1"
        assert dax_balls_to_overs_display(6) == "1.0"
        assert dax_balls_to_overs_display(7) == "1.1"
        assert dax_balls_to_overs_display(119) == "19.5"
        assert dax_balls_to_overs_display(120) == "20.0"


# =====================================================================
# 3. UNIT TESTS: BATTING & BOWLING METRIC PARITY
# =====================================================================

class TestScorecardMetricsParity:
    """Validates strict NULL vs. zero semantics and ratio calculations."""

    def test_batting_strike_rate_null_vs_duck(self):
        # Did not bat: 0 balls faced -> None (BLANK() in DAX)
        assert dax_batting_strike_rate(runs=0, balls_faced=0) is None
        # Duck: 4 balls faced, 0 runs -> 0.00
        assert dax_batting_strike_rate(runs=0, balls_faced=4) == 0.00
        # Normal innings: 39 runs off 19 balls -> 205.26
        assert dax_batting_strike_rate(runs=39, balls_faced=19) == 205.26

    def test_boundary_runs_and_percentage(self):
        # 0 runs -> 0.0% boundary percentage
        assert dax_boundary_runs(0, 0) == 0
        assert dax_boundary_run_percentage(0, 0, 0) == 0.0

        # Shubman Gill: 39 runs, 7 fours (28 runs), 0 sixes -> 28 boundary runs, 71.79%
        b_runs = dax_boundary_runs(fours=7, sixes=0)
        assert b_runs == 28
        b_pct = dax_boundary_run_percentage(runs=39, fours=7, sixes=0)
        assert b_pct == 71.79

        # Century with mixed boundaries: 100 runs, 10 fours (40), 5 sixes (30) = 70 boundary runs (70.0%)
        assert dax_boundary_runs(10, 5) == 70
        assert dax_boundary_run_percentage(100, 10, 5) == 70.0

    def test_bowling_economy_rate(self):
        # 0 balls bowled -> None (BLANK() in DAX)
        assert dax_bowling_economy(runs_conceded=0, total_balls=0) is None

        # 24 runs in 4.0 overs (24 balls) -> 6.00
        assert dax_bowling_economy(runs_conceded=24, total_balls=24) == 6.00

        # 22 runs in 2.4 overs (16 balls = 2.6667 dec ov) -> 8.25
        assert dax_bowling_economy(runs_conceded=22, total_balls=16) == 8.25

    def test_bowling_average_and_strike_rate_zero_wickets(self):
        # 0 wickets -> None (BLANK() in DAX)
        assert dax_bowling_average(runs_conceded=30, wickets=0) is None
        assert dax_bowling_strike_rate(total_balls=24, wickets=0) is None

        # 2 wickets, 22 runs conceded in 16 balls
        assert dax_bowling_average(runs_conceded=22, wickets=2) == 11.00
        assert dax_bowling_strike_rate(total_balls=16, wickets=2) == 8.00


# =====================================================================
# 4. UNIT TESTS: DATA PROVENANCE BANNER MULTI-STATE ROBUSTNESS
# =====================================================================

class TestDataProvenanceBannerParity:
    """Validates multi-state handling (simulated, live, completed, abandoned, mixed, unknown)."""

    def test_simulated_fixture(self):
        res = dax_data_provenance_banner([{"is_simulated": True, "is_live": True}])
        assert res == "● DEMO / SIMULATED DATA (OFFLINE REPLAY)"

    def test_live_active_match(self):
        res = dax_data_provenance_banner([{"is_simulated": False, "is_live": True}])
        assert res == "● OFFICIAL LIVE SOURCE (CRICKETDATA.ORG - IN PLAY)"

    def test_completed_match(self):
        res = dax_data_provenance_banner([{"is_simulated": False, "is_live": False, "is_completed": True}])
        assert res == "● OFFICIAL LIVE SOURCE (CRICKETDATA.ORG - COMPLETED)"

    def test_abandoned_match(self):
        res = dax_data_provenance_banner([{"is_simulated": False, "is_live": False, "is_abandoned": True}])
        assert res == "● OFFICIAL LIVE SOURCE (MATCH ABANDONED)"

    def test_mixed_provenance_matches(self):
        matches = [
            {"is_simulated": True, "is_live": True},
            {"is_simulated": False, "is_live": True}
        ]
        res = dax_data_provenance_banner(matches)
        assert res == "▲ MIXED DATA PROVENANCE (SELECT SINGLE FIXTURE)"

    def test_unknown_provenance(self):
        assert dax_data_provenance_banner([{"is_simulated": None}]) == "● PROVENANCE UNKNOWN"
        assert dax_data_provenance_banner([]) == "● NO FIXTURE SELECTED"


# =====================================================================
# 5. INTEGRATION PARITY: VALIDATION AGAINST LIVE POSTGRESQL VIEWS
# =====================================================================

class TestPostgreSqlViewsParity:
    """
    Connects to the configured local PostgreSQL database and asserts that
    SQL analytical views compute figures matching the DAX calculation parity.
    """

    @pytest.fixture(scope="module")
    def db_cursor(self):
        config = load_config()
        db = DatabaseRepository(config)
        conn = db.get_connection()
        with conn.cursor() as cur:
            yield cur

    def test_batting_view_columns_parity(self, db_cursor):
        """Validates that v_current_batting_scorecard SQL calculations match DAX formulas."""
        db_cursor.execute("""
            SELECT player_name, runs, balls_faced, fours, sixes, 
                   strike_rate, boundary_runs, boundary_run_percentage
            FROM v_current_batting_scorecard
        """)
        rows = db_cursor.fetchall()
        if not rows:
            pytest.skip("No batting rows present in test database. Run replay to populate.")

        for r in rows:
            runs = r["runs"]
            balls = r["balls_faced"]
            fours = r["fours"]
            sixes = r["sixes"]

            # 1. Boundary runs parity
            expected_b_runs = dax_boundary_runs(fours, sixes)
            assert r["boundary_runs"] == expected_b_runs

            # 2. Boundary percentage parity
            expected_b_pct = dax_boundary_run_percentage(runs, fours, sixes)
            if r["boundary_run_percentage"] is not None:
                assert math.isclose(float(r["boundary_run_percentage"]), expected_b_pct, rel_tol=1e-2)

            # 3. Strike rate parity
            expected_sr = dax_batting_strike_rate(runs, balls)
            if expected_sr is None:
                assert r["strike_rate"] is None
            else:
                assert math.isclose(float(r["strike_rate"]), expected_sr, rel_tol=1e-2)

    def test_bowling_view_columns_parity(self, db_cursor):
        """Validates that v_current_bowling_scorecard SQL calculations match DAX formulas."""
        db_cursor.execute("""
            SELECT player_name, overs_bowled, runs_conceded, wickets, 
                   economy_rate, bowling_average, bowling_strike_rate
            FROM v_current_bowling_scorecard
        """)
        rows = db_cursor.fetchall()
        if not rows:
            pytest.skip("No bowling rows present in test database. Run replay to populate.")

        for r in rows:
            overs = float(r["overs_bowled"])
            runs_c = r["runs_conceded"]
            wkts = r["wickets"]

            total_balls = dax_overs_to_balls([overs])

            # 1. Economy rate parity
            expected_eco = dax_bowling_economy(runs_c, total_balls)
            if expected_eco is None:
                assert r["economy_rate"] is None
            else:
                assert math.isclose(float(r["economy_rate"]), expected_eco, rel_tol=1e-2)

            # 2. Bowling average parity
            expected_avg = dax_bowling_average(runs_c, wkts)
            if expected_avg is None:
                assert r["bowling_average"] is None
            else:
                assert math.isclose(float(r["bowling_average"]), expected_avg, rel_tol=1e-2)

            # 3. Bowling strike rate parity
            expected_sr = dax_bowling_strike_rate(total_balls, wkts)
            if expected_sr is None:
                assert r["bowling_strike_rate"] is None
            else:
                assert math.isclose(float(r["bowling_strike_rate"]), expected_sr, rel_tol=1e-2)
