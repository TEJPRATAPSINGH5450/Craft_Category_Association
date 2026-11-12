import streamlit as st
import plotly.express as px
from dashboard.utils.data import csv,metadata,manifest,DataIssue
from dashboard.components.layout import header,metrics,note
from dashboard.components.charts import style,bar,COLORS

header(2,'Purchasing behaviour, in three groups.','Original-unit profiles alongside the selected K-Means model. Each point and assignment represents an invoice.')
profiles=csv('outputs/tables/kmeans_cluster_profiles.csv')
config=metadata('outputs/models/kmeans_configuration.json')
comparison=csv('outputs/tables/kmeans_model_comparison.csv')
selected=comparison[(comparison.feature_set=='primary_three')&(comparison.variant==config['variant'])&(comparison.k==config['k'])].iloc[0]
metrics([('Selected model','K = 3','log1p + RobustScaler, quantity/value/product count'),('Silhouette',f'{selected.silhouette:.3f}','Fixed sample of 2,000 invoices'),('Davies–Bouldin',f'{selected.davies_bouldin:.3f}','All invoices; lower is better'),('Calinski–Harabasz',f'{selected.calinski_harabasz:,.0f}','All invoices; higher is better')])
st.caption('Product diversity is diagnostic only: its Spearman correlation with product count is 0.927. Category assignments do not enter this K-Means model.')
a,b=st.columns([1,1.4])
with a:
    st.subheader('Cluster sizes')
    profiles['Cluster']=profiles.cluster.map(lambda c:f'Cluster {c}')
    st.plotly_chart(bar(profiles,'Cluster','invoice_count',color='Cluster'),use_container_width=True)
with b:
    st.subheader('Compare original values')
    feature=st.selectbox('Profile feature',['total_purchase_value','total_quantity','unique_product_count','product_diversity'],format_func=lambda x:x.replace('_',' ').title(),key='profile_feature')
    melted=profiles.melt(id_vars='Cluster',value_vars=[feature+'_mean',feature+'_median'],var_name='Statistic',value_name='Value')
    melted['Statistic']=melted.Statistic.map(lambda name:'Mean' if name.endswith('_mean') else 'Median')
    fig=px.bar(melted,x='Cluster',y='Value',color='Statistic',barmode='group',color_discrete_sequence=COLORS)
    st.plotly_chart(style(fig),use_container_width=True)
st.subheader('PCA lens on the selected model')
points=csv('dashboard/data/pca_coordinates.csv.gz')
if not points.Invoice.is_unique or len(points)!=39516: raise DataIssue('PCA invoice coordinates do not reconcile')
selected_cluster=st.selectbox('Highlight population',['All invoices',0,1,2],format_func=lambda x:x if isinstance(x,str) else f'Cluster {x}',key='pca_cluster')
subset=points if selected_cluster=='All invoices' else points[points.cluster==selected_cluster]
full=st.checkbox('Show all eligible points',value=False,key='pca_all')
shown=subset if full or len(subset)<=8000 else subset.sample(8000,random_state=42).sort_index()
shown=shown.copy(); shown['Cluster']=shown.cluster.map(lambda c:f'Cluster {c}')
fig=px.scatter(shown,x='PC1',y='PC2',color='Cluster',category_orders={'Cluster':['Cluster 0','Cluster 1','Cluster 2']},
    color_discrete_map={'Cluster 0':COLORS[0],'Cluster 1':COLORS[1],'Cluster 2':COLORS[2]},
    hover_data=['Invoice','total_purchase_value','total_quantity','unique_product_count'],opacity=.4,render_mode='webgl')
fig.update_traces(marker_size=4)
st.plotly_chart(style(fig,520),use_container_width=True)
pca=manifest('dashboard/data/manifest.json')['pca']
st.caption(f'{len(shown):,} of {len(subset):,} invoices displayed; fixed seed 42 when sampled. Two PCs explain {sum(pca["explained_variance_ratio"]):.2%} of transformed variance. PCA is visualization only: K-Means used three numerical features. No model is refitted here.')
with st.expander('Full profiles and evaluation history'):
    st.dataframe(profiles,use_container_width=True,hide_index=True)
    st.dataframe(comparison,use_container_width=True,hide_index=True)
note()

