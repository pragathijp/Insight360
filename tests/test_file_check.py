"""Tests for raw-file presence checks."""

import pytest

from src.ingestion.file_check import check_raw_files


def test_all_expected_files_present(tmp_path):
    expected_files = ["orders.csv", "customers.csv"]
    for filename in expected_files:
        (tmp_path / filename).touch()

    result = check_raw_files(tmp_path, expected_files)

    assert result == {"present": expected_files, "missing": []}


def test_missing_files_raise_in_strict_mode(tmp_path):
    expected_files = ["orders.csv", "customers.csv", "items.csv"]
    (tmp_path / "orders.csv").touch()

    with pytest.raises(FileNotFoundError) as exc_info:
        check_raw_files(tmp_path, expected_files, strict=True)

    assert "customers.csv" in str(exc_info.value)
    assert "items.csv" in str(exc_info.value)


def test_missing_files_are_returned_in_non_strict_mode(tmp_path):
    expected_files = ["orders.csv", "customers.csv"]
    (tmp_path / "orders.csv").touch()

    result = check_raw_files(tmp_path, expected_files, strict=False)

    assert result == {"present": ["orders.csv"], "missing": ["customers.csv"]}


def test_empty_expected_files_list(tmp_path):
    assert check_raw_files(tmp_path, []) == {"present": [], "missing": []}
