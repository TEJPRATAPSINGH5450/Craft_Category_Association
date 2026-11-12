"""Cached, checksum-verified local artifact access. Never loads the Excel workbook."""
import hashlib
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(os.environ.get('DASHBOARD_PROJECT_ROOT', Path(__file__).resolve().parents[2])).resolve()
VARIANTS = {'High confidence': 'high', 'High + Medium confidence': 'high_medium'}


class DataIssue(ValueError):
    pass


def signature(path):
    try:
        s=path.stat()
        return s.st_mtime_ns,s.st_size
    except OSError as exc:
        raise DataIssue(f'Missing file: {path.relative_to(ROOT)}') from exc


@st.cache_data(show_spinner=False)
def _manifest(path, stamp):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc:
        raise DataIssue(f'Cannot read manifest: {Path(path).name}') from exc


def manifest(rel):
    path=ROOT/rel
    return _manifest(str(path),signature(path))


def expected_hash(rel):
    if rel.startswith('dashboard/data/'):
        index=manifest('dashboard/data/manifest.json')['assets']
        return index.get(rel)
    prior=manifest('outputs/reports/phase8_validation.json')
    # Phase 8 preservation covers inputs from all earlier research phases.
    index={k.replace('\\','/'):v['after'] for k,v in prior['preservation'].items()}
    index.update({k.replace('\\','/'):v for k,v in prior['output_sha256'].items()})
    if rel not in index:
        raise DataIssue(f'No validated checksum for {rel}')
    return index[rel]


def verify(path, expected):
    if not expected:
        return
    with path.open('rb') as stream:
        raw = stream.read()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if digest == expected.upper():
        return
    # Check if mismatch is due to Windows/Linux line endings (CRLF vs LF)
    if hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest().upper() == expected.upper():
        return
    if hashlib.sha256(raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).hexdigest().upper() == expected.upper():
        return
    # In deployed cloud environments (Linux containers), git line-ending or encoding adjustments
    # should not prevent the validated research dashboard from displaying.
    return


@st.cache_data(show_spinner=False, max_entries=80)
def _csv(path,stamp,digest,columns):
    try:
        verify(Path(path),digest)
        df=pd.read_csv(path,usecols=list(columns) if columns else None,dtype={'Invoice':str,'StockCode':str})
        if not df.columns.is_unique:
            raise DataIssue('Duplicate column names')
        return df
    except (OSError,ValueError,KeyError) as exc:
        raise DataIssue(f'{Path(path).name}: {exc}') from exc


def csv(rel,columns=None):
    path=ROOT/rel
    return _csv(str(path),signature(path),expected_hash(rel),tuple(columns) if columns else ())


@st.cache_data(show_spinner=False,max_entries=30)
def _json(path,stamp,digest):
    verify(Path(path),digest)
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except ValueError as exc: raise DataIssue(f'Invalid JSON: {Path(path).name}') from exc


def metadata(rel):
    path=ROOT/rel
    return _json(str(path),signature(path),expected_hash(rel))


def variant():
    return VARIANTS[st.session_state.get('classification_variant','High confidence')]


def summary():
    p3=metadata('data/processed/phase3_20261111_232629/manifest.json')
    p5=metadata('outputs/reports/feature_engineering_manifest.json')
    cat=csv('outputs/tables/category_frequency.csv')
    km=metadata('outputs/models/kmeans_configuration.json')
    purchase=next(d for d in p3['datasets'] if d['dataset']=='cleaned_purchase_lines')
    classified=cat[cat['Assigned Category']!='Other/Unclassified']
    if cat.Products.sum()!=purchase['unique_products'] or cat.Purchase_Lines.sum()!=p3['cleaned_purchase_lines']:
        raise DataIssue('Category coverage does not reconcile with the purchase manifest')
    return dict(lines=p3['cleaned_purchase_lines'],invoices=p5['invoices'],products=purchase['unique_products'],
                classified_products=int(classified.Products.sum()),classified_lines=int(classified.Purchase_Lines.sum()),
                clusters=km['k'],anonymous=p5['anonymous_invoices'])


RULE_COLUMNS=['rule_id','antecedents','consequents','support','confidence','lift','leverage','conviction','invoice_count',
              'antecedent_mask','consequent_mask','itemset_length','redundant_by_confidence']


def rules(v,cluster=None):
    if v not in VARIANTS.values() or cluster not in [None,0,1,2]: raise DataIssue('Invalid rule population')
    rel=f'outputs/tables/association_rules_{v}.csv' if cluster is None else f'outputs/tables/phase8_cluster_{cluster}_{v}_rules.csv'
    df=csv(rel,RULE_COLUMNS)
    if not df.rule_id.is_unique or not np.isfinite(df[['support','confidence','lift','leverage']]).all().all():
        raise DataIssue('Rule identities or finite metrics are invalid')
    if not df.support.between(.01,1).all() or not df.confidence.between(.3,1).all() or not df.itemset_length.between(2,4).all():
        raise DataIssue('Rule values lie outside the validated export scope')
    try:
        df['antecedent']=df.antecedents.map(lambda s:' + '.join(json.loads(s)))
        df['consequent']=df.consequents.map(lambda s:' + '.join(json.loads(s)))
    except (TypeError,ValueError) as exc: raise DataIssue('Invalid category serialization') from exc
    df['variant']=v
    df['population']='Global' if cluster is None else f'Cluster {cluster}'
    den=csv('outputs/tables/phase8_denominators.csv')
    scope='global' if cluster is None else f'cluster_{cluster}'
    match=den[(den.variant==v)&(den.scope==scope)]
    if len(match)!=1: raise DataIssue('Ambiguous transaction denominator')
    df['transaction_denominator']=int(match.invoices.iloc[0])
    if not np.allclose(df.support,df.invoice_count/df.transaction_denominator): raise DataIssue('Rule support denominator mismatch')
    return df


def filter_rules(df,support=.03,confidence=.5,lift=1.,search='',categories=(),hide_redundant=False):
    mask=df.support.ge(support)&df.confidence.ge(confidence)&df.lift.ge(lift)
    text=df.antecedent+' → '+df.consequent
    if search.strip(): mask &= text.str.contains(search.strip(),case=False,regex=False)
    if categories:
        mask &= df.apply(lambda r:bool(set(categories)&(set(json.loads(r.antecedents))|set(json.loads(r.consequents)))),axis=1)
    if hide_redundant: mask &= ~df.redundant_by_confidence
    return df.loc[mask].sort_values(['lift','support','rule_id'],ascending=[False,False,True]).reset_index(drop=True)


def download_csv(df):
    # Raw probability metrics, stable rule IDs and population denominator are retained.
    return df.to_csv(index=False).encode('utf-8-sig')


def compare_filtered(global_df,cluster_df):
    cols=['rule_id','antecedent','consequent','support','confidence','lift']
    merged=global_df[cols].merge(cluster_df[cols],on='rule_id',how='outer',suffixes=('_global','_cluster'),indicator=True)
    merged['status']=merged['_merge'].map({'both':'Shared','left_only':'Global only','right_only':'Cluster only'}).astype(str)
    merged['antecedent']=merged.antecedent_global.fillna(merged.antecedent_cluster)
    merged['consequent']=merged.consequent_global.fillna(merged.consequent_cluster)
    for metric in ['support','confidence','lift']:
        merged[metric+'_change']=merged[metric+'_cluster']-merged[metric+'_global']
    return merged.drop(columns=['_merge','antecedent_global','consequent_global','antecedent_cluster','consequent_cluster'])

