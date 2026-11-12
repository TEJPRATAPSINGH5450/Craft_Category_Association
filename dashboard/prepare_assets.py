"""One-time display assets; no model fitting except visualization-only PCA.

Uses the saved preprocessing transform and existing labels. Never trains KMeans
or mines rules. Refuses to overwrite existing prepared assets.
"""
from pathlib import Path
import hashlib,json,sys
import pandas as pd
import numpy as np
import joblib
from sklearn.decomposition import PCA

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dashboard/data'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest().upper()

def run():
    if (OUT/'manifest.json').exists(): raise FileExistsError('Display assets already exist; version before rebuilding.')
    OUT.mkdir(parents=True,exist_ok=True)
    protected=[p for folder in ['data','docs','outputs','src'] for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    protected += [ROOT/'requirements.txt',ROOT/'README.md',ROOT/'PROJECT_INSTRUCTIONS.md']
    before={str(p.relative_to(ROOT)):sha(p) for p in protected}
    (OUT/'research_snapshot.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
    config=json.loads((ROOT/'outputs/models/kmeans_configuration.json').read_text())
    features=config['features']
    raw=pd.read_csv(ROOT/'outputs/tables/invoice_features_raw.csv.gz',usecols=['Invoice']+features+['product_diversity'],dtype={'Invoice':str})
    labels=pd.read_csv(ROOT/'outputs/tables/kmeans_cluster_assignments.csv',usecols=['Invoice','cluster'],dtype={'Invoice':str})
    joined=raw.merge(labels,on='Invoice',validate='one_to_one',how='left',sort=False)
    assert len(joined)==39516 and joined.Invoice.is_unique and joined.cluster.notna().all()
    model=joblib.load(ROOT/'outputs/models/kmeans_model.joblib')
    x=model.named_steps['preprocessing'].transform(raw)
    pca=PCA(n_components=2,svd_solver='full')
    coords=pca.fit_transform(x)
    assert np.allclose(pca.explained_variance_ratio_,config['pca_explained_variance_ratio'])
    joined['PC1']=coords[:,0]; joined['PC2']=coords[:,1]
    joined.to_csv(OUT/'pca_coordinates.csv.gz',index=False)
    records=[]
    for variant,file in [('high','apriori_basket_high_confidence.csv.gz'),('high_medium','apriori_basket_high_medium.csv.gz')]:
        basket=pd.read_csv(ROOT/'outputs/tables'/file,dtype={'Invoice':str})
        categories=basket.columns.drop('Invoice').tolist()
        merged=basket.merge(labels,on='Invoice',how='left',validate='one_to_one')
        for scope in ['global','cluster_0','cluster_1','cluster_2']:
            group=merged if scope=='global' else merged[merged.cluster.eq(int(scope[-1]))]
            for category in categories:
                count=int(group[category].sum())
                records.append(dict(variant=variant,scope=scope,category=category,invoice_count=count,denominator=len(group),prevalence=count/len(group)))
    pd.DataFrame(records).to_csv(OUT/'category_prevalence.csv',index=False)
    assert all(sha(ROOT/p)==digest for p,digest in before.items())
    assets={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [OUT/'pca_coordinates.csv.gz',OUT/'category_prevalence.csv']}
    manifest={'assets':assets,'pca':{'explained_variance_ratio':pca.explained_variance_ratio_.tolist(),'purpose':'display only; saved preprocessing.transform, existing cluster labels; no KMeans fit'},
              'source_hashes':{str(p.relative_to(ROOT)):before[str(p.relative_to(ROOT))] for p in [ROOT/'outputs/models/kmeans_model.joblib',ROOT/'outputs/tables/invoice_features_raw.csv.gz',ROOT/'outputs/tables/kmeans_cluster_assignments.csv']},
              'protected_file_count':len(before),'source_preservation_verified':True}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'invoices':len(joined),'protected_files':len(before),'pca_variance':pca.explained_variance_ratio_.tolist()}))

if __name__=='__main__':run()
