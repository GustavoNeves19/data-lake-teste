"""
Engenharia e P&D — Fichas Técnicas · BOM · Desenvolvimento de Produto · Seriais
Fonte parcial: dm_products (BOM, seriais, itens)
"""

import streamlit as st
import pandas as pd
import plotly.express as px

import os as _os
_FAVICON = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "assets", "nevoni_favicon.png")

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dashboard.utils.components import inject_css, page_header, kpi_card, section_title, sidebar_brand, coming_soon
from dashboard.utils.bq_client import query, PROJECT_PROD


PROJ = PROJECT_PROD
PRD  = f"{PROJ}.dm_products"

page_header(
    title="Engenharia e P&D",
    subtitle="Catálogo de Produtos · Estrutura BOM · Fichas Técnicas · Seriais",
    sources=[
        {"name": "ERP (SQL Server)", "active": True},
        {"name": "Miro (fluxogramas)", "active": False},
        {"name": "ClickUp (projetos)", "active": False},
    ],
)

tab_cat, tab_bom_eng, tab_roadmap = st.tabs([
    "Catálogo de Produtos",
    "Estrutura Técnica (BOM)",
    "Roadmap P&D",
])

# ── Tab: Catálogo ────────────────────────────────────────────
with tab_cat:
    section_title("Catálogo de Itens / SKUs")
    try:
        df_items = query(f"""
            SELECT
              i.item_code,
              i.item_description,
              f.family_name,
              g.group_name,
              i.unit,
              i.gross_weight,
              i.net_weight,
              i.is_active
            FROM `{PRD}.dim_item` i
            LEFT JOIN `{PRD}.dim_family` f USING (family_code)
            LEFT JOIN `{PRD}.dim_group`  g USING (group_code)
            ORDER BY i.item_code
            LIMIT 1000
        """)

        if df_items.empty:
            st.info("Sem itens cadastrados.")
        else:
            ativos = df_items[df_items["is_active"] == True] if "is_active" in df_items else df_items

            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi_card("Total SKUs", f'{len(df_items):,}')
            with c2: kpi_card("Ativos", f'{len(ativos):,}', variant="success")
            with c3: kpi_card("Famílias", str(df_items["family_name"].nunique()))
            with c4: kpi_card("Grupos", str(df_items["group_name"].nunique()))

            st.markdown("<br>", unsafe_allow_html=True)

            col_fam, col_grp = st.columns(2)
            with col_fam:
                df_fam = df_items.groupby("family_name").size().reset_index(name="qtd").sort_values("qtd", ascending=False).head(15)
                fig = px.bar(
                    df_fam, x="qtd", y="family_name",
                    orientation="h",
                    title="SKUs por Família",
                    labels={"family_name": "Família", "qtd": "Qtd."},
                    color_discrete_sequence=["#1E1882"],
                )
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            with col_grp:
                df_grp = df_items.groupby("group_name").size().reset_index(name="qtd").sort_values("qtd", ascending=False).head(10)
                fig2 = px.pie(
                    df_grp, names="group_name", values="qtd",
                    title="Mix por Grupo",
                    color_discrete_sequence=px.colors.sequential.Purples_r,
                )
                fig2.update_layout(paper_bgcolor="white")
                st.plotly_chart(fig2, use_container_width=True)

            section_title("Pesquisar Produto")
            busca = st.text_input("Filtrar por código ou descrição", placeholder="Ex: BPUMP, bomba...")
            if busca:
                mask = (
                    df_items["item_code"].str.contains(busca, case=False, na=False) |
                    df_items["item_description"].str.contains(busca, case=False, na=False)
                )
                st.dataframe(df_items[mask], use_container_width=True)
            else:
                st.dataframe(df_items.head(50), use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao consultar catálogo: {e}")

# ── Tab: BOM Engenharia ──────────────────────────────────────
with tab_bom_eng:
    section_title("Estrutura de Produto — BOM Multi-nível")

    try:
        df_bom = query(f"""
            SELECT
              b.parent_item_code,
              pi.item_description AS produto_pai,
              pf.family_name      AS familia_pai,
              b.child_item_code,
              ci.item_description AS componente,
              cf.family_name      AS familia_comp,
              b.quantity
            FROM `{PRD}.bridge_item_bom` b
            LEFT JOIN `{PRD}.dim_item` pi   ON pi.item_code = b.parent_item_code
            LEFT JOIN `{PRD}.dim_family` pf ON pf.family_code = pi.family_code
            LEFT JOIN `{PRD}.dim_item` ci   ON ci.item_code = b.child_item_code
            LEFT JOIN `{PRD}.dim_family` cf ON cf.family_code = ci.family_code
            ORDER BY b.parent_item_code, b.child_item_code
        """)

        if df_bom.empty:
            st.info("Sem estrutura BOM cadastrada.")
        else:
            c1, c2 = st.columns(2)
            with c1: kpi_card("Produtos com BOM",  str(df_bom["parent_item_code"].nunique()))
            with c2: kpi_card("Relações BOM Total", f'{len(df_bom):,}')

            st.markdown("<br>", unsafe_allow_html=True)
            produtos = sorted(df_bom["parent_item_code"].dropna().unique().tolist())
            sel = st.selectbox("Selecione um produto para ver BOM", ["(todos)"] + produtos)
            df_show = df_bom if sel == "(todos)" else df_bom[df_bom["parent_item_code"] == sel]

            st.dataframe(
                df_show[["parent_item_code", "produto_pai", "child_item_code", "componente", "quantidade" if "quantidade" in df_show else "quantity"]],
                use_container_width=True,
            )

    except Exception as e:
        st.error(f"Erro ao consultar BOM: {e}")

# ── Tab: Roadmap P&D ─────────────────────────────────────────
with tab_roadmap:
    section_title("Roadmap de Desenvolvimento de Produtos")
    coming_soon(
        "Integração Miro + ClickUp pendente",
        "Fluxogramas de P&D no Miro e tarefas no ClickUp serão integrados nesta visão.",
    )

    st.markdown("""
    **KPIs planejados para Engenharia:**
    - Produtos em desenvolvimento (ClickUp — status por fase)
    - Lead time médio de desenvolvimento (ideia → produção)
    - Fichas técnicas homologadas vs pendentes
    - Alterações de BOM por período
    - Produtos com serial ativo vs descontinuados

    **Fontes a integrar:**
    - **Miro** — fluxogramas de processo e P&D
    - **ClickUp** — projetos de desenvolvimento de produto
    """)

st.markdown("---")
st.caption("dm_products (BOM, seriais, itens) · Miro e ClickUp (em integração)")
