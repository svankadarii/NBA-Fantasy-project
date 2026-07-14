"""
Trains one XGBoost regressor per stat (pts, reb, ast, stl, blk, turnover),
using a time-based train/test split (train on earlier games, test on the
most recent ~20%) so accuracy reflects real forecasting, not lookahead.

Saves the model bundle to models/model_<version>.joblib, writes per-stat
MAE/RMSE to models/metrics_<version>.json (for the Streamlit dashboard in
step 5), and writes backtested predictions + actuals into the `predictions`
table so accuracy-over-time can be tracked from real data.

Usage:
    python train.py
"""

import json
import os
from datetime import datetime

import joblib
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sqlalchemy import text

from db import get_engine
from data_loader import load_training_frame
from features import add_rolling_features, add_rest_features, fantasy_points, STAT_COLUMNS, FEATURE_COLUMNS

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")


def write_backtest_predictions(engine, test_df, model_version):
    upsert_sql = text(
        """
        INSERT INTO predictions
            (player_id, game_id, model_version, predicted_pts, predicted_reb, predicted_ast,
             predicted_stl, predicted_blk, predicted_turnover, predicted_fantasy_points,
             actual_fantasy_points, prediction_date)
        VALUES (:player_id, :game_id, :model_version, :predicted_pts, :predicted_reb, :predicted_ast,
                :predicted_stl, :predicted_blk, :predicted_turnover, :predicted_fantasy_points,
                :actual_fantasy_points, NOW())
        ON CONFLICT (player_id, game_id, model_version) DO UPDATE SET
            predicted_pts = EXCLUDED.predicted_pts,
            predicted_reb = EXCLUDED.predicted_reb,
            predicted_ast = EXCLUDED.predicted_ast,
            predicted_stl = EXCLUDED.predicted_stl,
            predicted_blk = EXCLUDED.predicted_blk,
            predicted_turnover = EXCLUDED.predicted_turnover,
            predicted_fantasy_points = EXCLUDED.predicted_fantasy_points,
            actual_fantasy_points = EXCLUDED.actual_fantasy_points
        """
    )
    with engine.begin() as conn:
        for _, row in test_df.iterrows():
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
                    "actual_fantasy_points": float(row["actual_fantasy_points"]),
                },
            )
    print(f"Wrote {len(test_df)} backtest predictions to the predictions table.")


def main():
    engine = get_engine()

    print("Loading training data from Postgres...")
    df = load_training_frame(engine)
    print(f"Loaded {len(df)} player-game rows.")

    if len(df) < 200:
        print(
            "Not enough data yet to train a meaningful model (need at least "
            "a few hundred player-game rows). Let the ETL backfill run "
            "longer and try again."
        )
        return

    df = add_rolling_features(df, stat_cols=STAT_COLUMNS)
    df = add_rest_features(df)
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0)
    df["actual_fantasy_points"] = fantasy_points(
        df["pts"], df["reb"], df["ast"], df["stl"], df["blk"], df["turnover"]
    )

    df = df.sort_values("date").reset_index(drop=True)
    cutoff_idx = int(len(df) * 0.8)
    cutoff_date = df.iloc[cutoff_idx]["date"]
    train_df = df[df["date"] < cutoff_date].copy()
    test_df = df[df["date"] >= cutoff_date].copy()
    print(f"Train rows: {len(train_df)}, test rows: {len(test_df)} (split at {cutoff_date})")

    if len(test_df) == 0:
        print("Test split is empty — need a wider date range of completed games before training.")
        return

    models = {}
    metrics = {}

    for target in STAT_COLUMNS:
        model = xgb.XGBRegressor(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
        )
        model.fit(train_df[FEATURE_COLUMNS], train_df[target])
        preds = model.predict(test_df[FEATURE_COLUMNS])
        test_df[f"pred_{target}"] = preds

        mae = mean_absolute_error(test_df[target], preds)
        rmse = mean_squared_error(test_df[target], preds) ** 0.5
        metrics[target] = {"mae": round(float(mae), 3), "rmse": round(float(rmse), 3)}
        print(f"  {target}: MAE={mae:.2f}  RMSE={rmse:.2f}")

        models[target] = model

    test_df["predicted_fantasy_points"] = fantasy_points(
        test_df["pred_pts"], test_df["pred_reb"], test_df["pred_ast"],
        test_df["pred_stl"], test_df["pred_blk"], test_df["pred_turnover"],
    )

    model_version = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(MODEL_DIR, exist_ok=True)

    model_path = os.path.join(MODEL_DIR, f"model_{model_version}.joblib")
    joblib.dump({"models": models, "feature_columns": FEATURE_COLUMNS, "version": model_version}, model_path)
    print(f"Saved model bundle to {model_path}")

    metrics_path = os.path.join(MODEL_DIR, f"metrics_{model_version}.json")
    with open(metrics_path, "w") as f:
        json.dump(
            {
                "version": model_version,
                "trained_at": datetime.now().isoformat(),
                "train_rows": len(train_df),
                "test_rows": len(test_df),
                "cutoff_date": str(cutoff_date),
                "metrics": metrics,
            },
            f,
            indent=2,
        )
    print(f"Saved metrics to {metrics_path}")

    write_backtest_predictions(engine, test_df, model_version)
    print("Done.")


if __name__ == "__main__":
    main()
