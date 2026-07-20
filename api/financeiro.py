"""
Setor Financeiro — porta de dashboard/views/financeiro.py.

Lê a gold materializada (gold_financeiro): KPIs mensais e DRE por grupo (base
tables), mais Contas a Receber/Pagar, Liquidações e Fluxo de Caixa (views). Todos
os blocos têm dados reais. DRE colapsa company_code (SUM por grupo/descrição); os
KPIs já vêm consolidados por mês/regime. Regime é validado contra o enum.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from .bq import query, PROJECT_PROD

PROJ = PROJECT_PROD
GOLD_FIN = f"{PROJ}.gold_financeiro"
REGIMES = {"CAIXA", "COMPETENCIA"}
CORES_KPI = {"faturamento": "#1E1882", "margem_bruta": "#10B981", "ebitda": "#F59E0B"}


def _num(v, d=0.0) -> float:
    try:
        f = float(v)
        return d if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return d


def _regime(r: str) -> str:
    r = (r or "").upper()
    return r if r in REGIMES else "CAIXA"


def _range(ini: str | None, fim: str | None):
    hoje = date.today()
    f_def = hoje.replace(day=1)
    i_def = f_def.replace(year=f_def.year - 1)
    i = pd.Timestamp(ini).date().replace(day=1) if ini else i_def
    f = pd.Timestamp(fim).date().replace(day=1) if fim else f_def
    return i, f


def _etl(df, row) -> str | None:
    if "etl_loaded_at" in df.columns and pd.notna(row["etl_loaded_at"]):
        return str(pd.Timestamp(row["etl_loaded_at"]))
    return None


# ── Bloco A — KPIs Mensais ─────────────────────────────────────
def kpis(regime="CAIXA", ini=None, fim=None) -> dict:
    regime = _regime(regime)
    i, f = _range(ini, fim)
    df = query(f"""
        SELECT * FROM `{GOLD_FIN}.gold_fin_kpis_mensais`
        WHERE regime = '{regime}' AND mes BETWEEN DATE('{i}') AND DATE('{f}')
        ORDER BY mes DESC
    """)
    out = {"ready": True, "regime": regime, "range": {"ini": str(i), "fim": str(f)},
           "serie_meta": {"cores": CORES_KPI}}
    if df.empty:
        return {**out, "empty": True, "cards": [], "serie": []}

    fields = [("Faturamento", "faturamento"), ("Margem Bruta", "margem_bruta"),
              ("EBITDA", "ebitda"), ("Lucro Líquido", "lucro_liquido")]
    row = df.iloc[0]
    ant = df.iloc[1] if len(df) > 1 else None
    cards = []
    for label, fld in fields:
        val = _num(row[fld])
        mom, variant, dir_ = None, "neutral", "flat"
        if ant is not None and _num(ant[fld]) != 0:
            a = _num(ant[fld])
            mom = (val - a) / abs(a) * 100
            dir_ = "up" if mom >= 0 else "down"
            variant = "success" if mom >= 0 else "danger"
        cards.append({"label": label, "field": fld, "valor": val,
                      "mom_pct": mom, "dir": dir_, "variant": variant})

    df2 = df.sort_values("mes")
    serie = [{"mes": str(pd.Timestamp(r["mes"]).date()),
              "faturamento": _num(r["faturamento"]),
              "margem_bruta": _num(r["margem_bruta"]),
              "ebitda": _num(r["ebitda"])} for _, r in df2.iterrows()]

    hoje = date.today()
    parcial = (f.year == hoje.year and f.month == hoje.month)
    return {**out, "empty": False, "mes_corrente_parcial": parcial,
            "cards": cards, "serie": serie, "etl_loaded_at": _etl(df, row)}


# ── Bloco B — DRE por grupo + pizza ────────────────────────────
def dre(regime="CAIXA", ini=None, fim=None, mes=None) -> dict:
    regime = _regime(regime)
    i, f = _range(ini, fim)
    df = query(f"""
        SELECT mes, grupo_dre, descricao, ordem_exibicao,
               SUM(valor) AS valor, SUM(title_count) AS title_count
        FROM `{GOLD_FIN}.gold_fin_dre_mensal`
        WHERE regime = '{regime}' AND mes BETWEEN DATE('{i}') AND DATE('{f}')
        GROUP BY mes, grupo_dre, descricao, ordem_exibicao
        ORDER BY mes DESC, ordem_exibicao
    """)
    out = {"ready": True, "regime": regime}
    if df.empty:
        return {**out, "empty": True, "meses_disponiveis": [], "linhas": [], "pizza": []}

    df["mes"] = pd.to_datetime(df["mes"]).dt.date
    meses = sorted(df["mes"].unique().tolist(), reverse=True)
    mes_sel = pd.Timestamp(mes).date().replace(day=1) if mes else meses[0]
    if mes_sel not in meses:
        mes_sel = meses[0]
    dmes = df[df["mes"] == mes_sel]

    linhas = [{"grupo_dre": str(r["grupo_dre"]),
               "descricao": str(r["descricao"]) if pd.notna(r["descricao"]) else "",
               "valor": _num(r["valor"]),
               "ordem": int(r["ordem_exibicao"]) if pd.notna(r["ordem_exibicao"]) else 99,
               "title_count": int(r["title_count"] or 0)} for _, r in dmes.iterrows()]

    # Pizza por magnitude (|valor|) por grupo — mais informativa que só positivos.
    grp = dmes.groupby("grupo_dre")["valor"].sum().reset_index()
    pizza = [{"grupo_dre": str(r["grupo_dre"]), "valor": abs(_num(r["valor"]))}
             for _, r in grp.iterrows() if abs(_num(r["valor"])) > 0]

    return {**out, "empty": False, "meses_disponiveis": [str(m) for m in meses],
            "mes_selecionado": str(mes_sel), "linhas": linhas, "pizza": pizza,
            "etl_loaded_at": _etl(df, df.iloc[0])}


# ── Blocos D/E — Contas a Receber / Pagar ──────────────────────
def _contas(view: str) -> dict:
    df = query(f"SELECT * FROM `{GOLD_FIN}.{view}` ORDER BY vencimento")
    if df.empty:
        return {"ready": True, "empty": True, "resumo": {}, "por_vencimento": [], "titulos_sample": []}
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0.0)
    df["vencimento"] = pd.to_datetime(df["vencimento"], errors="coerce")
    total = float(df["valor"].sum())
    titulos = int(len(df))
    hoje = pd.Timestamp(date.today())
    vencido = float(df[df["vencimento"] < hoje]["valor"].sum())
    pct = vencido / total * 100 if total else 0.0
    variant = "danger" if pct > 15 else ("warning" if pct > 5 else "success")

    df["_mes"] = df["vencimento"].dt.to_period("M").dt.to_timestamp()
    pv = (df.dropna(subset=["_mes"]).groupby("_mes")["valor"].sum().reset_index().sort_values("_mes"))
    por_venc = [{"mes": str(r["_mes"].date()), "valor": _num(r["valor"])} for _, r in pv.iterrows()]

    sample = df.head(200)
    titulos_sample = [{
        "title_number": str(r.get("title_number", "")),
        "partner_name": str(r.get("partner_name", "")) if pd.notna(r.get("partner_name")) else "—",
        "vencimento": str(r["vencimento"].date()) if pd.notna(r["vencimento"]) else "—",
        "valor": _num(r["valor"]),
        "group_name": str(r.get("group_name", "")) if pd.notna(r.get("group_name")) else "—",
        "subgroup": str(r.get("subgroup", "")) if pd.notna(r.get("subgroup")) else "—",
    } for _, r in sample.iterrows()]

    return {
        "ready": True, "empty": False,
        "resumo": {"total": total, "titulos": titulos, "vencido": vencido,
                   "pct_vencido": pct, "pct_variant": variant},
        "por_vencimento": por_venc, "titulos_sample": titulos_sample,
    }


def contas_receber() -> dict:
    return _contas("contas_receber")


def contas_pagar() -> dict:
    return _contas("contas_pagar")


# ── Bloco F — Liquidações ──────────────────────────────────────
def liquidacoes() -> dict:
    df = query(f"SELECT * FROM `{GOLD_FIN}.liquidacoes_mensais` ORDER BY mes DESC LIMIT 24")
    if df.empty:
        return {"ready": True, "empty": True, "resumo": {}, "por_mes": []}
    df["mes"] = pd.to_datetime(df["mes"]).dt.date
    df["valor_liquidado"] = pd.to_numeric(df["valor_liquidado"], errors="coerce").fillna(0.0)
    df["qtd"] = pd.to_numeric(df["qtd"], errors="coerce").fillna(0)
    por_mes = [{"mes": str(r["mes"]), "tipo_liquidacao": str(r["tipo_liquidacao"]),
                "valor_liquidado": _num(r["valor_liquidado"]), "qtd": int(r["qtd"])}
               for _, r in df.iterrows()]
    return {"ready": True, "empty": False,
            "resumo": {"total_liquidado": float(df["valor_liquidado"].sum()),
                       "qtd": int(df["qtd"].sum())},
            "por_mes": por_mes}


# ── Bloco G — Fluxo de Caixa ───────────────────────────────────
def fluxo_caixa() -> dict:
    df = query(f"SELECT * FROM `{GOLD_FIN}.fluxo_caixa` ORDER BY mes DESC LIMIT 24")
    if df.empty:
        return {"ready": True, "empty": True, "resumo": {}, "por_mes": []}
    df["mes"] = pd.to_datetime(df["mes"]).dt.date
    for c in ("entradas", "saidas", "saldo"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    agg = (df.groupby("mes").agg(entradas=("entradas", "sum"), saidas=("saidas", "sum"),
                                 saldo=("saldo", "sum")).reset_index().sort_values("mes"))
    saldo_acum = float(agg["saldo"].sum())
    saldo_ult = _num(agg.iloc[-1]["saldo"]) if not agg.empty else 0.0
    por_mes = [{"mes": str(r["mes"]), "entradas": _num(r["entradas"]),
                "saidas": _num(r["saidas"]), "saldo": _num(r["saldo"])} for _, r in agg.iterrows()]
    return {"ready": True, "empty": False,
            "resumo": {"saldo_acumulado": saldo_acum, "saldo_ultimo_mes": saldo_ult,
                       "saldo_ultimo_variant": "success" if saldo_ult >= 0 else "danger"},
            "por_mes": por_mes}
