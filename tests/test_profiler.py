"""Tests for Olist data profiling and report generation."""

import pandas as pd
import pytest

from src.ingestion import profiler
from src.ingestion.profiler import (
    DEFAULT_KEY_MAP,
    duplicate_report,
    generate_all_reports,
    missing_report,
    profile_table,
    save_report,
    unique_report,
)


def test_profile_table_reports_structure_and_deep_memory():
    frame = pd.DataFrame(
        {"label": ["long object value", "long object value", None], "count": [1, 2, 2]}
    )

    result = profile_table(frame, "sample")

    assert result["table"] == "sample"
    assert result["row_count"] == 3
    assert result["column_count"] == 2
    assert result["columns"] == ["label", "count"]
    assert result["dtypes"] == {
        column: str(dtype) for column, dtype in frame.dtypes.items()
    }
    assert result["unique_counts"] == {"label": 1, "count": 2}
    assert result["memory_usage_bytes"] == int(
        frame.memory_usage(index=True, deep=True).sum()
    )


def test_missing_report_counts_and_percentages():
    dfs = {"orders": pd.DataFrame({"a": [1, None, None, 4], "b": [None, 2, 3, 4]})}

    result = missing_report(dfs).set_index("column")

    assert result.loc["a", "table"] == "orders"
    assert result.loc["a", "null_count"] == 2
    assert result.loc["a", "null_pct"] == pytest.approx(50.0)
    assert result.loc["b", "null_count"] == 1
    assert result.loc["b", "null_pct"] == pytest.approx(25.0)


def test_missing_report_omits_complete_columns_and_handles_empty_tables():
    dfs = {
        "complete": pd.DataFrame({"a": [1, 2]}),
        "empty": pd.DataFrame({"a": pd.Series(dtype="object")}),
        "no_columns": pd.DataFrame(),
    }

    result = missing_report(dfs)

    assert list(result.columns) == ["table", "column", "null_count", "null_pct"]
    assert result.empty


def test_empty_dataframe_profiles_safely():
    empty = pd.DataFrame({"id": pd.Series(dtype="object")})

    profile = profile_table(empty, "empty")
    duplicates = duplicate_report({"empty": empty}, {"empty": "id"}).iloc[0]

    assert profile["row_count"] == 0
    assert profile["column_count"] == 1
    assert profile["unique_counts"] == {"id": 0}
    assert duplicates["full_row_duplicate_count"] == 0
    assert duplicates["key_duplicate_count"] == 0


def test_duplicate_report_separates_full_row_and_single_key_duplicates():
    dfs = {
        "orders": pd.DataFrame({"order_id": ["a", "a", "b"], "amount": [1, 1, 2]})
    }

    result = duplicate_report(dfs, {"orders": "order_id"}).iloc[0]

    assert result["full_row_duplicate_count"] == 1
    assert result["key_columns"] == ["order_id"]
    assert result["key_duplicate_count"] == 1


def test_duplicate_report_counts_composite_key_duplicates():
    dfs = {
        "items": pd.DataFrame(
            {"order_id": ["a", "a", "a"], "item_id": [1, 1, 2], "value": [3, 4, 5]}
        )
    }

    result = duplicate_report(dfs, {"items": ("order_id", "item_id")}).iloc[0]

    assert result["full_row_duplicate_count"] == 0
    assert result["key_columns"] == ["order_id", "item_id"]
    assert result["key_duplicate_count"] == 1


def test_geolocation_zip_repetition_is_not_a_key_duplicate():
    df = pd.DataFrame(
        {
            "geolocation_zip_code_prefix": ["01000", "01000"],
            "geolocation_lat": [-23.5, -23.6],
        }
    )

    result = duplicate_report({"geolocation": df}, DEFAULT_KEY_MAP).iloc[0]

    assert "geolocation" not in DEFAULT_KEY_MAP
    assert result["full_row_duplicate_count"] == 0
    assert result["key_columns"] == []
    assert pd.isna(result["key_duplicate_count"])


def test_invalid_key_column_raises_clear_value_error():
    dfs = {"orders": pd.DataFrame({"order_id": ["a"]})}

    with pytest.raises(ValueError, match="orders.*missing_id"):
        duplicate_report(dfs, {"orders": "missing_id"})


def test_unique_report_excludes_null_values():
    dfs = {"orders": pd.DataFrame({"status": ["new", "new", None, "sent"]})}

    result = unique_report(dfs)

    assert result.to_dict("records") == [
        {"table": "orders", "column": "status", "distinct_value_count": 2}
    ]


def test_save_report_creates_profiling_directory_and_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(profiler, "REPORT_DIR", tmp_path / "reports" / "profiling")
    frame = pd.DataFrame({"value": [1, 2]})

    path = save_report(frame, "example.csv")

    assert path == tmp_path / "reports" / "profiling" / "example.csv"
    assert path.exists()
    assert pd.read_csv(path).to_dict("records") == [{"value": 1}, {"value": 2}]
    with pytest.raises(ValueError, match="plain filename"):
        save_report(frame, "../outside.csv")


@pytest.mark.parametrize("filename", [".", ".."])
def test_save_report_rejects_dot_filenames(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(profiler, "REPORT_DIR", tmp_path / "profiling")

    with pytest.raises(ValueError, match="plain filename"):
        save_report(pd.DataFrame({"value": [1]}), filename)


def test_generate_all_reports_saves_exactly_four_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(profiler, "REPORT_DIR", tmp_path / "profiling")
    dfs = {
        "orders": pd.DataFrame({"order_id": ["a", "a"], "optional": [None, "x"]}),
        "geolocation": pd.DataFrame(
            {"geolocation_zip_code_prefix": ["01000", "01000"], "lat": [1.0, 2.0]}
        ),
    }

    paths = generate_all_reports(dfs, DEFAULT_KEY_MAP)

    expected_names = {
        "structural_profile.csv",
        "missing_values.csv",
        "duplicates.csv",
        "unique_values.csv",
    }
    assert set(paths) == expected_names
    assert {path.name for path in tmp_path.joinpath("profiling").iterdir()} == expected_names

    structural = pd.read_csv(paths["structural_profile.csv"])
    assert set(structural["table"]) == {"orders", "geolocation"}
    order_profile = structural.set_index("table").loc["orders"]
    assert order_profile["row_count"] == 2
    assert order_profile["column_count"] == 2
    assert "order_id" in order_profile["columns"]
    assert "order_id" in order_profile["dtypes"]
    assert "order_id" in order_profile["unique_counts"]
    assert order_profile["memory_usage_bytes"] > 0
