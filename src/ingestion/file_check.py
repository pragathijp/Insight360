"""Utilities for checking the presence of raw data files."""

from pathlib import Path
from typing import Iterable


def check_raw_files(
    raw_dir: str | Path,
    expected_files: Iterable[str],
    strict: bool = True,
) -> dict[str, list[str]]:
    """Report which expected files are present in ``raw_dir``.

    Args:
        raw_dir: Directory to inspect.
        expected_files: Filenames that should be present in the directory.
        strict: Raise ``FileNotFoundError`` when any expected files are missing.

    Returns:
        A dictionary with ``present`` and ``missing`` filename lists.
    """
    directory = Path(raw_dir)
    present: list[str] = []
    missing: list[str] = []

    for filename in expected_files:
        if (directory / filename).is_file():
            present.append(filename)
        else:
            missing.append(filename)

    result = {"present": present, "missing": missing}
    if strict and missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing expected files in {directory}: {missing_list}")

    return result
