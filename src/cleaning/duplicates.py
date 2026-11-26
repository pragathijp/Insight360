"""Utilities for inspecting and explicitly removing duplicate key rows."""

import pandas as pd


def _validate_inputs(df: pd.DataFrame, key_cols: list[str]) -> None:
    """Validate the DataFrame and caller-supplied key columns."""
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")
    if not isinstance(key_cols, list) or not key_cols:
        raise ValueError("key_cols must be a non-empty list of column names")
    if any(not isinstance(column, str) or not column for column in key_cols):
        raise ValueError("key_cols must contain non-empty string column names")

    unknown_columns = [column for column in key_cols if column not in df.columns]
    if unknown_columns:
        raise ValueError(f"Unknown key column(s): {unknown_columns}")


def find_duplicates(df: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    """Return all rows in duplicate key groups, including first occurrences.

    Duplicate identification follows Pandas DataFrame.duplicated semantics,
    including its treatment of missing key values as duplicates when their
    key values match. The input is not modified, and source row order and
    index values are preserved.

    Args:
        df: DataFrame to inspect.
        key_cols: Non-empty list of columns defining duplicate groups.

    Returns:
        A copy containing every row whose key occurs more than once.

    Raises:
        ValueError: If df is not a DataFrame or key_cols is invalid.
    """
    _validate_inputs(df, key_cols)
    duplicate_mask = df.duplicated(subset=key_cols, keep=False)
    return df.loc[duplicate_mask].copy()


def drop_duplicates_logged(
    df: pd.DataFrame,
    key_cols: list[str],
    keep: str = "first",
) -> tuple[pd.DataFrame, int]:
    """Remove duplicate key rows and return the cleaned copy and removal count.

    Missing key values follow Pandas duplicate semantics: rows with equivalent
    missing key values are considered duplicates. No row is removed unless it
    belongs to a duplicate key group, and the retained rows keep their source
    order and index values.

    Args:
        df: DataFrame to process. The input is not modified.
        key_cols: Non-empty list of columns defining duplicate groups.
        keep: Retain the first or last row of each duplicate key group.

    Returns:
        A tuple containing the deduplicated DataFrame and number of rows
        removed.

    Raises:
        ValueError: If df, key_cols, or keep is invalid.
    """
    _validate_inputs(df, key_cols)
    if not isinstance(keep, str) or keep not in {"first", "last"}:
        raise ValueError("keep must be either 'first' or 'last'")

    duplicate_mask = df.duplicated(subset=key_cols, keep=keep)
    result = df.loc[~duplicate_mask].copy()
    rows_removed = len(df) - len(result)
    return result, rows_removed
