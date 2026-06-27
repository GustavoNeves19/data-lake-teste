"""
Nevoni 360° — Visão Geral / Monitor de Cargas.

Substitui o antigo despejo de números Bronze (sem regra de negócio) por um painel
de OPERAÇÃO do Data Lake: até quando cada fonte está fresca, a cadência programada
de carga e o histórico das execuções (horários que subiram).
Fontes: `.modified` das tabelas-chave (frescor universal, inclusive ERP) +
`ops.ingestion_runs` (log append-only das ingestões de API/CRM).
"""
import sys
from pathlib import Path
_ROOT = str(Path(__file__).resolve().parents[2])   # raiz do projeto
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import datetime as dt

import pandas as pd
import streamlit as st

from dashboard.utils.components import page_header, section_title
from dashboard.utils.bq_client import query, get_client, PROJECT_PROD

P = PROJECT_PROD

# Fonte/camada → (rótulo, tabela, idade "saudável" em minutos)
FONTES = [
    ("ERP · Vendas e pedidos",   f"{P}.dm_orders.fact_sales_order",            240),
    ("CRM · Pipedrive",          f"{P}.crm_raw.activities",                     90),
    ("Silver · RFV",             f"{P}.silver_comercial.silver_com_rfv_score", 360),
    ("Gold · Cliente 360",       f"{P}.gold_comercial.gold_com_cliente_360",   360),
    ("ERP · Clientes",           f"{P}.dm_partners.dim_partner",              1440),
    ("ERP · Produtos / SKUs",    f"{P}.dm_products.dim_item",                 1440),
]


@st.cache_data(ttl=60, show_spinner=False)
def _frescor():
    """last_modified (UTC, ISO) de cada tabela-chave. Metadado barato, sem custo de query."""
    cl = get_client()
    out = []
    for rotulo, tid, thr in FONTES:
        try:
            m = cl.get_table(tid).modified
            out.append((rotulo, m.isoformat(), thr))
        except Exception:
            out.append((rotulo, None, thr))
    return out


def _idade_txt(mins: int) -> str:
    if mins < 60:
        return f"há {mins} min"
    h, m = divmod(mins, 60)
    if h < 24:
        return f"há {h}h{m:02d}"
    d, h = divmod(h, 24)
    return f"há {d}d{h:02d}h"


def _cor(mins: int, thr: int) -> str:
    if mins <= thr:
        return "#10B981"        # verde — dentro do esperado
    if mins <= thr * 2:
        return "#D97706"        # âmbar — atrasando
    return "#DC2626"            # vermelho — parado


_CSS = """
<style>
.mc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:4px 0 8px;}
.mc-card{background:#fff;border:1px solid #ECECF3;border-left-width:4px;border-radius:12px;padding:14px 16px;
  box-shadow:0 1px 2px rgba(30,24,130,.04);}
.mc-top{display:flex;align-items:center;gap:8px;}
.mc-dot{width:9px;height:9px;border-radius:50%;flex:none;}
.mc-lbl{font-size:12px;color:#6B6B7A;font-weight:600;}
.mc-val{font-size:20px;font-weight:700;color:#15151F;margin-top:7px;font-variant-numeric:tabular-nums;}
.mc-age{font-size:12px;margin-top:3px;}
.cad-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:4px;}
.cad-card{background:#F7F7FB;border-radius:10px;padding:12px 14px;}
.cad-card .t{font-size:11px;color:#8A8A99;}
.cad-card .v{font-size:15px;font-weight:700;color:#1E1882;margin-top:4px;}
.cad-card .s{font-size:11px;color:#A6A6B2;margin-top:2px;}
</style>
"""


def _proxima(agora_brt):
    erp_times = [(6, 20), (9, 20), (12, 20), (15, 20), (17, 20)]
    nxt = None
    for h, m in erp_times:
        t = agora_brt.replace(hour=h, minute=m, second=0, microsecond=0)
        if t > agora_brt:
            nxt = t
            break
    if nxt is None:
        nxt = (agora_brt + dt.timedelta(days=1)).replace(hour=6, minute=20, second=0, microsecond=0)
    if agora_brt.minute < 20:
        crm = agora_brt.replace(minute=20, second=0, microsecond=0)
    else:
        crm = (agora_brt + dt.timedelta(hours=1)).replace(minute=20, second=0, microsecond=0)
    return nxt.strftime("%H:%M"), crm.strftime("%H:%M")


# ── Cabeçalho ─────────────────────────────────────────────────────────────────
page_header(
    title="Monitor de Cargas — Data Lake",
    subtitle="Frescor de cada fonte, cadência programada e histórico das execuções",
    sources=[
        {"name": "ERP (SQL Server)", "active": True},
        {"name": "CRM (Pipedrive)",  "active": True},
        {"name": "GoTo Connect",     "active": True},
        {"name": "Umbler",           "active": True},
        {"name": "Gmail",            "active": True},
        {"name": "Miro",             "active": True},
        {"name": "ClickUp",          "active": True},
    ],
)

# ── Frescor por fonte/camada ──────────────────────────────────────────────────
section_title("Frescor das fontes")
st.caption("Quão recente está o dado de cada camada. Verde = dentro do ritmo esperado · "
           "âmbar = atrasando · vermelho = parado.")

now_utc = dt.datetime.now(dt.timezone.utc)
cards = ""
for rotulo, iso, thr in _frescor():
    if iso is None:
        cards += (f'<div class="mc-card" style="border-left-color:#C9C9D4;">'
                  f'<div class="mc-top"><span class="mc-dot" style="background:#C9C9D4;"></span>'
                  f'<span class="mc-lbl">{rotulo}</span></div>'
                  f'<div class="mc-val">—</div><div class="mc-age" style="color:#A6A6B2;">sem leitura</div></div>')
        continue
    m = dt.datetime.fromisoformat(iso)
    mins = int((now_utc - m).total_seconds() // 60)
    cor = _cor(mins, thr)
    brt = (m - dt.timedelta(hours=3)).strftime("%d/%m · %H:%M")
    cards += (f'<div class="mc-card" style="border-left-color:{cor};">'
              f'<div class="mc-top"><span class="mc-dot" style="background:{cor};"></span>'
              f'<span class="mc-lbl">{rotulo}</span></div>'
              f'<div class="mc-val">{brt}</div>'
              f'<div class="mc-age" style="color:{cor};font-weight:600;">{_idade_txt(mins)} BRT</div></div>')
st.markdown(_CSS + f'<div class="mc-grid">{cards}</div>', unsafe_allow_html=True)

# ── Cadência programada ───────────────────────────────────────────────────────
agora_brt = now_utc - dt.timedelta(hours=3)
prox_erp, prox_crm = _proxima(agora_brt)
section_title("Cadência programada")
st.markdown(
    f'<div class="cad-grid">'
    f'<div class="cad-card"><div class="t">Sincronização do ERP</div><div class="v">5× ao dia</div>'
    f'<div class="s">06:20 · 09:20 · 12:20 · 15:20 · 17:20 BRT</div></div>'
    f'<div class="cad-card"><div class="t">CRM (Pipedrive)</div><div class="v">De hora em hora</div>'
    f'<div class="s">nas horas comerciais (:20)</div></div>'
    f'<div class="cad-card"><div class="t">Carga completa</div><div class="v">1× madrugada</div>'
    f'<div class="s">03:20 BRT · todos os domínios</div></div>'
    f'<div class="cad-card"><div class="t">Próxima sincronização ERP</div><div class="v">{prox_erp} BRT</div>'
    f'<div class="s">próximo CRM às {prox_crm}</div></div>'
    f'</div>',
    unsafe_allow_html=True,
)
st.caption("O ERP do Fred sobe 06/09/12/15/17 BRT; a gente dispara 15min depois, pra carga dele terminar. "
           "Entre as sincronizações, só o CRM sobe (a Gestão à Vista lê o CRM direto).")

# ── Histórico de execuções (CRM / APIs) ───────────────────────────────────────
section_title("Histórico de execuções")
st.caption("Log das ingestões de API/CRM (`ops.ingestion_runs`). O ERP entra pelo frescor acima, "
           "pois roda por um pipeline próprio.")
try:
    resumo = query(f"""
        SELECT source AS Fonte,
               FORMAT_DATETIME('%d/%m %H:%M', DATETIME(MAX(finished_at), 'America/Sao_Paulo')) AS `Última carga`,
               TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(finished_at), MINUTE) AS _min,
               COUNTIF(DATE(DATETIME(finished_at, 'America/Sao_Paulo')) = CURRENT_DATE('America/Sao_Paulo')) AS `Cargas hoje`
        FROM `{P}.ops.ingestion_runs`
        GROUP BY source
        ORDER BY MAX(finished_at) DESC
    """)
    if not resumo.empty:
        resumo["Há"] = resumo["_min"].apply(lambda x: _idade_txt(int(x)))
        st.dataframe(resumo[["Fonte", "Última carga", "Há", "Cargas hoje"]],
                     hide_index=True, use_container_width=True)
except Exception as e:
    st.warning(f"Não foi possível ler o resumo de execuções: {e}")

with st.expander("Ver as últimas 20 execuções (detalhe)"):
    try:
        det = query(f"""
            SELECT FORMAT_DATETIME('%d/%m %H:%M:%S', DATETIME(finished_at, 'America/Sao_Paulo')) AS Quando,
                   source AS Fonte, entity AS Entidade, status AS Status,
                   rows_loaded AS Linhas, ROUND(seconds, 1) AS Segundos
            FROM `{P}.ops.ingestion_runs`
            ORDER BY finished_at DESC
            LIMIT 20
        """)
        st.dataframe(det, hide_index=True, use_container_width=True)
    except Exception as e:
        st.warning(f"Não foi possível ler o detalhe: {e}")

st.markdown("---")
st.caption(f"Nevoni Data Lake · Monitor de Cargas · {P}")
