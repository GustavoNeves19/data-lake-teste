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

from dashboard.utils.bq_client import query, data_ultima_carga, PROJECT_PROD
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
.cv-fresh{font-size:11px;color:#A6A6B2;margin-top:11px;padding-top:8px;border-top:1px dashed #F0F0F5;
  text-align:center;}
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
    ultima    = data_ultima_carga()

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
        f'<div class="cv-fresh">Foto da última carga · {ultima} BRT — o ERP da equipe atualiza ao vivo; '
        f'os números se igualam a cada carga.</div>'
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


_CSS_FM = """
<style>
.fm-wrap{margin-top:18px;font-variant-numeric:tabular-nums;}
.fm-bar{background:#1E1882;color:#fff;text-align:center;font-weight:600;font-size:15px;
  padding:9px;border-radius:12px 12px 0 0;}
.fm-scroll{overflow-x:auto;border:1px solid #E6E6F0;border-top:none;}
.fm-tab{width:100%;border-collapse:separate;border-spacing:0;font-size:11px;}
.fm-tab th{background:#3C3489;color:#fff;font-weight:600;padding:6px 6px;text-align:right;
  white-space:nowrap;}
.fm-tab th.lbl{text-align:left;}
.fm-tab th.tot{background:#2C2C3A;}
.fm-tab td{padding:5px 6px;text-align:right;border-top:1px solid #F0F0F5;border-right:1px solid #F5F5F8;
  white-space:nowrap;}
.fm-tab td.lbl{text-align:left;font-weight:600;color:#15151F;background:#FAFAFC;}
.fm-tab td.tot{font-weight:700;background:#F2F2F7;}
.fm-tab tr.fm-yr td{font-weight:600;}
.fm-tab tr.fm-sub td{color:#6B6B7A;font-size:10.5px;}
.fm-note{font-size:11px;color:#A6A6B2;padding:9px 16px;border:1px solid #E6E6F0;border-top:none;
  border-radius:0 0 12px 12px;background:#fff;}
</style>
"""
_MES_AB = ["", "JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def _cor_yoy(pct):
    """(bg, fg) por crescimento YoY: verde forte ≥30%, âmbar 0-30%, vermelho <0, neutro None."""
    if pct is None:
        return ("#F7F7FB", "#15151F")
    if pct >= 0.30:
        return ("#10B981", "#FFFFFF")
    if pct >= 0:
        return ("#FDE68A", "#8A5A00")
    return ("#FCA5A5", "#7F1D1D")


def render_faturamento_mensal(anos=(2024, 2025, 2026)) -> None:
    """Matriz de faturamento mensal (notas) por ano com YoY% e acumulado (3º print
    do Vinícius). Puxa ao vivo do BQ; cada valor pintado pelo crescimento vs o
    mesmo mês do ano anterior. % mês = MoM-ano; % acum = acumulado no ano vs período."""
    a_min, a_max = min(anos), max(anos)
    try:
        df = query(f"""
            SELECT EXTRACT(YEAR FROM o.invoice_date) y, EXTRACT(MONTH FROM o.invoice_date) m,
                   SUM(o.product_amount) v
            FROM `{ORD}.fact_sales_order` o {NAT}
            WHERE o.invoice_date >= '{a_min-1}-01-01' AND o.invoice_date < '{a_max+1}-01-01'
            GROUP BY 1, 2
        """)
    except Exception as e:
        st.warning(f"Não foi possível montar o faturamento mensal: {e}")
        return

    M = {(int(r.y), int(r.m)): float(r.v or 0) for r in df.itertuples(index=False)}
    hoje = date.today()
    val = lambda y, m: M.get((y, m), 0.0)
    fut = lambda y, m: (y > hoje.year) or (y == hoje.year and m > hoje.month)

    acum = {}
    for y in range(a_min - 1, a_max + 1):
        s = 0.0
        for m in range(1, 13):
            s += val(y, m); acum[(y, m)] = s

    def yoy(cur, prev):
        return (cur / prev - 1) if prev else None

    head = ('<tr><th class="lbl"></th>'
            + "".join(f"<th>{_MES_AB[m]}</th>" for m in range(1, 13))
            + '<th class="tot">TOTAL</th></tr>')

    corpo = []
    for y in anos:
        tem_yoy = any(val(y - 1, m) > 0 for m in range(1, 13))
        tot_y, tot_prev = sum(val(y, m) for m in range(1, 13)), sum(val(y - 1, m) for m in range(1, 13))

        # linha de valores (pintada pelo YoY)
        cels = f'<td class="lbl">{y}</td>'
        for m in range(1, 13):
            if fut(y, m):
                cels += '<td></td>'; continue
            bg, fg = _cor_yoy(yoy(val(y, m), val(y - 1, m)))
            cels += f'<td style="background:{bg};color:{fg};">{_brl(val(y, m))[3:]}</td>'
        cels += f'<td class="tot">{_brl(tot_y)[3:]}</td>'
        corpo.append(f'<tr class="fm-yr">{cels}</tr>')

        # % mês (YoY)
        if tem_yoy:
            cels = '<td class="lbl">% mês</td>'
            for m in range(1, 13):
                p = yoy(val(y, m), val(y - 1, m))
                if fut(y, m) or p is None:
                    cels += '<td></td>'; continue
                bg, fg = _cor_yoy(p)
                cels += f'<td style="background:{bg};color:{fg};">{p*100:.0f}%</td>'
            pt = yoy(tot_y, tot_prev)
            cels += f'<td class="tot">{pt*100:.0f}%</td>' if pt is not None else '<td class="tot"></td>'
            corpo.append(f'<tr class="fm-sub">{cels}</tr>')

        # acumulado
        cels = '<td class="lbl">acum.</td>'
        for m in range(1, 13):
            cels += '<td></td>' if fut(y, m) else f'<td>{_brl(acum[(y, m)])[3:]}</td>'
        cels += '<td class="tot"></td>'
        corpo.append(f'<tr class="fm-sub">{cels}</tr>')

        # % acum
        if tem_yoy:
            cels = '<td class="lbl">% acum.</td>'
            for m in range(1, 13):
                p = yoy(acum[(y, m)], acum[(y - 1, m)])
                if fut(y, m) or p is None:
                    cels += '<td></td>'; continue
                bg, fg = _cor_yoy(p)
                cels += f'<td style="background:{bg};color:{fg};">{p*100:.0f}%</td>'
            corpo.append(f'<tr class="fm-sub">{cels}<td class="tot"></td></tr>')

    st.markdown(
        _CSS_FM
        + '<div class="fm-wrap"><div class="fm-bar">Faturamento Mensal</div>'
        + f'<div class="fm-scroll"><table class="fm-tab"><thead>{head}</thead>'
        + f'<tbody>{"".join(corpo)}</tbody></table></div>'
        + '<div class="fm-note">Valores em R$ · cores pelo crescimento vs o ano anterior '
          '(verde ≥ 30%, âmbar 0-30%, vermelho queda) · % mês = vs mesmo mês do ano anterior · '
          '% acum = acumulado no ano vs mesmo período.</div></div>',
        unsafe_allow_html=True,
    )
