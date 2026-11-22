# Initial Data Dictionary — Insight360

This draft is based on the actual CSV headers in `data/raw/`. In the loaded DataFrames, Pandas reports dtype `str` for every column; `src/ingestion/loader.py` passes `dtype=str`, so CSV values are loaded as strings. This records the observed Pandas dtype and loading behavior only; it does not infer semantic types such as numeric or date. Column meanings are kept at dataset level where field-level semantics are not established. Candidate keys are unverified unless noted otherwise.

## `orders` — `olist_orders_dataset.csv`

Order records and lifecycle timestamps/status.

| Column | Observed Pandas dtype |
| --- | --- |
| `order_id` | `str` |
| `customer_id` | `str` |
| `order_status` | `str` |
| `order_purchase_timestamp` | `str` |
| `order_approved_at` | `str` |
| `order_delivered_carrier_date` | `str` |
| `order_delivered_customer_date` | `str` |
| `order_estimated_delivery_date` | `str` |

**Identifiers and relationships:** Candidate key: order_id (not independently verified for uniqueness here). customer_id relates to customers.

## `customers` — `olist_customers_dataset.csv`

Customer identifiers and location attributes.

| Column | Observed Pandas dtype |
| --- | --- |
| `customer_id` | `str` |
| `customer_unique_id` | `str` |
| `customer_zip_code_prefix` | `str` |
| `customer_city` | `str` |
| `customer_state` | `str` |

**Identifiers and relationships:** Candidate row identifier: customer_id; customer_unique_id identifies a persistent customer across customer records.

## `order_items` — `olist_order_items_dataset.csv`

Line items associated with orders, products, and sellers.

| Column | Observed Pandas dtype |
| --- | --- |
| `order_id` | `str` |
| `order_item_id` | `str` |
| `product_id` | `str` |
| `seller_id` | `str` |
| `shipping_limit_date` | `str` |
| `price` | `str` |
| `freight_value` | `str` |

**Identifiers and relationships:** Candidate composite key: (order_id, order_item_id); links to orders, products, and sellers.

## `payments` — `olist_order_payments_dataset.csv`

Payment records associated with orders.

| Column | Observed Pandas dtype |
| --- | --- |
| `order_id` | `str` |
| `payment_sequential` | `str` |
| `payment_type` | `str` |
| `payment_installments` | `str` |
| `payment_value` | `str` |

**Identifiers and relationships:** Candidate composite key: (order_id, payment_sequential); links to orders.

## `reviews` — `olist_order_reviews_dataset.csv`

Review records and review-related fields associated with orders.

| Column | Observed Pandas dtype |
| --- | --- |
| `review_id` | `str` |
| `order_id` | `str` |
| `review_score` | `str` |
| `review_comment_title` | `str` |
| `review_comment_message` | `str` |
| `review_creation_date` | `str` |
| `review_answer_timestamp` | `str` |

**Identifiers and relationships:** Candidate identifier: review_id (uniqueness not independently verified); order_id relates to orders. Do not assume one review per order.

## `products` — `olist_products_dataset.csv`

Product attributes and category names.

| Column | Observed Pandas dtype |
| --- | --- |
| `product_id` | `str` |
| `product_category_name` | `str` |
| `product_name_lenght` | `str` |
| `product_description_lenght` | `str` |
| `product_photos_qty` | `str` |
| `product_weight_g` | `str` |
| `product_length_cm` | `str` |
| `product_height_cm` | `str` |
| `product_width_cm` | `str` |

**Identifiers and relationships:** Candidate key: product_id; product_category_name relates to category_translation.

## `sellers` — `olist_sellers_dataset.csv`

Seller identifiers and location attributes.

| Column | Observed Pandas dtype |
| --- | --- |
| `seller_id` | `str` |
| `seller_zip_code_prefix` | `str` |
| `seller_city` | `str` |
| `seller_state` | `str` |

**Identifiers and relationships:** Candidate key: seller_id.

## `geolocation` — `olist_geolocation_dataset.csv`

Geolocation records keyed by ZIP code prefix and location values.

| Column | Observed Pandas dtype |
| --- | --- |
| `geolocation_zip_code_prefix` | `str` |
| `geolocation_lat` | `str` |
| `geolocation_lng` | `str` |
| `geolocation_city` | `str` |
| `geolocation_state` | `str` |

**Identifiers and relationships:** No unique key asserted. geolocation_zip_code_prefix is repeated and relates to customer/seller ZIP prefixes as a non-unique lookup.

## `category_translation` — `product_category_name_translation.csv`

Portuguese product category names and English translations.

| Column | Observed Pandas dtype |
| --- | --- |
| `product_category_name` | `str` |
| `product_category_name_english` | `str` |

**Identifiers and relationships:** Candidate key: product_category_name (uniqueness not independently verified).

## Relationship overview

- Orders to customers through `customer_id`.
- Order items to orders (`order_id`), products (`product_id`), and sellers (`seller_id`).
- Payments to orders through `order_id`.
- Reviews to orders through `order_id`; review multiplicity must be checked rather than assumed.
- Products to category translations through `product_category_name`.
- Customers and sellers to geolocation through their ZIP code prefix columns; geolocation prefixes are non-unique.

Geolocation must be aggregated to one row per ZIP code prefix before joining to customer or seller records, because multiple geolocation records can exist for the same prefix and otherwise multiply rows.

The approved PRD relationship section was not available in the repository during this draft, so relationship notes follow the supplied D1-T9 request and observed column names. Candidate key uniqueness and foreign-key coverage remain to be verified in subsequent validation work.
