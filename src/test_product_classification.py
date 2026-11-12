"""Context regression tests; descriptive fixtures are not transaction records."""
import unittest
from classify_products import classify_description, RULES, UNKNOWN


class ContextTests(unittest.TestCase):
    def test_object_over_design(self):
        examples = {
            'CROCHET FOOD COVER': 'Kitchen & Tableware',
            'BUTTONS DESIGN JEWELLERY BOX': 'Storage & Household Accessories',
            'RUBY DROP CHANDELIER EARRINGS': 'Jewellery & Personal Accessories',
            'BIRD HOUSE HOT WATER BOTTLE': 'Textiles & Soft Furnishings',
            'MONEY BOX FIRST AID DESIGN': 'Storage & Household Accessories',
            'CARD HOLDER GINGHAM HEART': 'Storage & Household Accessories',
            'S/6 WOODEN SKITTLES IN COTTON BAG': 'Toys, Games & Novelty Items',
            'CHRISTMAS MUG W GIFT BOX': 'Kitchen & Tableware',
            'BIRD GARDEN DESIGN MUG': 'Kitchen & Tableware',
            'FELTCRAFT HAIRBAND': 'Jewellery & Personal Accessories',
            'SCARF KNITTING KIT': 'Craft & Sewing Supplies',
            'PORCELAIN BUTTERFLY OIL BURNER': 'Home Decor & Lighting',
        }
        for text, category in examples.items():
            with self.subTest(text=text):
                self.assertEqual(classify_description(text)[0], category)

    def test_insufficient_evidence_stays_unknown(self):
        for text in ['FELTCRAFT 6 FLOWER FRIENDS', 'VINTAGE SILVER SHAPE', 'HANDMADE', 'SET OF 3 BIRD LIGHT PINK FEATHER']:
            with self.subTest(text=text):
                self.assertEqual(classify_description(text)[:2], (UNKNOWN, 'Low'))

    def test_rule_ids_and_categories(self):
        self.assertEqual(len(RULES), len({r[0] for r in RULES}))
        self.assertNotIn('DUMMY', {r[2] for r in RULES})


if __name__ == '__main__':
    unittest.main()
