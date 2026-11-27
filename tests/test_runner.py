"""Tests for the D2-T8 validation runner."""

import json

import pandas as pd
import pytest

from src.validation import runner
from src.validation.runner import run_all_checks


@pytest.fixture(autouse=True)
def redirect_reports(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "REPORT_DIR", tmp_path / "reports" / "profiling")


def make_datasets():
    return {
        "orders": pd.DataFrame(
            {
                "order_id": ["O1", "O2"],
                "customer_id": ["C1", "C1"],
                "order_status": ["delivered", "canceled"],
                "order_purchase_timestamp": ["2024-01-01", "2024-01-02"],
                "order_approved_at": ["2024-01-01", "2024-01-02"],
                "order_delivered_carrier_date": ["2024-01-02", None],
                "order_delivered_customer_date": ["2024-01-03", None],
                "order_estimated_delivery_date": ["2024-01-04", "2024-01-05"],
            }
        ),
        "customers": pd.DataFrame(
            {
                "customer_id": ["C1"],
                "customer_unique_id": ["U1"],
                "customer_zip_code_prefix": ["01046"],
                "customer_city": ["city"],
                "customer_state": ["ST"],
            }
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
                "payment_type": ["credit_card", "voucher"],
                "payment_installments": ["1", "1"],
                "payment_value": ["11.00", "0"],
            }
        ),
        "reviews": pd.DataFrame(
            {
                "review_id": ["R1"],
                "order_id": ["O1"],
                "review_score": ["5"],
                "review_comment_title": ["good"],
                "review_comment_message": ["good"],
                "review_creation_date": ["2024-01-04"],
                "review_answer_timestamp": ["2024-01-05"],
            }
        ),
        "products": pd.DataFrame(
            {
                "product_id": ["P1"],
                "product_category_name": ["electronics"],
                "product_name_lenght": ["10"],
                "product_description_lenght": ["50"],
                "product_photos_qty": ["2"],
                "product_weight_g": ["100"],
                "product_length_cm": ["10"],
                "product_height_cm": ["5"],
                "product_width_cm": ["7"],
            }
        ),
        "sellers": pd.DataFrame(
            {
                "seller_id": ["S1"],
                "seller_zip_code_prefix": ["01046"],
                "seller_city": ["city"],
                "seller_state": ["ST"],
            }
        ),
        "geolocation": pd.DataFrame(
            {
                "geolocation_zip_code_prefix": ["01046", "01046"],
                "geolocation_lat": ["10", "20"],
                "geolocation_lng": ["-10", "-20"],
                "geolocation_city": ["city", "city"],
                "geolocation_state": ["ST", "ST"],
            }
        ),
        "category_translation": pd.DataFrame(
            {
                "product_category_name": ["electronics"],
                "product_category_name_english": ["electronics"],
            }
        ),
    }


def test_runner_validates_all_nine_dataset_keys_and_frame_types():
    data = make_datasets()
    report = run_all_checks(data)
    assert not report.empty

    with pytest.raises(ValueError, match="missing required dataset key"):
        run_all_checks({key: value for key, value in data.items() if key != "orders"})
    data["orders"] = None
    with pytest.raises(ValueError, match="must be pandas DataFrames"):
        run_all_checks(data)


def test_runner_emits_dataset_context_and_expected_check_mappings(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "REPORT_DIR", tmp_path / "reports" / "profiling")
    report = run_all_checks(make_datasets())

    assert set(report.columns) == {"check", "table", "status", "failed_rows", "sample"}
    assert report["table"].notna().all()
    checks = set(report["check"])
    assert "primary_key_uniqueness" in checks
    assert "foreign_key:orders.customer_id->customers.customer_id" in checks
    assert "zip_prefix_coverage:customers.customer_zip_code_prefix->geolocation" in checks
    assert "review_score_integer_1_to_5" in checks
    assert "full_row_duplicates" in checks
    assert "orders_without_items" in checks
    assert "orders_without_payments" in checks
    assert not any(row.startswith("allowed_values") and row.endswith("order_status") for row in checks)

    csv_path = tmp_path / "reports" / "profiling" / "data_quality_results.csv"
    assert csv_path.is_file()
    saved = pd.read_csv(csv_path)
    assert saved.columns.tolist() == ["check", "table", "status", "failed_rows", "sample"]
    assert json.loads(saved.loc[0, "sample"]) == []


def test_runner_enforces_integer_review_scores():
    data = make_datasets()
    data["reviews"].loc[0, "review_score"] = "2.5"

    report = run_all_checks(data)

    score_range = report.loc[report["check"] == "numeric_range"].iloc[0]
    integer_score = report.loc[
        report["check"] == "review_score_integer_1_to_5"
    ].iloc[0]
    assert score_range["status"] == "PASS"
    assert integer_score["status"] == "FAIL"
    assert integer_score["failed_rows"] == 1


def test_runner_reports_geolocation_exact_duplicates_and_order_child_gaps():
    data = make_datasets()
    data["geolocation"] = pd.concat(
        [data["geolocation"], data["geolocation"].iloc[[0]]], ignore_index=True
    )
    data["order_items"] = data["order_items"].iloc[[0]].copy()
    data["payments"] = data["payments"].iloc[[0]].copy()

    report = run_all_checks(data).set_index("check")

    assert report.loc["full_row_duplicates", "failed_rows"] == 1
    assert report.loc["orders_without_items", "failed_rows"] == 1
    assert report.loc["orders_without_items", "status"] == "REVIEW"
    assert report.loc["orders_without_payments", "status"] == "REVIEW"
    sample = report.loc["orders_without_items", "sample"]
    assert sample[0]["order_id"] == "O2"
    assert "does not establish invalidity" in sample[0]["interpretation"]


def test_runner_checks_zip_coverage_against_distinct_aggregated_prefixes():
    data = make_datasets()
    data["customers"].loc[0, "customer_zip_code_prefix"] = "99999"

    report = run_all_checks(data)
    coverage = report.loc[
        report["check"]
        == "zip_prefix_coverage:customers.customer_zip_code_prefix->geolocation"
    ].iloc[0]

    assert coverage["table"] == "customers"
    assert coverage["status"] == "FAIL"
    assert coverage["failed_rows"] == 1
    assert coverage["sample"][0]["value"] == "99999"


def test_runner_zip_coverage_works_when_geolocation_coordinates_are_invalid():
    data = make_datasets()
    data["geolocation"].loc[0, "geolocation_lat"] = "invalid-coordinate"

    report = run_all_checks(data)

    coverage = report.loc[
        report["check"]
        == "zip_prefix_coverage:customers.customer_zip_code_prefix->geolocation"
    ].iloc[0]
    assert coverage["status"] == "PASS"
    assert coverage["failed_rows"] == 0


def test_runner_does_not_hide_missing_geolocation_columns():
    data = make_datasets()
    data["geolocation"] = data["geolocation"].drop(columns="geolocation_lng")

    with pytest.raises(ValueError, match="geolocation is missing required column.*geolocation_lng"):
        run_all_checks(data)


def test_runner_reports_representative_foreign_key_failures():
    data = make_datasets()
    data["orders"].loc[0, "customer_id"] = "MISSING-CUSTOMER"
    data["order_items"].loc[0, "product_id"] = "MISSING-PRODUCT"
    data["reviews"].loc[0, "order_id"] = "MISSING-ORDER"

    report = run_all_checks(data).set_index("check")

    for check_name in (
        "foreign_key:orders.customer_id->customers.customer_id",
        "foreign_key:order_items.product_id->products.product_id",
        "foreign_key:reviews.order_id->orders.order_id",
    ):
        assert report.loc[check_name, "status"] == "FAIL"
        assert report.loc[check_name, "failed_rows"] == 1


def test_runner_reports_invalid_zip_values():
    data = make_datasets()
    data["customers"].loc[0, "customer_zip_code_prefix"] = "12x"

    report = run_all_checks(data).set_index("check")

    flat_report = report.reset_index()
    customer_zip = flat_report.loc[
        (flat_report["table"] == "customers")
        & (flat_report["check"] == "zip_format")
    ].iloc[0]
    assert customer_zip["status"] == "FAIL"
    assert customer_zip["failed_rows"] == 1
    coverage = report.loc[
        "zip_prefix_coverage:customers.customer_zip_code_prefix->geolocation"
    ]
    assert coverage["status"] == "FAIL"


def test_runner_keeps_unresolved_nulls_visible_as_failures():
    data = make_datasets()
    data["reviews"].loc[0, "review_comment_message"] = None
    data["products"].loc[0, "product_weight_g"] = None

    report = run_all_checks(data)

    review_nulls = report.loc[
        (report["table"] == "reviews") & (report["check"] == "unexpected_nulls")
    ].iloc[0]
    product_nulls = report.loc[
        (report["table"] == "products") & (report["check"] == "unexpected_nulls")
    ].iloc[0]
    assert review_nulls["status"] == "FAIL"
    assert product_nulls["status"] == "FAIL"


def test_runner_rejects_invalid_dataset_mapping():
    with pytest.raises(ValueError, match="dfs must be a dictionary"):
        run_all_checks(None)


def test_runner_writes_non_finite_samples_as_valid_json(monkeypatch):
    data = make_datasets()
    data["payments"]["payment_value"] = data["payments"]["payment_value"].astype(object)
    data["payments"].loc[0, "payment_value"] = float("inf")
    data["reviews"].loc[0, "review_score"] = None

    report = run_all_checks(data)

    row = report.loc[report["table"] == "payments"].query(
        "check == 'monetary_values'"
    ).iloc[0]
    assert row["status"] == "FAIL"
    saved = pd.read_csv(runner.REPORT_DIR / "data_quality_results.csv")
    saved_row = saved.loc[saved["table"] == "payments"].query(
        "check == 'monetary_values'"
    ).iloc[0]
    assert json.loads(saved_row["sample"])[0]["issues"][0]["value"] == "inf"
    saved_scores = pd.read_csv(runner.REPORT_DIR / "data_quality_results.csv")
    score_row = saved_scores.loc[
        (saved_scores["table"] == "reviews")
        & (saved_scores["check"] == "review_score_integer_1_to_5")
    ].iloc[0]
    assert json.loads(score_row["sample"])[0]["value"] is None
