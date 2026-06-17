"""
Setor Fiscal — Impostos · Importações · Carga Tributária
Gold primary → Bronze fallback automático
"""

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Fiscal | Nevoni 360°", page_icon="", layout="wide")

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dashboard.utils.components import inject_css, page_header, kpi_card, section_title, sidebar_brand
from dashboard.utils.bq_client import query_layer, fmt_brl, PROJECT_PROD
from dashboard.utils.gold_tables import Fiscal as G

inject_css()
sidebar_brand()

PROJ    = PROJECT_PROD
PAY     = f"{PROJ}.dm_payments"
IMPORTS = f"{PROJ}.dm_imports"

page_header(
    title="Setor Fiscal",
    subtitle="Impostos · Importações · Carga Tributária",
    sources=[{"name": "gold_fiscal", "active": True}, {"name": "ERP (Bronze fallback)", "active": True}],
)

tab_imp, tab_import, tab_carga = st.tabs([
    "Impostos Mensais", "Importações", "Carga Tributária",
])

# ── Impostos ─────────────────────────────────────────────────
with tab_imp:
    section_title("Impostos por Tipo e Período")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.IMPOSTOS_MENSAIS}` ORDER BY mes DESC LIMIT 200",
        bronze_sql=f"""
            SELECT
              tax_type,
              DATE_TRUNC(period, MONTH) AS mes,
              SUM(amount)               AS valor
            FROM `{PAY}.fact_tax_ledger`
            WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
              AND period IS NOT NULL
            GROUP BY 1, 2 ORDER BY 2, 1
        """,
        label="Ledger Fiscal",
    )

    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"])
        val_col  = next((c for c in ["valor", "montante", "amount"] if c in df.columns), None)
        tipo_col = next((c for c in ["tipo_imposto", "tax_type", "imposto"] if c in df.columns), None)

        c1, c2 = st.columns(2)
        with c1: kpi_card("Total Impostos (13m)", fmt_brl(df[val_col].sum()) if val_col else "—", variant="warning")
        with c2: kpi_card("Tipos de Imposto", str(df[tipo_col].nunique()) if tipo_col else "—")

        st.markdown("<br>", unsafe_allow_html=True)
        col_bar, col_pie = st.columns(2)
        with col_bar:
            if val_col:
                fig = px.bar(df.groupby("mes")[val_col].sum().reset_index().sort_values("mes"),
                             x="mes", y=val_col,
                             title="Impostos por Mês",
                             labels={"mes": "Mês", val_col: "R$"},
                             color_discrete_sequence=["#1E1882"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
        with col_pie:
            if tipo_col and val_col:
                df_tipo = df.groupby(tipo_col)[val_col].sum().reset_index().sort_values(val_col, ascending=False)
                fig2 = px.pie(df_tipo, names=tipo_col, values=val_col,
                              title="Mix por Tipo",
                              color_discrete_sequence=px.colors.sequential.Purples_r)
                fig2.update_layout(paper_bgcolor="white")
                st.plotly_chart(fig2, use_container_width=True)

        if tipo_col and val_col:
            fig3 = px.bar(df.sort_values("mes"), x="mes", y=val_col, color=tipo_col,
                          title="Evolução por Tipo de Imposto",
                          labels={"mes": "Mês", val_col: "R$", tipo_col: "Tipo"},
                          color_discrete_sequence=px.colors.sequential.Purples)
            fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig3, use_container_width=True)

# ── Importações ──────────────────────────────────────────────
with tab_import:
    section_title("Importações Consolidadas")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.IMPORTACOES_MENSAIS}` ORDER BY mes DESC LIMIT 100",
        bronze_sql=f"""
            SELECT
              DATE_TRUNC(order_date, MONTH) AS mes,
              origin_country,
              COUNT(*)                       AS qtd_importacoes,
              SUM(total_usd)                 AS total_usd,
              SUM(total_brl)                 AS total_brl,
              SUM(fob_value)                 AS fob_value,
              SUM(freight_value)             AS freight_value,
              SUM(ii_amount)                 AS II,
              SUM(ipi_amount)                AS IPI,
              SUM(pis_amount)                AS PIS,
              SUM(cofins_amount)             AS COFINS,
              SUM(icms_amount)               AS ICMS
            FROM `{IMPORTS}.fact_import_order`
            WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 24 MONTH)
              AND order_date IS NOT NULL
            GROUP BY 1, 2 ORDER BY 1
        """,
        label="Importações",
    )

    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"])
        brl_col  = next((c for c in ["total_brl", "valor_brl"] if c in df.columns), None)
        usd_col  = next((c for c in ["total_usd", "fob_usd"] if c in df.columns), None)
        qtd_col  = next((c for c in ["qtd_importacoes", "qtd"] if c in df.columns), None)
        pais_col = next((c for c in ["origin_country", "pais_origem"] if c in df.columns), None)

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Total (BRL)", fmt_brl(df[brl_col].sum()) if brl_col else "—", variant="warning")
        with c2: kpi_card("Total (USD)", f'$ {df[usd_col].sum():,.0f}' if usd_col else "—")
        with c3: kpi_card("Importações", f'{int(df[qtd_col].sum()):,}' if qtd_col else "—")
        with c4: kpi_card("Países Origem", str(df[pais_col].nunique()) if pais_col else "—")

        st.markdown("<br>", unsafe_allow_html=True)
        col_time, col_pais = st.columns(2)
        with col_time:
            if brl_col:
                df_mes = df.groupby("mes")[brl_col].sum().reset_index()
                fig = px.bar(df_mes, x="mes", y=brl_col,
                             title="Importações por Mês (BRL)",
                             labels={"mes": "Mês", brl_col: "R$"},
                             color_discrete_sequence=["#1E1882"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
        with col_pais:
            if pais_col and usd_col:
                df_pais = df.groupby(pais_col)[usd_col].sum().reset_index().sort_values(usd_col, ascending=False).head(10)
                fig2 = px.bar(df_pais, x=usd_col, y=pais_col, orientation="h",
                              title="Top 10 Países (USD)",
                              labels={pais_col: "País", usd_col: "USD"},
                              color_discrete_sequence=["#4844C8"])
                fig2.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                                   yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig2, use_container_width=True)

        # Tributos se existirem como colunas
        tributos = [c for c in ["II", "IPI", "PIS", "COFINS", "ICMS"] if c in df.columns]
        if tributos:
            section_title("Tributos de Importação por Mês")
            df_melt = df.groupby("mes")[tributos].sum().reset_index().melt(
                id_vars="mes", value_vars=tributos, var_name="Tributo", value_name="Valor")
            fig3 = px.bar(df_melt.sort_values("mes"), x="mes", y="Valor", color="Tributo",
                          title="Tributos por Mês",
                          labels={"mes": "Mês"},
                          color_discrete_sequence=px.colors.sequential.Purples)
            fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig3, use_container_width=True)

# ── Carga Tributária ─────────────────────────────────────────
with tab_carga:
    section_title("Carga Tributária por Produto / Família")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.CARGA_TRIBUTARIA}` ORDER BY mes DESC LIMIT 500",
        bronze_sql=f"""
            SELECT
              ii.item_code,
              SUM(ii.ii_amount + ii.ipi_amount + ii.pis_amount
                  + ii.cofins_amount + ii.icms_amount) AS tributos_totais,
              SUM(ii.total_brl)                          AS custo_total_brl,
              SAFE_DIVIDE(
                SUM(ii.ii_amount + ii.ipi_amount + ii.pis_amount
                    + ii.cofins_amount + ii.icms_amount),
                NULLIF(SUM(ii.total_brl), 0)
              ) * 100 AS carga_tributaria_pct
            FROM `{IMPORTS}.fact_import_item` ii
            GROUP BY 1
            ORDER BY 4 DESC
            LIMIT 50
        """,
        label="Carga Tributária",
    )

    if not df.empty:
        carga_col = next((c for c in ["carga_tributaria_pct", "pct_tributos", "carga_tributaria"] if c in df.columns), None)
        item_col  = next((c for c in ["item_code", "produto", "familia"] if c in df.columns), None)
        val_col   = next((c for c in ["tributos_totais"] if c in df.columns), None)

        col_l, col_r = st.columns(2)
        with col_l:
            if item_col and carga_col:
                df_top = df.nlargest(20, carga_col)
                fig = px.bar(df_top, x=item_col, y=carga_col,
                             title="Carga Tributária % — Top 20 Itens",
                             labels={item_col: "Item", carga_col: "% Carga"},
                             color_discrete_sequence=["#1E1882"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
        with col_r:
            if item_col and val_col:
                df_top2 = df.nlargest(10, val_col)
                fig2 = px.pie(df_top2, names=item_col, values=val_col,
                              title="Tributos Absolutos — Top 10",
                              color_discrete_sequence=px.colors.sequential.Purples_r)
                fig2.update_layout(paper_bgcolor="white")
                st.plotly_chart(fig2, use_container_width=True)

        st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("gold_fiscal (Gold) / dm_payments + dm_imports (Bronze fallback) · sapient-metrics-492914-m7")
