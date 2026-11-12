"""Phase 4 inventory only; reads Phase 3 purchase lines without changing them."""
import logging
from pathlib import Path
import pandas as pd
from inspect_dataset import ROOT, sha256

PURCHASE = ROOT / "data/processed/phase3_20261111_232629/cleaned_purchase_lines.csv.gz"


def inventory():
    df = pd.read_csv(PURCHASE, usecols=["StockCode", "Description", "description_normalized", "Invoice",
        "Quantity", "source_id", "raw_type_StockCode"], dtype=str, keep_default_na=False)
    assert len(df) == 1015214
    assert df.StockCode.nunique() == 4896
    assert df.groupby("StockCode").raw_type_StockCode.nunique().max() == 1, "Lexical stock-code collision"
    variants = df.groupby(["StockCode", "Description", "description_normalized"], sort=False).agg(
        purchase_lines=("Invoice", "size"), unique_invoices=("Invoice", "nunique"),
        example_source_id=("source_id", "first")).reset_index()
    products = df.groupby("StockCode", sort=False).agg(purchase_lines=("Invoice", "size"),
        unique_invoices=("Invoice", "nunique"), original_description_count=("Description", "nunique"),
        normalized_description_count=("description_normalized", "nunique"), stockcode_original_type=("raw_type_StockCode", "first")).reset_index()
    return variants, products


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    variants, products = inventory()
    folder = ROOT / ".cache/phase4_inventory"
    folder.mkdir(parents=True, exist_ok=True)
    variants.to_csv(folder / "description_inventory.csv", index=False)
    products.to_csv(folder / "product_inventory.csv", index=False)
    print(products.sort_values("purchase_lines", ascending=False).head(35).to_string(index=False))
    print("Description variants:", len(variants), "Multiple original descriptions:", products.original_description_count.gt(1).sum())
    print("Source SHA256:", sha256(PURCHASE))
