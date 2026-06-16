"""
Saúde dos Dados — Cascata de validação Nevoni → ERP → BQ → Dash
Fonte: gold_comercial.gold_qa_validacao
"""
import sys
from pathlib import Path
_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Saúde dos Dados | Nevoni 360°", page_icon="", layout="wide")

from dashboard.utils.components import inject_css, page_header, sidebar_brand
from dashboard.utils.bq_client import query, fmt_brl

inject_css()
sidebar_brand()

page_header(
    title="Saúde dos Dados",
    subtitle="Cascata de validação: Nevoni → ERP → BQ → Dashboard",
    sources=[{"name": "gold_qa_validacao", "active": True},
             {"name": "ops.ingestion_runs", "active": True}],
)

# ── Frescor das cargas (ingestão das fontes) ─────────────────
st.subheader("Frescor das cargas — ingestão das fontes")
try:
    df_fresh = query("""
        SELECT source, entity, status, rows_loaded, finished_at,
               TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), finished_at, HOUR) AS horas
        FROM (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY source, entity ORDER BY started_at DESC) rn
          FROM `sapient-metrics-492914-m7.ops.ingestion_runs`
        )
        WHERE rn = 1
        ORDER BY source, entity
    """)
except Exception as e:
    df_fresh = pd.DataFrame()
    st.info(f"`ops.ingestion_runs` indisponível. ({e})")

if not df_fresh.empty:
    df_fresh["rows_loaded"] = pd.to_numeric(df_fresh["rows_loaded"], errors="coerce").fillna(0).astype(int)
    df_fresh["horas"] = pd.to_numeric(df_fresh["horas"], errors="coerce").fillna(9999).astype(int)

    rollup = []
    for src, g in df_fresh.groupby("source"):
        if (g["status"] == "error").any():
            icon = "❌"
        elif (g["status"] == "ok").any():
            icon = "✅"
        else:
            icon = "⊘"
        rollup.append((src, icon, int(g["rows_loaded"].sum()), int(g["horas"].min())))
    rollup.sort()

    cols = st.columns(len(rollup))
    for c, (src, icon, linhas, horas) in zip(cols, rollup):
        quando = "hoje" if horas <= 24 else (f"há {horas // 24}d" if horas < 9999 else "—")
        c.metric(f"{icon} {src}", f"{linhas:,}".replace(",", ".") + " linhas", quando,
                 delta_color="off")

    paradas = df_fresh[(df_fresh["status"] == "skipped") | (df_fresh["horas"] > 72)]
    if not paradas.empty:
        nomes = ", ".join(f"{r['source']}.{r['entity']}" for _, r in paradas.iterrows())
        st.warning(f"Sem dados recentes (vazio ou parado): {nomes}", icon="⚠️")

    with st.expander("Detalhe por entidade"):
        d = df_fresh.copy()
        d["status"] = d["status"].map(
            {"ok": "✅ ok", "error": "❌ erro", "skipped": "⊘ vazio"}).fillna(d["status"])
        d["última carga"] = pd.to_datetime(d["finished_at"]).dt.strftime("%d/%m %H:%M")
        d = d.rename(columns={"source": "fonte", "entity": "entidade",
                              "rows_loaded": "linhas", "horas": "horas atrás"})
        st.dataframe(d[["fonte", "entidade", "status", "linhas", "última carga", "horas atrás"]],
                     use_container_width=True, hide_index=True)

st.divider()

# ── Carrega dados ────────────────────────────────────────────
@st.cache_data(ttl=300)
def carrega_qa():
    sql = """
    SELECT *
    FROM `sapient-metrics-492914-m7.gold_comercial.gold_qa_validacao`
    ORDER BY data_referencia DESC, escopo, metrica
    """
    return query(sql)

df = carrega_qa()

if df.empty:
    st.warning("Tabela `gold_qa_validacao` vazia. Rode `populate_qa_validacao.py` primeiro.")
    st.stop()

# ── Filtros ──────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    periodos = sorted(df['data_referencia'].unique(), reverse=True)
    periodo_sel = st.selectbox("Período de referência", periodos, format_func=lambda d: pd.to_datetime(d).strftime('%b/%Y'))
with c2:
    escopos = ['(todos)'] + sorted(df['escopo'].unique().tolist())
    escopo_sel = st.selectbox("Escopo", escopos)
with c3:
    metricas = ['(todas)'] + sorted(df['metrica'].unique().tolist())
    metrica_sel = st.selectbox("Métrica", metricas)

df_f = df[df['data_referencia'] == periodo_sel].copy()
if escopo_sel != '(todos)':
    df_f = df_f[df_f['escopo'] == escopo_sel]
if metrica_sel != '(todas)':
    df_f = df_f[df_f['metrica'] == metrica_sel]

st.divider()

# ── KPIs de status agregado ──────────────────────────────────
total = len(df_f)
verde = (df_f['status'] == 'VERDE').sum()
amarelo = (df_f['status'] == 'AMARELO').sum()
vermelho = (df_f['status'] == 'VERMELHO').sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Verde (<1%)", f"{verde}/{total}", help="Métricas com Δ total < 1% vs Nevoni")
c2.metric("Amarelo (1-3%)", f"{amarelo}/{total}")
c3.metric("Vermelho (>3%)", f"{vermelho}/{total}")
saude_pct = verde / total * 100 if total else 0
c4.metric("Saúde global", f"{saude_pct:.0f}%", help="% de métricas verdes")

st.divider()

# ── Cascata por escopo (faturamento) ─────────────────────────
st.subheader("Cascata Nevoni → ERP → BQ — Faturamento")
fat = df_f[df_f['metrica'] == 'faturamento'].copy()

for _, r in fat.iterrows():
    v_nev = float(r['valor_nevoni'])
    v_erp = float(r['valor_erp'])
    v_bq  = float(r['valor_bq'])
    d_en  = float(r['delta_erp_nevoni'])
    d_be  = float(r['delta_bq_erp'])
    d_tot = float(r['delta_total_pct'])
    status_icon = {'VERDE': '', 'AMARELO': '', 'VERMELHO': ''}.get(r['status'], '?')

    with st.expander(f"{status_icon} **{r['escopo']}** — Δ total {d_tot:+.2f}% [{r['status']}]", expanded=(r['status'] != 'VERDE')):
        col1, col2, col3 = st.columns(3)
        col1.metric("1⃣ Nevoni (gestor)", fmt_brl(v_nev), help=r.get('fonte_nevoni', ''))
        col2.metric("2⃣ ERP NSR_ERP", fmt_brl(v_erp), f"Δ {fmt_brl(d_en)}", help=r.get('query_erp_ref', ''))
        col3.metric("3⃣ BQ silver", fmt_brl(v_bq), f"Δ {fmt_brl(d_be)}", help=r.get('tabela_bq_ref', ''))

        # Gráfico cascata
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "total"],
            x=["Nevoni", "Δ ERP-Nevoni", "Δ BQ-ERP", "BQ final"],
            y=[v_nev, d_en, d_be, 0],
            text=[fmt_brl(v_nev), fmt_brl(d_en), fmt_brl(d_be), fmt_brl(v_bq)],
            textposition="outside",
            increasing={"marker": {"color": "#16a34a"}},
            decreasing={"marker": {"color": "#dc2626"}},
            totals={"marker": {"color": "#1E1882"}},
        ))
        fig.update_layout(height=300, margin=dict(t=20, b=20, l=20, r=20), showlegend=False,
                          plot_bgcolor='white')
        st.plotly_chart(fig, use_container_width=True)

        if r.get('observacao'):
            st.caption(f"{r['observacao']}")

st.divider()

# ── Tabela detalhada ─────────────────────────────────────────
st.subheader("Detalhamento completo")
cols_show = ['escopo','metrica','valor_nevoni','valor_erp','valor_bq',
             'delta_erp_nevoni','delta_bq_erp','delta_total_pct','status']
df_tab = df_f[cols_show].copy()
df_tab.columns = ['Escopo','Métrica','Nevoni','ERP','BQ','Δ ERP-Nev','Δ BQ-ERP','Δ total %','Status']

def style_status(val):
    return {'VERDE': 'background-color: #dcfce7; color: #166534;',
            'AMARELO': 'background-color: #fef3c7; color: #92400e;',
            'VERMELHO': 'background-color: #fee2e2; color: #991b1b;'}.get(val, '')

st.dataframe(
    df_tab.style.applymap(style_status, subset=['Status'])
                .format({'Nevoni': '{:,.2f}', 'ERP': '{:,.2f}', 'BQ': '{:,.2f}',
                         'Δ ERP-Nev': '{:+,.2f}', 'Δ BQ-ERP': '{:+,.2f}',
                         'Δ total %': '{:+.2f}%'}),
    use_container_width=True,
    hide_index=True,
)

# ── Metadados ────────────────────────────────────────────────
st.divider()
ultima = df['validado_em'].max()
c1, c2 = st.columns(2)
c1.caption(f"Última validação: {pd.to_datetime(ultima).strftime('%d/%m/%Y %H:%M')} UTC")
c2.caption(f"Fonte: `gold_comercial.gold_qa_validacao`")

with st.expander("ℹ Como funciona a cascata", expanded=False):
    st.markdown("""
**4 camadas de validação:**

1. **Nevoni** — número declarado pelo gestor (planilha do Alves, manual)
2. **ERP NSR_ERP** — consulta direta no SQL Server com filtro canônico validado pelo Fred
3. **BQ silver/gold** — número produzido pelo pipeline ETL
4. **Dashboard** — o que o usuário vê (sempre = BQ)

**Tolerâncias:**
- **VERDE**: Δ total < 1% (diferença trivial, dentro de arredondamento)
- **AMARELO**: 1% ≤ Δ < 3% (verificar regra)
- **VERMELHO**: Δ ≥ 3% (problema de método ou dados desatualizados)

**Onde quebra?**
- Se Δ ERP-Nevoni for grande → planilha Nevoni usa critério diferente do canônico
- Se Δ BQ-ERP for grande → silver/gold com filtro desatualizado, precisa rebuild
- Se ambos forem 0 → tudo alinhado, dashboard é confiável
    """)
