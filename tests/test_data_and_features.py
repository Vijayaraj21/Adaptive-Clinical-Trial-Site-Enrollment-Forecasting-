"""Unit tests for Phase 1 (Data Acquisition) and Phase 2 (Features & EDA)."""


from src.data.ctgov import load_trial_metadata
from src.features.feature_pipeline import FeaturePipeline
from src.simulation.synthetic import SyntheticTrialGenerator


def test_ctgov_metadata_schema():
    meta = load_trial_metadata()
    assert "protocolSection" in meta
    proto = meta["protocolSection"]
    assert "identificationModule" in proto
    assert "contactsLocationsModule" in proto
    locations = proto["contactsLocationsModule"]["locations"]
    assert len(locations) > 0


def test_synthetic_data_generation():
    generator = SyntheticTrialGenerator()
    panel_df, gt = generator.run()
    assert len(panel_df) == 40 * 104
    assert panel_df["site_id"].nunique() == 40
    assert panel_df["week"].max() == 104
    assert (panel_df["enrolled_count"] >= 0).all()
    assert len(gt["never_enrolling_sites"]) > 0
    # Inactive weeks must have zero enrollment
    inactive = panel_df[panel_df["is_active"] == 0]
    assert (inactive["enrolled_count"] == 0).all()


def test_feature_pipeline_transformation():
    generator = SyntheticTrialGenerator()
    raw_df, _ = generator.run()
    pipe = FeaturePipeline()
    proc_df, _scalers = pipe.run(raw_df)

    assert len(proc_df) == len(raw_df)
    assert "enrolled_lag_1" in proc_df.columns
    assert "rolling_mean_enrolled_4w" in proc_df.columns
    assert "sin_52_h1" in proc_df.columns
    assert "eligible_volume_std" in proc_df.columns
    assert not proc_df["eligible_volume_std"].isna().any()

    # Standardized columns should have zero mean and unit variance
    mean_std = proc_df["eligible_volume_std"].mean()
    assert abs(mean_std) < 1e-2
    assert abs(proc_df["eligible_volume_std"].std() - 1.0) < 1e-2
