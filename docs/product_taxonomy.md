# Product taxonomy — description-taxonomy-v1

INT396: Craft Category Association Discovery Through Clustered Transaction Analysis.
Prepared for Aftab Khan and Tej Pratap Singh. Phase 4 only, 2026-11-12.

## Scope

Online Retail II is general retail/giftware data, not a verified handicraft dataset. This taxonomy describes recorded product functions and explicit material wording. It does not establish artisan manufacture, authenticity, production method or provenance. Every product has `Handmade Provenance = Not established`, including products with CRAFT, FELTCRAFT, CROCHET or HAND wording.

The inventory covers all 4,896 distinct StockCodes and 1,015,214 purchase lines from Phase 3. All 5,607 original description variants are retained. The inventory found 646 codes with multiple exact original descriptions. StockCode case, whitespace and original numeric/string type are preserved; codes differing by case are not merged.

## Why product function is the primary taxonomy

The suggested material categories overlap: a wooden photo frame is both wood and home decor; a glass necklace is glass and jewellery. Many descriptions omit material. Forcing a material-led partition would require guesses or arbitrary precedence. Instead, assign one functional category per StockCode and separately record potentially overlapping explicit material cues. Giftware is not a catch-all: an item being giftable supplies no specific function or handmade evidence.

| Category | Included evidence/examples | Important boundaries |
|---|---|---|
| Kitchen & Tableware | Mugs, teapots, cake stands/cases, biscuit tins, food covers, cutlery, lunch boxes, serving dishes and baking tools | A cake-shaped money box is storage. A bird-design mug is not a garden product. Generic bowls/trays can be Medium confidence. |
| Home Decor & Lighting | Candle/tea-light holders, lamps, lanterns, clocks, frames, signs, mirrors, explicit ornaments, fragrance oil burners and lighting accessories | Material or attractive design alone is insufficient. LIGHT PINK is a colour, not lighting. Chandelier earrings are jewellery. |
| Storage & Household Accessories | Trinket/jewellery boxes, household containers, hooks, knobs, shelves, organisers, money boxes and household accessories | First-aid wording on a money box is a motif. More specific food-storage descriptions can support Kitchen. Generic containers are provisional. |
| Textiles & Soft Furnishings | Cushions/covers, towels, aprons, mats, blankets, textile household accessories and hot-water bottles | Function-based family, not a claim that every component is textile. A bird-house-design hot-water bottle is not a bird house. |
| Bags & Carry Accessories | Shopping/lunch/picnic bags, purses, wallets, luggage-related accessories, umbrellas/parasols and portable fans | Gift bags are packaging; bag charms are personal accessories; a cotton bag containing a game does not classify the game as a bag. |
| Jewellery & Personal Accessories | Necklaces, bracelets, earrings, hair accessories, keyrings, wearable badges/leis and personal fashion accessories | Gold/silver colour does not establish precious-metal composition. Jewellery boxes belong to storage. |
| Paper & Stationery | Notebooks, pens/pencils, greeting-card evidence, writing sets, calendars, labels/adhesive stationery and office accessories | Playing cards/card games are toys/games; card holders are storage. Ambiguous FUN CARDS remain reviewable. |
| Craft & Sewing Supplies | Explicit sewing/knitting/craft kits and tools, ribbons, thread accessories, modelling clay, paint/stencil sets and craft components with explicit intended use | CROCHET, EMBROIDERY, BUTTON or FELTCRAFT as a finish/design does not suffice. Crochet food covers are kitchenware. Finished products are not automatically supplies. |
| Gift Packaging & Party Supplies | Gift wrapping/tags/bags, party bags, balloons, confetti and explicit gift boxes | Packaging accompanying a more specific object does not normally define that object's category. Generic gift boxes have provisional confidence. |
| Seasonal & Celebration Decorations | Explicit Christmas/Easter decorations, bunting, garlands, wreaths, baubles, tinsel and paper chains | Christmas mugs remain kitchenware; Christmas cards remain stationery; Christmas ribbons remain craft supplies. Occasion is subordinate to a clearer functional object. |
| Toys, Games & Novelty Items | Explicit toys, puzzles, games, skittles, soft toys, playhouses and novelty play items | Animal shapes alone do not prove a toy. Decorative flying ducks without a stated use remain unclassified. |
| Garden & Outdoor Accessories | Watering cans, plant/bird accessories, gardening tools/markers and explicit outdoor-use accessories | A garden-themed mug is kitchenware; a garden fork is not dining cutlery. |
| Bath & Personal Care Accessories | Soap-related items, flannels, plasters, hand warmers and personal-care accessories | Bathroom signs belong to decor; storage boxes with medical motifs are not medical equipment. |
| Pet Accessories | Explicit pet bowls, collars/leads and pet-use accessories | Dog/cat motifs do not make ordinary household products pet accessories. |
| Other/Unclassified | Insufficient, competing or contradictory product-function evidence | This is a review status category, not a substantive item group for future association-rule interpretation. |

## Evidence and confidence

Classification uses existing normalized descriptions (trim, whitespace collapse, uppercase) and retains original descriptions verbatim. Regex word boundaries, specific object phrases and documented priority values distinguish product nouns from modifiers. All matching rules, not just the winner, appear in the variant-level audit. The saved JSON records rule IDs, patterns, priorities and material patterns.

- **High:** explicit functional evidence and consistent classifications across all description variants, or a directly resolved contextual reading documented in an individual review. This is not independently measured classification accuracy.
- **Medium:** a broader functional noun, compatible but less-specific variants, or a plausible contextual interpretation requiring human confirmation. Counts of classified products include these provisional assignments and disclose them separately.
- **Low:** missing functional evidence, unresolved equal-specificity conflicts or incompatible StockCode descriptions. Assigned Other/Unclassified and marked **Manual review required**.

Sales frequency never overrides conflicting category evidence. A most-frequent description is used only as the representative display label, with deterministic lexical tie-breaking. All descriptions contribute to the StockCode-level decision. A variant with equally specific competing categories is not treated as merely missing evidence.

## Contextual review

`product_mapping_review_decisions.csv` records assistant review of selected high-frequency ambiguous products and cross-description conflicts. It includes decisions to leave products unresolved. The reviewer is identified as Codex; this is description-only review, not a claim of human sign-off or external catalog verification. All Low products still require manual review. Medium assignments are provisional even after assistant review.

Examples:

- `84946`: tea-light glass versus tea glass remains unresolved rather than selecting the more frequent label.
- `22407`: both descriptions identify a money box; FIRST AID is a design, so storage is supported.
- `22175`/`22176`: the explicit soft-toy variant supports a provisional toy assignment despite a generic decoration variant.
- `22149`: FELTCRAFT FLOWER FRIENDS does not establish whether the product is a kit or finished object, so remains unclassified.
- Seasonal/general descriptions of the same heart decoration can support a provisional seasonal assignment when an actual variant states Christmas.

Review selection is purposeful, not a representative accuracy sample. Do not report an accuracy percentage or assume unreviewed products have been manually checked. The broader Medium/Low review queue is supplied separately from the mandatory Low-confidence queue.

## Materials and provenance

Separate material evidence fields record exact matching terms for ceramic/porcelain, wood, textile/fibre, metal, glass, paper/card, wicker/rattan, plastic/acrylic, slate/stone, and enamel coating. Multiple labels can apply to a product and their counts overlap. A match may describe a component or packaging, not the complete product. ENAMEL indicates coating, not an inferred metal substrate. No material is inferred from GOLD, SILVER or VINTAGE alone. Material absence means Not stated, not a guessed composition.

These fields support future investigation of material-related retail patterns. They are not certified material classifications, evidence of craftsmanship, or permission to call all decorative products handicrafts.

## Text similarity decision

TF-IDF and nearest-description similarity were considered but not implemented. Shared design language can connect different functions and cannot settle uncertain product identity. Explicit object rules and transparent review are appropriate for this first mapping; similarity may later generate review suggestions only if separately authorized. No text feature matrix or model features were produced during Phase 4.

## Outputs, joining and change control

- `product_category_mapping.csv`: one row per original StockCode, all required classification fields, all description variants, frequency, material evidence and source reference.
- `product_description_inventory.csv`: original variants with line/invoice frequency and example worksheet/row references.
- `product_inventory.csv`: product counts, unique invoices and description multiplicity.
- `product_mapping_decision_audit.csv`: every original variant, all matching rules, provisional rule result and final product decision.
- `category_frequency.csv`: mutually exclusive product-category totals and purchase-line coverage, including High/Medium/Low breakdowns.
- `unclassified_products.csv`: all Other/Unclassified products; Low confidence and mandatory manual review.
- `products_requiring_review.csv`: broader Medium/Low queue.
- `material_evidence_frequency.csv`: overlapping material evidence, not additive category totals.

Read StockCode as string with automatic NA recognition disabled; preserve the original type metadata when joining. A future mapping revision must use a new version and retain prior outputs. Phase 3 purchase files have not been modified or enriched in place. Unknown should not later be mined as though unrelated products form one meaningful merchandise category. Future category analysis must state mapping coverage and invoice denominators explicitly.

Stop after Phase 4 and wait for approval before Phase 5 feature engineering.
