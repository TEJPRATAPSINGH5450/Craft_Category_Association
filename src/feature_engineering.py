"""Phase 5: invoice features and binary category matrices, without ML fitting.

Scalers are fitted descriptively to this dataset, not to a predictive train/test
experiment. Every Phase 3/4 input is read-only and hashed before/after the run.
"""
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, RobustScaler
from inspect_dataset import ROOT, SOURCE, sha256, markdown

os.environ['MPLCONFIGDIR'] = str(ROOT / '.cache/matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

TABLES = ROOT / 'outputs/tables'
REPORTS = ROOT / 'outputs/reports'
GRAPHS = ROOT / 'outputs/graphs'
PURCHASE = ROOT / 'data/processed/phase3_20261111_232629/cleaned_purchase_lines.csv.gz'
MAPPING = TABLES / 'product_category_mapping.csv'
UNKNOWN = 'Other/Unclassified'
LOG = logging.getLogger('phase5')


def make_basket(lines, invoices, categories, confidences):
    eligible = lines.category_confidence.isin(confidences) & lines.mapped_category.ne(UNKNOWN)
    counts = pd.crosstab(lines.loc[eligible, 'Invoice'], lines.loc[eligible, 'mapped_category'])
    binary = counts.reindex(index=invoices, columns=categories, fill_value=0).gt(0).astype('uint8')
    binary.index.name = 'Invoice'
    binary.columns.name = None
    return binary, eligible


def run():
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        raise RuntimeError('Use the project virtual environment')
    names = ['invoice_features_raw.csv.gz', 'apriori_basket_high_confidence.csv.gz',
             'apriori_basket_high_medium.csv.gz', 'feature_summary.csv', 'invoice_category_coverage.csv.gz',
             'integrated_purchase_lines.csv.gz', 'apriori_category_comparison.csv',
             'apriori_coverage_comparison.csv', 'feature_correlations_pearson.csv',
             'feature_correlations_spearman.csv', 'feature_redundancy.csv',
             'feature_scaling_comparison.csv']
    scaled_names = [f'invoice_features_{name}.csv.gz' for name in ['standard', 'robust', 'log_standard', 'log_robust']]
    reserved = [TABLES / n for n in names + scaled_names] + [REPORTS / n for n in
        ['feature_engineering_report.md', 'feature_engineering_manifest.json', 'feature_transformations.json']]
    reserved += [GRAPHS / ('phase5_' + n + '.png') for n in ['distributions', 'correlations', 'scaling']]
    if any(p.exists() for p in reserved):
        raise FileExistsError('Phase 5 outputs already exist; version them rather than overwrite')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(REPORTS / 'phase5_feature_engineering.log')])
    prior = list(PURCHASE.parent.iterdir()) + [SOURCE]
    prior += list(TABLES.glob('*.csv')) + list(REPORTS.glob('category_mapping*'))
    prior += [ROOT / 'docs/product_taxonomy.md', ROOT / 'docs/product_mapping_review_decisions.csv']
    before = {str(p): sha256(p) for p in prior if p.is_file()}
    manifest3 = json.loads((PURCHASE.parent / 'manifest.json').read_text())
    for item in manifest3['files']:
        assert before[item['path']] == item['sha256'], 'Phase 3 hash changed before feature engineering'
    assert before[str(SOURCE)] == manifest3['sha256_after']
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)
    LOG.info('Loading unchanged Phase 3 purchase lines and Phase 4 mapping')
    original = pd.read_csv(PURCHASE, dtype=str, keep_default_na=False)
    mapping = pd.read_csv(MAPPING, dtype={'StockCode': str}, keep_default_na=False)
    check('mapping_stockcode_unique', mapping.StockCode.is_unique)
    check('source_line_count', len(original) == 1015214)
    check('source_ids_unique', original.source_id.is_unique)
    check('source_product_count', original.StockCode.nunique() == 4896)
    category_map = mapping[['StockCode', 'Assigned Category', 'Confidence Level', 'Review Status', 'stockcode_original_type']].rename(
        columns={'Assigned Category': 'mapped_category', 'Confidence Level': 'category_confidence',
                 'Review Status': 'category_review_status', 'stockcode_original_type': 'mapping_stockcode_type'})
    joined = original.merge(category_map, on='StockCode', how='left', validate='many_to_one', indicator=True, sort=False)
    unmatched = int(joined['_merge'].ne('both').sum())
    check('no_unmatched_stockcodes', unmatched == 0)
    check('join_preserves_line_count', len(joined) == len(original))
    check('join_preserves_source_order', joined.source_id.equals(original.source_id))
    check('stockcode_type_agrees', joined.raw_type_StockCode.eq(joined.mapping_stockcode_type).all())
    pd.testing.assert_frame_equal(original, joined[original.columns])
    check('original_columns_and_descriptions_preserved', True)
    joined = joined.drop(columns='_merge')
    LOG.info('Many-to-one integration verified; %s lines retained', len(joined))
    q = pd.to_numeric(joined.Quantity, errors='raise')
    price = pd.to_numeric(joined.Price, errors='raise')
    dates = pd.to_datetime(joined.InvoiceDate, errors='raise')
    check('positive_quantity_nonnegative_price', q.gt(0).all() and price.ge(0).all())
    check('no_cancelled_or_nonpurchase_lines', joined.dataset.eq('cleaned_purchase_lines').all() and ~joined.Invoice.str.match(r'(?i)^C').any())
    check('finite_source_measures', np.isfinite(q).all() and np.isfinite(price).all())
    measures = pd.DataFrame({'Invoice': joined.Invoice, 'StockCode': joined.StockCode, 'quantity': q,
        'value': q * price, 'unit_price': price, 'timestamp': dates,
        'customer': joined['Customer ID'].replace('', pd.NA),
        'category': joined.mapped_category, 'confidence': joined.category_confidence})
    grouped = measures.groupby('Invoice', sort=True)
    raw = grouped.agg(line_count=('StockCode', 'size'), total_quantity=('quantity', 'sum'),
        total_purchase_value=('value', 'sum'), unique_product_count=('StockCode', 'nunique'),
        average_line_unit_price=('unit_price', 'mean'), median_line_unit_price=('unit_price', 'median'),
        first_purchase_timestamp=('timestamp', 'min'), last_purchase_timestamp=('timestamp', 'max'),
        timestamp_count=('timestamp', 'nunique'), known_customer_count=('customer', 'nunique'))
    raw['customer_id'] = grouped.customer.first().fillna('')
    raw['missing_customer_lines'] = measures.customer.isna().groupby(measures.Invoice).sum()
    raw['anonymous_invoice'] = raw.known_customer_count.eq(0)
    raw['weighted_average_unit_price'] = raw.total_purchase_value / raw.total_quantity
    raw['unique_products_per_line'] = raw.unique_product_count / raw.line_count
    product_quantities = measures.groupby(['Invoice', 'StockCode']).quantity.sum()
    squared = product_quantities.pow(2).groupby(level=0).sum()
    raw['product_diversity'] = 1 - squared / raw.total_quantity.pow(2)
    raw['zero_price_lines'] = price.eq(0).groupby(joined.Invoice).sum()
    raw['invoice_span_minutes'] = (raw.last_purchase_timestamp - raw.first_purchase_timestamp).dt.total_seconds() / 60
    raw['hour_sin'] = np.sin(2 * np.pi * (raw.first_purchase_timestamp.dt.hour + raw.first_purchase_timestamp.dt.minute / 60) / 24)
    raw['hour_cos'] = np.cos(2 * np.pi * (raw.first_purchase_timestamp.dt.hour + raw.first_purchase_timestamp.dt.minute / 60) / 24)
    raw['weekday_sin'] = np.sin(2 * np.pi * raw.first_purchase_timestamp.dt.dayofweek / 7)
    raw['weekday_cos'] = np.cos(2 * np.pi * raw.first_purchase_timestamp.dt.dayofweek / 7)
    invoices = raw.index
    categories = sorted(set(mapping.loc[mapping['Assigned Category'].ne(UNKNOWN), 'Assigned Category']))
    high, high_mask = make_basket(joined, invoices, categories, ['High'])
    hm, hm_mask = make_basket(joined, invoices, categories, ['High', 'Medium'])
    check('expected_invoice_count', len(invoices) == 39516 and invoices.is_unique)
    check('expected_category_count', len(categories) == 14)
    check('high_category_lines', int(high_mask.sum()) == 819845)
    check('high_medium_category_lines', int(hm_mask.sum()) == 953999)
    check('low_unknown_never_assigned_item', not joined.loc[hm_mask, 'mapped_category'].eq(UNKNOWN).any())
    check('high_subset_of_high_medium', (high.to_numpy() <= hm.to_numpy()).all())
    check('all_invoices_preserved_in_both_baskets', high.index.equals(raw.index) and hm.index.equals(raw.index))
    raw['unique_categories_high'] = high.sum(axis=1)
    raw['unique_categories_high_medium'] = hm.sum(axis=1)
    for name, mask in [('high', high_mask), ('high_medium', hm_mask)]:
        raw[f'{name}_classified_lines'] = joined.loc[mask].groupby('Invoice').size().reindex(invoices, fill_value=0)
        raw[f'{name}_line_coverage'] = raw[f'{name}_classified_lines'] / raw.line_count
    raw['unclassified_lines'] = raw.line_count - raw.high_medium_classified_lines
    spending = measures.loc[hm_mask].groupby(['Invoice', 'category']).value.sum().unstack(fill_value=0).reindex(index=invoices, columns=categories, fill_value=0)
    category_columns = {}
    for number, category in enumerate(categories, 1):
        spend_col, share_col = f'category_{number:02d}_spend', f'category_{number:02d}_spend_share'
        category_columns[category] = {'spend': spend_col, 'share': share_col}
        raw[spend_col] = spending[category]
        raw[share_col] = spending[category] / raw.total_purchase_value
    raw['unclassified_purchase_value'] = raw.total_purchase_value - spending.sum(axis=1)
    # Floating roundoff can produce ~1e-12 residuals on fully mapped invoices;
    # compute the true unknown subtotal directly instead of clipping measurements.
    raw['unclassified_purchase_value'] = measures.loc[~hm_mask].groupby('Invoice').value.sum().reindex(invoices, fill_value=0)
    raw['unclassified_spend_share'] = raw.unclassified_purchase_value / raw.total_purchase_value
    check('no_zero_invoice_value', raw.total_purchase_value.gt(0).all())
    check('invoice_lines_reconcile', raw.line_count.sum() == len(joined))
    check('invoice_quantity_reconciles', np.isclose(raw.total_quantity.sum(), q.sum(), rtol=1e-12))
    check('invoice_values_reconcile', np.isclose(raw.total_purchase_value.sum(), (q * price).sum(), rtol=1e-12))
    check('known_customer_consistent_per_invoice', raw.known_customer_count.le(1).all())
    check('diversity_bounds', raw.product_diversity.between(-1e-12, 1 + 1e-12).all())
    check('category_values_reconcile', np.allclose(spending.sum(axis=1) + raw.unclassified_purchase_value, raw.total_purchase_value, rtol=1e-12, atol=1e-8))
    share_cols = [v['share'] for v in category_columns.values()] + ['unclassified_spend_share']
    check('category_shares_sum_to_one', np.allclose(raw[share_cols].sum(axis=1), 1, atol=1e-10))
    numeric = raw.select_dtypes(include=['number', 'bool']).astype(float)
    check('raw_numeric_features_finite_nonmissing', np.isfinite(numeric.to_numpy()).all())
    # Diagnostic metadata and algebraic derivatives remain in raw output, but
    # are not automatically included in the candidate K-Means experiment.
    proposed = ['total_quantity', 'total_purchase_value', 'unique_product_count', 'product_diversity']
    selected = []
    omitted = {}
    spearman = numeric[proposed].corr(method='spearman')
    for col in proposed:
        if numeric[col].nunique() <= 1:
            omitted[col] = 'constant'
        elif any(abs(spearman.loc[col, old]) >= .95 for old in selected):
            omitted[col] = 'absolute Spearman correlation >= 0.95 with an earlier selected feature; inspect redundancy table'
        else:
            selected.append(col)
    pearson_all = numeric.corr(method='pearson')
    spearman_all = numeric.corr(method='spearman')
    pearson_all.to_csv(TABLES / 'feature_correlations_pearson.csv', index_label='feature')
    spearman_all.to_csv(TABLES / 'feature_correlations_spearman.csv', index_label='feature')
    diagnostic_cols = ['line_count', 'total_quantity', 'total_purchase_value', 'unique_product_count', 'product_diversity',
                       'average_line_unit_price', 'weighted_average_unit_price', 'unique_products_per_line', 'unique_categories_high_medium']
    redundancy = []
    for i, a in enumerate(diagnostic_cols):
        for b in diagnostic_cols[i+1:]:
            redundancy.append({'feature_a': a, 'feature_b': b, 'pearson': pearson_all.loc[a, b],
                'spearman': spearman_all.loc[a, b], 'abs_spearman_ge_095': abs(spearman_all.loc[a, b]) >= .95})
    pd.DataFrame(redundancy).to_csv(TABLES / 'feature_redundancy.csv', index=False)
    log_cols = [col for col in selected if col != 'product_diversity' and numeric[col].min() >= 0 and numeric[col].skew() > 1]
    base = numeric[selected]
    logged = base.copy()
    logged[log_cols] = np.log1p(logged[log_cols])
    scaling, transformations, variants = [], {}, {}
    for name, values, scaler in [('standard', base, StandardScaler()), ('robust', base, RobustScaler()),
                                 ('log_standard', logged, StandardScaler()), ('log_robust', logged, RobustScaler())]:
        transformed = pd.DataFrame(scaler.fit_transform(values), index=invoices, columns=selected)
        check(f'{name}_finite', np.isfinite(transformed.to_numpy()).all())
        check(f'{name}_invertible', np.allclose(scaler.inverse_transform(transformed), values, rtol=1e-10, atol=1e-10))
        variants[name] = transformed
        center = scaler.mean_ if isinstance(scaler, StandardScaler) else scaler.center_
        transformations[name] = {'columns': selected, 'log1p_columns': log_cols if name.startswith('log_') else [],
            'scaler': type(scaler).__name__, 'center': center.tolist(), 'scale': scaler.scale_.tolist(),
            'fit_population': 'all 39516 invoices; descriptive preparation only',
            'refit_required_for_held_out_evaluation': True}
        for col in selected:
            s = transformed[col]
            scaling.append({'variant': name, 'feature': col, 'min': s.min(), 'max': s.max(),
                'median': s.median(), 'mean': s.mean(), 'std_ddof0': s.std(ddof=0),
                'iqr': s.quantile(.75) - s.quantile(.25), 'skewness': s.skew(),
                'p99': s.quantile(.99), 'max_abs': s.abs().max()})
    scale_table = pd.DataFrame(scaling)
    scale_table.to_csv(TABLES / 'feature_scaling_comparison.csv', index=False)
    feature_summary = numeric.describe(percentiles=[.01, .25, .5, .75, .95, .99]).T.rename_axis('feature').reset_index()
    feature_summary['missing_count'] = feature_summary.feature.map(numeric.isna().sum())
    feature_summary['skewness'] = feature_summary.feature.map(numeric.skew())
    feature_summary['unique_values'] = feature_summary.feature.map(numeric.nunique())
    feature_summary['selected_for_candidate_kmeans'] = feature_summary.feature.isin(selected)
    feature_summary['log1p_in_log_variants'] = feature_summary.feature.isin(log_cols)
    feature_summary['role'] = np.where(feature_summary.feature.isin(selected), 'candidate_model_feature', 'diagnostic_or_optional_not_selected')
    feature_summary.to_csv(TABLES / 'feature_summary.csv', index=False)
    coverage_cols = ['line_count', 'missing_customer_lines', 'anonymous_invoice', 'high_classified_lines', 'high_medium_classified_lines',
                     'high_line_coverage', 'high_medium_line_coverage', 'unclassified_lines', 'unique_categories_high', 'unique_categories_high_medium']
    coverage = raw[coverage_cols].copy()
    coverage['high_empty_basket'] = high.sum(axis=1).eq(0)
    coverage['high_medium_empty_basket'] = hm.sum(axis=1).eq(0)
    basket_stats, category_stats = [], []
    for name, basket, mask in [('high', high, high_mask), ('high_medium', hm, hm_mask)]:
        check(f'{name}_binary', np.isin(basket.to_numpy(), [0, 1]).all())
        check(f'{name}_no_missing_or_duplicate_invoice', not basket.isna().any().any() and basket.index.is_unique)
        unique_pairs = joined.loc[mask, ['Invoice', 'mapped_category']].drop_duplicates()
        check(f'{name}_ones_equal_unique_invoice_category_pairs', int(basket.to_numpy().sum()) == len(unique_pairs))
        # Presence is collapsed intentionally; repeated source lines remain in the
        # integrated data and totals, not multiplied into basket item weights.
        basket_stats.append({'variant': name, 'total_invoices': len(basket), 'categories': len(categories),
            'source_lines_represented': len(joined), 'eligible_category_lines': int(mask.sum()),
            'eligible_line_percentage': float(mask.mean() * 100), 'nonempty_invoices': int(basket.any(axis=1).sum()),
            'nonempty_invoice_percentage': float(basket.any(axis=1).mean() * 100),
            'empty_invoices_retained': int(basket.sum(axis=1).eq(0).sum()),
            'single_category_invoices_retained': int(basket.sum(axis=1).eq(1).sum()),
            'anonymous_invoices_retained': int(raw.anonymous_invoice.sum()),
            'unique_invoice_category_pairs': len(unique_pairs),
            'repeat_invoice_category_line_occurrences_collapsed': int(mask.sum()) - len(unique_pairs)})
        eligible_by_cat = joined.loc[mask].groupby('mapped_category').size()
        for cat in categories:
            category_stats.append({'variant': name, 'category': cat, 'eligible_lines': int(eligible_by_cat.get(cat, 0)),
                'invoices_with_category': int(basket[cat].sum()),
                'prevalence_all_purchase_invoices_pct': float(basket[cat].mean() * 100),
                'prevalence_nonempty_baskets_pct': float(basket[cat].sum() / basket.any(axis=1).sum() * 100)})
    basket_summary = pd.DataFrame(basket_stats)
    basket_summary.to_csv(TABLES / 'apriori_coverage_comparison.csv', index=False)
    pd.DataFrame(category_stats).to_csv(TABLES / 'apriori_category_comparison.csv', index=False)
    LOG.info('Engineered %s invoices, %s category columns; selected features %s', len(raw), len(categories), selected)
    # Re-read each numerical artifact to check keys, precision and binary values.
    saved = []
    def save_numeric(name, frame):
        path = TABLES / name
        frame.to_csv(path, index=True, index_label='Invoice', compression={'method': 'gzip', 'compresslevel': 1})
        restored = pd.read_csv(path, dtype={'Invoice': str, 'customer_id': str}, keep_default_na=False, float_precision='round_trip').set_index('Invoice')
        check(name + '_keys_roundtrip', restored.index.equals(frame.index))
        check(name + '_columns_roundtrip', list(restored.columns) == list(frame.columns))
        for col in frame.columns:
            if pd.api.types.is_numeric_dtype(frame[col]):
                check(name + '_' + col, np.allclose(pd.to_numeric(restored[col]), frame[col], rtol=1e-12, atol=1e-12))
            elif pd.api.types.is_datetime64_any_dtype(frame[col]):
                check(name + '_' + col, pd.to_datetime(restored[col]).equals(frame[col]))
            else:
                check(name + '_' + col, restored[col].astype(str).equals(frame[col].astype(str)))
        saved.append(path)
    save_numeric('invoice_features_raw.csv.gz', raw)
    save_numeric('apriori_basket_high_confidence.csv.gz', high)
    save_numeric('apriori_basket_high_medium.csv.gz', hm)
    save_numeric('invoice_category_coverage.csv.gz', coverage)
    for name, frame in variants.items():
        save_numeric(f'invoice_features_{name}.csv.gz', frame)
    integrated_path = TABLES / 'integrated_purchase_lines.csv.gz'
    joined.to_csv(integrated_path, index=False, compression={'method': 'gzip', 'compresslevel': 1})
    offset = 0
    for chunk in pd.read_csv(integrated_path, dtype=str, keep_default_na=False, chunksize=100000):
        pd.testing.assert_frame_equal(chunk.reset_index(drop=True), joined.iloc[offset:offset+len(chunk)].reset_index(drop=True), check_dtype=False)
        offset += len(chunk)
    check('integrated_saved_every_field_roundtrip', offset == len(joined))
    saved.append(integrated_path)

    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout='constrained')
    for i, col in enumerate(['total_quantity', 'total_purchase_value', 'unique_product_count']):
        axes[0, i].hist(raw[col], bins=70, log=True, color='#28798e')
        axes[0, i].set_title(col.replace('_', ' '))
        axes[0, i].set_ylabel('Invoices (log count)')
        axes[1, i].hist(np.log1p(raw[col]), bins=70, log=True, color='#a45d3d')
        axes[1, i].set_xlabel('log1p(' + col.replace('_', ' ') + ')')
        axes[1, i].set_ylabel('Invoices (log count)')
    fig.suptitle('Invoice feature distributions — all 39,516 invoices; no outliers removed')
    fig.savefig(GRAPHS / 'phase5_distributions.png', dpi=160, bbox_inches='tight'); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), layout='constrained')
    labels = [c.replace('_', ' ') for c in diagnostic_cols]
    for ax, method, matrix in [(axes[0], 'Pearson', pearson_all), (axes[1], 'Spearman', spearman_all)]:
        sns.heatmap(matrix.loc[diagnostic_cols, diagnostic_cols], ax=ax, vmin=-1, vmax=1, cmap='vlag', annot=True, fmt='.2f',
                    xticklabels=labels, yticklabels=labels, cbar=False, annot_kws={'fontsize': 8})
        ax.set_title(method + ' correlations')
        ax.tick_params(axis='x', rotation=65)
    fig.savefig(GRAPHS / 'phase5_correlations.png', dpi=160, bbox_inches='tight'); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), layout='constrained')
    for ax, metric, title in [(axes[0], 'max_abs', 'Largest absolute transformed value'), (axes[1], 'skewness', 'Skewness after transformation')]:
        plot = scale_table.pivot(index='feature', columns='variant', values=metric)
        plot.plot.bar(ax=ax)
        ax.set_title(title); ax.set_xlabel(''); ax.tick_params(axis='x', rotation=25)
        if metric == 'max_abs': ax.set_yscale('log')
    fig.suptitle('StandardScaler vs RobustScaler, with and without log1p — no clipping')
    fig.savefig(GRAPHS / 'phase5_scaling.png', dpi=160, bbox_inches='tight'); plt.close(fig)
    after = {name: sha256(Path(name)) for name in before}
    check('all_prior_files_and_raw_unchanged', before == after)
    transform_record = {'selected_features': selected, 'candidate_features_omitted_as_redundant': omitted,
        'log1p_rule': 'nonnegative selected size/value feature with raw sample skewness > 1; diversity not logged',
        'log1p_features': log_cols, 'category_spending_columns': category_columns,
        'variants': transformations, 'recommended_candidate': 'log_robust',
        'reason': 'Reduce heavy-tail magnitude using log1p; use median/IQR scaling as a candidate, with log_standard retained for comparison. No clustering results establish a winner.',
        'original_features_preserved': True, 'invoices_removed': 0,
        'identifiers_excluded_from_feature_columns': ['Invoice', 'Customer ID', 'StockCode', 'customer_id'],
        'category_denominator': 'all 39516 purchase invoices in both matrices; empty rows retained',
        'zero_meaning': 'no qualifying observed category; unknown/low-confidence items do not establish true absence',
        'confidence_note': 'Phase 4 descriptive confidence, not human certification or handmade verification'}
    (REPORTS / 'feature_transformations.json').write_text(json.dumps(transform_record, indent=2), encoding='utf-8')
    summary = {'created_at': datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(), 'source_lines': len(original),
        'joined_lines': len(joined), 'unmatched_stockcodes': unmatched, 'invoices': len(raw), 'categories': len(categories),
        'anonymous_invoices': int(raw.anonymous_invoice.sum()), 'invoices_with_multiple_timestamps': int(raw.timestamp_count.gt(1).sum()),
        'selected_features': selected, 'log1p_features': log_cols, 'omitted_features': omitted,
        'basket_variants': basket_stats, 'checks': checks, 'all_checks_passed': all(checks.values()),
        'preservation': [{'path': name, 'before': before[name], 'after': after[name]} for name in before],
        'output_hashes': {str(p.relative_to(ROOT)): sha256(p) for p in reserved if p.exists()},
        'python': sys.version, 'pandas': pd.__version__, 'numpy': np.__version__,
        'pipeline_sha256': sha256(Path(__file__)), 'algorithms_run': []}
    (REPORTS / 'feature_engineering_manifest.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    report = f"""# Phase 5 feature engineering report

INT396 — Aftab Khan and Tej Pratap Singh. Generated {summary['created_at']}.

## Integration and observation units

Read 1,015,214 Phase 3 purchase lines and 4,896 Phase 4 mapping keys. A validated many-to-one StockCode join produced **{len(joined):,} lines**, **{unmatched} unmatched codes**, and no line multiplication. Original descriptions, original business fields and worksheet/row source references remain intact in `integrated_purchase_lines.csv.gz`. Original StockCode type metadata was checked; code case was not changed. All source files remain unchanged.

The primary observation unit is **{len(raw):,} invoices**, including **{int(raw.anonymous_invoice.sum()):,} anonymous invoices**. No invoice was removed for missing Customer ID, low-confidence products, single-category content, bulk quantity or outliers. Invoice IDs are row keys only. No Invoice/Customer/StockCode identifiers enter numerical model columns.

## Raw feature definitions

- `total_quantity`: sum of positive recorded quantity across retained invoice lines.
- `total_purchase_value`: sum of Quantity × Price in source price units. Zero-priced lines contribute zero and remain present; no price is imputed.
- `unique_product_count`: distinct original StockCodes per invoice.
- `unique_categories_high` / `unique_categories_high_medium`: distinct qualifying assigned categories; Unknown is excluded. These measure observed classified categories, not complete true diversity.
- `average_line_unit_price`: arithmetic mean of line prices. `weighted_average_unit_price`: total value / total quantity. `median_line_unit_price` is a robustness diagnostic. The weighted mean is algebraically dependent on totals and excluded from the baseline.
- `product_diversity`: 1 − sum over products of (product quantity / total invoice quantity)^2. Repeated lines for a product are aggregated before computing this Simpson-style concentration complement. A one-product invoice has zero diversity. `unique_products_per_line` is a separate line-granularity diagnostic, not the selected diversity measure.
- Category spending columns record High+Medium category value and its share of **total invoice value**, with exact category-to-column names saved in `feature_transformations.json`. Unclassified value/share stays explicit. The 14 category shares plus unclassified share sum to one. These shares are optional composition features, not part of the baseline selected feature matrix.
- Timestamp minimum/maximum and span remain metadata. Cyclic hour and weekday features use the earliest recorded invoice timestamp, without assuming a timezone. **{int(raw.timestamp_count.gt(1).sum()):,} invoices have multiple timestamps**; the span is retained. These temporal features are not selected by default, to avoid turning a purchasing-pattern study into a calendar segmentation.
- Customer identity/missingness, line coverage, zero-price counts and category coverage are audit metadata. Empty customer IDs remain missing; no fictitious customer is created.

## Feature assessment and selection

Raw numerical feature statistics, skewness, percentiles, missing counts, roles and selected flags are in `feature_summary.csv`. Pearson and Spearman correlation matrices and pairwise redundancy diagnostics are supplied. Constant feature correlations may be undefined (NaN) in correlation tables; that is not missing source data or a missing model feature.

Candidate model columns: **{', '.join(selected)}**. Initial candidates were quantity, purchase value, product count and product diversity. Selection retains the first candidate and excludes later candidates with absolute Spearman correlation ≥ 0.95 to an already selected candidate, or zero variability. Omitted candidates: `{json.dumps(omitted)}`. This transparent screening is not a claim of optimal clustering features.

Line count is not added alongside product count by default. Weighted unit price is derived from quantity/value and is not added to those totals. Category counts partly reflect basket size and mapping coverage; all category shares are compositionally constrained, and adding them blindly would change feature weighting. Correlation alone does not establish that all retained features contribute independently. Phase 6 should compare this candidate baseline with justified alternatives.

## Transformations and scaler evaluation

Logged features: **{', '.join(log_cols)}**, selected by nonnegative values and sample skewness > 1. Applied log1p only to copies; no original feature was overwritten. Bounded product diversity is not logged. Four matrices preserve the same invoice order: StandardScaler and RobustScaler on original selected features, and each scaler on log-transformed features.

StandardScaler uses population mean/standard deviation (ddof=0); RobustScaler uses median and interquartile range. Parameters and exact feature order are saved. Robust scaling alone does not remove extreme values or make K-Means robust to them. No winsorization, clipping, imputation or record deletion was used. Inverse-transform checks passed. Log1p changes skewness; ordinary centering/scaling does not remove skewness.

The **log1p + RobustScaler** matrix is a proposed starting candidate, with log1p + StandardScaler retained for comparison. No model was fitted, so no clustering-quality winner is claimed. All scalers here were fitted on the full dataset for descriptive preparation. If Phase 6 introduces held-out evaluation, refit transformations inside its development split; do not reuse these full-data parameters to claim leakage-free validation.

{markdown(scale_table)}

## Apriori preparation and coverage

Both matrices have the same **{len(raw):,} invoice rows × {len(categories)} functional category columns**. Cells are binary observed presence, never quantity, value or frequency. The category labels retain the Phase 4 evidential limitations: High is not external verification, Medium is provisional, and none establishes handmade production.

{markdown(basket_summary)}

Repeated invoice-category line occurrences are intentionally collapsed to one presence bit, not deleted from source data. Single-category invoices remain present. Low-confidence/unclassified items remain in the integrated data and invoice numerical totals but never become an Unknown item column. High+Medium is a cell-wise superset of High. The coverage sidecar records qualifying line counts, coverage fractions and empty baskets for each invoice.

All-zero category rows are retained so both matrices have the same purchase-invoice denominator. Here 0 means no qualifying category was observed; unresolved or excluded-confidence items prevent interpreting 0 as definitive true absence. In later rule mining, keeping these rows estimates support among all purchase invoices. Any nonempty-only sensitivity analysis must explicitly declare its changed denominator. The category comparison table supplies both all-invoice prevalence and nonempty-basket prevalence, labeled separately. No rule mining was performed.

## Validation and preservation

All **{len(checks)}** recorded validation checks passed. Checks cover invoice uniqueness, exact join cardinality, StockCode types, source-row/description preservation, source-policy eligibility, aggregate quantity/value/line reconciliation, finite features, diversity and share bounds, binary correctness, unique invoice-category pair counts, confidence coverage and aligned invoice universes. Each generated compressed data file was re-read; saved raw/scaled/binary columns were compared with the computed values. Every field in the integrated line export was checked after reload.

All **{len(before)}** protected input files were SHA-256 checked before and after, including the raw workbook, all Phase 3 files and Phase 4 artifacts present at start. Phase 3 dataset hashes also matched their original manifest before processing. Preservation details, software versions, transformations and output hashes are recorded in `feature_engineering_manifest.json` and `feature_transformations.json`.

## Outputs and reproducibility

Required outputs are in `outputs/tables/`: `invoice_features_raw.csv.gz`, `apriori_basket_high_confidence.csv.gz`, `apriori_basket_high_medium.csv.gz`, and `feature_summary.csv`. Additional outputs include the immutable joined-line export, invoice coverage, four separate scaled candidate matrices, correlation/redundancy tables and basket comparisons. Read Invoice and StockCode as strings. Invoice is an index column in the numerical CSVs, never a feature.

Plots: `outputs/graphs/phase5_distributions.png`, `phase5_correlations.png`, `phase5_scaling.png`. All invoices are represented in distribution plots; no tails are silently dropped.

Run `.venv\\Scripts\\python.exe src\\feature_engineering.py` on the approved inputs in an output namespace with no existing Phase 5 files. Existing deliverables are protected from overwrite; version them before a new run. No K-Means, Apriori or dashboard was implemented.

**Phase 5 complete. Stop and obtain approval before Phase 6.**
"""
    (REPORTS / 'feature_engineering_report.md').write_text(report, encoding='utf-8')
    LOG.info('Phase 5 complete. Invoice counts and coverage: %s', basket_stats)
    print(json.dumps({'invoices': len(raw), 'selected': selected, 'omitted': omitted, 'checks': len(checks),
                      'baskets': basket_stats}, indent=2))


if __name__ == '__main__':
    run()
