"""Phase 3 read-only diagnostics used to review routing policies, not a cleaner."""
import logging
from pathlib import Path
import pandas as pd
from inspect_dataset import SOURCE, SHEETS, COLUMNS, sha256

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    out = Path(__file__).resolve().parents[1] / ".cache" / "phase3_investigation"
    out.mkdir(parents=True, exist_ok=True)
    parts = []
    for sheet in SHEETS:
        part = pd.read_excel(SOURCE, sheet_name=sheet, engine="openpyxl", keep_default_na=False, na_values=[""])
        part["source_sheet"] = sheet
        part["source_row"] = range(2, len(part) + 2)
        parts.append(part)
        logging.info("Loaded %s", sheet)
    df = pd.concat(parts, ignore_index=True)
    df["desc_norm"] = df.Description.where(df.Description.map(lambda v: isinstance(v, str))).astype("string").str.strip().str.replace(r"\s+", " ", regex=True).str.upper()
    df["stock_text"] = df.StockCode.astype("string")
    df["cancel"] = df.Invoice.astype("string").str.match(r"(?i)^C", na=False)
    # Occurrence-matched, exact eight-column comparison for overlap investigation only.
    group = df.groupby(COLUMNS, dropna=False, sort=False).ngroup()
    occ = df.groupby([group, df.source_sheet], sort=False).cumcount()
    copy = pd.DataFrame({"group": group, "occ": occ}).duplicated()
    canonical = df.loc[~copy]
    zero = canonical.loc[canonical.Price.eq(0)]
    zero.groupby(["StockCode", "desc_norm"], dropna=False).agg(
        rows=("Invoice", "size"), positive_qty=("Quantity", lambda s: (s > 0).sum()),
        negative_qty=("Quantity", lambda s: (s < 0).sum()),
        known_customer=("Customer ID", "count")).reset_index().sort_values("rows", ascending=False).to_csv(out / "zero_price_groups.csv", index=False)
    zero[zero.Quantity.gt(0) & zero["Customer ID"].notna()].to_csv(out / "zero_price_positive_known_customer.csv", index=False)
    # Review all description text on non-C negative or nonpositive-price entries.
    suspect = (~canonical.cancel & canonical.Quantity.lt(0)) | canonical.Price.le(0)
    canonical.loc[suspect].groupby("desc_norm", dropna=False).agg(
        rows=("Invoice", "size"), codes=("StockCode", "nunique"),
        min_qty=("Quantity", "min"), max_qty=("Quantity", "max"), min_price=("Price", "min"), max_price=("Price", "max")
    ).reset_index().sort_values("rows", ascending=False).to_csv(out / "suspect_descriptions.csv", index=False)
    atypical = ~canonical.stock_text.str.fullmatch(r"\d{5}[A-Za-z]*", na=False)
    canonical.loc[atypical].groupby(["StockCode", "desc_norm"], dropna=False).size().reset_index(name="rows").sort_values("rows", ascending=False).to_csv(out / "atypical_codes.csv", index=False)
    print({"canonical_rows_if_reconciled": len(canonical), "copies": int(copy.sum()), "zero_price_rows": len(zero), "sha256": sha256(SOURCE)})

if __name__ == "__main__":
    main()
