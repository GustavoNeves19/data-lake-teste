"""Identidade visual Nevoni — cores, CSS injetável."""

# ── Paleta Nevoni ─────────────────────────────────────────────
PRIMARY      = "#1E1882"   # roxo principal
PRIMARY_DARK = "#0D0B50"   # roxo escuro (gradiente)
PRIMARY_LIGHT = "#4844C8"  # roxo médio
PRIMARY_PALE  = "#EEF0FF"  # roxo muito claro (bg cards)
GRAY          = "#6B7280"
GRAY_LIGHT    = "#F3F4F6"
SUCCESS       = "#10B981"
WARNING       = "#F59E0B"
DANGER        = "#EF4444"
TEXT_DARK     = "#111827"
BG            = "#F8F9FE"

# ── CSS global ────────────────────────────────────────────────
CSS = """
<style>
/* Layout */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1440px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D0B50 0%, #1E1882 60%, #2C28A8 100%);
}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
    color: rgba(255,255,255,0.85) !important;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.15) !important;
}
[data-testid="stSidebarNav"] a span {
    color: rgba(255,255,255,0.75) !important;
}
[data-testid="stSidebarNav"] a[aria-selected="true"] span {
    color: white !important;
    font-weight: 700;
}
[data-testid="stSidebarNav"] a[aria-selected="true"] {
    background: rgba(255,255,255,0.12) !important;
    border-radius: 8px;
}

/* Page header band */
.page-header {
    background: linear-gradient(135deg, #0D0B50 0%, #1E1882 100%);
    color: white;
    padding: 22px 28px;
    border-radius: 14px;
    margin-bottom: 20px;
}
.page-header h1 {
    color: white !important;
    margin: 0 0 4px 0;
    font-size: 22px;
    font-weight: 700;
}
.page-header p {
    color: rgba(255,255,255,0.65);
    margin: 0;
    font-size: 13px;
}

/* KPI metric card */
.kpi-card {
    background: white;
    border-radius: 12px;
    padding: 18px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border-left: 4px solid #1E1882;
    height: 100%;
    min-height: 100px;
}
.kpi-card.warning { border-left-color: #F59E0B; }
.kpi-card.danger  { border-left-color: #EF4444; }
.kpi-card.success { border-left-color: #10B981; }
.kpi-label {
    color: #6B7280;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 0 0 6px 0;
}
.kpi-value {
    color: #111827;
    font-size: 26px;
    font-weight: 700;
    margin: 0;
    line-height: 1.1;
}
.kpi-delta {
    font-size: 12px;
    margin-top: 5px;
    display: flex;
    align-items: center;
    gap: 3px;
}
.delta-up   { color: #10B981; }
.delta-down { color: #EF4444; }
.delta-flat { color: #6B7280; }

/* Sector card (home 360) */
.sector-card {
    background: white;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    cursor: pointer;
    min-height: 150px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: box-shadow 0.2s, transform 0.2s;
    border: 1px solid #F0F0F8;
}
.sector-card:hover {
    box-shadow: 0 8px 24px rgba(30,24,130,0.12);
    transform: translateY(-2px);
}
.sector-icon  { font-size: 30px; line-height: 1; }
.sector-name  { font-size: 15px; font-weight: 700; color: #111827; margin: 0; }
.sector-sub   { font-size: 12px; color: #6B7280; margin: 0; }

/* Status badges */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
}
.badge-ready   { background: #D1FAE5; color: #065F46; }
.badge-partial { background: #FEF3C7; color: #92400E; }
.badge-planned { background: #F3F4F6; color: #6B7280; }
.badge-raw     { background: #DBEAFE; color: #1E40AF; }

/* Source pill (header) */
.sources-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
}
.src-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255,255,255,0.13);
    color: rgba(255,255,255,0.9);
    padding: 3px 11px;
    border-radius: 20px;
    font-size: 12px;
}
.src-pill.pending {
    opacity: 0.5;
}

/* Coming soon section */
.coming-soon-box {
    background: white;
    border-radius: 14px;
    padding: 48px 24px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    border: 2px dashed #E5E7EB;
}
.coming-soon-box h3 { color: #6B7280; margin-bottom: 8px; }
.coming-soon-box p  { color: #9CA3AF; font-size: 14px; }

/* Data table */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Tabs */
.stTabs [data-baseweb="tab"] {
    font-weight: 600;
    color: #6B7280;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #1E1882;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #1E1882 !important;
}

/* Divider */
.section-title {
    font-size: 16px;
    font-weight: 700;
    color: #111827;
    margin: 24px 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #EEF0FF;
}

/* Hide default Streamlit chrome */
#MainMenu  { visibility: hidden; }
footer     { visibility: hidden; }
.stDeployButton { display: none; }
</style>
"""
