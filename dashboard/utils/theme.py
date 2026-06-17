"""Identidade visual Nevoni — cores, CSS injetável (refino visual jun/2026)."""

# ── Paleta Nevoni ─────────────────────────────────────────────
PRIMARY      = "#1E1882"   # índigo principal
PRIMARY_DARK = "#15104F"
PRIMARY_LIGHT = "#4844C8"
PRIMARY_PALE  = "#EEF0FF"
GRAY          = "#8A8A99"
GRAY_LIGHT    = "#F3F4F6"
SUCCESS       = "#059669"
WARNING       = "#B45309"
DANGER        = "#DC2626"
TEXT_DARK     = "#15151F"
BG            = "#F7F7FB"
HAIRLINE      = "#ECECF3"

# ── CSS global ────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, button, input, textarea, select {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

/* Layout */
.main .block-container { padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1480px; }
.block-container { font-variant-numeric: tabular-nums; }

/* Sidebar */
[data-testid="stSidebar"] { background: #15104F; }
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span { color: rgba(255,255,255,0.82) !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.12) !important; }
[data-testid="stSidebarNav"] a span { color: rgba(255,255,255,0.66) !important; font-size: 13.5px; }
[data-testid="stSidebarNav"] a[aria-selected="true"] span { color: #fff !important; font-weight: 600; }
[data-testid="stSidebarNav"] a[aria-selected="true"] { background: rgba(255,255,255,0.10) !important; border-radius: 7px; }

/* Page header — banda sólida, plana (sem gradiente de template) */
.page-header {
    background: #1E1882; color: white;
    padding: 20px 26px; border-radius: 12px; margin-bottom: 22px;
}
.page-header h1 { color: white !important; margin: 0 0 3px 0; font-size: 22px; font-weight: 600; letter-spacing: -.01em; }
.page-header p { color: rgba(255,255,255,0.62); margin: 0; font-size: 13px; }

/* KPI card — hairline plano, sem borda-lateral colorida, números tabulares */
.kpi-card {
    background: #fff; border: 1px solid #ECECF3; border-radius: 10px;
    padding: 15px 17px; height: 100%; min-height: 92px;
}
.kpi-card.success { border-top: 2px solid #10B981; }
.kpi-card.warning { border-top: 2px solid #D97706; }
.kpi-card.danger  { border-top: 2px solid #DC2626; }
.kpi-label { color: #8A8A99; font-size: 12px; font-weight: 500; margin: 0 0 9px 0; }
.kpi-value {
    color: #15151F; font-size: 23px; font-weight: 600; margin: 0; line-height: 1.1;
    font-variant-numeric: tabular-nums; letter-spacing: -.022em;
}
.kpi-delta { font-size: 12px; margin-top: 7px; display: flex; align-items: center; gap: 4px; }
.delta-up   { color: #059669; }
.delta-down { color: #DC2626; }
.delta-flat { color: #9A9AA8; }

/* Grid responsivo de KPIs — reflui sozinho (resolve o "não responsivo") */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 11px; }

/* Retrofit de responsividade: qualquer linha st.columns que contenha um KPI card
   passa a REFLUIR (quebra de linha) em vez de espremer. Cobre todos os call-sites
   antigos sem reescrever Python. :has() é suportado no Chrome do Streamlit. */
[data-testid="stHorizontalBlock"]:has(.kpi-card) { flex-wrap: wrap; gap: 11px; row-gap: 11px; }
[data-testid="stHorizontalBlock"]:has(.kpi-card) > [data-testid="stColumn"] {
    flex: 1 1 160px; min-width: 160px;
}

/* Sector card (home 360) */
.sector-card {
    background: #fff; border-radius: 12px; padding: 18px; border: 1px solid #ECECF3;
    cursor: pointer; min-height: 138px; display: flex; flex-direction: column; gap: 9px;
    transition: border-color .15s, transform .15s;
}
.sector-card:hover { border-color: #1E1882; transform: translateY(-1px); }
.sector-icon  { font-size: 22px; line-height: 1; color: #1E1882; }
.sector-name  { font-size: 15px; font-weight: 600; color: #15151F; margin: 0; }
.sector-sub   { font-size: 12px; color: #8A8A99; margin: 0; }

/* Status badges */
.badge { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 500; }
.badge-ready   { background: #E1F5EE; color: #0F6E56; }
.badge-partial { background: #FAEEDA; color: #854F0B; }
.badge-planned { background: #F1EFE8; color: #5F5E5A; }
.badge-raw     { background: #E6F1FB; color: #0C447C; }

/* Source pills (header) */
.sources-row { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }
.src-pill {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(255,255,255,0.12); color: rgba(255,255,255,0.9);
    padding: 3px 11px; border-radius: 6px; font-size: 12px;
}
.src-pill.pending { opacity: 0.45; }

/* Coming soon */
.coming-soon-box {
    background: #fff; border-radius: 12px; padding: 48px 24px; text-align: center;
    border: 1px solid #ECECF3;
}
.coming-soon-box h3 { color: #6B7280; margin-bottom: 8px; font-weight: 600; }
.coming-soon-box p  { color: #9CA3AF; font-size: 14px; }

/* Tabelas */
[data-testid="stDataFrame"] { border: 1px solid #ECECF3; border-radius: 8px; overflow: hidden; }

/* Tabs — limpo, sublinhado índigo */
.stTabs [data-baseweb="tab-list"] { gap: 22px; }
.stTabs [data-baseweb="tab"] { font-weight: 500; color: #9A9AA8; font-size: 14px; }
.stTabs [data-baseweb="tab"][aria-selected="true"] { color: #1E1882; }
.stTabs [data-baseweb="tab-highlight"] { background: #1E1882 !important; }

/* Section title — leve, sem barra grossa */
.section-title {
    font-size: 16px; font-weight: 600; color: #15151F; margin: 26px 0 12px 0; padding: 0;
}

/* ── Painel de Gestão à Vista ─────────────────────────────────── */
.gv-band {
    background: #1E1882; color: #fff; border-radius: 14px;
    padding: 20px 26px; margin-bottom: 18px;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
}
.gv-band .t  { font-size: 21px; font-weight: 600; letter-spacing: -.01em; margin: 0; }
.gv-band .s  { font-size: 13px; color: rgba(255,255,255,.66); margin: 0; }
.gv-foot {
    background: #EEF0FF; color: #1E1882; border-radius: 14px; padding: 14px 22px; margin-top: 18px;
    font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 10px;
}
/* grid mais arejado: trilho 300px + gap 18 (resolve o "apertado") */
.gv-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 18px; }
.gv-card {
    background: #fff; border: 1px solid #ECECF3; border-radius: 14px; padding: 20px 22px;
    box-shadow: 0 1px 2px rgba(30,24,130,.04);
}
.gv-card.gv-wide { grid-column: span 2; }
@media (max-width: 720px) { .gv-card.gv-wide { grid-column: span 1; } }
.gv-chan { display: flex; gap: 10px; margin-top: 12px; }
.gv-chan > div { flex: 1; background: #F7F7FB; border-radius: 8px; padding: 9px; text-align: center; }
.gv-chan .lbl { font-size: 10.5px; color: #8A8A99; }
.gv-chan .val { font-size: 15px; font-weight: 600; color: #15151F; }
.gv-head { display: flex; align-items: center; gap: 9px; margin-bottom: 14px; }
.gv-badge { width: 22px; height: 22px; border-radius: 50%; font-size: 12px; font-weight: 600;
    display: inline-flex; align-items: center; justify-content: center; flex: none; }
/* título = rótulo de seção (degrau claro acima de sub/note) */
.gv-title { font-size: 11px; color: #6B6B7A; font-weight: 700; letter-spacing: .045em; text-transform: uppercase; }
.gv-hero  { font-size: 28px; font-weight: 600; color: #15151F; letter-spacing: -.02em; line-height: 1.1;
    font-variant-numeric: tabular-nums; }
.gv-hero.gv-effort { color: #1E1882; }   /* nº de esforço usa o índigo da marca */
.gv-sub   { font-size: 12.5px; color: #6B6B7A; margin-top: 5px; }
.gv-bar-track { height: 6px; background: #F0F0F5; border-radius: 4px; overflow: hidden; }
.gv-bar-fill  { height: 100%; border-radius: 4px; }
.gv-rk-row { margin-bottom: 9px; }
.gv-rk-top { display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 3px; gap: 10px; }
/* funil da engenharia reversa: separado do hero, ritmo tabular */
.gv-eng-funil { margin-top: 14px; padding-top: 12px; border-top: 1px solid #F0F0F5; }
.gv-eng-row { display: flex; justify-content: space-between; font-size: 12.5px; margin: 6px 0;
    font-variant-numeric: tabular-nums; }
.gv-eng-row .lbl { color: #8A8A99; }
.gv-eng-row .val { color: #15151F; font-weight: 600; }
/* atividades: concluído x atrasado legíveis (atraso = cobrança) */
.gv-ativ-done { color: #15151F; font-weight: 600; font-variant-numeric: tabular-nums; }
.gv-ativ-late { color: #DC2626; font-weight: 600; background: #FEECEC; padding: 1px 7px; border-radius: 6px; font-size: 11px; }
.gv-stage { height: 22px; border-radius: 4px; display: flex; align-items: center;
    justify-content: space-between; padding: 0 10px; color: #fff; font-size: 12px; margin-bottom: 3px; }
.gv-note { font-size: 11px; color: #A6A6B2; margin-top: 10px; padding-top: 8px; border-top: 1px dashed #F0F0F5; }

/* Esconde chrome do Streamlit */
#MainMenu  { visibility: hidden; }
footer     { visibility: hidden; }
.stDeployButton { display: none; }
</style>
"""
