# Data Quality Findings — Insight360

This document records findings from the existing D1-T9 EDA, D1-T10 relationship validation, and D1-T11 timestamp/distribution analysis. It does not prescribe or perform cleaning. Counts refer to the loaded source extract. Notebook references below use **zero-based cell indices** from the current `notebooks/01_data_exploration.ipynb`; section/question numbers are included where present. D1-T10 relationship/key details are also in `reports/profiling/relationship_report.csv`.

Missing values are reported as Pandas recognizes them after `load_all()` with `dtype=str`. A NULL is not automatically an error: status-dependent lifecycle timestamps and absent review text may be expected, but project rules do not establish that for every field. “Candidate Day-2 rule” means a proposed validation or investigation step, not an approved cleaning decision.

## Findings

### DQ-01 — Order lifecycle timestamp NULLs

- **Dataset / columns:** `orders.order_approved_at`; `orders.order_delivered_carrier_date`; `orders.order_delivered_customer_date`.
- **Observed finding:** 160, 1,783, and 2,965 NULLs, respectively. By status, approval NULLs include 141 canceled, 14 delivered, and 5 created orders; carrier-date NULLs include 609 unavailable, 550 canceled, 314 invoiced, 301 processing, 5 created, 2 approved, and 2 delivered; customer-delivery NULLs include 1,107 shipped, 619 canceled, 609 unavailable, 314 invoiced, 301 processing, 8 delivered, 5 created, and 2 approved.
- **Why it matters:** Lifecycle milestones may not exist for orders that did not reach them. The delivered-status NULLs warrant specific review and can affect delivery metrics.
- **Candidate Day-2 rule:** Validate NULL expectations by `order_status` and milestone; require/flag milestone timestamps only for statuses where the project confirms they should exist. Do not impute timestamps.
- **Disposition:** Retain status-consistent NULLs; flag delivered rows for investigation (14 missing approval, 2 missing carrier, 8 missing customer delivery).
- **Evidence:** D1-T9 missing-value analysis, cells 8 and 18 (Question 2); D1-T11 timestamp parsing and status-specific delivery calculation, cells 74 and 80.

### DQ-02 — Review free-text NULLs

- **Dataset / columns:** `reviews.review_comment_title`, `reviews.review_comment_message`.
- **Observed finding:** 87,656 NULL titles and 58,247 NULL messages.
- **Why it matters:** Comment text is not present on many review records; treating these as failed records or replacing them would alter source meaning.
- **Candidate Day-2 rule:** Confirm whether comment fields are optional in the project/source contract; validate counts and preserve NULLs if optional. Do not substitute text.
- **Disposition:** Retain and investigate expected optionality; no cleaning decision is established.
- **Evidence:** D1-T9 missing-value analysis, cells 8 and 18 (Question 2).

### DQ-03 — Product catalog attribute NULLs

- **Dataset / columns:** `products.product_category_name`, `product_name_lenght`, `product_description_lenght`, `product_photos_qty`, `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm`.
- **Observed finding:** 610 NULLs each in category, name length, description length, and photo quantity; 2 NULLs each in weight and three dimensions. The category translation relationship has 610 NULL product category keys separately reported as child NULLs.
- **Why it matters:** Missing category/attribute values limit category-level reporting and analyses using product characteristics. The available materials do not establish which attributes are mandatory or why they are absent.
- **Candidate Day-2 rule:** Check whether the missing values cluster on the same product records and validate required-field expectations with the source/project owner; report completeness by field before selecting any treatment.
- **Disposition:** Flag for investigation; retain source NULLs until requirements are confirmed.
- **Evidence:** D1-T9 missing-value analysis, cells 8 and 18 (Question 2); D1-T10 relationship validation, cell 69.

### DQ-04 — Duplicate review candidate identifiers

- **Dataset / columns:** `reviews.review_id`.
- **Observed finding:** Candidate key check reports 814 duplicate extra complete-key rows; no NULL review IDs. Review counts by order are 98,126 orders with one review row, 543 with two, and 4 with three.
- **Why it matters:** `review_id` cannot uniquely identify every row in this extract as observed. Multiple review rows per order are also present, so order-level uniqueness must not be assumed.
- **Candidate Day-2 rule:** Inspect the 814 rows grouped by `review_id` and compare their other fields/source provenance; establish the intended grain and identifier rule before deduplicating or changing a key.
- **Disposition:** Investigate and flag; retain all rows. Do not deduplicate automatically.
- **Evidence:** D1-T9 full-row and identifier analyses, cells 10, 12, 21, and 24 (Questions 3–4); D1-T10 candidate-key report, cell 69; review multiplicity metric in cell 69.

### DQ-05 — Exact duplicate geolocation rows

- **Dataset / columns:** `geolocation` (full row across `geolocation_zip_code_prefix`, `geolocation_lat`, `geolocation_lng`, `geolocation_city`, `geolocation_state`).
- **Observed finding:** 261,831 full-row duplicate extra rows in D1-T9.
- **Why it matters:** Repeated identical locations can overweight locations in calculations that aggregate raw geolocation rows. They are not evidence that source records may safely be discarded without a defined use case.
- **Candidate Day-2 rule:** Measure duplicate rows at the intended geolocation grain and compare results with/without exact duplicates for a documented downstream aggregate; retain raw records absent an approved rule.
- **Disposition:** Flag/investigate; retain source data.
- **Evidence:** D1-T9 full-row duplicate analysis, cells 10 and 21 (Question 3); D1-T10 geolocation cardinality, cell 69; D1-T11 geolocation distribution, cell 76.

### DQ-06 — Product categories without English translation

- **Dataset / columns:** `products.product_category_name` → `category_translation.product_category_name`.
- **Observed finding:** 2 distinct non-NULL product category values lack a translation: `pc_gamer` and `portateis_cozinha_e_preparadores_de_alimentos`. They occur on 13 product rows in total (3 and 10). There are also 610 NULL product category rows, counted separately from orphan keys. The relationship report status is FAIL for the two distinct orphan keys.
- **Why it matters:** English-category summaries can omit or mislabel these categories if unmatched values are dropped. NULL category rows are not non-NULL orphan keys.
- **Candidate Day-2 rule:** Compare source category values with the translation table and confirm whether mappings should be added; preserve unmatched and NULL categories explicitly in reports until resolved.
- **Disposition:** Investigate mapping coverage; retain categories and flag unmapped values. No translation is invented.
- **Evidence:** D1-T10 foreign-key validation, cell 69; D1-T11 translated-category analysis, cell 76.

### DQ-07 — ZIP-prefix referential coverage gaps

- **Dataset / columns:** `customers.customer_zip_code_prefix` and `sellers.seller_zip_code_prefix` → distinct `geolocation.geolocation_zip_code_prefix` values.
- **Observed finding:** 157 distinct customer prefixes and 7 distinct seller prefixes have no matching geolocation prefix (relationship status FAIL for both). The report samples the unmatched values. No NULL ZIP keys were reported. Raw geolocation has 1,000,163 rows but only 19,015 distinct non-NULL prefixes; it is a non-unique lookup, not a unique-key parent.
- **Why it matters:** Some customer/seller records cannot be covered by this geolocation source. Joining the raw geolocation table directly can multiply rows because prefixes repeat.
- **Candidate Day-2 rule:** Keep coverage checks against distinct non-NULL geolocation prefixes; review unmatched prefixes and source coverage. For any join, first define and validate a one-row-per-prefix aggregation appropriate to the analysis.
- **Disposition:** Flag unmatched references and investigate coverage; retain records. Never treat raw geolocation prefixes as a unique primary key.
- **Evidence:** D1-T10 foreign-key and geolocation cardinality checks, cell 69; relationship interpretation, cell 71; D1-T9 ZIP multiplicity, cell 63 (Question 17); D1-T11 geolocation distribution, cell 76.

### DQ-08 — Candidate key uniqueness and incomplete relationship coverage

- **Dataset / columns:** Candidate keys: `orders.order_id`; `customers.customer_id`; `order_items.(order_id, order_item_id)`; `payments.(order_id, payment_sequential)`; `reviews.review_id`; `products.product_id`; `sellers.seller_id`; `category_translation.product_category_name`.
- **Observed finding:** All configured candidate keys except `reviews.review_id` are unique with zero incomplete key rows. `reviews.review_id` has 814 duplicate extra complete-key rows. Six non-ZIP foreign-key relationships pass with 0 orphan distinct keys: orders→customers; order_items→orders/products/sellers; payments→orders; reviews→orders. Products→category translations has 2 distinct non-NULL orphan keys (DQ-06). Customer/seller ZIP coverage has the gaps in DQ-07. Null keys were excluded from set comparisons and separately counted; relationship child NULLs were 610 product category rows and 0 for the other reported relationships.
- **Why it matters:** Uniqueness and referential coverage affect safe joins and aggregation. A candidate key is an observed check, not a guarantee of business identity.
- **Candidate Day-2 rule:** Keep these checks in validation; verify review identifier semantics and resolve/accept the category and ZIP coverage gaps with source owners. Preserve separate table grains.
- **Disposition:** Flag the review key and failed relationships; retain the passing relationships as validated for this extract, subject to future refresh checks.
- **Evidence:** D1-T9 identifier analysis, cells 12 and 24 (Question 4); D1-T10 relationship/key validation, cells 69 and 71; machine-readable detail in `reports/profiling/relationship_report.csv`.

### DQ-09 — Orders without item or payment child rows

- **Dataset / columns:** `orders.order_id` compared with `order_items.order_id` and `payments.order_id`.
- **Observed finding:** 775 distinct orders have no order-item rows; 1 distinct order has no payment rows. Relationship validation reports counts based on distinct non-NULL order IDs. The order-status distribution includes non-delivered and canceled statuses, so the counts alone do not establish invalid records.
- **Why it matters:** Analyses that assume every order has child rows may undercount or misstate order-level totals. Joining order items directly to payments can multiply rows because those tables have separate grains.
- **Candidate Day-2 rule:** Review orders without children by `order_status` and source business rules; calculate item and payment measures separately at their own grains.
- **Disposition:** Investigate by status; retain records and do not synthesize child rows.
- **Evidence:** D1-T9 Questions 5 and 11, cells 26–28 and 44–46; D1-T10 cardinality metrics, cell 69 and interpretation cell 71.

### DQ-10 — Timestamp chronology inconsistencies

- **Dataset / columns:** `orders.order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date`.
- **Observed finding:** 166 rows have carrier handoff before purchase; 1,359 have carrier handoff before approval; 23 have customer delivery before carrier handoff. Purchase after approval: 0; customer delivery before purchase: 0; estimated delivery before purchase: 0. The reported comparisons require both timestamps to be valid; no source values were changed.
- **Why it matters:** Chronology anomalies may indicate source timestamp issues or differing event definitions and can affect lead-time analysis.
- **Candidate Day-2 rule:** Recheck these comparisons on parsed non-NULL timestamp pairs, review the flagged order IDs and event definitions, and retain raw timestamps until adjudicated.
- **Disposition:** Flag and investigate the 166, 1,359, and 23 cases; retain current records. No correction is justified yet.
- **Evidence:** D1-T9 Question 16, cells 59–61; D1-T11 timestamp parsing/chronology, cells 72–74 and interpretation cell 80.

### DQ-11 — Timestamp parse failures and delivered-order duration

- **Dataset / columns:** `orders.order_purchase_timestamp`, `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, and `order_estimated_delivery_date`; `order_items.shipping_limit_date`; `reviews.review_creation_date` and `review_answer_timestamp`. Duration uses purchase and customer-delivery timestamps with `order_status`.
- **Observed finding:** Parsing the eight timestamp columns with `errors='coerce'` introduced no additional missing values; all source NULLs remained distinguishable from parsing failures. There are 96,478 delivered orders; 8 are missing one or both duration timestamps; 96,470 valid delivered-order duration observations; 0 negative durations. Duration in days: mean 12.558217, median 10.217477, minimum 0.533414, maximum 209.628611. D1-T9 and corrected D1-T11 use the same delivered-only population and reconcile to these statistics.
- **Why it matters:** Delivery metrics are meaningful only for the stated delivered-order population; including other statuses would change the population.
- **Candidate Day-2 rule:** Keep parsing failures separately measurable and calculate delivery duration only for delivered orders with both timestamps; flag missing timestamps and negative values rather than silently dropping them.
- **Disposition:** Retain the observed valid durations; flag the 8 delivered orders with missing duration timestamps for review. No parse failures or negative durations were observed in this extract.
- **Evidence:** D1-T9 Question 15, cells 56–58; D1-T11 timestamp/delivery analysis and reconciliation, cells 72–74 and 80.

### DQ-12 — IQR-flagged price and freight values

- **Dataset / columns:** `order_items.price`, `order_items.freight_value`.
- **Observed finding:** D1-T9’s 1.5×IQR screen flags 8,427 price values and 12,134 freight values as potential outliers.
- **Why it matters:** Extreme values may affect means, totals, and visual scales; an IQR flag alone does not show that a value is erroneous.
- **Candidate Day-2 rule:** Review flagged rows against item/order context and source units; report robust summaries and sensitivity analyses before considering any correction.
- **Disposition:** Retain and investigate; do not cap, delete, or alter values based only on the IQR screen.
- **Evidence:** D1-T9 Question 14, cells 53–55; D1-T11 reuses the descriptive distributions, cells 72 and 76.

### DQ-13 — Geolocation ZIP-prefix multiplicity

- **Dataset / columns:** `geolocation.geolocation_zip_code_prefix`.
- **Observed finding:** 17,972 of 19,015 distinct prefixes have multiple rows; maximum 1,146 records for one prefix; 981,148 extra rows beyond one per prefix. This is distinct from the 261,831 exact full-row duplicate extras in DQ-05.
- **Why it matters:** Prefix is not a unique geolocation key. A direct join to customer/seller records can expand rows and bias counts or measures.
- **Candidate Day-2 rule:** Before a ZIP-level join, define an appropriate aggregation and assert one row per prefix in the derived lookup; preserve and profile the raw geolocation grain separately.
- **Disposition:** Retain raw source rows; aggregate only in a documented downstream analysis when required.
- **Evidence:** D1-T9 Question 17, cells 62–64; D1-T10 cardinality metrics, cell 69; D1-T11 geolocation distribution, cell 76.

### DQ-14 — Multiple rows per persistent customer identifier

- **Dataset / columns:** `customers.customer_unique_id` (with `customer_id` as customer-row identifier).
- **Observed finding:** 96,096 distinct non-NULL persistent customer IDs across 99,441 customer records; mean 1.0348 records per ID, median 1, maximum 17. D1-T10 reports no NULL values for this grouping key.
- **Why it matters:** `customer_unique_id` is not a unique key for customer rows. Treating it as one can collapse records or distort customer-level joins.
- **Candidate Day-2 rule:** Use `customer_id` for row-level relationships and explicitly group by `customer_unique_id` only for persistent-customer analyses; inspect high multiplicities if needed.
- **Disposition:** Retain as observed multiplicity; it is not by itself a data error.
- **Evidence:** D1-T9 Questions 7–8, cells 32–37; D1-T10 cardinality metrics, cell 69.

## Unresolved questions

- Which order statuses require each lifecycle timestamp, and are the delivered-status missing milestone values source defects?
- Are review title/message fields optional, and what is the intended uniqueness/grain of `review_id` when duplicate identifiers occur?
- Which product attributes are mandatory, and why do 610 products lack category and several attributes while 2 lack physical measurements?
- Should the two product categories absent from the translation table be added, intentionally left untranslated, or handled under another mapping rule?
- What explains the unmatched customer/seller ZIP prefixes and timestamp chronology cases? What geolocation aggregation is appropriate for each future analysis?
- Are orders without item/payment records valid for their statuses, or do they need source-level investigation?
- Are the IQR-flagged price/freight values valid extremes, and what units/conventions apply?

No raw data has been changed, and no cleaning action is authorized by these observations alone.
