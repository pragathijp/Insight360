"""Tests for the reusable Insight360 validation checks."""

import pandas as pd
import pytest

from src.validation.checks import (
    check_allowed_values,
    check_fk,
    check_monetary,
    check_nulls,
    check_pk,
    check_range,
    check_timestamp_order,
    check_zip_format,
)


_RESULT_KEYS = {"check", "table", "status", "failed_rows", "sample"}


def assert_result(result, *, check, status, failed_rows):
    assert set(result) == _RESULT_KEYS
    assert result["check"] == check
    assert result["table"] is None
    assert result["status"] == status
    assert result["failed_rows"] == failed_rows
    assert len(result["sample"]) <= 5


def test_check_pk_passes_for_unique_single_and_composite_keys():
    single = check_pk(pd.DataFrame({"id": ["a", "b"]}), ["id"])
    composite = check_pk(
        pd.DataFrame({"order_id": ["a", "a"], "item_id": [1, 2]}),
        ["order_id", "item_id"],
    )

    assert_result(single, check="primary_key_uniqueness", status="PASS", failed_rows=0)
    assert_result(composite, check="primary_key_uniqueness", status="PASS", failed_rows=0)


def test_check_pk_counts_incomplete_rows_and_duplicate_extras():
    frame = pd.DataFrame(
        {
            "order_id": ["a", "a", "a", "b", None],
            "item_id": [1, 1, 1, None, 2],
        },
        index=[10, 11, 12, 13, 14],
    )

    result = check_pk(frame, ["order_id", "item_id"])

    assert_result(result, check="primary_key_uniqueness", status="FAIL", failed_rows=4)
    assert result["sample"] == [
        {"index": 11, "issue": "duplicate_extra", "key": {"order_id": "a", "item_id": 1}},
        {"index": 12, "issue": "duplicate_extra", "key": {"order_id": "a", "item_id": 1}},
        {"index": 13, "issue": "incomplete_key", "key": {"order_id": "b", "item_id": None}},
        {"index": 14, "issue": "incomplete_key", "key": {"order_id": None, "item_id": 2}},
    ]


def test_check_pk_sample_is_limited_to_five_rows():
    frame = pd.DataFrame({"id": ["a"] * 7})

    result = check_pk(frame, ["id"])

    assert result["failed_rows"] == 6
    assert len(result["sample"]) == 5


def test_check_pk_handles_duplicate_dataframe_index_labels():
    frame = pd.DataFrame({"id": ["dup", "dup", "ok", None]}, index=[5, 5, 8, 8])

    result = check_pk(frame, ["id"])

    assert_result(result, check="primary_key_uniqueness", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {"index": 5, "issue": "duplicate_extra", "key": {"id": "dup"}},
        {"index": 8, "issue": "incomplete_key", "key": {"id": None}},
    ]


@pytest.mark.parametrize(
    ("df", "cols"),
    [
        (None, ["id"]),
        (pd.DataFrame({"id": [1]}), []),
        (pd.DataFrame({"id": [1]}), "id"),
        (pd.DataFrame({"id": [1]}), [""]),
        (pd.DataFrame({"id": [1]}), ["missing"]),
        (pd.DataFrame({"id": [1]}), ["id", "id"]),
    ],
)
def test_check_pk_rejects_invalid_arguments(df, cols):
    with pytest.raises(ValueError):
        check_pk(df, cols)


def test_check_fk_ignores_nulls_and_counts_orphan_child_rows():
    child = pd.DataFrame({"parent_id": ["a", "missing", "missing", None, "other"]}, index=[4, 5, 6, 7, 8])
    parent = pd.DataFrame({"id": ["a", None]})

    result = check_fk(child, parent, "parent_id", "id")

    assert_result(result, check="foreign_key_integrity", status="FAIL", failed_rows=3)
    assert result["sample"] == [
        {"index": 5, "value": "missing"},
        {"index": 6, "value": "missing"},
        {"index": 8, "value": "other"},
    ]


def test_check_fk_passes_when_all_non_null_child_keys_exist():
    result = check_fk(
        pd.DataFrame({"fk": ["a", None]}),
        pd.DataFrame({"pk": ["a", None]}),
        "fk",
        "pk",
    )

    assert_result(result, check="foreign_key_integrity", status="PASS", failed_rows=0)


@pytest.mark.parametrize(
    ("child", "parent", "child_col", "parent_col"),
    [
        (None, pd.DataFrame({"id": []}), "id", "id"),
        (pd.DataFrame({"id": []}), None, "id", "id"),
        (pd.DataFrame({"id": []}), pd.DataFrame({"id": []}), "missing", "id"),
        (pd.DataFrame({"id": []}), pd.DataFrame({"id": []}), "id", "missing"),
        (pd.DataFrame({"id": []}), pd.DataFrame({"id": []}), "", "id"),
    ],
)
def test_check_fk_rejects_invalid_arguments(child, parent, child_col, parent_col):
    with pytest.raises(ValueError):
        check_fk(child, parent, child_col, parent_col)


def test_check_nulls_exempts_only_named_columns_and_counts_rows_once():
    frame = pd.DataFrame(
        {
            "optional": [None, None, "present", None],
            "first": [None, None, "ok", "ok"],
            "second": ["ok", None, "ok", None],
        },
        index=[20, 21, 22, 23],
    )

    result = check_nulls(frame, ["optional"])

    assert_result(result, check="unexpected_nulls", status="FAIL", failed_rows=3)
    assert result["sample"] == [
        {"index": 20, "columns": ["first"]},
        {"index": 21, "columns": ["first", "second"]},
        {"index": 23, "columns": ["second"]},
    ]


def test_check_nulls_passes_when_only_expected_nulls_are_present():
    result = check_nulls(pd.DataFrame({"optional": [None, "x"]}), ["optional"])

    assert_result(result, check="unexpected_nulls", status="PASS", failed_rows=0)


@pytest.mark.parametrize(
    ("df", "expected"),
    [
        (None, []),
        (pd.DataFrame({"x": [None]}), None),
        (pd.DataFrame({"x": [None]}), "x"),
        (pd.DataFrame({"x": [None]}), ["missing"]),
        (pd.DataFrame({"x": [None]}), ["x", "x"]),
    ],
)
def test_check_nulls_rejects_invalid_arguments(df, expected):
    with pytest.raises(ValueError):
        check_nulls(df, expected)


def test_check_allowed_values_fails_for_null_and_unlisted_values():
    frame = pd.DataFrame({"order_status": ["delivered", "cancelled", None]}, index=[1, 2, 3])

    result = check_allowed_values(frame, "order_status", {"delivered", "canceled"})

    assert_result(result, check="allowed_values", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {"index": 2, "value": "cancelled"},
        {"index": 3, "value": None},
    ]


@pytest.mark.parametrize("allowed", ["x", b"x", [], set(), None, [None]])
def test_check_allowed_values_rejects_invalid_allowed_values(allowed):
    with pytest.raises(ValueError):
        check_allowed_values(pd.DataFrame({"x": ["x"]}), "x", allowed)


def test_check_allowed_values_rejects_invalid_dataframe_or_column():
    with pytest.raises(ValueError, match="pandas DataFrame"):
        check_allowed_values(None, "x", ["x"])
    with pytest.raises(ValueError, match="missing required column"):
        check_allowed_values(pd.DataFrame(), "x", ["x"])


def test_check_range_uses_inclusive_bounds_and_skips_nulls():
    frame = pd.DataFrame({"score": [1, 3, 5, 0, 6, None]}, index=[10, 11, 12, 13, 14, 15])

    result = check_range(frame, "score", 1, 5)

    assert_result(result, check="numeric_range", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {"index": 13, "value": 0},
        {"index": 14, "value": 6},
    ]


def test_check_range_counts_unparseable_non_null_values_as_failures():
    result = check_range(pd.DataFrame({"amount": ["2.5", "bad", None]}), "amount", 0, 3)

    assert_result(result, check="numeric_range", status="FAIL", failed_rows=1)
    assert result["sample"] == [{"index": 1, "value": "bad"}]


@pytest.mark.parametrize("bounds", [(5, 1), (float("nan"), 1), (0, float("inf")), (True, 2), ("0", 2)])
def test_check_range_rejects_invalid_bounds(bounds):
    with pytest.raises(ValueError, match="finite numeric bounds"):
        check_range(pd.DataFrame({"x": [1]}), "x", *bounds)


def test_check_range_rejects_invalid_dataframe_or_column():
    with pytest.raises(ValueError, match="pandas DataFrame"):
        check_range(None, "x", 0, 1)
    with pytest.raises(ValueError, match="missing required column"):
        check_range(pd.DataFrame(), "x", 0, 1)


def test_check_monetary_allows_zero_skips_null_and_fails_negative_or_text():
    frame = pd.DataFrame(
        {"price": [0, 1.5, -2, "not-money", None], "freight": [0, 0, 0, 0, None]},
        index=[4, 5, 6, 7, 8],
    )

    result = check_monetary(frame, ["price", "freight"])

    assert_result(result, check="monetary_values", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {"index": 6, "issues": [{"column": "price", "value": -2}]},
        {"index": 7, "issues": [{"column": "price", "value": "not-money"}]},
    ]


def test_check_monetary_passes_zero_and_positive_values():
    result = check_monetary(pd.DataFrame({"payment": [0, "2.50", None]}), ["payment"])

    assert_result(result, check="monetary_values", status="PASS", failed_rows=0)


def test_check_monetary_fails_positive_and_negative_infinity():
    frame = pd.DataFrame({"amount": [float("inf"), float("-inf"), 0, 2.5]})

    result = check_monetary(frame, ["amount"])

    assert_result(result, check="monetary_values", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {"index": 0, "issues": [{"column": "amount", "value": float("inf")}]},
        {"index": 1, "issues": [{"column": "amount", "value": float("-inf")}]},
    ]


def test_check_monetary_counts_row_once_when_multiple_columns_fail():
    frame = pd.DataFrame(
        {
            "price": [-1, "invalid", 2],
            "freight": [float("inf"), -3, 0],
        },
        index=[7, 8, 9],
    )

    result = check_monetary(frame, ["price", "freight"])

    assert_result(result, check="monetary_values", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {
            "index": 7,
            "issues": [
                {"column": "price", "value": -1},
                {"column": "freight", "value": float("inf")},
            ],
        },
        {
            "index": 8,
            "issues": [
                {"column": "price", "value": "invalid"},
                {"column": "freight", "value": -3},
            ],
        },
    ]


def test_check_monetary_handles_duplicate_dataframe_index_labels():
    frame = pd.DataFrame({"amount": [-1, 0, -2]}, index=[5, 5, 8])

    result = check_monetary(frame, ["amount"])

    assert_result(result, check="monetary_values", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {"index": 5, "issues": [{"column": "amount", "value": -1}]},
        {"index": 8, "issues": [{"column": "amount", "value": -2}]},
    ]


@pytest.mark.parametrize(
    ("df", "cols"),
    [
        (None, ["amount"]),
        (pd.DataFrame({"amount": [1]}), []),
        (pd.DataFrame({"amount": [1]}), "amount"),
        (pd.DataFrame({"amount": [1]}), ["missing"]),
        (pd.DataFrame({"amount": [1]}), ["amount", "amount"]),
    ],
)
def test_check_monetary_rejects_invalid_arguments(df, cols):
    with pytest.raises(ValueError):
        check_monetary(df, cols)


def test_check_timestamp_order_passes_in_order_equal_and_null_pairs():
    frame = pd.DataFrame(
        {
            "earlier": ["2024-01-01", "2024-01-01", None],
            "later": ["2024-01-02", "2024-01-01", "2024-01-02"],
        }
    )

    result = check_timestamp_order(frame, "earlier", "later")

    assert_result(result, check="timestamp_order", status="PASS", failed_rows=0)


def test_check_timestamp_order_fails_reversed_and_invalid_non_null_timestamps():
    frame = pd.DataFrame(
        {
            "earlier": ["2024-01-02", "not-a-date", None, "2024-01-01"],
            "later": ["2024-01-01", "2024-01-03", "not-a-date", "2024-01-02"],
        },
        index=[8, 9, 10, 11],
    )

    result = check_timestamp_order(frame, "earlier", "later")

    assert_result(result, check="timestamp_order", status="FAIL", failed_rows=2)
    assert result["sample"] == [
        {"index": 8, "issue": "order_violation", "earlier": "2024-01-02", "later": "2024-01-01"},
        {"index": 9, "issue": "invalid_timestamp", "earlier": "not-a-date", "later": "2024-01-03"},
    ]


def test_check_timestamp_order_skips_null_invalid_pair_but_checks_complete_pairs():
    frame = pd.DataFrame(
        {
            "earlier": [
                None,
                "invalid-earlier",
                "2024-01-01",
                "2024-01-02",
                "2024-01-01",
            ],
            "later": [
                "invalid-later",
                "2024-01-02",
                "invalid-later",
                "2024-01-01",
                "2024-01-01",
            ],
        },
        index=[10, 11, 12, 13, 14],
    )

    result = check_timestamp_order(frame, "earlier", "later")

    assert_result(result, check="timestamp_order", status="FAIL", failed_rows=3)
    assert result["sample"] == [
        {
            "index": 11,
            "issue": "invalid_timestamp",
            "earlier": "invalid-earlier",
            "later": "2024-01-02",
        },
        {
            "index": 12,
            "issue": "invalid_timestamp",
            "earlier": "2024-01-01",
            "later": "invalid-later",
        },
        {
            "index": 13,
            "issue": "order_violation",
            "earlier": "2024-01-02",
            "later": "2024-01-01",
        },
    ]


def test_check_timestamp_order_rejects_invalid_dataframe_or_columns():
    with pytest.raises(ValueError, match="pandas DataFrame"):
        check_timestamp_order(None, "a", "b")
    with pytest.raises(ValueError, match="missing required column"):
        check_timestamp_order(pd.DataFrame({"a": []}), "a", "b")


def test_check_zip_format_requires_exact_width_ascii_digits_and_keeps_zeroes():
    series = pd.Series(["01046", "12345", "1046", "12 45", 12345, None], index=[4, 5, 6, 7, 8, 9])

    result = check_zip_format(series, 5)

    assert_result(result, check="zip_format", status="FAIL", failed_rows=4)
    assert result["sample"] == [
        {"index": 6, "value": "1046"},
        {"index": 7, "value": "12 45"},
        {"index": 8, "value": 12345},
        {"index": 9, "value": None},
    ]


def test_check_zip_format_passes_custom_width_and_limits_sample():
    valid = check_zip_format(pd.Series(["0007", "1234"]), 4)
    many_bad = check_zip_format(pd.Series(["x"] * 7), 5)

    assert_result(valid, check="zip_format", status="PASS", failed_rows=0)
    assert_result(many_bad, check="zip_format", status="FAIL", failed_rows=7)
    assert len(many_bad["sample"]) == 5


@pytest.mark.parametrize("width", [0, -1, 2.5, True, None])
def test_check_zip_format_rejects_invalid_width(width):
    with pytest.raises(ValueError, match="width must be a positive integer"):
        check_zip_format(pd.Series(["12"]), width)


def test_check_zip_format_rejects_non_series_input():
    with pytest.raises(ValueError, match="pandas Series"):
        check_zip_format(["01046"], 5)


def test_checks_do_not_modify_inputs():
    df = pd.DataFrame({"id": ["a", "a"], "amount": [1, -1]}, index=[8, 2])
    child = pd.DataFrame({"fk": ["x", None]})
    parent = pd.DataFrame({"pk": ["y", None]})
    zip_series = pd.Series(["01046", None], index=[3, 4])
    snapshots = [df.copy(deep=True), child.copy(deep=True), parent.copy(deep=True)]
    zip_snapshot = zip_series.copy(deep=True)

    check_pk(df, ["id"])
    check_fk(child, parent, "fk", "pk")
    check_nulls(df, [])
    check_allowed_values(df, "id", ["a"])
    check_range(df, "amount", 0, 2)
    check_monetary(df, ["amount"])
    check_timestamp_order(
        pd.DataFrame({"start": ["2024-01-01"], "end": ["2024-01-02"]}),
        "start",
        "end",
    )
    check_zip_format(zip_series, 5)

    pd.testing.assert_frame_equal(df, snapshots[0])
    pd.testing.assert_frame_equal(child, snapshots[1])
    pd.testing.assert_frame_equal(parent, snapshots[2])
    pd.testing.assert_series_equal(zip_series, zip_snapshot)
