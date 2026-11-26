"""Utilities for applying explicitly configured missing-value rules."""

from collections.abc import Mapping
from typing import Any

import pandas as pd


_ACTIONS = {"keep", "fill_value", "flag", "drop_row"}
_UNSET = object()


def handle_missing(
    df: pd.DataFrame,
    rules: Mapping[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Apply configured missing-value actions to a copy of df.

    Rules map column names to an action string or a mapping containing an
    action key. fill_value rules also require value; flag rules may set
    flag_column. An optional top-level table value is copied into each log
    entry; it defaults to None.

    Example::

        {
            "table": "orders",
            "order_approved_at": {"action": "keep"},
            "customer_note": {"action": "fill_value", "value": "unknown"},
            "delivery_date": {"action": "flag"},
        }

    rows_affected counts missing values in the working column immediately
    before that rule is applied. Rules are processed in mapping insertion order.

    Args:
        df: DataFrame to process. The caller's DataFrame is never modified.
        rules: Mapping of column names to actions, optionally including a
            top-level table label for log entries.

    Returns:
        A copy of the DataFrame and one log dictionary per configured rule.

    Raises:
        ValueError: If a rule is malformed, uses an unsupported action,
            references an unknown column, or would overwrite an existing
            column with a generated flag.
    """
    if not isinstance(rules, Mapping):
        raise ValueError("rules must be a mapping of column names to actions")

    table_name: str | None = None
    column_rules: dict[str, Any] = dict(rules)
    if "table" in column_rules:
        table_name = column_rules.pop("table")
        if table_name is not None and (
            not isinstance(table_name, str) or not table_name
        ):
            raise ValueError("table metadata must be a non-empty string or None")

    normalised: list[tuple[str, str, Any]] = []
    generated_flag_columns: set[str] = set()
    for column, specification in column_rules.items():
        if not isinstance(column, str):
            raise ValueError(f"rule column names must be strings; got {column!r}")
        if column not in df.columns:
            raise ValueError(f"Rule references unknown DataFrame column {column!r}")

        if isinstance(specification, str):
            action = specification
            options: Mapping[str, Any] = {}
        elif isinstance(specification, Mapping):
            action = specification.get("action")
            options = specification
        else:
            raise ValueError(
                f"Rule for column {column!r} must be an action string or mapping"
            )

        if not isinstance(action, str) or action not in _ACTIONS:
            raise ValueError(
                f"Unsupported or missing action {action!r} for column {column!r}; "
                f"supported actions are {sorted(_ACTIONS)}"
            )

        allowed_options = {"action"}
        if action == "fill_value":
            allowed_options.add("value")
            if "value" not in options:
                raise ValueError(
                    f"fill_value rule for column {column!r} requires an explicit 'value'"
                )
            fill_value = options["value"]
            if (
                not pd.api.types.is_scalar(fill_value)
                or bool(pd.isna(fill_value))
            ):
                raise ValueError(
                    f"fill_value for column {column!r} must be a non-missing scalar"
                )
            normalised.append((column, action, fill_value))
        elif action == "flag":
            allowed_options.add("flag_column")
            flag_column = options.get("flag_column", f"is_{column}_missing")
            if not isinstance(flag_column, str) or not flag_column:
                raise ValueError(
                    f"flag_column for column {column!r} must be a non-empty string"
                )
            if (
                flag_column == column
                or flag_column in df.columns
                or flag_column in generated_flag_columns
            ):
                raise ValueError(
                    f"Flag column {flag_column!r} for {column!r} already exists"
                )
            generated_flag_columns.add(flag_column)
            normalised.append((column, action, flag_column))
        else:
            normalised.append((column, action, _UNSET))

        extra_options = set(options) - allowed_options
        if extra_options:
            raise ValueError(
                f"Unexpected option(s) for {action!r} rule on {column!r}: "
                f"{sorted(extra_options)}"
            )

    result = df.copy(deep=True)
    log: list[dict[str, Any]] = []
    for column, action, option in normalised:
        missing = result[column].isna()
        rows_affected = int(missing.sum())

        if action == "fill_value":
            result[column] = result[column].fillna(option)
        elif action == "flag":
            result[option] = missing.astype(bool)
        elif action == "drop_row":
            result = result.loc[~missing].copy()
        # keep intentionally leaves the source column unchanged.

        log.append(
            {
                "table": table_name,
                "column": column,
                "action": action,
                "rows_affected": rows_affected,
            }
        )

    return result, log
