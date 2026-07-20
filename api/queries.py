"""
Camada de consultas Comercial — porta fiel do dashboard/pages/02_Comercial_e_Compras.py.

O SQL e a agregação pandas são idênticos ao Streamlit, garantindo que os números
batam ao centavo. Cada função devolve estruturas JSON-safe prontas pro React.
"""

from __future__ import annotations

import calendar
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd

from .bq import query, PROJECT_PROD
from . import gestao_vista as gv

PROJ = PROJECT_PROD
ORDERS = f"{PROJ}.dm_orders"
QUOTES = f"{PROJ}.dm_quotes"
PARTNERS = f"{PROJ}.dm_partners"
IMPORTS = f"{PROJ}.dm_imports"
SILVER_COM = f"{PROJ}.silver_comercial"
GOLD_COM = f"{PROJ}.gold_comercial"
CRM = f"{PROJ}.crm_raw"

_MES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

# Normalização de nome do vendedor (idêntico ao Streamlit).
SP_DISPLAY = """CASE COALESCE(rfv_salesperson, 'Sem Vendedor')
        WHEN 'Guilherme'    THEN 'Guilherme Aquino'
        WHEN 'Kaua'         THEN 'Kauã Rodrigues'
        WHEN 'Kauã'         THEN 'Kauã Rodrigues'
        WHEN 'Ramos'        THEN 'Kauan Ramos'
        WHEN 'Richard'      THEN 'Richard Lucas'
        WHEN 'Giovanna'     THEN 'Geovanna Gomes'
        WHEN 'Ribeiro'      THEN 'Cauã Ribeiro'
        WHEN 'Sem Vendedor' THEN 'Cliente Novo'
        ELSE COALESCE(rfv_salesperson, 'Cliente Novo')
      END"""

GIOVANNA_RESIDUO_FILTER = (
    "AND NOT (rfv_familia = 'HOSPITALAR' AND rfv_salesperson = 'Giovanna')"
)

# ── RFV por CARTEIRA (YCARCOM) ─────────────────────────────────────────────────
# A carteira vem do CLIENTE (carteira_code / YCARCOM), NÃO do vendedor da venda.
# Rótulo (decisão Gustavo 10/07): Farmácia é bucket único "Cauã (Farmácia)" (não é
# dividida em A-F); senão o carteira_code CA-CF vira "Carteira A"…"Carteira F";
# cliente sem carteira -> "Sem carteira".
_CART_LETRA = {"CA": "A", "CB": "B", "CC": "C", "CD": "D", "CE": "E", "CF": "F"}
# Família de cada carteira (grupo do titular, confirmado no ERP 10/07: 5 Hosp + 1 SAC;
# F = Eduardo/licitação). Serve pro rótulo do filtro vir já segmentado.
_CART_FAMILIA = {"CA": "Hospitalar", "CB": "Hospitalar", "CC": "Hospitalar",
                 "CD": "Hospitalar", "CE": "Hospitalar", "CF": "Licitação"}


def _cart_label(code, familia):
    if familia and "FARMACIA" in str(familia).upper():
        return "Cauã (Farmácia)"
    if not code:
        return "Sem carteira"
    return f"Carteira {_CART_LETRA.get(str(code), str(code))}"


# Silver com a carteira do cliente anexada (derivada via partner_codes_list -> dim_partner).
# ANY_VALUE da carteira entre as filiais do cliente (elas quase sempre concordam); serve
# pra CONTAGEM/segmentação. O VALOR exato por carteira vem da base oficial (_carteira_faturamento).
SILVER_CART = f"""(
    SELECT s.*,
        COALESCE(cc.carteira_code, 'Sem carteira') AS carteira_raw
    FROM `{SILVER_COM}.silver_com_rfv_score` s
    LEFT JOIN (
        SELECT z.partner_name, ANY_VALUE(dp.carteira_code) AS carteira_code
        FROM `{SILVER_COM}.silver_com_rfv_score` z,
             UNNEST(SPLIT(z.partner_codes_list, ',')) pc
        JOIN `{PARTNERS}.dim_partner` dp ON CAST(dp.partner_code AS STRING) = TRIM(pc)
        WHERE dp.carteira_code IS NOT NULL
        GROUP BY z.partner_name
    ) cc ON cc.partner_name = s.partner_name
)"""


def _carteira_faturamento(carteira_code: str, ref: str) -> float:
    """Faturamento EXATO da carteira (base oficial: por partner_code/YCARCOM,
    financial_flag<>'N', exclui 000054, janela 12m terminando em `ref`).
    Bate o Alves no centavo (Δ=0). carteira_code = 'CA'..'CF'."""
    try:
        df = query(f"""
            SELECT SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o
            JOIN `{ORDERS}.dim_operation_nature` n
              ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
            JOIN `{PARTNERS}.dim_partner` p ON p.partner_code = o.partner_code
            WHERE o.invoice_date >= DATE_TRUNC(DATE_SUB(DATE '{ref}', INTERVAL 1 YEAR), MONTH)
              AND o.invoice_date <= DATE '{ref}'
              AND p.carteira_code = '{carteira_code}'
              AND o.channel_code <> '000054'
        """)
        return _num(df.iloc[0]["v"]) if not df.empty else 0.0
    except Exception:
        return 0.0

CANAL_CASE = """
CASE
  WHEN o.salesperson_group_code = 'FA' THEN 'Hospitalar'
  WHEN o.salesperson_group_code = 'FR' THEN 'Farmácias'
  WHEN o.salesperson_group_code = 'PC' THEN 'SAC'
  WHEN o.salesperson_group_code = 'EC' OR o.salesperson_group_code IS NULL THEN 'Marketplace'
  ELSE 'Outros'
END
"""

ORDEM_CANAL = ["Hospitalar", "Marketplace", "Farmácias", "SAC", "Outros"]

# Sub-canal do Marketplace (YCODVEN), mesma classificação do PRICE
# (sql/gold_price/build_gold_price.sql) — só faz sentido dentro do balde
# "Marketplace" do CANAL_CASE acima (group_code EC/NULL).
SUB_CANAL_MKT = {
    "92": "Mercado Livre",
    "AM": "Amazon",
    "SH": "Shopee", "SHOPEE": "Shopee",
    "LI": "Outros Marketplaces", "OL": "Outros Marketplaces",
    "90": "Outros Marketplaces", "91": "Outros Marketplaces", "AME": "Outros Marketplaces",
}


def _sub_canal_marketplace(channel_code) -> str:
    return SUB_CANAL_MKT.get(str(channel_code).strip().upper(), "Outros Marketplaces")


# ── helpers ───────────────────────────────────────────────────
def _num(v, default=0.0):
    """Converte para float JSON-safe (NaN/None -> default)."""
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _safe_pct(num, den):
    return (num - den) / den * 100 if den else None


def mes_label(d) -> str:
    d = pd.Timestamp(d)
    return f"{_MES_PT[d.month]}/{d.year}"


# ══════════════════════════════════════════════════════════════
# Aba VENDAS — Dashboard Semanal de Liderança
# ══════════════════════════════════════════════════════════════
def meses_disponiveis() -> list[dict]:
    df = query(f"""
        SELECT DISTINCT DATE_TRUNC(invoice_date, MONTH) AS mes
        FROM `{ORDERS}.fact_sales_order`
        WHERE invoice_date >= '2024-01-01' AND invoice_date IS NOT NULL
        ORDER BY 1 DESC LIMIT 30
    """)
    meses = pd.to_datetime(df["mes"]).dt.date.tolist()
    return [{"value": str(m), "label": mes_label(m)} for m in meses]


def vendas(mes: str, incluir_marketplace: bool = True) -> dict:
    """Dashboard de Liderança para o mês `mes` (YYYY-MM-DD, 1º dia do mês).

    `incluir_marketplace` (toggle do Streamlit, default ON): quando False, tira o
    canal Marketplace dos KPIs/canais/semanal (ticket B2B puro).
    """
    mes_ref = pd.Timestamp(mes).date()
    mes_ant = (pd.Timestamp(mes_ref) - pd.offsets.MonthBegin(1)).date()
    mes_ano_ant = pd.Timestamp(mes_ref).replace(year=mes_ref.year - 1).date()
    # Evolução mensal por canal usa uma janela própria (12 meses); independente da
    # query de 3 meses acima — dispara junto, não em sequência (perf).
    mes_inicio = (pd.Timestamp(mes_ref) - pd.offsets.MonthBegin(11)).date()
    mes_fim = (pd.Timestamp(mes_ref) + pd.offsets.MonthEnd(0)).date()

    sql = {
        "df": f"""
          SELECT
            {CANAL_CASE} AS canal,
            o.channel_code,
            DATE_TRUNC(o.invoice_date, MONTH) AS mes,
            o.order_number, o.invoice_date, o.product_amount
          FROM `{ORDERS}.fact_sales_order` o
          JOIN `{ORDERS}.dim_operation_nature` n
            ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
          WHERE DATE_TRUNC(o.invoice_date, MONTH) IN (
                DATE('{mes_ref}'), DATE('{mes_ant}'), DATE('{mes_ano_ant}'))
            AND o.invoice_date IS NOT NULL
        """,
        "df_evol": f"""
          SELECT
            DATE_TRUNC(o.invoice_date, MONTH) AS mes,
            {CANAL_CASE} AS canal,
            SUM(o.product_amount) AS faturamento
          FROM `{ORDERS}.fact_sales_order` o
          JOIN `{ORDERS}.dim_operation_nature` n
            ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
          WHERE o.invoice_date BETWEEN DATE('{mes_inicio}') AND DATE('{mes_fim}')
            AND o.invoice_date IS NOT NULL
          GROUP BY mes, canal
          ORDER BY mes, canal
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    df, df_evol = dfs["df"], dfs["df_evol"]

    out: dict = {
        "mes_ref": str(mes_ref), "mes_ant": str(mes_ant), "mes_ano_ant": str(mes_ano_ant),
        "label_ref": mes_label(mes_ref), "label_ant": mes_label(mes_ant),
        "label_yoy": mes_label(mes_ano_ant),
    }
    if df.empty:
        out.update(empty=True)
        return out

    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df["mes"] = pd.to_datetime(df["mes"]).dt.date
    df["product_amount"] = pd.to_numeric(df["product_amount"], errors="coerce").fillna(0.0)

    df_mes = df[df["mes"] == mes_ref]
    df_ant = df[df["mes"] == mes_ant]
    df_yoy = df[df["mes"] == mes_ano_ant]

    if not incluir_marketplace:
        df_mes = df_mes[df_mes["canal"] != "Marketplace"]
        df_ant = df_ant[df_ant["canal"] != "Marketplace"]
        df_yoy = df_yoy[df_yoy["canal"] != "Marketplace"]

    fat_mes = float(df_mes["product_amount"].sum())
    fat_ant = float(df_ant["product_amount"].sum())
    fat_yoy = float(df_yoy["product_amount"].sum())
    trans_mes = int(len(df_mes))
    ticket = fat_mes / trans_mes if trans_mes else 0

    # Projeção: só no mês corrente — onde a equipe DEVERIA estar hoje (meta GERAL).
    # Lê a meta do Postgres (metas_equipe) via gv.meta_atual, mesma fonte da Gestão
    # à Vista, para refletir edições feitas pela liderança em tempo real.
    hoje = date.today()
    if mes_ref.year == hoje.year and mes_ref.month == hoje.month:
        meta_geral = gv.meta_atual("GERAL", mes_ref)
        projecao = gv.projecao_esperada(meta_geral, hoje)
    else:
        meta_geral = None
        projecao = None

    out["empty"] = False
    out["kpis"] = {
        "faturamento": fat_mes, "fat_ant": fat_ant, "fat_yoy": fat_yoy,
        "var_mom": _safe_pct(fat_mes, fat_ant), "var_yoy": _safe_pct(fat_mes, fat_yoy),
        "ticket": ticket, "transacoes": trans_mes,
        # meta = meta mensal total (Postgres); projecao = ponto onde deveríamos estar hoje.
        # Front usa meta como 100% da barra de ritmo, projecao como marca do ponto.
        "meta": meta_geral,
        "projecao": projecao,
    }

    # Breakdown por canal
    ag = df_mes.groupby("canal").agg(
        faturamento=("product_amount", "sum"),
        transacoes=("order_number", "count"),
    ).reset_index()
    ant = df_ant.groupby("canal")["product_amount"].sum().rename("fat_ant").reset_index()
    yoy = df_yoy.groupby("canal")["product_amount"].sum().rename("fat_yoy").reset_index()
    ag = ag.merge(ant, on="canal", how="left").merge(yoy, on="canal", how="left")
    ag["fat_ant"] = ag["fat_ant"].fillna(0)
    ag["fat_yoy"] = ag["fat_yoy"].fillna(0)
    ag["__ord"] = ag["canal"].map({c: i for i, c in enumerate(ORDEM_CANAL)}).fillna(99)
    ag = ag.sort_values("__ord")

    canais = []
    for _, r in ag.iterrows():
        fat = _num(r["faturamento"])
        trans = int(r["transacoes"])
        canais.append({
            "canal": r["canal"],
            "faturamento": fat,
            "fat_ant": _num(r["fat_ant"]),
            "fat_yoy": _num(r["fat_yoy"]),
            "transacoes": trans,
            "ticket": fat / trans if trans else 0,
            "var_mom": _safe_pct(fat, _num(r["fat_ant"])),
            "var_yoy": _safe_pct(fat, _num(r["fat_yoy"])),
        })
    out["canais"] = canais

    # Detalhe do Marketplace por sub-canal (Mercado Livre/Amazon/Shopee/Outros),
    # pedido do grupo (15/07): "quais sub canais entram no faturamento do
    # marketplace" + "deixar explícito a fonte". Mesma classificação por
    # channel_code (YCODVEN) usada no PRICE, aplicada só às linhas já
    # classificadas como Marketplace pelo CANAL_CASE (salesperson_group_code
    # EC/nulo) — fonte é a mesma fact_sales_order/invoice_date do card acima.
    mkt_mes = df_mes[df_mes["canal"] == "Marketplace"].copy()
    marketplace_detalhe = []
    if not mkt_mes.empty:
        mkt_mes["sub_canal"] = mkt_mes["channel_code"].apply(_sub_canal_marketplace)
        fat_mkt_total = float(mkt_mes["product_amount"].sum())
        ag_mkt = mkt_mes.groupby("sub_canal").agg(
            faturamento=("product_amount", "sum"),
            transacoes=("order_number", "count"),
        ).reset_index().sort_values("faturamento", ascending=False)
        for _, r in ag_mkt.iterrows():
            fat = _num(r["faturamento"])
            trans = int(r["transacoes"])
            marketplace_detalhe.append({
                "sub_canal": r["sub_canal"],
                "faturamento": fat,
                "transacoes": trans,
                "ticket": fat / trans if trans else 0,
                "pct_marketplace": (fat / fat_mkt_total * 100) if fat_mkt_total else 0,
            })
    out["marketplace_detalhe"] = marketplace_detalhe

    # Evolução mensal por canal — últimos 12 meses (df_evol já veio junto com df, acima)
    evolucao = []
    total_mensal = []
    if not df_evol.empty:
        df_evol["mes"] = pd.to_datetime(df_evol["mes"])
        df_evol["faturamento"] = pd.to_numeric(df_evol["faturamento"], errors="coerce").fillna(0)
        df_evol["mes_label"] = df_evol["mes"].dt.strftime("%b/%y").str.capitalize()
        # pivot: uma linha por mês, uma coluna por canal
        piv = df_evol.pivot_table(index=["mes", "mes_label"], columns="canal",
                                  values="faturamento", aggfunc="sum", fill_value=0).reset_index()
        piv = piv.sort_values("mes")
        for _, r in piv.iterrows():
            row = {"mes_label": r["mes_label"]}
            for c in ORDEM_CANAL:
                row[c] = _num(r[c]) if c in piv.columns else 0
            evolucao.append(row)
        tot = df_evol.groupby(["mes", "mes_label"], as_index=False)["faturamento"].sum().sort_values("mes")
        tot["MoM"] = tot["faturamento"].pct_change() * 100
        for _, r in tot.iterrows():
            total_mensal.append({
                "mes_label": r["mes_label"],
                "faturamento": _num(r["faturamento"]),
                "mom": None if pd.isna(r["MoM"]) else float(r["MoM"]),
            })
    out["evolucao"] = evolucao
    out["total_mensal"] = total_mensal

    # Semanal — semana do mês (1-7, 8-14, ...)
    df_w = df_mes.copy()
    semanas = []
    if not df_w.empty:
        df_w["semana_mes"] = ((df_w["invoice_date"].dt.day - 1) // 7) + 1
        ag_sem = df_w.groupby(["semana_mes", "canal"]).agg(
            faturamento=("product_amount", "sum")).reset_index()
        ultimo = calendar.monthrange(mes_ref.year, mes_ref.month)[1]

        def _range_label(n):
            inicio = (n - 1) * 7 + 1
            fim = min(n * 7, ultimo)
            return f"Sem {n} ({inicio:02d}-{fim:02d}/{mes_ref.month:02d})"

        ag_sem["semana_label"] = ag_sem["semana_mes"].apply(_range_label)
        piv_s = ag_sem.pivot_table(index=["semana_mes", "semana_label"], columns="canal",
                                   values="faturamento", aggfunc="sum", fill_value=0).reset_index()
        piv_s = piv_s.sort_values("semana_mes")
        for _, r in piv_s.iterrows():
            row = {"semana_label": r["semana_label"]}
            for c in ORDEM_CANAL:
                row[c] = _num(r[c]) if c in piv_s.columns else 0
            semanas.append(row)
    out["semanas"] = semanas
    return out


def vendas_periodo(de: str, ate: str) -> dict:
    """Período Exato — pedidos (order_date) vs notas (invoice_date) na janela [de, ate].

    Régua dupla: notas faturadas por invoice_date, vendas/pedidos por order_date.
    """
    sql = {
        "notas": f"""
            SELECT {CANAL_CASE} AS canal, COUNT(*) AS pedidos, SUM(o.product_amount) AS faturamento
            FROM `{ORDERS}.fact_sales_order` o
            JOIN `{ORDERS}.dim_operation_nature` n
              ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
            WHERE o.invoice_date BETWEEN '{de}' AND '{ate}'
            GROUP BY 1 ORDER BY faturamento DESC
        """,
        "ped": f"""
            SELECT SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o
            JOIN `{ORDERS}.dim_operation_nature` n
              ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
            WHERE o.order_date BETWEEN '{de}' AND '{ate}'
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    notas, ped = dfs["notas"], dfs["ped"]
    tot_fat = float(notas["faturamento"].sum()) if not notas.empty else 0.0
    tot_ped = int(notas["pedidos"].sum()) if not notas.empty else 0
    tot_vendas = _num(ped.iloc[0]["v"]) if not ped.empty else 0.0
    por_canal = [{
        "canal": str(r["canal"]), "pedidos": int(r["pedidos"]),
        "faturamento": _num(r["faturamento"]),
    } for _, r in notas.iterrows()]
    return {
        "de": de, "ate": ate,
        "vendas_pedidos": tot_vendas, "faturamento_notas": tot_fat,
        "pedidos": tot_ped, "ticket": tot_fat / tot_ped if tot_ped else 0.0,
        "por_canal": por_canal,
    }


# ══════════════════════════════════════════════════════════════
# Aba COMPRAS
# ══════════════════════════════════════════════════════════════
def compras() -> dict:
    """Compras e Suprimentos — porta fiel do Streamlit (Nevoni FABRICA: doméstico +
    importação China). Todas as queries de compra filtram excluded_at IS NULL e
    natureza financeira (financial_flag<>'N'); janelas de 12 meses.

    As 6 queries são independentes entre si (só se combinam depois, em Python),
    então rodam em paralelo — troca ~6x round-trips sequenciais do BigQuery por 1
    (o tempo total vira o da mais lenta, não a soma de todas)."""
    sql = {
        # 3a) Compras mercadoria doméstica (12m)
        "dom": f"""
            SELECT COUNT(*) AS ordens, SUM(o.product_amount) AS valor
            FROM `{ORDERS}.fact_purchase_order` o
            JOIN `{ORDERS}.dim_operation_nature` n
              ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
            WHERE o.invoice_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
              AND o.excluded_at IS NULL
        """,
        # 3b) Importação (acumulado, todo período) — BRL/USD + top fornecedor
        "imp": f"""
            WITH s AS (
                SELECT supplier_name, SUM(total_brl) AS v
                FROM `{IMPORTS}.fact_import_order` WHERE excluded_at IS NULL GROUP BY 1
            )
            SELECT (SELECT SUM(v) FROM s) AS total_v,
                   (SELECT SUM(total_usd) FROM `{IMPORTS}.fact_import_order` WHERE excluded_at IS NULL) AS usd,
                   (SELECT v FROM s ORDER BY v DESC LIMIT 1) AS top_v,
                   (SELECT supplier_name FROM s ORDER BY v DESC LIMIT 1) AS top_name
        """,
        # 3c) Vendas (12m) — denominador da razão compra/venda
        "ven": f"""
            SELECT SUM(o.product_amount) AS v
            FROM `{ORDERS}.fact_sales_order` o
            JOIN `{ORDERS}.dim_operation_nature` n
              ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
            WHERE o.invoice_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
        """,
        # 3d) Vendas vs Compras por mês (12 meses fechados, exclui mês corrente)
        "ser": f"""
            WITH v AS (
              SELECT DATE_TRUNC(o.invoice_date, MONTH) AS mes, SUM(o.product_amount) AS vendas
              FROM `{ORDERS}.fact_sales_order` o
              JOIN `{ORDERS}.dim_operation_nature` n
                ON n.nature_code=o.nature_code AND n.financial_flag<>'N'
              WHERE o.invoice_date >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 12 MONTH)
                AND o.invoice_date < DATE_TRUNC(CURRENT_DATE(), MONTH) GROUP BY 1),
            c AS (
              SELECT DATE_TRUNC(o.invoice_date, MONTH) AS mes, SUM(o.product_amount) AS compras
              FROM `{ORDERS}.fact_purchase_order` o
              JOIN `{ORDERS}.dim_operation_nature` n
                ON n.nature_code=o.nature_code AND n.financial_flag<>'N'
              WHERE o.invoice_date >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 12 MONTH)
                AND o.invoice_date < DATE_TRUNC(CURRENT_DATE(), MONTH) AND o.excluded_at IS NULL GROUP BY 1)
            SELECT v.mes, v.vendas, COALESCE(c.compras, 0) AS compras
            FROM v LEFT JOIN c USING(mes) ORDER BY v.mes
        """,
        # 3e) Importação por fornecedor (top 8)
        "impf": f"""
            SELECT supplier_name, ROUND(SUM(total_brl), 0) AS valor
            FROM `{IMPORTS}.fact_import_order` WHERE excluded_at IS NULL
            GROUP BY 1 ORDER BY valor DESC LIMIT 8
        """,
        # 3f) Top fornecedores domésticos (12m, top 10)
        "topf": f"""
            SELECT p.partner_name AS fornecedor, COUNT(*) AS ordens, ROUND(SUM(o.product_amount), 2) AS valor
            FROM `{ORDERS}.fact_purchase_order` o
            JOIN `{ORDERS}.dim_operation_nature` n
              ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
            LEFT JOIN `{PARTNERS}.dim_partner` p USING (partner_code)
            WHERE o.invoice_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH) AND o.excluded_at IS NULL
            GROUP BY 1 ORDER BY valor DESC LIMIT 10
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    dom, imp, ven, ser, impf, topf = (dfs["dom"], dfs["imp"], dfs["ven"],
                                       dfs["ser"], dfs["impf"], dfs["topf"])

    dom_val = _num(dom.iloc[0]["valor"]) if not dom.empty else 0.0
    dom_ord = int(dom.iloc[0]["ordens"] or 0) if not dom.empty else 0

    imp_brl = _num(imp.iloc[0]["total_v"]) if not imp.empty else 0.0
    imp_usd = _num(imp.iloc[0]["usd"]) if not imp.empty else 0.0
    top_v = _num(imp.iloc[0]["top_v"]) if not imp.empty else 0.0
    top_name = (str(imp.iloc[0]["top_name"])
                if not imp.empty and pd.notna(imp.iloc[0]["top_name"]) else "—")

    ven_val = _num(ven.iloc[0]["v"]) if not ven.empty else 0.0
    razao = dom_val / ven_val * 100 if ven_val else 0.0
    conc = top_v / imp_brl * 100 if imp_brl else 0.0

    serie = []
    if not ser.empty:
        ser["mes"] = pd.to_datetime(ser["mes"])
        for _, r in ser.iterrows():
            serie.append({
                "mes_label": f"{_MES_PT[r['mes'].month][:3]}/{str(r['mes'].year)[2:]}",
                "vendas": _num(r["vendas"]),
                "compras": _num(r["compras"]),
            })

    import_fornecedores = [{
        "fornecedor": (str(r["supplier_name"])[:26] if pd.notna(r["supplier_name"]) else "—"),
        "valor": _num(r["valor"]),
    } for _, r in impf.iterrows()] if not impf.empty else []

    top_fornecedores = [{
        "fornecedor": str(r["fornecedor"]) if pd.notna(r["fornecedor"]) else "—",
        "ordens": int(r["ordens"] or 0),
        "valor": _num(r["valor"]),
    } for _, r in topf.iterrows()] if not topf.empty else []

    return {
        "empty": dom_val == 0 and imp_brl == 0,
        "kpis": {
            "compras_dom": dom_val,
            "compras_dom_ordens": dom_ord,
            "importacao_brl": imp_brl,
            "importacao_usd": imp_usd,
            "razao_compra_venda": razao,
            "concentracao_import": conc,
            "top_fornecedor_import": top_name,
        },
        "serie": serie,
        "import_fornecedores": import_fornecedores,
        "top_fornecedores": top_fornecedores,
    }


# ══════════════════════════════════════════════════════════════
# Aba ORÇAMENTOS
# ══════════════════════════════════════════════════════════════
def orcamentos() -> dict:
    """Pipeline e Conversão — porta fiel do Streamlit.

    `quote_date` é 100% NULL no ERP e `quote_status` é 99% NULL, então datamos por
    `created_at_erp` (TIMESTAMP) e usamos `detailed_status` (1=aberto, 2=ganho).
    Janela externa = 365 dias de criação. excluded_at IS NULL em tudo.
    """
    sql = {
        # 4a) KPIs: Pipeline Vivo (≤90d), Parados (+180d), Conversão (safra ≥90d)
        "kpi": f"""
            SELECT
              ROUND(SUM(IF(detailed_status=1 AND created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY), total_amount, 0)),2)  AS pipe,
              COUNTIF(detailed_status=1 AND created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY))                            AS pipe_n,
              ROUND(SUM(IF(detailed_status=1 AND created_at_erp<TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 180 DAY), total_amount, 0)),2) AS parado,
              COUNTIF(detailed_status=1 AND created_at_erp<TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 180 DAY))                           AS parado_n,
              ROUND(SAFE_DIVIDE(
                COUNTIF(detailed_status=2 AND created_at_erp<=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY)),
                COUNTIF(created_at_erp<=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY)))*100, 1)                                      AS conv
            FROM `{QUOTES}.fact_quote`
            WHERE excluded_at IS NULL AND created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
        """,
        # 4b) Ciclo de venda (mediana quote→nota, dias)
        "cic": f"""
            SELECT CAST(APPROX_QUANTILES(DATE_DIFF(o.invoice_date, DATE(q.created_at_erp), DAY), 2)[OFFSET(1)] AS INT64) AS ciclo
            FROM `{QUOTES}.fact_quote` q
            JOIN `{ORDERS}.fact_sales_order` o ON o.quote_number = q.quote_number
            WHERE q.created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
              AND o.invoice_date >= DATE(q.created_at_erp) AND o.invoice_date IS NOT NULL
        """,
        # 4c) Conversão por safra (mensal)
        "saf": f"""
            SELECT FORMAT_DATE('%b/%y', DATE(created_at_erp)) AS mes,
                   DATE_TRUNC(DATE(created_at_erp), MONTH)     AS ord,
                   ROUND(SAFE_DIVIDE(COUNTIF(detailed_status=2), COUNT(*))*100, 1) AS conv
            FROM `{QUOTES}.fact_quote`
            WHERE excluded_at IS NULL AND created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
            GROUP BY 1, 2 ORDER BY ord
        """,
        # 4d) Em aberto por idade
        "idade": f"""
            SELECT CASE
                WHEN created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 30 DAY)  THEN '1. até 30d (quente)'
                WHEN created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 90 DAY)  THEN '2. 31-90d'
                WHEN created_at_erp>=TIMESTAMP_SUB(CURRENT_TIMESTAMP(),INTERVAL 180 DAY) THEN '3. 91-180d'
                ELSE '4. +180d (morto)' END                  AS idade,
                ROUND(SUM(total_amount), 0)                  AS valor
            FROM `{QUOTES}.fact_quote`
            WHERE excluded_at IS NULL AND detailed_status=1
              AND created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
            GROUP BY 1 ORDER BY 1
        """,
        # 4e) Parados +180d (top 20)
        "par": f"""
            SELECT COALESCE(p.partner_name, CAST(q.partner_code AS STRING))   AS cliente,
                   DATE_DIFF(CURRENT_DATE(), DATE(q.created_at_erp), DAY)      AS dias_parado,
                   q.total_amount                                             AS valor
            FROM `{QUOTES}.fact_quote` q
            LEFT JOIN `{PARTNERS}.dim_partner` p USING (partner_code)
            WHERE q.excluded_at IS NULL AND q.detailed_status=1
              AND q.created_at_erp <  TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 180 DAY)
              AND q.created_at_erp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
            ORDER BY q.total_amount DESC LIMIT 20
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    kpi, cic, saf, idade, par = dfs["kpi"], dfs["cic"], dfs["saf"], dfs["idade"], dfs["par"]

    k = kpi.iloc[0] if not kpi.empty else None
    ciclo = int(cic.iloc[0]["ciclo"]) if not cic.empty and pd.notna(cic.iloc[0]["ciclo"]) else None

    conversao_safra = [{
        "mes": str(r["mes"]).capitalize(),
        "conv": _num(r["conv"]),
    } for _, r in saf.iterrows()] if not saf.empty else []

    aberto_idade = [{
        "idade": str(r["idade"]), "valor": _num(r["valor"]),
    } for _, r in idade.iterrows()] if not idade.empty else []

    parados = [{
        "cliente": str(r["cliente"]) if pd.notna(r["cliente"]) else "—",
        "dias_parado": int(r["dias_parado"]) if pd.notna(r["dias_parado"]) else 0,
        "valor": _num(r["valor"]),
    } for _, r in par.iterrows()] if not par.empty else []

    return {
        "empty": k is None,
        "kpis": {
            "pipeline_vivo": _num(k["pipe"]) if k is not None else 0.0,
            "pipeline_n": int(k["pipe_n"]) if k is not None and pd.notna(k["pipe_n"]) else 0,
            "parado": _num(k["parado"]) if k is not None else 0.0,
            "parado_n": int(k["parado_n"]) if k is not None and pd.notna(k["parado_n"]) else 0,
            "conversao": _num(k["conv"]) if k is not None else 0.0,
            "ciclo": ciclo,
        },
        "conversao_safra": conversao_safra,
        "aberto_idade": aberto_idade,
        "parados": parados,
    }


# ══════════════════════════════════════════════════════════════
# Aba FUNIL CRM
# ══════════════════════════════════════════════════════════════
PIPELINES = {
    "Funil Vendas Farmácia": f"{CRM}.funil_vendas_farmacia",
    "Recorrência Farmácia": f"{CRM}.recorrencia_farmacia",
    "Recorrência Distribuidores": f"{CRM}.recorrencia_distribuidores",
}


def crm_pipelines() -> list[str]:
    return list(PIPELINES.keys())


def crm(pipeline: str = "TODOS") -> dict:
    union_sql = "\n  UNION ALL\n".join([
        f"SELECT '{nome}' AS pipeline_nome, deal_id, title, value, status, "
        f"stage_id, owner_id, add_time, won_time "
        f"FROM `{tbl}` WHERE is_deleted IS NOT TRUE"
        for nome, tbl in PIPELINES.items()
    ])
    where_pip = f"WHERE pipeline_nome = '{pipeline}'" if pipeline != "TODOS" else ""
    df = query(f"""
        WITH deals AS ({union_sql})
        SELECT
          d.pipeline_nome, d.deal_id, d.title, d.value, d.status,
          s.stage_name, s.order_nr AS stage_order,
          u.name AS owner_nome,
          d.add_time, d.won_time
        FROM deals d
        LEFT JOIN `{CRM}.dim_crm_stage` s ON s.stage_id = d.stage_id
        LEFT JOIN `{CRM}.dim_crm_user`  u ON u.user_id  = d.owner_id
        {where_pip}
    """)
    if df.empty:
        return {"empty": True}
    df["value"] = pd.to_numeric(df["value"], errors="coerce").fillna(0.0)
    total = len(df)
    ganhos = df[df["status"] == "won"]
    perdidos = df[df["status"] == "lost"]
    abertos = df[df["status"] == "open"]
    taxa = len(ganhos) / total * 100 if total else 0

    # Eficiência: win rate sobre fechados, ciclo médio (add→won) e forecast ponderado.
    fechados = len(ganhos) + len(perdidos)
    win_rate_fech = len(ganhos) / fechados * 100 if fechados else 0.0
    forecast = float(abertos["value"].sum()) * (win_rate_fech / 100)
    ciclo = None
    if not ganhos.empty:
        at = pd.to_datetime(ganhos["add_time"], errors="coerce", utc=True)
        wt = pd.to_datetime(ganhos["won_time"], errors="coerce", utc=True)
        dias = (wt - at).dt.days
        dias = dias[(dias >= 0) & (dias <= 365)]
        ciclo = float(dias.mean()) if len(dias) else None

    stage = (abertos.groupby(["stage_order", "stage_name"], dropna=False)
             .agg(deals=("deal_id", "count"), valor=("value", "sum"))
             .reset_index().sort_values("stage_order"))
    stage_data = [{
        "stage_name": (str(r["stage_name"]) if pd.notna(r["stage_name"]) else "—"),
        "deals": int(r["deals"]), "valor": _num(r["valor"]),
    } for _, r in stage.iterrows()]

    owner = (df.groupby(df["owner_nome"].fillna("Sem owner"))
             .agg(deals=("deal_id", "count"), pipeline=("value", "sum"))
             .reset_index().rename(columns={"owner_nome": "vendedor"}))
    owner = owner.sort_values("pipeline", ascending=False).head(10)
    owner_data = [{
        "vendedor": str(r["vendedor"]), "deals": int(r["deals"]), "pipeline": _num(r["pipeline"]),
    } for _, r in owner.iterrows()]

    ab = abertos[["pipeline_nome", "title", "stage_name", "owner_nome", "value"]].copy()
    ab = ab.sort_values("value", ascending=False).head(30)
    deals_abertos = [{
        "pipeline": str(r["pipeline_nome"]),
        "deal": str(r["title"]) if pd.notna(r["title"]) else "—",
        "estagio": str(r["stage_name"]) if pd.notna(r["stage_name"]) else "—",
        "vendedor": str(r["owner_nome"]) if pd.notna(r["owner_nome"]) else "—",
        "valor": _num(r["value"]),
    } for _, r in ab.iterrows()]

    return {
        "empty": False,
        "kpis": {
            "total": int(total), "abertos": int(len(abertos)),
            "ganhos": int(len(ganhos)), "perdidos": int(len(perdidos)),
            "taxa_ganho": taxa,
            "pipeline_aberto": _num(abertos["value"].sum()),
            "valor_ganho": _num(ganhos["value"].sum()),
            "win_rate_fechados": win_rate_fech,
            "ciclo_medio": ciclo,
            "forecast_ponderado": forecast,
        },
        "stage_data": stage_data,
        "owner_data": owner_data,
        "deals_abertos": deals_abertos,
    }


# ══════════════════════════════════════════════════════════════
# Aba RANKING CLIENTES
# ══════════════════════════════════════════════════════════════
# Bronze fallback do Streamlit (gold_comercial.ranking_clientes NÃO existe, então
# este é o SQL que de fato roda). Mesma metodologia da Matriz RFV/Vendas: venda
# faturada (order_status 3,4), natureza financeira (financial_flag<>'N'), sem o
# site-loja 000054, janela = a do RFV (12m até o último mês fechado). Agrupa por
# NOME normalizado pra não rachar empresa com vários endereços (AIR LIQUIDE em 13
# cidades). Senão o mesmo cliente dá número diferente entre abas.
RANKING_BRONZE_SQL = f"""
WITH base AS (
    SELECT
      UPPER(TRIM(p.partner_name)) AS nome_norm,
      p.partner_name, p.city, p.state,
      o.order_number, o.product_amount
    FROM `{ORDERS}.fact_sales_order` o
    JOIN `{PARTNERS}.dim_partner` p USING (partner_code)
    JOIN `{ORDERS}.dim_operation_nature` n
      ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
    WHERE o.order_status IN (3, 4)
      AND o.channel_code <> '000054'
      AND o.invoice_date BETWEEN
          DATE_TRUNC(DATE_SUB((SELECT MAX(DATE(data_referencia))
              FROM `{SILVER_COM}.silver_com_rfv_score`), INTERVAL 1 YEAR), MONTH)
          AND (SELECT MAX(DATE(data_referencia))
              FROM `{SILVER_COM}.silver_com_rfv_score`)
)
SELECT
  ANY_VALUE(partner_name) AS cliente,
  ARRAY_AGG(city  IGNORE NULLS ORDER BY product_amount DESC LIMIT 1)[SAFE_OFFSET(0)] AS city,
  ARRAY_AGG(state IGNORE NULLS ORDER BY product_amount DESC LIMIT 1)[SAFE_OFFSET(0)] AS state,
  COUNT(DISTINCT order_number) AS qtd_pedidos,
  SUM(product_amount)   AS faturamento
FROM base
GROUP BY nome_norm
ORDER BY faturamento DESC
LIMIT 100
"""


def ranking() -> dict:
    df = query(RANKING_BRONZE_SQL)
    if df.empty:
        return {"empty": True, "rows": [], "kpis": {}}

    df = df.sort_values("faturamento", ascending=False).reset_index(drop=True)
    df["faturamento"] = pd.to_numeric(df["faturamento"], errors="coerce").fillna(0.0)
    total = float(df["faturamento"].sum())
    df["acum_pct"] = (df["faturamento"].cumsum() / total * 100) if total else 0.0

    def _classe(p):
        return "A" if p <= 80 else ("B" if p <= 95 else "C")

    df["classe"] = df["acum_pct"].apply(_classe)
    n_a = int((df["classe"] == "A").sum())
    n_top20 = max(1, int(len(df) * 0.20))
    fat_top20 = float(df.head(n_top20)["faturamento"].sum())
    pct_top20 = fat_top20 / total * 100 if total else 0.0

    rows = [{
        "posicao": i + 1,
        "cliente": str(r["cliente"]) if pd.notna(r["cliente"]) else "—",
        "city": str(r["city"]) if pd.notna(r["city"]) else "—",
        "state": str(r["state"]) if pd.notna(r["state"]) else "—",
        "qtd_pedidos": int(r["qtd_pedidos"] or 0),
        "faturamento": _num(r["faturamento"]),
        "classe": str(r["classe"]),
        "acum_pct": _num(r["acum_pct"]),
    } for i, r in df.iterrows()]

    return {
        "empty": False,
        "rows": rows,
        "kpis": {
            "top100_faturamento": total,
            "classe_a": n_a,
            "concentracao_top20": pct_top20,
        },
    }


# ══════════════════════════════════════════════════════════════
# Aba MATRIZ RFV
# ══════════════════════════════════════════════════════════════
def qa_status() -> list[dict]:
    try:
        df = query(f"""
            SELECT escopo, status, delta_total_pct
            FROM `{GOLD_COM}.gold_qa_validacao`
            WHERE metrica = 'faturamento'
              AND data_referencia = (SELECT MAX(data_referencia) FROM `{GOLD_COM}.gold_qa_validacao`)
            ORDER BY CASE escopo
                WHEN 'GERAL' THEN 1 WHEN 'HOSPITALAR' THEN 2
                WHEN 'FARMACIAS' THEN 3 WHEN 'SAC' THEN 4 ELSE 9 END
        """)
    except Exception:
        return []
    return [{
        "escopo": r["escopo"], "status": r["status"],
        "delta": _num(r["delta_total_pct"]),
    } for _, r in df.iterrows()]


def rfv_periodos() -> list[dict]:
    try:
        df = query(f"""
            SELECT DISTINCT DATE(data_referencia) AS periodo
            FROM `{SILVER_COM}.silver_com_rfv_score`
            ORDER BY 1 DESC LIMIT 13
        """)
    except Exception:
        return []
    return [{"value": str(p), "label": mes_label(p)} for p in df["periodo"].tolist()]


def rfv_carteiras(familia: str = "TODOS", periodo: str | None = None) -> list[dict]:
    """Carteiras do filtro: SÓ as A-F (CA-CF). Sem vendedor/novos (regra Gustavo 10/07).
    Farmácia e não-carteirizados aparecem só no 'Todas' / no filtro de Família."""
    fam_w = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    per_w = f"AND DATE(data_referencia) = '{periodo}'" if periodo else ""
    try:
        df = query(f"""
            SELECT DISTINCT carteira_raw FROM {SILVER_CART}
            WHERE 1=1 {fam_w} {per_w}
        """)
        vals = set(str(v) for v in df["carteira_raw"].dropna().tolist())
    except Exception:
        vals = set()
    out = [{"value": "TODOS", "label": "Todas as carteiras"}]
    for code in ["CA", "CB", "CC", "CD", "CE", "CF"]:
        if code in vals:
            out.append({"value": code,
                        "label": f"Carteira {_CART_LETRA[code]} · {_CART_FAMILIA[code]}"})
    return out


def _rfv_where(familia, carteira, periodo):
    fam_w = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    cart_w = f"AND carteira_raw = '{carteira}'" if carteira and carteira != "TODOS" else ""
    per_w = f"AND DATE(data_referencia) = '{periodo}'" if periodo else ""
    return f"WHERE 1=1 {fam_w} {cart_w} {per_w} {GIOVANNA_RESIDUO_FILTER}", fam_w, cart_w, per_w


def rfv(familia: str = "TODOS", carteira: str = "TODOS", periodo: str | None = None) -> dict:
    where, fam_w, cart_w, per_w = _rfv_where(familia, carteira, periodo)
    fam_painel = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    fam_alerta = fam_painel

    sql = {
        "df_kpi": f"""
            SELECT
                COUNT(DISTINCT partner_name) AS total_clientes,
                COUNTIF(classificacao_3 = 1) AS campeoes,
                COUNTIF(classificacao_3 = 2) AS fieis,
                COUNTIF(classificacao_3 = 3) AS fp,
                COUNTIF(classificacao_3 = 8) AS nao_pode_perder,
                COUNTIF(classificacao_3 = 10) AS hibernando,
                COUNTIF(classificacao_3 IN (9, 10)) AS em_risco,
                COUNTIF(classificacao_3 = 11) AS perdidos,
                ROUND(SUM(valor_total), 0) AS faturamento,
                MAX(data_referencia) AS data_referencia
            FROM {SILVER_CART}
            {where}
        """,
        "df_cells": f"""
            SELECT freq_bucket, rec_bucket, classificacao_2 AS segmento,
                   classificacao_3 AS seg_num,
                   COUNT(DISTINCT partner_name) AS clientes,
                   ROUND(SUM(valor_total), 2) AS faturamento
            FROM {SILVER_CART}
            {where}
            GROUP BY 1, 2, 3, 4
        """,
        "df_seg": f"""
            SELECT classificacao_3 AS seg_num,
                   ANY_VALUE(classificacao_2) AS segmento,
                   COUNT(DISTINCT partner_name) AS clientes,
                   ROUND(SUM(valor_total), 2) AS faturamento
            FROM {SILVER_CART}
            {where}
            GROUP BY 1 ORDER BY 1
        """,
        # Painel por vendedor
        "df_prfv": f"""
            SELECT
                {SP_DISPLAY} AS rfv_salesperson,
                COUNT(DISTINCT partner_name) AS qtd_clientes_carteira,
                COUNTIF(classificacao_1 = 'F1R1') AS qtd_campeoes,
                COUNTIF(classificacao_1 IN ('F1R2','F1R3','F2R1','F2R2','F2R3')) AS qtd_fieis,
                COUNTIF(classificacao_1 IN ('F3R1','F3R2','F4R1','F4R2')) AS qtd_fieis_potencial,
                COUNTIF(classificacao_1 IN ('F1R4','F1R5')) AS qtd_nao_pode_perder,
                COUNTIF(classificacao_1 IN ('F2R4','F2R5','F3R4','F3R5','F4R4')) AS qtd_em_risco_hibernando,
                COUNTIF(classificacao_1 IN ('F4R5','F5R4','F5R5')) AS qtd_perdidos,
                ROUND(SUM(valor_total), 0) AS faturamento,
                ROUND(SAFE_DIVIDE(SUM(valor_total), NULLIF(COUNT(DISTINCT partner_name), 0)), 0) AS ticket_medio
            FROM `{SILVER_COM}.silver_com_rfv_score`
            WHERE COALESCE(rfv_salesperson, 'Cliente Novo') NOT LIKE 'Eduardo%'
              AND COALESCE(rfv_salesperson, 'Cliente Novo') NOT LIKE 'Karina%'
              {fam_painel} {per_w} {GIOVANNA_RESIDUO_FILTER}
            GROUP BY 1 ORDER BY faturamento DESC
        """,
        "df_pcrm": f"""
            SELECT
                {SP_DISPLAY} AS rfv_salesperson,
                SUM(crm_deals_open) AS crm_deals_open,
                ROUND(SUM(crm_valor_pipeline), 0) AS pipeline_crm,
                SUM(alertas_oportunidade) AS alertas_oportunidade,
                SUM(alertas_churn) AS alertas_churn,
                SUM(clientes_fora_radar) AS clientes_fora_radar
            FROM `{GOLD_COM}.gold_com_vendedor_painel`
            WHERE rfv_salesperson NOT LIKE 'Eduardo%' AND rfv_salesperson NOT LIKE 'Karina%'
              {fam_painel}
              AND DATE(data_referencia) = (SELECT MAX(DATE(data_referencia)) FROM `{GOLD_COM}.gold_com_vendedor_painel`)
            GROUP BY 1
        """,
        # Alertas (dedup por nome + tipo)
        "df_al": f"""
            WITH dedup AS (
                SELECT UPPER(TRIM(partner_name)) AS nome_norm, tipo_alerta,
                       MAX(faturamento_periodo) AS faturamento_periodo
                FROM `{GOLD_COM}.gold_com_alerta_comercial`
                WHERE rfv_salesperson NOT LIKE 'Eduardo%' AND rfv_salesperson NOT LIKE 'Karina%'
                  {fam_alerta}
                GROUP BY 1, 2
            )
            SELECT tipo_alerta, COUNT(DISTINCT nome_norm) AS qtd,
                   ROUND(SUM(faturamento_periodo), 0) AS valor_total
            FROM dedup GROUP BY tipo_alerta ORDER BY qtd DESC
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    df_kpi, df_cells, df_seg = dfs["df_kpi"], dfs["df_cells"], dfs["df_seg"]
    df_prfv, df_pcrm, df_al = dfs["df_prfv"], dfs["df_pcrm"], dfs["df_al"]

    kpi = {}
    if not df_kpi.empty:
        r = df_kpi.iloc[0]
        ref = (pd.to_datetime(r["data_referencia"]).date().isoformat()
               if pd.notna(r["data_referencia"]) else None)
        # Faturamento: pra uma carteira CA-CF, usa a BASE OFICIAL (por partner_code,
        # bate o Alves no centavo). Pros demais recortes (TODOS/Farmácia/Sem carteira),
        # o SUM(valor_total) do silver (cliente único) já é a referência. Depende do
        # `ref` acima, então roda DEPOIS do bloco paralelo (não dá pra paralelizar).
        fat = _num(r["faturamento"])
        if carteira in _CART_LETRA and ref:
            fat = _carteira_faturamento(carteira, ref)
        kpi = {
            "total_clientes": int(r["total_clientes"] or 0),
            "campeoes": int(r["campeoes"] or 0),
            "fieis": int(r["fieis"] or 0),
            "fp": int(r["fp"] or 0),
            "nao_pode_perder": int(r["nao_pode_perder"] or 0),
            "em_risco": int(r["em_risco"] or 0),
            "perdidos": int(r["perdidos"] or 0),
            "faturamento": fat,
            "data_referencia": (pd.to_datetime(r["data_referencia"]).strftime("%d/%m/%Y")
                                if pd.notna(r["data_referencia"]) else None),
        }

    cells = [{
        "freq_bucket": r["freq_bucket"], "rec_bucket": r["rec_bucket"],
        "segmento": str(r["segmento"]), "seg_num": int(r["seg_num"]),
        "clientes": int(r["clientes"]), "faturamento": _num(r["faturamento"]),
    } for _, r in df_cells.iterrows()]

    segments = [{
        "seg_num": int(r["seg_num"]), "segmento": str(r["segmento"]),
        "clientes": int(r["clientes"]), "faturamento": _num(r["faturamento"]),
    } for _, r in df_seg.iterrows()]

    painel_df = df_prfv.merge(df_pcrm, on="rfv_salesperson", how="left")
    for c in ["crm_deals_open", "pipeline_crm", "alertas_oportunidade", "alertas_churn", "clientes_fora_radar"]:
        if c in painel_df.columns:
            painel_df[c] = painel_df[c].fillna(0).astype(int)
    painel = [{
        "vendedor": str(r["rfv_salesperson"]),
        "clientes": int(r["qtd_clientes_carteira"] or 0),
        "campeoes": int(r["qtd_campeoes"] or 0),
        "fieis": int(r["qtd_fieis"] or 0),
        "fieis_potencial": int(r["qtd_fieis_potencial"] or 0),
        "nao_pode_perder": int(r["qtd_nao_pode_perder"] or 0),
        "em_risco_hibernando": int(r["qtd_em_risco_hibernando"] or 0),
        "perdidos": int(r["qtd_perdidos"] or 0),
        "faturamento": _num(r["faturamento"]),
        "ticket_medio": _num(r["ticket_medio"]),
        "crm_deals": int(r.get("crm_deals_open", 0) or 0),
        "pipeline_crm": _num(r.get("pipeline_crm", 0)),
        "alertas_oportunidade": int(r.get("alertas_oportunidade", 0) or 0),
        "alertas_churn": int(r.get("alertas_churn", 0) or 0),
        "clientes_fora_radar": int(r.get("clientes_fora_radar", 0) or 0),
    } for _, r in painel_df.iterrows()]

    alertas = [{
        "tipo_alerta": r["tipo_alerta"], "qtd": int(r["qtd"]),
        "valor_total": _num(r["valor_total"]),
    } for _, r in df_al.iterrows()]

    return {"kpi": kpi, "cells": cells, "segments": segments, "painel": painel, "alertas": alertas}


def rfv_segmento(seg: int, familia="TODOS", carteira="TODOS", periodo=None) -> dict:
    _, fam_w, cart_w, per_w = _rfv_where(familia, carteira, periodo)
    df = query(f"""
        SELECT
            partner_name AS nome_cliente,
            rfv_familia AS familia,
            {SP_DISPLAY} AS vendedor,
            FORMAT_DATE('%d/%m/%Y', ultima_compra_data) AS ultima_compra,
            recencia_dias AS dias_sem_comprar,
            frequencia AS frequencia,
            ROUND(valor_total, 2) AS valor_total
        FROM {SILVER_CART}
        WHERE classificacao_3 = {int(seg)}
        {fam_w} {cart_w} {per_w} {GIOVANNA_RESIDUO_FILTER}
        ORDER BY recencia_dias DESC, valor_total DESC
    """)
    rows = [{
        "nome_cliente": str(r["nome_cliente"]) if pd.notna(r["nome_cliente"]) else "—",
        "familia": str(r["familia"]) if pd.notna(r["familia"]) else "—",
        "vendedor": str(r["vendedor"]) if pd.notna(r["vendedor"]) else "—",
        "ultima_compra": str(r["ultima_compra"]) if pd.notna(r["ultima_compra"]) else "—",
        "dias_sem_comprar": int(r["dias_sem_comprar"]) if pd.notna(r["dias_sem_comprar"]) else 0,
        "frequencia": int(r["frequencia"]) if pd.notna(r["frequencia"]) else 0,
        "valor_total": _num(r["valor_total"]),
    } for _, r in df.iterrows()]
    fat = float(df["valor_total"].sum()) if not df.empty else 0.0
    cnt = len(rows)
    return {
        "rows": rows, "qtd": cnt, "faturamento": fat,
        "ticket": fat / cnt if cnt else 0,
    }


def rfv_alerta(tipo: str, familia="TODOS") -> dict:
    fam_alerta = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    df = query(f"""
        WITH base AS (
            SELECT
                UPPER(TRIM(partner_name)) AS nome_norm,
                ANY_VALUE(partner_name) AS nome_cliente,
                COUNT(DISTINCT partner_code) AS qtd_filiais,
                STRING_AGG(DISTINCT rfv_familia, ' + ' ORDER BY rfv_familia) AS familias,
                STRING_AGG(DISTINCT {SP_DISPLAY}, ', ' ORDER BY {SP_DISPLAY}) AS vendedores,
                STRING_AGG(DISTINCT segmento_rfv, ', ' ORDER BY segmento_rfv) AS segmentos,
                MAX(faturamento_periodo) AS faturamento,
                MAX(qtd_deals_open) AS deals_abertos,
                MAX(valor_pipeline_open) AS pipeline_crm,
                MIN(dias_sem_deal_crm) AS dias_sem_deal,
                ANY_VALUE(descricao_alerta) AS descricao
            FROM `{GOLD_COM}.gold_com_alerta_comercial`
            WHERE tipo_alerta = '{tipo}'
              AND rfv_salesperson NOT LIKE 'Eduardo%' AND rfv_salesperson NOT LIKE 'Karina%'
              {fam_alerta}
            GROUP BY 1
        ),
        bridge_agg AS (
            SELECT UPPER(TRIM(partner_name)) AS nome_norm,
                   MAX(IF(org_id IS NOT NULL, 1, 0)) AS tem_crm,
                   STRING_AGG(DISTINCT org_name, ', ') AS nomes_crm
            FROM `{SILVER_COM}.param_com_entity_bridge`
            WHERE partner_name IS NOT NULL GROUP BY 1
        )
        SELECT
            b.nome_cliente, b.familias, b.qtd_filiais AS filiais, b.vendedores, b.segmentos,
            ROUND(b.faturamento, 2) AS faturamento, b.deals_abertos,
            ROUND(b.pipeline_crm, 2) AS pipeline_crm, b.dias_sem_deal,
            CASE WHEN br.tem_crm = 1 THEN 'Sim' ELSE 'Não' END AS no_crm,
            COALESCE(br.nomes_crm, '—') AS org_pipedrive, b.descricao
        FROM base b LEFT JOIN bridge_agg br USING (nome_norm)
        ORDER BY b.faturamento DESC
    """)
    rows = [{
        "cliente": str(r["nome_cliente"]) if pd.notna(r["nome_cliente"]) else "—",
        "familias": str(r["familias"]) if pd.notna(r["familias"]) else "—",
        "filiais": int(r["filiais"]) if pd.notna(r["filiais"]) else 0,
        "vendedores": str(r["vendedores"]) if pd.notna(r["vendedores"]) else "—",
        "segmentos": str(r["segmentos"]) if pd.notna(r["segmentos"]) else "—",
        "faturamento": _num(r["faturamento"]),
        "deals_abertos": int(r["deals_abertos"]) if pd.notna(r["deals_abertos"]) else 0,
        "pipeline_crm": _num(r["pipeline_crm"]),
        "dias_sem_deal": int(r["dias_sem_deal"]) if pd.notna(r["dias_sem_deal"]) else 0,
        "no_crm": str(r["no_crm"]),
        "org_pipedrive": str(r["org_pipedrive"]) if pd.notna(r["org_pipedrive"]) else "—",
        "descricao": str(r["descricao"]) if pd.notna(r["descricao"]) else "—",
    } for _, r in df.iterrows()]
    fat = float(df["faturamento"].sum()) if not df.empty else 0.0
    cnt = len(rows)
    return {"rows": rows, "qtd": cnt, "faturamento": fat, "ticket": fat / cnt if cnt else 0}
