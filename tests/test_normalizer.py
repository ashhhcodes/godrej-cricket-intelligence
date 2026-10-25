"""
Unit tests for data normalizer and semantic validation.
Validates NULL vs Zero handling, lifecycle transitions, and malformed field resilience.
"""

import json
from pathlib import Path
import pytest
from src.normalizer import (
    normalize_match_info,
    normalize_match_state,
    normalize_scorecard,
    parse_utc_timestamp,
    determine_match_lifecycle,
    classify_competition,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def current_matches_json():
    with open(FIXTURES_DIR / "cricapi_current_matches.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def match_scorecard_json():
    with open(FIXTURES_DIR / "cricapi_match_scorecard.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def completed_match_json():
    with open(FIXTURES_DIR / "cricapi_completed_match.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def abandoned_match_json():
    with open(FIXTURES_DIR / "cricapi_abandoned_match.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def malformed_json():
    with open(FIXTURES_DIR / "cricapi_malformed.json", "r", encoding="utf-8") as f:
        return json.load(f)


class TestNormalizerSemantics:

    def test_null_vs_zero_semantics_batting(self, match_scorecard_json):
        """
        Verify that:
        1. A batter who did not face a ball (balls_faced = 0) has strike_rate = None (NULL).
        2. A batter who faced balls but scored 0 has strike_rate = 0.00 (genuine zero).
        3. A batter who scored runs has a properly calculated strike rate.
        """
        innings, batters, bowlers = normalize_scorecard(match_scorecard_json, match_id_fk=1)

        # Glenn Maxwell: 0 runs off 3 balls -> strike_rate MUST be 0.00
        maxwell = [b for b in batters if "Maxwell" in b["player_name"]][0]
        assert maxwell["runs"] == 0
        assert maxwell["balls_faced"] == 3
        assert maxwell["strike_rate"] == 0.00, "Faced 3 balls with 0 runs must be genuine 0.00 strike rate"

        # Pat Cummins: did not bat (0 runs, 0 balls) -> strike_rate MUST be None (NULL)
        cummins = [b for b in batters if "Cummins" in b["player_name"]][0]
        assert cummins["runs"] == 0
        assert cummins["balls_faced"] == 0
        assert cummins["strike_rate"] is None, "0 balls faced must result in strike_rate = None (NULL), never 0.00"

        # Travis Head: 35 runs off 18 balls -> strike_rate ~ 194.44
        head = [b for b in batters if "Head" in b["player_name"]][0]
        assert head["runs"] == 35
        assert head["balls_faced"] == 18
        assert head["strike_rate"] == 194.44

    def test_null_vs_zero_semantics_bowling(self, match_scorecard_json):
        """
        Verify that bowler figures have proper economy rates and NULL handling.
        """
        innings, batters, bowlers = normalize_scorecard(match_scorecard_json, match_id_fk=1)

        bumrah = [bw for bw in bowlers if "Bumrah" in bw["player_name"]][0]
        assert bumrah["overs_bowled"] == 3.3
        assert bumrah["wickets"] == 1
        assert bumrah["maidens"] == 0
        assert bumrah["economy_rate"] is not None

        # Synthesize a bowler who bowled 0 overs
        zero_over_bowler = {
            "data": {
                "scorecard": [
                    {
                        "inning": "Test Inning",
                        "bowling": [{"bowler": "Non Bowler", "o": 0.0, "r": 0, "w": 0}]
                    }
                ]
            }
        }
        _, _, bowlers_zero = normalize_scorecard(zero_over_bowler, match_id_fk=1)
        assert bowlers_zero[0]["economy_rate"] is None, "0 overs bowled must result in economy_rate = None (NULL)"

    def test_utc_timestamp_parsing(self):
        """Verify strict timezone-aware UTC datetime parsing across various date formats."""
        dt1 = parse_utc_timestamp("2026-10-25T13:30:00Z")
        assert dt1.year == 2026 and dt1.month == 10 and dt1.day == 25
        assert dt1.tzinfo is not None

        dt2 = parse_utc_timestamp("2026-10-25 14:00:00")
        assert dt2.hour == 14 and dt2.tzinfo is not None

        # Fallback on invalid string
        dt3 = parse_utc_timestamp("garbage_timestamp")
        assert dt3 is not None and dt3.tzinfo is not None

    def test_lifecycle_states(self, completed_match_json, abandoned_match_json, current_matches_json):
        """Verify correct classification of live, completed, upcoming, and abandoned matches."""
        # Completed
        completed_match = normalize_match_info(completed_match_json)
        assert completed_match["is_completed"] is True
        assert completed_match["is_live"] is False
        assert completed_match["is_abandoned"] is False

        # Abandoned
        abandoned_match = normalize_match_info(abandoned_match_json)
        assert abandoned_match["is_abandoned"] is True
        assert abandoned_match["is_completed"] is False
        assert abandoned_match["is_live"] is False

        # Live / Scheduled
        live_item = current_matches_json["data"][0]
        live_match = normalize_match_info(live_item)
        assert live_match["is_live"] is True
        assert live_match["is_completed"] is False

    def test_malformed_json_resilience(self, malformed_json):
        """Verify the normalizer does not crash when encountering malformed fields and data types."""
        # Should not raise exception
        normalized_match = normalize_match_info(malformed_json)
        assert normalized_match["provider_match_id"] == "cricapi-malformed-005"
        assert normalized_match["match_name"] == "Broken Payload Match"

        normalized_state = normalize_match_state(malformed_json, match_id_fk=99, is_live=False)
        assert normalized_state["current_runs"] is None

        innings, batters, bowlers = normalize_scorecard(malformed_json, match_id_fk=99)
        assert len(batters) == 1
        assert batters[0]["runs"] == 0
        assert batters[0]["strike_rate"] is None

    def test_competition_classification(self):
        """Verify competition format classification heuristics."""
        assert classify_competition("Chennai Super Kings vs Mumbai Indians", "IPL 2026") == "IPL"
        assert classify_competition("India vs Pakistan", "ICC T20 World Cup") == "International"
        assert classify_competition("Mumbai vs Karnataka", "Ranji Trophy 2026") == "Domestic"
        assert classify_competition("Club A vs Club B", "Local League") == "Other"
