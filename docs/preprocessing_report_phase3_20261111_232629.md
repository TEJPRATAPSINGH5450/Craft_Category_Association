# Phase 3 preprocessing report

Project: Craft Category Association Discovery Through Clustered Transaction Analysis (INT396).
Members: Aftab Khan and Tej Pratap Singh. Run: `phase3_20261111_232629`. Policy: `phase3-v1`.

## Outcome

Retained **1,015,214 purchase lines** (95.1135% of 1,067,371 original lines; 97.1638% of canonical lines). These are source-supported merchandise purchase records under the documented rules, not independently verified delivery/payment events. No synthetic rows, invented identifiers, numerical imputation, outlier removal, winsorization, scaling, model fitting or category mapping was performed. All original business columns remain unchanged.

## Separate outputs and counts

| dataset | overlapping_view | lines | unique_invoices | unique_products | unique_customers | missing_customer_id | missing_description_raw |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cleaned_purchase_lines | 0 | 1,015,214 | 39,516 | 4,896 | 5,852 | 226,953 | 0 |
| return_review | 0 | 21,038 | 10,470 | 4,024 | 2,445 | 3,396 | 2,633 |
| operational_adjustments | 0 | 4,817 | 4,642 | 377 | 641 | 2,261 | 34 |
| unresolved_records | 0 | 3,779 | 3,033 | 1,299 | 584 | 2,677 | 1,608 |
| duplicate_audit | 0 | 22,523 | 1,088 | 2,481 | 622 | 7,720 | 107 |
| missing_customer_id | 1 | 235,287 | 8,752 | 5,177 | 0 | 235,287 | 4,275 |
| zero_price_review | 1 | 6,024 | 5,379 | 2,971 | 51 | 5,954 | 4,275 |

Unique counts exclude missing IDs and include recorded stock codes, not verified craft categories. Customers/invoices/products can occur in multiple partitions: only the primary line counts plus duplicate copies are additive. Missing-customer and zero-price datasets are explicitly overlapping diagnostics. `row_audit` contains all 1,067,371 original source references and is not added to retention totals.

Original 1,067,371 = canonical 1,044,848 + duplicate copies 22,523. Canonical lines are partitioned into the four analytical/review datasets; none is deleted.

## Sequential retention ledger

Each row is the actual execution order. The `lines` column is the remaining unassigned pool, not always the purchase count. Once rows are routed to purchases, they leave this pool and enter the cumulative purchase total. All four identity counts are saved for every step in `sequential_retention.csv` along with cumulative destination totals.

| step | operation | input_lines | newly_routed_lines | lines | unique_invoices | unique_products | unique_customers | cumulative_cleaned_purchase_lines |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Load original worksheets | 1,067,371 | 0 | 1,067,371 | 53,628 | 5,305 | 5,942 | 0 |
| 1 | Reconcile exact cross-sheet occurrence pairs | 1,067,371 | 22,523 | 1,044,848 | 53,628 | 5,305 | 5,942 | 0 |
| 2 | Normalize descriptions and recover unambiguous prior descriptions | 1,044,848 | 0 | 1,044,848 | 53,628 | 5,305 | 5,942 | 0 |
| 3 | Separate evidenced operational/test/voucher entries | 1,044,848 | 4,817 | 1,040,031 | 52,484 | 5,279 | 5,921 | 0 |
| 4 | Preserve ambiguous Manual entries for review | 1,040,031 | 1,403 | 1,038,628 | 51,748 | 5,277 | 5,876 | 0 |
| 5 | Validate required fields | 1,038,628 | 0 | 1,038,628 | 51,748 | 5,277 | 5,876 | 0 |
| 6 | Review remaining negative prices | 1,038,628 | 0 | 1,038,628 | 51,748 | 5,277 | 5,876 | 0 |
| 7 | Preserve merchandise cancellation/return lines | 1,038,628 | 17,953 | 1,020,675 | 44,363 | 5,277 | 5,856 | 0 |
| 8 | Preserve non-C negative lines without calling them cancellations | 1,020,675 | 3,064 | 1,017,611 | 41,299 | 4,972 | 5,856 | 0 |
| 9 | Preserve other negative C-prefix lines for review | 1,017,611 | 21 | 1,017,590 | 41,278 | 4,961 | 5,853 | 0 |
| 10 | Review cancellation-prefix sign exceptions | 1,017,590 | 0 | 1,017,590 | 41,278 | 4,961 | 5,853 | 0 |
| 11 | Review remaining atypical invoice identities | 1,017,590 | 0 | 1,017,590 | 41,278 | 4,961 | 5,853 | 0 |
| 12 | Review zero-quantity records | 1,017,590 | 0 | 1,017,590 | 41,278 | 4,961 | 5,853 | 0 |
| 13 | Review residual note descriptions | 1,017,590 | 79 | 1,017,511 | 41,199 | 4,961 | 5,853 | 0 |
| 14 | Review unsupported product identity | 1,017,511 | 65 | 1,017,446 | 41,135 | 4,896 | 5,853 | 0 |
| 15 | Retain evidence-supported zero-price merchandise | 1,017,446 | 126 | 1,017,320 | 41,135 | 4,896 | 5,853 | 126 |
| 16 | Preserve remaining zero-price candidates for review | 1,017,320 | 2,232 | 1,015,088 | 39,516 | 4,896 | 5,852 | 126 |
| 17 | Retain all remaining supported positive-price purchases | 1,015,088 | 1,015,088 | 0 | 0 | 0 | 0 | 1,015,214 |
| 18 | Preserve any unhandled records | 0 | 0 | 0 | 0 | 0 | 0 | 1,015,214 |

## Exclusion and retention reasons

| dataset | decision_reason | lines | unique_invoices | unique_products | unique_customers |
| --- | --- | --- | --- | --- | --- |
| cleaned_purchase_lines | positive_merchandise_purchase | 1,015,088 | 39,516 | 4,896 | 5,852 |
| cleaned_purchase_lines | supported_zero_price_merchandise_on_paid_invoice | 126 | 97 | 94 | 41 |
| duplicate_audit | exact_cross_sheet_copy_same_occurrence | 22,523 | 1,088 | 2,481 | 622 |
| operational_adjustments | bad_debt_adjustment | 6 | 6 | 1 | 0 |
| operational_adjustments | bank_charges | 100 | 95 | 1 | 22 |
| operational_adjustments | carriage | 277 | 277 | 1 | 45 |
| operational_adjustments | commission | 16 | 16 | 1 | 1 |
| operational_adjustments | discount | 173 | 151 | 1 | 55 |
| operational_adjustments | dotcom_postage | 1,425 | 1,425 | 1 | 1 |
| operational_adjustments | explicit_adjustment | 70 | 70 | 2 | 53 |
| operational_adjustments | explicit_zero_price_operational_note | 409 | 409 | 355 | 0 |
| operational_adjustments | gift_voucher_not_merchandise | 100 | 93 | 9 | 0 |
| operational_adjustments | platform_fee | 36 | 36 | 1 | 0 |
| operational_adjustments | postage | 2,086 | 2,084 | 1 | 496 |
| operational_adjustments | samples_not_purchase | 102 | 37 | 1 | 0 |
| operational_adjustments | test_record | 17 | 17 | 2 | 5 |
| return_review | c_prefix_merchandise_return_or_cancellation | 17,953 | 7,399 | 2,872 | 2,443 |
| return_review | negative_c_prefix_product_identity_unresolved | 21 | 21 | 14 | 20 |
| return_review | non_c_negative_requires_return_vs_inventory_review | 3,064 | 3,064 | 2,302 | 0 |
| unresolved_records | ambiguous_description_or_operational_note | 79 | 79 | 70 | 0 |
| unresolved_records | manual_entry_merchandise_identity_not_established | 1,403 | 1,290 | 2 | 582 |
| unresolved_records | merchandise_identity_not_supported_by_sales_history | 65 | 65 | 65 | 0 |
| unresolved_records | zero_price_purchase_context_unresolved | 2,232 | 1,619 | 1,199 | 3 |

Every excluded line is present in return review, operational adjustments, unresolved records or duplicate audit with a nonempty exclusion reason. Missing Customer ID, missing Description, bulk quantity and IQR flags are not exclusion criteria. An incomplete record may still be unresolved for a separate documented identity or purchase-context reason.

## Cross-worksheet overlap and repeated purchases

Compared all eight original columns before normalization. Confirmed 22,202 exact cross-sheet groups with matching sheet multiplicities and 22,523 one-to-one occurrence pairs in December 1–9, 2010. Retained first-sheet occurrences and any unmatched records from either sheet. Each archived copy links to its retained original through `retained_source_id`. Exact record values, different source sheets, dates and occurrence multiplicity were validated. The archive represents repeated source coverage, not inferred cancellation of business purchases.

Retained **11,812** exact repeat occurrences inside the canonical source. No blanket `drop_duplicates` or Invoice + StockCode deduplication was applied. Composite-key and multiple-timestamp invoice review tables are supplied; multiple timestamps were not automatically split into new invoices. No invoice has conflicting known customers or countries. Basket feature construction remains deferred.

## Zero-price investigation

All **6,024** canonical zero-price lines were investigated and exported in `zero_price_review`. Operational entries were identified from reviewed code/description evidence, never from price alone. For potential merchandise, checked a matching product/normalized-description pair observed on actual positive-price merchandise lines and a positive-price merchandise witness in the same invoice. This criterion does not require Customer ID.

Retained **126** supported zero-price merchandise lines with unchanged zero price and explicit evidence references. They are eligible for presence-based purchase analysis; `purchase_value_eligible=False` distinguishes them from positive-price value observations. The data do not establish whether these were free gifts, promotions or missing charges. Remaining cases retain their original records and reasons for review; a zero price was not imputed.

| dataset | decision_reason | zero_price_evidence | lines |
| --- | --- | --- | --- |
| cleaned_purchase_lines | supported_zero_price_merchandise_on_paid_invoice | product_description_match_and_paid_merchandise_same_invoice | 126 |
| operational_adjustments | carriage | insufficient_or_nonpurchase_context | 3 |
| operational_adjustments | dotcom_postage | insufficient_or_nonpurchase_context | 7 |
| operational_adjustments | explicit_zero_price_operational_note | insufficient_or_nonpurchase_context | 409 |
| operational_adjustments | gift_voucher_not_merchandise | insufficient_or_nonpurchase_context | 22 |
| operational_adjustments | postage | insufficient_or_nonpurchase_context | 7 |
| operational_adjustments | test_record | insufficient_or_nonpurchase_context | 3 |
| return_review | non_c_negative_requires_return_vs_inventory_review | insufficient_or_nonpurchase_context | 3,064 |
| unresolved_records | ambiguous_description_or_operational_note | insufficient_or_nonpurchase_context | 79 |
| unresolved_records | manual_entry_merchandise_identity_not_established | insufficient_or_nonpurchase_context | 7 |
| unresolved_records | merchandise_identity_not_supported_by_sales_history | insufficient_or_nonpurchase_context | 65 |
| unresolved_records | zero_price_purchase_context_unresolved | insufficient_or_nonpurchase_context | 2,232 |

Product-context evidence may use another observed transaction from the complete descriptive dataset; temporal modeling must rebuild such evidence inside the chosen development window. Description *recovery*, in contrast, uses only observations at or before the target date and does not borrow a later description.

## Returns and operational entries

`return_review` is a review dataset, not a count of confirmed physical returns. C-prefix merchandise lines are marked cancellation/return candidates without asserting links to original sales. Non-C negatives are explicitly labeled for return-versus-inventory review. Reviewed operational notes/codes are routed separately before sign handling, so fee reversals are not called merchandise returns. Ambiguous Manual entries are unresolved. Source signs remain unchanged; no return is netted against a purchase automatically.

Operational reasons are narrow, versioned rules derived from reviewed source descriptions: postage, carriage, discounts, charges/fees, samples, bad debt, tests, vouchers and explicit zero-price inventory/operational notes. Atypical code format alone is never an exclusion rule; legitimate atypical merchandise codes remain eligible when supported. Ambiguous CHECK/unknown notes are not automatically asserted to be stock adjustments.

## Data quality and recovery

| scope | lines | unique_invoices | unique_products | unique_customers | missing_customer_id | missing_description_raw | C_prefix_lines | zero_prices | nontext_descriptions | quantity_outlier_flags | price_outlier_flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | 1,067,371 | 53,628 | 5,305 | 5,942 | 243,007 | 4,382 | 19,494 | 6,202 | 4 | 116,489 | 68,105 |
| canonical | 1,044,848 | 53,628 | 5,305 | 5,942 | 235,287 | 4,275 | 19,165 | 6,024 | 4 | 114,673 | 66,510 |
| purchases | 1,015,214 | 39,516 | 4,896 | 5,852 | 226,953 | 0 | 0 | 126 | 0 | 109,575 | 59,505 |

Description normalization creates separate fields (trim, whitespace collapse, uppercase), retaining original Description and its original type. Recovered **3,485** canonical missing/nontext descriptions only when the exact StockCode had one distinct usable merchandise description observed by that timestamp. Each recovery links to its source record; conflicting/no-prior evidence remains Unknown. Recovery does not turn an operational or unsupported zero-price event into a purchase. There is no craft-category assignment.

Quantity and Price had no missing source values; no numerical imputer was needed. Customer IDs and invoice IDs remain untouched. IQR flags are retained for later investigation without removing legitimate large purchases. No feature transforms were applied in this phase.

## Validation and reproducibility

All **69** recorded checks passed. Every saved CSV was re-read in chunks and every saved field compared against the in-memory source/derived values. Saved partition membership is unique, disjoint and exhaustive across all original rows; overlapping diagnostics are validated separately. Checks include original-column preservation, duplicate equality/multiplicity, zero-price evidence, purchase sign/prefix rules, invoice consistency, description chronology and complete exclusion reasons.

Raw SHA-256 before and after: `BCBE73B35F5B7BABF197FB0CB983A11F5D9FF929078D4AA53D171B1F2DF2E980` (identical to Phase 1 manifest). Output SHA-256 values, schema, software versions, source-code snapshot hash and policy are saved in the manifests. CSVs are gzip-compressed, not sampled. Type sidecars preserve mixed source-column types; use `schema.json` rather than automatic CSV type inference. Empty original cells remain missing. Raw data were not uploaded or modified.

Run `.venv\Scripts\python.exe src\preprocess_dataset.py` to reproduce into a new timestamped directory. Reports/tables are local. Input workbook checksum changes stop processing. Unit fixtures are synthetic test cases only, never analytical records or retention inputs.

Datasets: `data/processed/phase3_20261111_232629`.
Tables: `outputs/tables/phase3_20261111_232629`.
Reports and validation: `outputs/reports/phase3_20261111_232629`.

## Limitations and next phase

Transaction roles are evidence-based data preparation, not proof of physical goods transfer. Zero-price semantics, ambiguous notes and non-C negative transactions remain explicitly qualified. Same-sheet exact repeats are preserved because the workbook supplies no line IDs establishing that they are accidental duplicates. Description recovery is contextual and unambiguous within observed prior history, not external verification. The original dataset is general retail/giftware, not verified handicraft-only data.

Phase 3 is complete. **Stop and obtain explicit approval before Phase 4 product/category mapping.** No K-Means, Apriori or dashboard was implemented.
