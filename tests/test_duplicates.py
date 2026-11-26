"""Tests for duplicate detection and explicitly configured removal."""

import pandas as pd
import pytest

from src.cleaning.duplicates import drop_duplicates_logged, find_duplicates


def test_find_duplicates_by_single_key_includes_first_occurrence():
    frame = pd.DataFrame(
        {"order_id": ["a", "b", "a"], "value": [1, 2, 3]},
        index=[10, 20, 30],
    )

    result = find_duplicates(frame, ["order_id"])

    assert result.index.tolist() == [10, 30]
    assert result["value"].tolist() == [1, 3]


def test_find_duplicates_by_composite_key():
    frame = pd.DataFrame(
        {
            "order_id": ["a", "a", "a", "b"],
            "item_id": [1, 1, 2, 1],
            "value": [10, 11, 12, 13],
        }
    )

    result = find_duplicates(frame, ["order_id", "item_id"])

    assert result.index.tolist() == [0, 1]
    assert result[["order_id", "item_id"]].values.tolist() == [["a", 1], ["a", 1]]


def test_find_duplicates_returns_empty_dataframe_when_no_duplicates():
    frame = pd.DataFrame({"id": ["a", "b"], "value": [1, 1]}, index=[4, 8])

    result = find_duplicates(frame, ["id"])

    assert result.empty
    assert result.columns.tolist() == frame.columns.tolist()


def test_keep_first_retains_first_occurrence_and_reports_removed_count():
    frame = pd.DataFrame(
        {"id": ["a", "b", "a", "c"], "value": [1, 2, 3, 4]},
        index=[5, 7, 9, 11],
    )

    result, removed = drop_duplicates_logged(frame, ["id"])

    assert result.index.tolist() == [5, 7, 11]
    assert result["value"].tolist() == [1, 2, 4]
    assert removed == 1


def test_keep_last_retains_last_occurrence_and_reports_removed_count():
    frame = pd.DataFrame(
        {"id": ["a", "b", "a", "c"], "value": [1, 2, 3, 4]},
        index=[5, 7, 9, 11],
    )

    result, removed = drop_duplicates_logged(frame, ["id"], keep="last")

    assert result.index.tolist() == [7, 9, 11]
    assert result["value"].tolist() == [2, 3, 4]
    assert removed == 1


def test_deduplication_preserves_relative_order_and_original_index():
    frame = pd.DataFrame(
        {"id": ["x", "y", "x", "z", "y"], "position": [0, 1, 2, 3, 4]},
        index=[20, 10, 30, 40, 50],
    )

    result, removed = drop_duplicates_logged(frame, ["id"], keep="last")

    assert result.index.tolist() == [30, 40, 50]
    assert result["position"].tolist() == [2, 3, 4]
    assert removed == 2


def test_input_dataframe_remains_unchanged():
    frame = pd.DataFrame({"id": ["a", "a"], "value": [1, 2]}, index=[3, 8])
    original = frame.copy(deep=True)

    find_duplicates(frame, ["id"])
    drop_duplicates_logged(frame, ["id"])

    pd.testing.assert_frame_equal(frame, original)


def test_missing_key_values_follow_pandas_duplicate_semantics():
    frame = pd.DataFrame({"id": [None, None, "a"], "value": [1, 2, 3]})

    found = find_duplicates(frame, ["id"])
    result, removed = drop_duplicates_logged(frame, ["id"])

    assert found.index.tolist() == [0, 1]
    assert result.index.tolist() == [0, 2]
    assert removed == 1


def test_empty_key_columns_raise_value_error():
    frame = pd.DataFrame({"id": [1]})

    with pytest.raises(ValueError, match="non-empty list"):
        find_duplicates(frame, [])


def test_unknown_key_columns_raise_value_error():
    frame = pd.DataFrame({"id": [1]})

    with pytest.raises(ValueError, match="Unknown key column"):
        find_duplicates(frame, ["missing"])


@pytest.mark.parametrize("keep", ["all", "none", None, 1])
def test_invalid_keep_values_raise_value_error(keep):
    frame = pd.DataFrame({"id": [1, 1]})

    with pytest.raises(ValueError, match="keep must be either"):
        drop_duplicates_logged(frame, ["id"], keep=keep)


@pytest.mark.parametrize("key_cols", [None, "id", ("id",), ["",], [1]])
def test_malformed_key_column_arguments_raise_value_error(key_cols):
    frame = pd.DataFrame({"id": [1, 1]})

    with pytest.raises(ValueError, match="key_cols|Unknown key"):
        find_duplicates(frame, key_cols)


@pytest.mark.parametrize("function", [find_duplicates, drop_duplicates_logged])
def test_invalid_dataframe_raises_clear_value_error(function):
    with pytest.raises(ValueError, match="pandas DataFrame"):
        function(None, ["id"])
