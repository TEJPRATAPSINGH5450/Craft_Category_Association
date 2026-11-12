import json
import streamlit as st
from dashboard.utils.data import rules,variant,csv,download_csv
from dashboard.components.layout import header,metrics,note
from dashboard.components.rules import controls,show_table,rule_charts

header(3,'Explore the global rulebook.','Filter observed associations across all eligible invoices. A common consequent can produce high confidence without strong lift.')
v=variant(); df=rules(v)
filtered,params=controls(df,'global')
metrics([('Matching rules',f'{len(filtered):,}','Rules meeting all current filters'),('Support denominator','39,516','Includes empty baskets'),('Classification variant',v.replace('_',' + ').title(),'Selected description-evidence variant')])
table_tab,charts_tab,items_tab=st.tabs(['Association rules','Association views','Frequent itemsets'])
with table_tab: show_table(filtered,'global_'+v)
with charts_tab: rule_charts(filtered,'global')
with items_tab:
    itemsets=csv(f'outputs/tables/frequent_itemsets_{v}.csv')
    length=st.slider('Minimum itemset length',1,13,2,key='global_item_length')
    eligible=itemsets[itemsets.support.ge(params['support'])&itemsets.length.ge(length)].copy()
    if params['search'].strip(): eligible=eligible[eligible.itemsets.str.contains(params['search'],case=False,regex=False)]
    eligible['Categories']=eligible.itemsets.map(lambda x:' + '.join(json.loads(x)))
    st.caption('Itemsets use the support and search filters only. Confidence and lift describe rules, not itemsets. Itemsets have no length cap.')
    st.download_button('Download filtered itemsets',download_csv(eligible),'global_itemsets.csv','text/csv')
    st.dataframe(eligible[['Categories','length','support','invoice_count']].sort_values('support',ascending=False),hide_index=True,use_container_width=True)
note()

