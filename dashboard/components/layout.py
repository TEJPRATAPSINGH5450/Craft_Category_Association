import streamlit as st
from dashboard.utils.data import VARIANTS


def shell():
    st.markdown('''<style>
    .block-container {max-width:1500px;padding-top:2.4rem;padding-bottom:3rem;}
    h1 {letter-spacing:-.035em;font-weight:750!important;} h2 {letter-spacing:-.02em;}
    [data-testid="stMetric"] {border:1px solid color-mix(in srgb,currentColor 12%,transparent);border-radius:14px;padding:18px 20px;}
    [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;letter-spacing:-.025em;}
    [data-testid="stSidebar"] {border-right:1px solid color-mix(in srgb,currentColor 10%,transparent);}
    .eyebrow {color:#189a91;font-size:.75rem;font-weight:700;letter-spacing:.15em;margin-bottom:.5rem;}
    .brand {font-size:1.35rem;font-weight:750;letter-spacing:-.04em;margin-bottom:.2rem;}
    .subtitle {opacity:.65;font-size:.88rem;line-height:1.6;}
    </style>''',unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="eyebrow">INT396 · RESEARCH EXPLORER</div><div class="brand">Craft Category<br>Association Discovery</div>',unsafe_allow_html=True)
        st.caption('Clustered transaction analysis')
        st.divider()
        st.selectbox('Classification evidence',list(VARIANTS),key='classification_variant',help='Changes category assignments, not the invoice population.')
        st.caption('High + Medium includes provisional classifications.')
        st.divider()
    st.sidebar.caption('Online Retail II · 2009–2011\n\nAftab Khan · Tej Pratap Singh')


def header(number,title,description):
    st.markdown(f'<div class="eyebrow">{number:02d} / RESEARCH WORKSPACE</div>',unsafe_allow_html=True)
    st.title(title)
    st.markdown(description)
    st.write('')


def metrics(items):
    for col,(label,value,help_text) in zip(st.columns(len(items)),items):
        col.metric(label,value,help=help_text)


def note():
    st.caption('General retail and giftware data. Category labels do not establish handmade or artisan provenance. Associations are not causal.')

