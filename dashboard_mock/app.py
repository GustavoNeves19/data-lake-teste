"""Nevoni 360 — Visão executiva do Data Lake.
Cobertura dos 7 setores: Comercial · Financeiro · Compras · Produção · SAC · Operacional · Marketing.
Dados mockados (números do comercial são reais — validados 28/05/2026).
Rodar: streamlit run dashboard_mock/app.py
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nevoni 360 · Data Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta premium
NAVY        = "#0F1B2D"
NAVY_LIGHT  = "#1E2D47"
CHAMPAGNE   = "#C8A35C"
CHAMPAGNE_L = "#E8D5A8"
TEAL        = "#5BA9A0"
SLATE       = "#64748B"
SLATE_LIGHT = "#94A3B8"
CANVAS      = "#FAFBFC"
BORDER      = "#E5E7EB"
SUCCESS     = "#10B981"
WARNING     = "#F59E0B"
DANGER      = "#EF4444"

# Setores · cores
SETORES = {
    "Comercial":   {"icon": "◐", "cor": "#1E3A5F", "maturidade": "Gold"},
    "Financeiro":  {"icon": "$",  "cor": "#0F766E", "maturidade": "Gold"},
    "Compras":     {"icon": "⊞", "cor": "#7C3AED", "maturidade": "Silver"},
    "Produção":    {"icon": "⚙", "cor": "#DC2626", "maturidade": "Silver"},
    "SAC":         {"icon": "◊", "cor": "#C8A35C", "maturidade": "Bronze"},
    "Operacional": {"icon": "▣", "cor": "#0891B2", "maturidade": "Silver"},
    "Marketing":   {"icon": "✦", "cor": "#BE185D", "maturidade": "Bronze"},
}


# ─────────────────────────────────────────────────────────────────────────────
# CSS — design system
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=DM+Serif+Display&display=swap');

    html, body, [class*="css"], .stMarkdown {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        -webkit-font-smoothing: antialiased;
        color: {NAVY};
    }}
    .stApp {{ background: {CANVAS}; }}
    .main > div {{ padding-top: 1rem; }}

    /* Brand bar */
    .brand-bar {{
        display: flex; align-items: center; justify-content: space-between;
        padding: 0.5rem 0 1.5rem 0;
        border-bottom: 1px solid {BORDER};
        margin-bottom: 2rem;
    }}
    .brand-mark {{ display: flex; align-items: center; gap: 0.85rem; }}
    .brand-diamond {{
        width: 40px; height: 40px;
        background: linear-gradient(135deg, {NAVY} 0%, {NAVY_LIGHT} 100%);
        border-radius: 10px; display: flex; align-items: center; justify-content: center;
        color: {CHAMPAGNE}; font-size: 1.2rem; font-weight: 700;
        box-shadow: 0 4px 12px rgba(15,27,45,0.18);
    }}
    .brand-text {{
        font-family: 'DM Serif Display', serif;
        font-size: 1.55rem; color: {NAVY}; font-weight: 400;
        letter-spacing: -0.01em; line-height: 1;
    }}
    .brand-text .three-sixty {{ color: {CHAMPAGNE}; font-weight: 400; }}
    .brand-meta {{
        font-size: 0.72rem; color: {SLATE}; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.1em; margin-top: 0.3rem;
    }}
    .brand-meta-period {{
        display: inline-block; padding: 0.35rem 0.75rem;
        background: {NAVY}; color: white; border-radius: 6px;
        font-size: 0.72rem; letter-spacing: 0.05em; font-weight: 500;
    }}

    /* Page title */
    .page-title {{
        font-family: 'DM Serif Display', serif;
        font-size: 2.1rem; color: {NAVY}; font-weight: 400;
        letter-spacing: -0.02em; margin: 0 0 0.3rem 0; line-height: 1.1;
    }}
    .page-subtitle {{
        color: {SLATE}; font-size: 0.95rem; font-weight: 400;
        margin: 0 0 2rem 0;
    }}

    /* KPI cards */
    .kpi-card {{
        background: white; padding: 1.3rem 1.5rem; border-radius: 14px;
        border: 1px solid {BORDER}; transition: all 0.2s ease; height: 100%;
    }}
    .kpi-card:hover {{ border-color: {CHAMPAGNE}; box-shadow: 0 4px 16px rgba(15,27,45,0.05); }}
    .kpi-card.featured {{
        background: linear-gradient(135deg, {NAVY} 0%, {NAVY_LIGHT} 100%);
        border: none; color: white;
    }}
    .kpi-card.featured .kpi-label,
    .kpi-card.featured .kpi-trend {{ color: {CHAMPAGNE_L}; }}
    .kpi-card.featured .kpi-value {{ color: white; }}
    .kpi-label {{
        color: {SLATE}; font-size: 0.7rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.1em; margin: 0;
    }}
    .kpi-value {{
        color: {NAVY}; font-size: 1.95rem; font-weight: 700;
        margin: 0.55rem 0 0.2rem 0; letter-spacing: -0.02em; line-height: 1;
    }}
    .kpi-value .unit {{
        font-size: 1rem; color: {SLATE}; font-weight: 500; margin-left: 0.2rem;
    }}
    .kpi-card.featured .kpi-value .unit {{ color: {CHAMPAGNE_L}; }}
    .kpi-trend {{
        margin-top: 0.55rem; font-size: 0.78rem; color: {SLATE};
    }}
    .kpi-trend-up   {{ color: {SUCCESS}; font-weight: 600; }}
    .kpi-trend-down {{ color: {DANGER};  font-weight: 600; }}

    /* Section title */
    .section-title {{
        font-size: 0.74rem; color: {SLATE}; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.12em;
        margin: 0 0 1rem 0;
        display: flex; align-items: center; gap: 0.6rem;
    }}
    .section-title::before {{
        content: ""; display: inline-block;
        width: 3px; height: 14px; background: {CHAMPAGNE}; border-radius: 2px;
    }}

    /* Setor card (visão 360) */
    .setor-card {{
        background: white; border: 1px solid {BORDER}; border-radius: 14px;
        padding: 1.4rem; transition: all 0.2s ease; height: 100%;
        position: relative; overflow: hidden;
    }}
    .setor-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(15,27,45,0.08);
        border-color: {CHAMPAGNE};
    }}
    .setor-stripe {{
        position: absolute; top: 0; left: 0; right: 0; height: 3px;
    }}
    .setor-head {{
        display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1rem;
    }}
    .setor-icon {{
        width: 36px; height: 36px; border-radius: 9px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.1rem; color: white; font-weight: 700;
    }}
    .setor-name {{ font-size: 1rem; font-weight: 700; color: {NAVY}; }}
    .setor-status {{ font-size: 0.7rem; color: {SLATE}; margin-top: 0.1rem; }}
    .setor-kpi {{
        margin: 0.5rem 0; padding: 0.5rem 0;
        border-top: 1px solid {BORDER}; font-size: 0.82rem;
    }}
    .setor-kpi-label {{ color: {SLATE}; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em; }}
    .setor-kpi-value {{ color: {NAVY}; font-weight: 700; font-size: 1.1rem; margin-top: 0.15rem; }}

    /* Maturidade pill */
    .pill-gold   {{ background: rgba(200,163,92,0.15); color: #8B6914; }}
    .pill-silver {{ background: rgba(148,163,184,0.18); color: #475569; }}
    .pill-bronze {{ background: rgba(176,135,96,0.18); color: #78350F; }}
    .pill-tag {{
        display: inline-block; padding: 0.2rem 0.6rem; border-radius: 12px;
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.04em;
        text-transform: uppercase;
    }}

    /* Card genérico */
    .card {{
        background: white; border: 1px solid {BORDER}; border-radius: 14px;
        padding: 1.4rem 1.5rem; margin-bottom: 1rem;
    }}
    .card-title {{ color: {NAVY}; font-size: 1rem; font-weight: 600; margin: 0 0 0.3rem 0; }}
    .card-subtitle {{ color: {SLATE}; font-size: 0.82rem; margin: 0 0 1rem 0; }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: white; border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] > div {{ padding-top: 1.5rem; }}
    .sidebar-brand {{
        padding: 0 0 1.5rem 0;
        border-bottom: 1px solid {BORDER};
        margin-bottom: 1.5rem;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.25rem; background: white; padding: 0.4rem;
        border-radius: 12px; border: 1px solid {BORDER};
    }}
    .stTabs [data-baseweb="tab"] {{
        padding: 0.55rem 1.1rem; border-radius: 8px;
        font-weight: 500; color: {SLATE}; font-size: 0.88rem;
    }}
    .stTabs [aria-selected="true"] {{ background: {NAVY} !important; color: white !important; }}

    /* Layer pills */
    .layer-pill {{
        display: flex; align-items: center; gap: 0.7rem;
        padding: 0.55rem 0.85rem;
        background: white; border: 1px solid {BORDER}; border-radius: 10px;
        margin-bottom: 0.45rem; font-size: 0.82rem;
    }}
    .layer-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
    .layer-dot.bronze {{ background: #B08760; }}
    .layer-dot.silver {{ background: #9CA3AF; }}
    .layer-dot.gold   {{ background: {CHAMPAGNE}; }}
    .layer-label {{ font-weight: 600; color: {NAVY}; }}
    .layer-meta  {{ color: {SLATE}; font-size: 0.72rem; margin-left: auto; }}

    /* Hide streamlit defaults */
    #MainMenu, footer, header[data-testid="stHeader"] {{ display: none !important; }}
    hr {{ border-color: {BORDER}; margin: 2rem 0; }}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# DADOS — Comercial validado · resto mockado
# ─────────────────────────────────────────────────────────────────────────────
PERIODO = "abr/2025 — abr/2026"

# Comercial (REAL)
RFV_TOTAL = 10_220_771.63
RFV_CLIENTES = 1_822
RFV_NOTAS = 3_613

# Financeiro (mock)
FAT_TOTAL_NEVONI = 13_471_628
MARGEM_BRUTA = 0.42
EBITDA = 0.18
INADIMPLENCIA = 0.024

# Operacional (mock)
ESTOQUE_TOTAL = 4_850_000
GIRO_ESTOQUE = 5.2
OEE = 0.78

# SAC (mock)
SAC_TICKETS_MES = 287
SAC_NPS = 68
SAC_FCR = 0.74  # First-call resolution

# Compras (mock)
COMPRAS_TOTAL = 7_820_000
LEAD_TIME_MEDIO = 14  # dias
OTD_FORNECEDORES = 0.86

# Marketing (mock)
LEADS_QUALIFICADOS = 412
CAC = 1_280
CONVERSAO = 0.118

# Setores · KPIs primários
df_setores = pd.DataFrame([
    {"setor": "Comercial",   "kpi_label": "Faturamento RFV",    "kpi_value": "R$ 10,22M", "kpi_sub": "1.822 clientes",         "tendencia": "+12% YoY"},
    {"setor": "Financeiro",  "kpi_label": "EBITDA",             "kpi_value": "R$ 2,42M",  "kpi_sub": "Margem 18%",             "tendencia": "+2,1 p.p."},
    {"setor": "Compras",     "kpi_label": "Volume compras",     "kpi_value": "R$ 7,82M",  "kpi_sub": "OTD 86%",                "tendencia": "-3% MoM"},
    {"setor": "Produção",    "kpi_label": "OEE",                "kpi_value": "78%",       "kpi_sub": "Meta 82%",               "tendencia": "+4 p.p."},
    {"setor": "SAC",         "kpi_label": "NPS",                "kpi_value": "68",        "kpi_sub": "287 tickets/mês",        "tendencia": "+6 pts"},
    {"setor": "Operacional", "kpi_label": "Giro de estoque",    "kpi_value": "5,2x",      "kpi_sub": "R$ 4,85M parado",        "tendencia": "+0,3x"},
    {"setor": "Marketing",   "kpi_label": "Leads qualificados", "kpi_value": "412",       "kpi_sub": "CAC R$ 1.280",           "tendencia": "+18% MoM"},
])

# Famílias (REAL)
df_familias = pd.DataFrame([
    {"familia": "Hospitalar", "clientes": 732, "faturamento": 8_215_348.87},
    {"familia": "SAC",        "clientes": 494, "faturamento": 1_187_004.34},
    {"familia": "Farmácias",  "clientes": 596, "faturamento":   818_418.42},
])

# DRE simplificado (mock)
df_dre = pd.DataFrame([
    {"linha": "Receita Bruta",       "valor": 13_471_628,  "pct":   100.0},
    {"linha": "Impostos s/ vendas",  "valor": -1_582_400,  "pct":  -11.7},
    {"linha": "Receita Líquida",     "valor": 11_889_228,  "pct":   88.3},
    {"linha": "CMV",                 "valor": -7_125_300,  "pct":  -52.9},
    {"linha": "Lucro Bruto",         "valor":  4_763_928,  "pct":   35.4},
    {"linha": "Despesas operacionais","valor": -2_345_100, "pct":  -17.4},
    {"linha": "EBITDA",              "valor":  2_418_828,  "pct":   18.0},
])

# Série mensal por setor (mock)
meses = pd.date_range("2025-04-01", "2026-04-01", freq="MS")
rng = np.random.default_rng(7)
df_serie_setor = pd.DataFrame({
    "mes": meses,
    "Comercial":  [580, 620, 700, 690, 750, 680, 710, 730, 690, 720, 740, 700, 685],
    "Financeiro": [110, 118, 132, 128, 142, 130, 135, 140, 132, 138, 142, 136, 132],
    "Compras":    [420, 450, 510, 490, 540, 500, 520, 540, 510, 530, 545, 520, 510],
})


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div class="sidebar-brand">
        <div class="brand-mark">
            <div class="brand-diamond">◆</div>
            <div>
                <div class="brand-text">Nevoni <span class="three-sixty">360°</span></div>
                <div style="font-size: 0.68rem; color: {SLATE}; margin-top: 0.15rem; letter-spacing: 0.04em;">Data Intelligence Platform</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<p class="section-title">Recorte</p>', unsafe_allow_html=True)
    st.selectbox("Período", [PERIODO, "mai/2026", "ano corrente"], label_visibility="collapsed")
    st.selectbox("Empresa", ["Consolidado", "Nevoni Ind.", "Nevoni Com."], label_visibility="collapsed")

    st.markdown(f'<p class="section-title" style="margin-top: 1.5rem;">Setores</p>', unsafe_allow_html=True)
    for nome, info in SETORES.items():
        cls = f"pill-{info['maturidade'].lower()}"
        st.markdown(f"""
        <div class="layer-pill">
            <span style="color: {info['cor']}; font-size: 1rem;">{info['icon']}</span>
            <span class="layer-label">{nome}</span>
            <span class="pill-tag {cls}" style="margin-left: auto;">{info['maturidade']}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f'<p class="section-title" style="margin-top: 1.5rem;">Pipeline</p>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="layer-pill"><div class="layer-dot bronze"></div><span class="layer-label">Bronze</span><span class="layer-meta">36 tabelas</span></div>
    <div class="layer-pill"><div class="layer-dot silver"></div><span class="layer-label">Silver</span><span class="layer-meta">8 tabelas</span></div>
    <div class="layer-pill"><div class="layer-dot gold"></div><span class="layer-label">Gold</span><span class="layer-meta">4 tabelas</span></div>
    """, unsafe_allow_html=True)

    st.markdown(f"<div style='margin-top: 2rem; padding-top: 1rem; border-top: 1px solid {BORDER}; font-size: 0.7rem; color: {SLATE};'>Última carga<br><b style='color: {NAVY};'>28/05/2026 · 14:30 BRT</b></div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# BRAND BAR
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="brand-bar">
    <div class="brand-mark">
        <div class="brand-diamond">◆</div>
        <div>
            <div class="brand-text">Nevoni <span class="three-sixty">360°</span></div>
            <div class="brand-meta">Data Intelligence · Visão Executiva</div>
        </div>
    </div>
    <div style="text-align: right;">
        <div style="font-size: 0.7rem; color: {SLATE}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.4rem;">Período de análise</div>
        <span class="brand-meta-period">{PERIODO}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Title
st.markdown(f"""
<h1 class="page-title">Nevoni 360 — Painel Executivo Integrado</h1>
<p class="page-subtitle">Visão consolidada dos sete setores · dados unificados no Data Lake · atualização diária</p>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# KPIs TOPO (consolidados)
# ─────────────────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns([1.4, 1, 1, 1, 1])

with col1:
    st.markdown(f"""
    <div class="kpi-card featured">
        <p class="kpi-label">Faturamento consolidado</p>
        <p class="kpi-value">R$ 13,47<span class="unit">milhões</span></p>
        <p class="kpi-trend">
            <span style="background: rgba(200,163,92,0.25); color: {CHAMPAGNE_L}; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600;">+14% YoY</span>
            12 meses encerrados em abr/2026
        </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""<div class="kpi-card"><p class="kpi-label">EBITDA</p><p class="kpi-value">18,0<span class="unit">%</span></p><p class="kpi-trend"><span class="kpi-trend-up">+2,1 p.p.</span></p></div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""<div class="kpi-card"><p class="kpi-label">Margem Bruta</p><p class="kpi-value">42,0<span class="unit">%</span></p><p class="kpi-trend"><span class="kpi-trend-up">+0,8 p.p.</span></p></div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""<div class="kpi-card"><p class="kpi-label">Inadimplência</p><p class="kpi-value">2,4<span class="unit">%</span></p><p class="kpi-trend"><span class="kpi-trend-down">+0,3 p.p.</span></p></div>""", unsafe_allow_html=True)
with col5:
    st.markdown(f"""<div class="kpi-card"><p class="kpi-label">Clientes ativos</p><p class="kpi-value">1.822</p><p class="kpi-trend">por nome (consolida filiais)</p></div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_360, tab_comercial, tab_financeiro, tab_operacional, tab_sac, tab_arq = st.tabs([
    "Visão 360", "Comercial", "Financeiro", "Operacional", "SAC", "Arquitetura"
])


def chart_theme(fig, height=None):
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=12, color=NAVY),
        margin=dict(l=0, r=10, t=10, b=0), height=height,
        xaxis=dict(showgrid=False, zeroline=False, color=SLATE),
        yaxis=dict(gridcolor="#F1F5F9", zeroline=False, color=SLATE),
    )
    return fig


# ── TAB VISÃO 360 ────────────────────────────────────────────────────────────
with tab_360:
    st.markdown('<p class="section-title">Painel dos 7 setores</p>', unsafe_allow_html=True)

    # Grid 4x2 de setores
    cols_row1 = st.columns(4)
    cols_row2 = st.columns(4)
    todas_cols = cols_row1 + cols_row2

    for idx, (_, row) in enumerate(df_setores.iterrows()):
        setor = row["setor"]
        info = SETORES[setor]
        cls_pill = f"pill-{info['maturidade'].lower()}"
        tend_class = "kpi-trend-up" if "+" in row["tendencia"] else "kpi-trend-down"

        with todas_cols[idx]:
            st.markdown(f"""
            <div class="setor-card">
                <div class="setor-stripe" style="background: {info['cor']};"></div>
                <div class="setor-head">
                    <div class="setor-icon" style="background: {info['cor']};">{info['icon']}</div>
                    <div>
                        <div class="setor-name">{setor}</div>
                        <div class="setor-status"><span class="pill-tag {cls_pill}">{info['maturidade']}</span></div>
                    </div>
                </div>
                <div class="setor-kpi">
                    <div class="setor-kpi-label">{row['kpi_label']}</div>
                    <div class="setor-kpi-value">{row['kpi_value']}</div>
                    <div style="color: {SLATE}; font-size: 0.78rem; margin-top: 0.15rem;">{row['kpi_sub']}</div>
                </div>
                <div style="font-size: 0.78rem; margin-top: 0.4rem;"><span class="{tend_class}">{row['tendencia']}</span></div>
            </div>
            """, unsafe_allow_html=True)

    # Card "Adicionar" no slot vazio
    with todas_cols[7]:
        st.markdown(f"""
        <div class="setor-card" style="background: {CANVAS}; border: 2px dashed {BORDER}; display: flex; align-items: center; justify-content: center; flex-direction: column; min-height: 100%;">
            <div style="font-size: 1.5rem; color: {SLATE_LIGHT}; margin-bottom: 0.3rem;">+</div>
            <div style="color: {SLATE}; font-size: 0.82rem; text-align: center;">Próximo setor<br>em mapeamento</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tendência cruzada
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown('<p class="section-title">Tendência cruzada · Comercial vs Compras vs Financeiro</p>', unsafe_allow_html=True)
        fig = go.Figure()
        cor_setor = {"Comercial": "#1E3A5F", "Compras": "#7C3AED", "Financeiro": "#0F766E"}
        for s in ["Comercial", "Compras", "Financeiro"]:
            fig.add_trace(go.Scatter(
                x=df_serie_setor["mes"], y=df_serie_setor[s], mode="lines+markers", name=s,
                line=dict(color=cor_setor[s], width=2.5, shape="spline"),
                marker=dict(size=7, line=dict(width=2, color="white")),
                hovertemplate=f"<b>{s}</b><br>%{{x|%b/%Y}}<br>R$ %{{y}}k<extra></extra>",
            ))
        fig = chart_theme(fig, height=340)
        fig.update_yaxes(title="R$ (milhares)", title_font=dict(size=11, color=SLATE))
        fig.update_layout(legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown('<p class="section-title">Maturidade do Data Lake</p>', unsafe_allow_html=True)
        maturidade = pd.DataFrame([
            {"Maturidade": "Gold",   "Setores": 2, "cor": CHAMPAGNE},
            {"Maturidade": "Silver", "Setores": 3, "cor": "#9CA3AF"},
            {"Maturidade": "Bronze", "Setores": 2, "cor": "#B08760"},
        ])
        fig = go.Figure(go.Pie(
            labels=maturidade["Maturidade"], values=maturidade["Setores"], hole=0.65,
            marker=dict(colors=maturidade["cor"], line=dict(color="white", width=2)),
            textfont=dict(color="white", size=13, family="Inter"),
            textinfo="value",
            hovertemplate="<b>%{label}</b><br>%{value} setores<extra></extra>",
        ))
        fig.add_annotation(text=f"<b style='color:{NAVY}; font-size:24px;'>7</b><br><span style='color:{SLATE}; font-size:10px;'>SETORES</span>",
                          x=0.5, y=0.5, showarrow=False, font=dict(family="Inter"))
        fig = chart_theme(fig, height=340)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.05, font=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True)


# ── TAB COMERCIAL ────────────────────────────────────────────────────────────
with tab_comercial:
    st.markdown('<p class="section-title">RFV Geral · abr/25 — abr/26</p>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    for col, label, value, sub in [
        (c1, "Faturamento RFV", "R$ 10,22M", "✓ valida contra ERP"),
        (c2, "Clientes únicos", "1.822", "por nome"),
        (c3, "Notas faturadas", "3.613", "R$ 2.829/nota"),
        (c4, "Ticket médio", "R$ 5,6k", "+12% YoY"),
    ]:
        col.markdown(f"""<div class="kpi-card"><p class="kpi-label">{label}</p><p class="kpi-value">{value}</p><p class="kpi-trend">{sub}</p></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.markdown('<p class="section-title">Faturamento por família</p>', unsafe_allow_html=True)
        df_ord = df_familias.sort_values("faturamento", ascending=True)
        cores_fam = {"Hospitalar": "#1E3A5F", "SAC": "#C8A35C", "Farmácias": "#5BA9A0"}
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=df_ord["familia"], x=df_ord["faturamento"], orientation="h",
            marker=dict(color=[cores_fam[f] for f in df_ord["familia"]], line=dict(width=0)),
            text=[f"<b>R$ {v/1_000_000:.2f}M</b>" for v in df_ord["faturamento"]],
            textposition="outside", textfont=dict(color=NAVY, size=13),
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
        ))
        fig = chart_theme(fig, height=290)
        fig.update_xaxes(showticklabels=False)
        fig.update_yaxes(tickfont=dict(size=13, color=NAVY))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<p class="section-title">Clientes únicos</p>', unsafe_allow_html=True)
        cores = [cores_fam[f] for f in df_familias["familia"]]
        fig = go.Figure(go.Pie(
            labels=df_familias["familia"], values=df_familias["clientes"], hole=0.65,
            marker=dict(colors=cores, line=dict(color="white", width=2)),
            textfont=dict(color="white", size=13, family="Inter"), textinfo="value",
            hovertemplate="<b>%{label}</b><br>%{value} clientes<extra></extra>",
        ))
        fig.add_annotation(text=f"<b style='color:{NAVY}; font-size:24px;'>1.822</b><br><span style='color:{SLATE}; font-size:10px;'>TOTAL</span>",
                          x=0.5, y=0.5, showarrow=False, font=dict(family="Inter"))
        fig = chart_theme(fig, height=290)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.05, font=dict(size=11)))
        st.plotly_chart(fig, use_container_width=True)


# ── TAB FINANCEIRO ───────────────────────────────────────────────────────────
with tab_financeiro:
    st.markdown('<p class="section-title">Demonstrativo simplificado</p>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.4, 1])
    with c1:
        df_dre_show = df_dre.copy()
        df_dre_show["valor_fmt"] = df_dre_show["valor"].apply(lambda v: f"R$ {v:,.0f}".replace(",", "."))
        df_dre_show["pct_fmt"] = df_dre_show["pct"].apply(lambda v: f"{v:+.1f}%")
        st.dataframe(
            df_dre_show[["linha", "valor_fmt", "pct_fmt"]].rename(columns={
                "linha": "Linha", "valor_fmt": "Valor (R$)", "pct_fmt": "% Receita"
            }), use_container_width=True, hide_index=True,
        )

    with c2:
        st.markdown('<p class="section-title">Margens chave</p>', unsafe_allow_html=True)
        for label, value, target, cor in [
            ("Margem Bruta", 42.0, 40.0, "#0F766E"),
            ("EBITDA",       18.0, 16.0, CHAMPAGNE),
            ("Lucro Líquido", 12.4, 12.0, NAVY),
        ]:
            pct = min(value / 50, 1.0)
            st.markdown(f"""
            <div class="card" style="padding: 1rem 1.2rem; margin-bottom: 0.7rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <span style="color: {NAVY}; font-weight: 600; font-size: 0.9rem;">{label}</span>
                    <span style="color: {cor}; font-weight: 700;">{value:.1f}%</span>
                </div>
                <div style="background: #F1F5F9; height: 6px; border-radius: 3px; overflow: hidden;">
                    <div style="width: {pct*100}%; height: 100%; background: {cor};"></div>
                </div>
                <div style="font-size: 0.72rem; color: {SLATE}; margin-top: 0.4rem;">Meta {target:.0f}%</div>
            </div>
            """, unsafe_allow_html=True)


# ── TAB OPERACIONAL ──────────────────────────────────────────────────────────
with tab_operacional:
    c1, c2, c3, c4 = st.columns(4)
    for col, label, value, sub in [
        (c1, "OEE Produção",       "78%",      "Meta 82%"),
        (c2, "Giro estoque",       "5,2x",     "Anual"),
        (c3, "Lead time compras",  "14 dias",  "Média"),
        (c4, "OTD fornecedores",   "86%",      "On-time delivery"),
    ]:
        col.markdown(f"""<div class="kpi-card"><p class="kpi-label">{label}</p><p class="kpi-value">{value}</p><p class="kpi-trend">{sub}</p></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="section-title">Estoque por família · valorizado</p>', unsafe_allow_html=True)
    df_estoque = pd.DataFrame([
        {"familia": "Hospitalar", "valor": 3_200_000},
        {"familia": "Farmácias",  "valor":   980_000},
        {"familia": "SAC/Peças",  "valor":   670_000},
    ])
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_estoque["familia"], y=df_estoque["valor"],
        marker=dict(color=[NAVY, TEAL, CHAMPAGNE], line=dict(width=0)),
        text=[f"<b>R$ {v/1_000_000:.2f}M</b>" for v in df_estoque["valor"]],
        textposition="outside", textfont=dict(color=NAVY, size=13),
    ))
    fig = chart_theme(fig, height=320)
    fig.update_yaxes(showticklabels=False)
    st.plotly_chart(fig, use_container_width=True)


# ── TAB SAC ──────────────────────────────────────────────────────────────────
with tab_sac:
    c1, c2, c3, c4 = st.columns(4)
    for col, label, value, sub in [
        (c1, "NPS",                 "68",   "+6 pts MoM"),
        (c2, "Tickets/mês",         "287",  "Pico 412 (jul)"),
        (c3, "First-call resolution","74%", "Meta 80%"),
        (c4, "Tempo médio resposta","2h 14min", "-22min MoM"),
    ]:
        col.markdown(f"""<div class="kpi-card"><p class="kpi-label">{label}</p><p class="kpi-value">{value}</p><p class="kpi-trend">{sub}</p></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div class="card">
        <p class="card-title">Integração SAC</p>
        <p class="card-subtitle">Fontes de dados unificadas</p>
        <ul style="margin: 0; padding-left: 1.2rem; color: {NAVY}; line-height: 1.8; font-size: 0.9rem;">
            <li><b>GoTo Connect</b> · ligações e ramais — dataset <code>goto_raw</code></li>
            <li><b>Pipedrive CRM</b> · tickets e pipeline — dataset <code>crm_raw</code></li>
            <li><b>Umbler Talk</b> · WhatsApp comercial — bronze em produção</li>
            <li><b>Gmail integration</b> · suporte por email — em mapeamento</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)


# ── TAB ARQUITETURA ──────────────────────────────────────────────────────────
with tab_arq:
    st.markdown('<p class="section-title">Arquitetura Medallion</p>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, cls, label, desc, n, unit, meta, info in [
        (c1, "bronze", "Bronze", "Dados brutos do ERP", "36", "tabelas", "1.245.678 linhas · 02:00 BRT", "Replica fielmente o ERP. Sem filtros de regra de negócio. Preserva histórico completo."),
        (c2, "silver", "Silver", "Regras de negócio",   "8",  "tabelas", "312.445 linhas · 02:30 BRT",   "Filtros, joins, exclusões contextuais. Aplica o contrato Medallion."),
        (c3, "gold",   "Gold",   "Pronto para consumo", "4",  "tabelas", "18.902 linhas · 03:00 BRT",    "Agregações, scores RFV, KPIs executivos prontos para dashboards."),
    ]:
        col.markdown(f"""
        <div class="card" style="height: 100%;">
            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1rem;">
                <div class="layer-dot {cls}" style="width: 14px; height: 14px;"></div>
                <span style="font-size: 1.1rem; font-weight: 700; color: {NAVY};">{label}</span>
            </div>
            <p style="color: {SLATE}; font-size: 0.82rem; margin: 0 0 1rem 0;">{desc}</p>
            <div style="display: flex; align-items: baseline; gap: 0.4rem; margin-bottom: 0.5rem;">
                <span style="font-size: 2rem; font-weight: 700; color: {NAVY};">{n}</span>
                <span style="color: {SLATE}; font-size: 0.85rem;">{unit}</span>
            </div>
            <p style="color: {SLATE}; font-size: 0.78rem; margin: 0 0 1rem 0;">{meta}</p>
            <p style="color: {NAVY}; font-size: 0.82rem; line-height: 1.5; margin: 0;">{info}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<p class="section-title">Fontes integradas</p>', unsafe_allow_html=True)

    fontes = [
        ("ERP NSR",      "SQL Server · 36 tabelas · 56k clientes", NAVY),
        ("Pipedrive CRM",  "API v2 · 10 tabelas · 16.601 deals",   "#7C3AED"),
        ("GoTo Connect",   "OAuth2 · ramais e ligações",            "#0F766E"),
        ("Umbler Talk",    "WhatsApp comercial · bronze ativo",     "#DC2626"),
        ("Gmail",          "API · em mapeamento",                    CHAMPAGNE),
    ]
    cols = st.columns(len(fontes))
    for col, (nome, sub, cor) in zip(cols, fontes):
        col.markdown(f"""
        <div class="card" style="text-align: center; padding: 1.2rem 0.8rem;">
            <div style="width: 42px; height: 42px; background: {cor}; border-radius: 50%;
                        margin: 0 auto 0.7rem; display: flex; align-items: center;
                        justify-content: center; color: white; font-weight: 700;">{nome[0]}</div>
            <div style="color: {NAVY}; font-weight: 700; font-size: 0.92rem;">{nome}</div>
            <div style="color: {SLATE}; font-size: 0.72rem; margin-top: 0.3rem; line-height: 1.4;">{sub}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="margin-top: 1.5rem; padding: 1rem 1.2rem; background: linear-gradient(135deg, rgba(200,163,92,0.08), rgba(200,163,92,0.02));
                border-radius: 10px; border-left: 3px solid {CHAMPAGNE};">
        <p style="margin: 0; color: {NAVY}; font-size: 0.9rem;">
            <b style="color: #8B6914;">Atualização 28/05/2026.</b>
            Refator Medallion concluído em 38 queries do extract. Cobertura
            <code>dim_partner</code> de 27% → 100%. Próxima etapa: Gold por setor.
        </p>
    </div>
    """, unsafe_allow_html=True)


# Footer
st.markdown(f"""
<div style="margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid {BORDER};
            display: flex; justify-content: space-between; font-size: 0.75rem; color: {SLATE};">
    <span><b style="color: {NAVY};">Nevoni 360°</b> · Data Intelligence Platform · v0.1 (preview)</span>
    <span>Comercial validado · demais setores em homologação</span>
</div>
""", unsafe_allow_html=True)
