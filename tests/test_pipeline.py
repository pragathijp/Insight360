"""Tests for the D2-T8 cleaning pipeline."""

import pandas as pd
import pytest

from src.cleaning import pipeline
from src.cleaning.pipeline import clean_all


def make_datasets():
    return {
        "orders": pd.DataFrame(
            {
                "order_id": ["O1", "O2"],
                "customer_id": ["C1", "C1"],
                "order_status": [" DELIVERED ", " CANCELED "],
                "order_purchase_timestamp": ["2024-01-01", "2024-01-02"],
                "order_approved_at": ["2024-01-01", "2024-01-02"],
                "order_delivered_carrier_date": ["2024-01-02", None],
                "order_delivered_customer_date": [None, None],
                "order_estimated_delivery_date": ["2024-01-04", "2024-01-05"],
            },
            index=[8, 3],
        ),
        "customers": pd.DataFrame(
            {
                "customer_id": ["C1"],
                "customer_unique_id": ["U1"],
                "customer_zip_code_prefix": [" 1046 "],
                "customer_city": [" New City "],
                "customer_state": [" ST "],
            },
            index=[4],
        ),
        "order_items": pd.DataFrame(
            {
                "order_id": ["O1", "O2"],
                "order_item_id": ["1", "1"],
                "product_id": ["P1", "P1"],
                "seller_id": ["S1", "S1"],
                "shipping_limit_date": ["2024-01-02", "2024-01-03"],
                "price": ["10.00", "0"],
                "freight_value": ["1.00", "0"],
            }
        ),
        "payments": pd.DataFrame(
            {
                "order_id": ["O1", "O2"],
                "payment_sequential": ["1", "1"],
                "payment_type": [" Credit Card ", "Voucher"],
                "payment_installments": ["1", "1"],
                "payment_value": ["11.00", "0"],
            }
        ),
        "reviews": pd.DataFrame(
            {
                "review_id": ["R1", "R1"],
                "order_id": ["O1", "O2"],
                "review_score": ["5", "4"],
                "review_comment_title": [None, "ok"],
                "review_comment_message": ["good", None],
                "review_creation_date": ["2024-01-04", "2024-01-04"],
                "review_answer_timestamp": ["2024-01-05", "2024-01-05"],
            }
        ),
        "products": pd.DataFrame(
            {
                "product_id": ["P1", "P2"],
                "product_category_name": [" Electronics ", None],
                "product_name_lenght": ["10", None],
                "product_description_lenght": ["50", None],
                "product_photos_qty": ["2", None],
                "product_weight_g": ["100", None],
                "product_length_cm": ["10", None],
                "product_height_cm": ["5", None],
                "product_width_cm": ["7", None],
            }
        ),
        "sellers": pd.DataFrame(
            {
                "seller_id": ["S1"],
                "seller_zip_code_prefix": ["01046"],
                "seller_city": [" Seller City "],
                "seller_state": [" ST "],
            }
        ),
        "geolocation": pd.DataFrame(
            {
                "geolocation_zip_code_prefix": ["01046", "01046"],
                "geolocation_lat": ["10", "20"],
                "geolocation_lng": ["-10", "-20"],
                "geolocation_city": [" City ", "City"],
                "geolocation_state": [" ST ", "ST"],
            },
            index=[12, 12],
        ),
        "category_translation": pd.DataFrame(
            {
                "product_category_name": ["electronics"],
                "product_category_name_english": ["Electronics"],
            }
        ),
    }


def test_clean_all_preserves_sources_and_applies_documented_operations(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "reports" / "profiling")
    data = make_datasets()
    original = {key: frame.copy(deep=True) for key, frame in data.items()}

    cleaned, log_df = clean_all(data)

    for key, frame in data.items():
        pd.testing.assert_frame_equal(frame, original[key])
        assert len(cleaned[key]) == len(frame)

    orders = cleaned["orders"]
    assert orders["order_status"].tolist() == ["delivered", "canceled"]
    assert orders["is_delivery_date_missing"].tolist()[0] is True
    assert pd.isna(orders["is_delivery_date_missing"].iloc[1])
    assert bool(orders["is_carrier_date_missing"].iloc[0]) is False
    assert pd.isna(orders["is_carrier_date_missing"].iloc[1])
    assert pd.api.types.is_datetime64_any_dtype(orders["order_purchase_timestamp"])

    assert cleaned["customers"]["customer_zip_code_prefix"].tolist() == ["01046"]
    assert cleaned["customers"]["customer_city"].tolist() == ["new city"]
    assert cleaned["payments"]["payment_type"].tolist() == ["credit card", "voucher"]
    assert str(cleaned["order_items"]["price"].dtype) == "float64"
    assert str(cleaned["reviews"]["review_score"].dtype) == "Int64"
    assert len(cleaned["reviews"]) == 2  # repeated candidate review IDs are retained

    assert len(cleaned["geolocation"]) == len(data["geolocation"])
    geo_by_zip = cleaned["geolocation_by_zip"]
    assert geo_by_zip["geolocation_zip_code_prefix"].tolist() == ["01046"]
    assert geo_by_zip.loc[0, "geolocation_lat"] == 15.0
    assert geo_by_zip.loc[0, "geolocation_lng"] == -15.0
    assert "product_category_name_english" in cleaned["products"].columns
    assert cleaned["products"].loc[0, "product_category_name_english"] == "Electronics"
    assert pd.isna(cleaned["products"].loc[1, "product_category_name"])

    assert {"table", "operation", "column", "rows_before", "rows_after", "rows_affected", "details"} == set(log_df.columns)
    summary = log_df.loc[log_df["operation"] == "table_row_count_summary"]
    assert set(summary["table"]) == set(data)
    assert (summary["rows_affected"] == 0).all()
    assert (summary["rows_before"] == summary["rows_after"]).all()
    assert log_df.loc[log_df["operation"].str.startswith("handle_missing"), "rows_affected"].sum() > 0

    log_path = tmp_path / "reports" / "profiling" / "cleaning_log.csv"
    assert log_path.is_file()
    assert pd.read_csv(log_path).columns.tolist() == log_df.columns.tolist()


def test_clean_all_is_repeatable(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "profiling")
    data = make_datasets()

    first_data, first_log = clean_all(data)
    second_data, second_log = clean_all(data)

    assert first_data.keys() == second_data.keys()
    for key in first_data:
        pd.testing.assert_frame_equal(first_data[key], second_data[key])
    pd.testing.assert_frame_equal(first_log, second_log)


def test_type_conversion_log_counts_only_rows_with_changed_values(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "profiling")
    data = make_datasets()
    data["order_items"]["order_item_id"] = pd.Series([1, 1], dtype="int64")
    data["order_items"]["price"] = pd.Series([10.0, 0.0], dtype="float64")
    data["order_items"]["freight_value"] = pd.Series([1.0, 0.0], dtype="float64")

    _, log_df = clean_all(data)

    type_log = log_df.loc[
        (log_df["table"] == "order_items")
        & (log_df["operation"] == "standardise_types")
    ].iloc[0]
    assert type_log["rows_affected"] == 0
    assert "scalar value changed" in type_log["details"]


def test_clean_all_flags_delivered_orders_with_unparseable_delivery_date(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "profiling")
    data = make_datasets()
    data["orders"].loc[8, "order_delivered_customer_date"] = "not-a-date"

    cleaned, log_df = clean_all(data)

    assert pd.isna(cleaned["orders"].loc[8, "order_delivered_customer_date"])
    assert bool(cleaned["orders"].loc[8, "is_delivery_date_missing"])
    parse_log = log_df.loc[
        (log_df["table"] == "orders")
        & (log_df["operation"] == "standardise_dates")
        & (log_df["column"] == "order_delivered_customer_date")
    ].iloc[0]
    assert parse_log["rows_affected"] == 1


def test_clean_all_surfaces_invalid_numeric_values(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "profiling")
    data = make_datasets()
    data["payments"].loc[0, "payment_value"] = "not-numeric"

    with pytest.raises(ValueError, match="payment_value"):
        clean_all(data)


def test_clean_all_rejects_duplicate_category_translation_keys(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "profiling")
    data = make_datasets()
    data["category_translation"] = pd.concat(
        [data["category_translation"], data["category_translation"]],
        ignore_index=True,
    )
    original_product_count = len(data["products"])

    with pytest.raises(ValueError, match="duplicate non-null product_category_name"):
        clean_all(data)

    assert len(data["products"]) == original_product_count


def test_clean_all_logs_invalid_customer_zip_without_dropping_row(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "REPORT_DIR", tmp_path / "profiling")
    data = make_datasets()
    data["customers"].loc[4, "customer_zip_code_prefix"] = "not-a-zip"

    cleaned, log_df = clean_all(data)

    assert len(cleaned["customers"]) == len(data["customers"])
    assert pd.isna(cleaned["customers"].loc[4, "customer_zip_code_prefix"])
    zip_log = log_df.loc[
        (log_df["table"] == "customers")
        & (log_df["operation"] == "normalise_zip")
    ].iloc[0]
    assert zip_log["rows_affected"] == 1


@pytest.mark.parametrize("bad_input", [None, [], {"orders": None}])
def test_clean_all_validates_input_mapping_and_frames(bad_input):
    with pytest.raises(ValueError):
        clean_all(bad_input)


def test_clean_all_rejects_missing_required_dataset():
    data = make_datasets()
    del data["geolocation"]

    with pytest.raises(ValueError, match="missing required dataset key"):
        clean_all(data)
