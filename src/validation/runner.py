"""Orchestrate Insight360 validation checks and save their report."""

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from src.cleaning.zip_codes import normalise_zip
from src.ingestion.profiler import DEFAULT_KEY_MAP
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
REPORT_COLUMNS = ["check", "table", "status", "failed_rows", "sample"]
_TIMESTAMP_PAIRS = (
    ("order_purchase_timestamp", "order_approved_at"),
    ("order_purchase_timestamp", "order_delivered_carrier_date"),
    ("order_approved_at", "order_delivered_carrier_date"),
    ("order_delivered_carrier_date", "order_delivered_customer_date"),
    ("order_purchase_timestamp", "order_delivered_customer_date"),
    ("order_purchase_timestamp", "order_estimated_delivery_date"),
)
_EXPECTED_NULLS = {
    # Delivery date NULLs are handled separately for delivered orders below.
    "orders": ["order_delivered_carrier_date", "order_delivered_customer_date"],
    # A missing source category is explicitly retained as an allowed NULL.
    "products": ["product_category_name"],
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


def _record(
    rows: list[dict[str, Any]],
    table: str,
    result: dict[str, Any],
    *,
    check_name: str | None = None,
) -> None:
    row = dict(result)
    row["table"] = table
    if check_name is not None:
        row["check"] = check_name
    rows.append({column: row[column] for column in REPORT_COLUMNS})


def _custom_result(
    check: str,
    table: str,
    failed_rows: int,
    sample: list[Any],
    *,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "check": check,
        "table": table,
        "status": status or ("FAIL" if failed_rows else "PASS"),
        "failed_rows": int(failed_rows),
        "sample": sample[:5],
    }


def _json_safe(value: Any) -> Any:
    """Convert sample values to strict JSON-compatible scalars and containers."""
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if pd.api.types.is_scalar(value):
        try:
            if bool(pd.isna(value)):
                return None
        except (TypeError, ValueError):
            pass
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    return value


def _geolocation_lookup(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return distinct valid ZIP prefixes for referential coverage checks.

    Coverage depends only on ZIP prefixes, so it remains checkable when raw
    geolocation coordinates are invalid. All required raw geolocation columns
    are still validated here; coordinate aggregation and validation remain the
    responsibility of ``aggregate_geolocation`` in the cleaning pipeline.
    """
    geo = dfs["geolocation"]
    required = (
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    )
    missing = [column for column in required if column not in geo.columns]
    if missing:
        raise ValueError(f"geolocation is missing required column(s): {missing}")

    if "geolocation_by_zip" in dfs:
        aggregate = dfs["geolocation_by_zip"]
        if not isinstance(aggregate, pd.DataFrame):
            raise ValueError("geolocation_by_zip must be a pandas DataFrame")
        if "geolocation_zip_code_prefix" not in aggregate.columns:
            raise ValueError(
                "geolocation_by_zip is missing required column "
                "'geolocation_zip_code_prefix'"
            )
        normalized = normalise_zip(aggregate["geolocation_zip_code_prefix"])
        prefixes = normalized.dropna().drop_duplicates().sort_values()
        return pd.DataFrame({"geolocation_zip_code_prefix": prefixes.tolist()})

    normalized = normalise_zip(geo["geolocation_zip_code_prefix"])
    prefixes = normalized.dropna().drop_duplicates().sort_values()
    return pd.DataFrame({"geolocation_zip_code_prefix": prefixes.tolist()})


def _geolocation_duplicate_result(geo: pd.DataFrame) -> dict[str, Any]:
    duplicate_extra = geo.duplicated(keep="first")
    samples = [
        {"index": index, "row": row.to_dict()}
        for index, row in geo.loc[duplicate_extra].head(5).iterrows()
    ]
    return _custom_result(
        "full_row_duplicates", "geolocation", int(duplicate_extra.sum()), samples
    )


def _orders_without_child_result(
    orders: pd.DataFrame,
    children: pd.DataFrame,
    check_name: str,
) -> dict[str, Any]:
    child_ids = children["order_id"].dropna()
    missing_mask = orders["order_id"].notna() & ~orders["order_id"].isin(child_ids)
    sample = [
        {
            "order_id": row["order_id"],
            "order_status": row["order_status"],
            "interpretation": "review by status; absence alone does not establish invalidity",
        }
        for _, row in orders.loc[missing_mask, ["order_id", "order_status"]]
        .head(5)
        .iterrows()
    ]
    count = int(missing_mask.sum())
    return _custom_result(
        check_name,
        "orders",
        count,
        sample,
        status="REVIEW" if count else "PASS",
    )


def run_all_checks(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Run applicable documented validations and save a CSV report.

    The returned table column identifies the dataset context even though the
    individual check functions do not accept a table-name argument.
    """
    _validate_datasets(dfs)
    rows: list[dict[str, Any]] = []

    for table, key_columns in DEFAULT_KEY_MAP.items():
        _record(rows, table, check_pk(dfs[table], list(key_columns) if isinstance(key_columns, tuple) else [key_columns]))

    # NULL checks: unresolved fields are deliberately not exempted, so they
    # remain visible as FAIL results pending a source/business decision.
    for table in DATASET_KEYS:
        expected = list(_EXPECTED_NULLS.get(table, []))
        if table == "orders":
            expected.extend(
                column
                for column in ("is_delivery_date_missing", "is_carrier_date_missing")
                if column in dfs[table].columns
            )
        if table == "products" and "product_category_name_english" in dfs[table].columns:
            expected.append("product_category_name_english")
        _record(rows, table, check_nulls(dfs[table], expected))

    # DQ-01/DQ-09: delivered orders should have both delivery timestamps.
    orders = dfs["orders"]
    delivered = orders.loc[
        orders["order_status"].eq("delivered"),
        ["order_delivered_carrier_date", "order_delivered_customer_date"],
    ]
    delivered_result = check_nulls(delivered, [])
    _record(
        rows,
        "orders",
        delivered_result,
        check_name="delivered_delivery_timestamps",
    )

    relationships = [
        ("orders", "customer_id", "customers", "customer_id"),
        ("order_items", "order_id", "orders", "order_id"),
        ("payments", "order_id", "orders", "order_id"),
        ("reviews", "order_id", "orders", "order_id"),
        ("order_items", "product_id", "products", "product_id"),
        ("order_items", "seller_id", "sellers", "seller_id"),
        (
            "products",
            "product_category_name",
            "category_translation",
            "product_category_name",
        ),
    ]
    for child_table, child_col, parent_table, parent_col in relationships:
        name = f"{child_table}.{child_col}->{parent_table}.{parent_col}"
        _record(
            rows,
            child_table,
            check_fk(dfs[child_table], dfs[parent_table], child_col, parent_col),
            check_name=f"foreign_key:{name}",
        )

    geo_lookup = _geolocation_lookup(dfs)
    for table, zip_column in (
        ("customers", "customer_zip_code_prefix"),
        ("sellers", "seller_zip_code_prefix"),
    ):
        _record(
            rows,
            table,
            check_fk(
                dfs[table],
                geo_lookup,
                zip_column,
                "geolocation_zip_code_prefix",
            ),
            check_name=f"zip_prefix_coverage:{table}.{zip_column}->geolocation",
        )

    # The order-status check is intentionally omitted: the observed status set
    # is not an authoritative allowed-values contract.
    allowed_scores: set[Any] = {1, 2, 3, 4, 5, "1", "2", "3", "4", "5"}
    _record(rows, "reviews", check_range(dfs["reviews"], "review_score", 1, 5))
    _record(
        rows,
        "reviews",
        check_allowed_values(dfs["reviews"], "review_score", allowed_scores),
        check_name="review_score_integer_1_to_5",
    )

    for table, columns in (
        ("order_items", ["price", "freight_value"]),
        ("payments", ["payment_value"]),
    ):
        _record(rows, table, check_monetary(dfs[table], columns))

    for earlier_col, later_col in _TIMESTAMP_PAIRS:
        check_name = f"timestamp_order:{earlier_col}<={later_col}"
        _record(
            rows,
            "orders",
            check_timestamp_order(orders, earlier_col, later_col),
            check_name=check_name,
        )

    for table, column in (
        ("customers", "customer_zip_code_prefix"),
        ("sellers", "seller_zip_code_prefix"),
        ("geolocation", "geolocation_zip_code_prefix"),
    ):
        _record(rows, table, check_zip_format(dfs[table][column], 5))

    # Raw geolocation is intentionally not checked as a PK; DQ-05 is a
    # separate full-row duplicate finding.
    rows.append(_geolocation_duplicate_result(dfs["geolocation"]))
    rows.append(
        _orders_without_child_result(
            orders, dfs["order_items"], "orders_without_items"
        )
    )
    rows.append(
        _orders_without_child_result(
            orders, dfs["payments"], "orders_without_payments"
        )
    )

    report = pd.DataFrame(rows, columns=REPORT_COLUMNS)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_report = report.copy(deep=True)
    csv_report["sample"] = csv_report["sample"].map(
        lambda sample: json.dumps(
            _json_safe(sample), ensure_ascii=False, default=str, allow_nan=False
        )
    )
    csv_report.to_csv(REPORT_DIR / "data_quality_results.csv", index=False)
    return report
