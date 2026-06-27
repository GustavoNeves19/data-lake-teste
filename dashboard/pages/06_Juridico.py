"""Setor Jurídico e Homologações — planejado."""

import streamlit as st

import os as _os
_FAVICON = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "assets", "nevoni_favicon.png")
st.set_page_config(page_title="Jurídico | Nevoni 360°", page_icon=_FAVICON, layout="wide")

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dashboard.utils.components import inject_css, page_header, sidebar_brand, coming_soon
inject_css()
sidebar_brand()

page_header(
    title="Jurídico e Homologações",
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
