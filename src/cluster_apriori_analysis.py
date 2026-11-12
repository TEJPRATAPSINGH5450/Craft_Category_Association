"""Phase 8: invoice-cluster category rules, exact comparisons and exploratory tests.

Prior artifacts are read-only. K-Means is not fitted. Cluster support includes
empty baskets. Rules use the Phase 7 scope of 2–4 total categories.
"""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
import sys
import json
import itertools
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import scipy
from scipy.stats import fisher_exact, chi2_contingency, false_discovery_control
from mlxtend.frequent_patterns import apriori, association_rules
import mlxtend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from apriori_analysis import sha, dump, markdown, count_supersets, mask_of, encode, names, enrich_rules, METRICS

T, R, G = (ROOT / 'outputs' / s for s in ['tables','reports','graphs'])
SUPPORTS = [.01,.02,.03,.05]
CONFIDENCES = [.30,.40,.50,.60]
SCOPES = ['global','cluster_0','cluster_1','cluster_2']
VARIANTS = ['high','high_medium']


def metrics(counts, a, b):
    n, na, nb, nab = [float(v) for v in [counts[0],counts[a],counts[b],counts[a|b]]]
    confidence = nab/na if na else np.nan
    return {'support':nab/n, 'confidence':confidence, 'lift':confidence/(nb/n) if nb else np.nan,
            'leverage':nab/n-na*nb/(n*n), 'conviction':(1-nb/n)/(1-confidence) if confidence < 1 else (np.inf if confidence == 1 else np.nan),
            'invoice_count':int(nab),'antecedent_count':int(na),'consequent_count':int(nb)}


def qualifies(m, support=.03, confidence=.5):
    return m['support'] >= support and m['confidence'] >= confidence


def wilson(x,n):
    if not n:
        return np.nan,np.nan
    z=1.959963984540054; p=x/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return center-half,center+half


def test_table(tab):
    """Two-sided test; approximate OR interval explicitly marked for sparse data."""
    tab=np.asarray(tab,dtype=np.int64)
    expected=np.outer(tab.sum(axis=1),tab.sum(axis=0))/tab.sum() if tab.sum() else np.zeros((2,2))
    if (tab.sum(axis=0)==0).any() or (tab.sum(axis=1)==0).any():
        method,p='degenerate_not_testable',1.0
    elif (expected<5).any():
        method,p='fisher_two_sided',float(fisher_exact(tab,alternative='two-sided').pvalue)
    else:
        method,p='pearson_chi_square_no_yates',float(chi2_contingency(tab,correction=False).pvalue)
    a,b,c,d=tab.ravel().astype(float)
    raw_or=a*d/(b*c) if b*c else (np.inf if a*d else np.nan)
    corrected=bool((tab==0).any())
    cells=tab.astype(float)+(.5 if corrected else 0)
    aa,bb,cc,dd=cells.ravel()
    estimate=aa*dd/(bb*cc)
    se=np.sqrt((1/cells).sum())
    lo,hi=np.exp(np.log(estimate)+np.array([-1,1])*1.959963984540054*se)
    return dict(test=method,p_value=p,minimum_expected=float(expected.min()),odds_ratio=raw_or,
                odds_ratio_ci_estimate=estimate,odds_ratio_ci_low=lo,odds_ratio_ci_high=hi,
                ci_zero_cell_correction=corrected,ci_method='approximate_log_Wald_OR; +0.5 all cells if any zero')


def adjust(frame):
    # One family across both variants and all populations, including p=1 degenerate cases.
    frame['q_bh']=false_discovery_control(frame.p_value.to_numpy(),method='bh')
    frame['q_by']=false_discovery_control(frame.p_value.to_numpy(),method='by')
    return frame


def run():
    if Path(sys.prefix).resolve() != (ROOT/'.venv').resolve():
        raise RuntimeError('Use project virtual environment')
    required=['cluster_0_rules.csv','cluster_1_rules.csv','cluster_2_rules.csv','cluster_frequent_itemsets.csv',
              'global_vs_cluster_comparison.csv','cluster_rule_overlap.csv']
    if any((T/p).exists() for p in required) or (R/'cluster_apriori_report.md').exists():
        raise FileExistsError('Existing Phase 8 outputs: version them before rerunning')
    protected=[p for folder in ['data','docs','outputs','src'] for p in (ROOT/folder).rglob('*')
               if p.is_file() and '__pycache__' not in p.parts and p.name!=Path(__file__).name]
    before={str(p.relative_to(ROOT)):sha(p) for p in protected}
    checks={}
    def check(name,value):
        checks[name]=bool(value)
        if not value: raise AssertionError(name)
    for manifest,field in [('feature_engineering_manifest.json','output_hashes'),('kmeans_validation.json','output_sha256'),('phase7_apriori_validation.json','output_sha256')]:
        for p,h in json.loads((R/manifest).read_text(encoding='utf-8'))[field].items():
            check('hash_'+p,sha(ROOT/p)==h)
    cfg7=json.loads((R/'phase7_apriori_parameters.json').read_text(encoding='utf-8'))
    check('phase7_compatible_scope',cfg7['max_rule_itemset_length']==4 and cfg7['transaction_denominator']==39516)
    assignments=pd.read_csv(T/'kmeans_cluster_assignments.csv',dtype={'Invoice':str})
    profiles=pd.read_csv(T/'kmeans_cluster_profiles.csv').set_index('cluster')
    check('assignment_keys_unique',len(assignments)==39516 and assignments.Invoice.is_unique and assignments.cluster.notna().all())
    check('three_clusters',set(assignments.cluster)=={0,1,2})
    counts_by={}; baskets={}; rules_by={}; freq_by={}; denominator_rows=[]; grids=[]; membership_rows=[]
    for variant,file in [('high','apriori_basket_high_confidence.csv.gz'),('high_medium','apriori_basket_high_medium.csv.gz')]:
        source=pd.read_csv(T/file,dtype={'Invoice':str},keep_default_na=False)
        categories=source.columns.drop('Invoice').tolist()
        check(variant+'_category_order',categories==cfg7['category_order'])
        check(variant+'_binary_unique',source.Invoice.is_unique and source[categories].isin([0,1]).all().all())
        joined=source.merge(assignments[['Invoice','cluster']],on='Invoice',how='left',validate='one_to_one',sort=False)
        check(variant+'_join_preserved',len(joined)==39516 and joined.Invoice.equals(source.Invoice) and joined.cluster.notna().all())
        pd.testing.assert_frame_equal(joined[source.columns],source)
        check(variant+'_unchanged_cells',True)
        for scope in SCOPES:
            part=joined if scope=='global' else joined.loc[joined.cluster.eq(int(scope[-1]))]
            binary=part.set_index('Invoice')[categories].astype(bool)
            n=len(binary); baskets[(variant,scope)]=binary
            cnt,_=count_supersets(binary); counts_by[(variant,scope)]=cnt
            if scope!='global': check(variant+'_'+scope+'_phase6_count',n==int(profiles.loc[int(scope[-1]),'invoice_count']))
            denominator_rows.append(dict(variant=variant,scope=scope,invoices=n,empty_baskets=int(binary.sum(axis=1).eq(0).sum()),
                single_category_baskets=int(binary.sum(axis=1).eq(1).sum()),unique_invoice_category_pairs=int(binary.to_numpy().sum())))
            if scope=='global':
                freq=pd.read_csv(T/f'frequent_itemsets_{variant}.csv')
                rules=pd.read_csv(T/f'association_rules_{variant}.csv')
                check(variant+'_global_itemsets_complete',set(freq.itemset_mask)==set(np.flatnonzero(cnt/n>=.01))-{0})
                check(variant+'_global_supports',np.allclose(freq.support,cnt[freq.itemset_mask.to_numpy(int)]/n))
                freq_by[(variant,scope)]=freq; rules_by[(variant,scope)]=rules
            else:
                print(f'Mining {variant} {scope} (N={n}, including empty)',flush=True)
                for support in SUPPORTS:
                    freq=apriori(binary,min_support=support,use_colnames=True,max_len=None,low_memory=True)
                    fm=freq.itemsets.map(lambda items:mask_of(items,categories)).to_numpy(int)
                    check(f'{variant}_{scope}_{support}_complete_itemsets',set(fm)==set(np.flatnonzero(cnt/n>=support))-{0})
                    check(f'{variant}_{scope}_{support}_exact_supports',np.allclose(freq.support,cnt[fm]/n,rtol=1e-12,atol=1e-12))
                    bounded=freq[freq.itemsets.map(len).le(4)]
                    rawrules=association_rules(bounded,num_itemsets=n,metric='confidence',min_threshold=.3,return_metrics=METRICS)
                    if support==.01:
                        rules=enrich_rules(rawrules,cnt,categories)
                        rules['variant']=variant; rules['cluster']=int(scope[-1]); rules['transaction_denominator']=n
                        rules_by[(variant,scope)]=rules
                        export=pd.DataFrame(dict(itemset_mask=fm,itemsets=[encode(m,categories) for m in fm],
                            length=[int(m).bit_count() for m in fm],support=freq.support.to_numpy(),invoice_count=cnt[fm],
                            variant=variant,cluster=int(scope[-1]),transaction_denominator=n))
                        freq_by[(variant,scope)]=export
                    else:
                        base=rules_by[(variant,scope)]
                        computed={f'{mask_of(a,categories)}->{mask_of(b,categories)}' for a,b in zip(rawrules.antecedents,rawrules.consequents)}
                        check(f'{variant}_{scope}_{support}_threshold_rule_equivalence',computed==set(base.loc[base.support.ge(support),'rule_id']))
            # Exact metric validation for global loaded rules and every cluster export.
            rules=rules_by[(variant,scope)]
            check(variant+scope+'_unique_rules',rules.rule_id.is_unique)
            exact=[metrics(cnt,int(a),int(b)) for a,b in zip(rules.antecedent_mask,rules.consequent_mask)]
            for metric in ['support','confidence','lift','leverage','conviction']:
                check(variant+scope+'_exact_'+metric,np.allclose(rules[metric],[e[metric] for e in exact],rtol=1e-10,atol=1e-12,equal_nan=True))
            for support in SUPPORTS:
                for confidence in CONFIDENCES:
                    selected=rules[rules.support.ge(support)&rules.confidence.ge(confidence)]
                    grids.append(dict(variant=variant,scope=scope,min_support=support,min_confidence=confidence,denominator=n,
                        min_joint_invoice_count=int(np.ceil(n*support)),frequent_itemsets=int(freq_by[(variant,scope)].support.ge(support).sum()),
                        rules=len(selected),positive_lift_rules=int(selected.lift.gt(1).sum()),highlight_rules=int((selected.lift.ge(1.1)&~selected.redundant_by_confidence).sum())))
        globalcnt=counts_by[(variant,'global')]
        check(variant+'_cluster_counts_sum',np.array_equal(globalcnt,sum(counts_by[(variant,s)] for s in SCOPES[1:])))
        check(variant+'_partition_no_loss',set().union(*(set(baskets[(variant,s)].index) for s in SCOPES[1:]))==set(source.Invoice))
    for scope in SCOPES:
        check(scope+'_aligned_variant_rows',baskets[('high',scope)].index.equals(baskets[('high_medium',scope)].index))
        check(scope+'_medium_superset',(~baskets[('high',scope)]|baskets[('high_medium',scope)]).all().all())
    for c in range(3):
        pd.concat([rules_by[(v,f'cluster_{c}')] for v in VARIANTS],ignore_index=True).to_csv(T/f'cluster_{c}_rules.csv',index=False)
        for v in VARIANTS:
            rules_by[(v,f'cluster_{c}')].to_csv(T/f'phase8_cluster_{c}_{v}_rules.csv',index=False)
    pd.concat([f for (v,s),f in freq_by.items() if s!='global'],ignore_index=True).to_csv(T/'cluster_frequent_itemsets.csv',index=False)
    denominators=pd.DataFrame(denominator_rows); denominators.to_csv(T/'phase8_denominators.csv',index=False)
    grid=pd.DataFrame(grids); grid.to_csv(T/'phase8_threshold_sensitivity.csv',index=False)
    sets={}
    for key,df in rules_by.items(): sets[key]=set(df.loc[df.support.ge(.03)&df.confidence.ge(.5),'rule_id'])
    overlap=[]; comparisons=[]
    for v in VARIANTS:
        universe=set.union(*(sets[(v,s)] for s in SCOPES))
        for rid in sorted(universe):
            a,b=map(int,rid.split('->'))
            flags={s:rid in sets[(v,s)] for s in SCOPES}
            membership_rows.append(dict(variant=v,rule_id=rid,antecedents=encode(a,categories),consequents=encode(b,categories),
                **flags,cluster_memberships=sum(flags[s] for s in SCOPES[1:]),common_all_clusters=all(flags[s] for s in SCOPES[1:]),
                common_global_and_clusters=all(flags.values())))
        for s1,s2 in itertools.combinations(SCOPES,2):
            a,b=sets[(v,s1)],sets[(v,s2)]
            overlap.append(dict(variant=v,scope_a=s1,scope_b=s2,shared=len(a&b),only_a=len(a-b),only_b=len(b-a),
                                union=len(a|b),jaccard=len(a&b)/len(a|b) if a|b else np.nan))
        for scope in SCOPES[1:]:
            for rid in sorted(sets[(v,'global')]|sets[(v,scope)]):
                a,b=map(int,rid.split('->')); gm=metrics(counts_by[(v,'global')],a,b); cm=metrics(counts_by[(v,scope)],a,b)
                comparisons.append(dict(variant=v,cluster=int(scope[-1]),rule_id=rid,antecedents=encode(a,categories),consequents=encode(b,categories),
                    global_qualifies=rid in sets[(v,'global')],cluster_qualifies=rid in sets[(v,scope)],
                    status='shared' if rid in sets[(v,'global')]&sets[(v,scope)] else ('cluster_only' if rid in sets[(v,scope)] else 'global_only'),
                    global_denominator=39516,cluster_denominator=int(counts_by[(v,scope)][0]),
                    **{f'global_{k}':val for k,val in gm.items()},**{f'cluster_{k}':val for k,val in cm.items()},
                    **{f'{k}_change':cm[k]-gm[k] for k in ['support','confidence','lift','leverage']}))
    membership=pd.DataFrame(membership_rows); membership.to_csv(T/'phase8_rule_membership.csv',index=False)
    comparison=pd.DataFrame(comparisons); comparison.to_csv(T/'global_vs_cluster_comparison.csv',index=False)
    overlaps=pd.DataFrame(overlap); overlaps.to_csv(T/'cluster_rule_overlap.csv',index=False)
    variant_rows=[]
    for scope in SCOPES:
        a,b=sets[('high',scope)],sets[('high_medium',scope)]
        variant_rows.append(dict(scope=scope,shared=len(a&b),high_only=len(a-b),high_medium_only=len(b-a),
            jaccard=len(a&b)/len(a|b) if a|b else np.nan))
    variants=pd.DataFrame(variant_rows); variants.to_csv(T/'phase8_classification_variant_stability.csv',index=False)
    # Prespecified family of all 91 unordered category pairs x 4 populations x 2 variants.
    statrows=[]; differential=[]
    for v in VARIANTS:
        for scope in SCOPES:
            cnt=counts_by[(v,scope)]; n=int(cnt[0])
            for i,j in itertools.combinations(range(14),2):
                a,b=1<<i,1<<j; na,nb,nab=map(int,[cnt[a],cnt[b],cnt[a|b]])
                tab=[[nab,na-nab],[nb-nab,n-na-nb+nab]]
                check(f'cells_{v}_{scope}_{i}_{j}',min(sum(tab,[]))>=0 and sum(sum(tab,[]))==n)
                lower,upper=wilson(nab,n)
                cl,cu=wilson(nab,na)
                statrows.append(dict(variant=v,scope=scope,category_a=categories[i],category_b=categories[j],pair_mask=a|b,
                    n11=tab[0][0],n10=tab[0][1],n01=tab[1][0],n00=tab[1][1],denominator=n,
                    **metrics(cnt,a,b),support_ci_low=lower,support_ci_high=upper,confidence_a_to_b_ci_low=cl,confidence_a_to_b_ci_high=cu,
                    **test_table(tab)))
        for scope in SCOPES[1:]:
            cnt=counts_by[(v,scope)]; rest=counts_by[(v,'global')]-cnt
            for i,j in itertools.permutations(range(14),2):
                a,b=1<<i,1<<j
                nab,na,rab,ra=map(int,[cnt[a|b],cnt[a],rest[a|b],rest[a]])
                lo,hi=wilson(nab,na); rlo,rhi=wilson(rab,ra)
                differential.append(dict(variant=v,cluster=int(scope[-1]),rule_id=f'{a}->{b}',antecedent=categories[i],consequent=categories[j],
                    cluster_antecedent_invoices=na,rest_antecedent_invoices=ra,cluster_joint=nab,rest_joint=rab,
                    cluster_confidence=nab/na if na else np.nan,rest_confidence=rab/ra if ra else np.nan,
                    confidence_difference=nab/na-rab/ra if na and ra else np.nan,
                    confidence_difference_ci_low=lo-rhi,confidence_difference_ci_high=hi-rlo,
                    **test_table([[nab,na-nab],[rab,ra-rab]])))
    stats=adjust(pd.DataFrame(statrows)); diff=adjust(pd.DataFrame(differential))
    check('statistical_family_sizes',len(stats)==728 and len(diff)==1092)
    check('adjusted_p_bounds',stats.q_bh.between(0,1).all() and diff.q_bh.between(0,1).all() and stats.q_by.between(0,1).all() and diff.q_by.between(0,1).all())
    stats.to_csv(T/'phase8_pair_association_tests.csv',index=False)
    diff.to_csv(T/'phase8_cluster_vs_rest_tests.csv',index=False)
    # Select illustrative positive pairs; never use p-value alone for a highlight.
    highlights=[]
    for v in VARIANTS:
        for scope in SCOPES[1:]:
            df=rules_by[(v,scope)]
            top=df[df.baseline_thresholds & df.lift.ge(1.1)&df.itemset_length.eq(2)].sort_values(['lift','support'],ascending=False).head(8)
            for row in top.itertuples():
                ps=stats[(stats.variant==v)&(stats.scope==scope)&(stats.pair_mask==(row.antecedent_mask|row.consequent_mask))].iloc[0]
                ds=diff[(diff.variant==v)&(diff.cluster==int(scope[-1]))&(diff.rule_id==row.rule_id)].iloc[0]
                highlights.append(dict(variant=v,cluster=int(scope[-1]),rule_id=row.rule_id,
                    antecedent=names(row.antecedent_mask,categories),consequent=names(row.consequent_mask,categories),
                    support=row.support,confidence=row.confidence,lift=row.lift,invoice_count=row.invoice_count,
                    global_qualifies=row.rule_id in sets[(v,'global')],q_bh=ps.q_bh,q_by=ps.q_by,
                    odds_ratio=ps.odds_ratio,odds_ratio_ci_low=ps.odds_ratio_ci_low,odds_ratio_ci_high=ps.odds_ratio_ci_high,
                    confidence_difference_vs_rest=ds.confidence_difference,difference_q_bh=ds.q_bh,difference_q_by=ds.q_by))
    highlights=pd.DataFrame(highlights); highlights.to_csv(T/'phase8_highlighted_rules.csv',index=False)
    base=grid[grid.min_support.eq(.03)&grid.min_confidence.eq(.5)].copy()
    # Figure 1: baseline counts, keeping variants separated.
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    for ax,v in zip(axes,VARIANTS):
        sub=base[base.variant==v].set_index('scope').reindex(SCOPES)
        ax.bar(SCOPES,sub.rules); ax.tick_params(axis='x',rotation=20)
        for i,count in enumerate(sub.rules): ax.text(i,count,str(count),ha='center',va='bottom')
        ax.set(title=v,ylabel='Rules (2–4 categories)',ylim=(0,max(sub.rules)*1.16))
    fig.suptitle('Global versus invoice clusters: support ≥3%, confidence ≥50%')
    fig.tight_layout(); fig.savefig(G/'phase8_rule_counts.png',dpi=150); plt.close(fig)
    # Figure 2: baseline category-pair networks, fixed shared positions.
    fig,axes=plt.subplots(2,3,figsize=(16,12))
    for r,v in enumerate(VARIANTS):
        for c in range(3):
            ax=axes[r,c]; angles=np.linspace(0,2*np.pi,14,endpoint=False)
            pos={category:np.array([np.cos(t),np.sin(t)]) for category,t in zip(categories,angles)}
            top=highlights[(highlights.variant==v)&(highlights.cluster==c)]
            for row in top.itertuples():
                ax.add_patch(FancyArrowPatch(pos[row.antecedent],pos[row.consequent],connectionstyle='arc3,rad=.12',arrowstyle='-|>',
                    mutation_scale=12,linewidth=1+5*row.support,alpha=.6,color='#237e9a',shrinkA=8,shrinkB=8))
            for i,cat in enumerate(categories):
                p=pos[cat]; ax.scatter(*p,s=45,color='#d78b46'); ax.text(*(p*1.16),str(i+1),ha='center',va='center',fontsize=9)
            if top.empty: ax.text(0,0,'No pair meets\nhighlight criteria',ha='center')
            ax.set(title=f'{v} / cluster {c}',xlim=(-1.35,1.35),ylim=(-1.35,1.35),aspect='equal'); ax.axis('off')
    legend='\n'.join(f'{i+1}. {cat}' for i,cat in enumerate(categories))
    fig.text(.5,.01,legend,ha='center',fontsize=8)
    fig.suptitle('Up to 8 positive pair rules per cluster: support ≥3%, confidence ≥50%, lift ≥1.10\nArrow direction is conditional association, not causation; width is support')
    fig.subplots_adjust(top=.89,bottom=.24,hspace=.2)
    fig.savefig(G/'phase8_networks.png',dpi=150); plt.close(fig)
    # Figure 3: same pair identities measured in every population, even below thresholds.
    fig,axes=plt.subplots(1,2,figsize=(15,7))
    for ax,v in zip(axes,VARIANTS):
        top=highlights[highlights.variant==v].sort_values('lift',ascending=False).drop_duplicates('rule_id').head(6)
        for offset,scope in zip([-.3,-.1,.1,.3],SCOPES):
            vals=[metrics(counts_by[(v,scope)],*map(int,rid.split('->')))['lift'] for rid in top.rule_id]
            ax.barh(np.arange(len(top))+offset,vals,height=.18,label=scope)
        ax.set_yticks(np.arange(len(top)),[a+' →\n'+b for a,b in zip(top.antecedent,top.consequent)],fontsize=8)
        ax.axvline(1,color='gray',ls='--'); ax.set(title=v,xlabel='Lift, same identities in each population'); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(G/'phase8_lift_comparison.png',dpi=150); plt.close(fig)
    # Figure 4: all baseline rules, fixed ranges across panels.
    fig,axes=plt.subplots(2,4,figsize=(16,8),sharex=True,sharey=True)
    vmax=max(df.lift.max() if len(df) else 1 for df in rules_by.values())
    for r,v in enumerate(VARIANTS):
        for c,scope in enumerate(SCOPES):
            df=rules_by[(v,scope)]; df=df[df.support.ge(.03)&df.confidence.ge(.5)]
            axes[r,c].scatter(df.support,df.confidence,c=df.lift,vmin=0,vmax=vmax,cmap='viridis',s=5,alpha=.4)
            axes[r,c].set(title=f'{v} / {scope}',xlabel='Support',ylabel='Confidence',xlim=(0,1),ylim=(.48,1.02))
    fig.suptitle('Baseline rules: support denominator is the full relevant population; colour indicates lift')
    fig.tight_layout(); fig.savefig(G/'phase8_support_confidence.png',dpi=150); plt.close(fig)
    # Figure 5: exactly one-cluster rules vs multi-cluster shared rules.
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    for ax,v in zip(axes,VARIANTS):
        mem=membership[membership.variant==v]
        unique=[int((mem[f'cluster_{c}']&mem.cluster_memberships.eq(1)).sum()) for c in range(3)]
        shared=[len(sets[(v,f'cluster_{c}')])-unique[c] for c in range(3)]
        ax.bar(range(3),unique,label='Qualifies in this cluster only'); ax.bar(range(3),shared,bottom=unique,label='Shared with another cluster')
        ax.set(title=v,xlabel='Cluster ID',ylabel='Baseline rule count',xticks=range(3)); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(G/'phase8_shared_unique.png',dpi=150); plt.close(fig)
    # Figure 6: pairwise lift for all pairs, no mining threshold filter.
    fig,axes=plt.subplots(2,4,figsize=(16,9))
    for r,v in enumerate(VARIANTS):
        for c,scope in enumerate(SCOPES):
            mat=np.full((14,14),np.nan)
            for i,j in itertools.combinations(range(14),2): mat[i,j]=mat[j,i]=metrics(counts_by[(v,scope)],1<<i,1<<j)['lift']
            im=axes[r,c].imshow(mat,vmin=0,vmax=3,cmap='coolwarm')
            axes[r,c].set(title=f'{v} / {scope}',xticks=range(14),yticks=range(14),xticklabels=range(1,15),yticklabels=range(1,15))
            axes[r,c].tick_params(labelsize=7)
    fig.colorbar(im,ax=axes.ravel().tolist(),label='Pair lift (colour capped at 3)',shrink=.6)
    fig.text(.5,.005,legend,ha='center',fontsize=7)
    fig.suptitle('All category-pair lifts (not threshold-filtered); grey/blank diagonal is not a rule')
    fig.subplots_adjust(bottom=.24,top=.91,wspace=.3,hspace=.25,right=.84)
    fig.savefig(G/'phase8_pair_heatmaps.png',dpi=150); plt.close(fig)
    # Disk round trips for required tables, without treating CSV dtype inference as data loss.
    for c in range(3):
        saved=pd.read_csv(T/f'cluster_{c}_rules.csv')
        expected=pd.concat([rules_by[(v,f'cluster_{c}')] for v in VARIANTS],ignore_index=True)
        pd.testing.assert_frame_equal(expected,saved,check_dtype=False,rtol=1e-10,atol=1e-12)
        check(f'cluster_{c}_export_roundtrip',True)
    for path,frame in [('global_vs_cluster_comparison.csv',comparison),('cluster_rule_overlap.csv',overlaps)]:
        pd.testing.assert_frame_equal(frame,pd.read_csv(T/path),check_dtype=False,rtol=1e-10,atol=1e-12)
        check(path+'_roundtrip',True)
    preserve={p:{'before':h,'after':sha(ROOT/p)} for p,h in before.items()}
    check('all_prior_artifacts_unchanged',all(x['before']==x['after'] for x in preserve.values()))
    config={'created_at':datetime.now(ZoneInfo('Asia/Calcutta')).isoformat(),'supports':SUPPORTS,'confidences':CONFIDENCES,
        'baseline_support':.03,'baseline_confidence':.5,'highlight_min_lift':1.1,'max_rule_categories':4,'max_frequent_itemset_length':None,
        'category_order':categories,'denominator_includes_empty':True,'randomness':'none; deterministic Apriori and fixed circular plots',
        'statistical_families':{'pair_association':728,'cluster_vs_rest_conditional_prevalence':1092},
        'correction':'BH separately for each stated family; BY also reported for dependence sensitivity','alpha':.05,
        'confidence_intervals':'95% pointwise Wilson for proportions; conservative difference of Wilson bounds; approximate log-Wald OR with +0.5 for zero cells',
        'global_artifacts_reused':True,'kmeans_retrained':False,'versions':{'python':sys.version,'mlxtend':mlxtend.__version__,'scipy':scipy.__version__,'pandas':pd.__version__},
        'script_sha256':sha(Path(__file__)),'source_references':'Invoice IDs remain in Phase 5 baskets and Phase 6 assignments; join to unchanged integrated_purchase_lines.csv.gz for source_id/source_sheet/source_row.'}
    dump(R/'phase8_configuration.json',config)
    stories=[]
    for v in VARIANTS:
        for c in range(3):
            top=highlights[(highlights.variant==v)&(highlights.cluster==c)].head(2)
            if top.empty: stories.append(f'- {v}, cluster {c}: no simple pair meets support ≥3%, confidence ≥50%, lift ≥1.10. This is not proof of no associations.')
            for row in top.itertuples():
                stories.append(f'- **{v}, cluster {c}: {row.antecedent} → {row.consequent}**: {row.invoice_count:,} invoices, support {row.support:.2%}, confidence {row.confidence:.2%}, lift {row.lift:.3f}. '
                    f'Global baseline qualification: {row.global_qualifies}. Pair-test BH q={row.q_bh:.3g}, BY q={row.q_by:.3g}; '
                    f'OR {row.odds_ratio:.3f} (approximate 95% CI {row.odds_ratio_ci_low:.3f}–{row.odds_ratio_ci_high:.3f}). '
                    f'Confidence difference versus the remaining invoices: {row.confidence_difference_vs_rest:+.2%}, BH q={row.difference_q_bh:.3g}.')
    common=[]
    for v in VARIANTS:
        sub=membership[membership.variant==v]
        common.append(dict(variant=v,common_all_clusters=int(sub.common_all_clusters.sum()),common_global_and_clusters=int(sub.common_global_and_clusters.sum()),
            unique_to_one_cluster=int(sub.cluster_memberships.eq(1).sum())))
    strongest_common=[]
    for v in VARIANTS:
        ids=membership.loc[membership.variant.eq(v)&membership.common_all_clusters,'rule_id'].tolist()
        for rid in ids[:5]:
            a,b=map(int,rid.split('->')); strongest_common.append(f'- {v}: {names(a,categories)} → {names(b,categories)} qualifies in all three clusters.')
    report=f'''# Phase 8 — Invoice-cluster Apriori and global comparison

Generated {config['created_at']}. These are **invoice-level purchasing-behaviour segments**, not customer segments. Existing K=3 assignments were reused; no retraining, preprocessing or dashboard work occurred.

## Integration and denominators

Both Phase 5 matrices were joined one-to-one with Phase 6 assignments. No invoices or category columns changed; every invoice belongs to exactly one cluster. Boolean cells were checked, cluster counts reconcile with Phase 6, and the sum of cluster itemset counts equals global counts for every possible category subset.

{markdown(denominators)}

Support is n(A∪B)/the full population above, **including empty baskets**. Confidence uses the antecedent invoice count. Both variants retain the same invoice universe per cluster. Confidence labels describe mapping evidence, not verified handmade provenance. Original source references remain in the unchanged purchase-line integration file; rule identities and category masks use Phase 7's recorded order.

## Mining scope and sensitivity

Apriori independently mined each cluster and variant at support 1%, 2%, 3%, 5%; confidence 30%, 40%, 50%, 60% was evaluated by exact filtering from 30%. All frequent itemset lengths are retained. Rules contain **2–4 total categories**, matching Phase 7. Required cluster rule files contain explicitly labelled variant rows, with separate per-variant exports also saved; no counts pool the two classification variants. Exports use the 1%/30% floor, while comparisons below use 3%/50%. High-lift highlights require lift ≥1.10, but this is a practical effect-size screen, not an optimized or significance threshold. An empty qualifying rule set is a valid result.

Global frequent itemsets/rules were loaded from Phase 7 and independently recounted; no global model was rerun. Cluster frequent itemsets were checked against exhaustive bitmask support counts at all support thresholds. The full 128-row threshold table records actual denominators and minimum joint invoice counts.

Baseline results:

{markdown(base[['variant','scope','denominator','min_joint_invoice_count','frequent_itemsets','rules','positive_lift_rules']])}

## Shared, unique and hidden-by-global-threshold rules

{markdown(overlaps)}

{markdown(pd.DataFrame(common))}

“Unique” means qualifying at the fixed thresholds in only that population; it does not mean an association is impossible elsewhere. Global-versus-cluster comparisons use the union of qualified identities and recompute both metrics from exact counts even when one side fails thresholds. Missing confidence/lift means an absent denominator, not an invented zero. All delta columns are cluster minus global. The membership table distinguishes sharing across clusters from sharing with global results. Global membership overlaps clusters, so global-versus-cluster deltas are descriptive, not independent-group hypothesis tests.

Examples qualifying in every cluster (up to five per variant, deterministic identity order):

{chr(10).join(strongest_common) if strongest_common else 'No rule meets the baseline in every cluster. This is a threshold-specific result, not evidence of no common purchasing behaviour.'}

## Classification sensitivity

{markdown(variants)}

Adding Medium-confidence assignments changes observed category prevalence and rule qualification. Changes are sensitivity to the same invoices and alternative description classifications, not independent replication. The baseline, category order, rule length limit and denominators are identical across variants. Rule uniqueness should be interpreted jointly with absolute invoice counts and support/confidence sensitivity, particularly for the smaller cluster 2.

## Exploratory statistical reliability

We prespecified all 91 unordered category pairs in each of four populations and both variants: **728 tests**, regardless of whether mining selected the pair. Each 2×2 table counts both categories, antecedent only, consequent only, neither; empty baskets contribute to neither. Two-sided Fisher exact is used if any expected count is below five; otherwise Pearson chi-square without Yates correction. Degenerate tables are marked not testable and assigned p=1 conservatively. BH correction is applied across the entire 728-test family; BY correction is also supplied because tests overlap and dependence assumptions for BH may not hold.

A second separate family tests **1,092** directed category-pair confidence differences: 182 directions × 3 clusters × 2 variants. Among invoices containing the antecedent, consequent presence is compared between a cluster and the disjoint remaining invoices. These tests concern conditional prevalence differences, not a formal interaction test or equality of lift. BH and BY apply across the entire second family. No cluster is tested against its overlapping global sample.

Effect sizes include lift, leverage, odds ratio and confidence differences. Intervals are 95% pointwise Wilson bounds for support/confidence; differences use conservative differences of Wilson endpoints. OR intervals are approximate log-Wald, adding 0.5 to all four cells only when a zero occurs; this correction is flagged and does not alter the Fisher test or exported raw OR. Sparse-table intervals warrant caution. P-values reported as zero reflect floating-point underflow, not proof of a zero probability. Full uncertainty and contingency counts are exported.

Pair-test BH q<.05: {int(stats.q_bh.lt(.05).sum())}/{len(stats)}; BY q<.05: {int(stats.q_by.lt(.05).sum())}/{len(stats)}. Cluster-versus-rest BH q<.05: {int(diff.q_bh.lt(.05).sum())}/{len(diff)}; BY q<.05: {int(diff.q_by.lt(.05).sum())}/{len(diff)}. These totals include negative associations and are not counts of positive business opportunities.

**All statistical findings remain exploratory and conditional on assumptions.** Repeated invoices from the same customer, time/season effects and anonymous buyers can violate invoice independence; multiple-testing correction does not fix this. Cluster labels were learned from basket-related numerical features in the same dataset, so conditioning on clusters can induce or change associations. No held-out or customer-blocked confirmation was performed. Tests of all pairs reduce rule-selection screening bias but do not remove these limitations; higher-order rules have descriptive metrics only, not automatic statistical certification.

## Interpretable findings

{chr(10).join(stories)}

Large baskets can contain many categories together, producing high confidence without high lift. Conversely, low-support patterns can have large lift with insufficient evidence. Interpret these measured rules alongside the count, leverage, interval and variant sensitivity. They support merchandising hypotheses, not causation, profitability claims or handmade-product purchasing claims. No result here establishes that purchasing one category causes another.

## Visualizations, validation and deliverables

Six figures cover rule counts, fixed-layout cluster pair networks, lift on identical rule identities, support/confidence, shared-versus-unique rules, and all-pair lift heatmaps. Network highlights use up to eight simple rules per cluster; an empty network is shown explicitly. Heatmap colours cap at lift 3 while exact values are retained in the pair table. Rule scatter colour scales are shared across populations. All graphs use actual observations.

All **{len(checks)} checks passed**. All **{len(preserve)} prior files** have unchanged SHA-256, including the original workbook and Phase 3–7 artifacts. Saved rule/comparison tables were reloaded and compared, exact metrics reconciled, and invoice partitions checked. `phase8_validation.json` records checks and hashes; `phase8_configuration.json` records parameters, versions and scope. Source code refuses to overwrite prior Phase 8 deliverables.

Required tables: `cluster_0_rules.csv`, `cluster_1_rules.csv`, `cluster_2_rules.csv`, `cluster_frequent_itemsets.csv`, `global_vs_cluster_comparison.csv`, `cluster_rule_overlap.csv`. Supporting files include separate confidence-variant rules, membership, threshold sensitivity, pair tests, cluster-versus-rest tests and highlights.

Methods: [SciPy Fisher exact](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.fisher_exact.html), [chi-square contingency](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2_contingency.html), [BH/BY correction](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.false_discovery_control.html).

**Phase 8 complete. Stop for approval before Phase 9.**
'''
    (R/'cluster_apriori_report.md').write_text(report,encoding='utf-8')
    output=[T/p for p in required]+[R/'cluster_apriori_report.md']+[p for folder in [T,R,G] for p in folder.glob('phase8_*') if p.is_file()]
    dump(R/'phase8_validation.json',{'checks':checks,'all_passed':all(checks.values()),'preservation':preserve,
        'output_sha256':{str(p.relative_to(ROOT)):sha(p) for p in output}})
    print('BASELINE\n'+base.to_string(index=False),flush=True)
    print('VARIANT STABILITY\n'+variants.to_string(index=False),flush=True)
    print('COMMON\n'+pd.DataFrame(common).to_string(index=False),flush=True)
    print('CHECKS',len(checks),'PROTECTED',len(preserve),flush=True)


def finalize_review():
    """Readable plot legends and ranked combinations, without rerunning mining."""
    config=json.loads((R/'phase8_configuration.json').read_text(encoding='utf-8'))
    categories=config['category_order']
    stats=pd.read_csv(T/'phase8_pair_association_tests.csv')
    fig,axes=plt.subplots(2,4,figsize=(16,10))
    for r,v in enumerate(VARIANTS):
        for c,scope in enumerate(SCOPES):
            mat=np.full((14,14),np.nan)
            sub=stats[(stats.variant==v)&(stats.scope==scope)]
            for row in sub.itertuples():
                i,j=categories.index(row.category_a),categories.index(row.category_b)
                mat[i,j]=mat[j,i]=row.lift
            im=axes[r,c].imshow(mat,vmin=0,vmax=3,cmap='coolwarm')
            axes[r,c].set(title=f'{v} / {scope}',xticks=range(14),yticks=range(14),xticklabels=range(1,15),yticklabels=range(1,15))
            axes[r,c].tick_params(labelsize=7)
    fig.subplots_adjust(bottom=.27,top=.9,wspace=.3,hspace=.25,right=.85)
    cax=fig.add_axes([.89,.34,.015,.48])
    fig.colorbar(im,cax=cax,label='Pair lift (colour capped at 3)')
    legend='\n'.join(f'{i+1}. {cat}' for i,cat in enumerate(categories))
    fig.text(.5,.015,legend,ha='center',fontsize=8)
    fig.suptitle('All category-pair lifts; no mining threshold filter; blank diagonal is not a rule')
    fig.savefig(G/'phase8_pair_heatmaps.png',dpi=150); plt.close(fig)
    plotted={}
    for v in VARIANTS:
        for scope in SCOPES:
            df=pd.read_csv(T/f'association_rules_{v}.csv') if scope=='global' else pd.read_csv(T/f'phase8_{scope}_{v}_rules.csv')
            plotted[(v,scope)]=df[df.support.ge(.03)&df.confidence.ge(.5)]
    vmax=max(df.lift.max() if len(df) else 1 for df in plotted.values())
    fig,axes=plt.subplots(2,4,figsize=(16,8),sharex=True,sharey=True)
    for r,v in enumerate(VARIANTS):
        for c,scope in enumerate(SCOPES):
            df=plotted[(v,scope)]
            dots=axes[r,c].scatter(df.support,df.confidence,c=df.lift,vmin=0,vmax=vmax,cmap='viridis',s=5,alpha=.4)
            axes[r,c].set(title=f'{v} / {scope}',xlabel='Support',ylabel='Confidence',xlim=(0,1),ylim=(.48,1.02))
            if df.empty: axes[r,c].text(.5,.75,'No baseline rules',ha='center',fontsize=9)
    fig.subplots_adjust(left=.06,bottom=.09,top=.9,wspace=.25,hspace=.3,right=.88)
    cax=fig.add_axes([.92,.2,.012,.6]); fig.colorbar(dots,cax=cax,label='Lift (shared scale)')
    fig.suptitle('Baseline rules: support ≥3%, confidence ≥50%; full population denominators')
    fig.savefig(G/'phase8_support_confidence.png',dpi=150); plt.close(fig)
    freq=pd.read_csv(T/'cluster_frequent_itemsets.csv')
    top=(freq[freq.length.ge(2)].sort_values(['variant','cluster','support','itemset_mask'],ascending=[True,True,False,True])
         .groupby(['variant','cluster'],sort=False).head(5).copy())
    top['combination']=top.itemset_mask.map(lambda m:names(m,categories))
    top.to_csv(T/'phase8_top_category_combinations.csv',index=False)
    summary=top.groupby(['variant','cluster'],sort=False).head(1)[['variant','cluster','combination','invoice_count','support']]
    text='''## Final interpretation and most frequent combinations

At the baseline, every cluster 0 rule also qualifies globally, while cluster 1 contains every global rule plus additional rules. Cluster 2 has no baseline rules, so none is shared across all three clusters. This nested qualification structure is consistent with the strong role of basket size; it does not establish three independent customer preference types.

Cluster 2 is not devoid of co-purchasing: at 2% support / 50% confidence there are three rules in each variant; at 1% / 50% there are 13 High and 24 High+Medium rules. These are sensitivity results with lower absolute counts, not a replacement for the fixed baseline.

Most frequent multi-category combination in each cluster (full top-five lists saved separately; itemsets mined at 1%):

'''+markdown(summary)+'''

The cluster 1 Pet Accessories → Garden & Outdoor Accessories example qualifies locally but fails global baseline support. This is a difference in threshold qualification, not necessarily a larger local lift than global lift. Pair counts, adjusted tests and confidence intervals provide exploratory support, subject to repeated-customer dependence and data-derived clustering. No significance result establishes business value or causation.

'''
    report=R/'cluster_apriori_report.md'
    current=report.read_text(encoding='utf-8')
    marker='**Phase 8 complete. Stop for approval before Phase 9.**'
    if '## Final interpretation and most frequent combinations' not in current:
        report.write_text(current.replace(marker,text+marker),encoding='utf-8')
    config['script_sha256']=sha(Path(__file__))
    config['visual_review_completed']=True
    dump(R/'phase8_configuration.json',config)
    validation_path=R/'phase8_validation.json'
    validation=json.loads(validation_path.read_text(encoding='utf-8'))
    for p in [G/'phase8_pair_heatmaps.png',G/'phase8_support_confidence.png',T/'phase8_top_category_combinations.csv',report,R/'phase8_configuration.json']:
        validation['output_sha256'][str(p.relative_to(ROOT))]=sha(p)
    if not all(sha(ROOT/p)==h for p,h in validation['output_sha256'].items()):
        raise AssertionError('Final artifact hash verification')
    validation['final_output_hashes_verified']=True
    dump(validation_path,validation)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
    finalize_review()
