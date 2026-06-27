"""
Dashboard 360° Nevoni — Página Principal / Visão Geral
Mostra a maturidade real do Data Lake e KPIs disponíveis hoje.
"""

import sys
from pathlib import Path
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
from datetime import date

from dashboard.utils.branding import FAVICON

st.set_page_config(
    page_title="Nevoni 360° | Dashboard Gerencial",
    page_icon=FAVICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.utils.components import inject_css, page_header, kpi_card, kpi_row, sector_card, section_title, sidebar_brand
from dashboard.utils.bq_client import query, fmt_brl, PROJECT_PROD, data_ultima_carga

inject_css()
sidebar_brand()

PROJ   = PROJECT_PROD
ORDERS = f"{PROJ}.dm_orders"
QUOTES = f"{PROJ}.dm_quotes"
PAY    = f"{PROJ}.dm_payments"
PROD   = f"{PROJ}.dm_production"
INV    = f"{PROJ}.dm_inventory"
IMP    = f"{PROJ}.dm_imports"
PRD    = f"{PROJ}.dm_products"
PART   = f"{PROJ}.dm_partners"

# ── Header ───────────────────────────────────────────────────
page_header(
    title="Nevoni 360° — Visão Gerencial Integrada",
    subtitle=f"Dados de {data_ultima_carga()} BRT · vendas/faturamento · {PROJECT_PROD}",
    sources=[
        {"name": "ERP (SQL Server)", "active": True},
        {"name": "CRM (Pipedrive)",  "active": True},
        {"name": "GoTo Connect",     "active": True},
        {"name": "Umbler",           "active": True},
        {"name": "Gmail",            "active": True},
        {"name": "Miro",             "active": False},
        {"name": "ClickUp",          "active": False},
    ],
)

# ── Mensagem de contexto ─────────────────────────────────────
st.markdown(
    """
    <div style="
        background: linear-gradient(135deg, #EEF0FF 0%, #F5F3FF 100%);
        border-left: 4px solid #1E1882;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 20px;
    ">
        <p style="margin:0; font-size:14px; color:#1E1882; font-weight:700;">
            O Data Lake Nevoni já tem dados reais em todos os setores operacionais
        </p>
        <p style="margin:6px 0 0; font-size:13px; color:#374151;">
            Mesmo com apenas o setor Financeiro em nível Silver, os dados Bronze do ERP cobrem
            Comercial, Produção, Estoque, Fiscal e Engenharia com volume histórico expressivo.
            Os números abaixo são <strong>reais</strong>, extraídos diretamente do BigQuery.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── KPIs executivos reais ─────────────────────────────────────
section_title("Dados disponíveis hoje — Bronze ERP")

with st.spinner("Consultando BigQuery..."):
    erros = []

    # Faturamento 2025
    try:
        df = query(f"""
            SELECT SUM(total_amount) v, COUNT(*) n
            FROM `{ORDERS}.fact_sales_order`
            WHERE invoice_date BETWEEN '2025-01-01' AND '2025-12-31'
        """)
        fat_2025   = float(df["v"].iloc[0] or 0)
        ped_2025   = int(df["n"].iloc[0] or 0)
    except Exception as e:
        fat_2025 = ped_2025 = None; erros.append(str(e))

    # Histórico liquidado
    try:
        df = query(f"SELECT SUM(paid_amount) v, COUNT(*) n FROM `{PAY}.fact_settled_title`")
        liq_total = float(df["v"].iloc[0] or 0)
        liq_n     = int(df["n"].iloc[0] or 0)
    except Exception as e:
        liq_total = liq_n = None; erros.append(str(e))

    # Estoque
    try:
        df = query(f"""
            SELECT COUNT(*) n, SUM(general_balance) geral, SUM(available_balance) disponivel
            FROM `{INV}.snapshot_inventory_balance`
            WHERE general_balance > 0
        """)
        est_itens = int(df["n"].iloc[0] or 0)
        est_geral = float(df["geral"].iloc[0] or 0)
        est_disp  = float(df["disponivel"].iloc[0] or 0)
    except Exception as e:
        est_itens = est_geral = est_disp = None; erros.append(str(e))

    # Parceiros e catálogo
    try:
        df_p = query(f"SELECT COUNT(*) n FROM `{PART}.dim_partner`")
        df_i = query(f"SELECT COUNT(*) n FROM `{PRD}.dim_item`")
        parceiros = int(df_p["n"].iloc[0] or 0)
        skus      = int(df_i["n"].iloc[0] or 0)
    except Exception as e:
        parceiros = skus = None; erros.append(str(e))

kpi_row([
    {"label": "Faturamento 2025",
     "value": fmt_brl(fat_2025) if fat_2025 else "—",
     "delta": f"{ped_2025:,} pedidos" if ped_2025 else "", "variant": "success"},
    {"label": "Histórico Liquidado",
     "value": fmt_brl(liq_total) if liq_total else "—",
     "delta": f"{liq_n:,} títulos" if liq_n else ""},
    {"label": "Itens em Estoque",
     "value": f"{est_itens:,}" if est_itens else "—",
     "delta": f"{est_geral:,.0f} unid. gerais" if est_geral else ""},
    {"label": "Parceiros / Clientes",
     "value": f"{parceiros:,}" if parceiros else "—",
     "delta": "base ativa ERP"},
    {"label": "SKUs no Catálogo",
     "value": f"{skus:,}" if skus else "—",
     "delta": "com estrutura BOM"},
])

st.markdown("<br>", unsafe_allow_html=True)

# ── Faturamento anual ─────────────────────────────────────────
col_fat, col_orc = st.columns(2)

with col_fat:
    section_title("Faturamento por Ano")
    try:
        import plotly.express as px
        df_fat = query(f"""
            SELECT
              EXTRACT(YEAR FROM invoice_date) AS ano,
              COUNT(*)                         AS pedidos,
              SUM(total_amount)                AS faturamento
            FROM `{ORDERS}.fact_sales_order`
            WHERE invoice_date >= '2020-01-01'
              AND invoice_date IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)
        df_fat["ano"] = df_fat["ano"].astype(int).astype(str)
        fig = px.bar(df_fat, x="ano", y="faturamento",
                     text=df_fat["pedidos"].apply(lambda n: f"{int(n):,} ped."),
                     labels={"ano": "Ano", "faturamento": "R$"},
                     color_discrete_sequence=["#1E1882"])
        fig.update_traces(textposition="outside")
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                          showlegend=False, margin=dict(t=20))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Fonte: dm_orders.fact_sales_order · ERP NSR_ERP")
    except Exception as e:
        st.warning(f"Erro ao carregar faturamento: {e}")

with col_orc:
    section_title("Orçamentos vs Pedidos")
    try:
        import plotly.graph_objects as go
        df_ped = query(f"""
            SELECT EXTRACT(YEAR FROM invoice_date) AS ano, COUNT(*) n, SUM(total_amount) v
            FROM `{ORDERS}.fact_sales_order`
            WHERE invoice_date >= '2020-01-01' AND invoice_date IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)
        df_orc = query(f"""
            SELECT EXTRACT(YEAR FROM quote_date) AS ano, COUNT(*) n, SUM(total_amount) v
            FROM `{QUOTES}.fact_quote`
            WHERE quote_date >= '2020-01-01' AND quote_date IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """)
        df_ped["ano"] = df_ped["ano"].astype(int).astype(str)
        df_orc["ano"] = df_orc["ano"].astype(int).astype(str)

        fig2 = go.Figure()
        fig2.add_bar(x=df_orc["ano"], y=df_orc["v"], name="Orçamentos",
                     marker_color="#EEF0FF", marker_line_color="#1E1882", marker_line_width=1.5)
        fig2.add_bar(x=df_ped["ano"], y=df_ped["v"], name="Pedidos Efetivados",
                     marker_color="#1E1882")
        fig2.update_layout(barmode="overlay", plot_bgcolor="white", paper_bgcolor="white",
                           legend=dict(orientation="h", y=1.1), margin=dict(t=20),
                           yaxis_title="R$", xaxis_title="Ano")
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("Fonte: dm_orders · dm_quotes · O volume de orçamentos indica demanda potencial não convertida")
    except Exception as e:
        st.warning(f"Erro ao carregar orçamentos: {e}")

st.markdown("<br>", unsafe_allow_html=True)

# ── Maturidade por setor ──────────────────────────────────────
section_title("Maturidade do Data Lake por Setor")
st.caption("Volume real de dados disponíveis hoje no BigQuery (Bronze). Gold eleva a qualidade analítica de cada setor.")

with st.spinner("Carregando maturidade..."):
    setores = []

    # Comercial
    try:
        df = query(f"""
            SELECT
              COUNT(*)          AS pedidos,
              SUM(total_amount) AS faturamento,
              MIN(invoice_date) AS desde
            FROM `{ORDERS}.fact_sales_order`
            WHERE invoice_date IS NOT NULL
        """)
        df2 = query(f"SELECT COUNT(*) n FROM `{ORDERS}.fact_order_item`")
        setores.append({
            "icon": "", "nome": "Comercial e Compras",
            "resumo": f"{int(df['pedidos'].iloc[0]):,} pedidos de venda · {int(df2['n'].iloc[0]):,} itens",
            "volume": fmt_brl(float(df["faturamento"].iloc[0] or 0)),
            "periodo": f"desde {str(df['desde'].iloc[0])[:7]}",
            "camada": "Bronze pronto",
            "cor": "#DBEAFE",
        })
    except: pass

    # Compras
    try:
        df = query(f"""
            SELECT COUNT(*) pedidos, SUM(total_amount) compras
            FROM `{ORDERS}.fact_purchase_order`
            WHERE invoice_date IS NOT NULL
        """)
        setores.append({
            "icon": "", "nome": "Compras e Suprimentos",
            "resumo": f"{int(df['pedidos'].iloc[0]):,} pedidos de compra",
            "volume": fmt_brl(float(df["compras"].iloc[0] or 0)),
            "periodo": "histórico completo ERP",
            "camada": "Bronze pronto",
            "cor": "#DBEAFE",
        })
    except: pass

    # Operacional
    try:
        df_mov = query(f"SELECT COUNT(*) n FROM `{INV}.fact_inventory_movement`")
        df_est = query(f"SELECT COUNT(*) n, SUM(general_balance) g FROM `{INV}.snapshot_inventory_balance` WHERE general_balance>0")
        df_op  = query(f"SELECT COUNT(*) n FROM `{PROD}.fact_production_order`")
        setores.append({
            "icon": "", "nome": "Operacional e Produção",
            "resumo": f"{int(df_op['n'].iloc[0]):,} OPs · {int(df_mov['n'].iloc[0]):,} mov. estoque",
            "volume": f"{float(df_est['g'].iloc[0] or 0):,.0f} unid. em estoque",
            "periodo": f"{int(df_est['n'].iloc[0]):,} SKUs com saldo",
            "camada": "Bronze pronto",
            "cor": "#DBEAFE",
        })
    except: pass

    # Fiscal / Financeiro
    try:
        df_cr = query(f"SELECT COUNT(*) n, SUM(net_amount) v FROM `{PAY}.fact_receivable`")
        df_cp = query(f"SELECT COUNT(*) n, SUM(net_amount) v FROM `{PAY}.fact_payable`")
        df_lq = query(f"SELECT COUNT(*) n, SUM(paid_amount) v FROM `{PAY}.fact_settled_title`")
        setores.append({
            "icon": "", "nome": "Financeiro",
            "resumo": f"{int(df_lq['n'].iloc[0]):,} títulos liquidados · {int(df_cr['n'].iloc[0]):,} CR · {int(df_cp['n'].iloc[0]):,} CP",
            "volume": fmt_brl(float(df_lq["v"].iloc[0] or 0)) + " liquidado",
            "periodo": "Silver parcial — 5 questões abertas c/ Diego",
            "camada": "Silver parcial ",
            "cor": "#D1FAE5",
        })
    except: pass

    # Importações / Fiscal
    try:
        df = query(f"""
            SELECT COUNT(*) n, SUM(total_brl) brl,
                   SUM(ii_amount+ipi_amount+pis_amount+cofins_amount+icms_amount) tributos
            FROM `{IMP}.fact_import_order`
        """)
        setores.append({
            "icon": "", "nome": "Fiscal e Importações",
            "resumo": f"{int(df['n'].iloc[0]):,} importações · tributos mapeados",
            "volume": fmt_brl(float(df["tributos"].iloc[0] or 0)) + " em tributos",
            "periodo": "II · IPI · PIS · COFINS · ICMS",
            "camada": "Bronze pronto",
            "cor": "#DBEAFE",
        })
    except: pass

    # Engenharia
    try:
        df_sku = query(f"SELECT COUNT(*) n FROM `{PRD}.dim_item`")
        df_bom = query(f"SELECT COUNT(*) n FROM `{PRD}.bridge_item_bom`")
        df_ser = query(f"SELECT COUNT(*) n FROM `{PRD}.fact_serial_number`")
        setores.append({
            "icon": "", "nome": "Engenharia e P&D",
            "resumo": f"{int(df_sku['n'].iloc[0]):,} SKUs · {int(df_bom['n'].iloc[0]):,} relações BOM · {int(df_ser['n'].iloc[0]):,} seriais",
            "volume": "Catálogo completo",
            "periodo": "Estrutura BOM multi-nível disponível",
            "camada": "Bronze pronto",
            "cor": "#DBEAFE",
        })
    except: pass

# Renderiza cards de maturidade
for i in range(0, len(setores), 3):
    cols = st.columns(3)
    for j, col in enumerate(cols):
        if i + j < len(setores):
            s = setores[i + j]
            with col:
                st.markdown(
                    f"""
                    <div style="
                        background: white;
                        border-radius: 14px;
                        padding: 18px 20px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
                        border-top: 4px solid {'#10B981' if 'Silver' in s['camada'] else '#1E1882'};
                        min-height: 150px;
                        margin-bottom: 12px;
                    ">
                        <div style="font-size:15px; font-weight:700; color:#111827;">{s['nome']}</div>
                        <div style="font-size:12px; color:#6B7280; margin: 4px 0;">{s['resumo']}</div>
                        <div style="font-size:16px; font-weight:700; color:#1E1882; margin: 6px 0;">{s['volume']}</div>
                        <div style="font-size:11px; color:#9CA3AF;">{s['periodo']}</div>
                        <span style="
                            display:inline-block; margin-top:8px;
                            background:{'#D1FAE5' if 'Silver' in s['camada'] else '#EEF0FF'};
                            color:{'#065F46' if 'Silver' in s['camada'] else '#1E1882'};
                            padding:2px 10px; border-radius:20px; font-size:11px; font-weight:600;
                        ">{s['camada']}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

st.markdown("<br>", unsafe_allow_html=True)

# ── SAC pill separado (CRM) ───────────────────────────────────
st.markdown(
    """
    <div style="
        background: white; border-radius:14px; padding:18px 20px;
        box-shadow:0 2px 8px rgba(0,0,0,0.06);
        border-top:4px solid #1E1882;
        display:flex; gap:24px; align-items:center; flex-wrap:wrap;
        margin-bottom:20px;
    ">
        <div>
            <div style="font-size:15px;font-weight:700;color:#111827;">SAC e Assistência Técnica</div>
            <div style="font-size:12px;color:#6B7280;">Pipedrive CRM (6 pipelines SAC mapeados) · GoTo Connect · Umbler Talk</div>
        </div>
        <div style="margin-left:auto; text-align:right;">
            <div style="font-size:12px;color:#6B7280;">Fonte</div>
            <div style="font-size:13px;font-weight:600;color:#1E1882;">crm_raw · dm_calls · umbler_raw</div>
        </div>
        <span style="background:#EEF0FF;color:#1E1882;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600;">Bronze pronto</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Arquitetura ───────────────────────────────────────────────
section_title("Arquitetura — onde cada setor está hoje")
st.markdown("""
| Setor | Camada atual | O que falta para Gold |
|---|---|---|
| **Financeiro** | Silver parcial (8 tabelas) | Fechar 5 questões conceituais c/ Diego |
| **Comercial e Compras** | Bronze completo | Criar `gold_comercial` (agregações + CRM) |
| **Operacional e Produção** | Bronze completo | Criar `gold_operacional` (eficiência, giro) |
| **Fiscal e Importações** | Bronze completo | Criar `gold_fiscal` (carga tributária) |
| **SAC e AT** | Bronze (CRM + GoTo) | Criar `gold_sac` (SLA, TMR, CSAT) |
| **Engenharia e P&D** | Bronze completo (BOM, seriais) | Criar `gold_engenharia` + integrar Miro/ClickUp |
| **Jurídico** | Sem fonte ainda | Definir fonte (Drive, ClickUp, planilha) |
""")

st.markdown("---")
st.caption(f"Nevoni Data Lake · Dashboard 360° · {PROJECT_PROD} · {date.today()}")
