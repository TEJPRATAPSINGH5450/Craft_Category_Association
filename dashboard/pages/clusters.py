import streamlit as st
from dashboard.utils.data import rules,variant,csv,filter_rules,compare_filtered,download_csv
from dashboard.components.layout import header,metrics,note
from dashboard.components.rules import controls,show_table,rule_charts
from dashboard.components.charts import bar

header(4,'Associations within purchasing groups.','Compare invoice-level segments using the same rule definitions and filters. Empty baskets remain in each cluster denominator.')
v=variant(); cluster=st.selectbox('Purchasing-behaviour cluster',[0,1,2],format_func=lambda c:f'Cluster {c}',key='analysis_cluster')
df=rules(v,cluster); filtered,params=controls(df,'cluster')
den=csv('outputs/tables/phase8_denominators.csv'); d=den[(den.variant==v)&(den.scope==f'cluster_{cluster}')].iloc[0]
metrics([('Cluster invoices',f'{int(d.invoices):,}','Support denominator for this cluster'),('Empty baskets',f'{int(d.empty_baskets):,}','Retained, not dropped'),('Matching rules',f'{len(filtered):,}','Current filters; no new mining')])
rt,ct,pt=st.tabs(['Cluster rulebook','Global comparison','Category footprint'])
with rt:
    show_table(filtered,f'cluster_{cluster}_{v}'); rule_charts(filtered,f'cluster_{cluster}')
with ct:
    global_filtered=filter_rules(rules(v),**params)
    compared=compare_filtered(global_filtered,filtered)
    shared=int(compared.status.eq('Shared').sum()); union=len(compared)
    metrics([('Shared rules',f'{shared:,}','Meets current filters in both populations'),('Cluster only',f'{int(compared.status.eq("Cluster only").sum()):,}','Threshold-specific, not proof of absence globally'),('Jaccard',f'{shared/union:.2%}' if union else 'Not defined','Intersection / union; undefined when both sets are empty')])
    status=st.multiselect('Rule membership',['Shared','Cluster only','Global only'],default=['Shared','Cluster only','Global only'],key='rule_membership')
    view=compared[compared.status.isin(status)]
    st.download_button('Download current comparison',download_csv(view),f'cluster_{cluster}_comparison.csv','text/csv')
    st.dataframe(view,hide_index=True,use_container_width=True)
    st.caption('Both populations use the same live filters. Blank metrics mean that side did not meet the filters; they are not zero. Deltas are provided only for shared filtered rules. These overlapping populations are not independent statistical samples.')
with pt:
    categories=csv('dashboard/data/category_prevalence.csv')
    selected=categories[(categories.variant==v)&categories.scope.isin(['global',f'cluster_{cluster}'])]
    fig=bar(selected,'prevalence','category',color='scope',orientation='h',height=600)
    fig.update_layout(barmode='group'); fig.update_xaxes(tickformat='.0%',title='Fraction of invoices containing category')
    st.plotly_chart(fig,use_container_width=True)
note()

