"""
SAC e Assistência Técnica — Atendimentos · SLA · Chamadas · Chat
Gold primary → Bronze fallback automático
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
from dashboard.utils.bq_client import query_layer, PROJECT_PROD
from dashboard.utils.gold_tables import SAC as G


PROJ = PROJECT_PROD
# Pipelines SAC no Pipedrive (IDs mapeados no settings)
SAC_PIPELINE_IDS = "(4, 5, 7, 9)"

page_header(
    title="SAC e Assistência Técnica",
    subtitle="Atendimentos · SLA · Chamadas GoTo Connect · Chat Umbler",
    sources=[
        {"name": "gold_sac", "active": True},
        {"name": "CRM + GoTo + Umbler (Bronze fallback)", "active": True},
    ],
)

tab_atend, tab_sla, tab_calls, tab_chat = st.tabs([
    "Atendimentos", "SLA", "Chamadas", "Chat",
])

# ── Atendimentos ─────────────────────────────────────────────
with tab_atend:
    section_title("Volume de Atendimentos por Mês")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.ATENDIMENTOS_MENSAIS}` ORDER BY mes DESC LIMIT 24",
        bronze_sql=f"""
            SELECT
              DATE_TRUNC(TIMESTAMP(add_time), MONTH) AS mes,
              pipeline_id,
              status,
              COUNT(*)                               AS qtd_atendimentos,
              AVG(
                TIMESTAMP_DIFF(
                  COALESCE(TIMESTAMP(close_time), CURRENT_TIMESTAMP()),
                  TIMESTAMP(add_time),
                  HOUR
                )
              ) AS tmr_horas
            FROM `{PROJ}.crm_raw.deals`
            WHERE pipeline_id IN {SAC_PIPELINE_IDS}
              AND add_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 395 DAY)
            GROUP BY 1, 2, 3
            ORDER BY 1
        """,
        label="Atendimentos SAC",
    )

    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"])
        qtd_col  = next((c for c in ["qtd_atendimentos", "tickets", "qtd"] if c in df.columns), None)
        stat_col = next((c for c in ["status"] if c in df.columns), None)
        pip_col  = next((c for c in ["pipeline_id", "pipeline"] if c in df.columns), None)

        total = df[qtd_col].sum() if qtd_col else 0
        ganhos = df[df[stat_col] == "won"] if stat_col and "won" in df[stat_col].values else pd.DataFrame()

        c1, c2, c3, c4 = st.columns(4)
        with c1: kpi_card("Total Atendimentos", f'{int(total):,}')
        with c2: kpi_card("Resolvidos", f'{int(ganhos[qtd_col].sum()):,}' if not ganhos.empty and qtd_col else "—", variant="success")
        with c3:
            taxa = ganhos[qtd_col].sum() / total * 100 if not ganhos.empty and qtd_col and total else None
            kpi_card("Taxa Resolução", f"{taxa:.1f}%" if taxa else "—",
                      variant="success" if (taxa or 0) > 80 else "warning")
        with c4:
            tmr_col = next((c for c in ["tmr_horas"] if c in df.columns), None)
            avg_tmr = float(df[tmr_col].mean()) if tmr_col else None
            kpi_card("TMR Médio", f"{avg_tmr:.0f}h" if avg_tmr else "—",
                      variant="success" if (avg_tmr or 999) < 48 else "warning")

        st.markdown("<br>", unsafe_allow_html=True)
        df_mes = df.groupby("mes")[qtd_col].sum().reset_index() if qtd_col else None
        if df_mes is not None:
            fig = px.bar(df_mes.sort_values("mes"), x="mes", y=qtd_col,
                         title="Volume de Atendimentos por Mês",
                         labels={"mes": "Mês", qtd_col: "Tickets"},
                         color_discrete_sequence=["#1E1882"])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

        col_s, col_p = st.columns(2)
        with col_s:
            if stat_col and qtd_col:
                fig2 = px.pie(df.groupby(stat_col)[qtd_col].sum().reset_index(),
                              names=stat_col, values=qtd_col, title="Por Status",
                              color_discrete_sequence=["#10B981", "#F59E0B", "#EF4444", "#1E1882"])
                fig2.update_layout(paper_bgcolor="white")
                st.plotly_chart(fig2, use_container_width=True)
        with col_p:
            if pip_col and qtd_col:
                df_pip = df.groupby(pip_col)[qtd_col].sum().reset_index()
                df_pip[pip_col] = df_pip[pip_col].astype(str)
                fig3 = px.bar(df_pip, x=pip_col, y=qtd_col,
                              title="Atendimentos por Pipeline",
                              labels={pip_col: "Pipeline", qtd_col: "Qtd."},
                              color_discrete_sequence=["#4844C8"])
                fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig3, use_container_width=True)

    else:
        st.info("Dataset `crm_raw.deals` não localizado. Verifique permissões BQ e pipeline IDs SAC.")

# ── SLA ──────────────────────────────────────────────────────
with tab_sla:
    section_title("Indicadores de SLA")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.SLA_MENSAL}` ORDER BY mes DESC LIMIT 24",
        bronze_sql=f"""
            SELECT
              DATE_TRUNC(TIMESTAMP(add_time), MONTH) AS mes,
              pipeline_id,
              AVG(
                TIMESTAMP_DIFF(
                  COALESCE(TIMESTAMP(close_time), CURRENT_TIMESTAMP()),
                  TIMESTAMP(add_time),
                  HOUR
                )
              ) AS tmr_horas,
              COUNT(*) AS qtd
            FROM `{PROJ}.crm_raw.deals`
            WHERE pipeline_id IN {SAC_PIPELINE_IDS}
              AND add_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 395 DAY)
            GROUP BY 1, 2 ORDER BY 1
        """,
        label="SLA",
    )

    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"])
        tmr_col = next((c for c in ["tmr_horas", "tmr"] if c in df.columns), None)

        if tmr_col:
            ultimo_tmr = float(df.sort_values("mes").groupby("mes")[tmr_col].mean().iloc[-1])
            c1, c2 = st.columns(2)
            with c1:
                kpi_card("TMR Último Mês", f"{ultimo_tmr:.1f}h",
                          variant="success" if ultimo_tmr < 48 else "warning" if ultimo_tmr < 96 else "danger")
            with c2:
                avg_geral = float(df[tmr_col].mean())
                kpi_card("TMR Médio Geral", f"{avg_geral:.1f}h",
                          variant="success" if avg_geral < 48 else "warning")

            st.markdown("<br>", unsafe_allow_html=True)
            df_mes_tmr = df.groupby("mes")[tmr_col].mean().reset_index()
            fig = px.line(df_mes_tmr.sort_values("mes"), x="mes", y=tmr_col,
                          title="TMR Médio por Mês (horas)",
                          markers=True, color_discrete_sequence=["#1E1882"])
            fig.add_hline(y=48, line_dash="dot", line_color="#F59E0B", annotation_text="Meta 48h")
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.dataframe(df, use_container_width=True)

# ── Chamadas GoTo ────────────────────────────────────────────
with tab_calls:
    section_title("Chamadas GoTo Connect")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.CHAMADAS_MENSAIS}` ORDER BY mes DESC LIMIT 24",
        bronze_sql=f"""
            SELECT
              DATE_TRUNC(call_date, MONTH) AS mes,
              direction,
              call_result,
              COUNT(*)                      AS qtd_chamadas,
              SUM(duration_seconds) / 60    AS total_minutos,
              AVG(duration_seconds) / 60    AS avg_minutos
            FROM `{PROJ}.dm_calls.fact_call`
            WHERE call_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
              AND call_date IS NOT NULL
            GROUP BY 1, 2, 3 ORDER BY 1
        """,
        label="Chamadas GoTo",
    )

    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"])
        qtd_col = next((c for c in ["qtd_chamadas", "chamadas", "calls"] if c in df.columns), None)
        min_col = next((c for c in ["total_minutos", "minutos"] if c in df.columns), None)
        dir_col = next((c for c in ["direction", "direcao"] if c in df.columns), None)
        res_col = next((c for c in ["call_result", "resultado"] if c in df.columns), None)

        c1, c2, c3 = st.columns(3)
        with c1: kpi_card("Total Chamadas", f'{int(df[qtd_col].sum()):,}' if qtd_col else "—")
        with c2: kpi_card("Minutos Total",  f'{df[min_col].sum():,.0f}' if min_col else "—")
        with c3:
            if qtd_col and min_col and df[qtd_col].sum():
                kpi_card("Duração Média", f'{df[min_col].sum() / df[qtd_col].sum():.1f} min')
            else:
                kpi_card("Duração Média", "—")

        st.markdown("<br>", unsafe_allow_html=True)
        if qtd_col:
            fig = px.line(df.groupby("mes")[qtd_col].sum().reset_index().sort_values("mes"),
                          x="mes", y=qtd_col,
                          title="Volume de Chamadas por Mês",
                          markers=True, color_discrete_sequence=["#1E1882"])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

        col_d, col_r = st.columns(2)
        with col_d:
            if dir_col and qtd_col:
                fig2 = px.pie(df.groupby(dir_col)[qtd_col].sum().reset_index(),
                              names=dir_col, values=qtd_col, title="Entrada vs Saída",
                              color_discrete_sequence=["#1E1882", "#4844C8"])
                fig2.update_layout(paper_bgcolor="white")
                st.plotly_chart(fig2, use_container_width=True)
        with col_r:
            if res_col and qtd_col:
                fig3 = px.pie(df.groupby(res_col)[qtd_col].sum().reset_index(),
                              names=res_col, values=qtd_col, title="Por Resultado",
                              color_discrete_sequence=["#10B981", "#EF4444", "#F59E0B", "#1E1882"])
                fig3.update_layout(paper_bgcolor="white")
                st.plotly_chart(fig3, use_container_width=True)
    else:
        coming_soon("GoTo Connect", "Tabela `dm_calls.fact_call` ainda não carregada no BigQuery.")

# ── Chat Umbler ──────────────────────────────────────────────
with tab_chat:
    section_title("Chat e Mensageria — Umbler")

    df, camada = query_layer(
        gold_sql=f"SELECT * FROM `{G.CHAT_MENSAIS}` ORDER BY mes DESC LIMIT 24",
        bronze_sql=f"""
            SELECT
              DATE_TRUNC(created_at, MONTH) AS mes,
              channel                        AS canal,
              COUNT(*)                       AS conversas
            FROM `{PROJ}.umbler_raw.conversations`
            WHERE created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
              AND created_at IS NOT NULL
            GROUP BY 1, 2 ORDER BY 1
        """,
        label="Chat Umbler",
    )

    if not df.empty:
        df["mes"] = pd.to_datetime(df["mes"])
        qtd_col  = next((c for c in ["conversas", "qtd_conversas"] if c in df.columns), None)
        canal_col = next((c for c in ["canal", "channel"] if c in df.columns), None)

        c1, c2 = st.columns(2)
        with c1: kpi_card("Total Conversas", f'{int(df[qtd_col].sum()):,}' if qtd_col else "—")
        with c2: kpi_card("Canais", str(df[canal_col].nunique()) if canal_col else "—")

        if qtd_col:
            fig = px.bar(df.sort_values("mes"), x="mes", y=qtd_col,
                         color=canal_col if canal_col else None,
                         title="Conversas por Mês",
                         labels={"mes": "Mês", qtd_col: "Conversas"},
                         color_discrete_sequence=px.colors.sequential.Purples_r)
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
    else:
        coming_soon("Umbler Talk", "Dataset `umbler_raw` ainda não carregado no BigQuery.")

st.markdown("---")
st.caption("gold_sac (Gold) / crm_raw + dm_calls + umbler_raw (Bronze fallback) · sapient-metrics-492914-m7")
