import streamlit as st
import plotly.express as px
from dashboard.utils.data import csv,variant,download_csv
from dashboard.components.layout import header,note
from dashboard.components.charts import style,COLORS

header(5,'How robust are the findings?','Compare mapping uncertainty, population-specific rules and threshold sensitivity. Statistical evidence remains exploratory.')
v=variant()
a,b,c=st.tabs(['Classification & overlap','Threshold sensitivity','Statistical evidence'])
with a:
    st.subheader('High versus High + Medium')
    variants=csv('outputs/tables/phase8_classification_variant_stability.csv')
    fig=px.bar(variants,x='scope',y='jaccard',color='scope',color_discrete_sequence=COLORS)
    fig.update_yaxes(tickformat='.0%',range=[0,1])
    st.plotly_chart(style(fig),width='stretch')
    st.caption('Baseline: 3% support / 50% confidence, 2–4 categories per rule. Cluster 2 has two empty rule sets: Jaccard is undefined, not 100%.')
    st.dataframe(variants,hide_index=True,width='stretch')
    st.subheader('Global and cluster rule overlap · selected variant')
    overlap=csv('outputs/tables/cluster_rule_overlap.csv'); overlap=overlap[overlap.variant==v]
    st.dataframe(overlap,hide_index=True,width='stretch')
with b:
    grid=csv('outputs/tables/phase8_threshold_sensitivity.csv')
    confidence=st.select_slider('Confidence threshold',options=[.3,.4,.5,.6],value=.5,key='research_confidence')
    selected=grid[(grid.variant==v)&grid.min_confidence.eq(confidence)]
    fig=px.line(selected,x='min_support',y='rules',color='scope',markers=True,color_discrete_sequence=COLORS)
    fig.update_xaxes(tickformat='.0%',title='Minimum support'); fig.update_yaxes(title='Qualifying rule count')
    st.plotly_chart(style(fig),width='stretch')
    st.dataframe(selected,hide_index=True,width='stretch')
    st.caption('Observed experiment grid; no interpolation or new mining. More rules do not imply better thresholds.')
with c:
    st.info('Repeated invoices from the same customer and data-derived clusters limit independence. Adjusted significance is not causation or business importance.')
    mode=st.radio('Statistical question',['Within-population category association','Cluster versus remaining invoices'],key='stat_question')
    correction=st.selectbox('Multiple-testing correction',['q_bh','q_by'],format_func=lambda q:'Benjamini–Hochberg' if q=='q_bh' else 'Benjamini–Yekutieli (dependence sensitivity)',key='stat_correction')
    threshold=st.slider('Maximum adjusted p-value',.001,.1,.05,.001,key='stat_alpha',format='%.3f')
    if mode.startswith('Within'):
        stats=csv('outputs/tables/phase8_pair_association_tests.csv')
        scope=st.selectbox('Test population',['global','cluster_0','cluster_1','cluster_2'],key='stat_scope')
        view=stats[(stats.variant==v)&(stats.scope==scope)&stats[correction].le(threshold)]
        st.caption('All 91 unordered pairs × 4 populations × 2 variants = 728 tests in one correction family. Fisher for sparse expected cells; otherwise chi-square. Intervals are pointwise, not multiplicity-adjusted.')
    else:
        stats=csv('outputs/tables/phase8_cluster_vs_rest_tests.csv')
        cluster=st.selectbox('Test cluster',[0,1,2],key='stat_cluster')
        view=stats[(stats.variant==v)&stats.cluster.eq(cluster)&stats[correction].le(threshold)]
        st.caption('1,092 directed-pair tests in a separate correction family. Among antecedent invoices, compares consequent presence in a cluster against disjoint remaining invoices—not against the overlapping global population.')
    st.write(f'**{len(view):,} rows** meet the selected adjusted-p filter. Negative associations may also be significant.')
    st.download_button('Download statistical results',download_csv(view),'statistical_results.csv','text/csv')
    st.dataframe(view,hide_index=True,width='stretch')
    st.caption('Raw odds ratios and approximate intervals are retained. Zero-cell corrections are flagged; p-values displayed as zero may reflect floating-point underflow.')
note()

