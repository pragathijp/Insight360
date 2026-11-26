"""Tests for date and dtype standardisation."""

import logging

import pandas as pd
import pytest

from src.cleaning.types import standardise_dates, standardise_types


def test_standardise_dates_converts_valid_values():
    frame = pd.DataFrame({"date": ["2024-01-02", "2024-03-04"]})

    result = standardise_dates(frame, ["date"])

    assert pd.api.types.is_datetime64_any_dtype(result["date"])
    assert result["date"].tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-03-04"),
    ]


def test_invalid_date_strings_become_nat_and_are_reported(caplog):
    frame = pd.DataFrame({"date": ["2024-01-02", "bad-date", "also-bad"]})
    caplog.set_level(logging.INFO, logger="src.cleaning.types")

    result = standardise_dates(frame, ["date"])

    assert result["date"].isna().tolist() == [False, True, True]
    assert "column=date newly_created_nulls=2" in caplog.text


def test_existing_nulls_are_excluded_from_new_null_count(caplog):
    frame = pd.DataFrame({"date": ["2024-01-02", None, pd.NA]})
    caplog.set_level(logging.INFO, logger="src.cleaning.types")

    result = standardise_dates(frame, ["date"])

    assert result["date"].isna().tolist() == [False, True, True]
    assert "column=date newly_created_nulls=0" in caplog.text


def test_standardise_dates_reports_new_nulls_separately_from_existing_nulls(caplog):
    frame = pd.DataFrame({"date": ["2024-02-01", "bad-date", None]})
    caplog.set_level(logging.INFO, logger="src.cleaning.types")

    result = standardise_dates(frame, ["date"])

    assert result["date"].isna().tolist() == [False, True, True]
    assert "column=date newly_created_nulls=1" in caplog.text


def test_standardise_multiple_date_columns():
    frame = pd.DataFrame(
        {"purchased": ["2024-01-01"], "delivered": ["2024-01-03"]}
    )

    result = standardise_dates(frame, ["purchased", "delivered"])

    assert all(
        pd.api.types.is_datetime64_any_dtype(result[column])
        for column in frame.columns
    )
    assert result.loc[0, "delivered"] > result.loc[0, "purchased"]


def test_standardise_types_uses_schema_and_preserves_leading_zeroes():
    frame = pd.DataFrame(
        {
            "customer_id": ["0012", None],
            "zip_code": ["02140", "00007"],
            "quantity": ["1", "3"],
            "price": ["10.5", "2"],
        }
    )

    result = standardise_types(
        frame,
        {
            "customer_id": "string",
            "zip_code": "string",
            "quantity": "Int64",
            "price": "float64",
        },
    )

    assert str(result["customer_id"].dtype) == "string"
    assert str(result["zip_code"].dtype) == "string"
    assert result["customer_id"].iloc[0] == "0012"
    assert result["zip_code"].tolist() == ["02140", "00007"]
    assert str(result["quantity"].dtype) == "Int64"
    assert str(result["price"].dtype) == "float64"


def test_standardise_types_preserves_missing_values_for_nullable_dtypes():
    frame = pd.DataFrame({"quantity": ["1", None], "identifier": ["001", None]})

    result = standardise_types(
        frame, {"quantity": "Int64", "identifier": "string"}
    )

    assert pd.isna(result.loc[1, "quantity"])
    assert pd.isna(result.loc[1, "identifier"])


def test_standardise_types_raises_column_specific_conversion_error():
    frame = pd.DataFrame({"price": ["1.5", "not-numeric"]})

    with pytest.raises(ValueError, match="column 'price'.*float64"):
        standardise_types(frame, {"price": "float64"})


def test_unknown_date_column_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown date column.*missing"):
        standardise_dates(pd.DataFrame({"date": ["2024-01-01"]}), ["missing"])


def test_unknown_schema_column_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown column.*missing"):
        standardise_types(pd.DataFrame({"value": [1]}), {"missing": "Int64"})


@pytest.mark.parametrize("df", [None, {"date": ["2024-01-01"]}])
def test_invalid_dataframe_raises_clear_error(df):
    with pytest.raises(ValueError, match="pandas DataFrame"):
        standardise_dates(df, [])
    with pytest.raises(ValueError, match="pandas DataFrame"):
        standardise_types(df, {})


@pytest.mark.parametrize("cols", [None, "date", ("date",), [1], [""]])
def test_invalid_date_column_arguments_raise_clear_error(cols):
    frame = pd.DataFrame({"date": ["2024-01-01"]})

    with pytest.raises(ValueError, match="cols"):
        standardise_dates(frame, cols)


@pytest.mark.parametrize("schema", [None, [("value", "Int64")], "value"])
def test_invalid_schema_arguments_raise_clear_error(schema):
    with pytest.raises(ValueError, match="schema must be a dictionary"):
        standardise_types(pd.DataFrame({"value": [1]}), schema)


@pytest.mark.parametrize(
    "schema", [{1: "string"}, {"value": None}, {"value": []}]
)
def test_invalid_schema_entries_raise_clear_error(schema):
    with pytest.raises(ValueError):
        standardise_types(pd.DataFrame({"value": [1]}), schema)


def test_functions_preserve_input_index_order_and_unrelated_columns():
    frame = pd.DataFrame(
        {
            "date": ["2024-02-01", "bad-date", "2024-01-01"],
            "identifier": ["0002", "0001", "0003"],
            "unrelated": ["a", "b", "c"],
        },
        index=[9, 3, 7],
    )
    original = frame.copy(deep=True)

    dates = standardise_dates(frame, ["date"])
    result = standardise_types(dates, {"identifier": "string"})

    pd.testing.assert_frame_equal(frame, original)
    assert result.index.tolist() == [9, 3, 7]
    assert result["identifier"].tolist() == ["0002", "0001", "0003"]
    assert result["unrelated"].tolist() == ["a", "b", "c"]
