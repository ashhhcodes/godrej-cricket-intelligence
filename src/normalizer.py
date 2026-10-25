"""
Data normalization and validation engine.
Parses raw CricAPI payloads into structured, database-ready dictionaries
enforcing strict NULL versus zero semantics and timezone-aware UTC timestamps.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from src.logger import setup_logger

logger = setup_logger("normalizer")


def parse_utc_timestamp(val: Any) -> datetime:
    """
    Safely parses diverse date/time strings into a timezone-aware UTC datetime.
    Falls back to current UTC time if unparseable.
    """
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)

    if not val or not isinstance(val, str):
        return datetime.now(timezone.utc)

    # Clean ISO strings (e.g. 2026-10-25T13:30:00)
    cleaned = val.strip().replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(cleaned, fmt)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    logger.warning(f"Unable to parse timestamp '{val}'. Defaulting to current UTC time.")
    return datetime.now(timezone.utc)


def safe_int(val: Any, default: Optional[int] = 0) -> Optional[int]:
    """Safely coerces value to integer; returns default on failure."""
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely coerces value to float; returns default on failure."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def overs_to_balls(overs: float) -> int:
    """Converts cricket overs representation (e.g. 3.4) to actual ball count (22 balls)."""
    full_overs = int(overs)
    partial_balls = int(round((overs - full_overs) * 10))
    return (full_overs * 6) + partial_balls


def determine_match_lifecycle(status: Optional[str]) -> Tuple[bool, bool, bool]:
    """
    Determines (is_live, is_completed, is_abandoned) based on match status text.
    """
    if not status:
        return False, False, False

    s = status.lower()

    if any(k in s for k in ("abandon", "no result", "cancelled", "washed out")):
        return False, False, True

    if any(k in s for k in ("won by", "won the", "tie", "tied", "draw", "match drawn")):
        return False, True, False

    if any(k in s for k in ("opt to", "need", "trail by", "lead by", "innings break", "lunch", "tea", "stumps", "drinks")):
        return True, False, False

    if any(k in s for k in ("starts at", "match starts", "upcoming", "scheduled")):
        return False, False, False

    # Default heuristic: if status exists but match not over, treat as live
    return True, False, False


def classify_competition(match_name: str, series_name: Optional[str]) -> str:
    """Classifies match format into 'IPL', 'International', 'Domestic', or 'Other'."""
    combined = f"{match_name} {series_name or ''}".lower()
    if "ipl" in combined or "indian premier league" in combined:
        return "IPL"
    if any(k in combined for k in ("ranji", "syed mushtaq", "vijay hazare", "smat", "blast", "shield", "duleep", "deodhar")):
        return "Domestic"
    if any(k in combined for k in ("t20i", "odi", "test", "world cup", "asia cup", "champions trophy", "tour of")):
        return "International"
    return "Other"


def normalize_match_info(raw_data: Dict[str, Any], is_simulated: bool = False) -> Dict[str, Any]:
    """
    Normalizes match metadata from /match_info or /currentMatches item.
    """
    data = raw_data.get("data", raw_data)
    match_id = str(data.get("id") or data.get("unique_id") or "unknown_match")
    match_name = data.get("name") or "Unknown Match"
    series_name = data.get("series_name") or data.get("series_id")
    status_text = data.get("status") or "Scheduled"

    teams = data.get("teams") or []
    team_a = teams[0] if len(teams) > 0 else "Team A"
    team_b = teams[1] if len(teams) > 1 else "Team B"

    is_live, is_completed, is_abandoned = determine_match_lifecycle(status_text)
    match_date_utc = parse_utc_timestamp(data.get("dateTimeGMT") or data.get("date"))

    return {
        "provider_match_id": match_id,
        "series_name": series_name,
        "match_name": match_name,
        "match_type": (data.get("matchType") or "t20").lower(),
        "competition_category": classify_competition(match_name, series_name),
        "venue": data.get("venue"),
        "match_date_utc": match_date_utc,
        "team_a": team_a,
        "team_b": team_b,
        "toss_winner": data.get("tossWinner"),
        "toss_choice": data.get("tossChoice"),
        "match_winner": data.get("matchWinner"),
        "result_status": status_text,
        "is_live": is_live,
        "is_completed": is_completed,
        "is_abandoned": is_abandoned,
        "is_simulated": is_simulated,
    }


def normalize_match_state(raw_data: Dict[str, Any], match_id_fk: int, is_live: bool) -> Dict[str, Any]:
    """
    Normalizes real-time single-row state for match_state table.
    """
    data = raw_data.get("data", raw_data)
    status_text = data.get("status") or "In Progress"
    score_list = data.get("score") or []

    current_runs = None
    current_wickets = None
    current_overs = None
    current_innings_number = None
    batting_team = None
    bowling_team = None
    current_run_rate = None

    if isinstance(score_list, list) and len(score_list) > 0:
        latest_score = score_list[-1]
        current_runs = safe_int(latest_score.get("r"))
        current_wickets = safe_int(latest_score.get("w"))
        current_overs = safe_float(latest_score.get("o"))
        current_innings_number = len(score_list)
        inning_name = latest_score.get("inning", "")

        teams = data.get("teams") or []
        if teams:
            for t in teams:
                if t.lower() in inning_name.lower():
                    batting_team = t
                    bowling_team = [x for x in teams if x != t][0] if len(teams) > 1 else None
                    break

        # Compute CRR if overs > 0
        if current_runs is not None and current_overs and current_overs > 0.0:
            balls = overs_to_balls(current_overs)
            if balls > 0:
                current_run_rate = round((current_runs / balls) * 6.0, 2)

    return {
        "match_id": match_id_fk,
        "current_status_summary": status_text,
        "current_innings_number": current_innings_number,
        "batting_team": batting_team,
        "bowling_team": bowling_team,
        "current_runs": current_runs,
        "current_wickets": current_wickets,
        "current_overs": current_overs,
        "current_run_rate": current_run_rate,
        "required_run_rate": None,
        "target_runs": None,
        "last_api_poll_utc": datetime.now(timezone.utc),
        "last_source_update_utc": parse_utc_timestamp(data.get("dateTimeGMT")),
        "is_live": is_live,
    }


def normalize_scorecard(
    raw_data: Dict[str, Any],
    match_id_fk: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Normalizes innings, batting scorecard, and bowling scorecard.
    Strictly guarantees:
      - strike_rate is NULL if balls_faced == 0
      - strike_rate is 0.0 if balls_faced > 0 and runs == 0
      - economy_rate is NULL if overs_bowled == 0.0
    """
    data = raw_data.get("data", raw_data)
    raw_scorecards = data.get("scorecard") or []

    innings_list = []
    batting_list = []
    bowling_list = []

    if not isinstance(raw_scorecards, list):
        return innings_list, batting_list, bowling_list

    for idx, raw_inning in enumerate(raw_scorecards, start=1):
        inning_name = raw_inning.get("inning") or f"Innings {idx}"
        teams = data.get("teams") or []
        batting_team = "Team Batting"
        bowling_team = "Team Bowling"

        for t in teams:
            if t.lower() in inning_name.lower():
                batting_team = t
                bowling_team = [x for x in teams if x != t][0] if len(teams) > 1 else "Opponent"
                break

        # Inning Totals
        extras_data = raw_inning.get("extras") or {}
        extras_total = safe_int(extras_data.get("r"), default=0)
        extras_byes = safe_int(extras_data.get("b"), default=0)
        extras_leg_byes = safe_int(extras_data.get("lb"), default=0)
        extras_wides = safe_int(extras_data.get("w"), default=0)
        extras_no_balls = safe_int(extras_data.get("nb"), default=0)

        # Compute totals from batting or matching score summary
        total_runs = 0
        total_wickets = 0
        total_overs = 0.0

        score_list = data.get("score") or []
        if isinstance(score_list, list) and len(score_list) >= idx:
            matching_score = score_list[idx - 1]
            total_runs = safe_int(matching_score.get("r"), default=0)
            total_wickets = safe_int(matching_score.get("w"), default=0)
            total_overs = safe_float(matching_score.get("o"), default=0.0)

        inning_dict = {
            "match_id": match_id_fk,
            "innings_number": idx,
            "innings_name": inning_name,
            "batting_team": batting_team,
            "bowling_team": bowling_team,
            "total_runs": total_runs,
            "total_wickets": total_wickets,
            "total_overs": total_overs,
            "run_rate": round((total_runs / overs_to_balls(total_overs)) * 6.0, 2) if total_overs > 0 else None,
            "extras_total": extras_total,
            "extras_byes": extras_byes,
            "extras_leg_byes": extras_leg_byes,
            "extras_wides": extras_wides,
            "extras_no_balls": extras_no_balls,
            "is_declared": False,
            "is_completed": idx < len(score_list),
        }
        innings_list.append(inning_dict)

        # Batters
        raw_batters = raw_inning.get("batting") or []
        for pos, b in enumerate(raw_batters, start=1):
            player_name = b.get("batsman") or b.get("name") or "Unknown Batter"
            pid = b.get("pid") or b.get("id") or f"pid-{player_name.lower().replace(' ', '-')}"
            dismissal = b.get("dismissal-info") or b.get("dismissal")
            is_dismissed = bool(dismissal and dismissal.strip().lower() != "not out")

            runs = safe_int(b.get("r"), default=0)
            balls = safe_int(b.get("b"), default=0)
            fours = safe_int(b.get("4s"), default=0)
            sixes = safe_int(b.get("6s"), default=0)

            # Strict NULL vs 0 semantics for strike rate:
            strike_rate: Optional[float] = None
            if balls == 0:
                strike_rate = None  # Did not bat / faced 0 balls -> strike rate is mathematically undefined
            elif runs == 0:
                strike_rate = 0.00  # Faced balls but scored 0 runs -> genuine zero strike rate
            else:
                strike_rate = round((runs / balls) * 100.0, 2)

            batting_list.append({
                "match_id": match_id_fk,
                "innings_number": idx,
                "provider_player_id": str(pid),
                "player_name": player_name,
                "batting_position": pos,
                "dismissal_info": dismissal,
                "is_dismissed": is_dismissed,
                "runs": runs,
                "balls_faced": balls,
                "fours": fours,
                "sixes": sixes,
                "strike_rate": strike_rate,
            })

        # Bowlers
        raw_bowlers = raw_inning.get("bowling") or []
        for order, bw in enumerate(raw_bowlers, start=1):
            bowler_name = bw.get("bowler") or bw.get("name") or "Unknown Bowler"
            pid = bw.get("pid") or bw.get("id") or f"pid-{bowler_name.lower().replace(' ', '-')}"

            overs = safe_float(bw.get("o"), default=0.0)
            maidens = safe_int(bw.get("m"), default=0)
            runs_conceded = safe_int(bw.get("r"), default=0)
            wickets = safe_int(bw.get("w"), default=0)
            dots = safe_int(bw.get("d"), default=None)  # None if provider did not supply dots

            # Strict NULL vs 0 semantics for economy rate:
            economy_rate: Optional[float] = None
            if overs == 0.0:
                economy_rate = None  # 0 overs bowled -> economy rate is undefined
            else:
                balls_bowled = overs_to_balls(overs)
                economy_rate = round((runs_conceded / balls_bowled) * 6.0, 2) if balls_bowled > 0 else None

            bowling_list.append({
                "match_id": match_id_fk,
                "innings_number": idx,
                "provider_player_id": str(pid),
                "player_name": bowler_name,
                "bowling_order": order,
                "overs_bowled": overs,
                "maidens": maidens,
                "runs_conceded": runs_conceded,
                "wickets": wickets,
                "economy_rate": economy_rate,
                "dots": dots,
                "wides": safe_int(bw.get("wides"), default=0),
                "no_balls": safe_int(bw.get("noballs"), default=0),
            })

    return innings_list, batting_list, bowling_list
