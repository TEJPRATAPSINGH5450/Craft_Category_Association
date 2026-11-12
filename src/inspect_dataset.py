"""Read-only Phase 2 inspection. Writes reports, aggregate CSVs and PNGs only.

Run from any directory with the project's virtual-environment interpreter.
No source records are removed, imputed, standardized, or exported as cleaned data.
"""

from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
os.environ["MPLCONFIGDIR"] = str(ROOT / ".cache" / "matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SOURCE = ROOT / "data" / "raw" / "online_retail_II.xlsx"
SHEETS = ["Year 2009-2010", "Year 2010-2011"]
COLUMNS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate",
           "Price", "Customer ID", "Country"]
PERCENTILES = [.01, .05, .25, .5, .75, .95, .99, .999]
LOG = logging.getLogger("phase2")


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest().upper()


def markdown(frame):
    """Small dependency-free Markdown renderer for report summary tables."""
    def cell(value):
        if pd.isna(value):
            return "—"
        if isinstance(value, (float, np.floating)):
            return f"{value:,.4f}".rstrip("0").rstrip(".")
        if isinstance(value, (int, np.integer)):
            return f"{value:,}"
        return str(value).replace("|", "\\|").replace("\n", " ")
    rows = ["| " + " | ".join(map(str, frame.columns)) + " |",
            "| " + " | ".join("---" for _ in frame.columns) + " |"]
    rows.extend("| " + " | ".join(cell(v) for v in row) + " |"
                for row in frame.itertuples(index=False, name=None))
    return "\n".join(rows)


def main():
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise RuntimeError("Use the project's .venv interpreter.")
    run_id = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("phase2_%Y%m%d_%H%M%S")
    paths = {name: ROOT / "outputs" / name / run_id for name in ["tables", "graphs", "reports"]}
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(paths["reports"] / "inspection.log")])
    original_hash = sha256(SOURCE)
    manifest = json.loads((ROOT / "docs" / "dataset_manifest.json").read_text(encoding="utf-8-sig"))
    if original_hash != manifest["SHA256"]:
        raise RuntimeError("Raw input differs from the Phase 1 checksum; investigate before continuing.")

    def table(name, frame):
        frame.to_csv(paths["tables"] / f"{name}.csv", index=False)
        return frame

    def figure(name, fig):
        fig.savefig(paths["graphs"] / f"{name}.png", dpi=170, bbox_inches="tight")
        plt.close(fig)

    LOG.info("Loading workbook read-only with Pandas/openpyxl: %s", SOURCE)
    frames = {}
    with pd.ExcelFile(SOURCE, engine="openpyxl") as book:
        if set(book.sheet_names) != set(SHEETS):
            raise ValueError(f"Unexpected sheets: {book.sheet_names}")
        for name in SHEETS:
            # Only empty cells are NA; literal strings such as 'NA' are preserved.
            frames[name] = pd.read_excel(book, sheet_name=name, keep_default_na=False, na_values=[""])
            if list(frames[name].columns) != COLUMNS:
                raise ValueError(f"Unexpected columns in {name}: {list(frames[name].columns)}")
            LOG.info("Loaded %s: %s rows x %s columns", name, *frames[name].shape)
    df = pd.concat(frames.values(), ignore_index=True)
    n = len(df)
    provenance = pd.concat([pd.DataFrame({"source_sheet": name,
                                         "excel_row": np.arange(2, len(part) + 2)})
                            for name, part in frames.items()], ignore_index=True)
    scopes = {**frames, "Combined": df}
    dimensions = table("worksheet_dimensions", pd.DataFrame([
        {"scope": name, "rows": len(part), "columns": len(part.columns)}
        for name, part in scopes.items()]))
    schema = table("column_types", pd.DataFrame([
        {"scope": name, "column": col, "pandas_dtype": str(part[col].dtype),
         "observed_nonmissing_python_types": ", ".join(sorted(part[col].dropna().map(lambda x: type(x).__name__).unique()))}
        for name, part in scopes.items() for col in COLUMNS]))
    missing = table("missing_values", pd.DataFrame([
        {"scope": name, "column": col, "missing": int(part[col].isna().sum()),
         "percentage": float(part[col].isna().mean() * 100)}
        for name, part in scopes.items() for col in COLUMNS]))
    unique = table("unique_counts", pd.DataFrame([
        {"scope": name, "invoices": part.Invoice.nunique(), "products": part.StockCode.nunique(),
         "customers": part["Customer ID"].nunique(), "countries": part.Country.nunique(),
         "descriptions": part.Description.nunique()}
        for name, part in scopes.items()]))
    LOG.info("Computing exact duplicates and numeric/date diagnostics")
    duplicates = table("duplicate_summary", pd.DataFrame([
        {"scope": name, "repeat_occurrences_after_first": int(part.duplicated().sum()),
         "all_rows_in_duplicate_groups": int(part.duplicated(keep=False).sum()),
         "distinct_duplicate_groups": int(part.loc[part.duplicated(keep=False)].drop_duplicates().shape[0])}
        for name, part in scopes.items()]))
    # Exact equality uses all eight original columns; source metadata is excluded.
    cross_groups = df.groupby(COLUMNS, dropna=False, sort=False).ngroup()
    cross_counts = pd.DataFrame({"group": cross_groups, "sheet": provenance.source_sheet}).groupby("group").sheet.nunique()
    cross_ids = cross_counts.index[cross_counts.gt(1)]
    cross_mask = cross_groups.isin(cross_ids)
    duplicate_mask = df.duplicated(keep=False)
    table("duplicate_row_locations", provenance.loc[duplicate_mask].assign(
        duplicate_group=cross_groups[duplicate_mask].to_numpy(),
        repeats_prior_row=df.duplicated()[duplicate_mask].to_numpy(),
        occurs_in_both_sheets=cross_mask[duplicate_mask].to_numpy()))

    invoice_text = df.Invoice.astype("string")
    cancelled = invoice_text.str.match(r"(?i)^C", na=False)
    quantities = pd.to_numeric(df.Quantity, errors="coerce")
    prices = pd.to_numeric(df.Price, errors="coerce")
    dates = pd.to_datetime(df.InvoiceDate, errors="coerce")
    numeric = {"Quantity": quantities, "Price": prices}
    def signs(series):
        return pd.Series(np.select([series.lt(0), series.eq(0), series.gt(0)],
                                   ["negative", "zero", "positive"], default="missing_or_invalid"), index=series.index)
    sign_rows = []
    for name, part in scopes.items():
        for col in numeric:
            values = pd.to_numeric(part[col], errors="coerce")
            for sign in ["negative", "zero", "positive", "missing_or_invalid"]:
                count = int(signs(values).eq(sign).sum())
                sign_rows.append({"scope": name, "column": col, "sign": sign, "rows": count,
                                  "percentage": count / len(part) * 100})
    sign_table = table("quantity_price_signs", pd.DataFrame(sign_rows))
    cancellation = table("cancellation_summary", pd.DataFrame([
        {"scope": name, "cancelled_rows": int(part.Invoice.astype("string").str.match(r"(?i)^C", na=False).sum()),
         "cancelled_unique_invoices": part.loc[part.Invoice.astype("string").str.match(r"(?i)^C", na=False), "Invoice"].nunique()}
        for name, part in scopes.items()]))
    table("cancelled_invoice_ids", df.loc[cancelled].groupby("Invoice").agg(
        line_count=("StockCode", "size"), earliest=("InvoiceDate", "min"), latest=("InvoiceDate", "max"),
        minimum_quantity=("Quantity", "min"), maximum_quantity=("Quantity", "max")).reset_index())
    table("cancellation_quantity_crosstab", pd.crosstab(cancelled.rename("C_prefix"), signs(quantities).rename("quantity_sign")).reset_index())
    table("quantity_price_crosstab", pd.crosstab(signs(quantities).rename("quantity_sign"), signs(prices).rename("price_sign")).reset_index())
    date_summary = table("date_summary", pd.DataFrame([
        {"scope": name, "earliest": pd.to_datetime(part.InvoiceDate, errors="coerce").min(),
         "latest": pd.to_datetime(part.InvoiceDate, errors="coerce").max(),
         "missing_dates": int(part.InvoiceDate.isna().sum()),
         "invalid_nonmissing_dates": int((part.InvoiceDate.notna() & pd.to_datetime(part.InvoiceDate, errors="coerce").isna()).sum()),
         "rows_not_in_chronological_order": int(pd.to_datetime(part.InvoiceDate, errors="coerce").diff().lt(pd.Timedelta(0)).sum())}
        for name, part in scopes.items()]))
    stats = table("numeric_descriptive_statistics", pd.DataFrame(numeric).describe(percentiles=PERCENTILES).T.rename_axis("column").reset_index())
    df.describe(include="all", percentiles=PERCENTILES).T.rename_axis("column").reset_index().to_csv(
        paths["tables"] / "all_column_descriptive_statistics.csv", index=False)
    for name, part in frames.items():
        table("numeric_statistics_" + name.replace(" ", "_"), part[["Quantity", "Price"]].describe(percentiles=PERCENTILES).T.rename_axis("column").reset_index())

    outlier_rows = []
    outlier_flags = {}
    for col, series in numeric.items():
        finite = series[np.isfinite(series)]
        q1, q3 = finite.quantile([.25, .75])
        iqr = q3 - q1
        low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        flag = series.lt(low) | series.gt(high)
        outlier_flags[col] = flag
        outlier_rows.append({"column": col, "q1": q1, "q3": q3, "iqr": iqr,
                             "lower_fence": low, "upper_fence": high,
                             "below_fence": int(series.lt(low).sum()), "above_fence": int(series.gt(high).sum()),
                             "flagged_rows": int(flag.sum()), "percentage": float(flag.mean() * 100)})
    outliers = table("iqr_outlier_summary", pd.DataFrame(outlier_rows))
    extremes = []
    for col, series in numeric.items():
        for end, indices in [("lowest", series.nsmallest(10).index), ("highest", series.nlargest(10).index)]:
            examples = pd.concat([provenance.loc[indices], df.loc[indices]], axis=1).copy()
            examples.insert(0, "ranked_by", col)
            examples.insert(1, "end", end)
            extremes.append(examples)
    table("extreme_value_examples", pd.concat(extremes, ignore_index=True))

    description_counts = df.Description.value_counts(dropna=True).rename_axis("Description").reset_index(name="line_count")
    description_counts["percentage_of_all_rows"] = description_counts.line_count / n * 100
    descriptions = table("description_frequencies", description_counts)
    countries = table("country_frequencies", df.groupby("Country", dropna=False).agg(
        line_count=("Invoice", "size"), unique_invoices=("Invoice", "nunique"),
        unique_customers=("Customer ID", "nunique")).sort_values("line_count", ascending=False).reset_index())
    stock_description = table("stock_description_variation", df.groupby("StockCode", dropna=False).agg(
        line_count=("Invoice", "size"), distinct_nonmissing_descriptions=("Description", "nunique"),
        missing_descriptions=("Description", lambda s: s.isna().sum())).reset_index().sort_values("distinct_nonmissing_descriptions", ascending=False))
    # Review flags are diagnostic heuristics, not category mapping or exclusion rules.
    desc_text = df.Description.astype("string")
    nontext_description = df.Description.notna() & ~df.Description.map(lambda value: isinstance(value, str))
    stock_text = df.StockCode.astype("string")
    atypical_stock = ~stock_text.str.fullmatch(r"\d{5}[A-Za-z]*", na=False) & stock_text.notna()
    table("atypical_stock_codes", df.loc[atypical_stock].groupby(["StockCode", "Description"], dropna=False).size().reset_index(name="line_count").sort_values("line_count", ascending=False))
    invoice_groups = df.groupby("Invoice", dropna=False).agg(
        line_count=("StockCode", "size"), products=("StockCode", "nunique"),
        customers=("Customer ID", "nunique"), countries=("Country", "nunique"),
        timestamps=("InvoiceDate", "nunique"))
    table("invoice_size_statistics", invoice_groups[["line_count", "products"]].describe(percentiles=PERCENTILES).T.rename_axis("metric").reset_index())
    table("invoice_consistency_flags", invoice_groups.loc[(invoice_groups[["customers", "countries", "timestamps"]] > 1).any(axis=1)].reset_index())
    prefix = invoice_text.str.extract(r"^([^0-9]+)", expand=False).fillna("numeric/no prefix")
    table("invoice_prefixes", prefix.value_counts().rename_axis("prefix").reset_index(name="line_count"))

    quality = []
    def issue(label, mask, meaning, treatment):
        quality.append({"issue": label, "rows": int(mask.sum()), "percentage": float(mask.mean() * 100),
                        "interpretation": meaning, "possible_treatment_after_approval": treatment})
    issue("Missing Customer ID", df["Customer ID"].isna(), "Customer identity is unavailable; invoice baskets may still be usable.",
          "Do not invent IDs. Retain for invoice-level analysis when invoice/product data suffice; exclude only from customer-level analyses with documented coverage.")
    issue("Missing Description", df.Description.isna(), "Descriptions cannot support later category validation.",
          "Review StockCode description history and provenance; leave unresolved items unknown rather than guessing a category.")
    issue("Exact repeat occurrences after first", df.duplicated(), "Identical eight-column records can inflate frequencies but may represent repeated legitimate line entries.",
          "Investigate duplication and worksheet overlap; approve and document any deduplication policy before applying it.")
    issue("Cancellation-prefix invoice rows", cancelled, "C-prefix is an operational cancellation flag; no linkage to original sales is inferred.",
          "Separate cancellations/returns from purchase baskets; consider a separate returns analysis and document any matching logic.")
    issue("Negative quantity", quantities.lt(0), "Negative entries may be returns, cancellations or adjustments.",
          "Review cancellation status and descriptions; define purchase eligibility before excluding or netting quantities.")
    issue("Negative quantity without C prefix", quantities.lt(0) & ~cancelled, "Cancellation-prefix detection alone does not capture all negative entries.",
          "Review separately for inventory adjustments or other operational entries.")
    issue("Zero quantity", quantities.eq(0), "No positive item quantity is recorded.", "Review and define eligibility; do not silently replace with a positive quantity.")
    issue("Zero price", prices.eq(0), "Could reflect gifts, adjustments or incomplete pricing; cause is not established.",
          "Inspect context. Price-based analyses and presence-only baskets may require different documented policies.")
    issue("Negative price", prices.lt(0), "May reflect accounting adjustments or data errors rather than normal product pricing.",
          "Inspect affected stock codes and descriptions; do not take absolute values or impute a price automatically.")
    issue("Quantity IQR flag", outlier_flags["Quantity"], "Exploratory 1.5-IQR flag on all finite quantities; legitimate bulk orders can be flagged.",
          "Review extremes and compare robust/log-scaled representations later; do not remove solely on this flag.")
    issue("Price IQR flag", outlier_flags["Price"], "Exploratory 1.5-IQR flag on all finite prices; unusual prices are not automatically errors.",
          "Review item/charge context and distribution; evaluate sensitivity before choosing transformations or exclusions.")
    issue("Description surrounding whitespace", desc_text.ne(desc_text.str.strip()).fillna(False), "Text variants may fragment frequency counts.",
          "Consider reversible normalization in a separate derived field during preprocessing; retain original descriptions.")
    issue("Nontext description", nontext_description, "Nonmissing description cells contain values that are not text.",
          "Inspect original cells and StockCode context; do not infer a product meaning or category from numeric description values.")
    issue("Whitespace-only description", desc_text.str.fullmatch(r"\s+", na=False), "A nonempty cell may still lack meaningful description text.", "Treat as a missing-description candidate after approval.")
    issue("Atypical stock-code format", atypical_stock, "Not five digits with optional letter suffix; a review heuristic, not proof of an invalid product.",
          "Inspect special charges, adjustments and valid alternative codes individually; do not bulk-delete based on pattern.")
    issue("Atypical invoice format", ~invoice_text.str.fullmatch(r"(?i)C?\d+", na=False) & invoice_text.notna(),
          "Outside numeric or C-prefixed numeric invoice pattern.", "Review prefixes and source context before treating these as purchase baskets.")
    for col, series in numeric.items():
        issue(f"Invalid nonmissing {col}", df[col].notna() & series.isna(), "Value failed numeric parsing.", "Investigate source value; never silently coerce during preprocessing.")
        issue(f"Nonfinite {col}", series.notna() & ~np.isfinite(series), "Infinity cannot support normal numerical analyses.", "Inspect source and quarantine from numerical calculations if confirmed.")
    issue("Fractional quantity", quantities.notna() & quantities.mod(1).ne(0), "May be incompatible with an assumed integer unit count.", "Validate units before rounding or excluding.")
    issue("Invalid nonmissing date", df.InvoiceDate.notna() & dates.isna(), "Date parsing failed.", "Inspect raw date values and formats before correcting.")
    quality_df = table("data_quality_flags", pd.DataFrame(quality))
    review_masks = {"negative_price": prices.lt(0), "nontext_description": nontext_description,
                    "C_prefix_nonnegative_quantity": cancelled & quantities.ge(0),
                    "atypical_invoice": ~invoice_text.str.fullmatch(r"(?i)C?\d+", na=False) & invoice_text.notna()}
    review_rows = []
    for reason, mask in review_masks.items():
        detail = pd.concat([provenance.loc[mask], df.loc[mask]], axis=1).copy()
        detail.insert(0, "review_reason", reason)
        review_rows.append(detail)
    table("unusual_record_details", pd.concat(review_rows, ignore_index=True))
    cross_dates = dates[cross_mask]
    negative_price_context = df.loc[prices.lt(0)].groupby(["StockCode", "Description"], dropna=False).size().reset_index(name="rows")

    monthly = pd.DataFrame({"month": dates.dt.to_period("M").astype("string"), "Invoice": df.Invoice,
                            "cancelled": cancelled, "quantity": quantities}).groupby("month", dropna=False).agg(
        line_count=("Invoice", "size"), unique_invoices=("Invoice", "nunique"),
        cancellation_lines=("cancelled", "sum"), signed_quantity=("quantity", "sum")).reset_index()
    table("monthly_activity", monthly)
    assert len(df) == sum(len(part) for part in frames.values())
    assert monthly.line_count.sum() == n
    assert countries.line_count.sum() == n
    assert descriptions.line_count.sum() + df.Description.isna().sum() == n
    assert all(group.rows.sum() == len(scopes[scope]) for (scope, _), group in sign_table.groupby(["scope", "column"]))
    assert int(df.duplicated().sum()) == n - len(df.drop_duplicates())
    assert int(df.duplicated(keep=False).sum()) == int(df.duplicated().sum()) + int(duplicates.iloc[-1].distinct_duplicate_groups)
    LOG.info("All row-count, duplicate and aggregation reconciliation checks passed")

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "axes.titleweight": "bold"})
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, layout="constrained")
    x = np.arange(len(monthly))
    axes[0].bar(x, monthly.line_count, color="#26748a", label="All invoice lines")
    axes[0].bar(x, monthly.cancellation_lines, color="#b85543", label="C-prefix lines (subset)")
    axes[0].set_ylabel("Invoice lines")
    axes[0].legend(frameon=False)
    axes[1].plot(x, monthly.unique_invoices, marker="o", color="#26748a")
    axes[1].set_ylabel("Unique invoice IDs")
    axes[1].set_xticks(x, monthly.month, rotation=60, ha="right")
    fig.suptitle("Monthly recorded activity — all rows retained\nFirst/last months may be partial; no deduplication or return filtering")
    figure("monthly_activity", fig)
    for col, series in numeric.items():
        finite = series[np.isfinite(series)]
        lo, hi = finite.quantile([.01, .99])
        central = finite.between(lo, hi)
        transformed = np.sign(finite) * np.log10(1 + finite.abs())
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
        axes[0].hist(transformed, bins=90, color="#26748a", log=True)
        axes[0].set_xlabel(f"sign({col}) × log10(1 + |{col}|)")
        axes[0].set_ylabel("Invoice lines (log scale)")
        axes[0].set_title(f"Full finite range (n={len(finite):,})")
        axes[1].hist(finite[central], bins=60, color="#26748a", log=True)
        axes[1].set_xlabel(col + (" (source price units)" if col == "Price" else " (recorded units)"))
        axes[1].set_ylabel("Invoice lines (log scale)")
        axes[1].set_title(f"1st–99th percentile view: {lo:g} to {hi:g}\n{int((~central).sum()):,} values outside this panel")
        fig.suptitle(f"{col} distribution — display transformations only; no records removed")
        figure(col.lower() + "_distribution", fig)
    fig, ax = plt.subplots(figsize=(11, 7), layout="constrained")
    top = descriptions.head(15).iloc[::-1]
    ax.barh(top.Description, top.line_count, color="#26748a")
    ax.set_xlabel("Invoice-line occurrences (all rows, exact description text)")
    ax.set_title("15 most frequent nonmissing product descriptions")
    figure("top_descriptions", fig)
    fig, ax = plt.subplots(figsize=(9, 4.5), layout="constrained")
    plot_missing = missing[missing.scope.eq("Combined")]
    ax.bar(plot_missing.column, plot_missing.percentage, color="#b85543")
    ax.set_ylabel("Missing rows (%)")
    ax.set_title("Missing values by column — combined worksheets")
    ax.tick_params(axis="x", rotation=35)
    figure("missing_values", fig)

    final_hash = sha256(SOURCE)
    if original_hash != final_hash:
        raise RuntimeError("Raw input hash changed during inspection.")
    summary = {
        "run_id": run_id, "source": str(SOURCE), "sha256_before": original_hash, "sha256_after": final_hash,
        "raw_unchanged": True, "records_retained": n, "columns": COLUMNS,
        "dimensions": dimensions.to_dict("records"), "unique_counts": unique.to_dict("records"),
        "cross_sheet_exact_duplicate_groups": len(cross_ids), "rows_in_cross_sheet_duplicate_groups": int(cross_mask.sum()),
        "cross_sheet_additional_repeats": int(df.duplicated().sum() - sum(part.duplicated().sum() for part in frames.values())),
        "cross_sheet_duplicate_date_min": str(cross_dates.min()), "cross_sheet_duplicate_date_max": str(cross_dates.max()),
        "invoices_shared_between_sheets": len(set(frames[SHEETS[0]].Invoice.dropna()) & set(frames[SHEETS[1]].Invoice.dropna())),
        "stock_codes_with_multiple_descriptions": int(stock_description.distinct_nonmissing_descriptions.gt(1).sum()),
        "invoices_with_multiple_customers": int(invoice_groups.customers.gt(1).sum()),
        "invoices_with_multiple_countries": int(invoice_groups.countries.gt(1).sum()),
        "invoices_with_multiple_timestamps": int(invoice_groups.timestamps.gt(1).sum()),
        "cancellation_rows_nonnegative_quantity": int((cancelled & quantities.ge(0)).sum()),
        "dates": date_summary.astype(str).to_dict("records"), "duplicate_counts": duplicates.to_dict("records"),
        "quality_flags": quality_df.to_dict("records"), "checks_passed": True,
        "python": sys.version, "pandas": pd.__version__, "numpy": np.__version__, "matplotlib": matplotlib.__version__,
    }
    (paths["reports"] / "inspection_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    quality_report = "# Phase 2 data-quality summary\n\n" + f"Run: `{run_id}`. Denominator: {n:,} original invoice lines. Flags overlap and must not be summed. No treatment has been applied.\n\n"
    quality_report += markdown(quality_df) + "\n\nMissing values for all columns:\n\n" + markdown(missing[missing.scope.eq("Combined")])
    quality_report += "\n\nExact duplicate equality uses all eight original columns, with missing values treated as equal by Pandas. Counts refer to loaded values, not Excel formatting. See the inspection report for overlap and invoice-identity concerns.\n"
    quality_report += f"\nCross-sheet overlap: {len(cross_ids):,} exact groups occur in both sheets, spanning {cross_dates.min()} to {cross_dates.max()}. Review overlap separately from within-sheet repeated entries. No duplicates have been removed.\n"
    (paths["reports"] / "data_quality_summary.md").write_text(quality_report, encoding="utf-8")
    report = f"""# Dataset inspection and exploratory analysis

Project: Craft Category Association Discovery Through Clustered Transaction Analysis

INT396 — Aftab Khan and Tej Pratap Singh. Run: `{run_id}` (Asia/Calcutta).

## Scope and method

Both worksheets were loaded using Pandas/openpyxl and concatenated in worksheet order. All {n:,} invoice-line records remain in the in-memory analysis. No cleaned dataset was exported. Empty cells are parsed as missing (`keep_default_na=False, na_values=['']`), preserving literal text tokens such as `NA`. Numeric/date conversions and text-format checks use separate diagnostic Series; original columns are not overwritten. No imputation, deduplication, category mapping, clustering or association-rule mining was performed.

An invoice line is not a whole basket. Unique counts exclude missing identifiers and use loaded values without case/whitespace normalization. StockCode counts represent distinct recorded codes, including possible charges and adjustments, not a verified count of saleable products. Customer ID is an identifier, even if inferred as numeric. Price units are not verified by workbook column names alone, so plots use source price units.

Source: `{SOURCE}`. SHA-256 before and after: `{original_hash}`. Hashes match the Phase 1 manifest. The source was opened only for reading.

## Worksheet dimensions

{markdown(dimensions)}

## Columns and data types

{markdown(schema)}

Mixed types in identifier columns require deliberate handling in preprocessing. Do not use numerical Customer ID magnitude as a feature.

## Missing values

{markdown(missing)}

Percentages use the row count of the corresponding scope. Blank strings are missing at import; whitespace-only strings are checked separately. No missing values were estimated or filled.

## Unique identifiers

{markdown(unique)}

There are {summary['invoices_shared_between_sheets']:,} invoice IDs shared between worksheets. Counts across sheets are therefore not assumed additive. {summary['invoices_with_multiple_customers']:,} invoice IDs have multiple nonmissing customers, {summary['invoices_with_multiple_countries']:,} have multiple countries, and {summary['invoices_with_multiple_timestamps']:,} have multiple timestamps. These are review flags, not proof of corrupted invoices. Investigate invoice identity, worksheet overlap and timestamp semantics before defining baskets.

## Exact duplicates and worksheet overlap

{markdown(duplicates)}

`repeat_occurrences_after_first` counts copies beyond one retained occurrence per exact group. `all_rows_in_duplicate_groups` includes the first occurrence. Equality uses all eight original columns and excludes provenance. There are {len(cross_ids):,} distinct exact groups appearing in both worksheets, involving {int(cross_mask.sum()):,} rows. Combining sheets adds {summary['cross_sheet_additional_repeats']:,} repeat occurrences beyond the sum of within-sheet repeat counts. This overlap can affect volume and future support estimates. Do not deduplicate automatically: validate repeated line entries and define an auditable policy first. Row locations are in `duplicate_row_locations.csv` (Excel row numbers include the header).

The cross-sheet duplicate records span {cross_dates.min()} to {cross_dates.max()}. This is observed repeated coverage, not merely a hypothetical overlap. Resolve its treatment before interpreting December 2010 volume or later basket frequencies.

## Cancellations, quantities and prices

Cancellation flag: Invoice starts with C, case-insensitive, without trimming or editing source values. This is a convention-based flag; cancellation-to-original-sale links have not been established.

{markdown(cancellation)}

{markdown(sign_table)}

{int((quantities.lt(0) & ~cancelled).sum()):,} negative-quantity rows lack the C prefix. {summary['cancellation_rows_nonnegative_quantity']:,} C-prefix rows have nonnegative quantities. See both sign cross-tabulations for overlaps. Negative quantities and prices must not be converted to absolute values automatically. Zero prices need context before deciding eligibility for price-based or presence-only analyses.

Negative-price descriptions observed in the source:

{markdown(negative_price_context)}

These labels support reviewing accounting entries separately from normal product purchases. They do not establish the cause of every unusual price. `cancelled_invoice_ids.csv` identifies all C-prefix invoice IDs, and `unusual_record_details.csv` gives provenance for negative prices, nontext descriptions, atypical invoices and C-prefix rows with nonnegative quantities. A row can appear under multiple review reasons.

## Dates and coverage

{markdown(date_summary)}

Valid dates span {dates.min()} to {dates.max()}. The workbook does not specify a timezone; timestamps remain timezone-naive. Chronological-order flags count backward steps in source row order and do not establish invalid dates. The final month may be incomplete; monthly counts are observed totals, not annualized estimates. Overlapping worksheet periods and duplicate rows remain included in all activity charts.

The combined backward date step arises at the concatenation boundary: the second sheet starts before the first sheet ends. December 2011 coverage ends on December 9, so its smaller count should not be interpreted as a full-month decline.

## Descriptive statistics and potential outliers

{markdown(stats)}

Standard deviation is the sample standard deviation (Pandas default, ddof=1). Quantiles use Pandas' default linear interpolation. Only Quantity and Price are treated as numerical measures; all-column and per-sheet descriptive tables are also supplied.

{markdown(outliers)}

Potential outliers use lower/upper fences Q1 − 1.5×IQR and Q3 + 1.5×IQR over all finite values, including returns/adjustments. These are exploratory flags, not evidence of errors. Compare legitimate bulk purchases, special charges and anomalous entries before considering exclusions, robust scaling or transformations. No clipping or record removal was applied. `extreme_value_examples.csv` provides the ten lowest and highest rows for each measure with worksheet and Excel-row provenance.

## Product-description frequency and unusual codes

{markdown(descriptions.head(20))}

Frequencies count lines, not units sold or distinct purchasing baskets, and include cancelled and duplicate entries. Missing descriptions are excluded only from this ranking and remain in the dataset. {summary['stock_codes_with_multiple_descriptions']:,} stock codes have multiple exact nonmissing descriptions. Formatting changes, genuine renaming and operational notes are possibilities that require investigation; this is not category mapping.

`atypical_stock_codes.csv` lists codes outside the heuristic five digits plus optional letters pattern. Review these individually; the pattern is not an authoritative validity rule. `invoice_prefixes.csv` lists observed prefixes. `stock_description_variation.csv` supports later verified description work.

## Country distribution

{markdown(countries.head(10))}

Country line counts include every row; unique invoice counts by country need not sum to global unique counts if invoice IDs span countries. Geographical concentration should be considered when interpreting generalizability. No geographic filter was applied.

## Data-quality issues and proposed treatments

{markdown(quality_df)}

Flags overlap. Treatments are recommendations for later approval, not actions already performed. Prioritize an explicit invoice/basket definition, worksheet-overlap review, purchase-versus-adjustment eligibility, missing-ID policy and reversible description normalization. Do not classify craft-related categories until Phase 4. Online Retail II is general retail/giftware data and does not establish handmade or artisan provenance.

## Visualizations

Monthly activity includes line counts, unique invoice IDs and C-prefix lines. Quantity and price plots show all finite observations using signed-log values plus a clearly labeled 1st–99th percentile detail panel. Tail values are excluded only from the detail panel, never from the data or full-range plot. Description frequency and missing-value plots provide additional initial context.

"""
    report_path = ROOT / "docs" / f"dataset_inspection_{run_id}.md"
    for plot in sorted(paths["graphs"].glob("*.png")):
        report += f"![{plot.stem.replace('_', ' ')}](../{plot.relative_to(ROOT).as_posix()})\n\n"
    report += f"""## Reproducibility and validation

Run `.venv\\Scripts\\python.exe src\\inspect_dataset.py` from the project root. Each execution creates new timestamped output directories, preserving earlier results. Package versions are recorded in `inspection_summary.json`; the project's full pins are in `requirements.txt`. The script hashes the raw workbook before and after analysis and checks against the Phase 1 manifest.

Passed checks: combined rows equal worksheet-row totals; monthly/country/sign counts reconcile; description counts plus missing descriptions equal the total; duplicate accounting reconciles. No algorithm was fitted and no external service received data.

Tables: `{paths['tables'].relative_to(ROOT).as_posix()}`.

Data-quality summary and machine-readable metrics: `{paths['reports'].relative_to(ROOT).as_posix()}`.

Graphs: `{paths['graphs'].relative_to(ROOT).as_posix()}`.

Phase 2 inspection is complete. Stop and obtain explicit approval before Phase 3 preprocessing.
"""
    report_path.write_text(report, encoding="utf-8")
    LOG.info("Completed. Report: %s", report_path)
    print(json.dumps({"report": str(report_path), "outputs": {key: str(value) for key, value in paths.items()},
                      "rows": n, "sha256": final_hash}, indent=2))


if __name__ == "__main__":
    main()
