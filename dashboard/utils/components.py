"""Componentes reutilizáveis do dashboard Nevoni."""

import streamlit as st
from dashboard.utils.theme import CSS


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "", sources: list[dict] | None = None):
    """Banda de cabeçalho roxa com título e fontes de dados ativas."""
    sources_html = ""
    if sources:
        pills = "".join(
            f'<span class="src-pill {"pending" if not s.get("active", True) else ""}">'
            f'{"●" if s.get("active", True) else "○"} {s["name"]}'
            f'</span>'
            for s in sources
        )
        sources_html = f'<div class="sources-row">{pills}</div>'

    st.markdown(
        f"""
        <div class="page-header">
          <h1>{title}</h1>
          <p>{subtitle}</p>
          {sources_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(
    label: str,
    value: str,
    delta: str = "",
    delta_dir: str = "flat",   # "up" | "down" | "flat"
    variant: str = "",         # "" | "warning" | "danger" | "success"
):
    """Card de KPI com borda colorida lateral."""
    delta_class = f"delta-{delta_dir}"
    arrow = {"up": "▲", "down": "▼", "flat": "—"}.get(delta_dir, "")
    delta_html = (
        f'<div class="kpi-delta {delta_class}">{arrow} {delta}</div>' if delta else ""
    )
    st.markdown(
        f"""
        <div class="kpi-card {variant}">
          <p class="kpi-label">{label}</p>
          <p class="kpi-value">{value}</p>
          {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(cards: list[dict]):
    """Linha de KPIs num grid RESPONSIVO (reflui sozinho em telas estreitas).

    cards: lista de dicts {label, value, delta?, delta_dir?, variant?}.
    Substitui o padrão `st.columns(N) + kpi_card`, que não quebra em mobile.
    """
    arrows = {"up": "▲", "down": "▼", "flat": ""}
    items = []
    for c in cards:
        dd = c.get("delta_dir", "flat")
        delta = c.get("delta", "")
        delta_html = (
            f'<div class="kpi-delta delta-{dd}">{arrows.get(dd, "")} {delta}</div>'
            if delta else ""
        )
        items.append(
            f'<div class="kpi-card {c.get("variant", "")}">'
            f'<p class="kpi-label">{c["label"]}</p>'
            f'<p class="kpi-value">{c["value"]}</p>'
            f'{delta_html}</div>'
        )
    st.markdown(f'<div class="kpi-grid">{"".join(items)}</div>', unsafe_allow_html=True)


def section_title(text: str):
    st.markdown(f'<p class="section-title">{text}</p>', unsafe_allow_html=True)


def sector_card(
    icon: str,
    name: str,
    subtitle: str,
    badge: str,       # "ready" | "partial" | "planned" | "raw"
    badge_label: str,
):
    label_map = {
        "ready":   ("badge-ready",   badge_label),
        "partial": ("badge-partial", badge_label),
        "planned": ("badge-planned", badge_label),
        "raw":     ("badge-raw",     badge_label),
    }
    cls, text = label_map.get(badge, ("badge-planned", badge_label))
    st.markdown(
        f"""
        <div class="sector-card">
          <div class="sector-icon">{icon}</div>
          <div>
            <p class="sector-name">{name}</p>
            <p class="sector-sub">{subtitle}</p>
          </div>
          <span class="badge {cls}">{text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def coming_soon(title: str = "Em construção", msg: str = ""):
    """Card neutro de setor em construção (cadeado). Sem vermelho, sem jargão
    técnico — é tela de executivo: o que ainda não tem dado aparece travado e limpo."""
    st.markdown(
        f"""
        <div class="coming-soon-box">
          <span class="lock">🔒</span>
          <h3>{title}</h3>
          <p>{msg if msg else "Este setor está em construção. Em breve disponível aqui."}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _logo_html() -> str:
    """Logo oficial da Nevoni em SVG inline (vetorial, nítido em qualquer tela,
    self-contained — sem arquivo nem base64). Círculo no índigo da marca (#1E1882)
    + anel branco + 'n'."""
    return (
        '<svg viewBox="0 0 120 120" width="60" height="60" role="img" aria-label="Nevoni" '
        'style="display:inline-block; margin-bottom:8px;">'
        '<circle cx="60" cy="60" r="58" fill="#1E1882"/>'
        '<circle cx="60" cy="60" r="49.5" fill="none" stroke="#ffffff" stroke-width="2.4" opacity="0.9"/>'
        '<g fill="#ffffff">'
        '<rect x="44" y="58" width="9" height="24" rx="4.5"/>'
        '<rect x="67" y="58" width="9" height="24" rx="4.5"/>'
        '<path d="M44 60 A16 16 0 0 1 76 60 L67 60 A7 7 0 0 0 53 60 Z"/>'
        '</g></svg>'
    )


def sidebar_brand():
    """Logo e informações de contexto na sidebar."""
    # Gate de acesso (no-op se auth não configurado em st.secrets). Como toda página
    # chama sidebar_brand(), isto protege o dashboard inteiro num ponto só.
    from dashboard.utils.auth import require_login, logout_button
    require_login()
    st.sidebar.markdown(
        f"""
        <div style="text-align:center; padding: 16px 0 8px;">
          {_logo_html()}
          <div style="color:white; font-size:16px; font-weight:700;">Nevoni</div>
          <div style="color:rgba(255,255,255,0.5); font-size:11px;">Dashboard 360°</div>
        </div>
        <hr style="margin: 8px 0 16px;"/>
        """,
        unsafe_allow_html=True,
    )
    logout_button()
