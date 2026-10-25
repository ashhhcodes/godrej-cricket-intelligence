"""
Deterministic Fixture Replay Simulator.
Plays back pre-recorded historical T20 match fixtures (from Cricsheet)
ball-by-ball or over-by-over, writing consistent, simulated records
marked with is_simulated = TRUE into PostgreSQL.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.db import DatabaseRepository
from src.logger import setup_logger

logger = setup_logger("replay_engine")


class FixtureReplayEngine:
    """
    Deterministic chronological replay engine.
    Advances cricket deliveries and calculates live scorecards, snapshots, and state.
    """

    def __init__(self, fixture_path: Path, db: DatabaseRepository):
        self.fixture_path = Path(fixture_path)
        self.db = db
        self.match_data: Dict[str, Any] = {}
        self.innings_data: List[Dict[str, Any]] = []
        
        # State tracking
        self.current_inning_idx: int = 0
        self.current_over_idx: int = 0
        self.current_ball_idx: int = 0
        self.ball_sequence_counter: int = 0
        self.is_finished: bool = False
        
        # Database IDs
        self.match_db_id: Optional[int] = None
        self.innings_db_ids: Dict[int, int] = {}
        
        # In-memory score tracking for active match
        self.scores: Dict[int, Dict[str, Any]] = {}
        self.batters: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self.bowlers: Dict[int, Dict[str, Dict[str, Any]]] = {}

        self._load_fixture()

    def _load_fixture(self) -> None:
        """Loads and parses the Cricsheet fixture JSON."""
        if not self.fixture_path.exists():
            raise FileNotFoundError(f"Fixture dataset not found at {self.fixture_path}")

        with open(self.fixture_path, "r", encoding="utf-8") as f:
            self.match_data = json.load(f)

        self.innings_data = self.match_data.get("innings", [])
        if not self.innings_data:
            raise ValueError(f"No innings found in fixture {self.fixture_path}")

        logger.info(
            f"Loaded fixture: {self.match_data.get('info', {}).get('event', {}).get('name', 'T20')} "
            f"({len(self.innings_data)} innings available)"
        )

    def initialize_replay(self) -> int:
        """
        Initializes the match in the database, resetting all counters.
        Returns the match primary key id.
        """
        info = self.match_data.get("info", {})
        teams = info.get("teams", ["Team A", "Team B"])
        toss = info.get("toss", {})
        event = info.get("event", {})
        event_name = event.get("name", "T20 Match")
        match_num = event.get("match_number", "1")
        match_name = f"{teams[0]} vs {teams[1]}, {event_name} Match {match_num}"

        dates = info.get("dates", ["2026-10-25"])
        match_date = datetime.strptime(dates[0], "%Y-%m-%d").replace(tzinfo=timezone.utc)

        match_record = {
            "provider_match_id": f"cricsheet-replay-{teams[0][:3]}-{teams[1][:3]}".lower(),
            "series_name": event_name,
            "match_name": match_name,
            "match_type": info.get("match_type", "t20").lower(),
            "competition_category": "IPL" if "ipl" in event_name.lower() else "International",
            "venue": info.get("venue", "Narendra Modi Stadium, Ahmedabad"),
            "match_date_utc": match_date,
            "team_a": teams[0],
            "team_b": teams[1],
            "toss_winner": toss.get("winner"),
            "toss_choice": toss.get("decision"),
            "match_winner": None,
            "result_status": "In Progress (Replay Simulation)",
            "is_live": True,
            "is_completed": False,
            "is_abandoned": False,
            "is_simulated": True,
        }

        self.match_db_id = self.db.upsert_match(match_record)

        # Reset counters
        self.current_inning_idx = 0
        self.current_over_idx = 0
        self.current_ball_idx = 0
        self.ball_sequence_counter = 0
        self.is_finished = False
        self.innings_db_ids.clear()
        self.scores.clear()
        self.batters.clear()
        self.bowlers.clear()

        # Initialize innings 1
        self._init_inning(0)

        logger.info(f"Initialized fixture replay for match_id={self.match_db_id} ('{match_name}')")
        return self.match_db_id

    def _init_inning(self, inning_idx: int) -> None:
        """Initializes state and database record for an innings."""
        inning_data = self.innings_data[inning_idx]
        batting_team = inning_data.get("team", "Batting Team")
        teams = self.match_data.get("info", {}).get("teams", [])
        bowling_team = [t for t in teams if t != batting_team][0] if len(teams) > 1 else "Bowling Team"
        inning_number = inning_idx + 1

        inning_record = {
            "match_id": self.match_db_id,
            "innings_number": inning_number,
            "innings_name": f"{batting_team} Innings {inning_number}",
            "batting_team": batting_team,
            "bowling_team": bowling_team,
            "total_runs": 0,
            "total_wickets": 0,
            "total_overs": 0.0,
            "run_rate": None,
            "extras_total": 0,
            "extras_byes": 0,
            "extras_leg_byes": 0,
            "extras_wides": 0,
            "extras_no_balls": 0,
            "is_declared": False,
            "is_completed": False,
        }

        innings_id = self.db.upsert_innings(inning_record)
        self.innings_db_ids[inning_idx] = innings_id
        self.ball_sequence_counter = 0

        self.scores[inning_idx] = {
            "runs": 0,
            "wickets": 0,
            "legal_balls": 0,
            "extras_total": 0,
            "byes": 0,
            "leg_byes": 0,
            "wides": 0,
            "no_balls": 0,
            "batting_team": batting_team,
            "bowling_team": bowling_team,
        }
        self.batters[inning_idx] = {}
        self.bowlers[inning_idx] = {}

    def step_delivery(self) -> Dict[str, Any]:
        """
        Advances the simulation by exactly one delivery.
        Updates ball_events, score_snapshots, scorecards, and match_state.
        """
        if self.is_finished:
            logger.info("Replay has already completed all innings.")
            return {"status": "completed", "is_finished": True}

        if self.match_db_id is None:
            self.initialize_replay()

        current_inning = self.innings_data[self.current_inning_idx]
        overs = current_inning.get("overs", [])

        if self.current_over_idx >= len(overs):
            # Move to next inning if available
            if self.current_inning_idx + 1 < len(self.innings_data):
                # Mark current inning completed
                prev_innings_id = self.innings_db_ids[self.current_inning_idx]
                prev_score = self.scores[self.current_inning_idx]
                overs_float = self._balls_to_overs(prev_score["legal_balls"])
                self.db.upsert_innings({
                    "match_id": self.match_db_id,
                    "innings_number": self.current_inning_idx + 1,
                    "innings_name": f"{prev_score['batting_team']} Innings {self.current_inning_idx + 1}",
                    "batting_team": prev_score["batting_team"],
                    "bowling_team": prev_score["bowling_team"],
                    "total_runs": prev_score["runs"],
                    "total_wickets": prev_score["wickets"],
                    "total_overs": overs_float,
                    "run_rate": round((prev_score["runs"] / prev_score["legal_balls"]) * 6.0, 2) if prev_score["legal_balls"] > 0 else 0.0,
                    "extras_total": prev_score["extras_total"],
                    "extras_byes": prev_score["byes"],
                    "extras_leg_byes": prev_score["leg_byes"],
                    "extras_wides": prev_score["wides"],
                    "extras_no_balls": prev_score["no_balls"],
                    "is_declared": False,
                    "is_completed": True,
                })

                self.current_inning_idx += 1
                self.current_over_idx = 0
                self.current_ball_idx = 0
                self._init_inning(self.current_inning_idx)
                current_inning = self.innings_data[self.current_inning_idx]
                overs = current_inning.get("overs", [])
            else:
                self.is_finished = True
                self._finalize_match()
                return {"status": "match_completed", "is_finished": True}

        current_over = overs[self.current_over_idx]
        deliveries = current_over.get("deliveries", [])
        delivery = deliveries[self.current_ball_idx]

        # Process Delivery
        self.ball_sequence_counter += 1
        runs_info = delivery.get("runs", {})
        batter_runs = runs_info.get("batter", 0)
        extra_runs = runs_info.get("extras", 0)
        total_runs = runs_info.get("total", 0)

        extras_dict = delivery.get("extras", {})
        is_wide = "wides" in extras_dict
        is_noball = "noballs" in extras_dict
        is_legal = not (is_wide or is_noball)

        extra_type = None
        if is_wide:
            extra_type = "wide"
        elif is_noball:
            extra_type = "no ball"
        elif "byes" in extras_dict:
            extra_type = "bye"
        elif "legbyes" in extras_dict:
            extra_type = "leg bye"

        wickets = delivery.get("wickets", [])
        is_wicket = len(wickets) > 0
        wicket_type = wickets[0].get("kind") if is_wicket else None
        player_dismissed = wickets[0].get("player_out") if is_wicket else None

        batter_name = delivery.get("batter", "Unknown")
        bowler_name = delivery.get("bowler", "Unknown")
        non_striker = delivery.get("non_striker")

        # Update Inning Running Totals
        score = self.scores[self.current_inning_idx]
        score["runs"] += total_runs
        if is_legal:
            score["legal_balls"] += 1
        if is_wicket:
            score["wickets"] += 1

        score["extras_total"] += extra_runs
        if "byes" in extras_dict:
            score["byes"] += extras_dict["byes"]
        if "legbyes" in extras_dict:
            score["leg_byes"] += extras_dict["legbyes"]
        if is_wide:
            score["wides"] += extras_dict["wides"]
        if is_noball:
            score["no_balls"] += extras_dict["noballs"]

        # Update Batter Record
        inning_batters = self.batters[self.current_inning_idx]
        if batter_name not in inning_batters:
            inning_batters[batter_name] = {
                "match_id": self.match_db_id,
                "provider_player_id": f"pid-{batter_name.lower().replace(' ', '-')}",
                "player_name": batter_name,
                "batting_position": len(inning_batters) + 1,
                "dismissal_info": "not out",
                "is_dismissed": False,
                "runs": 0,
                "balls_faced": 0,
                "fours": 0,
                "sixes": 0,
                "strike_rate": None,
            }

        b_stat = inning_batters[batter_name]
        b_stat["runs"] += batter_runs
        if not is_wide:
            b_stat["balls_faced"] += 1
        if batter_runs == 4:
            b_stat["fours"] += 1
        elif batter_runs == 6:
            b_stat["sixes"] += 1

        if is_wicket and player_dismissed == batter_name:
            b_stat["is_dismissed"] = True
            b_stat["dismissal_info"] = f"{wicket_type} b {bowler_name}"

        # Strict NULL vs 0 semantics:
        if b_stat["balls_faced"] == 0:
            b_stat["strike_rate"] = None
        elif b_stat["runs"] == 0:
            b_stat["strike_rate"] = 0.00
        else:
            b_stat["strike_rate"] = round((b_stat["runs"] / b_stat["balls_faced"]) * 100.0, 2)

        # Update Bowler Record
        inning_bowlers = self.bowlers[self.current_inning_idx]
        if bowler_name not in inning_bowlers:
            inning_bowlers[bowler_name] = {
                "match_id": self.match_db_id,
                "provider_player_id": f"pid-{bowler_name.lower().replace(' ', '-')}",
                "player_name": bowler_name,
                "bowling_order": len(inning_bowlers) + 1,
                "legal_balls": 0,
                "overs_bowled": 0.0,
                "maidens": 0,
                "runs_conceded": 0,
                "wickets": 0,
                "economy_rate": None,
                "dots": 0,
                "wides": 0,
                "no_balls": 0,
            }

        bw_stat = inning_bowlers[bowler_name]
        if is_legal:
            bw_stat["legal_balls"] += 1
        bw_stat["runs_conceded"] += total_runs
        if is_wicket and wicket_type != "run out":
            bw_stat["wickets"] += 1
        if total_runs == 0 and is_legal:
            bw_stat["dots"] += 1
        if is_wide:
            bw_stat["wides"] += 1
        if is_noball:
            bw_stat["no_balls"] += 1

        bw_stat["overs_bowled"] = self._balls_to_overs(bw_stat["legal_balls"])
        if bw_stat["overs_bowled"] > 0:
            bw_stat["economy_rate"] = round((bw_stat["runs_conceded"] / bw_stat["legal_balls"]) * 6.0, 2)

        # Database Upserts
        current_innings_id = self.innings_db_ids[self.current_inning_idx]
        current_overs_float = self._balls_to_overs(score["legal_balls"])
        crr = round((score["runs"] / score["legal_balls"]) * 6.0, 2) if score["legal_balls"] > 0 else 0.0

        # 1. Insert Ball Event
        ball_event = {
            "match_id": self.match_db_id,
            "innings_id": current_innings_id,
            "over_number": current_over.get("over", self.current_over_idx),
            "ball_number": self.current_ball_idx + 1,
            "ball_sequence": self.ball_sequence_counter,
            "batter_name": batter_name,
            "bowler_name": bowler_name,
            "non_striker_name": non_striker,
            "runs_batter": batter_runs,
            "runs_extra": extra_runs,
            "extra_type": extra_type,
            "total_ball_runs": total_runs,
            "is_wicket": is_wicket,
            "wicket_type": wicket_type,
            "player_dismissed": player_dismissed,
            "commentary_text": f"{bowler_name} to {batter_name}, {total_runs} run(s)" + (f", OUT! ({wicket_type})" if is_wicket else ""),
            "is_simulated": True,
        }
        self.db.insert_ball_events([ball_event])

        # 2. Update Batting & Bowling Scorecards
        self.db.upsert_batting_scorecard(current_innings_id, list(inning_batters.values()))
        self.db.upsert_bowling_scorecard(current_innings_id, list(inning_bowlers.values()))

        # 3. Insert Score Snapshot at over boundaries or milestones
        if self.current_ball_idx == len(deliveries) - 1 or score["legal_balls"] % 6 == 0:
            snapshot = {
                "match_id": self.match_db_id,
                "innings_id": current_innings_id,
                "snapshot_timestamp_utc": datetime.now(timezone.utc),
                "overs": current_overs_float,
                "runs": score["runs"],
                "wickets": score["wickets"],
                "run_rate": crr,
                "striker_name": batter_name,
                "non_striker_name": non_striker,
                "active_bowler_name": bowler_name,
            }
            self.db.insert_score_snapshot(snapshot)

        # 4. Update Innings
        self.db.upsert_innings({
            "match_id": self.match_db_id,
            "innings_number": self.current_inning_idx + 1,
            "innings_name": f"{score['batting_team']} Innings {self.current_inning_idx + 1}",
            "batting_team": score["batting_team"],
            "bowling_team": score["bowling_team"],
            "total_runs": score["runs"],
            "total_wickets": score["wickets"],
            "total_overs": current_overs_float,
            "run_rate": crr,
            "extras_total": score["extras_total"],
            "extras_byes": score["byes"],
            "extras_leg_byes": score["leg_byes"],
            "extras_wides": score["wides"],
            "extras_no_balls": score["no_balls"],
            "is_declared": False,
            "is_completed": False,
        })

        # 5. Update Match State
        target_runs = (self.scores[0]["runs"] + 1) if self.current_inning_idx > 0 else None
        rrr = None
        if target_runs is not None and score["legal_balls"] < 120:
            balls_left = 120 - score["legal_balls"]
            runs_needed = max(0, target_runs - score["runs"])
            rrr = round((runs_needed / balls_left) * 6.0, 2) if balls_left > 0 else 0.0

        state_summary = (
            f"{score['batting_team']} {score['runs']}/{score['wickets']} "
            f"({current_overs_float} ov) - Replay Simulation"
        )

        self.db.upsert_match_state({
            "match_id": self.match_db_id,
            "current_status_summary": state_summary,
            "current_innings_number": self.current_inning_idx + 1,
            "batting_team": score["batting_team"],
            "bowling_team": score["bowling_team"],
            "current_runs": score["runs"],
            "current_wickets": score["wickets"],
            "current_overs": current_overs_float,
            "current_run_rate": crr,
            "required_run_rate": rrr,
            "target_runs": target_runs,
            "last_api_poll_utc": datetime.now(timezone.utc),
            "last_source_update_utc": datetime.now(timezone.utc),
            "is_live": True,
        })

        # Advance pointer
        self.current_ball_idx += 1
        if self.current_ball_idx >= len(deliveries):
            self.current_over_idx += 1
            self.current_ball_idx = 0

        logger.debug(
            f"Replay Step: Inning {self.current_inning_idx + 1} | Over {current_overs_float} | "
            f"{score['batting_team']} {score['runs']}/{score['wickets']} | {batter_name} ({batter_runs}) vs {bowler_name}"
        )

        return {
            "status": "in_progress",
            "is_finished": False,
            "inning": self.current_inning_idx + 1,
            "overs": current_overs_float,
            "runs": score["runs"],
            "wickets": score["wickets"],
            "crr": crr,
            "batter": batter_name,
            "bowler": bowler_name,
        }

    def _balls_to_overs(self, balls: int) -> float:
        """Converts total legal ball count to overs float (e.g. 19 balls -> 3.1)."""
        overs = balls // 6
        remaining_balls = balls % 6
        return float(f"{overs}.{remaining_balls}")

    def _finalize_match(self) -> None:
        """Marks the match as completed with outcome from fixture."""
        outcome = self.match_data.get("info", {}).get("outcome", {})
        winner = outcome.get("winner")
        by_info = outcome.get("by", {})
        method = outcome.get("result", "")

        status_text = f"{winner} won"
        if "wickets" in by_info:
            status_text += f" by {by_info['wickets']} wickets"
        elif "runs" in by_info:
            status_text += f" by {by_info['runs']} runs"
        if method:
            status_text += f" ({method})"

        sql = """
        UPDATE matches SET
            match_winner = %s,
            result_status = %s,
            is_live = FALSE,
            is_completed = TRUE,
            updated_at_utc = NOW()
        WHERE id = %s;
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (winner, status_text, self.match_db_id))
            conn.commit()

        logger.info(f"Replay finalized for match_id={self.match_db_id}: {status_text}")
