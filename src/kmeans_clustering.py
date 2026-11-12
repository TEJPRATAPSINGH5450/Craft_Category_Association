"""Phase 6 only: reproducible invoice K-Means experiments and validation.

Run with .venv/Scripts/python.exe src/kmeans_clustering.py.
Existing artifacts are never overwritten. No earlier-phase files are edited.
"""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
os.environ.setdefault('OMP_NUM_THREADS', '2')
import json
import hashlib
import itertools
import sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import joblib
import sklearn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, RobustScaler, FunctionTransformer
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score, adjusted_rand_score
from threadpoolctl import threadpool_limits

T = ROOT / 'outputs/tables'
R = ROOT / 'outputs/reports'
G = ROOT / 'outputs/graphs'
M = ROOT / 'outputs/models'
FEATURES = ['total_quantity', 'total_purchase_value', 'unique_product_count', 'product_diversity']
VARIANTS = ['standard', 'robust', 'log_standard', 'log_robust']
SEEDS = [42, 7, 19, 83, 2026]


def sha(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest().upper()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, default=str, allow_nan=False), encoding='utf-8')


def transform(features, variant):
    logged = [c for c in features if c != 'product_diversity'] if variant.startswith('log_') else []
    other = [c for c in features if c not in logged]
    parts = []
    if logged:
        parts.append(('log1p', FunctionTransformer(np.log1p, feature_names_out='one-to-one'), logged))
    if other:
        parts.append(('unchanged', 'passthrough', other))
    return Pipeline([('columns', ColumnTransformer(parts, remainder='drop', verbose_feature_names_out=False)),
                     ('scale', RobustScaler() if 'robust' in variant else StandardScaler())])


def model(k, seed=42):
    return KMeans(n_clusters=int(k), init='k-means++', n_init=20,
                  max_iter=500, tol=1e-4, random_state=seed, algorithm='lloyd')


def table(df):
    # No optional tabulate dependency required.
    return '| ' + ' | '.join(map(str, df.columns)) + ' |\n| ' + ' | '.join(['---'] * len(df.columns)) + ' |\n' + '\n'.join(
        '| ' + ' | '.join(f'{v:.5g}' if isinstance(v, float) else str(v) for v in row) + ' |' for row in df.itertuples(index=False, name=None))


def run():
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        raise RuntimeError('Run in the project virtual environment')
    if any(p.name.startswith(('kmeans_', 'phase6_')) for folder in [T, R, G, M] if folder.exists() for p in folder.iterdir()):
        raise FileExistsError('Phase 6 outputs exist. Version outputs before another run.')
    M.mkdir(exist_ok=True)
    protected = [p for folder in ['data', 'docs', 'outputs', 'src'] for p in (ROOT / folder).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.name != Path(__file__).name]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    checks = {}
    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            raise AssertionError(name)
    manifest5 = json.loads((R / 'feature_engineering_manifest.json').read_text())
    for path, digest in manifest5['output_hashes'].items():
        check('phase5_hash_' + path, sha(ROOT / path) == digest)
    raw = pd.read_csv(T / 'invoice_features_raw.csv.gz', dtype={'Invoice': str, 'customer_id': str}, keep_default_na=False)
    check('39516_unique_invoices', len(raw) == 39516 and raw.Invoice.is_unique and raw.Invoice.ne('').all())
    check('all_purchase_lines', raw.line_count.sum() == 1015214)
    check('numeric_finite_complete', np.isfinite(raw[FEATURES].to_numpy(dtype=float)).all())
    check('positive_size_value', raw[FEATURES[:3]].gt(0).all().all())
    check('integer_product_count', raw.unique_product_count.mod(1).eq(0).all())
    check('diversity_bounds', raw.product_diversity.between(-1e-12, 1).all())
    check('one_product_zero_diversity', np.allclose(raw.loc[raw.unique_product_count.eq(1), 'product_diversity'], 0, atol=1e-12))
    check('simpson_upper_bound', (raw.product_diversity <= 1 - 1 / raw.unique_product_count + 1e-12).all())
    config5 = json.loads((R / 'feature_transformations.json').read_text())
    check('phase5_feature_definition', config5['selected_features'] == FEATURES)
    for variant in VARIANTS:
        prep = transform(FEATURES, variant)
        x = prep.fit_transform(raw)
        saved = pd.read_csv(T / f'invoice_features_{variant}.csv.gz', dtype={'Invoice': str})
        check('invoice_order_' + variant, saved.Invoice.equals(raw.Invoice))
        check('reproduced_phase5_' + variant, np.allclose(x, saved[FEATURES], rtol=1e-10, atol=1e-10))
    corr = raw[FEATURES].corr(method='spearman')
    corr.to_csv(T / 'kmeans_feature_spearman.csv')
    rho = float(corr.loc['unique_product_count', 'product_diversity'])
    # Primary choice made before observing clustering scores: avoid double weighting basket variety.
    sets = {'primary_three': FEATURES[:3], 'sensitivity_four': FEATURES}
    sample = np.sort(np.random.default_rng(2026).choice(len(raw), 2000, replace=False))
    pd.DataFrame({'Invoice': raw.Invoice.iloc[sample]}).to_csv(T / 'kmeans_silhouette_sample.csv', index=False)
    rows, cache = [], {}
    with threadpool_limits(limits=2):
        for set_name, features in sets.items():
            for variant in VARIANTS:
                prep = transform(features, variant)
                x = prep.fit_transform(raw)
                cache[(set_name, variant)] = (prep, x)
                for k in range(2, 11):
                    km = model(k).fit(x)
                    labels = km.labels_
                    counts = np.bincount(labels, minlength=k)
                    sample_k = np.unique(labels[sample]).size
                    sil = float(silhouette_score(x[sample], labels[sample])) if 1 < sample_k < len(sample) else np.nan
                    rows.append(dict(feature_set=set_name, variant=variant, k=k, inertia=km.inertia_, silhouette=sil,
                                     davies_bouldin=davies_bouldin_score(x, labels), calinski_harabasz=calinski_harabasz_score(x, labels),
                                     min_cluster=int(counts.min()), max_cluster=int(counts.max()), min_cluster_pct=100*counts.min()/len(raw),
                                     max_cluster_pct=100*counts.max()/len(raw), sample_clusters=sample_k, silhouette_sample_size=len(sample),
                                     n_iter=km.n_iter_, converged=km.n_iter_ < 500, seed=42, n_init=20))
                    print(f'{set_name} {variant} K={k}: silhouette={sil:.4f}, smallest={counts.min()}', flush=True)
    results = pd.DataFrame(rows)
    # Normalized elbow distance from the line joining K=2 and K=10, within each geometry only.
    for _, part in results.groupby(['feature_set', 'variant']):
        y = (part.inertia - part.inertia.iloc[-1]) / (part.inertia.iloc[0] - part.inertia.iloc[-1])
        results.loc[part.index, 'elbow_distance'] = (1 - (part.k - 2)/8) - y
    results['eligible_primary'] = (results.feature_set.eq('primary_three') & results.min_cluster_pct.ge(1)
                                   & results.sample_clusters.eq(results.k) & results.converged)
    eligible = results.loc[results.eligible_primary].copy()
    if eligible.empty:
        raise RuntimeError('No candidate meets documented minimum 1% cluster size; review results before selecting.')
    for metric, ascending in [('silhouette', False), ('davies_bouldin', True), ('calinski_harabasz', False), ('elbow_distance', False)]:
        eligible['rank_' + metric] = eligible[metric].rank(ascending=ascending, method='min')
    eligible['selection_rank_sum'] = eligible.filter(like='rank_').sum(axis=1)
    best = eligible.sort_values(['selection_rank_sum', 'k', 'variant']).iloc[0]
    results = results.merge(eligible[['feature_set', 'variant', 'k', 'selection_rank_sum']], how='left', on=['feature_set', 'variant', 'k'])
    results.to_csv(T / 'kmeans_model_comparison.csv', index=False)
    eligible.sort_values('selection_rank_sum').to_csv(T / 'kmeans_selection_ranking.csv', index=False)
    variant, k = str(best.variant), int(best.k)
    prep, x = cache[('primary_three', variant)]
    with threadpool_limits(limits=2):
        km = model(k).fit(x)
        labels = km.labels_
        repeat = model(k).fit(x)
        check('same_seed_exact_labels', np.array_equal(labels, repeat.labels_))
        check('same_seed_centers', np.array_equal(km.cluster_centers_, repeat.cluster_centers_))
        stability_models = {42: km}
        for seed in SEEDS[1:]:
            stability_models[seed] = model(k, seed).fit(x)
        stability = pd.DataFrame([{'seed_a': a, 'seed_b': b, 'adjusted_rand_index': adjusted_rand_score(stability_models[a].labels_, stability_models[b].labels_)}
                                  for a, b in itertools.combinations(SEEDS, 2)])
        stability.to_csv(T / 'kmeans_seed_stability.csv', index=False)
        pd.DataFrame([{'seed': seed, 'inertia': mdl.inertia_, 'n_iter': mdl.n_iter_} for seed, mdl in stability_models.items()]).to_csv(T / 'kmeans_seed_runs.csv', index=False)
        sensitivity_model = model(k).fit(cache[('sensitivity_four', variant)][1])
        ablation_ari = adjusted_rand_score(labels, sensitivity_model.labels_)
        # Repeat sampled silhouette with independent samples to disclose sampling sensitivity.
        sample_scores = []
        for seed in SEEDS:
            ix = np.random.default_rng(seed).choice(len(raw), 2000, replace=False)
            sample_scores.append({'seed': seed, 'sample_size': len(ix), 'clusters_represented': np.unique(labels[ix]).size,
                                  'silhouette': silhouette_score(x[ix], labels[ix])})
    pd.DataFrame(sample_scores).to_csv(T / 'kmeans_silhouette_sensitivity.csv', index=False)
    pipeline = Pipeline([('preprocessing', prep), ('kmeans', km)])
    joblib.dump(pipeline, M / 'kmeans_model.joblib')
    loaded = joblib.load(M / 'kmeans_model.joblib')
    check('serialized_pipeline_predictions', np.array_equal(loaded.predict(raw), labels))
    assigned = pd.DataFrame({'Invoice': raw.Invoice, 'cluster': labels})
    profile_source = raw.assign(cluster=labels)
    profile = profile_source.groupby('cluster')[FEATURES + ['line_count', 'average_line_unit_price']].agg(['mean', 'median', 'std', 'min', 'max'])
    profile.columns = ['_'.join(c) for c in profile.columns]
    profile.insert(0, 'invoice_count', profile_source.groupby('cluster').size())
    profile.insert(1, 'invoice_percentage', profile.invoice_count / len(raw)*100)
    profile['purchase_lines'] = profile_source.groupby('cluster').line_count.sum()
    profile['anonymous_invoices'] = profile_source.groupby('cluster').anonymous_invoice.sum()
    # Names derived from relative median ranks, not inferred product/customer identities.
    ranks = profile[[f'{f}_median' for f in FEATURES[:3]]].rank(method='min', pct=True)
    def level(v):
        return 'lower' if v <= 1/3 else ('middle' if v <= 2/3 else 'higher')
    names = {i: f'{level(ranks.loc[i, "total_purchase_value_median"])} value / {level(ranks.loc[i, "unique_product_count_median"])} product variety (C{i})' for i in profile.index}
    profile.insert(0, 'cluster_name', pd.Series(names))
    assigned['cluster_name'] = assigned.cluster.map(names)
    assigned.to_csv(T / 'kmeans_cluster_assignments.csv', index=False)
    profile.to_csv(T / 'kmeans_cluster_profiles.csv')
    check('all_invoices_assigned_once', assigned.Invoice.is_unique and assigned.Invoice.equals(raw.Invoice) and assigned.cluster.notna().all())
    check('all_k_clusters', assigned.cluster.nunique() == k)
    check('profile_counts_reconcile', profile.invoice_count.sum() == len(raw) and profile.purchase_lines.sum() == 1015214)
    check('anonymous_retained', profile.anonymous_invoices.sum() == raw.anonymous_invoice.sum())
    saved_assignments = pd.read_csv(T / 'kmeans_cluster_assignments.csv', dtype={'Invoice': str, 'cluster': labels.dtype})
    pd.testing.assert_frame_equal(assigned, saved_assignments)
    check('saved_assignments_match', True)
    saved_profile = pd.read_csv(T / 'kmeans_cluster_profiles.csv', index_col='cluster', dtype={'cluster': labels.dtype})
    pd.testing.assert_frame_equal(profile, saved_profile, check_dtype=False, rtol=1e-12, atol=1e-12)
    check('saved_profiles_match', True)
    for metric, title in [('inertia', 'Elbow / within-cluster sum of squares'), ('silhouette', 'Sampled silhouette (2,000 fixed invoices)'),
                          ('davies_bouldin', 'Davies–Bouldin (all invoices)'), ('calinski_harabasz', 'Calinski–Harabasz (all invoices)')]:
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        for ax, set_name in zip(axes, sets):
            for var in VARIANTS:
                sub = results[(results.feature_set == set_name) & (results.variant == var)]
                values = sub[metric] / sub[metric].iloc[0] if metric == 'inertia' else sub[metric]
                ax.plot(sub.k, values, marker='o', label=var)
            ax.set(title=set_name, xlabel='K', ylabel='WCSS relative to K=2' if metric == 'inertia' else metric)
            ax.legend(fontsize=8)
        fig.suptitle(title)
        fig.tight_layout()
        fig.savefig(G / f'phase6_{metric}.png', dpi=150)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(profile.index.astype(str), profile.invoice_count)
    for i, row in profile.iterrows():
        ax.text(str(i), row.invoice_count, f'{int(row.invoice_count):,}\n({row.invoice_percentage:.1f}%)', ha='center', va='bottom')
    ax.set(xlabel='Cluster ID', ylabel='Invoices', title=f'Selected K={k}: invoice counts', ylim=(0, profile.invoice_count.max()*1.18))
    fig.tight_layout(); fig.savefig(G / 'phase6_cluster_sizes.png', dpi=150); plt.close(fig)
    pca = PCA(n_components=2, svd_solver='full').fit(x)
    points = pca.transform(x)
    fig, ax = plt.subplots(figsize=(9, 6))
    for c in range(k):
        ix = labels == c
        ax.scatter(points[ix, 0], points[ix, 1], s=4, alpha=.25, label=f'C{c}', rasterized=True)
    ax.set(xlabel=f'PC1 ({pca.explained_variance_ratio_[0]:.1%})', ylabel=f'PC2 ({pca.explained_variance_ratio_[1]:.1%})',
           title='PCA visualization only — K-Means fitted in 3D transformed space')
    ax.legend(markerscale=3)
    fig.tight_layout(); fig.savefig(G / 'phase6_pca.png', dpi=150); plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, feature in zip(axes.flat, FEATURES):
        pos = np.arange(k)
        ax.bar(pos-.2, profile[feature+'_mean'], width=.4, label='Mean')
        ax.bar(pos+.2, profile[feature+'_median'], width=.4, label='Median')
        ax.set(title=feature.replace('_', ' '), xlabel='Cluster ID', xticks=pos)
        ax.legend()
    fig.suptitle('Cluster profiles in original units (diversity is diagnostic only)')
    fig.tight_layout(); fig.savefig(G / 'phase6_feature_profiles.png', dpi=150); plt.close(fig)
    preservation = {path: {'before': digest, 'after': sha(ROOT / path)} for path, digest in before.items()}
    check('all_prior_artifacts_unchanged', all(v['before'] == v['after'] for v in preservation.values()))
    configuration = {'features': FEATURES[:3], 'diagnostic_excluded_feature': 'product_diversity', 'spearman_product_count_diversity': rho,
        'variant': variant, 'k': k, 'log1p_columns': FEATURES[:3] if variant.startswith('log_') else [],
        'scaler': type(prep.named_steps['scale']).__name__, 'scaler_center': getattr(prep.named_steps['scale'], 'center_', getattr(prep.named_steps['scale'], 'mean_', None)).tolist(),
        'scaler_scale': prep.named_steps['scale'].scale_.tolist(), 'kmeans_parameters': km.get_params(),
        'cluster_names': names, 'sample_size': 2000, 'main_sample_seed': 2026, 'stability_seeds': SEEDS,
        'selection': 'Primary three-feature set; clusters >=1% of invoices; full sampled label coverage; converged. Equal-weight rank sum: silhouette high, DB low, CH high, normalized elbow distance high. Tie: smaller K then variant name.',
        'fit_population': 'all 39516 invoices; descriptive in-sample analysis, not held-out generalization',
        'pca_explained_variance_ratio': pca.explained_variance_ratio_.tolist(), 'four_feature_ari_same_variant_k': float(ablation_ari),
        'versions': {'python': sys.version, 'sklearn': sklearn.__version__, 'numpy': np.__version__, 'pandas': pd.__version__, 'joblib': joblib.__version__},
        'source_sha256': sha(T / 'invoice_features_raw.csv.gz'), 'script_sha256': sha(Path(__file__)), 'threads': 2}
    dump(M / 'kmeans_configuration.json', configuration)
    selected_metrics = best[['variant', 'k', 'silhouette', 'davies_bouldin', 'calinski_harabasz', 'inertia', 'min_cluster_pct']].to_frame().T
    summary = profile[['cluster_name', 'invoice_count', 'invoice_percentage'] + [f'{f}_mean' for f in FEATURES]].reset_index()
    report = f'''# Phase 6 — K-Means clustering and evaluation

Generated {datetime.now(timezone.utc).isoformat()}. All 39,516 invoices / 1,015,214 purchase lines retained. No Apriori or dashboard implemented.

## Verification and feature choice

Original quantity, purchase value, unique product count and quantity-share Simpson diversity definitions were inspected. Numerical values are finite and complete; quantities/value/product counts are positive; diversity lies within its theoretical bounds. Invoice keys are unique. All four Phase 5 scaling matrices were reproduced from original values within 1e-10 tolerance. Raw features were not changed.

Product count and diversity Spearman correlation is **{rho:.6f}**. Diversity = 1 - sum(product quantity / invoice quantity)^2, with a maximum of 1 - 1/product count. These are not identical measures, but including both can overweight basket variety. The primary experiment therefore uses **quantity, purchase value and unique product count**; diversity stays in profiles. All 36 models were also fitted with the original four features as a sensitivity analysis (72 grid fits total). Quantity and value are also correlated; they retain distinct volume/value interpretations and are not claimed independent.

## Experimental design and model selection

K=2–10 crossed with StandardScaler, RobustScaler, log1p+StandardScaler and log1p+RobustScaler. KMeans: k-means++, n_init=20, max_iter=500, tol=1e-4, Lloyd algorithm, random_state=42; local numerical threads limited to two. No outliers removed or clipped. All preprocessing fit on this full descriptive population; future held-out evaluation requires refitting preprocessing on its training population.

Silhouette uses the same uniformly sampled 2,000 invoices without replacement (NumPy default_rng seed 2026) for all 72 comparisons; sample invoice IDs and represented cluster counts are saved. Rare clusters can be absent from this sample. Inertia, Davies–Bouldin and Calinski–Harabasz use all invoices. WCSS is comparable only within the same feature/scaling geometry: curves are normalized at K=2; raw inertia remains in the comparison table. Normalized elbow distance is a heuristic, not proof of a natural K.

Selection was specified before fitting: use the three-feature primary set; require every cluster to contain at least 1% of invoices, convergence and every cluster represented in the silhouette sample. This pragmatic threshold targets usable purchasing segments, not an objective law; tiny-cluster candidates remain in the results, and rare purchases are retained. Among eligible models, minimize equal-weight rank sum for higher silhouette, lower DB, higher CH and higher normalized elbow distance. Ties prefer smaller K then variant name. Scores depend on the chosen geometry, so cross-scaling rankings are operational evidence, not directly comparable accuracy estimates. The selected model is provisional, not a uniquely proven optimum.

{table(selected_metrics)}

Top eligible candidates:

{table(eligible.sort_values(['selection_rank_sum', 'k']).head(8)[['variant','k','silhouette','davies_bouldin','calinski_harabasz','elbow_distance','selection_rank_sum']])}

## Original-unit profiles

{table(summary)}

Names describe relative cluster median value and product-count ranks (lower/middle/higher thirds among clusters). They do not infer customer identities, craftsmanship or product preferences. Full means, medians, standard deviations and ranges are saved. Diversity is reported but does not drive the selected model. Inspect means against medians because bulk purchases remain present. Smallest selected cluster: {profile.invoice_count.min():,} invoices ({profile.invoice_percentage.min():.2f}%); largest: {profile.invoice_count.max():,} ({profile.invoice_percentage.max():.2f}%). Anonymous invoices retained: {int(raw.anonymous_invoice.sum()):,}.

## Reproducibility and stability

Same-seed refit reproduced labels and centers exactly. Reloading the saved preprocessing-plus-KMeans pipeline reproduced every label. Five seeds {SEEDS}, each with 20 initializations, give ten pairwise adjusted Rand indices: minimum **{stability.adjusted_rand_index.min():.6f}**, mean **{stability.adjusted_rand_index.mean():.6f}**, maximum **{stability.adjusted_rand_index.max():.6f}**. ARI is label-permutation invariant. This measures initialization stability, not temporal or resampling stability. Selected silhouette across five independent 2,000-invoice samples ranges {min(s['silhouette'] for s in sample_scores):.6f}–{max(s['silhouette'] for s in sample_scores):.6f}; this is a sensitivity range, not a confidence interval.

Four-feature versus three-feature assignments at the selected K and scaling have ARI **{ablation_ari:.6f}**, exposing sensitivity to the redundant diversity feature. Full four-feature metric curves are included. No ground-truth cluster labels exist and no classification accuracy is claimed.

## Visualization and limitations

Graphs include elbow, silhouette, Davies–Bouldin, Calinski–Harabasz, cluster sizes, original-unit profiles and PCA. PCA explains {pca.explained_variance_ratio_.sum():.2%} of transformed variance in two dimensions and is visualization only; clustering used three numerical dimensions. All invoices appear in the PCA plot, with transparency for overlap.

K-Means uses Euclidean distances and favors compact centroid-based groups; skew, extreme purchases, differing densities and feature weights affect the partition. Log1p changes relative distances rather than removing unusual invoices. Internal indices and the rank heuristic do not establish business truth or a definitive optimal K. Categories, identifiers, customer missingness and date features were not clustering inputs. Category assignments do not establish handmade provenance. Seed stability does not substitute for future temporal/resampling validation or downstream association comparisons.

## Validation and files

All {len(checks)} checks passed, including one label per eligible invoice, saved-file agreement, reconciliation of purchase lines and anonymous invoices, and unchanged SHA-256 for all {len(preservation)} preexisting protected files. The original workbook and all Phase 3–5 artifacts remain unchanged. See `kmeans_validation.json` for checks and hashes; `outputs/models/kmeans_configuration.json` for preprocessing, software versions and parameters. `kmeans_model.joblib` is a scikit-learn Pipeline accepting a DataFrame with the three named raw feature columns; Invoice is never a model feature.

Required tables: `kmeans_cluster_assignments.csv`, `kmeans_cluster_profiles.csv`, `kmeans_model_comparison.csv`. Supporting tables document correlations, ranking, silhouette samples and seed stability. Run the script with the project virtual environment; it refuses to overwrite existing Phase 6 outputs. Load only trusted joblib files.

Method references: [scikit-learn KMeans](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html), [silhouette](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.silhouette_score.html), [clustering evaluation](https://scikit-learn.org/stable/modules/clustering.html#clustering-performance-evaluation).

**Phase 6 complete. Stop for explicit approval before Phase 7.**
'''
    (R / 'kmeans_clustering_report.md').write_text(report, encoding='utf-8')
    outputs = [p for folder in [T, R, G, M] for p in folder.iterdir() if p.is_file() and p.name.startswith(('kmeans_', 'phase6_'))]
    dump(R / 'kmeans_validation.json', {'checks': checks, 'all_passed': all(checks.values()), 'preservation': preservation,
        'output_sha256': {str(p.relative_to(ROOT)): sha(p) for p in outputs}})
    print('SELECTED', selected_metrics.to_json(orient='records'), flush=True)
    print('PROFILES\n', summary.to_string(index=False), flush=True)
    print('STABILITY', stability.adjusted_rand_index.describe().to_dict(), 'CHECKS', len(checks), flush=True)


if __name__ == '__main__':
    run()
