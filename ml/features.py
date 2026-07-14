"""
Pure feature-engineering functions — no DB dependency, so they can be unit
tested with synthetic data. All rolling/season-average features use
.shift(1) so a row's features are computed only from games strictly BEFORE
it (no data leakage: we never use a game's own stats to predict itself).
"""

import pandas as pd

STAT_COLUMNS = ["pts", "reb", "ast", "stl", "blk", "turnover"]


def rolling_feature_columns(stat_cols=STAT_COLUMNS):
    return (
        [f"{c}_avg_last5" for c in stat_cols]
        + [f"{c}_avg_last10" for c in stat_cols]
        + [f"{c}_season_avg" for c in stat_cols]
    )


FEATURE_COLUMNS = rolling_feature_columns() + ["days_rest", "is_back_to_back", "is_home"]


def add_rolling_features(df, group_col="player_id", date_col="date", stat_cols=STAT_COLUMNS):
    """Adds last-5-game avg, last-10-game avg, and season-to-date avg for each
    stat column, per player, using only games before the current row."""
    df = df.sort_values([group_col, date_col]).copy()

    for w in (5, 10):
        for col in stat_cols:
            df[f"{col}_avg_last{w}"] = df.groupby(group_col)[col].transform(
                lambda s: s.shift(1).rolling(w, min_periods=1).mean()
            )

    for col in stat_cols:
        df[f"{col}_season_avg"] = df.groupby(group_col)[col].transform(
            lambda s: s.shift(1).expanding().mean()
        )

    return df


def add_rest_features(df, group_col="player_id", date_col="date"):
    """Adds days_rest (days since the player's previous game) and a
    back-to-back flag. First game of a player's history gets days_rest=7
    (treated as fully rested — a reasonable default for a season opener)."""
    df = df.sort_values([group_col, date_col]).copy()
    df["_prev_date"] = df.groupby(group_col)[date_col].shift(1)
    df["days_rest"] = (pd.to_datetime(df[date_col]) - pd.to_datetime(df["_prev_date"])).dt.days
    df["days_rest"] = df["days_rest"].fillna(7)
    df["is_back_to_back"] = (df["days_rest"] <= 1).astype(int)
    df = df.drop(columns=["_prev_date"])
    return df


def fantasy_points(pts, reb, ast, stl, blk, turnover):
    """Standard DK-style points-league scoring (no double/triple-double bonus).
    Adjust these weights if your league uses different scoring rules."""
    return pts * 1.0 + reb * 1.25 + ast * 1.5 + stl * 2.0 + blk * 2.0 + turnover * -0.5
