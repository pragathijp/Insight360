"""Tests for configured missing-value handling."""

import pandas as pd
import pytest

from src.cleaning.missing import handle_missing


def test_keep_retains_missing_values_and_logs_count():
    frame = pd.DataFrame({"value": [1, None, 3]})

    result, log = handle_missing(frame, {"value": {"action": "keep"}})

    assert result["value"].isna().sum() == 1
    assert log == [
        {"table": None, "column": "value", "action": "keep", "rows_affected": 1}
    ]


def test_fill_value_replaces_missing_values():
    frame = pd.DataFrame({"value": ["a", None, "c"]})

    result, log = handle_missing(
        frame,
        {
            "table": "sample",
            "value": {"action": "fill_value", "value": "missing"},
        },
    )

    assert result["value"].tolist() == ["a", "missing", "c"]
    assert log[0] == {
        "table": "sample",
        "column": "value",
        "action": "fill_value",
        "rows_affected": 1,
    }


def test_none_table_metadata_is_removed_before_column_rules():
    frame = pd.DataFrame({"value": [None]})

    result, log = handle_missing(
        frame, {"table": None, "value": {"action": "keep"}}
    )

    assert result["value"].isna().sum() == 1
    assert log[0]["table"] is None


@pytest.mark.parametrize("table", ["", 123, []])
def test_invalid_table_metadata_raises_value_error(table):
    frame = pd.DataFrame({"value": [None]})

    with pytest.raises(ValueError, match="table metadata"):
        handle_missing(frame, {"table": table, "value": {"action": "keep"}})


def test_flag_creates_boolean_column_and_keeps_source_missing_values():
    frame = pd.DataFrame({"value": [1, None, 3]})

    result, log = handle_missing(frame, {"value": {"action": "flag"}})

    assert result["is_value_missing"].tolist() == [False, True, False]
    assert result["is_value_missing"].dtype == bool
    assert result["value"].isna().sum() == 1
    assert log[0]["rows_affected"] == 1


def test_flag_uses_explicit_flag_column_name():
    frame = pd.DataFrame({"comment": [None, "ok"]})

    result, _ = handle_missing(
        frame, {"comment": {"action": "flag", "flag_column": "has_no_comment"}}
    )

    assert result["has_no_comment"].tolist() == [True, False]


def test_flag_does_not_overwrite_existing_or_duplicate_flag_columns():
    frame = pd.DataFrame({"first": [None], "second": [None], "existing": [False]})

    with pytest.raises(ValueError, match="already exists"):
        handle_missing(frame, {"first": {"action": "flag", "flag_column": "existing"}})

    with pytest.raises(ValueError, match="already exists"):
        handle_missing(
            frame,
            {
                "first": {"action": "flag", "flag_column": "missing_flag"},
                "second": {"action": "flag", "flag_column": "missing_flag"},
            },
        )


def test_drop_row_removes_only_missing_rows_and_preserves_index():
    frame = pd.DataFrame(
        {"value": [1, None, 3], "other": [None, "keep", "also keep"]},
        index=[10, 20, 30],
    )

    result, log = handle_missing(frame, {"value": {"action": "drop_row"}})

    assert result.index.tolist() == [10, 30]
    assert result["value"].tolist() == [1.0, 3.0]
    assert pd.isna(result.loc[10, "other"])
    assert result.loc[30, "other"] == "also keep"
    assert log[0]["rows_affected"] == 1


def test_multiple_column_rules_are_applied_in_order_and_logged():
    frame = pd.DataFrame({"first": [None, 1, None], "second": ["x", None, None]})

    result, log = handle_missing(
        frame,
        {
            "first": {"action": "fill_value", "value": 0},
            "second": {"action": "flag"},
        },
    )

    assert result["first"].tolist() == [0.0, 1.0, 0.0]
    assert result["is_second_missing"].tolist() == [False, True, True]
    assert [entry["rows_affected"] for entry in log] == [2, 2]
    assert [entry["column"] for entry in log] == ["first", "second"]


def test_original_dataframe_is_not_modified():
    frame = pd.DataFrame({"value": [None, "text"]}, index=[5, 9])
    original = frame.copy(deep=True)

    handle_missing(frame, {"value": {"action": "fill_value", "value": "filled"}})

    pd.testing.assert_frame_equal(frame, original)


def test_keep_and_flag_preserve_original_index():
    frame = pd.DataFrame({"value": [None, 2]}, index=[7, 11])

    result, _ = handle_missing(frame, {"value": {"action": "flag"}})

    assert result.index.tolist() == [7, 11]


def test_zero_and_empty_string_are_not_treated_as_missing():
    frame = pd.DataFrame({"value": [0, "", None]})

    result, log = handle_missing(frame, {"value": {"action": "keep"}})

    assert result["value"].isna().sum() == 1
    assert log[0]["rows_affected"] == 1


def test_unsupported_action_raises_value_error():
    frame = pd.DataFrame({"value": [None]})

    with pytest.raises(ValueError, match="Unsupported"):
        handle_missing(frame, {"value": {"action": "interpolate"}})


def test_missing_fill_value_raises_value_error():
    frame = pd.DataFrame({"value": [None]})

    with pytest.raises(ValueError, match="requires an explicit 'value'"):
        handle_missing(frame, {"value": {"action": "fill_value"}})


def test_unknown_column_raises_clear_value_error():
    frame = pd.DataFrame({"value": [1]})

    with pytest.raises(ValueError, match="unknown DataFrame column 'missing'"):
        handle_missing(frame, {"missing": {"action": "keep"}})


@pytest.mark.parametrize(
    "rules",
    [
        None,
        {"value": None},
        {"value": {}},
        {"value": {"action": "keep", "unexpected": True}},
        {"value": {"action": "flag", "flag_column": ""}},
    ],
)
def test_invalid_rule_configurations_raise_value_error(rules):
    frame = pd.DataFrame({"value": [None]})

    with pytest.raises(ValueError):
        handle_missing(frame, rules)
