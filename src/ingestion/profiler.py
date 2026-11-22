"""Profiling helpers for the loaded Olist tables."""

from pathlib import Path
from typing import Any, Sequence

import pandas as pd


# Keys are based on the identifiers present in the supplied Olist dataset
# headers. The approved PRD relationship section was not present in the repo.
# Items and payments use composite keys; geolocation has no configured primary
# key because its ZIP prefix legitimately appears in multiple records.
DEFAULT_KEY_MAP: dict[str, str | tuple[str, ...]] = {
    "orders": "order_id",
    "customers": "customer_id",
    "order_items": ("order_id", "order_item_id"),
    "payments": ("order_id", "payment_sequential"),
    "reviews": "review_id",
    "products": "product_id",
    "sellers": "seller_id",
    "category_translation": "product_category_name",
}

REPORT_DIR = Path(__file__).resolve().parents[2] / "reports" / "profiling"


def profile_table(df: pd.DataFrame, name: str) -> dict[str, Any]:
    """Return structural statistics for one table.

    Unique counts exclude missing values. Memory usage includes the index and
    uses pandas' deep accounting for object-backed columns.
    """
    return {
        "table": name,
        "row_count": len(df.index),
        "column_count": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {column: str(dtype) for column, dtype in df.dtypes.items()},
        "unique_counts": {
            column: int(df[column].nunique(dropna=True)) for column in df.columns
        },
        "memory_usage_bytes": int(df.memory_usage(index=True, deep=True).sum()),
    }


def missing_report(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return one row per column with missing values across all tables."""
    rows: list[dict[str, Any]] = []
    for table, df in dfs.items():
        row_count = len(df.index)
        null_counts = df.isna().sum()
        for column, count in null_counts.items():
            null_count = int(count)
            if null_count:
                null_pct = (null_count / row_count * 100.0) if row_count else 0.0
                rows.append(
                    {
                        "table": table,
                        "column": column,
                        "null_count": null_count,
                        "null_pct": null_pct,
                    }
                )
    return pd.DataFrame(rows, columns=["table", "column", "null_count", "null_pct"])


def _normalize_key_columns(key_spec: str | Sequence[str]) -> list[str]:
    """Normalize a single or composite key specification to a list."""
    columns = [key_spec] if isinstance(key_spec, str) else list(key_spec)
    if not columns or any(not isinstance(column, str) or not column for column in columns):
        raise ValueError("Configured key columns must contain non-empty column names")
    return columns


def duplicate_report(
    dfs: dict[str, pd.DataFrame],
    key_map: dict[str, str | Sequence[str]],
) -> pd.DataFrame:
    """Report full-row duplicates and configured key duplicates per table.

    Tables without a configured key have a null key duplicate count and an
    empty key-column list. A key is valid only when all its columns exist.
    Duplicate counts measure extra rows beyond the first occurrence, not the
    number of distinct duplicated groups.
    """
    rows: list[dict[str, Any]] = []
    for table, df in dfs.items():
        key_columns: list[str] = []
        key_duplicate_count: int | None = None
        if table in key_map:
            key_columns = _normalize_key_columns(key_map[table])
            missing_columns = [column for column in key_columns if column not in df.columns]
            if missing_columns:
                raise ValueError(
                    f"Invalid key for table '{table}': column(s) not found: "
                    f"{', '.join(missing_columns)}"
                )
            key_duplicate_count = int(df.duplicated(subset=key_columns).sum())

        rows.append(
            {
                "table": table,
                "full_row_duplicate_count": int(df.duplicated().sum()),
                "key_columns": key_columns,
                "key_duplicate_count": key_duplicate_count,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "table",
            "full_row_duplicate_count",
            "key_columns",
            "key_duplicate_count",
        ],
    )


def unique_report(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return distinct non-null value counts for every table column."""
    rows = [
        {
            "table": table,
            "column": column,
            "distinct_value_count": int(df[column].nunique(dropna=True)),
        }
        for table, df in dfs.items()
        for column in df.columns
    ]
    return pd.DataFrame(rows, columns=["table", "column", "distinct_value_count"])


def save_report(df: pd.DataFrame, filename: str) -> Path:
    """Save a report CSV inside the project's ``reports/profiling`` directory.

    ``filename`` must be a plain filename, preventing path traversal outside
    the profiling directory.
    """
    if (
        not filename
        or filename in {".", ".."}
        or Path(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise ValueError("filename must be a plain filename inside reports/profiling")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = REPORT_DIR / filename
    df.to_csv(saved_path, index=False)
    return saved_path


def generate_all_reports(
    dfs: dict[str, pd.DataFrame],
    key_map: dict[str, str | Sequence[str]],
) -> dict[str, Path]:
    """Generate and save the four standard profiling reports."""
    structural_rows = [profile_table(df, name) for name, df in dfs.items()]
    reports = {
        "structural_profile.csv": pd.DataFrame(structural_rows),
        "missing_values.csv": missing_report(dfs),
        "duplicates.csv": duplicate_report(dfs, key_map),
        "unique_values.csv": unique_report(dfs),
    }
    return {filename: save_report(report, filename) for filename, report in reports.items()}
