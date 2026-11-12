# Dataset inspection and exploratory analysis

Project: Craft Category Association Discovery Through Clustered Transaction Analysis

INT396 — Aftab Khan and Tej Pratap Singh. Run: `phase2_20261111_224047` (Asia/Calcutta).

## Scope and method

Both worksheets were loaded using Pandas/openpyxl and concatenated in worksheet order. All 1,067,371 invoice-line records remain in the in-memory analysis. No cleaned dataset was exported. Empty cells are parsed as missing (`keep_default_na=False, na_values=['']`), preserving literal text tokens such as `NA`. Numeric/date conversions and text-format checks use separate diagnostic Series; original columns are not overwritten. No imputation, deduplication, category mapping, clustering or association-rule mining was performed.

An invoice line is not a whole basket. Unique counts exclude missing identifiers and use loaded values without case/whitespace normalization. StockCode counts represent distinct recorded codes, including possible charges and adjustments, not a verified count of saleable products. Customer ID is an identifier, even if inferred as numeric. Price units are not verified by workbook column names alone, so plots use source price units.

Source: `C:\Users\aftab\Desktop\SuperwiseProject\data\raw\online_retail_II.xlsx`. SHA-256 before and after: `BCBE73B35F5B7BABF197FB0CB983A11F5D9FF929078D4AA53D171B1F2DF2E980`. Hashes match the Phase 1 manifest. The source was opened only for reading.

## Worksheet dimensions

| scope | rows | columns |
| --- | --- | --- |
| Year 2009-2010 | 525,461 | 8 |
| Year 2010-2011 | 541,910 | 8 |
| Combined | 1,067,371 | 8 |

## Columns and data types

| scope | column | pandas_dtype | observed_nonmissing_python_types |
| --- | --- | --- | --- |
| Year 2009-2010 | Invoice | object | int, str |
| Year 2009-2010 | StockCode | object | int, str |
| Year 2009-2010 | Description | object | int, str |
| Year 2009-2010 | Quantity | int64 | int |
| Year 2009-2010 | InvoiceDate | datetime64[us] | Timestamp |
| Year 2009-2010 | Price | float64 | float |
| Year 2009-2010 | Customer ID | float64 | float |
| Year 2009-2010 | Country | str | str |
| Year 2010-2011 | Invoice | object | int, str |
| Year 2010-2011 | StockCode | object | int, str |
| Year 2010-2011 | Description | object | int, str |
| Year 2010-2011 | Quantity | int64 | int |
| Year 2010-2011 | InvoiceDate | datetime64[us] | Timestamp |
| Year 2010-2011 | Price | float64 | float |
| Year 2010-2011 | Customer ID | float64 | float |
| Year 2010-2011 | Country | str | str |
| Combined | Invoice | object | int, str |
| Combined | StockCode | object | int, str |
| Combined | Description | object | int, str |
| Combined | Quantity | int64 | int |
| Combined | InvoiceDate | datetime64[us] | Timestamp |
| Combined | Price | float64 | float |
| Combined | Customer ID | float64 | float |
| Combined | Country | str | str |

Mixed types in identifier columns require deliberate handling in preprocessing. Do not use numerical Customer ID magnitude as a feature.

## Missing values

| scope | column | missing | percentage |
| --- | --- | --- | --- |
| Year 2009-2010 | Invoice | 0 | 0 |
| Year 2009-2010 | StockCode | 0 | 0 |
| Year 2009-2010 | Description | 2,928 | 0.5572 |
| Year 2009-2010 | Quantity | 0 | 0 |
| Year 2009-2010 | InvoiceDate | 0 | 0 |
| Year 2009-2010 | Price | 0 | 0 |
| Year 2009-2010 | Customer ID | 107,927 | 20.5395 |
| Year 2009-2010 | Country | 0 | 0 |
| Year 2010-2011 | Invoice | 0 | 0 |
| Year 2010-2011 | StockCode | 0 | 0 |
| Year 2010-2011 | Description | 1,454 | 0.2683 |
| Year 2010-2011 | Quantity | 0 | 0 |
| Year 2010-2011 | InvoiceDate | 0 | 0 |
| Year 2010-2011 | Price | 0 | 0 |
| Year 2010-2011 | Customer ID | 135,080 | 24.9266 |
| Year 2010-2011 | Country | 0 | 0 |
| Combined | Invoice | 0 | 0 |
| Combined | StockCode | 0 | 0 |
| Combined | Description | 4,382 | 0.4105 |
| Combined | Quantity | 0 | 0 |
| Combined | InvoiceDate | 0 | 0 |
| Combined | Price | 0 | 0 |
| Combined | Customer ID | 243,007 | 22.7669 |
| Combined | Country | 0 | 0 |

Percentages use the row count of the corresponding scope. Blank strings are missing at import; whitespace-only strings are checked separately. No missing values were estimated or filled.

## Unique identifiers

| scope | invoices | products | customers | countries | descriptions |
| --- | --- | --- | --- | --- | --- |
| Year 2009-2010 | 28,816 | 4,632 | 4,383 | 40 | 4,681 |
| Year 2010-2011 | 25,900 | 4,070 | 4,372 | 38 | 4,223 |
| Combined | 53,628 | 5,305 | 5,942 | 43 | 5,698 |

There are 1,088 invoice IDs shared between worksheets. Counts across sheets are therefore not assumed additive. 0 invoice IDs have multiple nonmissing customers, 0 have multiple countries, and 83 have multiple timestamps. These are review flags, not proof of corrupted invoices. Investigate invoice identity, worksheet overlap and timestamp semantics before defining baskets.

## Exact duplicates and worksheet overlap

| scope | repeat_occurrences_after_first | all_rows_in_duplicate_groups | distinct_duplicate_groups |
| --- | --- | --- | --- |
| Year 2009-2010 | 6,865 | 13,283 | 6,418 |
| Year 2010-2011 | 5,268 | 10,147 | 4,879 |
| Combined | 34,335 | 67,242 | 32,907 |

`repeat_occurrences_after_first` counts copies beyond one retained occurrence per exact group. `all_rows_in_duplicate_groups` includes the first occurrence. Equality uses all eight original columns and excludes provenance. There are 22,202 distinct exact groups appearing in both worksheets, involving 45,046 rows. Combining sheets adds 22,202 repeat occurrences beyond the sum of within-sheet repeat counts. This overlap can affect volume and future support estimates. Do not deduplicate automatically: validate repeated line entries and define an auditable policy first. Row locations are in `duplicate_row_locations.csv` (Excel row numbers include the header).

The cross-sheet duplicate records span 2010-12-01 08:26:00 to 2010-12-09 20:01:00. This is observed repeated coverage, not merely a hypothetical overlap. Resolve its treatment before interpreting December 2010 volume or later basket frequencies.

## Cancellations, quantities and prices

Cancellation flag: Invoice starts with C, case-insensitive, without trimming or editing source values. This is a convention-based flag; cancellation-to-original-sale links have not been established.

| scope | cancelled_rows | cancelled_unique_invoices |
| --- | --- | --- |
| Year 2009-2010 | 10,206 | 4,592 |
| Year 2010-2011 | 9,288 | 3,836 |
| Combined | 19,494 | 8,292 |

| scope | column | sign | rows | percentage |
| --- | --- | --- | --- | --- |
| Year 2009-2010 | Quantity | negative | 12,326 | 2.3457 |
| Year 2009-2010 | Quantity | zero | 0 | 0 |
| Year 2009-2010 | Quantity | positive | 513,135 | 97.6543 |
| Year 2009-2010 | Quantity | missing_or_invalid | 0 | 0 |
| Year 2009-2010 | Price | negative | 3 | 0.0006 |
| Year 2009-2010 | Price | zero | 3,687 | 0.7017 |
| Year 2009-2010 | Price | positive | 521,771 | 99.2978 |
| Year 2009-2010 | Price | missing_or_invalid | 0 | 0 |
| Year 2010-2011 | Quantity | negative | 10,624 | 1.9605 |
| Year 2010-2011 | Quantity | zero | 0 | 0 |
| Year 2010-2011 | Quantity | positive | 531,286 | 98.0395 |
| Year 2010-2011 | Quantity | missing_or_invalid | 0 | 0 |
| Year 2010-2011 | Price | negative | 2 | 0.0004 |
| Year 2010-2011 | Price | zero | 2,515 | 0.4641 |
| Year 2010-2011 | Price | positive | 539,393 | 99.5355 |
| Year 2010-2011 | Price | missing_or_invalid | 0 | 0 |
| Combined | Quantity | negative | 22,950 | 2.1501 |
| Combined | Quantity | zero | 0 | 0 |
| Combined | Quantity | positive | 1,044,421 | 97.8499 |
| Combined | Quantity | missing_or_invalid | 0 | 0 |
| Combined | Price | negative | 5 | 0.0005 |
| Combined | Price | zero | 6,202 | 0.5811 |
| Combined | Price | positive | 1,061,164 | 99.4185 |
| Combined | Price | missing_or_invalid | 0 | 0 |

3,457 negative-quantity rows lack the C prefix. 1 C-prefix rows have nonnegative quantities. See both sign cross-tabulations for overlaps. Negative quantities and prices must not be converted to absolute values automatically. Zero prices need context before deciding eligibility for price-based or presence-only analyses.

Negative-price descriptions observed in the source:

| StockCode | Description | rows |
| --- | --- | --- |
| B | Adjust bad debt | 5 |

These labels support reviewing accounting entries separately from normal product purchases. They do not establish the cause of every unusual price. `cancelled_invoice_ids.csv` identifies all C-prefix invoice IDs, and `unusual_record_details.csv` gives provenance for negative prices, nontext descriptions, atypical invoices and C-prefix rows with nonnegative quantities. A row can appear under multiple review reasons.

## Dates and coverage

| scope | earliest | latest | missing_dates | invalid_nonmissing_dates | rows_not_in_chronological_order |
| --- | --- | --- | --- | --- | --- |
| Year 2009-2010 | 2009-12-01 07:45:00 | 2010-12-09 20:01:00 | 0 | 0 | 0 |
| Year 2010-2011 | 2010-12-01 08:26:00 | 2011-12-09 12:50:00 | 0 | 0 | 0 |
| Combined | 2009-12-01 07:45:00 | 2011-12-09 12:50:00 | 0 | 0 | 1 |

Valid dates span 2009-12-01 07:45:00 to 2011-12-09 12:50:00. The workbook does not specify a timezone; timestamps remain timezone-naive. Chronological-order flags count backward steps in source row order and do not establish invalid dates. The final month may be incomplete; monthly counts are observed totals, not annualized estimates. Overlapping worksheet periods and duplicate rows remain included in all activity charts.

The combined backward date step arises at the concatenation boundary: the second sheet starts before the first sheet ends. December 2011 coverage ends on December 9, so its smaller count should not be interpreted as a full-month decline.

## Descriptive statistics and potential outliers

| column | count | mean | std | min | 1% | 5% | 25% | 50% | 75% | 95% | 99% | 99.9% | max |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Quantity | 1,067,371 | 9.9389 | 172.7058 | -80,995 | -3 | 1 | 1 | 3 | 10 | 30 | 100 | 500 | 80,995 |
| Price | 1,067,371 | 4.6494 | 123.5531 | -53,594.36 | 0.21 | 0.42 | 1.25 | 2.1 | 4.15 | 9.95 | 18 | 217.016 | 38,970 |

Standard deviation is the sample standard deviation (Pandas default, ddof=1). Quantiles use Pandas' default linear interpolation. Only Quantity and Price are treated as numerical measures; all-column and per-sheet descriptive tables are also supplied.

| column | q1 | q3 | iqr | lower_fence | upper_fence | below_fence | above_fence | flagged_rows | percentage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Quantity | 1 | 10 | 9 | -12.5 | 23.5 | 4,459 | 112,030 | 116,489 | 10.9136 |
| Price | 1.25 | 4.15 | 2.9 | -3.1 | 8.5 | 5 | 68,100 | 68,105 | 6.3806 |

Potential outliers use lower/upper fences Q1 − 1.5×IQR and Q3 + 1.5×IQR over all finite values, including returns/adjustments. These are exploratory flags, not evidence of errors. Compare legitimate bulk purchases, special charges and anomalous entries before considering exclusions, robust scaling or transformations. No clipping or record removal was applied. `extreme_value_examples.csv` provides the ten lowest and highest rows for each measure with worksheet and Excel-row provenance.

## Product-description frequency and unusual codes

| Description | line_count | percentage_of_all_rows |
| --- | --- | --- |
| WHITE HANGING HEART T-LIGHT HOLDER | 5,918 | 0.5544 |
| REGENCY CAKESTAND 3 TIER | 4,412 | 0.4134 |
| JUMBO BAG RED RETROSPOT | 3,469 | 0.325 |
| ASSORTED COLOUR BIRD ORNAMENT | 2,958 | 0.2771 |
| PARTY BUNTING | 2,765 | 0.259 |
| STRAWBERRY CERAMIC TRINKET BOX | 2,613 | 0.2448 |
| LUNCH BAG  BLACK SKULL. | 2,529 | 0.2369 |
| JUMBO STORAGE BAG SUKI | 2,434 | 0.228 |
| HEART OF WICKER SMALL | 2,319 | 0.2173 |
| JUMBO SHOPPER VINTAGE RED PAISLEY | 2,297 | 0.2152 |
| 60 TEATIME FAIRY CAKE CASES | 2,271 | 0.2128 |
| PAPER CHAIN KIT 50'S CHRISTMAS  | 2,215 | 0.2075 |
| LUNCH BAG SPACEBOY DESIGN  | 2,206 | 0.2067 |
| REX CASH+CARRY JUMBO SHOPPER | 2,199 | 0.206 |
| HOME BUILDING BLOCK WORD | 2,192 | 0.2054 |
| WOODEN FRAME ANTIQUE WHITE  | 2,189 | 0.2051 |
| LUNCH BAG CARS BLUE | 2,184 | 0.2046 |
| NATURAL SLATE HEART CHALKBOARD  | 2,151 | 0.2015 |
| BAKING SET 9 PIECE RETROSPOT  | 2,150 | 0.2014 |
| POSTAGE | 2,115 | 0.1982 |

Frequencies count lines, not units sold or distinct purchasing baskets, and include cancelled and duplicate entries. Missing descriptions are excluded only from this ranking and remain in the dataset. 1,232 stock codes have multiple exact nonmissing descriptions. Formatting changes, genuine renaming and operational notes are possibilities that require investigation; this is not category mapping.

`atypical_stock_codes.csv` lists codes outside the heuristic five digits plus optional letters pattern. Review these individually; the pattern is not an authoritative validity rule. `invoice_prefixes.csv` lists observed prefixes. `stock_description_variation.csv` supports later verified description work.

## Country distribution

| Country | line_count | unique_invoices | unique_customers |
| --- | --- | --- | --- |
| United Kingdom | 981,330 | 49,108 | 5,410 |
| EIRE | 17,866 | 806 | 5 |
| Germany | 17,624 | 1,095 | 107 |
| France | 14,330 | 746 | 95 |
| Netherlands | 5,140 | 250 | 23 |
| Spain | 3,811 | 188 | 41 |
| Switzerland | 3,189 | 123 | 22 |
| Belgium | 3,123 | 183 | 29 |
| Portugal | 2,620 | 124 | 24 |
| Australia | 1,913 | 117 | 15 |

Country line counts include every row; unique invoice counts by country need not sum to global unique counts if invoice IDs span countries. Geographical concentration should be considered when interpreting generalizability. No geographic filter was applied.

## Data-quality issues and proposed treatments

| issue | rows | percentage | interpretation | possible_treatment_after_approval |
| --- | --- | --- | --- | --- |
| Missing Customer ID | 243,007 | 22.7669 | Customer identity is unavailable; invoice baskets may still be usable. | Do not invent IDs. Retain for invoice-level analysis when invoice/product data suffice; exclude only from customer-level analyses with documented coverage. |
| Missing Description | 4,382 | 0.4105 | Descriptions cannot support later category validation. | Review StockCode description history and provenance; leave unresolved items unknown rather than guessing a category. |
| Exact repeat occurrences after first | 34,335 | 3.2168 | Identical eight-column records can inflate frequencies but may represent repeated legitimate line entries. | Investigate duplication and worksheet overlap; approve and document any deduplication policy before applying it. |
| Cancellation-prefix invoice rows | 19,494 | 1.8264 | C-prefix is an operational cancellation flag; no linkage to original sales is inferred. | Separate cancellations/returns from purchase baskets; consider a separate returns analysis and document any matching logic. |
| Negative quantity | 22,950 | 2.1501 | Negative entries may be returns, cancellations or adjustments. | Review cancellation status and descriptions; define purchase eligibility before excluding or netting quantities. |
| Negative quantity without C prefix | 3,457 | 0.3239 | Cancellation-prefix detection alone does not capture all negative entries. | Review separately for inventory adjustments or other operational entries. |
| Zero quantity | 0 | 0 | No positive item quantity is recorded. | Review and define eligibility; do not silently replace with a positive quantity. |
| Zero price | 6,202 | 0.5811 | Could reflect gifts, adjustments or incomplete pricing; cause is not established. | Inspect context. Price-based analyses and presence-only baskets may require different documented policies. |
| Negative price | 5 | 0.0005 | May reflect accounting adjustments or data errors rather than normal product pricing. | Inspect affected stock codes and descriptions; do not take absolute values or impute a price automatically. |
| Quantity IQR flag | 116,489 | 10.9136 | Exploratory 1.5-IQR flag on all finite quantities; legitimate bulk orders can be flagged. | Review extremes and compare robust/log-scaled representations later; do not remove solely on this flag. |
| Price IQR flag | 68,105 | 6.3806 | Exploratory 1.5-IQR flag on all finite prices; unusual prices are not automatically errors. | Review item/charge context and distribution; evaluate sensitivity before choosing transformations or exclusions. |
| Description surrounding whitespace | 213,035 | 19.9589 | Text variants may fragment frequency counts. | Consider reversible normalization in a separate derived field during preprocessing; retain original descriptions. |
| Nontext description | 4 | 0.0004 | Nonmissing description cells contain values that are not text. | Inspect original cells and StockCode context; do not infer a product meaning or category from numeric description values. |
| Whitespace-only description | 0 | 0 | A nonempty cell may still lack meaningful description text. | Treat as a missing-description candidate after approval. |
| Atypical stock-code format | 6,094 | 0.5709 | Not five digits with optional letter suffix; a review heuristic, not proof of an invalid product. | Inspect special charges, adjustments and valid alternative codes individually; do not bulk-delete based on pattern. |
| Atypical invoice format | 6 | 0.0006 | Outside numeric or C-prefixed numeric invoice pattern. | Review prefixes and source context before treating these as purchase baskets. |
| Invalid nonmissing Quantity | 0 | 0 | Value failed numeric parsing. | Investigate source value; never silently coerce during preprocessing. |
| Nonfinite Quantity | 0 | 0 | Infinity cannot support normal numerical analyses. | Inspect source and quarantine from numerical calculations if confirmed. |
| Invalid nonmissing Price | 0 | 0 | Value failed numeric parsing. | Investigate source value; never silently coerce during preprocessing. |
| Nonfinite Price | 0 | 0 | Infinity cannot support normal numerical analyses. | Inspect source and quarantine from numerical calculations if confirmed. |
| Fractional quantity | 0 | 0 | May be incompatible with an assumed integer unit count. | Validate units before rounding or excluding. |
| Invalid nonmissing date | 0 | 0 | Date parsing failed. | Inspect raw date values and formats before correcting. |

Flags overlap. Treatments are recommendations for later approval, not actions already performed. Prioritize an explicit invoice/basket definition, worksheet-overlap review, purchase-versus-adjustment eligibility, missing-ID policy and reversible description normalization. Do not classify craft-related categories until Phase 4. Online Retail II is general retail/giftware data and does not establish handmade or artisan provenance.

## Visualizations

Monthly activity includes line counts, unique invoice IDs and C-prefix lines. Quantity and price plots show all finite observations using signed-log values plus a clearly labeled 1st–99th percentile detail panel. Tail values are excluded only from the detail panel, never from the data or full-range plot. Description frequency and missing-value plots provide additional initial context.

![missing values](../outputs/graphs/phase2_20261111_224047/missing_values.png)

![monthly activity](../outputs/graphs/phase2_20261111_224047/monthly_activity.png)

![price distribution](../outputs/graphs/phase2_20261111_224047/price_distribution.png)

![quantity distribution](../outputs/graphs/phase2_20261111_224047/quantity_distribution.png)

![top descriptions](../outputs/graphs/phase2_20261111_224047/top_descriptions.png)

## Reproducibility and validation

Run `.venv\Scripts\python.exe src\inspect_dataset.py` from the project root. Each execution creates new timestamped output directories, preserving earlier results. Package versions are recorded in `inspection_summary.json`; the project's full pins are in `requirements.txt`. The script hashes the raw workbook before and after analysis and checks against the Phase 1 manifest.

Passed checks: combined rows equal worksheet-row totals; monthly/country/sign counts reconcile; description counts plus missing descriptions equal the total; duplicate accounting reconciles. No algorithm was fitted and no external service received data.

Tables: `outputs/tables/phase2_20261111_224047`.

Data-quality summary and machine-readable metrics: `outputs/reports/phase2_20261111_224047`.

Graphs: `outputs/graphs/phase2_20261111_224047`.

Phase 2 inspection is complete. Stop and obtain explicit approval before Phase 3 preprocessing.
