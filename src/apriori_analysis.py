"""Phase 7: global category association mining, preserving all prior artifacts.

Run with the local virtual environment. All 39,516 invoices, including empty
baskets, are in every support denominator. No cluster-wise mining is performed.
"""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
import hashlib
import json
import sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import mlxtend
from mlxtend.frequent_patterns import apriori, association_rules
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from textwrap import fill

T, R, G = (ROOT / 'outputs' / part for part in ['tables', 'reports', 'graphs'])
SUPPORTS = [0.01, 0.02, 0.03, 0.05]
CONFIDENCES = [0.30, 0.40, 0.50, 0.60]
MAX_RULE_ITEMS = 4
N = 39516
METRICS = ['antecedent support', 'consequent support', 'support', 'confidence', 'lift', 'leverage', 'conviction']


def sha(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest().upper()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding='utf-8')


def markdown(df):
    return '| ' + ' | '.join(df.columns) + ' |\n| ' + ' | '.join(['---']*len(df.columns)) + ' |\n' + '\n'.join(
        '| ' + ' | '.join(f'{v:.5g}' if isinstance(v, float) else str(v) for v in row) + ' |' for row in df.itertuples(index=False, name=None))


def count_supersets(binary):
    """Independent exhaustive integer support counts, including mask 0 = N.

    Histogram the exact 14-bit baskets, then sum over supersets by zeta transform.
    This is a validation oracle; the requested mining is performed by Apriori.
    """
    masks = binary.to_numpy(dtype=np.int64) @ (1 << np.arange(binary.shape[1], dtype=np.int64))
    counts = np.bincount(masks, minlength=1 << binary.shape[1])
    for bit in range(binary.shape[1]):
        step = 1 << bit
        for start in range(0, len(counts), step*2):
            counts[start:start+step] += counts[start+step:start+2*step]
    return counts, masks


def mask_of(items, categories):
    return sum(1 << categories.index(c) for c in items)


def encode(mask, categories):
    return json.dumps([c for i, c in enumerate(categories) if mask & (1 << i)], ensure_ascii=False)


def names(mask, categories):
    return ' + '.join(c for i, c in enumerate(categories) if mask & (1 << i))


def rules_for(itemsets):
    readable = itemsets[itemsets.itemsets.map(len).le(MAX_RULE_ITEMS)]
    return association_rules(readable, num_itemsets=N, metric='confidence', min_threshold=.30, return_metrics=METRICS)


def enrich_rules(frame, counts, categories):
    frame = frame.copy()
    frame['antecedent_mask'] = frame.antecedents.map(lambda s: mask_of(s, categories))
    frame['consequent_mask'] = frame.consequents.map(lambda s: mask_of(s, categories))
    frame['rule_id'] = frame.antecedent_mask.astype(str) + '->' + frame.consequent_mask.astype(str)
    frame['antecedent_length'] = frame.antecedents.map(len)
    frame['consequent_length'] = frame.consequents.map(len)
    frame['itemset_length'] = frame.antecedent_length + frame.consequent_length
    frame['invoice_count'] = [int(counts[a | c]) for a, c in zip(frame.antecedent_mask, frame.consequent_mask)]
    # Compare every nonempty proper antecedent subset with the same consequent,
    # even if that simpler rule failed the reporting confidence threshold.
    best = []
    for a, c in zip(frame.antecedent_mask, frame.consequent_mask):
        sub, values = (a-1) & a, []
        while sub:
            values.append(counts[sub | c] / counts[sub])
            sub = (sub-1) & a
        best.append(max(values) if values else np.nan)
    frame['best_simpler_confidence'] = best
    frame['confidence_gain_over_simpler'] = frame.confidence - frame.best_simpler_confidence
    frame['redundant_by_confidence'] = frame.confidence_gain_over_simpler.le(1e-12)
    frame['positive_association'] = frame.lift.gt(1 + 1e-12) & frame.leverage.gt(0)
    frame['baseline_thresholds'] = frame.support.ge(.03) & frame.confidence.ge(.50)
    frame['highlight_eligible'] = frame.baseline_thresholds & frame.lift.ge(1.10) & ~frame.redundant_by_confidence
    frame['antecedents'] = frame.antecedent_mask.map(lambda m: encode(m, categories))
    frame['consequents'] = frame.consequent_mask.map(lambda m: encode(m, categories))
    return frame.sort_values(['antecedent_mask', 'consequent_mask']).reset_index(drop=True)


def run():
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        raise RuntimeError('Use the project virtual environment')
    required = ['frequent_itemsets_high.csv', 'frequent_itemsets_high_medium.csv', 'association_rules_high.csv',
                'association_rules_high_medium.csv', 'apriori_model_comparison.csv']
    if any((T / name).exists() for name in required) or (R / 'apriori_analysis_report.md').exists():
        raise FileExistsError('Phase 7 artifacts already exist; version outputs instead of overwriting')
    protected = [p for folder in ['data', 'docs', 'outputs', 'src'] for p in (ROOT / folder).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.name != Path(__file__).name]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    checks = {}
    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise AssertionError(name)
    for manifest_name, field in [('feature_engineering_manifest.json', 'output_hashes'), ('kmeans_validation.json', 'output_sha256')]:
        prior = json.loads((R / manifest_name).read_text())
        for path, digest in prior[field].items():
            check('hash_' + path, sha(ROOT / path) == digest)
    phase5coverage = pd.read_csv(T / 'apriori_coverage_comparison.csv').set_index('variant')
    phase5frequencies = pd.read_csv(T / 'apriori_category_comparison.csv')
    assignments = pd.read_csv(T / 'kmeans_cluster_assignments.csv', dtype={'Invoice': str})
    frames, counts_by_variant, mask_by_variant = {}, {}, {}
    coverage, frequencies, itemsets_by_variant, all_rules = [], [], {}, {}
    experiment_rows, threshold_rule_ids = [], {}
    for variant, filename in [('high', 'apriori_basket_high_confidence.csv.gz'), ('high_medium', 'apriori_basket_high_medium.csv.gz')]:
        raw = pd.read_csv(T / filename, dtype={'Invoice': str}, keep_default_na=False)
        check(variant + '_shape_unique', raw.shape == (N, 15) and raw.Invoice.is_unique and raw.Invoice.ne('').all())
        binary = raw.set_index('Invoice')
        check(variant + '_unique_categories', binary.columns.is_unique)
        check(variant + '_strict_binary_no_missing', binary.notna().all().all() and binary.isin([0, 1]).all().all())
        binary = binary.astype(bool)
        if frames:
            check('aligned_invoices_categories', binary.index.equals(frames['high'].index) and binary.columns.equals(frames['high'].columns))
            check('high_medium_cellwise_superset', (~frames['high'] | binary).all().all())
        check(variant + '_phase6_invoice_universe', set(raw.Invoice) == set(assignments.Invoice) and assignments.Invoice.is_unique)
        empty = int(binary.sum(axis=1).eq(0).sum())
        check(variant + '_empty_baskets_preserved', empty == int(phase5coverage.loc[variant, 'empty_invoices_retained']))
        check(variant + '_unique_invoice_category_pairs', int(binary.to_numpy().sum()) == int(phase5coverage.loc[variant, 'unique_invoice_category_pairs']))
        oldfreq = phase5frequencies[phase5frequencies.variant.eq(variant)].set_index('category').invoices_with_category
        check(variant + '_frequency_agrees_phase5', binary.sum().eq(oldfreq.reindex(binary.columns)).all())
        categories = binary.columns.tolist()
        frames[variant] = binary
        counts, invoice_masks = count_supersets(binary)
        counts_by_variant[variant], mask_by_variant[variant] = counts, invoice_masks
        check(variant + '_oracle_denominator', counts[0] == N)
        coverage.append(dict(variant=variant, invoices=N, categories=len(categories), empty_baskets=empty,
                             nonempty_baskets=N-empty, single_category_baskets=int(binary.sum(axis=1).eq(1).sum()),
                             unique_invoice_category_pairs=int(binary.to_numpy().sum())))
        frequencies.extend(dict(variant=variant, category=c, invoice_count=int(binary[c].sum()), support=float(binary[c].mean())) for c in categories)
        for support in SUPPORTS:
            print(f'Mining {variant}: support={support}', flush=True)
            frequent = apriori(binary, min_support=support, use_colnames=True, max_len=None, low_memory=True)
            fmasks = frequent.itemsets.map(lambda s: mask_of(s, categories)).to_numpy(dtype=int)
            check(f'{variant}_{support}_all_itemsets_exact', np.allclose(frequent.support, counts[fmasks]/N, atol=1e-12, rtol=1e-12))
            expected = set(np.flatnonzero(counts / N >= support)) - {0}
            check(f'{variant}_{support}_complete_itemsets', set(fmasks) == expected and len(fmasks) == len(expected))
            rules = rules_for(frequent)
            if support == .01:
                enriched = enrich_rules(rules, counts, categories)
                all_rules[variant] = enriched
                export = pd.DataFrame({'itemset_mask': fmasks, 'itemsets': [encode(m, categories) for m in fmasks],
                                       'length': [int(m).bit_count() for m in fmasks], 'support': frequent.support,
                                       'invoice_count': counts[fmasks], 'transaction_denominator': N})
                export = export.sort_values(['length', 'itemset_mask']).reset_index(drop=True)
                itemsets_by_variant[variant] = export
                export.to_csv(T / f'frequent_itemsets_{variant}.csv', index=False)
                enriched.to_csv(T / f'association_rules_{variant}.csv', index=False)
                # Validate all rule metrics from independent integer counts.
                a = enriched.antecedent_mask.to_numpy(dtype=int)
                c = enriched.consequent_mask.to_numpy(dtype=int)
                sa, sc, sac = counts[a]/N, counts[c]/N, counts[a | c]/N
                conf = sac / sa
                with np.errstate(divide='ignore', invalid='ignore'):
                    conv = (1-sc)/(1-conf)
                conv[conf >= 1] = np.inf
                expected_metrics = [sa, sc, sac, conf, conf/sc, sac-sa*sc, conv]
                for metric, values in zip(METRICS, expected_metrics):
                    check(variant + '_metric_' + metric, np.allclose(enriched[metric], values, rtol=1e-10, atol=1e-12, equal_nan=False))
                check(variant + '_rules_unique_disjoint', enriched.rule_id.is_unique and ((a & c) == 0).all())
                check(variant + '_rule_confidence_floor', enriched.confidence.ge(.30-1e-12).all())
                check(variant + '_finite_nonconviction_metrics', np.isfinite(enriched[METRICS[:-1]].to_numpy()).all())
                for file, original in [(f'frequent_itemsets_{variant}.csv', export), (f'association_rules_{variant}.csv', enriched)]:
                    reloaded = pd.read_csv(T / file)
                    pd.testing.assert_frame_equal(original, reloaded, check_dtype=False, rtol=1e-10, atol=1e-12)
                    check('reload_' + file, True)
            for confidence in CONFIDENCES:
                selected = rules[rules.confidence.ge(confidence)]
                ids = {f'{mask_of(a, categories)}->{mask_of(c, categories)}' for a, c in zip(selected.antecedents, selected.consequents)}
                threshold_rule_ids[(variant, support, confidence)] = ids
                base = all_rules[variant]
                expected_ids = set(base.loc[base.support.ge(support) & base.confidence.ge(confidence), 'rule_id'])
                check(f'{variant}_{support}_{confidence}_rule_filter_equivalence', ids == expected_ids)
                experiment_rows.append(dict(variant=variant, min_support=support, min_confidence=confidence, transaction_denominator=N,
                    frequent_itemsets=len(frequent), max_itemset_length=int(frequent.itemsets.map(len).max()), rules=len(selected),
                    max_rule_itemset_length=MAX_RULE_ITEMS,
                    positive_rules=int(selected.lift.gt(1+1e-12).sum()), lift_ge_1_10=int(selected.lift.ge(1.10).sum()),
                    median_support=float(selected.support.median()), median_confidence=float(selected.confidence.median()),
                    median_lift=float(selected.lift.median()), max_lift=float(selected.lift.max()),
                    median_leverage=float(selected.leverage.median()), infinite_conviction=int(np.isinf(selected.conviction).sum())))
        # Independent repeat of the default lowest-support mining establishes deterministic outputs.
        repeat = apriori(binary, min_support=.01, use_colnames=True, max_len=None, low_memory=True)
        check(variant + '_repeat_apriori', set(repeat.itemsets.map(lambda s: mask_of(s, categories))) == set(itemsets_by_variant[variant].itemset_mask))
    comparison = pd.DataFrame(experiment_rows)
    comparison.to_csv(T / 'apriori_model_comparison.csv', index=False)
    pd.DataFrame(coverage).to_csv(T / 'phase7_basket_validation.csv', index=False)
    pd.DataFrame(frequencies).to_csv(T / 'phase7_category_frequencies.csv', index=False)
    stability_rows = []
    for support in SUPPORTS:
        for confidence in CONFIDENCES:
            h, hm = [threshold_rule_ids[(v, support, confidence)] for v in ['high', 'high_medium']]
            stability_rows.append(dict(min_support=support, min_confidence=confidence, shared_rules=len(h & hm),
                high_only=len(h-hm), high_medium_only=len(hm-h), union_rules=len(h | hm), jaccard=len(h & hm)/len(h | hm) if h | hm else 1.0))
    stability = pd.DataFrame(stability_rows)
    stability.to_csv(T / 'phase7_rule_threshold_stability.csv', index=False)
    columns = ['rule_id', 'antecedents', 'consequents', 'support', 'confidence', 'lift', 'leverage', 'baseline_thresholds', 'highlight_eligible']
    matched = all_rules['high'][columns].merge(all_rules['high_medium'][columns], on='rule_id', how='outer', suffixes=('_high', '_high_medium'), indicator=True)
    for metric in ['support', 'confidence', 'lift', 'leverage']:
        matched[metric + '_change'] = matched[metric + '_high_medium'] - matched[metric + '_high']
    matched.to_csv(T / 'phase7_rule_variant_comparison.csv', index=False)
    top_by_variant, evidence = {}, []
    for variant, rules in all_rules.items():
        # Keep complicated rules in full exports; readable figures use directional pairs.
        top = rules[rules.highlight_eligible & rules.itemset_length.eq(2)].sort_values(['lift', 'support', 'rule_id'], ascending=[False, False, True]).head(10)
        top_by_variant[variant] = top
        for row in top.itertuples():
            union = row.antecedent_mask | row.consequent_mask
            invoice_ids = frames[variant].index[(mask_by_variant[variant] & union) == union]
            check(f'{variant}_evidence_{row.rule_id}', len(invoice_ids) == row.invoice_count)
            evidence.extend({'variant': variant, 'rule_id': row.rule_id, 'Invoice': inv} for inv in invoice_ids)
    pd.concat([d.assign(variant=v) for v, d in top_by_variant.items()], ignore_index=True).to_csv(T / 'phase7_highlighted_pair_rules.csv', index=False)
    pd.DataFrame(evidence).to_csv(T / 'phase7_highlighted_rule_invoice_evidence.csv.gz', index=False)
    # Six requested visualization types; all figure filters are explicit.
    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    for ax, (variant, items) in zip(axes, itemsets_by_variant.items()):
        top = items[items.length.ge(2)].nlargest(8, 'support').sort_values('support')
        ax.barh([fill(names(m, categories), 40) for m in top.itemset_mask], top.support)
        ax.set(title=variant, xlabel='Support / all 39,516 invoices')
    fig.suptitle('Most frequent category combinations (length ≥2; mined support ≥1%)')
    fig.tight_layout(); fig.savefig(G / 'phase7_frequent_combinations.png', dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, (variant, rules) in zip(axes, all_rules.items()):
        # All rules, no sampling; lift color scale fixed across variants.
        dots = ax.scatter(rules.support, rules.confidence, c=rules.lift, cmap='viridis', s=5, alpha=.35,
                          vmin=0, vmax=max(r.lift.max() for r in all_rules.values()), rasterized=True)
        ax.set(title=variant, xlabel='Support', ylabel='Confidence')
        ax.axvline(.03, ls='--', color='gray'); ax.axhline(.5, ls='--', color='gray')
    fig.colorbar(dots, ax=axes.tolist(), label='Lift', shrink=.8)
    fig.suptitle('Exported rules: 2–4 categories, support ≥1%, confidence ≥30% (dashes: baseline)')
    fig.subplots_adjust(top=.86, bottom=.14, wspace=.25, right=.84)
    fig.savefig(G / 'phase7_support_confidence.png', dpi=140); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5))
    edges = np.linspace(0, max(r.lift.max() for r in all_rules.values()), 45)
    for variant, rules in all_rules.items():
        ax.hist(rules.lift, bins=edges, histtype='step', linewidth=2, label=variant)
    ax.axvline(1, color='black', ls='--'); ax.legend()
    ax.set(title='Lift distribution — exported rules with 2–4 categories', xlabel='Lift', ylabel='Rule count')
    fig.tight_layout(); fig.savefig(G / 'phase7_lift_distribution.png', dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(17, 8))
    for ax, (variant, top) in zip(axes, top_by_variant.items()):
        top = top.sort_values('lift')
        labels = [fill(names(a, categories)+' → '+names(c, categories), 44) for a, c in zip(top.antecedent_mask, top.consequent_mask)]
        ax.barh(labels, top.lift)
        ax.axvline(1, color='gray', ls='--')
        ax.set(title=variant, xlabel='Lift')
    fig.suptitle('Top directional pair rules: support ≥3%, confidence ≥50%, lift ≥1.10')
    fig.tight_layout(); fig.savefig(G / 'phase7_top_rules.png', dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(16, 9))
    for ax, (variant, top) in zip(axes, top_by_variant.items()):
        angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False)
        pos = {1 << i: np.array([np.cos(a), np.sin(a)]) for i, a in enumerate(angles)}
        for row in top.itertuples():
            arrow = FancyArrowPatch(pos[row.antecedent_mask], pos[row.consequent_mask], arrowstyle='-|>',
                connectionstyle='arc3,rad=0.12', mutation_scale=14, linewidth=1+row.support*8, color='#267a9b', alpha=.6, shrinkA=10, shrinkB=10)
            ax.add_patch(arrow)
        for i, category in enumerate(categories):
            p = pos[1 << i]
            ax.scatter(*p, s=90, color='#db8c45')
            ax.text(*(p*1.19), str(i+1), ha='center', va='center', fontsize=11)
        ax.set(title=variant, xlim=(-1.4, 1.4), ylim=(-1.4, 1.4), aspect='equal'); ax.axis('off')
    legend = '\n'.join(f'{i+1}. {c}' for i,c in enumerate(categories))
    fig.text(.5, .02, legend, ha='center', fontsize=9)
    fig.suptitle('Top 10 pair rules per variant; arrows show rule direction, not causation\nSupport ≥3%, confidence ≥50%, lift ≥1.10; edge width reflects support')
    fig.subplots_adjust(bottom=.34, top=.85)
    fig.savefig(G / 'phase7_category_network.png', dpi=140); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5))
    for offset, (variant, items) in zip([-.18, .18], itemsets_by_variant.items()):
        ct = items.groupby('length').size()
        ax.bar(ct.index+offset, ct.values, width=.36, label=variant)
    ax.set(title='Frequent itemset lengths at minimum support 1% (no length cap)', xlabel='Number of categories', ylabel='Itemset count')
    ax.legend(); fig.tight_layout(); fig.savefig(G / 'phase7_itemset_lengths.png', dpi=140); plt.close(fig)
    baseline = comparison[comparison.min_support.eq(.03) & comparison.min_confidence.eq(.50)]
    base_stability = stability[stability.min_support.eq(.03) & stability.min_confidence.eq(.50)].iloc[0]
    shared = matched[matched._merge.eq('both')]
    # Recount identical highlighted rules under both variants, even if one misses export thresholds.
    important_ids = sorted(set().union(*(set(t.rule_id) for t in top_by_variant.values())))
    important_rows = []
    for rid in important_ids:
        a,c = map(int, rid.split('->'))
        row = {'rule_id': rid, 'antecedents': encode(a,categories), 'consequents': encode(c,categories)}
        for variant, counts in counts_by_variant.items():
            sa, sc, sac = counts[a]/N, counts[c]/N, counts[a|c]/N
            row.update({f'support_{variant}': sac, f'confidence_{variant}': sac/sa, f'lift_{variant}': sac/(sa*sc),
                        f'baseline_positive_{variant}': bool(sac >= .03 and sac/sa >= .5 and sac/(sa*sc) >= 1.1)})
        important_rows.append(row)
    important = pd.DataFrame(important_rows)
    important.to_csv(T / 'phase7_important_rule_stability.csv', index=False)
    interpretations = []
    for variant, top in top_by_variant.items():
        # Avoid reporting a reversed pair twice in prose.
        seen = set()
        for row in top.sort_values(['lift', 'support'], ascending=False).itertuples():
            union = row.antecedent_mask | row.consequent_mask
            if union in seen:
                continue
            seen.add(union)
            interpretations.append(f'- **{variant}: {names(row.antecedent_mask,categories)} → {names(row.consequent_mask,categories)}**. '
                f'The combination occurs in {row.invoice_count:,} invoices ({row.support:.2%} of all invoices). '
                f'Among invoices containing the antecedent, {row.confidence:.2%} also contain the consequent; '
                f'this is {row.lift:.3f} times its overall invoice prevalence. Leverage is {row.leverage:.4f}. '
                'This may inform a merchandising hypothesis, but does not establish that buying one causes the other.')
            if len(seen) == 3:
                break
    preservation = {p: {'before': h, 'after': sha(ROOT/p)} for p,h in before.items()}
    check('all_prior_files_unchanged', all(v['before'] == v['after'] for v in preservation.values()))
    parameters = {'support_thresholds': SUPPORTS, 'confidence_thresholds': CONFIDENCES, 'max_len': None, 'low_memory': True,
        'max_rule_itemset_length':MAX_RULE_ITEMS,
        'reporting_baseline': {'min_support': .03, 'min_confidence': .50, 'highlight_min_lift': 1.10},
        'export_floor': {'min_support': .01, 'min_confidence': .30}, 'transaction_denominator': N,
        'empty_baskets_retained': True, 'category_order': categories, 'randomness': 'none; deterministic mining, sorting and circular network layout',
        'redundancy': 'same consequent, nonempty proper antecedent subset with confidence >= current confidence within 1e-12',
        'metric_definitions': {'support':'n(A union B)/N', 'confidence':'n(A union B)/n(A)', 'lift':'confidence / support(B)',
            'leverage':'support(A union B) - support(A)*support(B)', 'conviction':'(1-support(B))/(1-confidence); +inf for confidence=1'},
        'source_lineage': {'baskets': ['outputs/tables/apriori_basket_high_confidence.csv.gz','outputs/tables/apriori_basket_high_medium.csv.gz'],
            'invoice_to_source_rows': 'outputs/tables/integrated_purchase_lines.csv.gz (Invoice, source_id, source_sheet, source_row and original descriptions retained)',
            'highlight_evidence': 'outputs/tables/phase7_highlighted_rule_invoice_evidence.csv.gz'},
        'versions': {'python':sys.version, 'mlxtend': mlxtend.__version__, 'pandas': pd.__version__, 'numpy': np.__version__},
        'script_sha256':sha(Path(__file__)), 'phase8_cluster_comparisons_performed':False}
    dump(R / 'phase7_apriori_parameters.json', parameters)
    report = f'''# Phase 7 — Global Apriori category associations

Generated {datetime.now(timezone.utc).isoformat()}. No cluster-wise comparison or dashboard has been performed.

## Data verification and denominator

Both input matrices have **39,516 unique invoice rows × 14 unique category columns**. Values were strictly 0/1 with no missing cells before Boolean conversion. Invoice order and category order match across variants; the High matrix is a cell-wise subset of High+Medium. Invoice sets match Phase 6 assignments, but cluster labels were not used in mining. Unique row and column keys give one cell per invoice-category combination; repeated purchase lines do not increase presence. Column counts agree with Phase 5.

{markdown(pd.DataFrame(coverage))}

**Every support denominator is 39,516, including empty baskets and anonymous-customer invoices.** Support is not divided by the number of nonempty baskets. A zero means no qualifying category was observed: it does not prove absence when descriptions or confidence were insufficient. Other/Unclassified is not an invented item. Source purchase eligibility remains exactly Phase 3 policy. Original descriptions, StockCodes and source worksheet/row references remain unchanged in the integrated purchase-line file. Highlighted rule evidence supplies matching invoice IDs, which join back to those original references.

## Methods and parameters

Used mlxtend {mlxtend.__version__} `apriori` and `association_rules`. Apriori was run separately at minimum support 1%, 2%, 3%, 5% in each variant, with no frequent-itemset-length cap and low_memory=True. Rule generation is explicitly limited to **2–4 total categories** (antecedent plus consequent). Within that scope, rules were generated at confidence 30%, then filtered exactly to 40%, 50%, 60%. This produces the same threshold-qualified rules without repeating identical enumeration. The comparison table has 32 rows. All frequent itemsets at 1% and all 2–4-category rules at support ≥1%, confidence ≥30% are exported once per variant; threshold columns and masks make filtering reproducible.

An initial unrestricted High-confidence search generated 9,901 frequent itemsets and 1,155,259 rules at the lowest thresholds, including lengthy conjunctions. Its incomplete run artifacts were preserved under `outputs/phase7_unrestricted_exploration/`. The four-category rule limit was then adopted for interpretability and practical reproducibility, not to optimize association scores or change support thresholds. Higher-order frequent itemsets remain fully exported and validated; the final rule counts and comparisons do **not** claim exhaustive coverage of rules involving five or more categories. This scope decision was made before inspecting the completed cross-variant results.

Minimum supporting invoice counts are {', '.join(f'{s:.0%}: {int(np.ceil(N*s)):,}' for s in SUPPORTS)}. The reporting baseline is **support ≥3%, confidence ≥50%**: at least {int(np.ceil(N*.03)):,} invoices and presence in at least half the antecedent baskets. Highlighted positive rules additionally require lift ≥1.10 and no confidence redundancy. These are transparent practical reporting choices, not learned optimal thresholds or statistical significance cutoffs. The full grid remains available; thresholds were not chosen to maximize rule counts. Rare categories below 1% cannot appear in these frequent itemsets; no absence-of-association claim follows.

Support = n(A∪B)/N; confidence = n(A∪B)/n(A); lift = confidence/support(B); leverage = support(A∪B)−support(A)support(B); conviction = (1−support(B))/(1−confidence). Infinite conviction is legitimate when confidence=1 and is preserved, not imputed. Missing simpler-rule confidence in single-antecedent rules means not applicable. High confidence can merely reflect a popular consequent: lift ≤1 is flagged as not a positive association. No rule is discarded from the comprehensive export because it is uninteresting.

## Threshold comparison

{markdown(comparison[['variant','min_support','min_confidence','frequent_itemsets','rules','positive_rules','median_lift','max_lift']])}

Baseline summary:

{markdown(baseline[['variant','frequent_itemsets','rules','median_support','median_confidence','median_lift','max_lift']])}

## Classification-variant sensitivity

At the baseline, **{int(base_stability.shared_rules):,} rules are shared**, {int(base_stability.high_only):,} appear only in High and {int(base_stability.high_medium_only):,} only in High+Medium; rule-set Jaccard is **{base_stability.jaccard:.4f}**. These differences mean failing a threshold in one variant, not necessarily zero co-occurrence. Across the lowest-threshold shared exports, median support change is {shared.support_change.median():.6f}, median confidence change {shared.confidence_change.median():.6f}, median lift change {shared.lift_change.median():.6f}; positive changes mean High+Medium minus High. Metrics are computed on matched rule identities, not unmatched averages. The important-rule table independently recounts highlighted identities in both variants, including rules below export thresholds.

Adding Medium-confidence products can increase joint support while changing antecedent and consequent prevalence, so confidence and lift can rise or fall. It is a classification sensitivity experiment on the same invoices, not independent replication. High confidence is a description-evidence label, not measured classification accuracy; Medium assignments remain provisional. Neither variant proves handmade provenance.

## Readable positive associations

The following highlights use simple one-category → one-category rules to avoid opaque long conjunctions. Full multivariate rules remain in the exports.

{chr(10).join(interpretations)}

## Redundancy, limitations and interpretation

A rule is flagged confidence-redundant when a nonempty proper subset of its antecedent, with the same consequent, has confidence at least as high (tolerance 1e-12). This examines all simpler antecedents, even below the export confidence threshold. High: {int(all_rules['high'].redundant_by_confidence.sum()):,} flagged rules; High+Medium: {int(all_rules['high_medium'].redundant_by_confidence.sum()):,}. This is a practical redundancy screen, not an exhaustive logical rule basis. Reverse rules are distinct conditional statements; network arrows indicate direction of the statement, never causal influence.

Lift, leverage and adequate support provide context for confidence. Even strong observed associations may reflect broad baskets, shared merchandising, seasonal effects or other confounding. This phase uses the full dataset descriptively; no held-out, bootstrap, temporal or causal validation is claimed. Large numbers of searched rules increase discovery bias; no p-values or formal significance claims are made. Negative-lift rules are preserved but the mining thresholds are not designed for exhaustive negative-association discovery. Empty and partially classified baskets affect observed supports. Statistical strength does not establish business profitability, craft provenance or causation.

## Figures and validation

Six figures cover frequent combinations (length ≥2), all-rule support/confidence, lift distributions, top positive pair rules, a directed category network, and itemset lengths. Top-rule/network plots use the reporting baseline and at most 10 directional pairs per variant; other chart scopes are explicitly labelled. Deterministic circular node positions avoid implying spatial similarity.

All **{len(checks)} checks passed**. An independent 14-bit basket histogram and exact superset-count calculation validated every frequent-itemset support and completeness at every support threshold, and all exported support/confidence/lift/leverage/conviction values. Exported itemsets/rules were reloaded and compared. Threshold filters, pair evidence, repeated Apriori runs, input hashes and all earlier artifacts were checked. All **{len(preservation)} protected files** have unchanged SHA-256, including raw Excel and Phase 3–6 artifacts. No invoices were removed and no earlier files were edited.

Required files are in `outputs/tables/`; parameters are in `outputs/reports/phase7_apriori_parameters.json`, validation and hashes in `phase7_apriori_validation.json`, and code in `src/apriori_analysis.py`. Itemsets are serialized as JSON arrays; masks use the recorded category order. Missing values after the outer variant comparison mean a rule was below export thresholds in one variant, not an invented zero. Source references remain local.

References: [mlxtend Apriori](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/apriori/), [mlxtend association rules and metric definitions](https://rasbt.github.io/mlxtend/user_guide/frequent_patterns/association_rules/).

**Phase 7 complete. Stop for explicit approval before Phase 8.**
'''
    (R / 'apriori_analysis_report.md').write_text(report, encoding='utf-8')
    outputs = [T/n for n in required] + [R/'apriori_analysis_report.md']
    outputs += [p for folder in [T,R,G] for p in folder.glob('phase7_*') if p.is_file()]
    dump(R / 'phase7_apriori_validation.json', {'checks': checks, 'all_passed': all(checks.values()), 'preservation': preservation,
         'output_sha256': {str(p.relative_to(ROOT)):sha(p) for p in outputs}})
    print('BASELINE\n'+baseline.to_string(index=False), flush=True)
    print('STABILITY', base_stability.to_dict(), flush=True)
    print('CHECKS',len(checks),'PROTECTED',len(preservation), flush=True)
    print('\n'.join(interpretations), flush=True)


if __name__ == '__main__':
    # Windows redirected consoles may default to cp1252; reports use UTF-8.
    sys.stdout.reconfigure(encoding='utf-8')
    run()
