"""Text, category translation, and status validation utilities."""

from collections.abc import Collection
from typing import Any

import pandas as pd


_TRANSLATED_COLUMN = "product_category_name_english"
_UNTRANSLATED_FLAG = "is_category_untranslated"


def _validate_dataframe(df: pd.DataFrame, name: str = "df") -> None:
    """Validate a DataFrame with unambiguous column labels."""
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"{name} must be a pandas DataFrame")
    if not df.columns.is_unique:
        raise ValueError(f"{name} must not contain duplicate column names")


def standardise_text(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Trim and lowercase explicitly selected string columns on a copy.

    Missing values are retained. Non-null values in selected columns must be
    strings; the function never coerces other values to text.
    """
    _validate_dataframe(df)
    if not isinstance(cols, list) or any(
        not isinstance(column, str) or not column for column in cols
    ):
        raise ValueError("cols must be a list of non-empty column names")
    if len(cols) != len(set(cols)):
        raise ValueError("cols must not contain duplicate column names")

    unknown = [column for column in cols if column not in df.columns]
    if unknown:
        raise ValueError(f"Unknown text column(s): {unknown}")

    result = df.copy(deep=True)
    for column in cols:
        non_null = result[column].dropna()
        if not non_null.map(lambda value: isinstance(value, str)).all():
            raise ValueError(
                f"Column {column!r} contains non-null non-string values"
            )
        result[column] = result[column].map(
            lambda value: value.strip().lower() if isinstance(value, str) else value
        )
    return result


def apply_translation(
    products: pd.DataFrame,
    translation: pd.DataFrame,
) -> pd.DataFrame:
    """Left-join English category names without changing product row grain.

    Duplicate non-null Portuguese translation keys are rejected instead of
    selecting an arbitrary mapping. NULL keys are excluded from the lookup so
    that missing product categories cannot match missing translation keys.
    """
    _validate_dataframe(products, "products")
    _validate_dataframe(translation, "translation")

    required_product = "product_category_name"
    required_translation = {
        "product_category_name",
        _TRANSLATED_COLUMN,
    }
    missing_products = [
        column for column in [required_product] if column not in products.columns
    ]
    missing_translation = sorted(required_translation - set(translation.columns))
    if missing_products:
        raise ValueError(f"products is missing required column(s): {missing_products}")
    if missing_translation:
        raise ValueError(
            f"translation is missing required column(s): {missing_translation}"
        )

    existing_outputs = [
        column
        for column in (_TRANSLATED_COLUMN, _UNTRANSLATED_FLAG)
        if column in products.columns
    ]
    if existing_outputs:
        raise ValueError(
            f"products already contains output column(s): {existing_outputs}"
        )

    lookup = translation.loc[
        translation[required_product].notna(),
        [required_product, _TRANSLATED_COLUMN],
    ].copy(deep=True)
    duplicate_keys = lookup.loc[
        lookup[required_product].duplicated(keep=False), required_product
    ].drop_duplicates()
    if not duplicate_keys.empty:
        sample_keys = duplicate_keys.head(5).tolist()
        raise ValueError(
            "translation contains duplicate non-null product_category_name "
            f"keys; sample: {sample_keys}"
        )

    # A positional key preserves order and duplicate index values across merge.
    position_column = "__categories_row_position__"
    while position_column in products.columns or position_column in lookup.columns:
        position_column = f"_{position_column}"
    left = products.copy(deep=True)
    left[position_column] = range(len(left))
    result = left.merge(lookup, how="left", on=required_product, sort=False)
    if len(result) != len(products):
        raise ValueError(
            "Category translation changed product row count: "
            f"{len(products)} rows before join, {len(result)} after join"
        )

    result = result.sort_values(position_column, kind="stable")
    result[_UNTRANSLATED_FLAG] = (
        result[required_product].notna() & result[_TRANSLATED_COLUMN].isna()
    ).astype(bool)
    result = result.drop(columns=position_column)
    result.index = products.index.copy()
    return result


def validate_status(
    df: pd.DataFrame,
    valid: Collection[str],
) -> dict[str, Any]:
    """Validate ``order_status`` against caller-supplied values.

    NULL values count as invalid. Invalid data is reported as a FAIL result;
    malformed arguments raise ValueError. At most five offending values are
    included in the sample.
    """
    _validate_dataframe(df)
    if "order_status" not in df.columns:
        raise ValueError("df is missing required column 'order_status'")
    if (
        isinstance(valid, (str, bytes))
        or not isinstance(valid, Collection)
        or not valid
    ):
        raise ValueError("valid must be a non-empty collection of status strings")
    if any(not isinstance(value, str) or not value for value in valid):
        raise ValueError("valid must contain only non-empty status strings")

    invalid = df["order_status"].isna() | ~df["order_status"].isin(valid)
    sample = df.loc[invalid, "order_status"].head(5).tolist()
    return {
        "check": "valid_order_status",
        "table": None,
        "status": "FAIL" if bool(invalid.any()) else "PASS",
        "failed_rows": int(invalid.sum()),
        "sample": sample,
    }
