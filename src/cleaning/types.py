"""Date and dtype standardization utilities for cleaned DataFrames."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.extensions import ExtensionDtype


logger = logging.getLogger(__name__)


def standardise_dates(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Convert selected columns to datetime and report newly created NULLs.

    Conversion uses pandas.to_datetime with errors set to coerce, so invalid
    date strings become NaT. Missing values present before conversion remain
    distinguishable from parse failures in the logged per-column counts. The
    caller's DataFrame is not modified.

    Args:
        df: DataFrame to convert.
        cols: List of date column names to standardise.

    Returns:
        A copied DataFrame with the selected columns converted to datetime.

    Raises:
        ValueError: If df or cols is invalid or a requested column is unknown.
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")
    if not isinstance(cols, list) or any(
        not isinstance(column, str) or not column for column in cols
    ):
        raise ValueError("cols must be a list of non-empty column names")

    unknown_columns = [column for column in cols if column not in df.columns]
    if unknown_columns:
        raise ValueError(f"Unknown date column(s): {unknown_columns}")

    result = df.copy(deep=True)
    for column in cols:
        original_nulls = int(df[column].isna().sum())
        converted = pd.to_datetime(result[column], errors="coerce")
        new_nulls = int(converted.isna().sum()) - original_nulls
        result[column] = converted
        logger.info(
            "Date standardisation column=%s newly_created_nulls=%d",
            column,
            new_nulls,
        )

    return result


def standardise_types(
    df: pd.DataFrame,
    schema: dict[str, Any],
) -> pd.DataFrame:
    """Convert explicitly mapped columns to their requested dtypes.

    Args:
        df: DataFrame to convert.
        schema: Dictionary mapping existing column names to target dtypes.

    Returns:
        A copied DataFrame with only schema-mapped columns converted.

    Raises:
        ValueError: If df or schema is invalid, a column is unknown, or a
            value cannot be converted to its requested dtype.
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")
    if not isinstance(schema, dict):
        raise ValueError("schema must be a dictionary mapping columns to dtypes")

    invalid_keys = [
        column
        for column in schema
        if not isinstance(column, str) or not column
    ]
    if invalid_keys:
        raise ValueError(f"schema keys must be non-empty column names: {invalid_keys}")

    unknown_columns = [column for column in schema if column not in df.columns]
    if unknown_columns:
        raise ValueError(f"Unknown column(s) in schema: {unknown_columns}")

    result = df.copy(deep=True)
    for column, target_dtype in schema.items():
        if target_dtype is None:
            raise ValueError(f"Target dtype for column {column!r} cannot be None")
        if not isinstance(target_dtype, (str, type, np.dtype, ExtensionDtype)):
            raise ValueError(
                f"Invalid target dtype for column {column!r}: {target_dtype!r}"
            )

        try:
            result[column] = result[column].astype(target_dtype)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"Could not convert column {column!r} to dtype "
                f"{target_dtype!r}: {exc}"
            ) from exc

    return result
