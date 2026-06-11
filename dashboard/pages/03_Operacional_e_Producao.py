"""
Operacional e Produção — OPs · Eficiência · Estoque · BOM
Gold primary → Bronze fallback automático
"""

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Operacional | Nevoni 360°", page_icon="🏭", layout="wide")

from dashboard.utils.components import inject_css, page_header, kpi_card, section_title, sidebar_brand
from dashboard.utils.bq_client import query_layer, fmt_num, PROJECT_PROD
from dashboard.utils.gold_tables import Operacional as G

inject_css()
sidebar_brand()

PROJ = PROJECT_PROD
PROD = f"{PROJ}.dm_production"
INV  = f"{PROJ}.dm_inventory"
PRD  = f"{PROJ}.dm_products"

page_header(
    title="🏭 Operacional e Produção",
    subtitle="Ordens de Produção · Eficiência · Estoque · BOM",
    sources=[{"name": "gold_operacional", "active": True}, {"name": "ERP (Bronze fallback)", "active": True}],
)

tab_op, tab_est, tab_bom = st.tabs([
    "⚙️ Ordens de Produção", "📦 Estoque", "🗂️ BOM",
])

# ── Ordens de Produção ───────────────────────────────────────
with tab_op:
    section_title("Ordens de Produção — Planejado vs Realizado")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.PRODUCAO_MENSAL}` ORDER BY mes DESC LIMIT 24",
        bronze_sql=f"""
            SELECT
              DATE_TRUNC(start_date, MONTH) AS mes,
              status,
              COUNT(*)                       AS qtd_op,
              SUM(quantity_plan)             AS qtd_planejada,
              SUM(quantity_produced)         AS qtd_produzida
            FROM `{PROD}.fact_production_order`
            WHERE start_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
              AND start_date IS NOT NULL
            GROUP BY 1, 2 ORDER BY 1
        """,
        label="Ordens de Produção",
    )

    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"])
        df_sorted = df.sort_values("mes")
        df_tot    = df_sorted.groupby("mes")[["qtd_op", "qtd_planejada", "qtd_produzida"]].sum().reset_index() \
                    if "status" in df.columns else df_sorted

        qtd_op   = "qtd_op"       if "qtd_op"       in df.columns else None
        plan_col = "qtd_planejada" if "qtd_planejada" in df.columns else None
        prod_col = "qtd_produzida" if "qtd_produzida" in df.columns else None

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Total OPs",       f'{int(df_tot[qtd_op].sum()):,}'   if qtd_op   else "—")
        with c2: kpi_card("Qtd. Planejada",  fmt_num(df_tot[plan_col].sum())    if plan_col else "—")
        with c3: kpi_card("Qtd. Produzida",  fmt_num(df_tot[prod_col].sum())    if prod_col else "—", variant="success")
        with c4:
            if plan_col and prod_col and df_tot[plan_col].sum():
                efic = df_tot[prod_col].sum() / df_tot[plan_col].sum() * 100
                kpi_card("Eficiência Global", f"{efic:.1f}%",
                          variant="success" if efic >= 90 else "warning" if efic >= 70 else "danger")
            else:
                kpi_card("Eficiência", "—")

        st.markdown("<br>", unsafe_allow_html=True)
        if plan_col and prod_col:
            fig = px.bar(df_tot, x="mes", y=[plan_col, prod_col],
                         barmode="group",
                         title="Planejado vs Produzido por Mês",
                         labels={"mes": "Mês", "value": "Qtd.", "variable": ""},
                         color_discrete_sequence=["#1E1882", "#10B981"])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

        if "status" in df.columns and qtd_op:
            fig2 = px.pie(df.groupby("status")[qtd_op].sum().reset_index(),
                          names="status", values=qtd_op,
                          title="OPs por Status",
                          color_discrete_sequence=["#10B981", "#1E1882", "#F59E0B", "#EF4444"])
            fig2.update_layout(paper_bgcolor="white")
            col_p, _ = st.columns([1, 2])
            with col_p:
                st.plotly_chart(fig2, use_container_width=True)

    # Componentes consumidos
    section_title("Consumo de Componentes (BOM × OP)")
    df_comp, _ = query_layer(
        gold_sql=f"SELECT item_code, SUM(quantity_consumed) AS consumido FROM `{G.PRODUCAO_MENSAL}` GROUP BY 1 ORDER BY 2 DESC LIMIT 20",
        bronze_sql=f"""
            SELECT
              item_code,
              SUM(quantity_consumed) AS consumido
            FROM `{PROD}.fact_production_comp_item`
            WHERE loaded_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 395 DAY)
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 20
        """,
        label="Componentes",
    )
    if not df_comp.empty and "consumido" in df_comp.columns:
        fig3 = px.bar(df_comp, x="item_code", y="consumido",
                      title="Top 20 Componentes Consumidos",
                      labels={"item_code": "Item", "consumido": "Qtd."},
                      color_discrete_sequence=["#4844C8"])
        fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig3, use_container_width=True)

# ── Estoque ──────────────────────────────────────────────────
with tab_est:
    section_title("Saldo de Estoque (Snapshot)")

    df_snap, _ = query_layer(
        gold_sql=f"SELECT * FROM `{G.ESTOQUE_SNAPSHOT}` ORDER BY saldo DESC LIMIT 300",
        bronze_sql=f"""
            SELECT
              s.item_code,
              i.item_description,
              f.family_name,
              g.group_name,
              s.total_qty  AS saldo,
              s.warehouse
            FROM `{INV}.snapshot_inventory_balance` s
            LEFT JOIN `{PRD}.dim_item`   i USING (item_code)
            LEFT JOIN `{PRD}.dim_family` f ON f.family_code = i.family_code
            LEFT JOIN `{PRD}.dim_group`  g ON g.group_code  = i.group_code
            WHERE s.total_qty > 0
            ORDER BY s.total_qty DESC
            LIMIT 300
        """,
        label="Estoque Snapshot",
    )

    if not df_snap.empty:
        saldo_col = next((c for c in ["saldo", "total_qty"] if c in df_snap.columns), None)
        fam_col   = next((c for c in ["family_name", "familia"] if c in df_snap.columns), None)

        c1, c2, c3 = st.columns(3)
        with c1: kpi_card("Itens em Estoque", f'{len(df_snap):,}')
        with c2: kpi_card("Total Qtd.", fmt_num(df_snap[saldo_col].sum()) if saldo_col else "—")
        with c3: kpi_card("Famílias", str(df_snap[fam_col].nunique()) if fam_col else "—")

        st.markdown("<br>", unsafe_allow_html=True)
        col_t, col_c = st.columns([2, 1])
        with col_t:
            st.dataframe(df_snap, use_container_width=True, hide_index=True)
        with col_c:
            if fam_col and saldo_col:
                df_fam = df_snap.groupby(fam_col)[saldo_col].sum().reset_index().sort_values(saldo_col, ascending=False).head(10)
                fig = px.pie(df_fam, names=fam_col, values=saldo_col,
                             title="Estoque por Família",
                             color_discrete_sequence=px.colors.sequential.Purples_r)
                fig.update_layout(paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)

    section_title("Movimentação Mensal")
    df_mov, _ = query_layer(
        gold_sql=f"SELECT * FROM `{G.MOVIMENTACAO_MENSAL}` ORDER BY mes DESC LIMIT 24",
        bronze_sql=f"""
            SELECT
              DATE_TRUNC(movement_date, MONTH) AS mes,
              SUM(quantity_in)                  AS entradas,
              SUM(quantity_out)                 AS saidas
            FROM `{INV}.fact_inventory_movement`
            WHERE movement_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
              AND movement_date IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """,
        label="Movimentação",
    )
    if not df_mov.empty:
        df_mov["mes"] = pd.to_datetime(df_mov["mes"])
        ent_col = next((c for c in ["entradas", "entrada"] if c in df_mov.columns), None)
        sai_col = next((c for c in ["saidas", "saída"] if c in df_mov.columns), None)
        if ent_col and sai_col:
            fig2 = px.bar(df_mov.sort_values("mes"), x="mes", y=[ent_col, sai_col],
                          barmode="group", title="Entradas vs Saídas de Estoque",
                          labels={"mes": "Mês", "value": "Qtd.", "variable": ""},
                          color_discrete_sequence=["#10B981", "#EF4444"])
            fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig2, use_container_width=True)

# ── BOM ──────────────────────────────────────────────────────
with tab_bom:
    section_title("Estrutura de Produto (BOM)")

    df, _ = query_layer(
        gold_sql=f"SELECT * FROM `{G.BOM_COMPLETO}` ORDER BY parent_item_code LIMIT 2000",
        bronze_sql=f"""
            SELECT
              b.parent_item_code,
              pi.item_description AS produto_pai,
              f.family_name        AS familia_pai,
              b.child_item_code,
              ci.item_description AS componente,
              b.quantity
            FROM `{PRD}.bridge_item_bom` b
            LEFT JOIN `{PRD}.dim_item`   pi ON pi.item_code = b.parent_item_code
            LEFT JOIN `{PRD}.dim_item`   ci ON ci.item_code = b.child_item_code
            LEFT JOIN `{PRD}.dim_family` f  ON f.family_code = pi.family_code
            ORDER BY b.parent_item_code
            LIMIT 2000
        """,
        label="BOM",
    )

    if not df.empty:
        pai_col = next((c for c in ["parent_item_code", "produto_pai"] if c in df.columns), None)
        c1, c2 = st.columns(2)
        with c1: kpi_card("Produtos com BOM",  str(df[pai_col].nunique()) if pai_col else "—")
        with c2: kpi_card("Relações BOM Total", f'{len(df):,}')

        st.markdown("<br>", unsafe_allow_html=True)
        if pai_col:
            sel = st.selectbox("Filtrar produto pai",
                               ["(todos)"] + sorted(df[pai_col].dropna().unique().tolist()))
            df = df if sel == "(todos)" else df[df[pai_col] == sel]
        st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("gold_operacional (Gold) / dm_production + dm_inventory + dm_products (Bronze fallback) · sapient-metrics-492914-m7")
