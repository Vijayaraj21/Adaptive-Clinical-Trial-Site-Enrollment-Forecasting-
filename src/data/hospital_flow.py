"""Hospital patient flow data loader and aggregator.

Supports MIMIC-IV / MIMIC-IV-ED tables if present in data/raw/mimic,
with seamless automatic fallback to the calibrated multi-site synthetic generator.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.simulation.synthetic import SyntheticTrialGenerator

logger = logging.getLogger(__name__)


class HospitalFlowLoader:
    """Loads and aggregates hospital flow and trial site longitudinal data."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.source = self.config.get("data", {}).get("source", "synthetic").lower()
        self.mimic_dir = Path(self.config.get("data", {}).get("mimic_dir", "data/raw/mimic"))
        self.raw_dir = Path(self.config.get("data", {}).get("raw_dir", "data/raw"))
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def load_data(self) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Load site panel either from MIMIC-IV tables or via synthetic generator."""
        if self.source == "mimic":
            mimic_data = self._try_load_mimic()
            if mimic_data is not None:
                return mimic_data, {"source": "mimic"}
            logger.warning(
                "MIMIC source selected, but raw tables not found in %s. Falling back to synthetic generator.",
                self.mimic_dir,
            )

        logger.info("Executing synthetic multi-center trial simulation.")
        generator = SyntheticTrialGenerator()
        df, gt = generator.run()
        return df, {"source": "synthetic", "ground_truth": gt}

    def _try_load_mimic(self) -> pd.DataFrame | None:
        """Attempt to load and process MIMIC-IV tables if available on disk."""
        adm_files = list(self.mimic_dir.glob("admissions*"))
        ed_files = list(self.mimic_dir.glob("edstays*"))

        if not adm_files or not ed_files:
            return None

        try:
            logger.info("Processing MIMIC-IV admissions from %s", adm_files[0])
            admissions = pd.read_csv(adm_files[0])
            admissions["admittime"] = pd.to_datetime(admissions["admittime"])
            admissions["dischtime"] = pd.to_datetime(admissions["dischtime"])

            # Weekly aggregation of admissions
            admissions["week_start"] = admissions["admittime"].dt.to_period("W").dt.start_time
            weekly_adm = admissions.groupby("week_start").size().rename("admissions").reset_index()

            # Process ED visits if present
            edstays = pd.read_csv(ed_files[0])
            edstays["intime"] = pd.to_datetime(edstays["intime"])
            edstays["week_start"] = edstays["intime"].dt.to_period("W").dt.start_time
            weekly_ed = edstays.groupby("week_start").size().rename("ed_visits").reset_index()

            merged = pd.merge(weekly_adm, weekly_ed, on="week_start", how="outer").fillna(0)
            merged = merged.sort_values("week_start").reset_index(drop=True)
            merged["week"] = np.arange(1, len(merged) + 1)
            merged["occupancy_proxy"] = np.clip(merged["admissions"] / (merged["admissions"].max() + 1e-5), 0.5, 0.98)
            merged["eligible_volume"] = (merged["admissions"] * 0.15).astype(int)
            merged["site_id"] = "MIMIC_BETH_ISRAEL"
            merged["country"] = "USA"
            merged["is_active"] = 1
            merged["weeks_since_activation"] = merged["week"]
            merged["enrolled_count"] = (merged["eligible_volume"] * 0.25).astype(int)
            return merged
        except (OSError, ValueError, KeyError) as e:
            logger.error("Error processing MIMIC data: %s", e)
            return None


def get_hospital_flow_panel(config_path: str = "config.yaml") -> tuple[pd.DataFrame, dict[str, Any]]:
    """Entry point for hospital flow data loading."""
    loader = HospitalFlowLoader(config_path)
    return loader.load_data()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    panel, meta = get_hospital_flow_panel()
    print("Loaded panel shape:", panel.shape)
    print("Sample columns:", list(panel.columns))
