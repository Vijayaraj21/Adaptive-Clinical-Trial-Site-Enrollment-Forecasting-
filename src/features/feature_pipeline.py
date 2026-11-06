"""Feature engineering pipeline for clinical trial enrollment forecasting.

Constructs lagged covariates, rolling window statistics, Fourier harmonic terms,
and standardized patient-flow features across sites and longitudinal weeks.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


class FeaturePipeline:
    """Transforms raw weekly trial panels into ML/Bayesian ready feature matrices."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        feat_cfg = self.config.get("features", {})
        self.lag_weeks: list[int] = feat_cfg.get("lag_weeks", [1, 2, 3, 4])
        self.rolling_windows: list[int] = feat_cfg.get("rolling_windows", [4, 8])
        self.fourier_terms: int = feat_cfg.get("fourier_terms", 2)
        self.standardize_cols: list[str] = feat_cfg.get(
            "standardize_covariates", ["eligible_volume", "ed_visits", "occupancy_proxy"]
        )

        self.processed_dir = Path(self.config["data"]["processed_dir"])
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.parquet_path = Path(self.config["data"]["processed_panel"])
        self.csv_path = Path(self.config["data"]["processed_panel_csv"])
        self.scaler_path = self.processed_dir / "covariate_scalers.json"

    def build_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
        """Transform panel dataframe with engineered features and standardized covariates."""
        df = df.copy()
        df = df.sort_values(["site_id", "week"]).reset_index(drop=True)

        # Standardize active column naming
        if "is_active" not in df.columns and "active_flag" in df.columns:
            df["is_active"] = df["active_flag"]
        elif "active_flag" not in df.columns and "is_active" in df.columns:
            df["active_flag"] = df["is_active"]

        # 1. Fourier Seasonality (harmonics 1 and 2 for annual 52-week cycle)
        for h in range(1, self.fourier_terms + 1):
            df[f"sin_52_h{h}"] = np.sin(2.0 * np.pi * h * df["week"] / 52.0).round(4)
            df[f"cos_52_h{h}"] = np.cos(2.0 * np.pi * h * df["week"] / 52.0).round(4)

        # 2. Cumulative enrollment per site
        df["cumulative_enrolled"] = df.groupby("site_id")["enrolled_count"].cumsum()

        # 3. Lag features (per site)
        for lag in self.lag_weeks:
            df[f"enrolled_lag_{lag}"] = (
                df.groupby("site_id")["enrolled_count"].shift(lag).fillna(0).astype(int)
            )
            df[f"eligible_lag_{lag}"] = (
                df.groupby("site_id")["eligible_volume"].shift(lag).fillna(0).astype(int)
            )

        # 4. Rolling statistics per site
        for win in self.rolling_windows:
            df[f"rolling_mean_enrolled_{win}w"] = (
                df.groupby("site_id")["enrolled_count"]
                .transform(lambda s, w=win: s.shift(1).rolling(w, min_periods=1).mean())
                .fillna(0.0)
                .round(3)
            )
            df[f"rolling_mean_eligible_{win}w"] = (
                df.groupby("site_id")["eligible_volume"]
                .transform(lambda s, w=win: s.shift(1).rolling(w, min_periods=1).mean())
                .fillna(0.0)
                .round(3)
            )

        # 5. Covariate Standardization (Z-score parameters saved for future inference)
        scalers: dict[str, dict[str, float]] = {}
        for col in self.standardize_cols:
            if col in df.columns:
                mean_val = float(df[col].mean())
                std_val = float(df[col].std()) if df[col].std() > 1e-6 else 1.0
                scalers[col] = {"mean": mean_val, "std": std_val}
                df[f"{col}_std"] = ((df[col] - mean_val) / std_val).round(4)

        # 6. Trial-level weekly cumulative total
        weekly_trial_totals = df.groupby("week")["enrolled_count"].sum().cumsum().rename("trial_cumulative_enrolled")
        df = df.merge(weekly_trial_totals, on="week", how="left")

        # Save scalers
        with open(self.scaler_path, "w", encoding="utf-8") as f:
            json.dump(scalers, f, indent=2)

        return df, scalers

    def run(self, raw_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
        """Execute pipeline and persist processed dataset."""
        processed_df, scalers = self.build_features(raw_df)
        processed_df.to_parquet(self.parquet_path, index=False)
        processed_df.to_csv(self.csv_path, index=False)
        return processed_df, scalers


if __name__ == "__main__":
    from src.data.hospital_flow import get_hospital_flow_panel

    raw_panel, _ = get_hospital_flow_panel()
    pipe = FeaturePipeline()
    proc_df, scl = pipe.run(raw_panel)
    print("Feature engineering complete.")
    print("Processed shape:", proc_df.shape)
    print("Columns:", len(proc_df.columns))
