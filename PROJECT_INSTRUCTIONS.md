# Project instructions

## Identity

Project: Craft Category Association Discovery Through Clustered Transaction Analysis.
Subject: INT396 – Unsupervised Learning.
Members: Aftab Khan and Tej Pratap Singh.
Workspace: SuperwiseProject (do not rename).

## Authorization and workflow

Complete only the explicitly authorized phase. Phases 1–5 deliverables are complete. Phase 4 produced a separate description-based taxonomy and auditable product mapping, preserving raw and Phase 3 files. Of 4,896 products, 4,232 are classified (including 702 provisional Medium-confidence assignments); 664 Low-confidence products require manual review. Assistant description review is not human approval or external verification. Phase 5 preserved all 1,015,214 purchase lines and created features and separate High/High+Medium binary matrices for all 39,516 invoices. See outputs/reports/feature_engineering_report.md and its preservation manifest. Stop and wait for explicit approval before Phase 6 K-Means. Proactive improvements do not authorize advancing phases.

Phase 4 artifacts: `docs/product_taxonomy.md`, `outputs/tables/product_category_mapping.csv`, `outputs/tables/category_frequency.csv`, `outputs/tables/unclassified_products.csv`, and `outputs/reports/category_mapping_report.md`. Preserve valid outputs and version future mapping revisions rather than overwriting this baseline. Never interpret the confidence labels as measured accuracy or claim handmade provenance. Material evidence is separate from the functional categories. Other/Unclassified is not a substantive merchandise category for future rule interpretation. Phase 5 feature matrices are complete; no K-Means, Apriori or dashboard has been implemented. Preserve Phase 5 outputs and refit scaling within any future training split. Retain all-zero baskets unless a separately documented sensitivity analysis explicitly changes the support denominator.

The strategy in `docs/PREPROCESSING_STRATEGY.md` has been accepted. Preserve every valid supported purchase line, not exactly 100,000 records; never manufacture records or weaken validity criteria to reach a target. Retain anonymous purchases, legitimate bulk purchases and statistical outliers unless a separate supported validity issue applies. Never impute identifiers. Investigate cross-sheet overlap before reconciliation, preserve within-source multiplicity unless proven redundant, and retain all excluded rows with reasons and original worksheet/Excel-row references. Investigate zero-price merchandise before routing it. Save purchase lines, return review, operational adjustments, unresolved records and duplicate audit separately. The missing-Customer-ID dataset is an overlapping view, not an additional disjoint population. Report transaction lines and unique invoices/products/customers after every operation, validate saved datasets, and verify raw SHA-256 after processing. Do not implement category mapping, K-Means, Apriori or dashboard functionality in Phase 3.

1. Environment and Project Initialization.
2. Dataset Inspection and Exploratory Data Analysis.
3. Data Cleaning and Preprocessing.
4. Product Description Analysis and Verified Category Mapping.
5. Feature Engineering.
6. K-Means Clustering.
7. Apriori Association Rule Mining.
8. Global vs Cluster-wise Association Comparison.
9. Research Analysis and Evaluation.
10. Visualizations and Dashboard.
11. Testing, Documentation and Final Report.

Do not implement ML algorithms, preprocessing, EDA, or dashboard code during Phase 1. Do not install Streamlit before the dashboard phase.

## Mandatory safeguards

- Never modify or overwrite original raw data; preserve its checksum.
- Keep original data in `data/raw/`; cleaned data belongs in `data/processed/`.
- Ask before moving a dataset. The initial move to `data/raw/` was explicitly approved.
- Never upload datasets or project contents to external services without authorization; never upload this dataset to GitHub.
- Exclude environments, raw and derived datasets, temporary files, and potentially sensitive generated outputs from Git.
- Do not delete existing user files or perform destructive operations without approval.
- Do not make system-wide configuration changes without approval; install project packages only inside `.venv`.
- Never fabricate research findings or label synthetic records as genuine transactions.
- Preserve reproducibility through dependency pins, input hashes, recorded parameters and random seeds, and documented methodological decisions.

## Scientific standards

Online Retail II contains general retail/giftware transactions. It is not verified handicraft-only data. Establish craft-related categories using documented, carefully verified classification with uncertainty and ambiguous items accounted for. Do not infer artisan or handmade provenance without evidence.

Planned research includes similar transaction groups, frequent item/category combinations, global versus cluster-specific rules, rare-category associations, threshold sensitivity, association stability, and meaningful visualizations. Later phases must define transaction units, evaluation design, category verification, and limitations before implementing experiments. Report actual observations only.

## Engineering standards

Use modular reusable Python, meaningful names, appropriate error handling and logging, clear documentation, input validation, and relevant verification. Avoid unnecessary dependencies. Work incrementally and document significant technical decisions. Scientific correctness and data integrity take priority over convenience.
