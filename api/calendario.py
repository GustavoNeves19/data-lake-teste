"""
Calendário de Vendas Diárias + Faturamento Mensal (3 anos) — porta fiel de
dashboard/utils/calendario_view.py.

Duas visões com RÉGUAS DIFERENTES (não trocar):
- Calendário: vendas diárias por `order_date` (emissão do pedido).
- Matriz anual: faturamento por `invoice_date` (nota fiscal), YoY 3 anos.

Ambas com a metodologia canônica (financial_flag<>'N'). Reutiliza a matemática
de dias úteis e a META_EQUIPE de gestao_vista (metas provisórias).
"""

from __future__ import annotations

import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from .bq import query, PROJECT_PROD
from . import gestao_vista as gv

PROJ = PROJECT_PROD
ORD = f"{PROJ}.dm_orders"
NAT = (f"JOIN `{ORD}.dim_operation_nature` n "
       f"ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'")

WEEKDAYS = ["DOMINGO", "SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO"]
MONTHS_ABBR = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def _f(v) -> float:
    try:
        f = float(v)
        return 0.0 if f != f else f
    except (TypeError, ValueError):
        return 0.0


# ── (1) Calendário de vendas diárias (régua = order_date) ──────────────
def calendario(mes: str | None = None) -> dict:
    mes_ref = pd.Timestamp(mes).date().replace(day=1) if mes else date.today().replace(day=1)
    mes_fim = (date(mes_ref.year + (mes_ref.month == 12),
                    (mes_ref.month % 12) + 1, 1))

    # Vendas (order_date) e Faturamento (invoice_date) são réguas diferentes e
    # independentes uma da outra — dispara juntas.
    sql = {
        "df": f"""
            SELECT o.order_date d, SUM(o.product_amount) v
            FROM `{ORD}.fact_sales_order` o {NAT}
            WHERE o.order_date >= '{mes_ref}' AND o.order_date < '{mes_fim}'
              AND o.order_date IS NOT NULL
            GROUP BY 1
        """,
        "fdf": f"""
            SELECT SUM(o.product_amount) v
            FROM `{ORD}.fact_sales_order` o {NAT}
            WHERE o.invoice_date >= '{mes_ref}' AND o.invoice_date < '{mes_fim}'
              AND o.invoice_date IS NOT NULL
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    df, fdf = dfs["df"], dfs["fdf"]
    diario = {}
    if not df.empty:
        df["d"] = pd.to_datetime(df["d"]).dt.date
        diario = {d.day: _f(v) for d, v in zip(df["d"], df["v"])}

    hoje = date.today()
    mes_corrente = (hoje.year == mes_ref.year and hoje.month == mes_ref.month)
    # Meta editável pela liderança via /admin: lê do Postgres (metas_equipe) primeiro, cai na constante gv.META_EQUIPE se vazia. Mês passado fica neutro.
    meta = gv.meta_atual("GERAL", mes_ref) if mes_corrente else 0.0
    tem_meta = meta > 0
    ref = hoje if mes_corrente else date.fromordinal(mes_fim.toordinal() - 1)

    du = gv.dias_uteis_mes(ref)
    du_corr = gv.dia_util_corrente(ref)
    meta_dia = meta / du if du else 0.0
    vendas = sum(diario.values())
    rem_total = max(meta - vendas, 0.0)
    dias_rest = max(du - du_corr, 0) if mes_corrente else 0
    rem_dia = rem_total / dias_rest if dias_rest else 0.0
    pct = vendas / meta if meta else 0.0

    # Projeção de vendas no ritmo por dia útil: realizado ÷ dias úteis corridos ×
    # dias úteis totais (onde a gente fecha o mês nesse ritmo). Mês fechado = o próprio realizado.
    projecao = (vendas / du_corr * du) if (mes_corrente and du_corr) else vendas

    # Bloco de Faturamento (nota emitida, invoice_date) — separado do de Vendas (pedido,
    # order_date), igual ao original do Vinícius: mostra Faturamento + Projeção. (fdf já
    # veio junto com df, acima)
    faturamento = _f(fdf.iloc[0]["v"]) if not fdf.empty else 0.0
    fat_projecao = (faturamento / du_corr * du) if (mes_corrente and du_corr) else faturamento

    cal = calendar.Calendar(firstweekday=6)  # domingo
    weeks = []
    for week in cal.monthdayscalendar(mes_ref.year, mes_ref.month):
        cells = []
        wtot = 0.0
        for day in week:
            if day == 0:
                cells.append({"day": 0, "empty": True})
                continue
            val = diario.get(day, 0.0)
            wtot += val
            hit = None if not tem_meta else (val >= meta_dia)
            cells.append({"day": day, "value": val, "hit": hit})
        weeks.append({"cells": cells, "week_total": wtot})

    return {
        "titulo": f"Vendas Diárias — {gv.MESES_PT[mes_ref.month]}/{mes_ref.year}",
        "mes": str(mes_ref),
        "weeks": weeks,
        "weekdays": WEEKDAYS,
        "footer": {
            "tem_meta": tem_meta,
            "meta_dia": meta_dia, "vendas": vendas, "meta": meta,
            "rem_dia": rem_dia, "dias_rest": dias_rest, "rem_total": rem_total,
            "pct": pct, "du": du, "du_corr": du_corr,
            "projecao": projecao,
            "faturamento": faturamento, "fat_projecao": fat_projecao,
        },
    }


# ── (2) Matriz de faturamento mensal 3 anos (régua = invoice_date) ─────
def faturamento_anual(anos=(2024, 2025, 2026)) -> dict:
    a_min, a_max = min(anos), max(anos)
    df = query(f"""
        SELECT EXTRACT(YEAR FROM o.invoice_date) y, EXTRACT(MONTH FROM o.invoice_date) m,
               SUM(o.product_amount) v
        FROM `{ORD}.fact_sales_order` o {NAT}
        WHERE o.invoice_date >= '{a_min - 1}-01-01' AND o.invoice_date < '{a_max + 1}-01-01'
        GROUP BY 1, 2
    """)
    M = {(int(r["y"]), int(r["m"])): _f(r["v"]) for _, r in df.iterrows()}

    def val(y, m):
        return M.get((y, m), 0.0)

    today = date.today()

    def fut(y, m):
        return y > today.year or (y == today.year and m > today.month)

    acum = {}
    for y in range(a_min - 1, a_max + 1):
        run = 0.0
        for m in range(1, 13):
            run += val(y, m)
            acum[(y, m)] = run

    def yoy(cur, prev):
        return (cur / prev - 1) if prev else None

    years = []
    for y in anos:
        tem_yoy = any(val(y - 1, m) > 0 for m in range(1, 13))
        values = [{"value": val(y, m), "yoy_pct": yoy(val(y, m), val(y - 1, m)),
                   "future": fut(y, m)} for m in range(1, 13)]
        value_total = sum(val(y, m) for m in range(1, 13))
        tot_prev = sum(val(y - 1, m) for m in range(1, 13))
        yoy_total = yoy(value_total, tot_prev)
        yoy_mes = ([{"pct": yoy(val(y, m), val(y - 1, m)), "future": fut(y, m)}
                    for m in range(1, 13)] if tem_yoy else None)
        acum_row = [{"value": acum[(y, m)], "future": fut(y, m)} for m in range(1, 13)]
        yoy_acum = ([{"pct": yoy(acum[(y, m)], acum[(y - 1, m)]), "future": fut(y, m)}
                     for m in range(1, 13)] if tem_yoy else None)
        years.append({
            "year": y, "values": values, "value_total": value_total,
            "yoy_mes": yoy_mes, "yoy_total": yoy_total,
            "acum": acum_row, "yoy_acum": yoy_acum, "tem_yoy": tem_yoy,
        })

    return {"months": MONTHS_ABBR, "years": years}
