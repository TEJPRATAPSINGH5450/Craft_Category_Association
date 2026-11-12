# INT396 Research Dashboard

Read-only Streamlit application for **Craft Category Association Discovery Through Clustered Transaction Analysis**, by Aftab Khan and Tej Pratap Singh. Dashboard work is Phase 9 as explicitly authorized; it does not change completed research phases.

## Start locally

From PowerShell:

```powershell
cd C:\Users\aftab\Desktop\SuperwiseProject
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **http://127.0.0.1:8501**. The project configuration binds only to localhost and disables usage telemetry. Stop the foreground server with Ctrl+C. If the port is occupied by an existing instance, use that instance or select another port with `--server.port 8502`.

## Environment

Streamlit 1.67.0 and Plotly 7.1.0 are installed in the existing `.venv`; no global packages were installed. Original `requirements.txt` is unchanged.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_dashboard.txt
```

For a fresh project environment, install the original research requirements first, then dashboard additions. `dashboard/requirements.lock.txt` records the complete tested environment, including transitive packages. This environment uses Python 3.14.4; validate pins before changing Python/platform.

## Six views

1. **Project Overview:** purchase lines, invoices, products, classification coverage, selected-variant category footprint and findings.
2. **K-Means Clustering:** original-unit means/medians, cluster sizes, numerical evaluation and interactive PCA.
3. **Global Apriori:** support/confidence/lift filters, category search, itemsets, rule metrics, directed pair network and downloads.
4. **Cluster-wise Analysis:** population selector, rules, category prevalence and a live global/cluster rule comparison.
5. **Research Comparison:** variant overlap, threshold grid and statistically evaluated associations with BH/BY filters.
6. **Methodology & Findings:** dataset preservation, product inventory search, model methods, findings and limitations.

Change classification evidence in the sidebar. Coverage KPIs explicitly use High+Medium, while rule/category views use the selected variant. Use the Streamlit main menu → Settings → Theme for light/dark/system appearance. Styling follows the native theme. Small screens collapse navigation and stack KPI cards; wide data tables remain horizontally scrollable.

## Analytical interpretation

- Clusters represent **invoices**, not customers. Identifiers are never model features.
- Every association support denominator includes empty baskets and anonymous invoices.
- Saved rule exports start at support 1%, confidence 30%, with 2–4 total categories. The UI cannot recover rules below those floors; it never reruns Apriori.
- Frequent itemsets have no length cap. Their tab uses support/search/length filters; confidence/lift are rule metrics.
- A zero-rule result is preserved. Lower thresholds are sensitivity choices, not automatic fixes.
- “Shared/unique” is qualification under the current filters. Comparison blanks mean that side did not meet the filters; they are not imputed zeros. The validated baseline research tables remain fixed at 3%/50%.
- Downloaded rule CSVs retain raw probability-scale metrics, population, classification variant and denominator. The display table converts support/confidence to percent. Infinity is preserved for conviction when appropriate.
- Statistical significance is exploratory. Repeated customers, seasonality and same-data cluster construction limit inference. No causal, business-profitability or handmade-provenance claims are made.

## Architecture and performance

```text
app.py                         navigation and graceful data-error boundary
dashboard/pages/               six page modules
dashboard/components/          layout, Plotly charts, rule controls/tables
dashboard/utils/data.py        caching, source checksums, schemas, pure filters
dashboard/data/                prepared display assets and provenance
dashboard/prepare_assets.py    one-time PCA/prevalence preparation
dashboard/test_dashboard.py    real-data integration tests
dashboard/validation/          machine-readable automated results
dashboard/previews/            browser screenshots
```

Data reads use `st.cache_data` keyed by path, file modification time, size, selected columns and expected checksum. The first load verifies the artifact against Phase 8 provenance; modified/missing artifacts stop the affected view. Only compact aggregate/rule tables are loaded during browsing. The raw workbook and million-row purchase file are never opened by the app.

PCA coordinates are precomputed from the saved preprocessing transform and existing labels; only visualization PCA was fitted during preparation. K-Means was not retrained. At runtime, no sklearn/joblib/mlxtend model operations occur. By default, PCA displays at most 8,000 invoices with seed 42 and explicitly states the sample size; users can show all points.

`prepare_assets.py` already ran successfully and refuses to overwrite its assets. Version the assets before rebuilding after an authorized research revision. No rebuild is needed to start the app. Provenance references local invoice IDs and the unchanged upstream files.

## Validation

```powershell
.\.venv\Scripts\python.exe dashboard/test_dashboard.py
```

On a restricted Windows sandbox, Streamlit and its test harness need permission to use local sockets; this is a runtime sandbox constraint. Standard PowerShell on the PC can use the commands above.

Tests cover all six pages in both variants, all clusters, KPI reconciliation, filters, search, actual CSV contents, empty results, missing files, checksum/schema rejection, PCA controls, statistical controls and preservation of 260 prior files. Browser review additionally verifies layout and a real CSV download. See `dashboard/validation_report.md` for outcomes and scope.

This is a local review application, not a publicly deployed service. Research outputs and derived dashboard data must stay local; do not commit or upload them. The original `.gitignore` already excludes CSV/outputs. Do not deploy through Streamlit's built-in Deploy control without separate authorization.
