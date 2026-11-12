import streamlit as st
from dashboard.utils.data import summary,csv,variant,metadata
from dashboard.components.layout import header,metrics,note
from dashboard.components.charts import bar

header(1,'Patterns behind the purchase.','An evidence-led view of retail baskets, purchasing-behaviour clusters and product-category associations.')
s=summary(); v=variant()
metrics([('Purchase lines',f'{s["lines"]:,}','Phase 3 cleaned purchase line items'),('Invoices',f'{s["invoices"]:,}','Includes anonymous-customer invoices and empty category baskets'),('Unique products',f'{s["products"]:,}','Distinct verified StockCode keys')])
st.write('')
st.caption('Coverage KPIs below include High + Medium assignments. The sidebar variant controls the evidence views and category footprint.')
metrics([('Classified products',f'{s["classified_products"]/s["products"]:.2%}','High + Medium product coverage; 4,232 of 4,896 products'),
         ('Classified purchase lines',f'{s["classified_lines"]/s["lines"]:.2%}','High + Medium line coverage; product coverage uses a different denominator'),('Purchasing clusters',str(s['clusters']),'Invoice-level segments, not customer segments')])
st.write('')
left,right=st.columns([1.55,1])
with left:
    st.subheader('Category footprint')
    cat=csv('outputs/tables/phase7_category_frequencies.csv'); cat=cat[cat.variant.eq(v)].sort_values('invoice_count')
    st.plotly_chart(bar(cat,'invoice_count','category',orientation='h',height=520),width='stretch')
    st.caption('Invoices containing each category; category counts overlap. Denominator: all 39,516 invoices.')
with right:
    st.subheader('What the research shows')
    with st.container(border=True):
        st.markdown('**01 · Basket size shapes associations**')
        st.write('The higher-value, higher-variety invoice cluster contains more qualifying rules than the global population.')
    with st.container(border=True):
        st.markdown('**02 · No result is still a result**')
        st.write('Cluster 2 has no rules at 3% support / 50% confidence. Lower-threshold results remain available as sensitivity analysis.')
    with st.container(border=True):
        st.markdown('**03 · Mapping uncertainty matters**')
        st.write('Medium-confidence assignments change cluster 0’s rule set more than cluster 1’s. They are provisional classifications.')
st.subheader('Evidence coverage · selected variant')
den=csv('outputs/tables/phase8_denominators.csv'); d=den[(den.variant==v)&(den.scope=='global')].iloc[0]
coverage=csv('outputs/tables/apriori_coverage_comparison.csv'); c=coverage[coverage.variant==v].iloc[0]
metrics([('Eligible category lines',f'{int(c.eligible_category_lines):,}',f'{c.eligible_line_percentage:.2f}% of purchase lines'),
         ('Empty baskets retained',f'{int(d.empty_baskets):,}','Included in association support denominators'),('Anonymous invoices',f'{s["anonymous"]:,}','Never removed merely because Customer ID is missing')])
note()

