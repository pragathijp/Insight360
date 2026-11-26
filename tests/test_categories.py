"""Tests for category and status standardisation utilities."""

import pandas as pd
import pytest

from src.cleaning.categories import (
    apply_translation,
    standardise_text,
    validate_status,
)


def test_standardise_text_trims_and_lowercases_selected_columns():
    frame = pd.DataFrame(
        {"category": ["  ELECTRONICS ", " Kitchen ", None], "other": [1, 2, 3]},
        index=[8, 3, 5],
    )

    result = standardise_text(frame, ["category"])

    assert result["category"].tolist()[:2] == ["electronics", "kitchen"]
    assert pd.isna(result.loc[5, "category"])
    assert result["other"].tolist() == [1, 2, 3]
    assert result.index.tolist() == [8, 3, 5]
    assert len(result) == len(frame)


def test_standardise_text_empty_columns_returns_unchanged_deep_copy():
    frame = pd.DataFrame({"value": [" Keep ", None]}, index=[4, 9])

    result = standardise_text(frame, [])

    pd.testing.assert_frame_equal(result, frame)
    assert result is not frame


def test_standardise_text_preserves_input():
    frame = pd.DataFrame({"category": ["  A ", None]}, index=[6, 2])
    original = frame.copy(deep=True)

    standardise_text(frame, ["category"])

    pd.testing.assert_frame_equal(frame, original)


def test_standardise_text_rejects_non_string_non_null_values():
    with pytest.raises(ValueError, match="non-string"):
        standardise_text(pd.DataFrame({"value": [" text ", 7, None]}), ["value"])


@pytest.mark.parametrize("df", [None, {"value": ["x"]}])
def test_standardise_text_rejects_invalid_dataframe(df):
    with pytest.raises(ValueError, match="pandas DataFrame"):
        standardise_text(df, [])


@pytest.mark.parametrize("cols", [None, "value", ("value",), [""], [1]])
def test_standardise_text_rejects_malformed_columns(cols):
    with pytest.raises(ValueError, match="cols"):
        standardise_text(pd.DataFrame({"value": ["x"]}), cols)


def test_standardise_text_rejects_unknown_and_duplicate_columns():
    frame = pd.DataFrame({"value": ["x"]})

    with pytest.raises(ValueError, match="Unknown text column.*missing"):
        standardise_text(frame, ["missing"])
    with pytest.raises(ValueError, match="duplicate"):
        standardise_text(frame, ["value", "value"])


def test_apply_translation_left_joins_and_flags_untranslated_categories():
    products = pd.DataFrame(
        {"product_id": ["p1", "p2", "p3", "p4"],
         "product_category_name": ["books", "missing", None, "empty-translation"]},
        index=[5, 2, 9, 1],
    )
    translation = pd.DataFrame(
        {
            "product_category_name": ["books", "empty-translation", None],
            "product_category_name_english": ["books english", None, "must not match"],
        }
    )

    result = apply_translation(products, translation)

    assert result.loc[5, "product_category_name_english"] == "books english"
    assert pd.isna(result.loc[2, "product_category_name_english"])
    assert pd.isna(result.loc[1, "product_category_name_english"])
    assert result["is_category_untranslated"].tolist() == [False, True, False, True]
    assert result["product_category_name"].iloc[[0, 1, 3]].tolist() == [
        "books", "missing", "empty-translation"
    ]
    assert pd.isna(result["product_category_name"].iloc[2])
    assert len(result) == len(products)
    assert result.index.tolist() == [5, 2, 9, 1]


def test_apply_translation_preserves_duplicate_product_index_order():
    products = pd.DataFrame(
        {"product_category_name": ["b", "a", "b"]}, index=[4, 4, 1]
    )
    translation = pd.DataFrame(
        {
            "product_category_name": ["a", "b"],
            "product_category_name_english": ["A", "B"],
        }
    )

    result = apply_translation(products, translation)

    assert result.index.tolist() == [4, 4, 1]
    assert result["product_category_name"].tolist() == ["b", "a", "b"]
    assert result["product_category_name_english"].tolist() == ["B", "A", "B"]


def test_apply_translation_rejects_duplicate_non_null_translation_keys():
    products = pd.DataFrame({"product_category_name": ["books"]})
    translation = pd.DataFrame(
        {
            "product_category_name": ["books", "books", None, None],
            "product_category_name_english": ["Books", "Reading", "x", "y"],
        }
    )

    with pytest.raises(ValueError, match="duplicate non-null.*books"):
        apply_translation(products, translation)


def test_apply_translation_preserves_both_input_frames():
    products = pd.DataFrame({"product_category_name": ["books", None]}, index=[8, 2])
    translation = pd.DataFrame(
        {
            "product_category_name": ["books", None],
            "product_category_name_english": ["Books", "not matched"],
        }
    )
    products_original = products.copy(deep=True)
    translation_original = translation.copy(deep=True)

    apply_translation(products, translation)

    pd.testing.assert_frame_equal(products, products_original)
    pd.testing.assert_frame_equal(translation, translation_original)


@pytest.mark.parametrize(
    ("products", "translation", "message"),
    [
        (None, pd.DataFrame(), "products must be a pandas DataFrame"),
        (pd.DataFrame(), None, "translation must be a pandas DataFrame"),
        (pd.DataFrame({"other": []}), pd.DataFrame(), "products is missing"),
        (
            pd.DataFrame({"product_category_name": []}),
            pd.DataFrame({"product_category_name": []}),
            "translation is missing",
        ),
        (
            pd.DataFrame(
                {"product_category_name": [], "product_category_name_english": []}
            ),
            pd.DataFrame(
                {"product_category_name": [], "product_category_name_english": []}
            ),
            "already contains output",
        ),
    ],
)
def test_apply_translation_validates_inputs_and_required_columns(
    products, translation, message
):
    with pytest.raises(ValueError, match=message):
        apply_translation(products, translation)


def test_validate_status_passes_for_supplied_valid_values():
    frame = pd.DataFrame({"order_status": ["created", "delivered"]})

    result = validate_status(frame, {"created", "delivered"})

    assert result == {
        "check": "valid_order_status",
        "table": None,
        "status": "PASS",
        "failed_rows": 0,
        "sample": [],
    }


def test_validate_status_fails_for_unlisted_and_null_values_with_sample():
    frame = pd.DataFrame(
        {"order_status": ["created", "surprise", None, "other", "unknown", "x", "y"]}
    )

    result = validate_status(frame, ["created"])

    assert set(result) == {"check", "table", "status", "failed_rows", "sample"}
    assert result["status"] == "FAIL"
    assert result["table"] is None
    assert result["failed_rows"] == 6
    assert result["sample"][0] == "surprise"
    assert pd.isna(result["sample"][1])
    assert result["sample"][2:] == ["other", "unknown", "x"]


def test_validate_status_does_not_modify_input():
    frame = pd.DataFrame({"order_status": ["created", None]}, index=[7, 3])
    original = frame.copy(deep=True)

    validate_status(frame, ["created"])

    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("valid", ["created", "", [], (), None, 1, ["created", None]])
def test_validate_status_rejects_malformed_valid_values(valid):
    frame = pd.DataFrame({"order_status": ["created"]})

    with pytest.raises(ValueError, match="valid"):
        validate_status(frame, valid)


def test_validate_status_rejects_invalid_dataframe_or_missing_column():
    with pytest.raises(ValueError, match="pandas DataFrame"):
        validate_status(None, ["created"])
    with pytest.raises(ValueError, match="order_status"):
        validate_status(pd.DataFrame({"status": ["created"]}), ["created"])
