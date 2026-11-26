"""Tests for ZIP normalization and geolocation aggregation."""

import logging

import pandas as pd
import pytest

from src.cleaning.zip_codes import aggregate_geolocation, normalise_zip


def test_normalise_zip_pads_short_values_and_preserves_existing_zeroes():
    values = pd.Series(["1046", "00123"], name="postal", index=[4, 9])

    result = normalise_zip(values)

    assert result.tolist() == ["01046", "00123"]
    assert str(result.dtype) == "string"
    assert result.name == "postal"


def test_normalise_zip_strips_whitespace_and_removes_non_digits():
    values = pd.Series([" 10-46 ", " 0 0 9 "])

    assert normalise_zip(values).tolist() == ["01046", "00009"]


def test_normalise_zip_marks_empty_and_over_width_values_missing():
    result = normalise_zip(pd.Series(["", "  -  ", "123456"]))

    assert result.isna().tolist() == [True, True, True]


def test_normalise_zip_logs_new_invalid_values_not_preexisting_nulls(caplog):
    values = pd.Series([None, pd.NA, "bad", "123456", "1046"], dtype=object)
    caplog.set_level(logging.INFO, logger="src.cleaning.zip_codes")

    result = normalise_zip(values)

    assert result.isna().tolist() == [True, True, True, True, False]
    assert "newly_invalid_values=2" in caplog.text


def test_normalise_zip_converts_integral_numbers_and_rejects_other_values():
    values = pd.Series([1046, 1046.0, 1046.5, True, False], dtype=object)

    result = normalise_zip(values)

    assert result.tolist()[:2] == ["01046", "01046"]
    assert result.isna().tolist() == [False, False, True, True, True]


def test_normalise_zip_preserves_series_metadata_order_and_input():
    values = pd.Series(["00102", "1046", None], name="zip", index=[8, 3, 7])
    original = values.copy(deep=True)

    result = normalise_zip(values)

    assert result.name == "zip"
    assert result.index.tolist() == [8, 3, 7]
    assert len(result) == len(values)
    assert result.iloc[:2].tolist() == ["00102", "01046"]
    assert pd.isna(result.iloc[2])
    pd.testing.assert_series_equal(values, original)


@pytest.mark.parametrize("width", [0, -1, 1.5, True, None, "5"])
def test_normalise_zip_rejects_invalid_width(width):
    with pytest.raises(ValueError, match="width must be a positive integer"):
        normalise_zip(pd.Series(["1046"]), width=width)


@pytest.mark.parametrize("value", [None, ["1046"], "1046"])
def test_normalise_zip_rejects_non_series_inputs(value):
    with pytest.raises(ValueError, match="pandas Series"):
        normalise_zip(value)


def _geo_frame(**overrides):
    data = {
        "geolocation_zip_code_prefix": ["1046", "01046", "01047"],
        "geolocation_lat": [10.0, 20.0, 5.0],
        "geolocation_lng": [-10.0, -20.0, -5.0],
        "geolocation_city": ["A", "B", "Only"],
        "geolocation_state": ["SP", "RJ", "MG"],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_aggregate_geolocation_uses_medians_and_one_row_per_normalized_prefix():
    geo = _geo_frame()

    result = aggregate_geolocation(geo)

    assert result["geolocation_zip_code_prefix"].tolist() == ["01046", "01047"]
    assert result["geolocation_zip_code_prefix"].is_unique
    first = result.set_index("geolocation_zip_code_prefix").loc["01046"]
    assert first["geolocation_lat"] == 15.0
    assert first["geolocation_lng"] == -15.0
    assert result.columns.tolist() == [
        "geolocation_zip_code_prefix",
        "geolocation_lat",
        "geolocation_lng",
        "geolocation_city",
        "geolocation_state",
    ]


def test_aggregate_geolocation_resolves_mode_ties_case_sensitively():
    geo = _geo_frame(
        geolocation_zip_code_prefix=["01046", "01046", "01046"],
        geolocation_city=["alpha", "Beta", "alpha"],
        geolocation_state=["SP", "RJ", "SP"],
    )
    # Add a tied city value so lexical ordering, rather than mode frequency,
    # determines the result.
    geo.loc[2, "geolocation_city"] = "Beta"
    geo.loc[2, "geolocation_state"] = "RJ"

    result = aggregate_geolocation(geo).iloc[0]

    assert result["geolocation_city"] == "Beta"
    assert result["geolocation_state"] == "RJ"


def test_aggregate_geolocation_ignores_missing_modes_and_coordinate_values():
    geo = _geo_frame(
        geolocation_zip_code_prefix=["01046", "01046", "01047"],
        geolocation_lat=[None, None, 5.0],
        geolocation_lng=[-10.0, None, -5.0],
        geolocation_city=[None, None, "Only"],
        geolocation_state=["SP", None, "MG"],
    )

    result = aggregate_geolocation(geo).set_index("geolocation_zip_code_prefix")

    assert pd.isna(result.loc["01046", "geolocation_lat"])
    assert result.loc["01046", "geolocation_lng"] == -10.0
    assert pd.isna(result.loc["01046", "geolocation_city"])
    assert result.loc["01046", "geolocation_state"] == "SP"


def test_exact_duplicate_geolocation_rows_contribute_to_aggregates():
    geo = pd.DataFrame(
        {
            "geolocation_zip_code_prefix": ["01046", "01046", "01046"],
            "geolocation_lat": [10.0, 10.0, 100.0],
            "geolocation_lng": [0.0, 0.0, 90.0],
            "geolocation_city": ["A", "A", "B"],
            "geolocation_state": ["SP", "SP", "RJ"],
        }
    )

    result = aggregate_geolocation(geo).iloc[0]

    assert result["geolocation_lat"] == 10.0
    assert result["geolocation_lng"] == 0.0
    assert result["geolocation_city"] == "A"
    assert result["geolocation_state"] == "SP"


def test_aggregate_geolocation_rejects_invalid_zip_prefixes():
    geo = _geo_frame(geolocation_zip_code_prefix=["01046", "123456", "01047"])

    with pytest.raises(ValueError, match="missing or invalid ZIP prefixes.*1 row"):
        aggregate_geolocation(geo)


def test_aggregate_geolocation_rejects_invalid_non_null_coordinates():
    geo = _geo_frame(geolocation_lat=[10.0, "not-a-number", 5.0])

    with pytest.raises(ValueError, match="geolocation_lat.*invalid sample"):
        aggregate_geolocation(geo)


def test_aggregate_geolocation_validates_dataframe_and_required_columns():
    with pytest.raises(ValueError, match="geo must be a pandas DataFrame"):
        aggregate_geolocation(None)
    with pytest.raises(ValueError, match="missing required column.*geolocation_lng"):
        aggregate_geolocation(_geo_frame().drop(columns="geolocation_lng"))


def test_aggregate_geolocation_does_not_mutate_input():
    geo = _geo_frame()
    original = geo.copy(deep=True)

    aggregate_geolocation(geo)

    pd.testing.assert_frame_equal(geo, original)
