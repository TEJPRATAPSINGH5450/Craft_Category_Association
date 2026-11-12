"""Auditable description-only Phase 4 mapping, separate from all purchase files.

No learned text features, product categories in transaction files, or ML models.
"""
import argparse
from datetime import datetime
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
from build_product_inventory import inventory, PURCHASE
from inspect_dataset import ROOT, sha256, markdown

VERSION = "description-taxonomy-v1"
UNKNOWN = "Other/Unclassified"
# Priority encodes phrase specificity, not sales popularity. All matches are
# retained in the evidence table; tied different categories remain unresolved.
RULES = [
    ("CX01", 155, "Paper & Stationery", r"\b(?:PURSE NOTEBOOK|PARTY INVITES|SHOPPING LIST|CALCULATOR|CALENDAR|EXERCISE BOOKS|NOTE BOOKS|ERASERS|ENVELOPES?)\b|^CARD\b(?! HOLDER)", "High"),
    ("CX02", 155, "Textiles & Soft Furnishings", r"\b(?:HOT WATER BOTTLE|BABY BIB)\b", "High"),
    ("CX03", 155, "Garden & Outdoor Accessories", r"\b(?:GARDEN FORK|GARDEN TROWEL|PLANT POT HOLDER|WASP CATCHER|POTTING SHED TWINE)\b", "High"),
    ("CX04", 155, "Jewellery & Personal Accessories", r"\b(?:CHANDELIER EARRINGS|HAIRBANDS|HAIRBAND|RAIN PONCHO)\b", "High"),
    ("CX05", 155, "Storage & Household Accessories", r"\b(?:JEWELLERY STAND|JEWELLERY BOX|JEWEL BOX|STACKING TINS|WALL TIDY|DOLLY PEGS|STORAGE CUBES|ORGANISER|ORGANIZER|MAGAZINE RACK|DRAWERKNOB|DRAWERKNOBS|DRESSING TABLE POT|MONEY BOX|TAPE MEASURE)\b", "High"),
    ("X01", 125, "Bath & Personal Care Accessories", r"\b(?:POCKET WARMER|BOTTLE PERFUME)\b", "High"),
    ("X02", 125, "Garden & Outdoor Accessories", r"\bHERB MARKER\b", "High"),
    ("X03", 125, "Bags & Carry Accessories", r"\b(?:WASHBAG|TRAVELING FAN|SANDALWOOD FAN)\b", "High"),
    ("X04", 125, "Home Decor & Lighting", r"\bOIL BURNER\b", "High"),
    ("X05", 125, "Craft & Sewing Supplies", r"\bSHIRT REPAIR KIT\b", "High"),
    ("X06", 125, "Toys, Games & Novelty Items", r"\bNAUGHTS.*CROSSES\b", "High"),
    ("X07", 120, "Gift Packaging & Party Supplies", r"\bGIFT WRAPS\b", "High"),
    ("X08", 120, "Home Decor & Lighting", r"\b(?:LANTERNS|TABLE LIGHT)\b", "High"),
    ("CX06", 155, "Toys, Games & Novelty Items", r"\b(?:SKITTLES IN COTTON BAG|BEACH SPADE|TRANSFER TATTOOS)\b", "High"),
    ("CX07", 145, "Craft & Sewing Supplies", r"\b(?:MAKE YOUR OWN.*CARD KIT|(?:FELTCRAFT|DOLLCRAFT).*KIT|WOOD STAMP SET|IRON ON PATCHES|SEW ON CROCHET FLOWERS)\b", "High"),
    ("K05", 125, "Kitchen & Tableware", r"\b(?:BREAKFAST SET|ICE LOLLY|SUGAR DISPENSER|LADLE|CHOPSTICKS|BEAKERS|SCRUBBING BRUSH)\b", "High"),
    ("B04", 125, "Bags & Carry Accessories", r"\b(?:BOTTLE BAG|WEEKEND BAG)\b", "High"),
    ("D05", 125, "Home Decor & Lighting", r"\b(?:WOODEN BLOCK LETTERS|PHOTO ALBUM|TORCH|TUBE MATCHES|BOX MATCHES)\b", "High"),
    ("S04", 105, "Seasonal & Celebration Decorations", r"\bTINSEL\b", "High"),
    ("K03", 125, "Kitchen & Tableware", r"\b(?:COOKIE CUTTERS?|BISCUIT CUTTERS?|JAM MAKING SET|JELLY MOULDS?|TEA GLASS|DRINKING STRAWS?|BENDY STRAWS|MILK BOTTLES?|EGG HOUSE|JAM JAR|COFFEE CONTAINER|TEA COFFEE SUGAR TINS|WASHING UP BRUSH)\b", "High"),
    ("P03", 125, "Paper & Stationery", r"\b(?:NOTEBOOKS|NOTEPADS|WRITING SET|ADDRESS BOOKS|STICKY NOTES|STICKY NOTE|NOTELETS|PAPERWEIGHT|PAPER WEIGHT|PEN HOLDER|PENCIL SHARPENER)\b", "High"),
    ("C02", 125, "Craft & Sewing Supplies", r"\b(?:COLOURING SET|COLORING SET|CRAYONS|MODELLING CLAY|MODELING CLAY|PAINT SET|STENCIL|CRAFT SCISSORS|SEWING SCISSORS|FLOWER PRESS)\b", "High"),
    ("T03", 125, "Toys, Games & Novelty Items", r"\b(?:SPINNING TOPS?|SNAKES.*LADDERS|CROQUET|ROUNDERS|PLAYHOUSE|DOLLS HOUSE|DOLL HOUSE|DOLLHOUSE|SANDCASTLE|SEASIDE BUCKET|SAND BUCKET)\b", "High"),
    ("D04", 120, "Home Decor & Lighting", r"\b(?:SIGNS?|CHOCOLATECANDLE|DOOR CHIMES|WINDCHIME|WINDCHIMES|CANDLESTICKS|CANDLEHOLDERS|BIRD ORNAMENT)\b", "High"),
    ("O03", 120, "Storage & Household Accessories", r"\b(?:TRINKET POTS?|MONEY BANK|MINI CHEST|BLACK BOARD|BLACKBOARD|WASHING UP GLOVES|MARKET CRATES|STORAGE CRATES|DRAWER KNOBS|DOOR KNOBS)\b", "High"),
    ("B02", 120, "Bags & Carry Accessories", r"\b(?:PICNIC BAG|OVERNIGHT BAG|BACK PACK|COSMETICS BAG|COTTON BAG|COTTON BAGS|TRAVEL BAG|TOILETRY BAG|SUITCASE)\b", "High"),
    ("J03", 120, "Jewellery & Personal Accessories", r"\b(?:KEY FOB|KEYRINGS|KEY RINGS|SILK FAN|HAIR TIE|HAIR ELASTIC|HAIRCLIP)\b", "High"),
    ("A02", 120, "Bath & Personal Care Accessories", r"\b(?:FLANNEL|FACE CLOTH|BATH PUFF|BATH DUCK|BATHROOM SET|LIP GLOSS|LIPGLOSS|LIP BALM|LIPBALM|SHOWER GEL|BATH OIL)\b", "High"),
    ("G02", 120, "Garden & Outdoor Accessories", r"\b(?:KNEELING PAD|PLANT LADDER|PLANT HOLDER|GARDEN BENCH|HAMMOCK|GROW A FLYTRAP|GROW A SUNFLOWER|GROW YOUR OWN|PLANT MARKER)\b", "High"),
    ("W02", 116, "Gift Packaging & Party Supplies", r"\b(?:PARTY BAGS?|ROLL WRAP|GIFT WRAPPING|CONFETTI)\b", "High"),
    ("W03", 95, "Gift Packaging & Party Supplies", r"\bGIFT BOX(?:ES)?\b", "Medium"),
    ("S03", 105, "Seasonal & Celebration Decorations", r"\b(?:CHRISTMAS|XMAS|EASTER|HALLOWEEN)\b.*\bDECS\b", "High"),
    ("K04", 95, "Kitchen & Tableware", r"\bDOILIES\b", "Medium"),
    ("B03", 95, "Bags & Carry Accessories", r"\bPARASOL\b", "Medium"),
    ("D01", 120, "Home Decor & Lighting", r"\b(?:T[ -]?LIGHT|TEA[ -]?LIGHT|CANDLE(?:S|STICK|HOLDER)?|CANDLE PLATE|FAIRY LIGHTS|NIGHT[ -]?LIGHT|NIGHT LIGHTS|LAMPS?\b|LAMPSHADE|LANTERN|CHANDELIER|PHOTO FRAME|PICTURE FRAME|PHOTO CLIP|METAL SIGN|DOOR\s?SIGN|WALL MIRROR|WALL CLOCK|ALARM CLOCK|DINER CLOCK|BOUDOIR CLOCK)\b", "High"),
    ("T01", 120, "Toys, Games & Novelty Items", r"\b(?:PLAYING CARDS|SNAP CARDS|CARD GAME|MAGIC DRAWING|SOFT TOY|JIGSAW|PUZZLE|SKITTLES|DOMINOES|BINGO|LUDO|MARBLES|YO[ -]?YO|GLIDERS?|HELICOPTER|WIND[ -]?UP|JUMPING|SKIPPING ROPE|FLYING DISC|KALEIDOSCOPE|HARMONICA|TOY\b|TOYS\b)\b", "High"),
    ("J01", 120, "Jewellery & Personal Accessories", r"\b(?:NECKLACE|NECKL\b|BRACELET|BANGLE|EARRINGS?|BROOCH|HAIRBAND|HAIR BAND|HAIR CLIP|HAIR GRIP|HAIR SLIDE|HAIR COMB|PHONE CHARM|BAG CHARM|KEYRING|KEY RING|KEY[ -]?CHAIN|CUFFLINKS?|CORSAGE|SCARF|SCARVES|TIARA)\b", "High"),
    ("C01", 130, "Craft & Sewing Supplies", r"\b(?:KNITTING KIT|SEWING KIT|CROCHET KIT|CRAFT KIT|SEWING|KNITTING|THIMBLE|NEEDLE CASE|PIN CUSHION|PINCUSHION|SPOOL|RIBBON REEL|BUTTON BOX|EMBROIDERY KIT)\b|\bRIBBONS$", "High"),
    ("C03", 130, "Craft & Sewing Supplies", r"^(?:SET OF |S/)?\d+ (?:RAFFIA )?RIBBONS\b", "High"),
    ("P01", 115, "Paper & Stationery", r"\b(?:NOTEBOOK|NOTE BOOK|NOTEPAD|NOTE PAD|PENCIL|PENCILS|PENCIL CASE|PENS?|STICKERS?|EXERCISE BOOK|ADDRESS BOOK|JOURNAL|DIARY|SCRAP\s?BOOK|WRITING SET|STATIONERY|ERASER|RUBBER|CHALK|RULER|BOOKMARK|BOOK MARK|BIRTHDAY CARD|GREETING CARD|CHRISTMAS CARD|POSTCARD|PARTY INVITES)\b", "High"),
    ("K01", 115, "Kitchen & Tableware", r"\b(?:MUGS?|TEAPOT|TEA POT|TEACUP|TEA CUP|SAUCER|TEA SET|TEASET|CAKE\s?STAND|CAKE CASES|BAKING|COOKIE CUTTER|BISCUIT CUTTER|COOKIECUTTER|CAKE TINS?|CAKE TIN|CAKE MOULD|CAKE MOLD|FOOD COVER|EGG CUP|EGGCUP|EGG HOLDER|EGG BASKET|EGG WARMER|EGG COSY|CUP WARMER|COASTERS?|PLACEMATS?|PLACE MAT|NAPKINS?|NAPKIN CHARMS?|NAPKIN RING|NAPKIN HOLDER|PLACE SETTINGS?|CUTLERY|FORKS?|SPOONS?|TEASPOONS?|MILK JUG|WATER JUG|CREAM JUG|CREAMER|SUGAR BOWL|SUGAR JAM BOWL|BUTTER DISH|BUTTERDIS[H]?|KITCHEN SCALES|KITCHEN SCALE|SALT|PEPPER|LUNCH BOX|LUNCHBOX|SNACK BOX|BREAD BIN|TEA CADDY|TEA TIN|RECIPE BOX|RECIPE BOOK|RECIPE HOLDER|COFFEE CADDY|BISCUIT TIN|POP\s?CORN HOLDER|SANDWICH BOX|BOTTLE OPENER|CORKSCREW|COCKTAIL PARASOLS?|ICE CUBE|ICE CREAM CUP|DRINKING GLASS|WINE GLASS|CHAMPAGNE GLASS|TUMBLER)\b", "High"),
    ("B01", 115, "Bags & Carry Accessories", r"\b(?:LUNCH BAG|SHOPPING BAG|SHOPPER|CHARLOTTE BAG|JUMBO BAG|JUMBO STORAGE BAG|JUMBO STORAGEBAG|RECYCLING BAG|AIRLINE BAG|WASH BAG|COSMETIC BAG|MAKE[ -]?UP BAG|SHOULDER BAG|HANDBAG|TOTE BAG|BACKPACK|PURSE|WALLET|UMBRELLA|RAIN HAT|PASSPORT COVER|LUGGAGE TAG|LUGGAGE LABEL)\b", "High"),
    ("H01", 115, "Textiles & Soft Furnishings", r"\b(?:TEA TOWEL|TEATOWEL|TOWELS?|APRON|CUSHION|CUSHIONS|CUSHIONCOVER|SQUARECUSHION|C/COVER|DOORMAT|DOOR MAT|TABLECLOTH|TABLE CLOTH|THROW|BLANKET|RUG|FILLER PAD|OVEN GLOVE|OVEN MITT|POT HOLDER|POTHOLDER|TEA COSY|TEA COZY|HOT WATER BOTTLE|HOT WATER BOTT|DRAUGHT EXCLUDER|LAUNDRY BAG|PEG BAG|PADS TO MATCH ALL CUSHIONS)\b", "High"),
    ("A01", 115, "Bath & Personal Care Accessories", r"\b(?:PLASTERS|HAND WARMER|HANDWARMER|SOAP|SOAP DISH|SOAPDIS[H]?|TOOTHBRUSH|BATH SALTS|BATH SPONGE|BATH FIZZ|BATH BOMB|SHOWER CAP|SHOE SHINE|SEWING REPAIR|NAIL FILE|NAIL BRUSH|MANICURE|EMERY BOARD|COMPACT MIRROR|POCKET MIRROR|TISSUES?|TISSUE BOX|FIRST AID|PILL BOX|PILLBOX)\b", "High"),
    ("G01", 115, "Garden & Outdoor Accessories", r"\b(?:WATERING CAN|BIRD\s?HOUSE|BIRD FEEDER|BIRDFEEDER|PLANTER|FLOWER POT|FLOWERPOT|GARDEN THERMOMETER|GARDEN TOOLS|GARDEN TROWEL|GARDEN FORK|GARDEN SPADE|GARDEN BRUSH|GARDEN GLOVES|SECATEURS|WHEELBARROW|PLANT POT|GROW YOUR OWN|PICNIC BASKET|GARDEN TABLE|WROUGHT IRON TABLE|BIRD BATH)\b", "High"),
    ("E01", 115, "Pet Accessories", r"\b(?:DOG BOWL|CAT BOWL|DOGS COLLAR|DOG COLLAR|DOGS NIGHT COLLAR|DOG LEAD|DOGS LEAD|DOG HOODIE|CAT COLLAR|DOG FOOD|CAT FOOD)\b", "High"),
    ("W01", 115, "Gift Packaging & Party Supplies", r"\b(?:WRAPPING PAPER|GIFT WRAP|GIFT BAG|GIFTBAG|GIFT TAG|GIFT TAGS|PARTY BAG|PAPER BAG|PAPER BAGS|BALLOONS?|BALLOON PUMP|PARTY CONES|PARTY HATS|PARTY POPPER|CAKE DECORATIONS|CAKE TOPPER)\b|^WRAP\b|\bWRAP$", "High"),
    ("O01", 110, "Storage & Household Accessories", r"\b(?:TRINKET BOX|JEWELLERY BOX|JEWELRY BOX|JEWEL BOX|KNICK KNACK|CHEST OF DRAWERS|DRAWER LINERS|DRAW LINERS|DRAWER LINER|B'DRAW LINERS|SHELF|SHELVES|STORAGE BOX|STORAGE TIN|STORAGE JAR|STORAGE BASKET|STORAGE BIN|BASKET SET|UMBRELLA STAND|COAT HOOK|KEY CABINET|KEY HOLDER|CLOTHES PEGS|HANGERS?|WASTE BIN|DUSTPAN|DUST PAN|DOORSTOP|DOOR STOP|DOOR KNOB|DRAWER KNOB|DRAWER HANDLE|DOOR HANDLE|FURNITURE KNOB|MONEY BOX|PIGGY BANK|BOOKENDS?|BOOK ENDS|CARD HOLDER|CARDHOLDER|LETTER HOLDER|LETTER RACK|MEMO HOLDER|MEMOBOARD|MEMO BOARD|NOTICEBOARD|CHALKBOARD|CHALK BOARD|BAR STOOL)\b", "High"),
    ("S01", 105, "Seasonal & Celebration Decorations", r"\b(?:BUNTING|GARLAND|PAPER CHAIN|CHRISTMAS TREE|XMAS TREE|CHRISTMAS DECORATIONS?|XMAS DECORATIONS?|CHRISTMAS.*(?:HANGING|FAIRY|ORNAMENT|STAR)|(?:HANGING|STAR).*CHRISTMAS|ADVENT|BAUBLES?|WREATH|CHRISTMAS STOCKING|EASTER.*DECORATION|PARTY DECORATION)\b", "High"),
    ("D02", 100, "Home Decor & Lighting", r"\b(?:ORNAMENT|DECORATIONS?|DECORATIVE|VASES?|WALL ART|WALL HANGING|BUILDING BLOCK WORD|WOOD LETTERS|WOODEN LETTERS|ARTIFICIAL FLOWER|ARTIFICIAL.*FLOWER|FAKE.*FLOWER|HANGING HEART|HEART OF WICKER|WICKER HEART|POT POURRI|POTPOURRI|SCENTED.*HEART|INCENSE|FRIDGE MAGNET|MAGNETS?|PICTURE|PHOTO|FRAMES?|MIRRORS?|CLOCKS?|LAMPS?|LIGHTS|CANVAS|SCULPTURE|DOOR CHIME|WIND CHIME|SUNCATCHER)\b", "High"),
    ("K02", 90, "Kitchen & Tableware", r"\b(?:BOWLS?|PLATES?|JUGS?|CUPS?|TRAYS?|DISH|DISHE[ S]|COLANDER|STRAINER|SIEVE|ROLLING PIN|SPATULA|WHISK|KITCHEN|COOKING|CASSEROLE|SAUCEPAN|MILK PAN|FRYING PAN|PIZZA CUTTER|SCOOP|BOTTLE STOPPER|TOAST RACK|SPOON REST|SPOONREST)\b", "Medium"),
    ("O02", 85, "Storage & Household Accessories", r"\b(?:BOXES|BOX|TINS?|JARS?|BASKETS?|HOOKS?|CABINET|CONTAINER|HOLDALL|BROOM|BIN|HAT STAND|COAT RACK)\b", "Medium"),
    ("P02", 85, "Paper & Stationery", r"^CARD\b|\b(?:CARDS|ENVELOPES|MEMO|POSTAGE STAMP)\b", "Medium"),
    ("J02", 85, "Jewellery & Personal Accessories", r"\b(?:RING|RINGS|JEWELLERY|JEWELRY|CHARM|BELT|HAIR|SCARF|WATCH)\b", "Medium"),
    ("T02", 85, "Toys, Games & Novelty Items", r"\b(?:GAME|GAMES|DOLL|DOLLS|TEDDY|TEDDIES|KITE|GLOBE|BALL|RATTLE|WINDMILL|BUBBLES|SPINNING TOP|BOUNCING|SQUEAK|WATER PISTOL|TOYBOX|JOKE|BREATH-A-LOSER)\b", "Medium"),
    ("S02", 80, "Seasonal & Celebration Decorations", r"\b(?:CHRISTMAS|XMAS|EASTER|HALLOWEEN|SANTA|SNOWMAN)\b", "Medium"),
    ("D03", 75, "Home Decor & Lighting", r"\b(?:HANGING|HEART ON STICK|BELL|BELLS|FINIAL|T-LIGHT\s?HOLD|T-LIGHT.*HLDR|HURRICANE|CANDLEABRA|CANDELABRA|DREAMCATCHER)\b", "Medium"),
]

MATERIAL_RULES = {
    "Ceramic/porcelain": r"\b(?:CERAMIC|CERAMICS|PORCELAIN|BONE CHINA|CHINA)\b",
    "Wood": r"\b(?:WOOD|WOODEN|BAMBOO)\b",
    "Textile/fibre": r"\b(?:COTTON|FABRIC|TEXTILE|FELT|FELTCRAFT|KNITTED|WOOL|LINEN|POLYESTER|SILK|CROCHET|CHENILLE)\b",
    "Metal": r"\b(?:METAL|ZINC|TIN|IRON|STEEL|ALUMINIUM|ALUMINUM|BRASS)\b",
    "Glass": r"\bGLASS\b",
    "Paper/card": r"\b(?:PAPER|CARDBOARD)\b",
    "Wicker/rattan": r"\b(?:WICKER|RATTAN)\b",
    "Plastic/acrylic": r"\b(?:PLASTIC|ACRYLIC|BAKELITE)\b",
    "Slate/stone": r"\b(?:SLATE|STONE|MARBLE)\b",
    "Enamel coating (base unspecified)": r"\bENAMEL\b",
}


def classify_description(text):
    hits = [{"rule_id": key, "priority": priority, "category": category, "confidence": conf,
             "matched_text": match.group()} for key, priority, category, pattern, conf in RULES
            if (match := re.search(pattern, text))]
    if not hits:
        return UNKNOWN, "Low", "No sufficiently specific product-function phrase", hits
    top = max(h["priority"] for h in hits)
    winners = [h for h in hits if h["priority"] == top]
    if len({h["category"] for h in winners}) > 1:
        return UNKNOWN, "Low", "Competing equally specific category evidence", hits
    chosen = winners[0]
    return chosen["category"], chosen["confidence"], f"{chosen['rule_id']}: explicit phrase '{chosen['matched_text']}'", hits


def build(preview=False):
    source_before = sha256(PURCHASE)
    cache = ROOT / ".cache/phase4_inventory"
    cache.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((PURCHASE.parent / "manifest.json").read_text(encoding="utf-8"))
    expected = next(f['sha256'] for f in source_manifest['files'] if f['dataset'] == 'cleaned_purchase_lines')
    assert source_before == expected, 'Phase 3 purchase file changed'
    if (cache / 'description_inventory.csv').exists() and (cache / 'product_inventory.csv').exists():
        variants = pd.read_csv(cache / 'description_inventory.csv', dtype={'StockCode': str}, keep_default_na=False)
        products = pd.read_csv(cache / 'product_inventory.csv', dtype={'StockCode': str}, keep_default_na=False)
        assert variants.purchase_lines.sum() == products.purchase_lines.sum() == 1015214
        assert len(products) == 4896 and products.StockCode.is_unique
        assert variants.groupby('StockCode').purchase_lines.sum().sort_index().equals(products.set_index('StockCode').purchase_lines.sort_index())
    else:
        variants, products = inventory()
    decisions_path = ROOT / "docs/product_mapping_review_decisions.csv"
    decisions = pd.read_csv(decisions_path, dtype=str, keep_default_na=False) if decisions_path.exists() else pd.DataFrame()
    overrides = decisions.set_index("StockCode").to_dict("index") if len(decisions) else {}
    if len(decisions):
        assert decisions.StockCode.is_unique and set(decisions.StockCode) <= set(products.StockCode)
    records, evidence = [], []
    for code, group in variants.groupby("StockCode", sort=True):
        results = []
        for row in group.itertuples(index=False):
            cat, conf, reason, hits = classify_description(row.description_normalized)
            results.append((cat, conf, reason))
            evidence.append({"StockCode": code, "Original Description": row.Description,
                "Normalized Description": row.description_normalized, "Purchase Lines": row.purchase_lines,
                "Example Source ID": row.example_source_id, "Rule Category": cat, "Rule Confidence": conf,
                "Rule Reason": reason, "All Rule Matches": json.dumps(hits, ensure_ascii=False)})
        cats = {r[0] for r in results if r[0] != UNKNOWN}
        competing_variant = any('Competing equally specific' in r[2] for r in results)
        if len(cats) == 1 and not competing_variant:
            assigned = next(iter(cats))
            conf = "High" if all(r[1] == "High" and r[0] == assigned for r in results) else "Medium"
            reason = "; ".join(sorted(set(r[2] for r in results)))
            if any(r[0] == UNKNOWN for r in results):
                reason += "; some variants lack specific evidence; review recommended"
        else:
            assigned, conf = UNKNOWN, "Low"
            reason = ("Competing equally specific evidence in at least one description; see variant audit" if competing_variant else
                      ("Conflicting category evidence across descriptions: " + ", ".join(sorted(cats)) if cats else "No unambiguous product-function evidence across descriptions"))
        method = "Keyword rules with StockCode-level description consistency"
        status = "Rule-classified; approval pending" if conf == "High" else ("Manual review recommended" if conf == "Medium" else "Manual review required")
        reviewed = "Not individually reviewed"
        if code in overrides:
            choice = overrides[code]
            assert choice["Assigned Category"] in {r[2] for r in RULES} | {UNKNOWN}
            assert choice["Confidence Level"] in {"High", "Medium", "Low"}
            assigned, conf = choice["Assigned Category"], choice["Confidence Level"]
            reason = choice["Classification Reason"]
            method = "Contextual review of all StockCode descriptions by assistant"
            status = "Manual review required" if conf == "Low" else "Assistant-reviewed; human approval pending"
            reviewed = choice["Reviewer"]
        ordered = group.sort_values(["purchase_lines", "Description"], ascending=[False, True], kind="stable")
        representative = ordered.iloc[0]
        descs = sorted(set(group.description_normalized))
        materials = sorted(label for label, pattern in MATERIAL_RULES.items() if any(re.search(pattern, d) for d in descs))
        material_evidence = {label: sorted(set(m.group() for d in descs for m in re.finditer(pattern, d)))
                             for label, pattern in MATERIAL_RULES.items() if label in materials}
        records.append({"StockCode": code, "Original Description": representative.Description,
            "Normalized Description": representative.description_normalized,
            "All Original Descriptions": json.dumps(group.Description.tolist(), ensure_ascii=False),
            "All Normalized Descriptions": json.dumps(descs, ensure_ascii=False),
            "Assigned Category": assigned, "Classification Method": method,
            "Confidence Level": conf, "Review Status": status, "Classification Reason": reason,
            "Reviewer": reviewed, "Material Evidence": "; ".join(materials) or "Not stated",
            "Material Evidence Terms": json.dumps(material_evidence, ensure_ascii=False),
            "Handmade Provenance": "Not established",
            "Purchase Lines": int(group.purchase_lines.sum()),
            "Original Description Count": len(group), "Normalized Description Count": len(descs),
            "Example Source ID": representative.example_source_id, "Taxonomy Version": VERSION})
    mapping = pd.DataFrame(records).merge(products[["StockCode", "unique_invoices", "stockcode_original_type"]], on="StockCode", validate="one_to_one")
    evidence = pd.DataFrame(evidence)
    assert len(mapping) == 4896 and mapping.StockCode.is_unique and mapping["Purchase Lines"].sum() == 1015214
    assert mapping.loc[mapping["Confidence Level"].eq("Low"), "Review Status"].eq("Manual review required").all()
    counts = mapping.groupby(["Assigned Category", "Confidence Level"]).agg(products=("StockCode", "size"), purchase_lines=("Purchase Lines", "sum")).reset_index()
    print(counts.to_string(index=False))
    print("Classified:", mapping["Assigned Category"].ne(UNKNOWN).sum(), "Low confidence:", mapping["Confidence Level"].eq("Low").sum())
    if preview:
        stamp = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%d_%H%M%S')
        mapping.to_csv(cache / f'mapping_preview_{stamp}.csv', index=False)
        evidence.to_csv(cache / f'evidence_preview_{stamp}.csv', index=False)
        return
    out = ROOT / "outputs/tables"
    report_dir = ROOT / "outputs/reports"
    target_names = ["product_category_mapping.csv", "category_frequency.csv", "unclassified_products.csv",
                    "product_description_inventory.csv", "product_inventory.csv", "product_mapping_decision_audit.csv",
                    "products_requiring_review.csv", "material_evidence_frequency.csv"]
    for name in target_names:
        if (out / name).exists():
            raise FileExistsError(f"Preserve prior artifact before a new version: {name}")
    if (report_dir / "category_mapping_report.md").exists():
        raise FileExistsError("Existing report must be versioned before rerun")
    freq = mapping.groupby("Assigned Category").agg(Products=("StockCode", "size"), Purchase_Lines=("Purchase Lines", "sum")).reset_index()
    freq["Product Percentage"] = freq.Products / len(mapping) * 100
    freq["Purchase Line Coverage Percentage"] = freq.Purchase_Lines / mapping["Purchase Lines"].sum() * 100
    for confidence in ["High", "Medium", "Low"]:
        sub = mapping[mapping["Confidence Level"].eq(confidence)].groupby("Assigned Category").agg(products=("StockCode", "size"), lines=("Purchase Lines", "sum"))
        freq[confidence + " Confidence Products"] = freq["Assigned Category"].map(sub.products).fillna(0).astype(int)
        freq[confidence + " Confidence Lines"] = freq["Assigned Category"].map(sub.lines).fillna(0).astype(int)
    freq = freq.sort_values("Purchase_Lines", ascending=False)
    unknown = mapping[mapping["Assigned Category"].eq(UNKNOWN)]
    review = mapping[mapping["Confidence Level"].ne("High")]
    mapping.to_csv(out / target_names[0], index=False)
    freq.to_csv(out / target_names[1], index=False)
    unknown.to_csv(out / target_names[2], index=False)
    variants.to_csv(out / target_names[3], index=False)
    products.to_csv(out / target_names[4], index=False)
    audit = evidence.merge(mapping[["StockCode", "Assigned Category", "Classification Method", "Confidence Level", "Review Status", "Classification Reason", "Reviewer"]], on="StockCode", validate="many_to_one")
    audit.to_csv(out / target_names[5], index=False)
    review.to_csv(out / target_names[6], index=False)
    material_records = []
    for material in list(MATERIAL_RULES) + ["Not stated"]:
        mask = mapping["Material Evidence"].str.split("; ").map(lambda labels: material in labels)
        material_records.append({"Material Evidence": material, "Products": int(mask.sum()), "Purchase Lines": int(mapping.loc[mask, "Purchase Lines"].sum()), "Overlapping Evidence Labels": True})
    pd.DataFrame(material_records).to_csv(out / target_names[7], index=False)
    assert freq.Products.sum() == 4896 and freq.Purchase_Lines.sum() == 1015214
    restored = pd.read_csv(out / target_names[0], dtype=str, keep_default_na=False)
    assert restored.StockCode.tolist() == mapping.StockCode.tolist()
    assert restored["Original Description"].tolist() == mapping["Original Description"].tolist()
    assert sha256(PURCHASE) == source_before
    classified = mapping["Assigned Category"].ne(UNKNOWN)
    high = mapping["Confidence Level"].eq("High")
    summary = {"unique_products": len(mapping), "original_description_variants": len(variants),
        "multiple_original_descriptions": int(products.original_description_count.gt(1).sum()),
        "multiple_normalized_descriptions": int(products.normalized_description_count.gt(1).sum()),
        "classified_products": int(classified.sum()), "classified_percentage": float(classified.mean() * 100),
        "classified_purchase_lines": int(mapping.loc[classified, "Purchase Lines"].sum()),
        "classified_line_coverage_percentage": float(mapping.loc[classified, "Purchase Lines"].sum() / 1015214 * 100),
        "high_confidence_products": int(high.sum()), "high_confidence_purchase_lines": int(mapping.loc[high, "Purchase Lines"].sum()),
        "medium_confidence_products": int(mapping["Confidence Level"].eq("Medium").sum()),
        "low_confidence_manual_review_required": int(mapping["Confidence Level"].eq("Low").sum()),
        "medium_or_low_review_queue": len(review), "assistant_individually_reviewed_products": len(overrides),
        "source_sha256_before": source_before, "source_sha256_after": sha256(PURCHASE),
        "taxonomy_version": VERSION, "generated_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
        "confidence_is_calibrated_probability": False, "handmade_provenance_established": False,
        "checks": ["4896 unique mapping keys", "all 1015214 purchase lines accounted for", "category counts reconcile", "every Low confidence product requires manual review", "representative original descriptions round-trip", "source purchase SHA256 unchanged"]}
    (report_dir / "category_mapping_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    rules = [{"id": key, "priority": p, "category": cat, "regex": regex, "confidence": conf} for key, p, cat, regex, conf in RULES]
    (report_dir / "category_mapping_rules.json").write_text(json.dumps({"version": VERSION, "rules": rules, "material_rules": MATERIAL_RULES}, indent=2), encoding="utf-8")
    report = f"""# Phase 4 category mapping report

Project: Craft Category Association Discovery Through Clustered Transaction Analysis, INT396.
Prepared for Aftab Khan and Tej Pratap Singh. Taxonomy version: `{VERSION}`.

## Results

- Products: **{len(mapping):,}**; purchase lines represented: **1,015,214**.
- Classified products: **{int(classified.sum()):,} ({classified.mean()*100:.2f}%)**.
- Classified purchase lines: **{summary['classified_purchase_lines']:,} ({summary['classified_line_coverage_percentage']:.2f}%)**.
- High confidence: **{int(high.sum()):,}** products. Medium confidence: **{summary['medium_confidence_products']:,}**.
- Low confidence / mandatory manual review: **{summary['low_confidence_manual_review_required']:,}**.
- Total Medium/Low review queue: **{len(review):,}** (Medium review recommended; Low required).
- Individually reviewed by the assistant from all descriptions: **{len(overrides):,}**. This is not a human sign-off or independent product verification.
- Original description variants: **{len(variants):,}**. Multiple original descriptions: **{summary['multiple_original_descriptions']:,}** products; multiple normalized descriptions: **{summary['multiple_normalized_descriptions']:,}**.

Classified totals include provisional Medium-confidence assignments. High-confidence-only counts are supplied separately; confidence is an ordinal evidence label, not measured accuracy. Low-confidence products remain Other/Unclassified and require manual review. No products or purchase lines were discarded.

## Category distribution

{markdown(freq[['Assigned Category', 'Products', 'Product Percentage', 'Purchase_Lines', 'Purchase Line Coverage Percentage']])}

Categories are mutually exclusive at StockCode level. Purchase-line frequency counts original retained line occurrences, not units sold or independent customers. Unique invoice counts per product are in the mapping and inventory; they must not be added to estimate global invoice counts. Material evidence tags are separate and overlapping, and must not be summed as a category partition.

## Method and evidence

See `docs/product_taxonomy.md` for category definitions and exclusions. Rules use normalized descriptions and explicit product-object phrases, with phrase specificity taking precedence over generic design/material words. All matched rules are preserved per original description in the decision audit, including nonwinning matches. Equal-priority contradictory evidence is unresolved. Different concrete categories across a StockCode's description variants trigger conflict review rather than a sales-weighted majority vote. One clear category plus insufficient variants is provisional Medium, not High.

The representative Original Description is the most frequent exact original variant, with deterministic lexical tie-breaking. This selects a display label only: all variants are retained and considered. Every variant has an example worksheet/row source ID and line frequency. Contextual assistant-review decisions are separately recorded in `docs/product_mapping_review_decisions.csv` with reviewer, category, confidence and reason. Their earlier rule results remain in the audit.

Material labels represent explicit wording such as ceramic, wood, glass, paper, or metal. They are not verified composition: wording can refer to a component, packaging or design. Gold/silver colour, vintage and craft wording do not establish material or production method. Handmade provenance is **Not established for every product**. No external product catalog or images were available for verification.

TF-IDF/similarity was considered but not run: shared design words can link objects of different functions, so similarity would not establish category truth. Explicit contextual rules and review are sufficient for this auditable first mapping. No text features, numerical model features, transaction matrices, clustering, Apriori or dashboard were generated.

## Ambiguity and review

`unclassified_products.csv` includes all unresolved StockCodes and all their original descriptions. `products_requiring_review.csv` additionally includes Medium-confidence provisional assignments. Read the reason field before approving a product. Unknown must not be mined as a meaningful merchandise category later. The assistant review status is explicitly distinguished from human approval.

Later category-based analyses must report mapping coverage and choose their invoice denominator explicitly. This phase does not filter transactions or generate baskets. Interpretation is limited to retail/giftware product functions and explicitly stated material cues; it cannot establish handicraft authenticity.

## Preservation and checks

Source: `data/processed/phase3_20261111_232629/cleaned_purchase_lines.csv.gz`.
SHA-256 before/after: `{source_before}` (unchanged).
Verified unique mapping keys, all 4,896 products represented, all 1,015,214 purchase lines accounted for, category reconciliation, mandatory review status for every Low-confidence product, and round-trip preservation of original representative descriptions. Other Phase 3 files and the raw workbook are checked separately in the preservation validation record.

Outputs are separate CSV/JSON/Markdown files. The original Description is never overwritten, and the mapping has not been joined into Phase 3 transaction files. Read StockCode as string and retain `stockcode_original_type` when joining to source data; do not normalize code case or leading zeros automatically.

Phase 4 only. **Stop for approval before Phase 5 feature engineering.**
"""
    (report_dir / "category_mapping_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    build(preview=parser.parse_args().preview)
