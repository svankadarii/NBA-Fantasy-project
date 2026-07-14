import pandas as pd


def load_training_frame(engine):
    """One row per (player, completed game), with the raw stat lines the
    feature/target computations build on."""
    query = """
        SELECT
            pgs.player_id,
            pgs.game_id,
            g.date,
            g.season,
            pgs.team_id,
            g.home_team_id,
            g.visitor_team_id,
            pgs.min,
            pgs.pts,
            pgs.reb,
            pgs.ast,
            pgs.stl,
            pgs.blk,
            pgs.turnover
        FROM player_game_stats pgs
        JOIN games g ON g.id = pgs.game_id
        WHERE g.status = 'Final'
        ORDER BY pgs.player_id, g.date
    """
    df = pd.read_sql(query, engine)
    df["is_home"] = (df["team_id"] == df["home_team_id"]).astype(int)
    return df


def load_upcoming_games(engine, as_of_date):
    """Games on/after as_of_date that haven't started yet (period=0)."""
    query = """
        SELECT g.id AS game_id, g.date, g.home_team_id, g.visitor_team_id
        FROM games g
        WHERE g.date >= %(as_of_date)s AND g.period = 0
        ORDER BY g.date
    """
    return pd.read_sql(query, engine, params={"as_of_date": as_of_date})


def load_active_players(engine):
    """Players currently rostered to a team (used to know who might play in
    an upcoming game)."""
    query = "SELECT id AS player_id, team_id, first_name, last_name FROM players WHERE team_id IS NOT NULL"
    return pd.read_sql(query, engine)
