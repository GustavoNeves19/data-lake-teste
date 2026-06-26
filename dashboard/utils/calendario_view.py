# -*- coding: utf-8 -*-
"""Calendário de Vendas Diárias (emissão de PEDIDO) — reunião 26/06 (Vinícius).

O time pediu o calendário do BI deles dentro do dashboard, "tudo no mesmo lugar".
Régua validada contra o print do Vinicius (dias 1-24 batem ao real):
  VENDAS  = SUM(product_amount) por order_date (emissão de pedido) + natureza<>'N'.
  (≠ faturamento, que é por invoice_date — esse vai na seção de baixo.)
Cada dia é verde quando bate a meta diária (meta mensal ÷ dias úteis) e amarelo
quando não bate. Meta vem do store editável (metas_store) com fallback no default.
"""
from __future__ import annotations

import calendar as _cal
from datetime import date

import streamlit as st

from dashboard.utils.bq_client import query, PROJECT_PROD
from dashboard.utils import gestao_vista as gv, metas_store

PROJ = PROJECT_PROD
ORD  = f"{PROJ}.dm_orders"
NAT  = (f"JOIN `{ORD}.dim_operation_nature` n "
        f"ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'")
MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
DIAS = ["DOMINGO", "SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO"]

_CSS = """
<style>
.cv-wrap{margin-top:8px;font-variant-numeric:tabular-nums;}
.cv-bar{background:#1E1882;color:#fff;text-align:center;font-weight:600;font-size:15px;
  padding:9px;border-radius:12px 12px 0 0;letter-spacing:.01em;}
.cv-tab{width:100%;border-collapse:separate;border-spacing:0;border:1px solid #E6E6F0;border-top:none;}
.cv-tab th{font-size:11px;font-weight:600;letter-spacing:.04em;padding:8px 4px;text-align:center;
  background:#3C3489;color:#fff;border-right:1px solid #4A4196;}
.cv-tab th.we{background:#EEF0F6;color:#6B6B7A;}
.cv-tab th.tot{background:#2C2C3A;color:#fff;}
.cv-tab td{height:62px;vertical-align:top;padding:6px 6px 8px;border-right:1px solid #F0F0F5;
  border-top:1px solid #F0F0F5;text-align:center;width:12%;}
.cv-tab td.empty{background:#FAFAFC;}
.cv-tab td.wtot{background:#F7F7FB;font-weight:700;color:#15151F;font-size:13px;vertical-align:middle;width:16%;}
.cv-day{font-size:12px;color:#8A8A99;margin-bottom:6px;}
.cv-chip{display:inline-block;font-size:12px;font-weight:600;padding:3px 7px;border-radius:6px;line-height:1.2;}
.cv-green{background:#10B981;color:#fff;}
.cv-amber{background:#FDE68A;color:#8A5A00;}
.cv-foot{border:1px solid #E6E6F0;border-top:none;border-radius:0 0 12px 12px;padding:14px 18px;background:#fff;}
.cv-stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px;}
.cv-st .l{font-size:11px;color:#8A8A99;}
.cv-st .v{font-size:18px;font-weight:700;color:#15151F;}
.cv-st .s{font-size:11px;color:#A6A6B2;}
.cv-prog{position:relative;height:26px;border-radius:8px;background:#FEE2E2;overflow:hidden;}
.cv-prog-fill{height:100%;background:#10B981;}
.cv-prog-lbl{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  font-weight:700;color:#15151F;font-size:14px;}
.cv-bar2{background:#1E1882;color:#fff;text-align:center;font-weight:600;font-size:15px;padding:9px;
  border-radius:12px;margin-top:16px;}
.cv-fat{display:grid;grid-template-columns:1fr 1fr;gap:12px;border:1px solid #E6E6F0;border-top:none;
  border-radius:0 0 12px 12px;padding:14px 18px;background:#fff;}
</style>
"""


def _brl(v: float) -> str:
    return f"R$ {float(v or 0):,.0f}".replace(",", ".")


def render_calendario(mes_ref: date, key_prefix: str = "cal") -> None:
    """Renderiza o calendário de vendas diárias + a faixa de faturamento do mês."""
    mes_fim = date(mes_ref.year + (mes_ref.month == 12), (mes_ref.month % 12) + 1, 1)

    # vendas por dia (emissão de pedido) + faturamento do mês (emissão de nota)
    try:
        dfd = query(f"""
            SELECT o.order_date d, SUM(o.product_amount) v
            FROM `{ORD}.fact_sales_order` o {NAT}
            WHERE o.order_date >= '{mes_ref}' AND o.order_date < '{mes_fim}'
              AND o.order_date IS NOT NULL
            GROUP BY 1
        """)
        dff = query(f"""
            SELECT SUM(o.product_amount) v
            FROM `{ORD}.fact_sales_order` o {NAT}
            WHERE o.invoice_date >= '{mes_ref}' AND o.invoice_date < '{mes_fim}'
        """)
    except Exception as e:
        st.warning(f"Não foi possível montar o calendário: {e}")
        return

    diario = {d.day: float(v or 0) for d, v in zip(dfd["d"], dfd["v"])}
    faturado = float(dff["v"].iloc[0] or 0)

    hoje = date.today()
    eh_corrente = (mes_ref.year == hoje.year and mes_ref.month == hoje.month)
    ref = hoje if eh_corrente else date.fromordinal(mes_fim.toordinal() - 1)

    meta      = metas_store.meta_do_mes("GERAL", mes_ref)
    du        = gv.dias_uteis_mes(ref)
    du_corr   = gv.dia_util_corrente(ref)
    meta_dia  = meta / du if du else 0.0
    vendas    = sum(diario.values())
    rem_total = max(meta - vendas, 0.0)
    dias_rest = max(du - du_corr, 0) if eh_corrente else 0
    rem_dia   = rem_total / dias_rest if dias_rest else 0.0
    pct       = (vendas / meta) if meta else 0.0
    proj      = gv.projecao_esperada(meta, ref)

    # ── grade do calendário (semana começando no DOMINGO) ───────────────────
    semanas = _cal.Calendar(firstweekday=6).monthdayscalendar(mes_ref.year, mes_ref.month)
    linhas = ""
    for semana in semanas:
        cels = ""
        wtot = 0.0
        for i, d in enumerate(semana):
            we = " we" if i in (0, 6) else ""
            if d == 0:
                cels += '<td class="empty"></td>'
                continue
            val = diario.get(d, 0.0)
            wtot += val
            if val > 0:
                cls = "cv-green" if val >= meta_dia else "cv-amber"
                chip = f'<div class="cv-chip {cls}">{_brl(val)}</div>'
            else:
                chip = ""
            cels += f'<td class="{we.strip()}"><div class="cv-day">{d}</div>{chip}</td>'
        cels += f'<td class="wtot">{_brl(wtot) if wtot else "R$ 0"}</td>'
        linhas += f"<tr>{cels}</tr>"

    ths = "".join(
        f'<th class="{"we" if i in (0,6) else ""}">{nome}</th>' for i, nome in enumerate(DIAS)
    ) + '<th class="tot">TOTAL</th>'

    titulo = f"Vendas Diárias — {MESES[mes_ref.month]}/{mes_ref.year}"
    rem_txt = (f'<div class="cv-st"><div class="l">Remanescente</div>'
               f'<div class="v">{_brl(rem_dia)}</div><div class="s">por dia · {dias_rest} dias úteis</div></div>'
               if dias_rest else
               '<div class="cv-st"><div class="l">Remanescente</div><div class="v">—</div>'
               '<div class="s">mês encerrado</div></div>')

    html = (
        _CSS +
        f'<div class="cv-wrap"><div class="cv-bar">{titulo}</div>'
        f'<table class="cv-tab"><thead><tr>{ths}</tr></thead><tbody>{linhas}</tbody></table>'
        f'<div class="cv-foot">'
        f'<div class="cv-stats">'
        f'<div class="cv-st"><div class="l">Meta diária</div><div class="v">{_brl(meta_dia)}</div>'
        f'<div class="s">meta mensal ÷ {du} dias úteis</div></div>'
        f'<div class="cv-st"><div class="l">Vendas (pedidos)</div><div class="v">{_brl(vendas)}</div>'
        f'<div class="s">emissão de pedido no mês</div></div>'
        f'<div class="cv-st"><div class="l">Meta mensal</div><div class="v">{_brl(meta)}</div>'
        f'<div class="s">editável na Gestão à Vista</div></div>'
        f'</div>'
        f'<div class="cv-stats">{rem_txt}'
        f'<div class="cv-st"><div class="l">Falta para a meta</div><div class="v">{_brl(rem_total)}</div>'
        f'<div class="s">meta − vendas</div></div>'
        f'<div class="cv-st"><div class="l">Atingido</div><div class="v">{pct*100:.0f}%</div>'
        f'<div class="s">vendas ÷ meta mensal</div></div></div>'
        f'<div class="cv-prog"><div class="cv-prog-fill" style="width:{min(pct,1)*100:.0f}%;"></div>'
        f'<div class="cv-prog-lbl">{pct*100:.0f}%</div></div>'
        f'</div>'
        # ── faixa de faturamento (emissão de nota) ──────────────────────────
        f'<div class="cv-bar2">Faturamento — {MESES[mes_ref.month]}/{mes_ref.year}</div>'
        f'<div class="cv-fat">'
        f'<div class="cv-st"><div class="l">Projeção (esperado até hoje)</div><div class="v">{_brl(proj)}</div>'
        f'<div class="s">meta ÷ dias úteis × dias decorridos</div></div>'
        f'<div class="cv-st"><div class="l">Faturamento (notas)</div><div class="v">{_brl(faturado)}</div>'
        f'<div class="s">emissão de nota no mês</div></div>'
        f'</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)
