"""Phase 3 preservation-first routing with occurrence-level provenance.

No category mapping, feature engineering, model fitting or rule mining.
All business columns remain unchanged. CSV type sidecars preserve mixed Excel types.
"""
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from inspect_dataset import ROOT, SOURCE, SHEETS, COLUMNS, sha256, markdown

POLICY_VERSION = "phase3-v1"
OPERATIONAL_CODES = {
    "POST": "postage", "DOT": "dotcom_postage", "C2": "carriage", "D": "discount",
    "S": "samples_not_purchase", "BANK CHARGES": "bank_charges", "AMAZONFEE": "platform_fee",
    "B": "bad_debt_adjustment", "CRUK": "commission", "ADJUST": "explicit_adjustment",
    "ADJUST2": "explicit_adjustment", "TEST001": "test_record", "TEST002": "test_record",
}
# These exact labels were reviewed in the Phase 3 diagnostic tables. Ambiguous
# CHECK, ?, AMAZON, DOTCOM, TEMP, MANUAL and blank labels are NOT auto-adjustments.
OPERATIONAL_NOTES = {
    "DAMAGED", "DAMAGES", "DAMAGES?", "FOUND", "MISSING", "ADJUSTMENT", "AMENDMENT",
    "SOLD AS SET ON DOTCOM", "UNSALEABLE, DESTROYED.", "THROWN AWAY", "SMASHED",
    "MAILOUT", "GIVEN AWAY", "CRUSHED", "HAD BEEN PUT ASIDE", "COUNTED", "WET DAMAGED",
    "NO STOCK", "PRINTING SMUDGES/THROWN AWAY", "INCORRECT STOCK ENTRY.", "BROKEN",
    "WET PALLET", "AMAZON ADJUSTMENT", "TEST", "WATER DAMAGED", "WET/RUSTY", "WET RUSTY",
    "WRONG CODE", "THIS IS A TEST PRODUCT.", "TAIG ADJUST", "STOCK CHECK", "EBAY SALES",
    "DOTCOM SALES",
}
AMBIGUOUS_NOTES = {"CHECK", "CHECKED", "?", "??", "???", "AMAZON", "DOTCOM", "EBAY",
                   "TEMP", "UPDATE", "MANUAL", "MIA", "WET"}
PRIMARY = ["cleaned_purchase_lines", "return_review", "operational_adjustments", "unresolved_records"]
LOG = logging.getLogger("phase3")


def normalize_description(series):
    return series.where(series.map(lambda value: isinstance(value, str))).astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.upper()


def exact_occurrence_links(df):
    """Pair equal occurrences across sheets; never collapse same-sheet repeats."""
    group = df.groupby(COLUMNS, dropna=False, sort=False).ngroup()
    occurrence = df.groupby([group, df.source_sheet], sort=False).cumcount()
    pair = pd.DataFrame({"exact_group": group, "occurrence": occurrence}, index=df.index)
    duplicate = pair.duplicated(keep="first")
    first_index = pd.Series(df.index.to_numpy(), index=df.index).groupby([group, occurrence], sort=False).transform("first")
    return group, occurrence, duplicate, first_index


def counters(part):
    return {"lines": len(part), "unique_invoices": int(part.Invoice.nunique()),
            "unique_products": int(part.StockCode.nunique()),
            "unique_customers": int(part["Customer ID"].nunique()),
            "missing_customer_id": int(part["Customer ID"].isna().sum()),
            "missing_description_raw": int(part.Description.isna().sum())}


def operational_reasons(df):
    stock = df.StockCode.astype("string")
    norm = df.description_normalized
    reason = stock.map(OPERATIONAL_CODES).fillna("").astype("string")
    gift = stock.str.match(r"^gift_0001_\d+$", na=False)
    reason.loc[gift] = "gift_voucher_not_merchandise"
    note = df.Price.eq(0) & norm.isin(OPERATIONAL_NOTES) & reason.eq("")
    reason.loc[note] = "explicit_zero_price_operational_note"
    return reason


def source_text(series):
    """Stable serialization of raw mixed strings/numbers; never fill an ID."""
    return series.map(lambda v: "" if pd.isna(v) else str(v)).astype("string")


def run():
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise RuntimeError("Run with the project's .venv interpreter")
    run_id = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("phase3_%Y%m%d_%H%M%S")
    processed = ROOT / "data" / "processed" / run_id
    reports = ROOT / "outputs" / "reports" / run_id
    tables = ROOT / "outputs" / "tables" / run_id
    for path in [processed, reports, tables]:
        path.mkdir(parents=True, exist_ok=False)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(reports / "preprocessing.log")])
    before = sha256(SOURCE)
    expected = json.loads((ROOT / "docs" / "dataset_manifest.json").read_text(encoding="utf-8-sig"))["SHA256"]
    if before != expected:
        raise RuntimeError("Raw hash differs from the approved Phase 1 input")
    parts = []
    with pd.ExcelFile(SOURCE, engine="openpyxl") as book:
        if book.sheet_names != SHEETS:
            raise ValueError("Unexpected worksheet layout")
        for sheet in SHEETS:
            part = pd.read_excel(book, sheet_name=sheet, keep_default_na=False, na_values=[""])
            if list(part.columns) != COLUMNS:
                raise ValueError("Unexpected original schema")
            part["source_sheet"] = sheet
            part["source_row"] = np.arange(2, len(part) + 2)
            part["source_id"] = sheet + ":" + part.source_row.astype(str)
            parts.append(part)
            LOG.info("Read %s: %s rows", sheet, len(part))
    df = pd.concat(parts, ignore_index=True)
    raw = df[COLUMNS].copy(deep=True)
    n = len(df)
    checks = []
    def check(name, condition):
        passed = bool(condition)
        checks.append({"check": name, "passed": passed})
        if not passed:
            raise AssertionError(name)
    check("original_row_count", n == 1067371)
    check("unique_source_references", df.source_id.is_unique)
    ledger = []
    def snapshot(step, remaining, affected, destination, note):
        ledger.append({"step": len(ledger), "operation": step, "input_lines": len(remaining) + affected,
                       "newly_routed_lines": affected, "destination": destination, **counters(remaining),
                       "percentage_of_original": len(remaining) / n * 100, "note": note})
    snapshot("Load original worksheets", df, 0, "", "All source rows; line counts are not invoice counts")
    group, occurrence, duplicates, retained_index = exact_occurrence_links(df)
    df["exact_group"] = group
    df["within_sheet_occurrence"] = occurrence
    df["retained_source_id"] = df.loc[retained_index, "source_id"].to_numpy()
    df["is_duplicate_copy"] = duplicates
    duplicate_idx = df.index[duplicates]
    canonical_idx = df.index[~duplicates]
    overlap = df.groupby(["exact_group", "source_sheet"], sort=False).size().unstack(fill_value=0)
    overlap = overlap[overlap.gt(0).all(axis=1)]
    check("overlap_occurrence_counts_equal", overlap.nunique(axis=1).eq(1).all())
    check("overlap_copies_22523", int(duplicates.sum()) == 22523)
    check("overlap_groups_22202", len(overlap) == 22202)
    # Full-value equality, not hash-only deduplication, plus one-to-one source links.
    pd.testing.assert_frame_equal(raw.loc[duplicate_idx].reset_index(drop=True),
                                  raw.loc[retained_index[duplicates]].reset_index(drop=True))
    check("duplicate_target_is_other_sheet", (df.loc[duplicate_idx, "source_sheet"].to_numpy() != df.loc[retained_index[duplicates], "source_sheet"].to_numpy()).all())
    check("unique_target_per_duplicate_occurrence", df.loc[duplicate_idx, "retained_source_id"].is_unique)
    check("copies_within_overlap_period", df.loc[duplicates, "InvoiceDate"].between("2010-12-01", "2010-12-10", inclusive="left").all())
    # Validate max multiplicity, preserving repeated purchases inside the source.
    expected_multiplicity = df.groupby(["exact_group", "source_sheet"]).size().groupby(level=0).max()
    retained_multiplicity = df.loc[~duplicates].groupby("exact_group").size()
    check("within_source_multiplicity_preserved", expected_multiplicity.equals(retained_multiplicity))
    snapshot("Reconcile exact cross-sheet occurrence pairs", df.loc[canonical_idx], len(duplicate_idx), "duplicate_audit", "Prefer first worksheet only for exact matching occurrence; all differing rows retained")
    LOG.info("Reconciled %s cross-sheet copies; %s canonical lines", len(duplicate_idx), len(canonical_idx))

    # Composite-key audit is investigative: no composite-key deduplication.
    canonical = df.loc[canonical_idx]
    composite = canonical.groupby(["Invoice", "StockCode", "InvoiceDate"], dropna=False).agg(
        lines=("source_id", "size"), quantity_variants=("Quantity", "nunique"),
        price_variants=("Price", "nunique"), description_variants=("Description", "nunique"),
        customer_variants=("Customer ID", "nunique"))
    composite.loc[composite.lines.gt(1)].reset_index().to_csv(tables / "composite_key_investigation.csv", index=False)
    invoice_consistency = canonical.groupby("Invoice", dropna=False).agg(
        customers=("Customer ID", "nunique"), countries=("Country", "nunique"),
        timestamps=("InvoiceDate", "nunique"), earliest=("InvoiceDate", "min"), latest=("InvoiceDate", "max"))
    invoice_consistency.loc[invoice_consistency.timestamps.gt(1)].reset_index().to_csv(tables / "multiple_timestamp_invoices.csv", index=False)
    check("invoice_no_conflicting_known_customer", invoice_consistency.customers.le(1).all())
    check("invoice_no_conflicting_country", invoice_consistency.countries.le(1).all())
    overlap.assign(paired_copies=overlap.min(axis=1)).reset_index().to_csv(tables / "overlap_reconciliation.csv", index=False)

    for col in ["Invoice", "StockCode", "Description"]:
        df["raw_type_" + col] = df[col].map(lambda v: "missing" if pd.isna(v) else type(v).__name__)
    df["description_normalized"] = normalize_description(df.Description)
    df["description_clean"] = df.description_normalized
    df["description_status"] = "observed_normalized"
    df["description_evidence_source_id"] = ""
    df["cancellation_prefix"] = df.Invoice.astype("string").str.match(r"(?i)^C", na=False)
    df["missing_customer_id"] = df["Customer ID"].isna()
    df["missing_description_raw"] = df.Description.isna()
    df["nontext_description_raw"] = df.Description.notna() & ~df.Description.map(lambda v: isinstance(v, str))
    op_reason = operational_reasons(df)
    stock = df.StockCode.astype("string")
    numeric_invoice = df.Invoice.astype("string").str.fullmatch(r"\d+", na=False)
    manual = stock.isin(["M", "m"])
    desc_valid = (df.description_normalized.str.contains(r"[A-Z]{2}", regex=True, na=False)
                  & ~df.description_normalized.isin(OPERATIONAL_NOTES | AMBIGUOUS_NOTES))
    valid_numbers = np.isfinite(df.Quantity) & np.isfinite(df.Price)
    seed = (~duplicates & op_reason.eq("") & ~manual & numeric_invoice & df.Quantity.gt(0)
            & df.Price.gt(0) & desc_valid & df.StockCode.notna() & valid_numbers)
    # Product identity evidence comes from real positive-price merchandise lines;
    # a five-digit stock pattern is deliberately NOT required.
    seed_frame = df.loc[seed].sort_values(["InvoiceDate", "source_row"], kind="stable")
    product_first = seed_frame.drop_duplicates("StockCode").set_index("StockCode")
    df["product_evidence_source_id"] = df.StockCode.map(product_first.source_id).fillna("")
    df["product_evidence_date"] = df.StockCode.map(product_first.InvoiceDate)
    product_supported = df.product_evidence_source_id.ne("")
    # Recovery uses only one distinct normalized description observed up to the
    # target timestamp. Future description changes do not authorize backfilling.
    desc_first = seed_frame.drop_duplicates(["StockCode", "description_normalized"])
    first = desc_first.drop_duplicates("StockCode").set_index("StockCode")
    second = desc_first.loc[desc_first.groupby("StockCode", sort=False).cumcount().eq(1)].set_index("StockCode")
    first_time = df.StockCode.map(first.InvoiceDate)
    second_time = df.StockCode.map(second.InvoiceDate)
    needs_description = df.description_normalized.isna() | df.description_normalized.eq("")
    recover = needs_description & first_time.le(df.InvoiceDate) & (second_time.isna() | second_time.gt(df.InvoiceDate))
    df.loc[needs_description, "description_status"] = "unknown_no_unambiguous_prior_description"
    df.loc[needs_description, "description_clean"] = "Unknown"
    df.loc[recover, "description_clean"] = df.loc[recover, "StockCode"].map(first.description_normalized)
    df.loc[recover, "description_status"] = "recovered_unique_prior_stock_description"
    df.loc[recover, "description_evidence_source_id"] = df.loc[recover, "StockCode"].map(first.source_id)
    snapshot("Normalize descriptions and recover unambiguous prior descriptions", df.loc[canonical_idx], 0, "derived_fields_only", "Original text retained; identifiers and measurements never imputed")

    # Route mutually exclusive roles. Uncertainty remains visible, never called a
    # confirmed return solely because Quantity is negative.
    df["dataset"] = "pending"
    df["decision_reason"] = ""
    df["exclusion_reason"] = ""
    df["routing_step"] = 0
    df.loc[duplicates, "dataset"] = "duplicate_audit"
    df.loc[duplicates, "decision_reason"] = "exact_cross_sheet_copy_same_occurrence"
    df.loc[duplicates, "exclusion_reason"] = "exact_cross_sheet_copy_same_occurrence"
    df.loc[duplicates, "routing_step"] = 1
    def route(mask, dataset, reason, step_name, note=""):
        selected = mask.fillna(False) & df.dataset.eq("pending")
        df.loc[selected, "dataset"] = dataset
        df.loc[selected, "decision_reason"] = reason.loc[selected] if isinstance(reason, pd.Series) else reason
        if dataset != "cleaned_purchase_lines":
            df.loc[selected, "exclusion_reason"] = df.loc[selected, "decision_reason"]
        df.loc[selected, "routing_step"] = len(ledger)
        remaining = df.loc[df.dataset.eq("pending")]
        snapshot(step_name, remaining, int(selected.sum()), dataset, note)
        return selected

    route(op_reason.ne(""), "operational_adjustments", op_reason, "Separate evidenced operational/test/voucher entries")
    route(manual, "unresolved_records", "manual_entry_merchandise_identity_not_established", "Preserve ambiguous Manual entries for review")
    invalid = ~valid_numbers | df.Invoice.isna() | df.StockCode.isna() | df.InvoiceDate.isna()
    route(invalid, "unresolved_records", "invalid_required_identity_measure_or_date", "Validate required fields", "Missing Customer ID or Description does not trigger this rule")
    route(df.Price.lt(0), "unresolved_records", "negative_price_without_confirmed_accounting_context", "Review remaining negative prices")
    route(df.Quantity.lt(0) & df.cancellation_prefix & product_supported, "return_review", "c_prefix_merchandise_return_or_cancellation", "Preserve merchandise cancellation/return lines", "Original sale linkage not asserted")
    route(df.Quantity.lt(0) & ~df.cancellation_prefix, "return_review", "non_c_negative_requires_return_vs_inventory_review", "Preserve non-C negative lines without calling them cancellations", "This subset is not a confirmed-return count")
    route(df.Quantity.lt(0), "return_review", "negative_c_prefix_product_identity_unresolved", "Preserve other negative C-prefix lines for review")
    route(df.cancellation_prefix, "unresolved_records", "c_prefix_with_nonnegative_quantity", "Review cancellation-prefix sign exceptions")
    route(~numeric_invoice, "unresolved_records", "unresolved_invoice_format", "Review remaining atypical invoice identities")
    route(df.Quantity.eq(0), "unresolved_records", "zero_quantity_not_purchase", "Review zero-quantity records")
    route(df.description_normalized.isin(OPERATIONAL_NOTES | AMBIGUOUS_NOTES), "unresolved_records",
          "ambiguous_description_or_operational_note", "Review residual note descriptions")
    route(~product_supported, "unresolved_records", "merchandise_identity_not_supported_by_sales_history", "Review unsupported product identity", "Code format, missing ID and missing description alone are not exclusion rules")

    # Zero-price investigation must precede any exclusion. A same-invoice paid
    # merchandise witness plus a matching observed product description supports
    # presence-only purchase analysis; the zero price is never replaced.
    pending_paid = df.dataset.eq("pending") & df.Quantity.gt(0) & df.Price.gt(0)
    paid_witness = df.loc[pending_paid].drop_duplicates("Invoice").set_index("Invoice").source_id
    df["paid_invoice_evidence_source_id"] = df.Invoice.map(paid_witness).fillna("")
    observed_pairs = pd.MultiIndex.from_frame(seed_frame[["StockCode", "description_normalized"]].drop_duplicates())
    candidate_pairs = pd.MultiIndex.from_arrays([df.StockCode, df.description_clean])
    matching_description = pd.Series(candidate_pairs.isin(observed_pairs), index=df.index)
    supported_zero = (df.Price.eq(0) & df.Quantity.gt(0) & product_supported & matching_description
                      & df.paid_invoice_evidence_source_id.ne(""))
    df["zero_price_evidence"] = "not_zero_price"
    df.loc[df.Price.eq(0), "zero_price_evidence"] = "insufficient_or_nonpurchase_context"
    df.loc[supported_zero, "zero_price_evidence"] = "product_description_match_and_paid_merchandise_same_invoice"
    zero_selected = route(supported_zero, "cleaned_purchase_lines", "supported_zero_price_merchandise_on_paid_invoice",
                          "Retain evidence-supported zero-price merchandise", "Eligible for presence-based analysis; free gift versus missing charge is not independently verified")
    route(df.Price.eq(0), "unresolved_records", "zero_price_purchase_context_unresolved", "Preserve remaining zero-price candidates for review", "Zero price investigated, never automatically filled or silently discarded")
    route(df.Quantity.gt(0) & df.Price.gt(0), "cleaned_purchase_lines", "positive_merchandise_purchase",
          "Retain all remaining supported positive-price purchases", "No outlier removal, within-sheet deduplication or missing-ID exclusion")
    route(df.dataset.eq("pending"), "unresolved_records", "unhandled_case_requires_review", "Preserve any unhandled records")
    check("no_unhandled_cases", not df.decision_reason.eq("unhandled_case_requires_review").any())
    df["purchase_value_eligible"] = df.dataset.eq("cleaned_purchase_lines") & df.Price.gt(0)
    # Retain outliers as flags only, using the Phase 2 descriptive fences.
    df["quantity_iqr_flag"] = df.Quantity.lt(-12.5) | df.Quantity.gt(23.5)
    df["price_iqr_flag"] = df.Price.lt(-3.1) | df.Price.gt(8.5)
    df["policy_version"] = POLICY_VERSION
    purchase = df.dataset.eq("cleaned_purchase_lines")
    check("purchase_positive_quantity", df.loc[purchase, "Quantity"].gt(0).all())
    check("purchase_nonnegative_price", df.loc[purchase, "Price"].ge(0).all())
    check("purchase_no_cancellation_prefix", not df.loc[purchase, "cancellation_prefix"].any())
    check("purchase_no_operational_or_manual", (op_reason[purchase].eq("") & ~manual[purchase]).all())
    check("purchase_zero_price_supported", supported_zero[purchase & df.Price.eq(0)].all())
    check("primary_partition_exhaustive", df.dataset.isin(PRIMARY + ["duplicate_audit"]).all())
    check("excluded_records_have_reasons", df.loc[~purchase, "exclusion_reason"].ne("").all())
    check("purchases_have_no_exclusion_reason", df.loc[purchase, "exclusion_reason"].eq("").all())
    pd.testing.assert_frame_equal(raw, df[COLUMNS])
    check("original_business_columns_unchanged_in_memory", True)
    check("recovery_uses_no_future_description", first_time[recover].le(df.loc[recover, "InvoiceDate"]).all())
    check("purchase_target_met_without_resampling", int(purchase.sum()) >= 100000)

    # A sequential remaining-pool ledger plus cumulative destination columns.
    for entry in ledger:
        step = entry["step"]
        for dest in PRIMARY + ["duplicate_audit"]:
            entry["cumulative_" + dest] = int((df.dataset.eq(dest) & df.routing_step.le(step)).sum())
        entry["cumulative_purchase_retention_pct"] = entry["cumulative_cleaned_purchase_lines"] / n * 100
    ledger_df = pd.DataFrame(ledger)
    ledger_df.to_csv(tables / "sequential_retention.csv", index=False)
    dataset_counts = pd.DataFrame([{"dataset": name, "overlapping_view": False, **counters(df.loc[df.dataset.eq(name)])}
                                   for name in PRIMARY + ["duplicate_audit"]])
    overlay = ~duplicates & df.missing_customer_id
    dataset_counts = pd.concat([dataset_counts, pd.DataFrame([{"dataset": "missing_customer_id", "overlapping_view": True, **counters(df.loc[overlay])},
        {"dataset": "zero_price_review", "overlapping_view": True, **counters(df.loc[~duplicates & df.Price.eq(0)])}])], ignore_index=True)
    dataset_counts.to_csv(tables / "dataset_counts.csv", index=False)
    reasons = df.groupby(["dataset", "decision_reason"]).agg(lines=("source_id", "size"), unique_invoices=("Invoice", "nunique"),
        unique_products=("StockCode", "nunique"), unique_customers=("Customer ID", "nunique")).reset_index()
    reasons.to_csv(tables / "decision_reason_counts.csv", index=False)
    zero_summary = df.loc[~duplicates & df.Price.eq(0)].groupby(["dataset", "decision_reason", "zero_price_evidence"]).size().reset_index(name="lines")
    zero_summary.to_csv(tables / "zero_price_investigation.csv", index=False)
    df.loc[~duplicates].groupby(["dataset", "description_status"]).size().reset_index(name="lines").to_csv(tables / "description_recovery_counts.csv", index=False)
    df.loc[~duplicates].groupby(["StockCode", "description_normalized", "dataset", "decision_reason"], dropna=False).size().reset_index(name="lines").to_csv(tables / "code_description_routing.csv", index=False)
    # Inspect return-review semantics and non-C negatives without collapsing them.
    df.loc[~duplicates & (df.Quantity.lt(0) | df.cancellation_prefix)].groupby(["dataset", "decision_reason", "cancellation_prefix"]).size().reset_index(name="lines").to_csv(tables / "negative_and_cancellation_routing.csv", index=False)
    snapshots = pd.DataFrame([{"scope": name, **counters(df.loc[mask]),
        "C_prefix_lines": int(df.loc[mask, "cancellation_prefix"].sum()),
        "zero_prices": int(df.loc[mask, "Price"].eq(0).sum()),
        "nontext_descriptions": int(df.loc[mask, "nontext_description_raw"].sum()),
        "quantity_outlier_flags": int(df.loc[mask, "quantity_iqr_flag"].sum()),
        "price_outlier_flags": int(df.loc[mask, "price_iqr_flag"].sum())}
        for name, mask in [("original", pd.Series(True, index=df.index)), ("canonical", ~duplicates), ("purchases", purchase)]])
    snapshots.to_csv(tables / "quality_before_after.csv", index=False)
    LOG.info("Routing complete: %s", dict(df.dataset.value_counts()))

    # Record schema and software before exporting. Mixed-type raw fields have
    # sidecars; CSV readers must not infer identifiers or treat literal NA as null.
    schema = {"format": "UTF-8 CSV, gzip compression; empty field means missing in original columns",
              "mixed_original_columns": ["Invoice", "StockCode", "Description"],
              "type_sidecars": ["raw_type_Invoice", "raw_type_StockCode", "raw_type_Description"],
              "row_reference": "source_sheet + source_row (Excel header is row 1); source_id is lineage, not a business ID",
              "columns": {col: str(df[col].dtype) for col in df.columns},
              "read_guidance": "Use pandas read_csv(dtype=str, keep_default_na=False) for lossless lexical inspection; restore mixed original types using raw_type_* sidecars. Numeric Price requires float_precision='round_trip'. InvoiceDate is ISO datetime. Never infer identifiers from CSV without the schema.",
              "overlay_warning": "missing_customer_id and zero_price_review overlap primary datasets; row_audit is a complete index and must not be added to retention totals"}
    (processed / "schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    (processed / "policy.json").write_text(json.dumps({"version": POLICY_VERSION, "operational_codes": OPERATIONAL_CODES,
        "operational_notes_at_zero_price": sorted(OPERATIONAL_NOTES), "ambiguous_notes": sorted(AMBIGUOUS_NOTES),
        "duplicate_policy": "exact eight-column occurrence matching across sheets; keep first sheet's occurrence and any unmatched rows",
        "zero_price_policy": "known positive-price merchandise code/normalized-description pair plus paid merchandise witness in same invoice",
        "description_recovery": "one distinct prior positive-price merchandise description for exact StockCode as of target date",
        "no_imputation": ["Customer ID", "Invoice", "StockCode", "Quantity", "Price"]}, indent=2), encoding="utf-8")
    code_snapshot = reports / "preprocess_dataset_source.py"
    code_snapshot.write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
    exported = []
    seen_primary = set()
    source_lookup = df.set_index("source_id", drop=False)
    def export_validate(name, frame, primary=False):
        path = processed / f"{name}.csv.gz"
        LOG.info("Writing and re-reading %s (%s lines)", name, len(frame))
        frame.to_csv(path, index=False, compression={"method": "gzip", "compresslevel": 1}, date_format="%Y-%m-%dT%H:%M:%S.%f")
        seen = set()
        for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=100000):
            ids = chunk.source_id
            check(f"{name}_chunk_ids_unique_{len(seen)}", ids.is_unique and not bool(seen.intersection(ids)))
            seen.update(ids)
            ref = source_lookup.loc[ids]
            # Every original field is compared with source values after restoring
            # numeric serialization. Also validate all derived/audit columns.
            for col in frame.columns:
                if col in ["InvoiceDate", "product_evidence_date"]:
                    actual = pd.to_datetime(chunk[col].replace("", pd.NA)).reset_index(drop=True)
                    expected_values = pd.to_datetime(ref[col]).reset_index(drop=True)
                    if not ((actual.isna() & expected_values.isna()) | actual.eq(expected_values)).all():
                        raise AssertionError(f"{name}: datetime roundtrip mismatch: {col}")
                else:
                    expected_values = source_text(ref[col]).reset_index(drop=True)
                    if not chunk[col].astype("string").reset_index(drop=True).eq(expected_values).all():
                        raise AssertionError(f"{name}: roundtrip mismatch: {col}")
        check(f"{name}_saved_membership", seen == set(frame.source_id))
        if primary:
            check(f"{name}_disjoint_from_other_partitions", not bool(seen_primary.intersection(seen)))
            seen_primary.update(seen)
        exported.append({"dataset": name, "path": str(path), "lines": len(frame), "sha256": sha256(path), "roundtrip_validated": True})

    for name in PRIMARY + ["duplicate_audit"]:
        export_validate(name, df.loc[df.dataset.eq(name)], primary=True)
    check("saved_primary_partitions_cover_every_source_row", seen_primary == set(df.source_id))
    export_validate("missing_customer_id", df.loc[overlay])
    export_validate("zero_price_review", df.loc[~duplicates & df.Price.eq(0)])
    audit_columns = ["source_id", "source_sheet", "source_row", "dataset", "decision_reason", "exclusion_reason",
                     "routing_step", "retained_source_id", "exact_group", "within_sheet_occurrence", "is_duplicate_copy",
                     "missing_customer_id", "missing_description_raw", "description_status", "description_evidence_source_id",
                     "product_evidence_source_id", "paid_invoice_evidence_source_id", "zero_price_evidence", "policy_version"]
    export_validate("row_audit", df[audit_columns])
    after = sha256(SOURCE)
    check("raw_sha256_unchanged_after_processing_and_export", before == after == expected)
    check("all_rows_preserved_in_partition_or_duplicate_archive", int(dataset_counts.loc[~dataset_counts.overlapping_view, "lines"].sum()) == n)
    (reports / "validation_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    summary = {"run_id": run_id, "policy_version": POLICY_VERSION, "source": str(SOURCE), "sha256_before": before,
               "sha256_after": after, "source_unchanged": before == after, "original_lines": n,
               "canonical_lines": len(canonical_idx), "cross_sheet_copies_archived": len(duplicate_idx),
               "within_source_exact_repeat_occurrences_preserved": int(df.loc[canonical_idx, COLUMNS].duplicated().sum()),
               "cleaned_purchase_lines": int(purchase.sum()), "retention_pct_original": float(purchase.mean() * 100),
               "retention_pct_canonical": float(purchase.sum() / len(canonical_idx) * 100),
               "supported_zero_price_purchases": int(zero_selected.sum()),
               "recovered_descriptions_canonical": int((recover & ~duplicates).sum()),
               "all_checks_passed": all(x["passed"] for x in checks), "validation_check_count": len(checks),
               "datasets": dataset_counts.to_dict("records"), "files": exported,
               "python": sys.version, "pandas": pd.__version__, "numpy": np.__version__,
               "source_code_sha256": sha256(code_snapshot), "phase4_authorized": False}
    (reports / "preprocessing_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (processed / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    # The report explicitly separates measurements, assumptions and unresolved roles.
    report = f"""# Phase 3 preprocessing report

Project: Craft Category Association Discovery Through Clustered Transaction Analysis (INT396).
Members: Aftab Khan and Tej Pratap Singh. Run: `{run_id}`. Policy: `{POLICY_VERSION}`.

## Outcome

Retained **{int(purchase.sum()):,} purchase lines** ({purchase.mean() * 100:.4f}% of {n:,} original lines; {purchase.sum() / len(canonical_idx) * 100:.4f}% of canonical lines). These are source-supported merchandise purchase records under the documented rules, not independently verified delivery/payment events. No synthetic rows, invented identifiers, numerical imputation, outlier removal, winsorization, scaling, model fitting or category mapping was performed. All original business columns remain unchanged.

## Separate outputs and counts

{markdown(dataset_counts)}

Unique counts exclude missing IDs and include recorded stock codes, not verified craft categories. Customers/invoices/products can occur in multiple partitions: only the primary line counts plus duplicate copies are additive. Missing-customer and zero-price datasets are explicitly overlapping diagnostics. `row_audit` contains all {n:,} original source references and is not added to retention totals.

Original {n:,} = canonical {len(canonical_idx):,} + duplicate copies {len(duplicate_idx):,}. Canonical lines are partitioned into the four analytical/review datasets; none is deleted.

## Sequential retention ledger

Each row is the actual execution order. The `lines` column is the remaining unassigned pool, not always the purchase count. Once rows are routed to purchases, they leave this pool and enter the cumulative purchase total. All four identity counts are saved for every step in `sequential_retention.csv` along with cumulative destination totals.

{markdown(ledger_df[['step', 'operation', 'input_lines', 'newly_routed_lines', 'lines', 'unique_invoices', 'unique_products', 'unique_customers', 'cumulative_cleaned_purchase_lines']])}

## Exclusion and retention reasons

{markdown(reasons)}

Every excluded line is present in return review, operational adjustments, unresolved records or duplicate audit with a nonempty exclusion reason. Missing Customer ID, missing Description, bulk quantity and IQR flags are not exclusion criteria. An incomplete record may still be unresolved for a separate documented identity or purchase-context reason.

## Cross-worksheet overlap and repeated purchases

Compared all eight original columns before normalization. Confirmed 22,202 exact cross-sheet groups with matching sheet multiplicities and 22,523 one-to-one occurrence pairs in December 1–9, 2010. Retained first-sheet occurrences and any unmatched records from either sheet. Each archived copy links to its retained original through `retained_source_id`. Exact record values, different source sheets, dates and occurrence multiplicity were validated. The archive represents repeated source coverage, not inferred cancellation of business purchases.

Retained **{summary['within_source_exact_repeat_occurrences_preserved']:,}** exact repeat occurrences inside the canonical source. No blanket `drop_duplicates` or Invoice + StockCode deduplication was applied. Composite-key and multiple-timestamp invoice review tables are supplied; multiple timestamps were not automatically split into new invoices. No invoice has conflicting known customers or countries. Basket feature construction remains deferred.

## Zero-price investigation

All **{int((~duplicates & df.Price.eq(0)).sum()):,}** canonical zero-price lines were investigated and exported in `zero_price_review`. Operational entries were identified from reviewed code/description evidence, never from price alone. For potential merchandise, checked a matching product/normalized-description pair observed on actual positive-price merchandise lines and a positive-price merchandise witness in the same invoice. This criterion does not require Customer ID.

Retained **{int(zero_selected.sum()):,}** supported zero-price merchandise lines with unchanged zero price and explicit evidence references. They are eligible for presence-based purchase analysis; `purchase_value_eligible=False` distinguishes them from positive-price value observations. The data do not establish whether these were free gifts, promotions or missing charges. Remaining cases retain their original records and reasons for review; a zero price was not imputed.

{markdown(zero_summary)}

Product-context evidence may use another observed transaction from the complete descriptive dataset; temporal modeling must rebuild such evidence inside the chosen development window. Description *recovery*, in contrast, uses only observations at or before the target date and does not borrow a later description.

## Returns and operational entries

`return_review` is a review dataset, not a count of confirmed physical returns. C-prefix merchandise lines are marked cancellation/return candidates without asserting links to original sales. Non-C negatives are explicitly labeled for return-versus-inventory review. Reviewed operational notes/codes are routed separately before sign handling, so fee reversals are not called merchandise returns. Ambiguous Manual entries are unresolved. Source signs remain unchanged; no return is netted against a purchase automatically.

Operational reasons are narrow, versioned rules derived from reviewed source descriptions: postage, carriage, discounts, charges/fees, samples, bad debt, tests, vouchers and explicit zero-price inventory/operational notes. Atypical code format alone is never an exclusion rule; legitimate atypical merchandise codes remain eligible when supported. Ambiguous CHECK/unknown notes are not automatically asserted to be stock adjustments.

## Data quality and recovery

{markdown(snapshots)}

Description normalization creates separate fields (trim, whitespace collapse, uppercase), retaining original Description and its original type. Recovered **{int((recover & ~duplicates).sum()):,}** canonical missing/nontext descriptions only when the exact StockCode had one distinct usable merchandise description observed by that timestamp. Each recovery links to its source record; conflicting/no-prior evidence remains Unknown. Recovery does not turn an operational or unsupported zero-price event into a purchase. There is no craft-category assignment.

Quantity and Price had no missing source values; no numerical imputer was needed. Customer IDs and invoice IDs remain untouched. IQR flags are retained for later investigation without removing legitimate large purchases. No feature transforms were applied in this phase.

## Validation and reproducibility

All **{len(checks):,}** recorded checks passed. Every saved CSV was re-read in chunks and every saved field compared against the in-memory source/derived values. Saved partition membership is unique, disjoint and exhaustive across all original rows; overlapping diagnostics are validated separately. Checks include original-column preservation, duplicate equality/multiplicity, zero-price evidence, purchase sign/prefix rules, invoice consistency, description chronology and complete exclusion reasons.

Raw SHA-256 before and after: `{after}` (identical to Phase 1 manifest). Output SHA-256 values, schema, software versions, source-code snapshot hash and policy are saved in the manifests. CSVs are gzip-compressed, not sampled. Type sidecars preserve mixed source-column types; use `schema.json` rather than automatic CSV type inference. Empty original cells remain missing. Raw data were not uploaded or modified.

Run `.venv\\Scripts\\python.exe src\\preprocess_dataset.py` to reproduce into a new timestamped directory. Reports/tables are local. Input workbook checksum changes stop processing. Unit fixtures are synthetic test cases only, never analytical records or retention inputs.

Datasets: `{processed.relative_to(ROOT).as_posix()}`.
Tables: `{tables.relative_to(ROOT).as_posix()}`.
Reports and validation: `{reports.relative_to(ROOT).as_posix()}`.

## Limitations and next phase

Transaction roles are evidence-based data preparation, not proof of physical goods transfer. Zero-price semantics, ambiguous notes and non-C negative transactions remain explicitly qualified. Same-sheet exact repeats are preserved because the workbook supplies no line IDs establishing that they are accidental duplicates. Description recovery is contextual and unambiguous within observed prior history, not external verification. The original dataset is general retail/giftware, not verified handicraft-only data.

Phase 3 is complete. **Stop and obtain explicit approval before Phase 4 product/category mapping.** No K-Means, Apriori or dashboard was implemented.
"""
    (reports / "preprocessing_report.md").write_text(report, encoding="utf-8")
    doc = ROOT / "docs" / f"preprocessing_report_{run_id}.md"
    doc.write_text(report, encoding="utf-8")
    LOG.info("COMPLETE: %s", doc)
    print(json.dumps({"report": str(doc), "processed_directory": str(processed), "summary": str(reports / "preprocessing_report.json"),
                      "purchase_lines": int(purchase.sum()), "checks_passed": len(checks)}, indent=2))


if __name__ == "__main__":
    run()
