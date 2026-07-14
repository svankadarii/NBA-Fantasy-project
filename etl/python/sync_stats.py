"""
Pulls player box score stats for a given date from nba_api (stats.nba.com,
unofficial) and upserts them into player_game_stats. Matched against games
already loaded into Postgres by the Node ETL (balldontlie.io), since
balldontlie's Free tier doesn't include the stats endpoint.

Usage:
    python sync_stats.py                # defaults to yesterday
    python sync_stats.py --date 2026-01-15
"""

import argparse
import time
from datetime import date, timedelta

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder, boxscoretraditionalv3

from db import get_connection
from name_utils import normalize_name


def clean(v):
    """Coerce pandas/numpy NaN and numpy scalar types to plain Python values
    psycopg2 can bind directly."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def call_with_retries(fn, retries=3, backoff=2):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:  # nba_api/stats.nba.com is flaky, worth retrying
            last_err = e
            print(f"    attempt {attempt}/{retries} failed: {e}")
            time.sleep(backoff * attempt)
    raise last_err


def get_our_games_for_date(conn, game_date):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT g.id, g.home_team_id, ht.abbreviation, g.visitor_team_id, vt.abbreviation
        FROM games g
        JOIN teams ht ON ht.id = g.home_team_id
        JOIN teams vt ON vt.id = g.visitor_team_id
        WHERE g.date = %s
        """,
        (game_date,),
    )
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "id": r[0],
            "home_team_id": r[1],
            "home_abbr": r[2],
            "visitor_team_id": r[3],
            "visitor_abbr": r[4],
        }
        for r in rows
    ]


def build_player_lookup(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, first_name, last_name FROM players")
    lookup = {}
    for pid, first, last in cur.fetchall():
        key = normalize_name(f"{first} {last}")
        if key in lookup:
            print(f"  Warning: duplicate normalized name '{key}' (player ids {lookup[key]} and {pid})")
        lookup[key] = pid
    cur.close()
    return lookup


def fetch_nba_games_for_date(game_date_str):
    """Returns {(home_abbr, visitor_abbr): nba_api_game_id} for the given date."""

    def _fetch():
        result = leaguegamefinder.LeagueGameFinder(
            date_from_nullable=game_date_str,
            date_to_nullable=game_date_str,
            league_id_nullable="00",
            timeout=30,
        )
        return result.get_data_frames()[0]

    df = call_with_retries(_fetch)
    mapping = {}
    for game_id, group in df.groupby("GAME_ID"):
        if len(group) != 2:
            continue
        home_row = group[group["MATCHUP"].str.contains("vs.", regex=False)]
        away_row = group[group["MATCHUP"].str.contains("@", regex=False)]
        if home_row.empty or away_row.empty:
            continue
        home_abbr = home_row.iloc[0]["TEAM_ABBREVIATION"]
        away_abbr = away_row.iloc[0]["TEAM_ABBREVIATION"]
        mapping[(home_abbr, away_abbr)] = game_id
    return mapping


def _parse_minutes(val):
    """V3 returns minutes as ISO duration (PT32M14.00S) or MM:SS — store as-is."""
    if val is None:
        return None
    s = str(val)
    # Convert ISO 8601 duration PT##M##.##S → MM:SS
    if s.startswith("PT"):
        s = s[2:]  # strip PT
        m, _, rest = s.partition("M")
        sec = rest.rstrip("S").split(".")[0]
        return f"{int(m):02d}:{int(sec):02d}"
    return s


def fetch_box_score(nba_game_id):
    def _fetch():
        bs = boxscoretraditionalv3.BoxScoreTraditionalV3(game_id=nba_game_id, timeout=30)
        return bs.get_data_frames()[0]  # PlayerStats

    return call_with_retries(_fetch)


UPSERT_SQL = """
    INSERT INTO player_game_stats
        (player_id, game_id, team_id, min, pts, ast, reb, oreb, dreb,
         stl, blk, turnover, pf, fgm, fga, fg_pct, fg3m, fg3a, fg3_pct,
         ftm, fta, ft_pct)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (player_id, game_id) DO UPDATE SET
        team_id = EXCLUDED.team_id,
        min = EXCLUDED.min,
        pts = EXCLUDED.pts,
        ast = EXCLUDED.ast,
        reb = EXCLUDED.reb,
        oreb = EXCLUDED.oreb,
        dreb = EXCLUDED.dreb,
        stl = EXCLUDED.stl,
        blk = EXCLUDED.blk,
        turnover = EXCLUDED.turnover,
        pf = EXCLUDED.pf,
        fgm = EXCLUDED.fgm,
        fga = EXCLUDED.fga,
        fg_pct = EXCLUDED.fg_pct,
        fg3m = EXCLUDED.fg3m,
        fg3a = EXCLUDED.fg3a,
        fg3_pct = EXCLUDED.fg3_pct,
        ftm = EXCLUDED.ftm,
        fta = EXCLUDED.fta,
        ft_pct = EXCLUDED.ft_pct
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD, defaults to yesterday")
    args = parser.parse_args()
    game_date = args.date or (date.today() - timedelta(days=1)).isoformat()

    conn = get_connection()
    total_inserted = 0
    total_skipped = 0
    try:
        games = get_our_games_for_date(conn, game_date)
        if not games:
            print(f"No games found in our DB for {game_date}. Run the Node ETL for this date first.")
            return

        team_abbr_to_id = {g["home_abbr"]: g["home_team_id"] for g in games}
        team_abbr_to_id.update({g["visitor_abbr"]: g["visitor_team_id"] for g in games})

        player_lookup = build_player_lookup(conn)

        print(f"Looking up nba_api games for {game_date}...")
        nba_game_map = fetch_nba_games_for_date(game_date)

        cur = conn.cursor()
        for g in games:
            key = (g["home_abbr"], g["visitor_abbr"])
            nba_game_id = nba_game_map.get(key)
            if not nba_game_id:
                print(f"  Could not match our game {g['id']} ({g['home_abbr']} vs {g['visitor_abbr']}) to an nba_api game.")
                continue

            print(f"Fetching box score for our game {g['id']} (nba_api game {nba_game_id})...")
            box = fetch_box_score(nba_game_id)
            time.sleep(0.6)  # be polite to stats.nba.com

            for _, row in box.iterrows():
                full_name = f"{row['firstName']} {row['familyName']}"
                player_norm = normalize_name(full_name)
                player_id = player_lookup.get(player_norm)
                if not player_id:
                    print(f"  Skipping unmatched player: {full_name}")
                    total_skipped += 1
                    continue

                team_id = team_abbr_to_id.get(row["teamTricode"])

                cur.execute(
                    UPSERT_SQL,
                    (
                        player_id,
                        g["id"],
                        team_id,
                        _parse_minutes(row.get("minutes")),
                        clean(row.get("points")),
                        clean(row.get("assists")),
                        clean(row.get("reboundsTotal")),
                        clean(row.get("reboundsOffensive")),
                        clean(row.get("reboundsDefensive")),
                        clean(row.get("steals")),
                        clean(row.get("blocks")),
                        clean(row.get("turnovers")),
                        clean(row.get("foulsPersonal")),
                        clean(row.get("fieldGoalsMade")),
                        clean(row.get("fieldGoalsAttempted")),
                        clean(row.get("fieldGoalsPercentage")),
                        clean(row.get("threePointersMade")),
                        clean(row.get("threePointersAttempted")),
                        clean(row.get("threePointersPercentage")),
                        clean(row.get("freeThrowsMade")),
                        clean(row.get("freeThrowsAttempted")),
                        clean(row.get("freeThrowsPercentage")),
                    ),
                )
                total_inserted += 1

            conn.commit()

        print(f"Done. Inserted/updated {total_inserted} stat lines, skipped {total_skipped} unmatched players.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
