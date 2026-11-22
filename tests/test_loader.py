"""Tests for loading the Olist CSV datasets."""

import pandas as pd
import pytest
from pandas.api.types import is_string_dtype

from src.config import EXPECTED_FILES
from src.ingestion.loader import load_all


DATASET_KEYS = [
    "orders",
    "customers",
    "order_items",
    "payments",
    "reviews",
    "products",
    "sellers",
    "geolocation",
    "category_translation",
]


def _write_csvs(raw_dir, *, first_file_text="id,value\n1,sample\n"):
    """Write one small CSV file per expected dataset."""
    for index, filename in enumerate(EXPECTED_FILES):
        content = first_file_text if index == 0 else "id,value\n1,sample\n"
        (raw_dir / filename).write_text(content, encoding="utf-8")


def test_loads_all_nine_csv_files(tmp_path):
    _write_csvs(tmp_path)

    datasets = load_all(tmp_path)

    assert len(datasets) == 9
    assert all(not dataframe.empty for dataframe in datasets.values())


def test_returns_expected_keys_and_dataframes(tmp_path):
    _write_csvs(tmp_path)

    datasets = load_all(tmp_path)

    assert list(datasets) == DATASET_KEYS
    assert all(isinstance(frame, pd.DataFrame) for frame in datasets.values())


@pytest.mark.parametrize(
    ("filename", "column"),
    [
        ("olist_customers_dataset.csv", "customer_zip_code_prefix"),
        ("olist_sellers_dataset.csv", "seller_zip_code_prefix"),
        ("olist_geolocation_dataset.csv", "geolocation_zip_code_prefix"),
    ],
)
def test_zip_prefix_columns_are_strings(tmp_path, filename, column):
    _write_csvs(tmp_path)
    (tmp_path / filename).write_text(f"{column}\n01234\n", encoding="utf-8")

    datasets = load_all(tmp_path)

    values = datasets[DATASET_KEYS[EXPECTED_FILES.index(filename)]][column]
    assert is_string_dtype(values.dtype)
    assert values.iloc[0] == "01234"


def test_dates_remain_strings(tmp_path):
    _write_csvs(tmp_path, first_file_text="order_date\n2017-01-02 03:04:05\n")

    dates = load_all(tmp_path)["orders"]["order_date"]

    assert is_string_dtype(dates.dtype)
    assert not pd.api.types.is_datetime64_any_dtype(dates.dtype)
    assert dates.iloc[0] == "2017-01-02 03:04:05"


def test_missing_file_raises_with_filename(tmp_path):
    _write_csvs(tmp_path)
    missing_filename = EXPECTED_FILES[0]
    (tmp_path / missing_filename).unlink()

    with pytest.raises(FileNotFoundError, match=missing_filename):
        load_all(tmp_path)


def test_missing_csv_preserves_file_not_found_error(tmp_path):
    _write_csvs(tmp_path)
    missing_filename = EXPECTED_FILES[-1]
    (tmp_path / missing_filename).unlink()

    with pytest.raises(FileNotFoundError, match=missing_filename):
        load_all(tmp_path)


def test_reads_utf8_file(tmp_path):
    _write_csvs(tmp_path)
    (tmp_path / EXPECTED_FILES[0]).write_text("city\nSão Paulo\n", encoding="utf-8")

    datasets = load_all(tmp_path)

    assert datasets["orders"]["city"].iloc[0] == "São Paulo"


def test_retries_latin1_when_utf8_decoding_fails(tmp_path):
    _write_csvs(tmp_path)
    (tmp_path / EXPECTED_FILES[0]).write_bytes("city\nSão Paulo\n".encode("latin-1"))

    datasets = load_all(tmp_path)

    assert datasets["orders"]["city"].iloc[0] == "São Paulo"
