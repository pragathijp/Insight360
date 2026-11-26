"""ZIP-prefix normalization and geolocation aggregation utilities."""

import logging
import math
import numbers
import re
from decimal import Decimal
from typing import Any

import pandas as pd


logger = logging.getLogger(__name__)
_GEOLOCATION_COLUMNS = [
    "geolocation_zip_code_prefix",
    "geolocation_lat",
    "geolocation_lng",
    "geolocation_city",
    "geolocation_state",
]


def _zip_text(value: Any) -> str | None:
    """Convert supported scalar ZIP inputs to normalized digit text."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        return re.sub(r"[^0-9]", "", value.strip())
    if isinstance(value, numbers.Integral):
        return str(int(value))
    if isinstance(value, numbers.Real):
        if math.isfinite(float(value)) and float(value).is_integer():
            return str(int(value))
        return None
    if isinstance(value, Decimal):
        if value.is_finite() and value == value.to_integral_value():
            return str(int(value))
        return None
    return None


def normalise_zip(series: pd.Series, width: int = 5) -> pd.Series:
    """Normalize ZIP-prefix values to fixed-width nullable digit strings.

    String inputs are stripped and have non-ASCII-digit characters removed.
    Integral numeric inputs are formatted as integer text; fractional numbers
    and booleans are invalid. Existing missing values remain missing. Newly
    invalid non-null values are counted in an INFO log record.
    """
    if not isinstance(series, pd.Series):
        raise ValueError("series must be a pandas Series")
    if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
        raise ValueError("width must be a positive integer")

    normalized: list[Any] = []
    newly_invalid = 0
    for value in series.tolist():
        if pd.isna(value) if pd.api.types.is_scalar(value) else False:
            normalized.append(pd.NA)
            continue

        digits = _zip_text(value)
        if not digits or len(digits) > width:
            normalized.append(pd.NA)
            newly_invalid += 1
            continue
        normalized.append(digits.zfill(width))

    logger.info("ZIP normalization newly_invalid_values=%d", newly_invalid)
    return pd.Series(
        pd.array(normalized, dtype="string"),
        index=series.index.copy(),
        name=series.name,
    )


def _mode_lexical(values: pd.Series) -> Any:
    """Return the most common non-null string, with lexical ascending ties."""
    non_null = values.dropna()
    if non_null.empty:
        return pd.NA
    if not non_null.map(lambda value: isinstance(value, str)).all():
        raise ValueError("geolocation city and state values must be strings or NULL")

    counts = non_null.value_counts()
    highest_count = counts.max()
    tied_values = counts[counts == highest_count].index.tolist()
    return sorted(tied_values)[0]


def aggregate_geolocation(geo: pd.DataFrame) -> pd.DataFrame:
    """Create one deterministic geolocation summary row per ZIP prefix.

    Coordinates are converted to numeric values and summarized by median.
    City and state use their non-null modes, with case-sensitive lexical
    ascending order resolving ties. Source rows, including exact duplicates,
    all participate in the aggregation.
    """
    if not isinstance(geo, pd.DataFrame):
        raise ValueError("geo must be a pandas DataFrame")
    if not geo.columns.is_unique:
        raise ValueError("geo must not contain duplicate column names")

    missing_columns = [column for column in _GEOLOCATION_COLUMNS if column not in geo]
    if missing_columns:
        raise ValueError(f"geo is missing required column(s): {missing_columns}")

    working = geo.loc[:, _GEOLOCATION_COLUMNS].copy(deep=True)
    working["geolocation_zip_code_prefix"] = normalise_zip(
        working["geolocation_zip_code_prefix"]
    )
    invalid_prefixes = working["geolocation_zip_code_prefix"].isna()
    if bool(invalid_prefixes.any()):
        raise ValueError(
            "geo contains missing or invalid ZIP prefixes after normalization: "
            f"{int(invalid_prefixes.sum())} row(s)"
        )

    for column in ("geolocation_lat", "geolocation_lng"):
        original = working[column]
        try:
            numeric = pd.to_numeric(original, errors="coerce")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                f"Could not convert coordinate column {column!r} to numeric: {exc}"
            ) from exc
        conversion_failures = original.notna() & numeric.isna()
        if bool(conversion_failures.any()):
            examples = original.loc[conversion_failures].head(5).tolist()
            raise ValueError(
                f"Could not convert coordinate column {column!r} to numeric; "
                f"invalid sample: {examples}"
            )
        working[column] = numeric

    if not working["geolocation_city"].dropna().map(
        lambda value: isinstance(value, str)
    ).all():
        raise ValueError("geolocation_city values must be strings or NULL")
    if not working["geolocation_state"].dropna().map(
        lambda value: isinstance(value, str)
    ).all():
        raise ValueError("geolocation_state values must be strings or NULL")

    grouped = working.groupby("geolocation_zip_code_prefix", sort=True)
    result = grouped.agg(
        {
            "geolocation_lat": "median",
            "geolocation_lng": "median",
            "geolocation_city": _mode_lexical,
            "geolocation_state": _mode_lexical,
        }
    ).reset_index()
    result = result.loc[:, _GEOLOCATION_COLUMNS]

    if not result["geolocation_zip_code_prefix"].is_unique:
        raise ValueError("Aggregated geolocation ZIP prefixes are not unique")
    return result
