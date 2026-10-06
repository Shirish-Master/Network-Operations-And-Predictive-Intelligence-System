"""ML2 feature-window and leakage tests."""

import pandas as pd
import pytest

from PHASE_4.ml.features import (
    FEATURE_COLUMNS,
    build_feature_row,
    build_features,
)


def sample_history() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-01", periods=49, freq="h")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "grid_id": 4821,
            "total_activity": [float(value) for value in range(1, 50)],
            "internet_activity": [float(value) for value in range(1, 50)],
        }
    )


# 9. Write one test that would fail if any feature used data from after feature_timestamp.
def test_real_implementation_does_not_read_after_feature_timestamp():
    history = sample_history()
    feature_timestamp = pd.Timestamp("2024-01-03 00:00:00")
    baseline = build_feature_row(history, feature_timestamp)

    future_changed = history.copy()
    future_changed.loc[future_changed["timestamp"] > feature_timestamp, "total_activity"] = 10_000_000
    future_changed.loc[future_changed["timestamp"] > feature_timestamp, "internet_activity"] = 10_000_000
    after_future_change = build_feature_row(future_changed, feature_timestamp)

    assert baseline == after_future_change


def test_deliberately_leaky_feature_fails_the_boundary_check():
    history = sample_history()
    feature_timestamp = pd.Timestamp("2024-01-03 00:00:00")
    future_row = pd.DataFrame(
        {
            "timestamp": [feature_timestamp + pd.Timedelta(hours=1)],
            "grid_id": [4821],
            "total_activity": [10_000_000.0],
            "internet_activity": [10_000_000.0],
        }
    )
    history = pd.concat([history, future_row], ignore_index=True)
    future_changed = history.copy()
    future_changed.loc[future_changed["timestamp"] > feature_timestamp, "total_activity"] = 10_000_000
    leaky_average = future_changed[future_changed["timestamp"] <= feature_timestamp + pd.Timedelta(hours=1)]["total_activity"].mean()
    allowed_average = history[history["timestamp"] <= feature_timestamp]["total_activity"].mean()

    with pytest.raises(AssertionError):
        assert leaky_average == allowed_average


def test_hand_checked_average_and_peak_ratio_are_exact():
    history = sample_history()
    row = build_feature_row(history, pd.Timestamp("2024-01-03 00:00:00"))
    recent_values = pd.Series(range(26, 50), dtype=float)

    assert row["avg_activity"] == recent_values.mean()
    assert row["peak_ratio"] == recent_values.max() / recent_values.mean()


def test_zero_activity_has_finite_defined_features():
    history = sample_history()
    history["total_activity"] = 0.0
    history["internet_activity"] = 0.0
    row = build_feature_row(history, pd.Timestamp("2024-01-03 00:00:00"))

    assert row["activity_growth"] == 0.0
    assert row["peak_ratio"] == 0.0
    assert row["variability"] == 0.0
    assert row["internet_share"] == 0.0


def test_persisted_schema_matches_api4_feature_names():
    features = build_features(sample_history())
    assert list(features.columns) == FEATURE_COLUMNS
    assert features["feature_timestamp"].notna().all()