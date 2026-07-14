"""
Generates predictions for upcoming (not-yet-played) games using the most
recently trained model.

Trick for feature parity with training: rather than writing separate
"as-of-today" feature logic, we append one placeholder row per
(player, upcoming game) onto the real historical rows, then run the SAME
add_rolling_features/add_rest_features functions used in training. Because
those functions use .shift(1), the placeholder row's rolling/season-average
features automatically end up being computed from all of that player's real
past games — exactly the features we want for a next-game prediction.

Usage:
    python predict_upcoming.py                # predicts today's/future games
"""

import glob
import os
from datetime import date

import pandas as pd
import joblib
from sqlalchemy import text

from db import get_engine
from data_loader import load_training_frame, load_upcoming_games, load_active_players
from features import add_rolling_features, add_rest_features, fantasy_points, STAT_COLUMNS, FEATURE_COLUMNS

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")


def latest_model_bundle():
    files = sorted(glob.glob(os.path.join(MODEL_DIR, "model_*.joblib")))
    if not files:
        raise RuntimeError("No trained model found in ml/models/. Run train.py first.")
    return joblib.load(files[-1])


def build_placeholder_rows(upcoming_games, active_players):
    """One row per (player on either roster, upcoming game), with real stat
    columns left as NaN — they'll never be used as training targets, only
    as the anchor point for computing 'features as of right now'."""
    rows = []
    for _, g in upcoming_games.iterrows():
        for team_id in (g["home_team_id"], g["visitor_team_id"]):
            roster = active_players[active_players["team_id"] == team_id]
            for _, p in roster.iterrows():
                rows.append(
                    {
                        "player_id": p["player_id"],
                        "game_id": g["game_id"],
                        "date": g["date"],
                        "team_id": team_id,
                        "home_team_id": g["home_team_id"],
                        "visitor_team_id": g["visitor_team_id"],
                        "min": None,
                        "pts": None,
                        "reb": None,
                        "ast": None,
                        "stl": None,
                        "blk": None,
                        "turnover": None,
                    }
                )
    return pd.DataFrame(rows)


def write_predictions(engine, pred_df, model_version):
    upsert_sql = text(
        """
        INSERT INTO predictions
            (player_id, game_id, model_version, predicted_pts, predicted_reb, predicted_ast,
             predicted_stl, predicted_blk, predicted_turnover, predicted_fantasy_points,
             prediction_date)
        VALUES (:player_id, :game_id, :model_version, :predicted_pts, :predicted_reb, :predicted_ast,
                :predicted_stl, :predicted_blk, :predicted_turnover, :predicted_fantasy_points, NOW())
        ON CONFLICT (player_id, game_id, model_version) DO UPDATE SET
            predicted_pts = EXCLUDED.predicted_pts,
            predicted_reb = EXCLUDED.predicted_reb,
            predicted_ast = EXCLUDED.predicted_ast,
            predicted_stl = EXCLUDED.predicted_stl,
            predicted_blk = EXCLUDED.predicted_blk,
            predicted_turnover = EXCLUDED.predicted_turnover,
            predicted_fantasy_points = EXCLUDED.predicted_fantasy_points,
            prediction_date = NOW()
        """
    )
    with engine.begin() as conn:
        for _, row in pred_df.iterrows():
            conn.execute(
                upsert_sql,
                {
                    "player_id": int(row["player_id"]),
                    "game_id": int(row["game_id"]),
                    "model_version": model_version,
                    "predicted_pts": float(row["pred_pts"]),
                    "predicted_reb": float(row["pred_reb"]),
                    "predicted_ast": float(row["pred_ast"]),
                    "predicted_stl": float(row["pred_stl"]),
                    "predicted_blk": float(row["pred_blk"]),
                    "predicted_turnover": float(row["pred_turnover"]),
                    "predicted_fantasy_points": float(row["predicted_fantasy_points"]),
                },
            )
    print(f"Wrote {len(pred_df)} live predictions to the predictions table.")


def main():
    engine = get_engine()
    today = date.today().isoformat()

    upcoming_games = load_upcoming_games(engine, today)
    if upcoming_games.empty:
        print(f"No upcoming (unplayed) games found for {today} or later. Nothing to predict.")
        return

    active_players = load_active_players(engine)
    history_df = load_training_frame(engine)

    placeholders = build_placeholder_rows(upcoming_games, active_players)
    combined = pd.concat([history_df, placeholders], ignore_index=True, sort=False)
    combined["is_home"] = (combined["team_id"] == combined["home_team_id"]).astype(int)

    combined = add_rolling_features(combined, stat_cols=STAT_COLUMNS)
    combined = add_rest_features(combined)
    combined[FEATURE_COLUMNS] = combined[FEATURE_COLUMNS].fillna(0)

    to_predict = combined[combined["pts"].isna()].copy()
    if to_predict.empty:
        print("Nothing to predict (all placeholder rows disappeared after merge — check roster/team data).")
        return

    bundle = latest_model_bundle()
    models = bundle["models"]
    model_version = bundle["version"]

    for target, model in models.items():
        to_predict[f"pred_{target}"] = model.predict(to_predict[FEATURE_COLUMNS])

    to_predict["predicted_fantasy_points"] = fantasy_points(
        to_predict["pred_pts"], to_predict["pred_reb"], to_predict["pred_ast"],
        to_predict["pred_stl"], to_predict["pred_blk"], to_predict["pred_turnover"],
    )

    write_predictions(engine, to_predict, model_version)
    print("Done.")


if __name__ == "__main__":
    main()
