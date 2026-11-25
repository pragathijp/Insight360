# Data Dictionary — Insight360

This dictionary reflects the nine source CSV schemas and values loaded by `src/ingestion/loader.py`. The loader passes `dtype=str`; the observed Pandas dtype for every column in the current loaded data is `str`. These are string values as loaded, not inferred semantic types. “Observed NULLs” is the count in the current source extract. Where the source and project materials do not define an expected NULL rule, that is stated explicitly rather than inferred. Source column spellings are preserved.

## `orders` — `olist_orders_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `order_id` | Order record identifier. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `customer_id` | Identifier of the customer record associated with the order. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `order_status` | Recorded order status. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `order_purchase_timestamp` | Recorded time the order was placed. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `order_approved_at` | Recorded time the order was approved. | `str` (loaded using `dtype=str`) | 160 | Approval may not have occurred or been recorded for every status; status-specific expectation is not established. Review the 14 delivered rows with NULL separately. |
| `order_delivered_carrier_date` | Recorded time the order was handed to the carrier. | `str` (loaded using `dtype=str`) | 1,783 | May be status/lifecycle dependent; do not treat all NULLs as errors. Review the 2 delivered rows with NULL separately. |
| `order_delivered_customer_date` | Recorded time the order was delivered to the customer. | `str` (loaded using `dtype=str`) | 2,965 | May be status/lifecycle dependent; do not treat all NULLs as errors. Review the 8 delivered rows with NULL separately. |
| `order_estimated_delivery_date` | Recorded estimated delivery date. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## `customers` — `olist_customers_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `customer_id` | Identifier for this customer record. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `customer_unique_id` | Persistent customer identifier used to group customer records. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `customer_zip_code_prefix` | Customer ZIP code prefix. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `customer_city` | Customer city value. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `customer_state` | Customer state value. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## `order_items` — `olist_order_items_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `order_id` | Identifier of the associated order. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `order_item_id` | Item sequence identifier within the order. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `product_id` | Identifier of the product on the item. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `seller_id` | Identifier of the seller for the item. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `shipping_limit_date` | Recorded shipping limit date/time. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `price` | Recorded item price value; currency/unit is not established here. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `freight_value` | Recorded freight value; currency/unit is not established here. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## `payments` — `olist_order_payments_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `order_id` | Identifier of the associated order. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `payment_sequential` | Payment sequence number within the order. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `payment_type` | Recorded payment method/type label. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `payment_installments` | Recorded installment count. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `payment_value` | Recorded payment value; currency/unit is not established here. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## `reviews` — `olist_order_reviews_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `review_id` | Review record identifier. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `order_id` | Identifier of the associated order. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `review_score` | Recorded review score. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `review_comment_title` | Review comment title text. | `str` (loaded using `dtype=str`) | 87,656 | No NULL rule is specified; possible absent free text needs confirmation. Retain missing values pending validation. |
| `review_comment_message` | Review comment message text. | `str` (loaded using `dtype=str`) | 58,247 | No NULL rule is specified; possible absent free text needs confirmation. Retain missing values pending validation. |
| `review_creation_date` | Recorded review creation date/time. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `review_answer_timestamp` | Recorded review answer time. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## `products` — `olist_products_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `product_id` | Product record identifier. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `product_category_name` | Source category name associated with the product. | `str` (loaded using `dtype=str`) | 610 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |
| `product_name_lenght` | Source product-name length value (source spelling retained). | `str` (loaded using `dtype=str`) | 610 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |
| `product_description_lenght` | Source product-description length value (source spelling retained). | `str` (loaded using `dtype=str`) | 610 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |
| `product_photos_qty` | Recorded quantity of product photos. | `str` (loaded using `dtype=str`) | 610 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |
| `product_weight_g` | Recorded product weight in grams, as indicated by the column name. | `str` (loaded using `dtype=str`) | 2 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |
| `product_length_cm` | Recorded product length in centimeters, as indicated by the column name. | `str` (loaded using `dtype=str`) | 2 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |
| `product_height_cm` | Recorded product height in centimeters, as indicated by the column name. | `str` (loaded using `dtype=str`) | 2 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |
| `product_width_cm` | Recorded product width in centimeters, as indicated by the column name. | `str` (loaded using `dtype=str`) | 2 | No NULL rule is specified; investigate catalog completeness before deciding whether a value is required. |

## `sellers` — `olist_sellers_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `seller_id` | Seller record identifier. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `seller_zip_code_prefix` | Seller ZIP code prefix. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `seller_city` | Seller city value. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `seller_state` | Seller state value. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## `geolocation` — `olist_geolocation_dataset.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `geolocation_zip_code_prefix` | ZIP code prefix associated with this geolocation record; prefixes repeat. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `geolocation_lat` | Latitude value recorded for the prefix/location. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `geolocation_lng` | Longitude value recorded for the prefix/location. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `geolocation_city` | City value recorded for the prefix/location. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `geolocation_state` | State value recorded for the prefix/location. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## `category_translation` — `product_category_name_translation.csv`

| Column | Meaning | Observed Pandas dtype | Observed NULLs | NULL behavior / notes |
| --- | --- | --- | ---: | --- |
| `product_category_name` | Source-language product category name. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |
| `product_category_name_english` | English translation of the source product category name. | `str` (loaded using `dtype=str`) | 0 | No source NULL rule is documented; observed zero NULLs in this extract. |

## Identifiers and relationships

- Candidate keys from the existing project documentation and D1-T10 checks: `orders.order_id`; `customers.customer_id`; `order_items.(order_id, order_item_id)`; `payments.(order_id, payment_sequential)`; `reviews.review_id`; `products.product_id`; `sellers.seller_id`; and `category_translation.product_category_name`. Their observed uniqueness is reported in the notebook’s D1-T10 section; `reviews.review_id` is not unique in this extract.
- `customer_unique_id` groups customer records for persistent-customer analysis; it is not the customer row identifier.
- `geolocation` has no asserted unique key. ZIP prefixes repeat. Geolocation must be aggregated to one row per ZIP code prefix before joining to customer or seller records, because multiple geolocation records can exist for the same prefix and otherwise multiply rows.

## Relationship overview

- Orders to customers through `orders.customer_id` → `customers.customer_id`.
- Order items to orders, products, and sellers through their respective `order_id`, `product_id`, and `seller_id` columns.
- Payments and reviews to orders through `order_id`; their table grains remain separate from order items.
- Products to category translations through `product_category_name`.
- Customers and sellers to geolocation through ZIP code prefixes. Geolocation prefixes are non-unique and require aggregation before joining.

Column meanings above are intentionally limited to what is supported by column names, source headers, and existing project analysis. Where units, business definitions, or NULL expectations are not established, they remain unspecified.
