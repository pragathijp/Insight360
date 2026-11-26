"""Reusable data-quality validation checks for Insight360 tables."""

from collections.abc import Collection
import math
import numbers
import re
from typing import Any

import pandas as pd


_SAMPLE_LIMIT = 5


def _validate_df(df: pd.DataFrame, name: str = "df") -> None:
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"{name} must be a pandas DataFrame")
    if not df.columns.is_unique:
        raise ValueError(f"{name} must not contain duplicate column names")


def _require_column(df: pd.DataFrame, column: str, name: str = "df") -> None:
    if not isinstance(column, str) or not column:
        raise ValueError("column names must be non-empty strings")
    if column not in df.columns:
        raise ValueError(f"{name} is missing required column {column!r}")


def _result(check: str, failed_rows: int, sample: list[Any]) -> dict[str, Any]:
    """Build the common, fixed-shape validation result."""
    return {
        "check": check,
        "table": None,
        "status": "FAIL" if failed_rows else "PASS",
        "failed_rows": int(failed_rows),
        "sample": sample[:_SAMPLE_LIMIT],
    }


def _sample_value(value: Any) -> Any:
    """Represent scalar NULLs uniformly in returned sample records."""
    if pd.api.types.is_scalar(value) and bool(pd.isna(value)):
        return None
    return value


def _validate_columns(df: pd.DataFrame, cols: list[str]) -> None:
    if not isinstance(cols, list) or not cols:
        raise ValueError("cols must be a non-empty list of column names")
    if any(not isinstance(column, str) or not column for column in cols):
        raise ValueError("cols must contain non-empty string column names")
    if len(set(cols)) != len(cols):
        raise ValueError("cols must not contain duplicate column names")
    unknown = [column for column in cols if column not in df.columns]
    if unknown:
        raise ValueError(f"Unknown column(s): {unknown}")


def check_pk(df: pd.DataFrame, cols: list[str]) -> dict[str, Any]:
    """Check complete primary-key values for uniqueness.

    Rows missing any key component fail. Among complete keys, duplicate
    failures count extra rows beyond the first occurrence of each key.
    """
    _validate_df(df)
    _validate_columns(df, cols)

    complete = df[cols].notna().all(axis=1)
    incomplete = ~complete
    duplicate_extra = pd.Series(False, index=df.index)
    duplicate_extra.loc[complete] = df.loc[complete].duplicated(
        subset=cols, keep="first"
    ).to_numpy()
    failed = incomplete | duplicate_extra

    samples: list[dict[str, Any]] = []
    for position, (index, row) in enumerate(df.iterrows()):
        if not bool(failed.iloc[position]):
            continue
        key = {column: _sample_value(row[column]) for column in cols}
        issue = "incomplete_key" if bool(incomplete.iloc[position]) else "duplicate_extra"
        samples.append({"index": index, "issue": issue, "key": key})
        if len(samples) == _SAMPLE_LIMIT:
            break

    return _result("primary_key_uniqueness", int(failed.sum()), samples)


def check_fk(
    child: pd.DataFrame,
    parent: pd.DataFrame,
    child_col: str,
    parent_col: str,
) -> dict[str, Any]:
    """Count non-NULL child rows whose key is absent from the parent table."""
    _validate_df(child, "child")
    _validate_df(parent, "parent")
    _require_column(child, child_col, "child")
    _require_column(parent, parent_col, "parent")

    child_values = child[child_col]
    parent_values = parent[parent_col].dropna()
    orphan_mask = child_values.notna() & ~child_values.isin(parent_values)
    samples = [
        {"index": index, "value": _sample_value(value)}
        for index, value in child.loc[orphan_mask, child_col].items()
    ][: _SAMPLE_LIMIT]
    return _result("foreign_key_integrity", int(orphan_mask.sum()), samples)


def check_nulls(
    df: pd.DataFrame,
    expected_null_cols: list[str],
) -> dict[str, Any]:
    """Check for NULLs outside explicitly expected-NULL columns.

    A row is counted once even if multiple unexpected-NULL columns occur in
    that row. Expected columns are exempt without applying status conditions.
    """
    _validate_df(df)
    if not isinstance(expected_null_cols, list):
        raise ValueError("expected_null_cols must be a list of column names")
    if any(not isinstance(column, str) or not column for column in expected_null_cols):
        raise ValueError("expected_null_cols must contain non-empty strings")
    if len(set(expected_null_cols)) != len(expected_null_cols):
        raise ValueError("expected_null_cols must not contain duplicates")
    unknown = [column for column in expected_null_cols if column not in df.columns]
    if unknown:
        raise ValueError(f"Unknown expected-NULL column(s): {unknown}")

    unexpected_cols = [
        column for column in df.columns if column not in set(expected_null_cols)
    ]
    if unexpected_cols:
        null_mask = df[unexpected_cols].isna()
        failed = null_mask.any(axis=1)
    else:
        null_mask = pd.DataFrame(False, index=df.index, columns=[])
        failed = pd.Series(False, index=df.index)

    samples: list[dict[str, Any]] = []
    for position, (index, _) in enumerate(df.iterrows()):
        if not bool(failed.iloc[position]):
            continue
        missing_columns = [
            column for column in unexpected_cols if bool(null_mask.iloc[position][column])
        ]
        samples.append({"index": index, "columns": missing_columns})
        if len(samples) == _SAMPLE_LIMIT:
            break
    return _result("unexpected_nulls", int(failed.sum()), samples)


def check_allowed_values(
    df: pd.DataFrame,
    col: str,
    allowed: Collection[Any],
) -> dict[str, Any]:
    """Check that non-NULL values belong to ``allowed``; NULLs also fail."""
    _validate_df(df)
    _require_column(df, col)
    if (
        isinstance(allowed, (str, bytes))
        or not isinstance(allowed, Collection)
        or len(allowed) == 0
    ):
        raise ValueError("allowed must be a non-empty collection of values")
    if any(
        pd.api.types.is_scalar(value) and bool(pd.isna(value))
        for value in allowed
    ):
        raise ValueError("allowed must not contain NULL values")

    values = df[col]
    failed = values.isna() | ~values.isin(allowed)
    samples = [
        {"index": index, "value": _sample_value(value)}
        for index, value in values.loc[failed].items()
    ][: _SAMPLE_LIMIT]
    return _result("allowed_values", int(failed.sum()), samples)


def _numeric_bounds(lo: Any, hi: Any) -> tuple[float, float]:
    if (
        isinstance(lo, bool)
        or isinstance(hi, bool)
        or not isinstance(lo, numbers.Real)
        or not isinstance(hi, numbers.Real)
        or not math.isfinite(float(lo))
        or not math.isfinite(float(hi))
        or lo > hi
    ):
        raise ValueError("lo and hi must be finite numeric bounds with lo <= hi")
    return float(lo), float(hi)


def _numeric_values(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return numeric values and a mask of invalid non-NULL source values."""
    try:
        values = pd.to_numeric(series, errors="coerce")
    except (TypeError, ValueError, OverflowError):
        values = series.map(
            lambda value: pd.to_numeric(value, errors="coerce")
            if pd.api.types.is_scalar(value) and not pd.isna(value)
            else pd.NA
        )
    invalid = series.notna() & values.isna()
    return values, invalid


def check_range(
    df: pd.DataFrame,
    col: str,
    lo: float,
    hi: float,
) -> dict[str, Any]:
    """Check numeric values against inclusive bounds; NULLs are skipped."""
    _validate_df(df)
    _require_column(df, col)
    lower, upper = _numeric_bounds(lo, hi)
    values, invalid = _numeric_values(df[col])
    failed = invalid | (values.notna() & ((values < lower) | (values > upper)))
    samples = [
        {"index": index, "value": _sample_value(value)}
        for index, value in df.loc[failed, col].items()
    ][: _SAMPLE_LIMIT]
    return _result("numeric_range", int(failed.sum()), samples)


def check_monetary(df: pd.DataFrame, cols: list[str]) -> dict[str, Any]:
    """Flag negative or non-numeric non-NULL monetary values.

    Zero values are allowed and NULLs are skipped. This check does not apply
    statistical outlier thresholds.
    """
    _validate_df(df)
    _validate_columns(df, cols)

    failed = pd.Series(False, index=df.index)
    per_column_failures: dict[str, pd.Series] = {}
    for column in cols:
        values, invalid = _numeric_values(df[column])
        negative = values.map(
            lambda value: not pd.isna(value) and bool(value < 0)
        )
        non_finite = values.map(
            lambda value: not pd.isna(value) and not math.isfinite(float(value))
        )
        column_failed = invalid | negative | non_finite
        per_column_failures[column] = column_failed
        failed |= column_failed

    samples: list[dict[str, Any]] = []
    for position, (index, row) in enumerate(df.iterrows()):
        if not bool(failed.iloc[position]):
            continue
        issues = [
            {"column": column, "value": _sample_value(row[column])}
            for column in cols
            if bool(per_column_failures[column].iloc[position])
        ]
        samples.append({"index": index, "issues": issues})
        if len(samples) == _SAMPLE_LIMIT:
            break
    return _result("monetary_values", int(failed.sum()), samples)


def check_timestamp_order(
    df: pd.DataFrame,
    earlier_col: str,
    later_col: str,
) -> dict[str, Any]:
    """Check chronological order, skipping source NULL pairs.

    Equal timestamps pass. Non-NULL parse failures and valid pairs where the
    later timestamp precedes the earlier timestamp fail.
    """
    _validate_df(df)
    _require_column(df, earlier_col)
    _require_column(df, later_col)

    earlier_raw = df[earlier_col]
    later_raw = df[later_col]
    failed_positions: list[bool] = [False] * len(df)
    issue_by_position: dict[int, str] = {}
    for position in range(len(df)):
        earlier_value = earlier_raw.iloc[position]
        later_value = later_raw.iloc[position]

        # A source NULL makes ordering ineligible; don't parse the companion value.
        if pd.isna(earlier_value) or pd.isna(later_value):
            continue

        try:
            earlier = pd.to_datetime(earlier_value, errors="coerce")
            later = pd.to_datetime(later_value, errors="coerce")
        except (TypeError, ValueError, OverflowError):
            failed_positions[position] = True
            issue_by_position[position] = "invalid_timestamp"
            continue

        if pd.isna(earlier) or pd.isna(later):
            failed_positions[position] = True
            issue_by_position[position] = "invalid_timestamp"
            continue
        try:
            if later < earlier:
                failed_positions[position] = True
                issue_by_position[position] = "order_violation"
        except (TypeError, ValueError):
            failed_positions[position] = True
            issue_by_position[position] = "invalid_timestamp"

    failed_count = sum(failed_positions)
    samples: list[dict[str, Any]] = []
    for position, (index, row) in enumerate(df.iterrows()):
        if not failed_positions[position]:
            continue
        samples.append(
            {
                "index": index,
                "issue": issue_by_position[position],
                "earlier": _sample_value(row[earlier_col]),
                "later": _sample_value(row[later_col]),
            }
        )
        if len(samples) == _SAMPLE_LIMIT:
            break
    return _result("timestamp_order", failed_count, samples)


def check_zip_format(series: pd.Series, width: int) -> dict[str, Any]:
    """Validate fixed-width ASCII digit ZIP strings without normalizing them."""
    if not isinstance(series, pd.Series):
        raise ValueError("series must be a pandas Series")
    if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
        raise ValueError("width must be a positive integer")

    valid = series.map(
        lambda value: isinstance(value, str)
        and re.fullmatch(rf"[0-9]{{{width}}}", value) is not None
    )
    failed = ~valid
    samples = [
        {"index": index, "value": _sample_value(value)}
        for index, value in series.loc[failed].items()
    ][: _SAMPLE_LIMIT]
    return _result("zip_format", int(failed.sum()), samples)
