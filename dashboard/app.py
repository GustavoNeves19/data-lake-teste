"""
Nevoni 360° — roteador da navegação.

Entrypoint do Streamlit Cloud. Usa st.navigation/st.Page (no lugar da pasta
pages/ automática) pra ter títulos com acento, ícones e seções na barra lateral.
As telas ficam em dashboard/views/ (sem set_page_config/inject_css/sidebar_brand
próprios — tudo é centralizado aqui e roda uma vez por interação).
"""
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent)   # raiz do projeto (acima de dashboard/)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
from dashboard.utils.branding import FAVICON

st.set_page_config(
    page_title="Nevoni 360° | Dashboard Gerencial",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.utils.components import inject_css, sidebar_brand

inject_css()
sidebar_brand()   # logo Nevoni + gate de login + botão "Sair" (uma vez, no roteador)

# ── Telas (título exibido + ícone Material) ───────────────────────────────────
visao       = st.Page("views/visao_geral.py", title="Visão Geral",           icon=":material/dashboard:", default=True)
comercial   = st.Page("views/comercial.py",   title="Comercial e Compras",   icon=":material/trending_up:")
operacional = st.Page("views/operacional.py", title="Operacional e Produção", icon=":material/precision_manufacturing:")
sac         = st.Page("views/sac.py",         title="SAC e Assistência",     icon=":material/support_agent:")
engenharia  = st.Page("views/engenharia.py",  title="Engenharia e P&D",      icon=":material/science:")
financeiro  = st.Page("views/financeiro.py",  title="Financeiro",            icon=":material/account_balance:")
juridico    = st.Page("views/juridico.py",    title="Jurídico",              icon=":material/gavel:")
oraculo     = st.Page("views/oraculo.py",     title="Oráculo",               icon=":material/auto_awesome:")

pg = st.navigation({
    "Início":       [visao],
    "Setores":      [comercial, operacional, sac, engenharia, financeiro, juridico],
    "Inteligência": [oraculo],
})
pg.run()
