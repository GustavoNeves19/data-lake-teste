"""
Setor Financeiro — DRE · Caixa · Contas a Pagar/Receber · KPIs · Metas
Fonte: gold_financeiro (camada ouro exclusivamente)
"""

import datetime as _dt

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Financeiro | Nevoni 360°", page_icon="💰", layout="wide")

from dashboard.utils.components import inject_css, page_header, kpi_card, section_title, sidebar_brand
from dashboard.utils.bq_client import query, gold_not_ready, fmt_brl, fmt_pct
from dashboard.utils.gold_tables import Financeiro as G

inject_css()
sidebar_brand()

page_header(
    title="💰 Setor Financeiro",
    subtitle="DRE · KPIs Mensais · Contas a Pagar/Receber · Fluxo de Caixa",
    sources=[{"name": "gold_financeiro", "active": True}],
)

# ── Filtros globais ──────────────────────────────────────────
_today = _dt.date.today()
_mes_atual = _today.replace(day=1)
_default_inicio = (_mes_atual.replace(year=_mes_atual.year - 1)
                   if _mes_atual.month == 1
                   else _mes_atual.replace(year=_mes_atual.year - 1, month=_mes_atual.month))

f_regime, f_de, f_ate = st.columns([1, 1, 1])
with f_regime:
    regime_sel = st.selectbox("Regime", ["CAIXA", "COMPETENCIA"], index=0)
with f_de:
    data_inicio = st.date_input("De (mês)", value=_default_inicio, format="DD/MM/YYYY")
with f_ate:
    data_fim = st.date_input("Até (mês)", value=_mes_atual, format="DD/MM/YYYY")

# Normaliza para primeiro dia do mês (gold guarda `mes` como DATE do dia 1)
_ini = data_inicio.replace(day=1)
_fim = data_fim.replace(day=1)
if _fim < _ini:
    st.warning("Data final anterior à inicial — ajustando.")
    _fim = _ini

if _mes_atual >= _ini and _mes_atual <= _fim:
    st.caption(f"ℹ️ Mês corrente ({_mes_atual.strftime('%m/%Y')}) é parcial — ainda em curso.")

tab_kpi, tab_dre, tab_cr, tab_cp, tab_liq, tab_fc = st.tabs([
    "📊 KPIs", "📈 DRE", "📥 Contas a Receber",
    "📤 Contas a Pagar", "✅ Liquidações", "💧 Fluxo de Caixa",
])

# ── KPIs Mensais ─────────────────────────────────────────────
with tab_kpi:
    section_title(f"KPIs Mensais — Regime {regime_sel.title()}")
    try:
        df = query(f"""
            SELECT *
            FROM `{G.KPIS_MENSAIS}`
            WHERE regime = '{regime_sel}'
              AND mes BETWEEN DATE '{_ini.isoformat()}' AND DATE '{_fim.isoformat()}'
            ORDER BY mes DESC
        """)
        if df.empty:
            gold_not_ready(G.KPIS_MENSAIS)
        else:
            # espera colunas: mes, faturamento, margem_bruta, ebitda, lucro_liquido, etc.
            ultimo = df.iloc[0]
            ant    = df.iloc[1] if len(df) > 1 else None

            cols = st.columns(4)
            kpis = [
                ("Faturamento",   "faturamento",   "fmt_brl"),
                ("Margem Bruta",  "margem_bruta",  "fmt_brl"),
                ("EBITDA",        "ebitda",         "fmt_brl"),
                ("Lucro Líquido", "lucro_liquido",  "fmt_brl"),
            ]
            for col, (label, field, _) in zip(cols, kpis):
                with col:
                    val = ultimo.get(field)
                    if ant is not None and ant.get(field):
                        delta = (val - ant[field]) / abs(ant[field]) * 100
                        kpi_card(label, fmt_brl(val),
                                 delta=fmt_pct(delta),
                                 delta_dir="up" if delta >= 0 else "down",
                                 variant="success" if delta >= 0 else "danger")
                    else:
                        kpi_card(label, fmt_brl(val))

            st.markdown("<br>", unsafe_allow_html=True)
            df["mes"] = pd.to_datetime(df["mes"])
            df_sorted = df.sort_values("mes")
            metricas_disp = [c for c in ["faturamento", "margem_bruta", "ebitda"] if c in df.columns]
            if metricas_disp:
                fig = px.line(df_sorted, x="mes", y=metricas_disp,
                              title=f"Evolução de KPIs — {len(df_sorted)} meses",
                              markers=True,
                              labels={"mes": "Mês", "value": "R$", "variable": ""},
                              color_discrete_sequence=["#1E1882", "#10B981", "#F59E0B"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        gold_not_ready(G.KPIS_MENSAIS, str(e))

# ── DRE ──────────────────────────────────────────────────────
with tab_dre:
    section_title(f"DRE — Demonstração de Resultado · Regime {regime_sel.title()}")
    try:
        df = query(f"""
            SELECT *
            FROM `{G.DRE_MENSAL}`
            WHERE regime = '{regime_sel}'
              AND mes BETWEEN DATE '{_ini.isoformat()}' AND DATE '{_fim.isoformat()}'
            ORDER BY mes DESC, ordem_exibicao
        """)
        if df.empty:
            gold_not_ready(G.DRE_MENSAL)
        else:
            meses_disp = sorted(df["mes"].unique(), reverse=True)
            col_sel, _ = st.columns([1, 3])
            with col_sel:
                mes_sel = st.selectbox("Mês de referência", meses_disp,
                                       format_func=lambda m: str(m)[:7])

            df_mes = df[df["mes"] == mes_sel]

            # Comparativo: mês selecionado vs anterior
            idx = list(meses_disp).index(mes_sel)
            df_ant = df[df["mes"] == meses_disp[idx + 1]] if idx + 1 < len(meses_disp) else pd.DataFrame()

            col_t, col_c = st.columns([3, 2])
            with col_t:
                df_show = df_mes[["grupo_dre", "descricao", "valor"]].copy() if "grupo_dre" in df_mes else df_mes
                df_show["valor"] = df_show["valor"].apply(fmt_brl)
                st.dataframe(df_show, use_container_width=True, hide_index=True)

            with col_c:
                if "grupo_dre" in df_mes.columns and "valor" in df_mes.columns:
                    df_pos = df_mes[df_mes["valor"] > 0]
                    if not df_pos.empty:
                        fig = px.pie(df_pos, names="grupo_dre", values="valor",
                                     title="Composição DRE (valores positivos)",
                                     color_discrete_sequence=px.colors.sequential.Purples_r)
                        fig.update_layout(paper_bgcolor="white")
                        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        gold_not_ready(G.DRE_MENSAL, str(e))

# ── Contas a Receber ─────────────────────────────────────────
with tab_cr:
    section_title("Contas a Receber")
    st.info("📅 Disponível na Fase 2 (próxima entrega)")
    try:
        df = query(f"""
            SELECT *
            FROM `{G.CONTAS_RECEBER}`
            ORDER BY vencimento
        """)
        if df.empty:
            gold_not_ready(G.CONTAS_RECEBER)
        else:
            vencido = df[df["vencimento"] < pd.Timestamp("today")] if "vencimento" in df else pd.DataFrame()
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi_card("Total a Receber", fmt_brl(df["valor"].sum()), variant="success")
            with c2: kpi_card("Títulos",         f'{len(df):,}')
            with c3: kpi_card("Vencido",         fmt_brl(vencido["valor"].sum() if not vencido.empty else 0), variant="danger")
            with c4:
                pv = vencido["valor"].sum() / df["valor"].sum() * 100 if df["valor"].sum() else 0
                kpi_card("% Vencido", f"{pv:.1f}%",
                          variant="danger" if pv > 15 else "warning" if pv > 5 else "success")

            st.markdown("<br>", unsafe_allow_html=True)
            if "vencimento" in df.columns:
                df["mes"] = pd.to_datetime(df["vencimento"]).dt.to_period("M").dt.to_timestamp()
                fig = px.bar(df.groupby("mes")["valor"].sum().reset_index(),
                             x="mes", y="valor",
                             title="Recebíveis por Vencimento",
                             labels={"mes": "Mês", "valor": "R$"},
                             color_discrete_sequence=["#1E1882"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df.head(200), use_container_width=True)

    except Exception as e:
        gold_not_ready(G.CONTAS_RECEBER, str(e))

# ── Contas a Pagar ───────────────────────────────────────────
with tab_cp:
    section_title("Contas a Pagar")
    st.info("📅 Disponível na Fase 2 (próxima entrega)")
    try:
        df = query(f"""
            SELECT *
            FROM `{G.CONTAS_PAGAR}`
            ORDER BY vencimento
        """)
        if df.empty:
            gold_not_ready(G.CONTAS_PAGAR)
        else:
            vencido = df[df["vencimento"] < pd.Timestamp("today")] if "vencimento" in df else pd.DataFrame()
            c1, c2, c3 = st.columns(3)
            with c1: kpi_card("Total a Pagar", fmt_brl(df["valor"].sum()), variant="warning")
            with c2: kpi_card("Títulos",       f'{len(df):,}')
            with c3: kpi_card("Vencido CP",    fmt_brl(vencido["valor"].sum() if not vencido.empty else 0), variant="danger")

            st.markdown("<br>", unsafe_allow_html=True)
            if "vencimento" in df.columns:
                df["mes"] = pd.to_datetime(df["vencimento"]).dt.to_period("M").dt.to_timestamp()
                fig = px.bar(df.groupby("mes")["valor"].sum().reset_index(),
                             x="mes", y="valor",
                             title="Pagamentos por Vencimento",
                             labels={"mes": "Mês", "valor": "R$"},
                             color_discrete_sequence=["#4844C8"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df.head(200), use_container_width=True)

    except Exception as e:
        gold_not_ready(G.CONTAS_PAGAR, str(e))

# ── Liquidações ──────────────────────────────────────────────
with tab_liq:
    section_title("Liquidações por Período")
    st.info("📅 Disponível na Fase 2 (próxima entrega)")
    try:
        df = query(f"""
            SELECT *
            FROM `{G.LIQUIDACOES_MENSAIS}`
            ORDER BY mes DESC
            LIMIT 24
        """)
        if df.empty:
            gold_not_ready(G.LIQUIDACOES_MENSAIS)
        else:
            df["mes"] = pd.to_datetime(df["mes"])
            c1, c2 = st.columns(2)
            with c1: kpi_card("Total Liquidado", fmt_brl(df["valor_liquidado"].sum() if "valor_liquidado" in df else 0), variant="success")
            with c2: kpi_card("Liquidações",     f'{df["qtd"].sum():,}' if "qtd" in df else "—")

            st.markdown("<br>", unsafe_allow_html=True)
            val_col = "valor_liquidado" if "valor_liquidado" in df else df.select_dtypes("number").columns[0]
            color_col = "tipo_liquidacao" if "tipo_liquidacao" in df else None
            fig = px.bar(df.sort_values("mes"), x="mes", y=val_col, color=color_col,
                         title="Liquidações por Mês",
                         labels={"mes": "Mês", val_col: "R$"},
                         color_discrete_sequence=px.colors.sequential.Purples_r)
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        gold_not_ready(G.LIQUIDACOES_MENSAIS, str(e))

# ── Fluxo de Caixa ───────────────────────────────────────────
with tab_fc:
    section_title("Fluxo de Caixa")
    st.info("📅 Disponível na Fase 2 (próxima entrega)")
    try:
        df = query(f"""
            SELECT *
            FROM `{G.FLUXO_CAIXA}`
            ORDER BY mes DESC
            LIMIT 24
        """)
        if df.empty:
            gold_not_ready(G.FLUXO_CAIXA)
        else:
            df["mes"] = pd.to_datetime(df["mes"])
            df_sorted = df.sort_values("mes")
            entradas_col = next((c for c in df.columns if "entrada" in c), None)
            saidas_col   = next((c for c in df.columns if "saida" in c or "saída" in c), None)
            saldo_col    = next((c for c in df.columns if "saldo" in c), None)

            if saldo_col:
                c1, c2 = st.columns(2)
                with c1: kpi_card("Saldo Acumulado", fmt_brl(df[saldo_col].sum()))
                with c2:
                    ultimo_saldo = float(df_sorted[saldo_col].iloc[-1])
                    kpi_card("Saldo Último Mês", fmt_brl(ultimo_saldo),
                              variant="success" if ultimo_saldo >= 0 else "danger")

            st.markdown("<br>", unsafe_allow_html=True)
            y_cols = [c for c in [entradas_col, saidas_col, saldo_col] if c]
            if y_cols:
                fig = px.bar(df_sorted, x="mes", y=y_cols,
                             barmode="group",
                             title="Fluxo de Caixa — Entradas vs Saídas",
                             labels={"mes": "Mês", "value": "R$", "variable": ""},
                             color_discrete_sequence=["#10B981", "#EF4444", "#1E1882"])
                fig.update_layout(plot_bgcolor="white", paper_bgcolor="white")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.dataframe(df_sorted, use_container_width=True)

    except Exception as e:
        gold_not_ready(G.FLUXO_CAIXA, str(e))

st.markdown("---")
st.caption("Fonte exclusiva: gold_financeiro · sapient-metrics-492914-m7 · us-east1")
