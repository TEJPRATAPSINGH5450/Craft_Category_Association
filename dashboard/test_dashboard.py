"""Integration tests against real validated outputs; no research files modified."""
import hashlib,io,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest
from dashboard.utils import data


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest().upper()


def run():
    checks={}; timings={}
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    def clean(at,label):
        check(label+'_no_exception',len(at.exception)==0)
        check(label+'_no_data_error',len(at.error)==0)
    start=time.perf_counter()
    at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()
    timings['overview_cold_seconds']=time.perf_counter()-start
    clean(at,'overview')
    metric={m.label:m.value for m in at.metric}
    check('overview_source_metrics',metric['Purchase lines']=='1,015,214' and metric['Invoices']=='39,516' and metric['Unique products']=='4,896')
    check('distinct_coverage_denominators',metric['Classified products']=='86.44%' and metric['Classified purchase lines']=='93.97%')
    start=time.perf_counter();at.run();timings['overview_warm_seconds']=time.perf_counter()-start
    pages=['overview','clustering','global_rules','clusters','research','methodology']
    for page in pages:
        for label in data.VARIANTS:
            at.selectbox(key='classification_variant').set_value(label).run()
            at.switch_page(f'dashboard/pages/{page}.py').run()
            clean(at,page+'_'+data.VARIANTS[label])
            check(page+'_'+data.VARIANTS[label]+'_title',len(at.title)==1)
    for label,v in data.VARIANTS.items():
        at.selectbox(key='classification_variant').set_value(label).run()
        at.switch_page('dashboard/pages/clusters.py').run()
        for c in [0,1,2]:
            at.selectbox(key='analysis_cluster').set_value(c).run()
            clean(at,f'cluster_{c}_{v}')
            expected=data.filter_rules(data.rules(v,c))
            got={m.label:m.value for m in at.metric}
            check(f'cluster_{c}_{v}_count',got['Matching rules']==f'{len(expected):,}')
            check(f'cluster_{c}_{v}_denominator',got['Cluster invoices']==f'{[21342,13705,4469][c]:,}')
            payload=data.download_csv(expected)
            loaded=pd.read_csv(io.BytesIO(payload))
            check(f'cluster_{c}_{v}_csv',loaded.rule_id.tolist()==expected.rule_id.tolist() and len(loaded)==len(expected))
            if c==2: check(v+'_empty_notice',any('No rules meet' in x.value for x in at.info))
    at.switch_page('dashboard/pages/global_rules.py').run()
    at.selectbox(key='classification_variant').set_value('High confidence').run()
    at.slider(key='global_support').set_value(.05)
    at.slider(key='global_confidence').set_value(.6)
    at.number_input(key='global_lift').set_value(1.5)
    at.text_input(key='global_search').set_value('Paper').run()
    clean(at,'filtered_global')
    expected=data.filter_rules(data.rules('high'),support=.05,confidence=.6,lift=1.5,search='Paper')
    check('filters_correct',next(m.value for m in at.metric if m.label=='Matching rules')==f'{len(expected):,}')
    loaded=pd.read_csv(io.BytesIO(data.download_csv(expected)))
    check('filtered_csv_values',loaded.rule_id.tolist()==expected.rule_id.tolist() and loaded.support.ge(.05).all() and loaded.confidence.ge(.6).all())
    check('download_controls_present',len(at.get('download_button'))>=2)
    at.text_input(key='global_search').set_value('zz_no_category_[regex_literal]').run()
    clean(at,'empty_literal_search')
    check('empty_search_works',next(m.value for m in at.metric if m.label=='Matching rules')=='0')
    at.switch_page('dashboard/pages/clustering.py').run()
    at.selectbox(key='pca_cluster').set_value(2).run();clean(at,'pca_cluster_selection')
    at.checkbox(key='pca_all').set_value(True).run();clean(at,'pca_all_points')
    at.selectbox(key='profile_feature').set_value('product_diversity').run();clean(at,'diversity_profile')
    at.switch_page('dashboard/pages/research.py').run()
    at.select_slider(key='research_confidence').set_value(.3).run();clean(at,'sensitivity_selection')
    at.radio(key='stat_question').set_value('Cluster versus remaining invoices').run()
    at.selectbox(key='stat_cluster').set_value(2).run();clean(at,'differential_statistics')
    at.selectbox(key='stat_correction').set_value('q_by').run();clean(at,'by_correction')
    at.switch_page('dashboard/pages/methodology.py').run()
    at.text_input(key='product_search').set_value('CERAMIC').run();clean(at,'product_description_search')
    # Missing-file UI and changed-file protection without touching original artifacts.
    original_root=data.ROOT
    with tempfile.TemporaryDirectory(prefix='dashboard_test_') as temporary:
        data.ROOT=Path(temporary)
        missing=AppTest.from_file(str(ROOT/'app.py'),default_timeout=60).run()
        check('missing_file_handled',not missing.exception and any('unavailable' in x.value for x in missing.error))
        data.ROOT=original_root
        f=Path(temporary)/'invalid.csv';f.write_text('a\n1\n')
        caught=False
        try:data.verify(f,'0'*64)
        except data.DataIssue:caught=True
        check('checksum_mismatch_rejected',caught)
        caught=False
        try:data._csv(str(f),data.signature(f),sha(f),('missing_column',))
        except data.DataIssue:caught=True
        check('invalid_schema_rejected',caught)
    # Actual baseline comparisons must match Phase 8, without pooling variants.
    for v in data.VARIANTS.values():
        global_rules=data.filter_rules(data.rules(v))
        comp=data.compare_filtered(global_rules,data.filter_rules(data.rules(v,1)))
        check(v+'_global_cluster_membership',comp.status.eq('Global only').sum()==0 and comp.status.eq('Shared').sum()==len(global_rules))
    source=json.loads((ROOT/'dashboard/data/research_snapshot.json').read_text())
    unchanged={p:sha(ROOT/p)==h for p,h in source.items()}
    check('all_prior_research_files_unchanged',all(unchanged.values()))
    runtime=[ROOT/'app.py']+list((ROOT/'dashboard/pages').glob('*.py'))+list((ROOT/'dashboard/components').glob('*.py'))+list((ROOT/'dashboard/utils').glob('*.py'))
    text='\n'.join(p.read_text(encoding='utf-8') for p in runtime)
    check('no_runtime_model_fitting_or_mining',not any(token in text for token in ['.fit(','.fit_predict(','.fit_transform(','from mlxtend','import joblib','from sklearn']))
    result={'all_passed':all(checks.values()),'checks':checks,'timings':timings,'protected_files':len(source),'preservation':unchanged,
            'browser_review':'Recorded separately in dashboard validation report','versions':{'streamlit':st.__version__,'pandas':pd.__version__}}
    out=ROOT/'dashboard/validation';out.mkdir(exist_ok=True)
    (out/'automated_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'checks':len(checks),'all_passed':all(checks.values()),'timings':timings,'protected_files':len(source)}),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    run()
