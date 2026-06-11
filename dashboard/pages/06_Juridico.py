"""Setor Jurídico e Homologações — planejado."""

import streamlit as st

st.set_page_config(page_title="Jurídico | Nevoni 360°", page_icon="⚖️", layout="wide")

from dashboard.utils.components import inject_css, page_header, sidebar_brand, coming_soon
inject_css()
sidebar_brand()

page_header(
    title="⚖️ Jurídico e Homologações",
    subtitle="Contratos · Certidões · INMETRO · Compliance",
)

coming_soon(
    "Setor em planejamento",
    "Fonte de dados a definir. Integração prevista para próxima sprint.",
)

st.markdown("""
**KPIs planejados:**
- Status de homologações INMETRO por produto
- Contratos ativos vs vencidos
- Certidões de regularidade fiscal (validade)
- Alertas de vencimento de documentos
- Processos jurídicos em andamento

**Fontes candidatas:**
- Google Drive / SharePoint (documentos)
- ClickUp (tarefas jurídicas)
- Planilhas de controle manual → ingestão via Google Sheets API
""")
