"""
PostgreSQL database repository module using psycopg v3.
Implements idempotent upsert operations, versioned schema migration execution,
and safe transaction lifecycle management with connection reuse.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import psycopg
from psycopg.rows import dict_row
from src.config import AppConfig
from src.logger import setup_logger

logger = setup_logger("db_repository")


class DatabaseRepository:
    """
    Manages PostgreSQL connections, schema migrations, and idempotent upserts.
    """

    def __init__(self, config: AppConfig, conn: Optional[psycopg.Connection] = None):
        self.config = config
        self._conn = conn

    def get_connection(self) -> psycopg.Connection:
        """
        Creates or returns an active PostgreSQL connection with dict_row factory.
        """
        if self._conn is not None:
            if getattr(self._conn, "closed", False) is not True:
                return self._conn

        try:
            logger.info(
                f"Establishing PostgreSQL connection to {self.config.postgres_host}:{self.config.postgres_port}/{self.config.postgres_db}"
            )
            self._conn = psycopg.connect(
                self.config.postgres_connection_string,
                row_factory=dict_row,
                autocommit=False
            )
            return self._conn
        except psycopg.Error as e:
            logger.error(f"PostgreSQL connection failure: {e}")
            raise

    def close(self) -> None:
        """Closes the active database connection if open."""
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
            logger.info("PostgreSQL connection closed.")

    def test_connection(self) -> bool:
        """Verifies database connectivity by executing SELECT 1."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS alive;")
                row = cur.fetchone()
                return bool(row and row["alive"] == 1)
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            return False

    def apply_migrations(self, sql_dir: Path) -> List[str]:
        """
        Executes all .sql migration files in lexicographical order.
        """
        applied = []
        if not sql_dir.exists():
            raise FileNotFoundError(f"Migrations directory not found: {sql_dir}")

        sql_files = sorted(sql_dir.glob("*.sql"))
        if not sql_files:
            logger.warning(f"No .sql files found in {sql_dir}")
            return applied

        conn = self.get_connection()
        with conn.cursor() as cur:
            for sql_file in sql_files:
                logger.info(f"Applying migration: {sql_file.name}")
                sql_content = sql_file.read_text(encoding="utf-8")
                cur.execute(sql_content)
                applied.append(sql_file.name)
        conn.commit()
        logger.info(f"Successfully applied {len(applied)} migrations.")
        return applied

    # =========================================================================
    # Idempotent Upsert Operations
    # =========================================================================

    def upsert_match(self, match: Dict[str, Any]) -> int:
        """
        Idempotently inserts or updates a match master record.
        Returns the internal primary key id.
        """
        sql = """
        INSERT INTO matches (
            provider_match_id, series_name, match_name, match_type,
            competition_category, venue, match_date_utc, team_a, team_b,
            toss_winner, toss_choice, match_winner, result_status,
            is_live, is_completed, is_abandoned, is_simulated, updated_at_utc
        ) VALUES (
            %(provider_match_id)s, %(series_name)s, %(match_name)s, %(match_type)s,
            %(competition_category)s, %(venue)s, %(match_date_utc)s, %(team_a)s, %(team_b)s,
            %(toss_winner)s, %(toss_choice)s, %(match_winner)s, %(result_status)s,
            %(is_live)s, %(is_completed)s, %(is_abandoned)s, %(is_simulated)s, NOW()
        )
        ON CONFLICT (provider_match_id) DO UPDATE SET
            series_name          = EXCLUDED.series_name,
            match_name           = EXCLUDED.match_name,
            venue                = EXCLUDED.venue,
            toss_winner          = EXCLUDED.toss_winner,
            toss_choice          = EXCLUDED.toss_choice,
            match_winner         = EXCLUDED.match_winner,
            result_status        = EXCLUDED.result_status,
            is_live              = EXCLUDED.is_live,
            is_completed         = EXCLUDED.is_completed,
            is_abandoned         = EXCLUDED.is_abandoned,
            updated_at_utc       = NOW()
        RETURNING id;
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, match)
            row = cur.fetchone()
            match_id = row["id"]
        conn.commit()
        return match_id

    def upsert_match_state(self, state: Dict[str, Any]) -> None:
        """
        Idempotently updates the single active state row for a match.
        """
        sql = """
        INSERT INTO match_state (
            match_id, current_status_summary, current_innings_number,
            batting_team, bowling_team, current_runs, current_wickets,
            current_overs, current_run_rate, required_run_rate, target_runs,
            last_api_poll_utc, last_source_update_utc, is_live, updated_at_utc
        ) VALUES (
            %(match_id)s, %(current_status_summary)s, %(current_innings_number)s,
            %(batting_team)s, %(bowling_team)s, %(current_runs)s, %(current_wickets)s,
            %(current_overs)s, %(current_run_rate)s, %(required_run_rate)s, %(target_runs)s,
            %(last_api_poll_utc)s, %(last_source_update_utc)s, %(is_live)s, NOW()
        )
        ON CONFLICT (match_id) DO UPDATE SET
            current_status_summary = EXCLUDED.current_status_summary,
            current_innings_number = EXCLUDED.current_innings_number,
            batting_team           = EXCLUDED.batting_team,
            bowling_team           = EXCLUDED.bowling_team,
            current_runs           = EXCLUDED.current_runs,
            current_wickets        = EXCLUDED.current_wickets,
            current_overs          = EXCLUDED.current_overs,
            current_run_rate       = EXCLUDED.current_run_rate,
            required_run_rate      = EXCLUDED.required_run_rate,
            target_runs            = EXCLUDED.target_runs,
            last_api_poll_utc      = EXCLUDED.last_api_poll_utc,
            last_source_update_utc = EXCLUDED.last_source_update_utc,
            is_live                = EXCLUDED.is_live,
            updated_at_utc         = NOW();
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, state)
        conn.commit()

    def upsert_innings(self, innings: Dict[str, Any]) -> int:
        """
        Idempotently inserts or updates an innings record.
        Returns the innings primary key id.
        """
        sql = """
        INSERT INTO innings (
            match_id, innings_number, innings_name, batting_team, bowling_team,
            total_runs, total_wickets, total_overs, run_rate,
            extras_total, extras_byes, extras_leg_byes, extras_wides, extras_no_balls,
            is_declared, is_completed, updated_at_utc
        ) VALUES (
            %(match_id)s, %(innings_number)s, %(innings_name)s, %(batting_team)s, %(bowling_team)s,
            %(total_runs)s, %(total_wickets)s, %(total_overs)s, %(run_rate)s,
            %(extras_total)s, %(extras_byes)s, %(extras_leg_byes)s, %(extras_wides)s, %(extras_no_balls)s,
            %(is_declared)s, %(is_completed)s, NOW()
        )
        ON CONFLICT (match_id, innings_number) DO UPDATE SET
            total_runs       = EXCLUDED.total_runs,
            total_wickets    = EXCLUDED.total_wickets,
            total_overs      = EXCLUDED.total_overs,
            run_rate         = EXCLUDED.run_rate,
            extras_total     = EXCLUDED.extras_total,
            extras_byes      = EXCLUDED.extras_byes,
            extras_leg_byes  = EXCLUDED.extras_leg_byes,
            extras_wides     = EXCLUDED.extras_wides,
            extras_no_balls  = EXCLUDED.extras_no_balls,
            is_completed     = EXCLUDED.is_completed,
            updated_at_utc   = NOW()
        RETURNING id;
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, innings)
            row = cur.fetchone()
            innings_id = row["id"]
        conn.commit()
        return innings_id

    def upsert_batting_scorecard(self, innings_id: int, batters: List[Dict[str, Any]]) -> None:
        """
        Idempotently inserts or updates batter scorecard rows.
        """
        if not batters:
            return

        sql = """
        INSERT INTO batting_scorecard (
            innings_id, match_id, provider_player_id, player_name,
            batting_position, dismissal_info, is_dismissed, runs,
            balls_faced, fours, sixes, strike_rate, updated_at_utc
        ) VALUES (
            %(innings_id)s, %(match_id)s, %(provider_player_id)s, %(player_name)s,
            %(batting_position)s, %(dismissal_info)s, %(is_dismissed)s, %(runs)s,
            %(balls_faced)s, %(fours)s, %(sixes)s, %(strike_rate)s, NOW()
        )
        ON CONFLICT (innings_id, provider_player_id) DO UPDATE SET
            batting_position = EXCLUDED.batting_position,
            dismissal_info   = EXCLUDED.dismissal_info,
            is_dismissed     = EXCLUDED.is_dismissed,
            runs             = EXCLUDED.runs,
            balls_faced      = EXCLUDED.balls_faced,
            fours            = EXCLUDED.fours,
            sixes            = EXCLUDED.sixes,
            strike_rate      = EXCLUDED.strike_rate,
            updated_at_utc   = NOW();
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            for b in batters:
                payload = dict(b)
                payload["innings_id"] = innings_id
                cur.execute(sql, payload)
        conn.commit()

    def upsert_bowling_scorecard(self, innings_id: int, bowlers: List[Dict[str, Any]]) -> None:
        """
        Idempotently inserts or updates bowler scorecard rows.
        """
        if not bowlers:
            return

        sql = """
        INSERT INTO bowling_scorecard (
            innings_id, match_id, provider_player_id, player_name,
            bowling_order, overs_bowled, maidens, runs_conceded,
            wickets, economy_rate, dots, wides, no_balls, updated_at_utc
        ) VALUES (
            %(innings_id)s, %(match_id)s, %(provider_player_id)s, %(player_name)s,
            %(bowling_order)s, %(overs_bowled)s, %(maidens)s, %(runs_conceded)s,
            %(wickets)s, %(economy_rate)s, %(dots)s, %(wides)s, %(no_balls)s, NOW()
        )
        ON CONFLICT (innings_id, provider_player_id) DO UPDATE SET
            bowling_order  = EXCLUDED.bowling_order,
            overs_bowled   = EXCLUDED.overs_bowled,
            maidens        = EXCLUDED.maidens,
            runs_conceded  = EXCLUDED.runs_conceded,
            wickets        = EXCLUDED.wickets,
            economy_rate   = EXCLUDED.economy_rate,
            dots           = EXCLUDED.dots,
            wides          = EXCLUDED.wides,
            no_balls       = EXCLUDED.no_balls,
            updated_at_utc = NOW();
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            for bw in bowlers:
                payload = dict(bw)
                payload["innings_id"] = innings_id
                cur.execute(sql, payload)
        conn.commit()

    def insert_score_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Inserts a periodic progress snapshot. Duplicate over entries for the same
        innings are ignored via ON CONFLICT DO NOTHING to prevent duplicate worm points.
        """
        sql = """
        INSERT INTO score_snapshots (
            match_id, innings_id, snapshot_timestamp_utc, overs,
            runs, wickets, run_rate, striker_name, non_striker_name,
            active_bowler_name, created_at_utc
        ) VALUES (
            %(match_id)s, %(innings_id)s, %(snapshot_timestamp_utc)s, %(overs)s,
            %(runs)s, %(wickets)s, %(run_rate)s, %(striker_name)s, %(non_striker_name)s,
            %(active_bowler_name)s, NOW()
        )
        ON CONFLICT (innings_id, overs) DO UPDATE SET
            runs        = EXCLUDED.runs,
            wickets     = EXCLUDED.wickets,
            run_rate    = EXCLUDED.run_rate;
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, snapshot)
        conn.commit()

    def insert_ball_events(self, events: List[Dict[str, Any]]) -> None:
        """
        Inserts granular ball delivery events. Preserves idempotency via
        ON CONFLICT (innings_id, ball_sequence) DO NOTHING.
        """
        if not events:
            return

        sql = """
        INSERT INTO ball_events (
            match_id, innings_id, over_number, ball_number, ball_sequence,
            batter_name, bowler_name, non_striker_name, runs_batter,
            runs_extra, extra_type, total_ball_runs, is_wicket,
            wicket_type, player_dismissed, commentary_text, is_simulated, created_at_utc
        ) VALUES (
            %(match_id)s, %(innings_id)s, %(over_number)s, %(ball_number)s, %(ball_sequence)s,
            %(batter_name)s, %(bowler_name)s, %(non_striker_name)s, %(runs_batter)s,
            %(runs_extra)s, %(extra_type)s, %(total_ball_runs)s, %(is_wicket)s,
            %(wicket_type)s, %(player_dismissed)s, %(commentary_text)s, %(is_simulated)s, NOW()
        )
        ON CONFLICT (innings_id, ball_sequence) DO NOTHING;
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            for ev in events:
                cur.execute(sql, ev)
        conn.commit()

    def record_api_usage(self, telemetry: Dict[str, Any]) -> None:
        """
        Appends an API request audit record to api_usage table.
        """
        sql = """
        INSERT INTO api_usage (
            timestamp_utc, endpoint, http_status, credits_consumed,
            hits_today, hits_limit, credits_remaining, response_time_ms,
            match_id_queried, status_message
        ) VALUES (
            %(timestamp_utc)s, %(endpoint)s, %(http_status)s, %(credits_consumed)s,
            %(hits_today)s, %(hits_limit)s, %(credits_remaining)s, %(response_time_ms)s,
            %(match_id_queried)s, %(status_message)s
        );
        """
        conn = self.get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, telemetry)
        conn.commit()
