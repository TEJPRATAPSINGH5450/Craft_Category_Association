import streamlit as st
from dashboard.utils.data import filter_rules, download_csv
from dashboard.components.charts import scatter_rules,network


def controls(df,prefix):
    with st.container(border=True):
        a,b,c=st.columns(3)
        support=a.slider('Minimum support',.01,1.0,.03,.01,key=prefix+'_support',format='%.2f')
        confidence=b.slider('Minimum confidence',.30,1.0,.50,.05,key=prefix+'_confidence',format='%.2f')
        lift=c.number_input('Minimum lift',min_value=0.,max_value=100.,value=1.,step=.1,key=prefix+'_lift')
        a,b=st.columns([2,1])
        search=a.text_input('Search categories',placeholder='e.g. Paper, Garden, Textiles',key=prefix+'_search')
        hide=b.checkbox('Hide confidence-redundant rules',value=False,key=prefix+'_redundant')
    st.caption('Export scope: support ≥1%, confidence ≥30%, 2–4 total categories. Filters select existing results; they do not run Apriori.')
    params=dict(support=support,confidence=confidence,lift=lift,search=search,hide_redundant=hide)
    return filter_rules(df,**params),params


def show_table(df,key):
    st.download_button('Download filtered rules · CSV',download_csv(df),file_name=f'{key}_filtered_rules.csv',mime='text/csv',key=key+'_download')
    if df.empty:
        st.info('No rules meet these filters. This is a threshold-specific result, not evidence that no associations exist.')
        return
    display=df[['antecedent','consequent','invoice_count','support','confidence','lift','leverage','conviction']].copy()
    display['support']*=100; display['confidence']*=100
    st.dataframe(display,width='stretch',hide_index=True,column_config={
        'antecedent':'Antecedent','consequent':'Consequent','invoice_count':'Joint invoices',
        'support':st.column_config.NumberColumn('Support (%)',format='%.2f'),
        'confidence':st.column_config.NumberColumn('Confidence (%)',format='%.2f'),
        'lift':st.column_config.NumberColumn('Lift',format='%.3f'),
        'leverage':st.column_config.NumberColumn('Leverage',format='%.4f'),
        'conviction':st.column_config.NumberColumn('Conviction',format='%.3f')})
    st.caption('CSV retains probability-scale support/confidence, rule IDs, classification variant and transaction denominator. Infinite conviction is mathematically valid when confidence = 1.')


def rule_charts(df,key):
    if df.empty: return
    a,b=st.columns([1,1])
    with a:
        st.subheader('Support meets confidence')
        st.plotly_chart(scatter_rules(df),width='stretch',key=key+'_scatter')
    with b:
        st.subheader('Category association network')
        pairs=df[df.itemset_length.eq(2)].nlargest(15,['lift','support'])
        if pairs.empty: st.info('No single-category → single-category rules match the filters.')
        else:
            st.plotly_chart(network(df),width='stretch',key=key+'_network')
            nodes=sorted(set(pairs.antecedent)|set(pairs.consequent))
            with st.expander('Network key and interpretation'):
                st.write('\n\n'.join(f'{i+1}. {n}' for i,n in enumerate(nodes)))
                st.caption('Top 15 directional pair rules by lift. Edge width = support. Arrow direction is conditional association, not causation; positions have no analytical meaning.')

