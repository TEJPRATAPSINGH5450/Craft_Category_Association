"""Read-only local research dashboard. Start with streamlit run app.py."""
import streamlit as st
from dashboard.components.layout import shell
from dashboard.utils.data import DataIssue

st.set_page_config(page_title='Craft Category Research | INT396', page_icon='◈', layout='wide', initial_sidebar_state='expanded')
shell()
pages = [
    st.Page('dashboard/pages/overview.py', title='Project Overview', icon=':material/space_dashboard:', default=True),
    st.Page('dashboard/pages/clustering.py', title='K-Means Clustering', icon=':material/scatter_plot:'),
    st.Page('dashboard/pages/global_rules.py', title='Global Apriori', icon=':material/hub:'),
    st.Page('dashboard/pages/clusters.py', title='Cluster-wise Analysis', icon=':material/bubble_chart:'),
    st.Page('dashboard/pages/research.py', title='Research Comparison', icon=':material/compare_arrows:'),
    st.Page('dashboard/pages/methodology.py', title='Methodology & Findings', icon=':material/menu_book:'),
]
page = st.navigation(pages)
try:
    page.run()
except DataIssue as exc:
    st.error('This view is unavailable because a required research artifact is missing or invalid.')
    st.caption(str(exc))
    st.info('Restore the original validated file, then refresh this page. No research data has been changed.')

