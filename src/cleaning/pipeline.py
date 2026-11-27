"""Apply the approved Insight360 cleaning rules in a fixed order."""

from pathlib import Path
from typing import Any

import pandas as pd

from src.cleaning.categories import apply_translation, standardise_text
from src.cleaning.missing import handle_missing
from src.cleaning.types import standardise_dates, standardise_types
from src.cleaning.zip_codes import aggregate_geolocation, normalise_zip


DATASET_KEYS = (
    "orders",
    "customers",
    "order_items",
    "payments",
    "reviews",
    "products",
    "sellers",
    "geolocation",
    "category_translation",
)
REPORT_DIR = Path(__file__).resolve().parents[2] / "reports" / "profiling"
LOG_COLUMNS = [
    "table",
    "operation",
    "column",
    "rows_before",
    "rows_after",
    "rows_affected",
    "details",
]
_DATE_COLUMNS = {
    "orders": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "order_items": ["shipping_limit_date"],
    "reviews": ["review_creation_date", "review_answer_timestamp"],
}
_TYPE_SCHEMAS = {
    "order_items": {
        "order_item_id": "Int64",
        "price": "float64",
        "freight_value": "float64",
    },
    "payments": {
        "payment_sequential": "Int64",
        "payment_installments": "Int64",
        "payment_value": "float64",
    },
    "reviews": {"review_score": "Int64"},
    "products": {
        "product_name_lenght": "Int64",
        "product_description_lenght": "Int64",
        "product_photos_qty": "Int64",
        "product_weight_g": "float64",
        "product_length_cm": "float64",
        "product_height_cm": "float64",
        "product_width_cm": "float64",
    },
    "geolocation": {
        "geolocation_lat": "float64",
        "geolocation_lng": "float64",
    },
}
_TEXT_COLUMNS = {
    "orders": ["order_status"],
    "payments": ["payment_type"],
    "customers": ["customer_city", "customer_state"],
    "sellers": ["seller_city", "seller_state"],
    "geolocation": ["geolocation_city", "geolocation_state"],
    "products": ["product_category_name"],
    "category_translation": ["product_category_name"],
}
_MISSING_RULES = {
    "orders": [
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
    ],
    "reviews": ["review_comment_title", "review_comment_message"],
    "products": [
        "product_category_name",
        "product_name_lenght",
        "product_description_lenght",
        "product_photos_qty",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ],
}


def _validate_datasets(dfs: dict[str, pd.DataFrame]) -> None:
    if not isinstance(dfs, dict):
        raise ValueError("dfs must be a dictionary of dataset DataFrames")
    missing = [key for key in DATASET_KEYS if key not in dfs]
    if missing:
        raise ValueError(f"dfs is missing required dataset key(s): {missing}")
    invalid = [key for key in DATASET_KEYS if not isinstance(dfs[key], pd.DataFrame)]
    if invalid:
        raise ValueError(f"Dataset value(s) must be pandas DataFrames: {invalid}")


def _log(
    records: list[dict[str, Any]],
    *,
    table: str,
    operation: str,
    column: str | None,
    rows_before: int,
    rows_after: int,
    rows_affected: int | None,
    details: str,
) -> None:
    records.append(
        {
            "table": table,
            "operation": operation,
            "column": column,
            "rows_before": rows_before,
            "rows_after": rows_after,
            "rows_affected": rows_affected,
            "details": details,
        }
    )


def _changed_value_rows(
    before: pd.DataFrame,
    after: pd.DataFrame,
    columns: list[str],
) -> int:
    """Count rows with at least one changed scalar value, positionally.

    Equal values with different dtypes are not counted as changed. A row is
    counted once even when several configured columns change.
    """
    changed_rows = 0
    before_values = [before[column].array for column in columns]
    after_values = [after[column].array for column in columns]
    for position in range(len(before)):
        row_changed = False
        for old_column, new_column in zip(before_values, after_values, strict=True):
            old_value = old_column[position]
            new_value = new_column[position]
            old_missing = bool(pd.isna(old_value))
            new_missing = bool(pd.isna(new_value))
            if old_missing or new_missing:
                equal = old_missing and new_missing
            else:
                try:
                    equal = bool(old_value == new_value)
                except (TypeError, ValueError):
                    equal = False
            if not equal:
                row_changed = True
                break
        changed_rows += int(row_changed)
    return changed_rows


def _keep_missing_values(
    cleaned: dict[str, pd.DataFrame], records: list[dict[str, Any]]
) -> None:
    """Apply documented retain-as-is missing rules and capture action logs."""
    for table, columns in _MISSING_RULES.items():
        frame = cleaned[table]
        rule_set: dict[str, Any] = {"table": table}
        rule_set.update({column: {"action": "keep"} for column in columns})
        before = len(frame)
        result, actions = handle_missing(frame, rule_set)
        cleaned[table] = result
        for action in actions:
            _log(
                records,
                table=table,
                operation=f"handle_missing:{action['action']}",
                column=action["column"],
                rows_before=before,
                rows_after=len(result),
                rows_affected=action["rows_affected"],
                details="Retained source NULLs per DATA_QUALITY.md",
            )


def _add_delivered_timestamp_flags(
    orders: pd.DataFrame,
    records: list[dict[str, Any]],
) -> pd.DataFrame:
    result = orders.copy(deep=True)
    delivered = result["order_status"].eq("delivered").fillna(False)
    flag_specs = (
        ("order_delivered_customer_date", "is_delivery_date_missing"),
        ("order_delivered_carrier_date", "is_carrier_date_missing"),
    )
    for date_column, flag_column in flag_specs:
        if flag_column in result.columns:
            raise ValueError(f"orders already contains derived column {flag_column!r}")
        flag = pd.Series(pd.NA, index=result.index, dtype="boolean")
        missing = delivered & result[date_column].isna()
        flag.loc[delivered] = missing.loc[delivered].astype("boolean")
        result[flag_column] = flag
        _log(
            records,
            table="orders",
            operation="delivered_timestamp_missing_flag",
            column=flag_column,
            rows_before=len(result),
            rows_after=len(result),
            rows_affected=int(missing.sum()),
            details=f"True/False only for delivered orders; other statuses are NULL ({date_column})",
        )
    return result


def clean_all(
    dfs: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Return a cleaned copy of all source tables and an auditable log.

    Processing order: standardise selected text; retain configured missing
    values; parse dates and standardise documented numeric fields; create
    delivered-only flags; translate product categories; normalize ZIP columns;
    and derive ``geolocation_by_zip``. No source rows are automatically deleted.
    """
    _validate_datasets(dfs)
    cleaned = {key: value.copy(deep=True) for key, value in dfs.items()}
    records: list[dict[str, Any]] = []
    starting_rows = {table: len(cleaned[table]) for table in DATASET_KEYS}

    # 1. Normalize only categorical text fields specified by PRD FR-2.5.
    for table, columns in _TEXT_COLUMNS.items():
        before = cleaned[table]
        result = standardise_text(before, columns)
        for column in columns:
            changed = before[column].ne(result[column]) & before[column].notna()
            _log(
                records,
                table=table,
                operation="standardise_text",
                column=column,
                rows_before=len(before),
                rows_after=len(result),
                rows_affected=int(changed.sum()),
                details="Trimmed whitespace and lowercased selected text",
            )
        cleaned[table] = result

    # 2. Apply explicit retain-as-is NULL rules before parsing dates so the
    # action log distinguishes source NULLs from later parse failures.
    _keep_missing_values(cleaned, records)

    # 3. Parse every documented timestamp column; errors are reported by the
    # date helper as newly created NULLs and are not silently filled.
    for table, columns in _DATE_COLUMNS.items():
        before = cleaned[table]
        result = standardise_dates(before, columns)
        for column in columns:
            newly_missing = int(result[column].isna().sum() - before[column].isna().sum())
            _log(
                records,
                table=table,
                operation="standardise_dates",
                column=column,
                rows_before=len(before),
                rows_after=len(result),
                rows_affected=max(0, newly_missing),
                details="Invalid non-NULL timestamps become NaT and are counted",
            )
        cleaned[table] = result

    # 4. Convert documented numeric measures and counts. Identifiers remain
    # strings; invalid conversions surface as column-specific ValueErrors.
    for table, schema in _TYPE_SCHEMAS.items():
        before = cleaned[table]
        result = standardise_types(before, schema)
        _log(
            records,
            table=table,
            operation="standardise_types",
            column=None,
            rows_before=len(before),
            rows_after=len(result),
            rows_affected=_changed_value_rows(before, result, list(schema)),
            details=(
                "Rows with at least one scalar value changed by the explicit "
                f"schema conversion (equal values across dtypes are unchanged): {schema}"
            ),
        )
        cleaned[table] = result

    # 5. Apply the documented delivered-only missing timestamp flags.
    cleaned["orders"] = _add_delivered_timestamp_flags(cleaned["orders"], records)

    # 6. Translate once, retaining product rows and the source category value.
    product_rows = len(cleaned["products"])
    cleaned["products"] = apply_translation(
        cleaned["products"], cleaned["category_translation"]
    )
    _log(
        records,
        table="products",
        operation="apply_translation",
        column="product_category_name",
        rows_before=product_rows,
        rows_after=len(cleaned["products"]),
        rows_affected=int(cleaned["products"]["is_category_untranslated"].sum()),
        details="Left join; source category and product row count preserved",
    )

    # 7. Normalize the ZIP columns while retaining every original row.
    zip_columns = {
        "customers": "customer_zip_code_prefix",
        "sellers": "seller_zip_code_prefix",
        "geolocation": "geolocation_zip_code_prefix",
    }
    for table, column in zip_columns.items():
        before = cleaned[table]
        result = before.copy(deep=True)
        normalized = normalise_zip(before[column])
        newly_invalid = int((before[column].notna() & normalized.isna()).sum())
        result[column] = normalized
        cleaned[table] = result
        _log(
            records,
            table=table,
            operation="normalise_zip",
            column=column,
            rows_before=len(before),
            rows_after=len(result),
            rows_affected=newly_invalid,
            details="Invalid non-NULL prefixes become missing; rows retained",
        )

    # 8. Keep raw geolocation rows and add a separate unique-prefix lookup.
    raw_geo_count = len(cleaned["geolocation"])
    cleaned["geolocation_by_zip"] = aggregate_geolocation(cleaned["geolocation"])
    _log(
        records,
        table="geolocation_by_zip",
        operation="aggregate_geolocation",
        column="geolocation_zip_code_prefix",
        rows_before=raw_geo_count,
        rows_after=len(cleaned["geolocation_by_zip"]),
        rows_affected=raw_geo_count - len(cleaned["geolocation_by_zip"]),
        details="Derived median coordinates and deterministic city/state modes; source duplicates included",
    )

    for table in DATASET_KEYS:
        _log(
            records,
            table=table,
            operation="table_row_count_summary",
            column=None,
            rows_before=starting_rows[table],
            rows_after=len(cleaned[table]),
            rows_affected=starting_rows[table] - len(cleaned[table]),
            details="Source rows retained; no automatic duplicate removal",
        )

    log_df = pd.DataFrame(records, columns=LOG_COLUMNS)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    log_df.to_csv(REPORT_DIR / "cleaning_log.csv", index=False)
    return cleaned, log_df
