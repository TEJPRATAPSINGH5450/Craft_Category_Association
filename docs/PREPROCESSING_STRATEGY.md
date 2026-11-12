# Proposed preprocessing strategy — approval required

Historical planning document. The user subsequently accepted this strategy and authorized Phase 3 with additional audit and preservation requirements. Phase 3 results are recorded in `preprocessing_report_phase3_20261111_232629.md`. The proposal text below is preserved as the pre-execution decision record; it is not the current execution status. Phase 4 remains unapproved.

Project: Craft Category Association Discovery Through Clustered Transaction Analysis, INT396.
Authors: Aftab Khan and Tej Pratap Singh.
Prepared: 2026-11-11, Asia/Calcutta.

## Status and decision

This document is a proposal, not an executed preprocessing report. No raw workbook was changed, no preprocessing pipeline was executed, and no processed dataset was generated for this request. Calculations below use existing Phase 2 summary tables only. Implementation of Phase 3 requires explicit approval; category mapping, feature generation and model execution remain subject to their later phase boundaries.

Recommend retaining every defensible product-purchase line regardless of missing Customer ID, missing description, bulk quantity or an outlier flag. Preserve returns, adjustments, duplicate-copy provenance and unresolved entries separately. A missing description does not by itself invalidate a known product code. The target of at least 100,000 genuine eligible purchase lines is a feasibility criterion, never a reason to relax validity rules, copy observations or create synthetic transactions.

## Evidence already measured

Source of counts: `outputs/tables/phase2_20261111_224047/` and `outputs/reports/phase2_20261111_224047/inspection_summary.json`.

| Observation | Measured count | Interpretation |
|---|---:|---|
| Original line-item rows | 1,067,371 | Both sheets, unchanged |
| Exact repeat occurrences beyond first | 34,335 | Equality is confirmed; redundancy as business events is not automatically confirmed |
| Exact groups appearing in both sheets | 22,202 | Repeated coverage from December 1–9, 2010 |
| Rows belonging to those cross-sheet groups | 45,046 | Includes both copies and legitimate within-source multiplicity |
| Paired cross-sheet copies under occurrence matching | 22,523 | Computed from existing duplicate-row provenance; every group has equal counts in the two sheets |
| C-prefix cancellation-flagged rows | 19,494 | 8,292 distinct C-prefix invoice IDs; includes one positive-quantity Manual entry |
| Negative quantities | 22,950 | 19,493 C-prefix and 3,457 non-C rows |
| Zero quantities | 0 | No imputation needed |
| Positive quantities | 1,044,421 | Not all are valid merchandise purchases |
| Positive-quantity, positive-price rows | 1,041,671 | Includes the one C-prefix positive-quantity row |
| Positive-quantity, zero-price rows | 2,745 | Review separately; not all 6,202 zero-price rows are purchase candidates |
| Negative prices | 5 | All labeled Adjust bad debt |
| Missing Customer ID | 243,007 | Cross-cutting flag; do not remove from invoice-based purchase analysis |
| Missing Description | 4,382 | Recovery/unknown handling, not automatic deletion |
| Nontext descriptions | 4 | Review without inventing product meaning |
| Missing quantities, prices, invoices, stock codes, countries or dates | 0 | No present need for numerical imputation |
| Unparseable dates/numerical values | 0 | Distinct from unusual but parseable values |

Counts overlap. In particular, do not subtract cancellation rows and all negative quantities independently, or add missing-ID records to the purchase total as if they were new rows.

## Expected retention calculation: measured candidate pool, unresolved final total

The following is a hypothetical accounting sequence computed from the Phase 2 quantity/price and cancellation cross-tabs. None of these operations has been executed on records.

| Proposed eligibility step | Incremental change | Candidate rows after step | Evidence/status |
|---|---:|---:|---|
| Begin with all original lines | — | 1,067,371 | Measured |
| Retain positive quantities for the purchase candidate view; preserve negative rows elsewhere | −22,950 | 1,044,421 | Measured; zero quantities = 0 |
| Set aside zero-price positive-quantity lines pending review | −2,745 | 1,041,676 | Measured; does not use the full-dataset zero-price total |
| Route negative-price positive-quantity lines away from purchases | −5 | 1,041,671 | Measured bad-debt entries |
| Exclude C-prefix rows still in this positive/positive pool | −1 | **1,041,670** | Measured Manual entry, not double-counting negative C-prefix rows |
| Reconcile approved redundant copies within this pool | −D | 1,041,670 − D | D requires joint row-level eligibility and duplicate analysis |
| Route remaining confirmed operational/test entries out of purchases | −A | 1,041,670 − D − A | A counts only newly excluded rows, avoiding overlap with D |
| Hold unresolved invalid or ambiguous purchase candidates for review | −U | 1,041,670 − D − A − U | U counts only additional rows, not missing IDs/descriptions by default |
| Admit validated zero-price merchandise purchases, if the purchase definition permits | +Z | **P = 1,041,670 − D − A − U + Z** | Z is distinct, reconciled genuine rows from the 2,745-row review pool; 0 ≤ Z ≤ 2,745 |
| Retain missing Customer IDs, preserve missing descriptions and flag bulk/outlier values | 0 automatic loss | P | Enforced preservation policy |

Candidate share before deduplication/operational review: **1,041,670 / 1,067,371 × 100 = 97.5921%**. Final retention will be **100 × P / 1,067,371**. P is not yet known and must not be called a measured valid-purchase total.

Conservative sensitivity calculation: even subtracting all **34,335** exact repeat occurrences from this candidate pool leaves **1,007,335**, or **94.3753%** of the original rows, *before* additional operational/ambiguity review. This is deliberately pessimistic duplicate accounting, not a recommendation to discard every repeat. Some repeats are outside the candidate pool, and within-sheet repeats can be legitimate. It is not a guaranteed final usable count.

The 100,000-line target holds if **D + A + U − Z ≤ 941,670**. Existing evidence therefore supports substantial headroom, but genuine eligibility and final retention can only be established after approved reconciliation and review. Do not report a forecast as an observed result. The target concerns line items: there are only 53,628 raw unique invoice IDs, so it does not imply 100,000 baskets, customers or independent observations.

## Proposed operation order and provenance

1. Verify source SHA-256 against the manifest and read both sheets without editing them. Retain source sheet and Excel row number as lineage metadata; these are not fabricated business identifiers.
2. Preserve original columns and types. Create separate, reversible diagnostic/normalized fields and validity flags. Do not fill missing Invoice, Customer ID or StockCode with invented identifiers.
3. Investigate cross-sheet overlap and invoice consistency, then apply only approved reconciliation. Keep every excluded copy in a provenance ledger linked to the retained occurrence.
4. Apply documented transaction-role rules, with explicit evidence and precedence. Keep ambiguous records in review rather than labeling them genuine purchases or confirmed returns by default.
5. Recover descriptions conservatively, keeping raw text and recovery provenance. Preserve unresolved records where product eligibility is otherwise established.
6. Produce versioned analytical views, all linked to source rows. Quantities/prices remain original in these views; any later transformed modeling features live separately.
7. Produce a retention ledger and validation report, verify the raw checksum again, and stop at the approved phase boundary.

The execution ledger must use the actual implementation order. Its intermediate counts may differ from the illustrative eligibility-first calculation above; the final result must reconcile under identical rules.

## Duplicate and overlap policy

**Exact comparison:** all eight original columns before text normalization, excluding provenance; missing-value equality is documented. Report both groups and excess occurrences. Normalization must not silently turn similar descriptions into exact source duplicates.

**Cross-sheet reconciliation:** pair identical occurrences within the overlapping period. For a row signature with sheet counts m1 and m2, the proposed overlap-only policy retains max(m1, m2) occurrences and archives min(m1, m2) duplicate copies. This preserves within-source multiplicity. The existing provenance table yields 22,523 candidate redundant copies and zero groups with unequal multiplicity. The matching count is stronger evidence of repeated coverage, but invoice context and near-matching records still need review before execution. Never drop the entire overlapping calendar interval merely because some rows match. Use a documented deterministic source preference only for confirmed matching copies; retain additional or differing records.

If all 22,523 copies are confirmed, the combined master view would contain **1,044,848** rows before role-based separation. This is a conditional all-role total, not a purchase count. A blanket exact-drop operation would instead remove 34,335 rows and could destroy legitimate repeated line entries; it is not the default.

**Composite-key investigation:** inspect Invoice + StockCode + timestamp, with quantity, price, customer and country as comparison fields. Repeated Invoice + StockCode alone does not prove duplication: separate quantities, price changes and repeated legitimate lines can occur. Review the 83 invoice IDs with multiple timestamps; do not split each distinct timestamp into a new basket or merge all same-day activity automatically. Keep the original invoice ID intact. If an internal basket key is needed after evidence of invoice-ID reuse, it must be a deterministic grouping key with documented provenance, not an imputed Invoice ID.

## Analytical datasets and transaction-role rules

These are planned outputs only; none has been generated.

| View | Eligibility and handling |
|---|---|
| Purchase analysis | Genuine merchandise with positive quantity, acceptable invoice/product identity, and no cancellation/operational exclusion. Positive price is the conservative baseline. Retain missing Customer IDs, unresolved descriptions with valid merchandise identity, legitimate bulk orders and statistical outliers. Validate zero-price merchandise separately and mark its status; keep a positive-price value-analysis subset. |
| Return analysis | Evidence-supported merchandise returns/cancellations, preserving original signed quantity, price and cancellation flag. Include eligible non-C returns only after context review. C-prefix alone does not make a fee reversal a product return. |
| Operational adjustments | Evidence-supported fees, postage/carriage, discounts, bad-debt adjustments, stock corrections, tests and other non-merchandise entries. Preserve both signs and source descriptions. Confirm context rather than treating every atypical code as an adjustment: some atypical codes describe real goods. Keep uncertain Manual entries in review. |
| Missing Customer ID | An overlapping diagnostic view of canonical source rows with missing IDs, carrying purchase/return/adjustment/review status. A record can belong here and in purchases. Never combine all such rows into one fictitious customer. |
| Unresolved review | Records whose transaction role or required identity remains unsupported. No forced labels or silent deletion; document what would resolve each case. |
| Duplicate-copy archive | Original copies excluded from canonical analysis, with retained-occurrence links and reasons. Never counted twice toward retention. |

Primary routing precedence: confirmed operational/test status first; then evidence-supported merchandise return/cancellation status; then valid positive merchandise purchases; otherwise unresolved review. Missingness and cancellation-prefix flags remain available independently of this routing. The one positive-quantity C-prefix Manual row stays outside purchases unless corrected with evidence. The 3,457 non-C negative rows are review candidates, not automatically cancellations or confirmed returns.

Do not subtract returns from original purchases by default: the main basket analysis describes recorded purchase occasions. A later net-of-returns sensitivity view requires reliable matching using actual identifiers, product, time, quantity and price. Preserve unmatched returns, permit partial/multiple returns where supported, and do not assert that superficially matching positive/negative extremes are definitely linked.

## Missing-value techniques: evaluated suitability

Quantity and Price have no missing values in the inspected workbook. A zero or negative value is observed information, not a missing value. Consequently numerical imputation currently has **no justified role in repairing these source measures**.

| Technique | Recommendation | K-Means / Apriori implications |
|---|---|---|
| Mean imputation | Reject as a source-data default. Consider only later for genuinely missing, suitably distributed continuous derived features if a justified comparison needs it. Never fill quantities, prices, descriptions or identifiers blindly. | Can reduce variance and distort Euclidean geometry; never creates a purchased item or invoice membership. |
| Median imputation | Conditional baseline for genuinely missing skewed derived numerical features, with a missingness indicator and retained original values. Not needed for current Quantity/Price. | Less tail-sensitive than the mean but can create an artificial feature concentration; no role in binary item presence. |
| Mode imputation | Reject global mode for descriptions, product/category labels or identifiers. A most-common label is not evidence of the missing item's identity. | Could artificially inflate popular categories, alter distances and invent associations. |
| KNN imputation | Not warranted by current missingness. Consider only for later continuous features with a meaningful scaled distance and validated missingness design. Benchmark memory/runtime on an appropriate sample if needed. | Can blur genuine groups by borrowing neighbors' values. Never infer purchases or customer identities from neighbors. |
| Iterative imputation | Not warranted now. Conditional future comparison for genuinely missing continuous features with plausible inter-feature relationships and recorded uncertainty/seed. Its scikit-learn implementation remains experimental. | Modeled fills may induce relationships that resemble cluster structure. Never use for identifiers, category truth or basket membership. |
| StockCode-based recovery | Preferred contextual option for missing/invalid descriptions. Use valid merchandise descriptions linked to the same actual StockCode with temporal/context consistency. Accept only unambiguous evidence; report coverage and conflicts. | Preserves usable product lines without inventing numerical measurements. Product baskets can already use validated StockCode even when description recovery fails. |
| Unknown / Unclassified | Preferred fallback metadata label for unresolved descriptions/categories. It is explicitly absence of verified classification, not an assigned product type. | Preserve transactions. Do not pool unrelated unknown products into one marketed category and mine rules as if it were real merchandise. |

For description recovery, retain `description_raw`, normalized description, recovery status, method, source rows and conflict flag. The 1,232 stock codes with multiple descriptions prohibit unconditional first-match or most-frequent-description assignment. Do not propagate operational notes as merchandise names. Missing Customer IDs stay missing even if another row appears to suggest an identity; this plan does not authorize customer-identity filling.

No manufactured missingness or imputation experiments are needed now. If later authorized to benchmark imputation, hide observed feature values only in a clearly labeled evaluation copy, never alter genuine source data or count the masked/reconstructed values as additional transactions. Fit imputers only on the development partition, assess recovery and distribution distortion, and do not claim that simulated missingness proves accuracy for naturally missing values. See [scikit-learn imputation guidance](https://scikit-learn.org/stable/modules/impute.html) and [IterativeImputer documentation](https://scikit-learn.org/stable/modules/generated/sklearn.impute.IterativeImputer.html).

## Outlier techniques: retain records, distinguish transformations from deletion

| Technique | Proposed use | Expected effect and limitation |
|---|---|---|
| IQR fences | Diagnostic flags, not an exclusion rule. Reassess on eligible purchases and later invoice features rather than reusing thresholds from mixed sales/returns/charges. | Phase 2 flagged 116,489 quantities and 68,105 prices, with overlap. Those counts are not proposed removals. Bulk orders can be valid. |
| Z-score | Secondary diagnostic on suitable features, including transformed versions; not an automatic absolute-z cutoff. | Raw heavy tails and extreme values affect mean/standard deviation; flagging is not proof of error. Report flags without changing row membership. |
| Winsorization | Optional sensitivity variant on derived K-Means feature copies only, with predefined percentile limits fitted on development data. Keep uncapped features and disclose affected counts. | Caps genuine magnitude and can erase meaningful bulk-purchase distinctions. No source-value overwrite; no main-path default. |
| Log transformation | Compare `log1p` for nonnegative skewed count/value features after transaction-role separation. Never log identifiers, blindly apply it to negative returns, or log category proportions automatically. | Compresses scale without deleting rows; changes the distance geometry and relative importance of bulk orders. |
| RobustScaler | Recommended candidate after optional log transformation, compared with StandardScaler on the same feature population. Handle constant/zero-IQR features explicitly. | Median/IQR scaling reduces sensitivity of scale estimation to tails, but does not cap extremes or make K-Means itself outlier-proof. |

Scaling/logging/winsorization have **zero automatic line-item loss** under this plan. Apriori's binary basket representation does not need these numerical transformations. It still needs transaction-role and duplicate review: binary encoding does not by itself prevent duplicated baskets from inflating support. Technical definitions: [RobustScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.RobustScaler.html), [SciPy winsorization](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.mstats.winsorize.html).

## Categorical preparation and phase boundaries

Phase 3 may create reversible description normalization fields: trim surrounding whitespace, collapse repeated whitespace and standardize case for comparisons. Preserve original strings, meaningful numbers, units and distinctions. Do not use aggressive punctuation deletion or stemming that merges different items. Preserve StockCode spelling/case/leading zeros; only canonicalize representations after explicit collision checks. Invoice and customer numbers are keys, never ordinal measurements.

Merchandise-versus-operational routing is a transaction-validity task, distinct from craft-category assignment. Product classification and verified craft-related category mapping remain **Phase 4**. Use evidence, confidence/status, versioned rules and reviewed ambiguous cases. The dataset is general retail/giftware; no code or description proves handmade provenance.

Encoding remains **Phase 5**: binary product/category presence for Apriori; numerical measures and, if justified, weighted category-share/presence features for K-Means. Do not ordinal-encode nominal products/countries. Do not one-hot encode Customer ID or Invoice as K-Means features. Keep rare categories visible for the later rare-association objective rather than automatically grouping all of them into Other.

## Separate algorithm preparation plans

**K-Means: favor invoice-level clustering for the main study.** It preserves anonymous purchases and aligns cluster membership with the invoice baskets used for global-versus-cluster comparisons. Candidate Phase 5 features include distinct merchandise products, positive units, basket value, and robust within-basket price summaries; verified category shares can be evaluated after Phase 4. Avoid redundant totals/averages that repeatedly weight basket size, and compare composition-focused versus size-focused feature sets. Report skewness/quantiles, feature correlations and substantive feature weights before fitting. Keep missing-ID status as a diagnostic rather than allowing it to define clusters by default.

Compare untransformed features plus StandardScaler, log-transformed skewed features plus StandardScaler, and log-transformed features plus RobustScaler. A capped-feature version is optional sensitivity analysis, not the main dataset. K-Means optimizes squared-distance inertia, so transforms and feature weights affect its meaning; compare cluster stability, silhouette in each declared feature space, sizes and interpretability, not raw inertia across incompatible scales. Do not pick the representation solely because it produces the largest silhouette. See [KMeans documentation](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html).

Customer-level RFM-style features may be a secondary analysis for observed customer IDs only. Report its narrower coverage and do not sacrifice anonymous invoice records from the main purchase view. These are plans for later phases, not authorization to generate features or fit models now.

**Apriori: use one resolved invoice per basket and one validated item per column.** Encode whether an eligible product appears at least once using boolean presence; repeated lines or bulk quantity do not increase that basket's item indicator. Retain missing customer IDs and single-item invoices; do not remove single-item baskets simply because they cannot produce multi-item rules, as that changes support denominators. Keep original line-to-basket links so dimensional aggregation is never reported as data loss. The package expects one-hot transaction input; see [mlxtend Apriori documentation](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/apriori/).

Use exactly the same eligible invoice universe for global and cluster-specific rule comparisons, with explicit global/within-cluster denominators and support counts. Distinct product codes remain valid for product-level baskets when category is unknown. For category rules, omit unresolved labels from item columns, report mapping coverage, and explicitly choose the basket denominator: retain empty mapped baskets if estimating prevalence among all eligible purchases, or use a clearly labeled restricted population. Never silently change denominators or treat Unknown as a substantive category. Do not infer absent products in a basket from missing data.

## Alternative comparisons and leakage controls

After the relevant phase approvals, compare overlap-only reconciliation versus an evidence-reviewed within-sheet deduplication variant; positive-price purchases versus additionally validated zero-price merchandise; and the K-Means feature transformations above. Report line counts, invoices, product coverage, anonymous-customer coverage and genuine bulk-order representation for each variant. For category analysis, quantify unresolved coverage separately from purchase-line retention.

Resolve shared source occurrences before defining evaluation splits so copies cannot leak across partitions. Use invoice-level splits for the main invoice study; use customer-level grouping only for claims about unseen identified customers. Do not infer anonymous customer groups. Fit learned imputation/scaling/capping parameters and data-derived description recovery on development data only for held-out evaluations. Apply the same learned transformations to validation data. Resample invoices rather than treating correlated invoice lines as independent observations. Time-based stability studies must handle the overlap and incomplete final month explicitly. This plan does not run those experiments.

## Required execution report and acceptance checks

Create a sequential ledger with operation, rule/version, input rows, newly affected rows, retained rows, destination, cumulative purchase eligibility and percentage of original rows. Each count must come from the actual processed records; retain overlapping issue flags separately from mutually exclusive routing totals.

The final report must include original rows; exact-repeat detections; reviewed redundant copies excluded; C-prefix rows before and after reconciliation; valid purchase rows before and after each eligibility rule; confirmed merchandise returns; operational adjustments; unresolved rows; missing-ID and missing-description counts in both the original and each analytical view; recovered versus unresolved descriptions; final usable purchase lines; eligible invoice baskets; and the percentage retained. Confirmed returns, adjustments, recovered descriptions and final purchases are **not yet measured** and must remain pending, not zero.

Require these checks before declaring completion:

- Raw SHA-256 is unchanged before/after; every analytical row maps to genuine source evidence.
- Original rows = canonical rows + archived redundant copies.
- Canonical rows = purchases + merchandise returns/cancellations + operational adjustments + unresolved review, using mutually exclusive primary roles.
- The missing-ID view is an overlay, excluded from that additive identity.
- No row is excluded solely for missing Customer ID/Description, statistical outlier status or legitimate bulk quantity. Any exclusion has a separate supported validity reason.
- No synthetic transactions or invented business identifiers exist; no duplicate copies count toward the 100,000 target.
- Assert purchase eligibility, genuine source linkage, numeric/date validity, stable basket identity and no unreviewed special-code leakage.
- Publish ledger differences across approved variants, including basket counts and category coverage. Aggregation must not masquerade as line-item loss.
- Test the 100,000 target only after these checks; if it fails, report why and do not relax validity rules just to pass.

## Approval boundary

Requested next authorization: implement Phase 3 with this preservation-first policy, investigate and reconcile duplicate overlap, produce the separated analytical views and measured retention ledger, and leave ambiguous entries documented for review. Category mapping remains Phase 4, feature generation Phase 5, K-Means Phase 6 and Apriori Phase 7. Until approval arrives, this document and project instructions are the only project changes authorized by this request.
