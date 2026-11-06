"""Synthetic clinical trial site enrollment generator.

Generates realistic longitudinal hospital-flow covariates and negative-binomial
enrollment counts across international trial sites, incorporating activation delays,
hospital-size heterogeneity, hidden screening/consent rates, seasonality,
and non-enrolling sites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


class SyntheticTrialGenerator:
    """Simulates realistic multi-center clinical trial site flow and enrollment."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        synth_cfg = self.config.get("synthetic", {})
        self.n_sites: int = synth_cfg.get("n_sites", 40)
        self.n_countries: int = synth_cfg.get("n_countries", 5)
        self.n_weeks: int = synth_cfg.get("n_weeks", 104)
        self.seed: int = synth_cfg.get("random_seed", 42)
        self.zero_inflation_prob: float = synth_cfg.get("zero_inflation_prob", 0.08)
        self.rng = np.random.default_rng(self.seed)

        self.raw_dir = Path(self.config["data"]["raw_dir"])
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.gt_path = Path(self.config["data"]["synthetic_ground_truth"])

    def generate_site_metadata(self) -> pd.DataFrame:
        """Create site profiles with hierarchy, capacity, and activation latencies."""
        countries = ["USA", "UK", "Germany", "Canada", "France"][: self.n_countries]
        tiers = ["Academic Medical Center", "Regional Hospital", "Community Hospital"]

        sites: list[dict[str, Any]] = []
        for i in range(1, self.n_sites + 1):
            country = countries[(i - 1) % len(countries)]
            tier = self.rng.choice(tiers, p=[0.45, 0.35, 0.20])

            if tier == "Academic Medical Center":
                base_beds = self.rng.integers(600, 1100)
                mean_admit = self.rng.integers(350, 550)
                ed_ratio = self.rng.uniform(2.8, 3.8)
            elif tier == "Regional Hospital":
                base_beds = self.rng.integers(350, 600)
                mean_admit = self.rng.integers(200, 350)
                ed_ratio = self.rng.uniform(2.4, 3.2)
            else:
                base_beds = self.rng.integers(150, 350)
                mean_admit = self.rng.integers(90, 200)
                ed_ratio = self.rng.uniform(1.8, 2.6)

            # Activation week: truncated normal (mean ~8, std ~4, min 1, max 30)
            act_week = int(np.clip(np.round(self.rng.normal(8.0, 4.5)), 1, 30))

            # Dormant / never-enrolling site flag (~8% chance)
            is_zero_site = bool(self.rng.random() < self.zero_inflation_prob)

            # Latent screening and consent rates
            screening_rate = float(np.clip(self.rng.normal(0.14, 0.03), 0.05, 0.25))
            consent_rate = float(np.clip(self.rng.normal(0.28, 0.06), 0.10, 0.50))

            # Country-level effect on log-rate
            country_effect = {"USA": 0.15, "Germany": 0.10, "UK": 0.0, "Canada": -0.05, "France": -0.10}.get(country, 0.0)
            # Site random intercept
            site_rand_intercept = float(self.rng.normal(country_effect, 0.35))

            sites.append(
                {
                    "site_id": f"SITE_{i:03d}",
                    "site_name": f"{country} AMC Site {i:03d}" if tier == "Academic Medical Center" else f"{country} Hospital {i:03d}",
                    "country": country,
                    "hospital_tier": tier,
                    "bed_capacity": int(base_beds),
                    "mean_weekly_admissions": int(mean_admit),
                    "ed_admit_ratio": float(np.round(ed_ratio, 2)),
                    "activation_week": act_week,
                    "never_enrolling_site": is_zero_site,
                    "true_screening_rate": np.round(screening_rate, 4),
                    "true_consent_rate": np.round(consent_rate, 4),
                    "true_site_intercept": np.round(site_rand_intercept, 4),
                }
            )

        return pd.DataFrame(sites)

    def generate_longitudinal_panel(self, site_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Generate weekly hospital flow covariates and negative-binomial enrollment counts."""
        # True beta coefficients for data generation
        beta_eligible = 0.38
        beta_occupancy = 0.18
        beta_sin = 0.15
        beta_cos = 0.10
        nb_alpha = 2.5  # overdispersion parameter: Var = mu + alpha * mu^2

        records: list[dict[str, Any]] = []

        for _, site in site_df.iterrows():
            site_id = site["site_id"]
            country = site["country"]
            mean_adm = site["mean_weekly_admissions"]
            ed_mult = site["ed_admit_ratio"]
            act_week = site["activation_week"]
            never_enroll = site["never_enrolling_site"]
            alpha_s = site["true_site_intercept"]

            # Initialize AR(1) state for occupancy and volume shocks
            ar_shock = 0.0

            for t in range(1, self.n_weeks + 1):
                # Seasonality: 52-week annual cycle (winter peak at t=48-52 and 1-4)
                fourier_sin = np.sin(2 * np.pi * t / 52.0)
                fourier_cos = np.cos(2 * np.pi * t / 52.0)
                seasonality_boost = 0.12 * fourier_cos + 0.08 * fourier_sin

                # AR(1) weekly hospital volume fluctuations
                ar_shock = 0.70 * ar_shock + self.rng.normal(0.0, 0.08)

                # Admissions count
                expected_adm = mean_adm * (1.0 + seasonality_boost + ar_shock)
                admissions = int(np.clip(self.rng.poisson(max(expected_adm, 20)), 15, None))

                # ED visits
                ed_expected = admissions * ed_mult * (1.0 + 0.05 * fourier_cos)
                ed_visits = int(np.clip(self.rng.poisson(max(ed_expected, 30)), 20, None))

                # Occupancy proxy (ratio between 0.60 and 0.98)
                base_occ = 0.78 + 0.06 * fourier_cos + 0.04 * (admissions / (mean_adm + 1e-5) - 1.0)
                occupancy_proxy = float(np.clip(base_occ + self.rng.normal(0, 0.02), 0.58, 0.98))

                # Eligible patient volume (subset of patients meeting trial inclusion)
                elig_pool = admissions * 0.40 + ed_visits * 0.12
                eligible_volume = int(np.clip(self.rng.binomial(int(elig_pool), site["true_screening_rate"]), 0, None))

                # Activation status
                is_active = (t >= act_week)
                weeks_since_act = max(0, t - act_week) if is_active else 0

                # Enrollment calculation
                if (not is_active) or never_enroll:
                    enrolled_count = 0
                    true_mu = 0.0
                else:
                    # Normalized log volume effect
                    vol_factor = np.log1p(eligible_volume) - 2.5
                    occ_factor = (occupancy_proxy - 0.78) / 0.10

                    # Ramp-up effect: sites start slower in first 4 weeks post-activation
                    ramp_up = np.clip(weeks_since_act / 4.0, 0.25, 1.0)

                    log_mu = (
                        alpha_s
                        + beta_eligible * vol_factor
                        + beta_occupancy * occ_factor
                        + beta_sin * fourier_sin
                        + beta_cos * fourier_cos
                    )
                    base_mu = np.exp(log_mu) * ramp_up
                    true_mu = float(max(base_mu, 0.01))

                    # Sample from Negative Binomial using Gamma-Poisson mixture
                    # Negative Binomial: n = 1/alpha, p = 1 / (1 + alpha * mu)
                    # Gamma(k, theta) where k = 1/alpha, theta = alpha * mu
                    k_shape = 1.0 / nb_alpha
                    theta_scale = nb_alpha * true_mu
                    gamma_rate = self.rng.gamma(k_shape, theta_scale)
                    enrolled_count = int(self.rng.poisson(gamma_rate))

                records.append(
                    {
                        "site_id": site_id,
                        "country": country,
                        "hospital_tier": site["hospital_tier"],
                        "week": t,
                        "activation_week": act_week,
                        "is_active": int(is_active),
                        "weeks_since_activation": weeks_since_act,
                        "admissions": admissions,
                        "ed_visits": ed_visits,
                        "occupancy_proxy": np.round(occupancy_proxy, 4),
                        "eligible_volume": eligible_volume,
                        "fourier_sin52": np.round(fourier_sin, 4),
                        "fourier_cos52": np.round(fourier_cos, 4),
                        "enrolled_count": enrolled_count,
                        "true_latent_rate": np.round(true_mu, 4),
                    }
                )

        panel_df = pd.DataFrame(records)

        # Ground truth summary
        ground_truth: dict[str, Any] = {
            "parameters": {
                "beta_eligible": beta_eligible,
                "beta_occupancy": beta_occupancy,
                "beta_sin52": beta_sin,
                "beta_cos52": beta_cos,
                "nb_overdispersion_alpha": nb_alpha,
            },
            "total_sites": int(self.n_sites),
            "total_weeks": int(self.n_weeks),
            "total_enrolled": int(panel_df["enrolled_count"].sum()),
            "never_enrolling_sites": site_df[site_df["never_enrolling_site"]]["site_id"].tolist(),
            "site_profiles": site_df.to_dict(orient="records"),
        }

        return panel_df, ground_truth

    def run(self) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Run complete generation and save outputs."""
        site_df = self.generate_site_metadata()
        panel_df, ground_truth = self.generate_longitudinal_panel(site_df)

        # Save outputs
        with open(self.gt_path, "w", encoding="utf-8") as f:
            json.dump(ground_truth, f, indent=2)

        raw_panel_parquet = self.raw_dir / "synthetic_weekly_panel.parquet"
        raw_panel_csv = self.raw_dir / "synthetic_weekly_panel.csv"
        panel_df.to_parquet(raw_panel_parquet, index=False)
        panel_df.to_csv(raw_panel_csv, index=False)

        return panel_df, ground_truth


if __name__ == "__main__":
    generator = SyntheticTrialGenerator()
    df, gt = generator.run()
    print("Synthetic generation complete.")
    print(f"Panel shape: {df.shape}")
    print(f"Total cumulative trial enrollment: {df['enrolled_count'].sum()}")
    print(f"Never-enrolling sites: {gt['never_enrolling_sites']}")
