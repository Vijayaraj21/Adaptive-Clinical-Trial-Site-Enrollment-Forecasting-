"""Unit tests for Phase 3 (Baselines) and Phase 4 (Hierarchical Bayesian Models)."""

from pathlib import Path

import arviz as az
import pandas as pd

from src.models.baselines import (
    PerSitePoissonGammaBaseline,
    PooledPoissonBaseline,
    XGBoostLagBaseline,
    evaluate_baseline_predictions,
)


def test_pooled_poisson_baseline():
    df = pd.read_parquet("data/processed/weekly_site_panel.parquet")
    train = df[df["week"] <= 50]
    test = df[df["week"] > 50]

    model = PooledPoissonBaseline().fit(train)
    preds = model.predict(test)

    assert len(preds) == len(test)
    assert (preds >= 0.0).all()
    # Inactive rows must predict 0
    inactive_mask = (test["is_active"] == 0).to_numpy()
    assert (preds[inactive_mask] == 0.0).all()

    metrics = evaluate_baseline_predictions(test["enrolled_count"].to_numpy(), preds)
    assert "mae" in metrics and "rmse" in metrics
    assert metrics["mae"] > 0


def test_per_site_poisson_gamma_baseline():
    df = pd.read_parquet("data/processed/weekly_site_panel.parquet")
    train = df[df["week"] <= 50]
    test = df[df["week"] > 50]

    model = PerSitePoissonGammaBaseline().fit(train)
    preds = model.predict(test)

    assert len(preds) == len(test)
    assert (preds >= 0.0).all()
    metrics = evaluate_baseline_predictions(test["enrolled_count"].to_numpy(), preds)
    assert metrics["rmse"] > 0


def test_xgboost_lag_baseline():
    df = pd.read_parquet("data/processed/weekly_site_panel.parquet")
    train = df[df["week"] <= 50]
    test = df[df["week"] > 50]

    model = XGBoostLagBaseline().fit(train)
    preds = model.predict(test)

    assert len(preds) == len(test)
    assert (preds >= 0.0).all()
    metrics = evaluate_baseline_predictions(test["enrolled_count"].to_numpy(), preds)
    assert metrics["mae"] > 0


def test_hierarchical_bayesian_trace_loading_and_structure():
    trace_path = Path("models_cache/model_a_trace.nc")
    assert trace_path.exists()

    idata = az.from_netcdf(trace_path)
    assert hasattr(idata, "posterior")
    assert "alpha_0" in idata.posterior
    assert "a_site" in idata.posterior
    assert "beta_eligible" in idata.posterior
    assert "alpha_nb" in idata.posterior

    assert len(idata.posterior.chain) == 4
    assert len(idata.posterior.draw) == 1000

    # Diagnostics
    summary = az.summary(idata, var_names=["alpha_0", "beta_eligible"])
    assert (summary["r_hat"] < 1.10).all()
