"""Baseline models for clinical trial enrollment forecasting.

Implements:
1. Pooled Poisson Regression (complete pooling across all sites).
2. Per-Site Poisson-Gamma conjugate model (no pooling / completely unpooled).
3. XGBoost Count Regressor on lagged covariates and rolling window statistics.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import statsmodels.api as sm
import xgboost as xgb

logger = logging.getLogger(__name__)


class PooledPoissonBaseline:
    """Pooled Poisson Generalized Linear Model (ignores site heterogeneity)."""

    def __init__(self, feature_cols: list[str] | None = None):
        self.feature_cols = feature_cols or [
            "eligible_volume_std",
            "ed_visits_std",
            "occupancy_proxy_std",
            "sin_52_h1",
            "cos_52_h1",
        ]
        self.model = None
        self.results = None

    def fit(self, df: pd.DataFrame) -> PooledPoissonBaseline:
        """Fit GLM Poisson model on active observations."""
        active = df[df["is_active"] == 1].copy()
        if len(active) == 0:
            active = df.copy()

        X = sm.add_constant(active[self.feature_cols])
        y = active["enrolled_count"]
        self.model = sm.GLM(y, X, family=sm.families.Poisson())
        self.results = self.model.fit()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict expected enrollment rate per observation."""
        if self.results is None:
            raise RuntimeError("Model must be fitted before predict.")

        X = sm.add_constant(df[self.feature_cols], has_constant="add")
        preds = self.results.predict(X)
        # Inactive weeks always enroll 0
        is_active = df["is_active"].to_numpy()
        preds = np.where(is_active == 1, preds, 0.0)
        return np.maximum(preds, 0.0)


class PerSitePoissonGammaBaseline:
    """Independent per-site Poisson-Gamma conjugate Bayesian update (no pooling)."""

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.site_posteriors: dict[str, tuple[float, float]] = {}
        self.global_mean_rate: float = 1.0

    def fit(self, df: pd.DataFrame) -> PerSitePoissonGammaBaseline:
        """Calculate conjugate Gamma posterior for each site."""
        active = df[df["is_active"] == 1]
        self.global_mean_rate = float(active["enrolled_count"].mean()) if len(active) > 0 else 1.0

        for site_id, grp in df.groupby("site_id"):
            act_grp = grp[grp["is_active"] == 1]
            total_events = float(act_grp["enrolled_count"].sum())
            exposure_weeks = float(len(act_grp))

            alpha_post = self.prior_alpha + total_events
            beta_post = self.prior_beta + exposure_weeks
            self.site_posteriors[site_id] = (alpha_post, beta_post)

        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict per-site expected rates."""
        preds = np.zeros(len(df))
        for i, (_, row) in enumerate(df.iterrows()):
            if row["is_active"] == 0:
                preds[i] = 0.0
                continue
            site_id = row["site_id"]
            if site_id in self.site_posteriors:
                a, b = self.site_posteriors[site_id]
                preds[i] = a / b
            else:
                preds[i] = self.global_mean_rate
        return preds


class XGBoostLagBaseline:
    """XGBoost Poisson count regressor using lag and rolling features."""

    def __init__(self, feature_cols: list[str] | None = None, n_estimators: int = 80, max_depth: int = 4):
        self.feature_cols = feature_cols or [
            "enrolled_lag_1",
            "enrolled_lag_2",
            "enrolled_lag_3",
            "enrolled_lag_4",
            "eligible_lag_1",
            "eligible_lag_2",
            "rolling_mean_enrolled_4w",
            "rolling_mean_eligible_4w",
            "eligible_volume_std",
            "occupancy_proxy_std",
            "sin_52_h1",
            "cos_52_h1",
        ]
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.model = xgb.XGBRegressor(
            objective="count:poisson",
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=0.06,
            random_state=42,
            n_jobs=2,
        )

    def fit(self, df: pd.DataFrame) -> XGBoostLagBaseline:
        """Fit XGBoost model on active site-week data."""
        active = df[df["is_active"] == 1].copy()
        if len(active) == 0:
            active = df.copy()

        X = active[self.feature_cols]
        y = active["enrolled_count"]
        self.model.fit(X, y)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict counts on dataset."""
        X = df[self.feature_cols]
        raw_preds = self.model.predict(X)
        is_active = df["is_active"].to_numpy()
        preds = np.where(is_active == 1, raw_preds, 0.0)
        return np.maximum(preds, 0.0)


def evaluate_baseline_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute MAE, RMSE, and Poisson deviance."""
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    # Poisson deviance: 2 * sum(y * log(y/mu) - (y - mu))
    eps = 1e-6
    mu = np.clip(y_pred, eps, None)
    y = np.clip(y_true, 0, None)
    y_safe = np.where(y > 0, y, 1.0)
    term1 = np.where(y > 0, y * np.log(y_safe / mu), 0.0)
    dev = 2.0 * np.mean(term1 - (y - mu))

    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "poisson_deviance": round(float(dev), 4)}


if __name__ == "__main__":
    df = pd.read_parquet("data/processed/weekly_site_panel.parquet")
    # Split train (weeks 1-60) and test (weeks 61-104)
    train_df = df[df["week"] <= 60]
    test_df = df[df["week"] > 60]
    y_test = test_df["enrolled_count"].to_numpy()

    # 1. Pooled Poisson
    p_model = PooledPoissonBaseline().fit(train_df)
    p_preds = p_model.predict(test_df)
    print("Pooled Poisson:", evaluate_baseline_predictions(y_test, p_preds))

    # 2. Per-Site Poisson-Gamma
    pg_model = PerSitePoissonGammaBaseline().fit(train_df)
    pg_preds = pg_model.predict(test_df)
    print("Per-Site Poisson-Gamma:", evaluate_baseline_predictions(y_test, pg_preds))

    # 3. XGBoost
    xgb_model = XGBoostLagBaseline().fit(train_df)
    xgb_preds = xgb_model.predict(test_df)
    print("XGBoost:", evaluate_baseline_predictions(y_test, xgb_preds))
