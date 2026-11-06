"""Exploratory Data Analysis and statistical visualization for trial enrollment.

Generates publication-quality charts for enrollment trajectories, patient flow
correlations, seasonality patterns, and site-level recruitment heterogeneity.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import yaml


class ClinicalTrialEDA:
    """Generates visual analytics and statistical summaries for the trial dataset."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        self.fig_dir = Path(self.config.get("evaluation", {}).get("figures_dir", "reports/figures"))
        self.fig_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = Path(self.config.get("evaluation", {}).get("reports_dir", "reports"))
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Style setup
        sns.set_theme(style="whitegrid", font="sans-serif")
        plt.rcParams.update({"font.size": 11, "axes.labelsize": 12, "figure.autolayout": True})

    def generate_all(self, df: pd.DataFrame) -> dict[str, Any]:
        """Generate all 4 required EDA figures and a comprehensive statistical summary."""
        summary = self.compute_summary_stats(df)
        self.plot_enrollment_curves(df)
        self.plot_enrollment_vs_flow(df)
        self.plot_seasonality(df)
        self.plot_site_heterogeneity(df)

        with open(self.reports_dir / "eda_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    def compute_summary_stats(self, df: pd.DataFrame) -> dict[str, Any]:
        """Compute core biostatistical summary metrics for the site panel."""
        n_sites = int(df["site_id"].nunique())
        total_weeks = int(df["week"].max())
        total_enrolled = int(df["enrolled_count"].sum())

        site_totals = df.groupby("site_id")["enrolled_count"].sum()
        zero_sites = int((site_totals == 0).sum())

        active_rows = df[df["is_active"] == 1]
        mean_active_rate = float(active_rows["enrolled_count"].mean())
        median_active_rate = float(active_rows["enrolled_count"].median())
        p90_active_rate = float(active_rows["enrolled_count"].quantile(0.90))

        # Flow correlation
        corr_flow_enrollment = float(df[["eligible_volume", "enrolled_count"]].corr().iloc[0, 1])
        corr_occ_enrollment = float(df[["occupancy_proxy", "enrolled_count"]].corr().iloc[0, 1])

        # Activation stats
        act_weeks = df.groupby("site_id")["activation_week"].first()
        median_act = float(act_weeks.median())

        return {
            "n_sites": n_sites,
            "total_weeks": total_weeks,
            "total_enrolled": total_enrolled,
            "never_enrolling_site_count": zero_sites,
            "active_recruiting_site_count": n_sites - zero_sites,
            "median_activation_week": median_act,
            "mean_weekly_enrollment_per_active_site": round(mean_active_rate, 2),
            "median_weekly_enrollment_per_active_site": round(median_active_rate, 2),
            "p90_weekly_enrollment_per_active_site": round(p90_active_rate, 2),
            "correlation_eligible_volume_vs_enrolled": round(corr_flow_enrollment, 3),
            "correlation_occupancy_vs_enrolled": round(corr_occ_enrollment, 3),
            "countries": df["country"].unique().tolist(),
        }

    def plot_enrollment_curves(self, df: pd.DataFrame) -> None:
        """Fig 1: Cumulative enrollment trajectories across all sites and trial total."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), sharex=True)

        # Left: Individual site trajectories
        for site_id, grp in df.groupby("site_id"):
            tot = grp["enrolled_count"].sum()
            if tot == 0:
                ax1.plot(grp["week"], grp["cumulative_enrolled"], color="#e74c3c", alpha=0.7, lw=1.8, label="Dormant (0 Enrolled)" if site_id == df[df.groupby('site_id')['enrolled_count'].transform('sum') == 0]['site_id'].iloc[0] else "")
            else:
                ax1.plot(grp["week"], grp["cumulative_enrolled"], color="#3498db", alpha=0.35, lw=1.2)

        ax1.set_title("Per-Site Cumulative Enrollment (N=40)", fontweight="bold")
        ax1.set_xlabel("Trial Week")
        ax1.set_ylabel("Cumulative Enrolled Patients")
        ax1.legend(loc="upper left")

        # Right: Trial aggregate trajectory vs target
        trial_agg = df.groupby("week")["enrolled_count"].sum().cumsum()
        target = self.config.get("synthetic", {}).get("target_enrollment", 1200)
        deadline = self.config.get("synthetic", {}).get("deadline_week", 90)

        ax2.plot(trial_agg.index, trial_agg.values, color="#2c3e50", lw=2.8, label="Trial Cumulative Actual")
        ax2.axhline(target, color="#27ae60", linestyle="--", lw=2, label=f"Target ({target} patients)")
        ax2.axvline(deadline, color="#e67e22", linestyle=":", lw=2, label=f"Deadline (Week {deadline})")
        ax2.set_title("Total Trial Aggregate Enrollment", fontweight="bold")
        ax2.set_xlabel("Trial Week")
        ax2.set_ylabel("Total Cumulative Enrolled Patients")
        ax2.legend(loc="upper left")

        plt.savefig(self.fig_dir / "eda_enrollment_curves.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

    def plot_enrollment_vs_flow(self, df: pd.DataFrame) -> None:
        """Fig 2: Weekly enrollment count vs eligible hospital volume by hospital tier."""
        fig, ax = plt.subplots(figsize=(9, 6))

        active_df = df[df["is_active"] == 1]
        sns.scatterplot(
            data=active_df,
            x="eligible_volume",
            y="enrolled_count",
            hue="hospital_tier",
            alpha=0.45,
            s=40,
            palette="Set2",
            ax=ax,
        )
        sns.regplot(
            data=active_df,
            x="eligible_volume",
            y="enrolled_count",
            scatter=False,
            color="#2c3e50",
            line_kws={"lw": 2.5, "linestyle": "-"},
            ax=ax,
        )

        ax.set_title("Patient Flow: Eligible Volume vs Weekly Site Enrollment", fontweight="bold")
        ax.set_xlabel("Weekly Hospital Eligible Patient Count")
        ax.set_ylabel("Weekly Enrolled Count")
        plt.savefig(self.fig_dir / "eda_enrollment_vs_eligible.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

    def plot_seasonality(self, df: pd.DataFrame) -> None:
        """Fig 3: Aggregate hospital admissions, ED visits, and enrollment seasonality."""
        weekly = df.groupby("week").agg(
            total_enrolled=("enrolled_count", "sum"),
            mean_admissions=("admissions", "mean"),
            mean_ed=("ed_visits", "mean"),
            mean_occupancy=("occupancy_proxy", "mean"),
        )

        fig, ax1 = plt.subplots(figsize=(12, 6))
        ax2 = ax1.twinx()

        p1 = ax1.plot(weekly.index, weekly["total_enrolled"], color="#2980b9", lw=2.5, label="Weekly Trial Enrollment")
        p2 = ax2.plot(weekly.index, weekly["mean_admissions"], color="#e67e22", lw=2, linestyle="--", label="Mean Site Admissions")
        p3 = ax2.plot(weekly.index, weekly["mean_occupancy"] * 400, color="#27ae60", lw=1.5, linestyle=":", label="Occupancy Index (Scaled)")

        lines = p1 + p2 + p3
        labels = [l.get_label() for l in lines]
        ax1.legend(lines, labels, loc="upper right")

        ax1.set_title("Longitudinal Trial Seasonality & Hospital Pressure Cycles", fontweight="bold")
        ax1.set_xlabel("Trial Week (104 Weeks / 2 Years)")
        ax1.set_ylabel("Weekly Enrolled Patients", color="#2980b9")
        ax2.set_ylabel("Hospital Flow Metrics", color="#e67e22")

        plt.savefig(self.fig_dir / "eda_seasonality_and_flow.png", dpi=200, bbox_inches="tight")
        plt.close(fig)

    def plot_site_heterogeneity(self, df: pd.DataFrame) -> None:
        """Fig 4: Site heterogeneity and recruitment rate distribution per active week."""
        active_df = df[df["is_active"] == 1]
        site_rates = (
            active_df.groupby(["site_id", "country", "hospital_tier"])["enrolled_count"]
            .mean()
            .reset_index()
            .rename(columns={"enrolled_count": "mean_weekly_rate"})
            .sort_values("mean_weekly_rate", ascending=False)
        )

        fig, ax = plt.subplots(figsize=(14, 7))
        sns.barplot(
            data=site_rates,
            x="site_id",
            y="mean_weekly_rate",
            hue="country",
            dodge=False,
            palette="Spectral",
            ax=ax,
        )
        ax.tick_params(axis="x", rotation=90, labelsize=8)
        ax.set_title("Site Recruitment Heterogeneity: Mean Weekly Enrollment Rate per Active Week", fontweight="bold")
        ax.set_xlabel("Site ID (Ranked by Enrolling Efficiency)")
        ax.set_ylabel("Mean Weekly Enrolled Count")
        ax.axhline(site_rates["mean_weekly_rate"].mean(), color="black", linestyle="--", label="Global Active Mean")
        ax.legend(title="Country", loc="upper right")

        plt.savefig(self.fig_dir / "eda_site_heterogeneity.png", dpi=200, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    df = pd.read_parquet("data/processed/weekly_site_panel.parquet")
    eda = ClinicalTrialEDA()
    summary = eda.generate_all(df)
    print("EDA Complete:", summary)
