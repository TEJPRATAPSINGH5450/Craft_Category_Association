# Craft Category Association Discovery Through Clustered Transaction Analysis

INT396 – Unsupervised Learning academic project by **Aftab Khan** and **Tej Pratap Singh**.

## Scope and research objectives

Planned methods are K-Means clustering and Apriori association rule mining. Research will compare global and cluster-specific associations, investigate rare-category associations, examine threshold sensitivity and stability, and communicate findings through visualizations.

Online Retail II is a general retail/giftware dataset, **not a verified handicraft-only dataset**. Craft-related category labels require a documented, carefully verified classification process. Product descriptions do not establish handmade or artisan provenance.

## Current status

Phases 1–5 deliverables are complete. Phase 5 preserved all 1,015,214 purchase lines and created numerical features for 39,516 invoices, including 2,922 anonymous invoices. Both binary category matrices retain all invoices and have 14 category columns. High-confidence assignments cover 80.76% of purchase lines; High+Medium assignments cover 93.97%. All 175 validation checks passed and 26 protected input hashes remained unchanged. Model fitting and rule mining have not been performed. Stop for explicit approval before Phase 6.

Phase 5 deliverables:

- [Feature engineering report](outputs/reports/feature_engineering_report.md)
- [Reproducible pipeline](src/feature_engineering.py)
- [Original invoice features](outputs/tables/invoice_features_raw.csv.gz)
- [High-confidence binary baskets](outputs/tables/apriori_basket_high_confidence.csv.gz)
- [High+Medium binary baskets](outputs/tables/apriori_basket_high_medium.csv.gz)
- [Feature summary](outputs/tables/feature_summary.csv)
- [Transformation parameters](outputs/reports/feature_transformations.json)
- [Validation and preservation manifest](outputs/reports/feature_engineering_manifest.json)

Four scaling candidates are saved separately. The initial candidate uses log1p for quantity, value and product count, followed by RobustScaler; product diversity is scaled without log1p. No clustering performance has been evaluated. Refit transformations within training subsets for future held-out evaluation. Unclassified products remain in numerical totals but never become invented category labels; all-zero baskets remain present with coverage flags. Phase 4 confidence labels are evidence assessments, not measured accuracy or handmade provenance.

Phase 4 deliverables:

- [Product taxonomy and scope](docs/product_taxonomy.md)
- [Product category mapping](outputs/tables/product_category_mapping.csv)
- [Category frequencies and line coverage](outputs/tables/category_frequency.csv)
- [Unclassified products requiring manual review](outputs/tables/unclassified_products.csv)
- [Classification report](outputs/reports/category_mapping_report.md)
- [Decision audit](outputs/tables/product_mapping_decision_audit.csv)
- [Validation and preservation record](outputs/reports/category_mapping_validation.json)

The taxonomy assigns a primary product function and records material wording separately. It never establishes handmade provenance. The 48 individual assistant reviews are explicitly distinguished from human approval. All 5,607 original description variants are retained. Read StockCode as text using the supplied original-type metadata when joining later; no categories were written into Phase 3 files. The final builder refuses to replace existing outputs; future revisions must be versioned. Contextual regression tests are in `src/test_product_classification.py`.

Phase 3 deliverables:

- [Preprocessing report](docs/preprocessing_report_phase3_20261111_232629.md)
- [Separate processed datasets and schema](data/processed/phase3_20261111_232629/)
- [Sequential retention ledger](outputs/tables/phase3_20261111_232629/sequential_retention.csv)
- [Dataset counts](outputs/tables/phase3_20261111_232629/dataset_counts.csv)
- [Validation checks](outputs/reports/phase3_20261111_232629/validation_checks.json)

The processed datasets are gzip-compressed CSV files. Read `schema.json` for original mixed types and identifier handling. `row_audit` accounts for all 1,067,371 source rows. `missing_customer_id` and `zero_price_review` are overlapping diagnostics and must not be added to the mutually exclusive partition totals. Source worksheet and Excel-row references are included. No source measurements or IDs were imputed, and no outliers were automatically removed.

To reproduce Phase 3 in a new versioned output directory:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s src -p test_preprocessing.py
.\.venv\Scripts\python.exe src\preprocess_dataset.py
```

The pipeline validates the raw checksum, reconciles exact cross-sheet occurrences while preserving within-source repeats, routes records under the saved policy, and re-reads every output to validate all saved fields and partition membership. It does not construct model features or category mappings. The unit tests use clearly labeled synthetic fixtures only; these never enter analytical datasets.

Latest Phase 2 deliverables:

- [Dataset inspection report](docs/dataset_inspection_phase2_20261111_224047.md)
- [Data-quality summary](outputs/reports/phase2_20261111_224047/data_quality_summary.md)
- [Summary tables](outputs/tables/phase2_20261111_224047/)
- [Visualizations](outputs/graphs/phase2_20261111_224047/)

Run `.venv\Scripts\python.exe src\inspect_dataset.py` to reproduce the inspection in new timestamped output directories. This reads the source without changing it. The earlier inspection run is preserved; the linked run includes additional unusual-record diagnostics.

## Local environment

Windows / PowerShell, Python 3.14.4, and a project-local `.venv`. Python 3.11/3.12 were preferred but were not registered on this PC. Python 3.14 was selected after the package resolver confirmed compatible Windows wheels. No system Python installation or system configuration change was needed.

From the project root in PowerShell:

```powershell
. .\.venv\Scripts\Activate.ps1
python --version
python -m pip check
python src/verify_environment.py
```

Activation applies to the current terminal only. Alternatively use `.\.venv\Scripts\python.exe` directly; no execution-policy change is necessary. In VS Code select `.venv\Scripts\python.exe` as the Python interpreter and notebook environment.

To recreate on compatible Windows/Python:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` records the full installed dependency set, including transitive packages, for reproducibility. Streamlit is deferred until Phase 10. Version pins are specific to this verified environment and should be revalidated when changing Python or OS.

## Workspace structure

```text
SuperwiseProject/
|-- .venv/
|-- data/
|   |-- raw/online_retail_II.xlsx
|   `-- processed/
|-- notebooks/
|-- src/verify_environment.py
|-- outputs/
|   |-- graphs/
|   |-- reports/
|   `-- tables/
|-- docs/
|-- requirements.txt
|-- README.md
|-- PROJECT_INSTRUCTIONS.md
`-- .gitignore
```

The original `online+retail+ii/` directory is preserved. With user approval, the workbook was moved from that directory to `data/raw/online_retail_II.xlsx`. Its size is 45,622,278 bytes; the before/after SHA-256 hashes matched. See `docs/dataset_manifest.json`. Phase 2 also confirmed the same checksum after inspection.

Verified worksheets: `Year 2009-2010` and `Year 2010-2011`. Verified columns: Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country.

## Data and reproducibility

Never edit or overwrite raw data. Write derived datasets to `data/processed/`. Keep data local and out of GitHub and other external services. Record parameters, seeds, input hashes, dependency versions, and evaluation decisions in subsequent phases. Never fabricate results or present synthetic data as genuine transactions.

See `PROJECT_INSTRUCTIONS.md` for phase boundaries and `docs/environment_report.md` for initialization verification.
#   C r a f t _ C a t e g o r y _ A s s o c i a t i o n  
 