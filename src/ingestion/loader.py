"""Load the Olist CSV datasets into pandas DataFrames."""

import logging
from pathlib import Path

import pandas as pd
from pandas.errors import ParserError

from src.config import EXPECTED_FILES

logger = logging.getLogger(__name__)

_DATASET_KEYS: tuple[str, ...] = (
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


def _read_csv(path: Path) -> pd.DataFrame:
    """Read one CSV as strings, retrying with Latin-1 if UTF-8 decoding fails."""
    try:
        try:
            return pd.read_csv(path, dtype=str, encoding="utf-8")
        except UnicodeDecodeError:
            logger.info("UTF-8 decoding failed for %s; retrying with Latin-1", path.name)
            return pd.read_csv(path, dtype=str, encoding="latin-1")
    except ParserError as exc:
        raise ValueError(f"Could not parse CSV file '{path.name}': {exc}") from exc
    except FileNotFoundError:
        raise
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(f"Could not read CSV file '{path.name}': {exc}") from exc


def load_all(raw_dir: str | Path) -> dict[str, pd.DataFrame]:
    """Load all nine expected Olist CSV files from ``raw_dir``.

    Values are initially read as strings. Missing values retain pandas' default
    interpretation, and no date parsing or other transformations are applied.

    Args:
        raw_dir: Directory containing the Olist CSV files.

    Returns:
        DataFrames keyed by dataset name.

    Raises:
        RuntimeError: If a file cannot be read.
        ValueError: If a file contains malformed CSV data.
    """
    directory = Path(raw_dir)
    datasets: dict[str, pd.DataFrame] = {}

    for key, filename in zip(_DATASET_KEYS, EXPECTED_FILES, strict=True):
        dataframe = _read_csv(directory / filename)
        datasets[key] = dataframe
        logger.info(
            "Loaded %s: %d rows, %d columns",
            filename,
            len(dataframe.index),
            len(dataframe.columns),
        )

    return datasets
