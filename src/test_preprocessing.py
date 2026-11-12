"""Synthetic unit fixtures only. These are never exported as transaction data."""
import unittest
import pandas as pd
from preprocess_dataset import exact_occurrence_links, normalize_description, operational_reasons


def sample(sheet, qty=1, price=2.5, description="TEST FIXTURE MUG", invoice=1, stock="10001"):
    return {"Invoice": invoice, "StockCode": stock, "Description": description,
            "Quantity": qty, "InvoiceDate": pd.Timestamp("2010-12-02"), "Price": price,
            "Customer ID": float("nan"), "Country": "TEST_FIXTURE", "source_sheet": sheet}


class PreprocessingRules(unittest.TestCase):
    def test_equal_multiplicity_retains_repeated_source_lines(self):
        df = pd.DataFrame([sample("A"), sample("A"), sample("B"), sample("B")])
        _, _, copies, links = exact_occurrence_links(df)
        self.assertEqual(copies.tolist(), [False, False, True, True])
        self.assertEqual(links.tolist(), [0, 1, 0, 1])

    def test_unequal_multiplicity_retains_extra_occurrence(self):
        df = pd.DataFrame([sample("A"), sample("B"), sample("B")])
        _, _, copies, _ = exact_occurrence_links(df)
        self.assertEqual(copies.tolist(), [False, True, False])

    def test_price_quantity_differences_are_not_duplicates(self):
        df = pd.DataFrame([sample("A"), sample("B", price=3), sample("B", qty=2)])
        self.assertFalse(exact_occurrence_links(df)[2].any())

    def test_normalization_preserves_numbers_punctuation_and_raw(self):
        raw = pd.Series(["  Set/2   cups.  ", 123, None])
        result = normalize_description(raw)
        self.assertEqual(result.iloc[0], "SET/2 CUPS.")
        self.assertTrue(result.iloc[1:].isna().all())
        self.assertEqual(raw.iloc[0], "  Set/2   cups.  ")

    def test_zero_price_alone_is_not_operational(self):
        df = pd.DataFrame([sample("A", price=0), sample("A", price=0, description="DAMAGED"),
                           sample("A", price=0, description="CHECK"), sample("A", stock="PADS"),
                           sample("A", stock="M", description="Manual"), sample("A", stock="POST", description="POSTAGE")])
        df["description_normalized"] = normalize_description(df.Description)
        self.assertEqual(operational_reasons(df).tolist(), ["", "explicit_zero_price_operational_note", "", "", "", "postage"])


if __name__ == "__main__":
    unittest.main()
