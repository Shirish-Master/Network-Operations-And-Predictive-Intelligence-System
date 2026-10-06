"""ML1: critique and define a non-circular grid activity prediction problem.

The available data contains hourly grid-level communication activity only. It does
not measure network capacity, throughput, latency, packet loss, or radio use.
Therefore the target below is an activity-risk proxy and must not be described as
proof of network state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


# 1. Compare three candidate problems: high-activity risk, anomalous activity, and activity drop.
@dataclass(frozen=True)
class CandidateProblem:
    name: str
    strength: str
    limitation: str


def compare_candidate_problems() -> tuple[CandidateProblem, ...]:
    return (
        CandidateProblem(
            name="high-activity risk",
            strength="Directly measurable from the available activity aggregates and useful for triage.",
            limitation="High activity is not evidence of capacity pressure or any other network condition.",
        ),
        CandidateProblem(
            name="anomalous activity",
            strength="Can identify behavior that differs from a grid's historical pattern.",
            limitation="Requires a stable historical baseline and may flag legitimate events or sparse data.",
        ),
        CandidateProblem(
            name="activity drop",
            strength="Can identify a future reduction in observed communication activity.",
            limitation="A drop may reflect user behavior, source quality, maintenance, or missing data rather than an incident.",
        ),
    )


# 2. Select one primary problem for the model.
PRIMARY_PROBLEM = CandidateProblem(
    name="high-activity risk",
    strength="Predict whether the next hourly interval will exceed a transparent activity threshold.",
    limitation="This is a training proxy for activity risk, not a claim about network condition.",
)


def primary_problem() -> CandidateProblem:
    return PRIMARY_PROBLEM


# 3. Define the prediction unit: a grid plus a time window.
@dataclass(frozen=True)
class PredictionUnit:
    entity: str
    interval: str
    cadence: str


PREDICTION_UNIT = PredictionUnit(
    entity="one grid_id",
    interval="one hourly interval",
    cadence="hourly",
)


def prediction_unit() -> PredictionUnit:
    return PREDICTION_UNIT


# 4. Define the target as a future window. The label describes the interval at t+1; the features describe the trailing window ending at t. See the trap below — this is the difference between a real prediction problem and a restatement of a threshold.
@dataclass(frozen=True)
class TemporalBoundary:
    feature_window_end: str
    label_window: str
    separation: timedelta


TEMPORAL_BOUNDARY = TemporalBoundary(
    feature_window_end="t",
    label_window="the single hourly interval at t+1",
    separation=timedelta(hours=1),
)


def temporal_boundary() -> TemporalBoundary:
    return TEMPORAL_BOUNDARY


# 5. Define the target strategy precisely. If synthetic threshold labels are used, document them as training proxies and state the threshold.
@dataclass(frozen=True)
class TargetStrategy:
    label_name: str
    definition: str
    threshold: str
    proxy_disclaimer: str


TARGET_STRATEGY = TargetStrategy(
    label_name="future_high_activity_proxy",
    definition="1 when total_activity in the hourly interval at t+1 is at or above the 90th percentile of training-period hourly total_activity; otherwise 0.",
    threshold="training-period 90th percentile of hourly total_activity, calculated without using the held-out future interval",
    proxy_disclaimer="This synthetic label represents future high observed activity only. It is not a congestion label and does not measure capacity pressure.",
)


def target_strategy() -> TargetStrategy:
    return TARGET_STRATEGY


# 6. Define the business action: “investigate”, never “the network is congested”.
BUSINESS_ACTION = "If the positive proxy is returned, instruct an operator to investigate the grid and corroborate it with independent network evidence."


def business_action() -> str:
    return BUSINESS_ACTION


# 7. Identify the data leakage risks, and state how the t / t+1 boundary prevents each one.
@dataclass(frozen=True)
class LeakageRisk:
    risk: str
    prevention: str


LEAKAGE_RISKS = (
    LeakageRisk(
        risk="Using activity from t+1 or later when constructing features.",
        prevention="Freeze feature extraction at the trailing window's end t; exclude every timestamp after t.",
    ),
    LeakageRisk(
        risk="Calculating the threshold with held-out future observations.",
        prevention="Fit the threshold on the training period only, then apply that fixed threshold to t+1 labels.",
    ),
    LeakageRisk(
        risk="Including a same-window threshold flag as a feature.",
        prevention="The label describes t+1 while features describe only the trailing window ending at t, so the label cannot be reconstructed from the same interval.",
    ),
    LeakageRisk(
        risk="Randomly splitting adjacent hourly observations across train and test.",
        prevention="Use chronological splits so future intervals cannot influence training or feature normalization.",
    ),
)


def leakage_risks() -> tuple[LeakageRisk, ...]:
    return LEAKAGE_RISKS


NON_GOALS = (
    "Do not claim to detect congestion.",
    "Do not estimate network capacity.",
    "Do not estimate throughput.",
    "Do not infer latency, packet loss, or radio utilization that is absent from the data.",
)


def non_goals() -> tuple[str, ...]:
    return NON_GOALS


if __name__ == "__main__":
    print("Primary problem:", primary_problem().name)
    print("Prediction unit:", prediction_unit())
    print("Target:", target_strategy().definition)
    print("Business action:", business_action())
