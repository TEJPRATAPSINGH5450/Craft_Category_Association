import streamlit as st
from dashboard.utils.data import metadata,csv,summary
from dashboard.components.layout import header,note

header(6,'From transactions to evidence.','A transparent account of the data, methods, findings and limits of this research.')
st.markdown('### Craft Category Association Discovery Through Clustered Transaction Analysis\n**INT396 — Unsupervised Learning** · Aftab Khan and Tej Pratap Singh')
st.warning('Online Retail II is general retail/giftware data, not a verified handicraft-only dataset. Decorative or giftware labels do not prove handmade production.')
tabs=st.tabs(['Data & preservation','Models & metrics','Findings & limitations'])
with tabs[0]:
    p3=metadata('data/processed/phase3_20261111_232629/manifest.json')
    st.subheader('Two worksheets, preserved source references')
    st.write(f'The original workbook contains {p3["original_lines"]:,} transaction lines across 2009–2010 and 2010–2011. Phase 3 retained {p3["cleaned_purchase_lines"]:,} purchase lines ({p3["retention_pct_original"]:.2f}% of original rows).')
    st.markdown('''- Returns, operational adjustments, unresolved records and duplicate audits remain separate.
- Missing Customer IDs do not disqualify legitimate purchases. Identifiers were never imputed.
- Cross-sheet duplicates were investigated; legitimate within-source repeats and bulk purchases were preserved.
- Zero-price merchandise was investigated; 126 supported purchase lines were retained.
- Product classification uses description evidence, explicit confidence levels and review status. Original descriptions were not overwritten.''')
    st.code(p3['sha256_after'],language=None)
    st.caption('Original workbook SHA-256 recorded by preprocessing. The dashboard never opens or changes the workbook.')
    mapping=csv('outputs/tables/product_category_mapping.csv',columns=['StockCode','Original Description','Assigned Category','Confidence Level','Review Status','Classification Reason'])
    search=st.text_input('Search product descriptions or StockCodes',key='product_search')
    if search: mapping=mapping[mapping['Original Description'].str.contains(search,case=False,regex=False,na=False)|mapping.StockCode.str.contains(search,case=False,regex=False,na=False)]
    st.dataframe(mapping,hide_index=True,width='stretch')
with tabs[1]:
    st.markdown('''#### K-Means
Invoice-level quantity, purchase value and unique product count are transformed with log1p and RobustScaler. K=2–10 and four scaling variants were compared, alongside a four-feature sensitivity experiment. K=3 was selected with multiple internal metrics and a minimum cluster-size criterion. Diversity remains a profile measure because it overlaps strongly with product count.

Silhouette used a fixed 2,000-invoice sample; Davies–Bouldin and Calinski–Harabasz used all invoices. Five-seed mean adjusted Rand index was 0.9858. This assesses initialization stability, not temporal generalization. PCA is only a visualization.

#### Apriori
Binary invoice-category presence is used; quantities do not multiply an item. Every population denominator includes empty baskets. The tested support grid is 1%, 2%, 3%, 5%; confidence is 30%, 40%, 50%, 60%. Rule exports cover 2–4 total categories. Frequent itemsets are not length-capped.

Support measures joint prevalence. Confidence is conditional prevalence. Lift compares confidence with consequent prevalence. Leverage measures excess joint prevalence over independence. Conviction measures expected versus observed failures of the implication; it can be infinite. High confidence alone does not imply a strong positive association.

#### Reliability
All category pairs were tested, not only mined highlights. Fisher/chi-square tests, BH and BY corrections, odds ratios and approximate uncertainty intervals are reported. Cluster-versus-rest tests use disjoint invoice populations. No test certifies causality or business value.''')
with tabs[2]:
    st.markdown('''#### Main findings
- Home Decor & Lighting with Kitchen & Tableware is the most frequent multi-category combination in every cluster and both classification variants.
- Cluster 1 includes all global baseline rules plus additional locally qualifying associations. Basket size strongly influences these results.
- Cluster 2 has no baseline rules, but some appear at lower support thresholds.
- Adding Medium-confidence assignments changes cluster 0’s rule set more than cluster 1’s.

#### Limits and future scope
Category uncertainty, broad baskets, repeated customers, seasonality and clusters learned from the same dataset can change observed associations. Internal metrics do not establish a uniquely correct partition. Significance is exploratory; uncertainty intervals are pointwise. No customer-blocked, temporal holdout or causal validation is claimed.

Future research can examine customer-blocked resampling, temporal stability, rare-category sensitivity and manual verification of ambiguous descriptions. These experiments have not been run by the dashboard.''')
st.divider()
st.caption('Read-only presentation of validated research artifacts. Missing or changed input files stop the affected view. No training or Apriori execution occurs in this app.')
note()

