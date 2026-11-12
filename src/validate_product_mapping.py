"""Validate Phase 4 artifacts and preservation without rewriting valid outputs."""
import json
from pathlib import Path
import pandas as pd
from inspect_dataset import ROOT, sha256


def main():
    tables = ROOT / 'outputs/tables'
    reports = ROOT / 'outputs/reports'
    mapping = pd.read_csv(tables / 'product_category_mapping.csv', dtype={'StockCode': str}, keep_default_na=False)
    freq = pd.read_csv(tables / 'category_frequency.csv')
    unknown = pd.read_csv(tables / 'unclassified_products.csv', dtype={'StockCode': str}, keep_default_na=False)
    review = pd.read_csv(tables / 'products_requiring_review.csv', dtype={'StockCode': str}, keep_default_na=False)
    audit = pd.read_csv(tables / 'product_mapping_decision_audit.csv', dtype={'StockCode': str}, keep_default_na=False)
    original_inventory = pd.read_csv(ROOT / '.cache/phase4_inventory/description_inventory.csv', dtype={'StockCode': str}, keep_default_na=False)
    saved_inventory = pd.read_csv(tables / 'product_description_inventory.csv', dtype={'StockCode': str}, keep_default_na=False)
    checks = {}
    def check(name, passed):
        checks[name] = bool(passed)
        assert passed, name
    check('unique_complete_mapping', len(mapping) == 4896 and mapping.StockCode.is_unique)
    check('full_purchase_line_coverage_including_unknown', mapping['Purchase Lines'].sum() == 1015214)
    check('category_product_reconciliation', freq.Products.sum() == len(mapping))
    check('category_line_reconciliation', freq.Purchase_Lines.sum() == 1015214)
    check('mandatory_review_set_exact', set(unknown.StockCode) == set(mapping.loc[mapping['Confidence Level'].eq('Low'), 'StockCode']))
    check('low_confidence_status', unknown['Review Status'].eq('Manual review required').all())
    check('unknown_category_consistency', unknown['Assigned Category'].eq('Other/Unclassified').all())
    check('medium_low_queue_exact', set(review.StockCode) == set(mapping.loc[mapping['Confidence Level'].ne('High'), 'StockCode']))
    check('handmade_not_claimed', mapping['Handmade Provenance'].eq('Not established').all())
    check('no_missing_decision_fields', mapping[['Original Description', 'Normalized Description', 'Assigned Category', 'Classification Method', 'Confidence Level', 'Review Status', 'Classification Reason']].ne('').all().all())
    check('all_variants_audited', len(audit) == len(original_inventory) == 5607)
    check('audit_counts_reconcile', audit['Purchase Lines'].sum() == 1015214)
    pd.testing.assert_frame_equal(original_inventory, saved_inventory)
    check('original_description_inventory_preserved', True)
    for row in mapping.itertuples(index=False, name=None):
        entry = dict(zip(mapping.columns, row))
        originals = original_inventory.loc[original_inventory.StockCode.eq(entry['StockCode']), 'Description']
        check('all_original_variants_preserved_' + entry['StockCode'], set(json.loads(entry['All Original Descriptions'])) == set(originals))
    baseline = json.loads((ROOT / '.cache/phase4_preservation_before.json').read_text())
    preserved = []
    for name, before in baseline.items():
        after = sha256(ROOT / name)
        check('preserved_' + name, before == after)
        preserved.append({'path': str(ROOT / name), 'sha256_before': before, 'sha256_after': after, 'unchanged': before == after})
    record = {'passed': all(checks.values()), 'check_count': len(checks), 'checks': checks,
              'preserved_files': preserved,
              'artifact_hashes': {p.name: sha256(p) for p in tables.glob('*category*.csv')}}
    target = reports / 'category_mapping_validation.json'
    if target.exists():
        raise FileExistsError('Preserve the existing validation record; choose a versioned filename to repeat')
    target.write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps({'passed': record['passed'], 'checks': len(checks), 'preserved_files': len(preserved)}, indent=2))


if __name__ == '__main__':
    main()
