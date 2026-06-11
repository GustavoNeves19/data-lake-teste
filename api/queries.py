"""
Camada de consultas Comercial — porta fiel do dashboard/pages/02_Comercial_e_Compras.py.

O SQL e a agregação pandas são idênticos ao Streamlit, garantindo que os números
batam ao centavo. Cada função devolve estruturas JSON-safe prontas pro React.
"""

from __future__ import annotations

import calendar
import math

import numpy as np
import pandas as pd

from .bq import query, PROJECT_PROD

PROJ = PROJECT_PROD
ORDERS = f"{PROJ}.dm_orders"
QUOTES = f"{PROJ}.dm_quotes"
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


def vendas(mes: str) -> dict:
    """Dashboard de Liderança para o mês `mes` (YYYY-MM-DD, 1º dia do mês)."""
    mes_ref = pd.Timestamp(mes).date()
    mes_ant = (pd.Timestamp(mes_ref) - pd.offsets.MonthBegin(1)).date()
    mes_ano_ant = pd.Timestamp(mes_ref).replace(year=mes_ref.year - 1).date()

    df = query(f"""
      SELECT
        {CANAL_CASE} AS canal,
        DATE_TRUNC(o.invoice_date, MONTH) AS mes,
        o.order_number, o.invoice_date, o.product_amount
      FROM `{ORDERS}.fact_sales_order` o
      JOIN `{ORDERS}.dim_operation_nature` n
        ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'
      WHERE DATE_TRUNC(o.invoice_date, MONTH) IN (
            DATE('{mes_ref}'), DATE('{mes_ant}'), DATE('{mes_ano_ant}'))
        AND o.invoice_date IS NOT NULL
    """)

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

    fat_mes = float(df_mes["product_amount"].sum())
    fat_ant = float(df_ant["product_amount"].sum())
    fat_yoy = float(df_yoy["product_amount"].sum())
    trans_mes = int(len(df_mes))
    ticket = fat_mes / trans_mes if trans_mes else 0

    out["empty"] = False
    out["kpis"] = {
        "faturamento": fat_mes, "fat_ant": fat_ant, "fat_yoy": fat_yoy,
        "var_mom": _safe_pct(fat_mes, fat_ant), "var_yoy": _safe_pct(fat_mes, fat_yoy),
        "ticket": ticket, "transacoes": trans_mes,
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

    # Evolução mensal por canal — últimos 12 meses
    mes_inicio = (pd.Timestamp(mes_ref) - pd.offsets.MonthBegin(11)).date()
    mes_fim = (pd.Timestamp(mes_ref) + pd.offsets.MonthEnd(0)).date()
    df_evol = query(f"""
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
    """)
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


# ══════════════════════════════════════════════════════════════
# Aba COMPRAS
# ══════════════════════════════════════════════════════════════
def compras() -> dict:
    df = query(f"""
        SELECT
          DATE_TRUNC(order_date, MONTH) AS mes,
          COUNT(*) AS qtd_pedidos,
          SUM(total_amount) AS valor_compras
        FROM `{ORDERS}.fact_purchase_order`
        WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
          AND order_date IS NOT NULL
        GROUP BY 1 ORDER BY 1
    """)
    if df.empty:
        return {"empty": True, "total": 0, "qtd": 0, "serie": []}
    df["mes"] = pd.to_datetime(df["mes"])
    serie = [{
        "mes": r["mes"].strftime("%Y-%m-%d"),
        "mes_label": f"{_MES_PT[r['mes'].month][:3]}/{str(r['mes'].year)[2:]}",
        "valor_compras": _num(r["valor_compras"]),
        "qtd_pedidos": int(r["qtd_pedidos"]),
    } for _, r in df.iterrows()]
    return {
        "empty": False,
        "total": _num(df["valor_compras"].sum()),
        "qtd": int(df["qtd_pedidos"].sum()),
        "serie": serie,
    }


# ══════════════════════════════════════════════════════════════
# Aba ORÇAMENTOS
# ══════════════════════════════════════════════════════════════
def orcamentos() -> dict:
    # A coluna de status no ERP é `quote_status` (o SQL legado do Streamlit usava
    # `status`, que não existe em fact_quote — por isso a aba quebrava lá).
    df = query(f"""
        SELECT
          DATE_TRUNC(quote_date, MONTH) AS mes,
          COALESCE(quote_status, '—') AS status,
          COUNT(*) AS qtd,
          SUM(total_amount) AS valor
        FROM `{QUOTES}.fact_quote`
        WHERE quote_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
          AND quote_date IS NOT NULL
        GROUP BY 1, 2 ORDER BY 1
    """)
    if df.empty:
        return {"empty": True, "total": 0, "qtd": 0, "serie": [], "status_list": []}
    df["mes"] = pd.to_datetime(df["mes"])
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)
    df["status"] = df["status"].fillna("—").astype(str)
    status_list = sorted(df["status"].unique().tolist())
    piv = df.pivot_table(index="mes", columns="status", values="valor",
                         aggfunc="sum", fill_value=0).reset_index().sort_values("mes")
    serie = []
    for _, r in piv.iterrows():
        row = {"mes_label": f"{_MES_PT[r['mes'].month][:3]}/{str(r['mes'].year)[2:]}"}
        for s in status_list:
            row[s] = _num(r[s]) if s in piv.columns else 0
        serie.append(row)
    return {
        "empty": False,
        "total": _num(df["valor"].sum()),
        "qtd": int(df["qtd"].sum()),
        "status_list": status_list,
        "serie": serie,
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
        f"stage_id, owner_id, local_close_date, local_won_date, local_lost_date "
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
          d.local_close_date, d.local_won_date, d.local_lost_date
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
        },
        "stage_data": stage_data,
        "owner_data": owner_data,
        "deals_abertos": deals_abertos,
    }


# ══════════════════════════════════════════════════════════════
# Aba RANKING CLIENTES
# ══════════════════════════════════════════════════════════════
def ranking() -> dict:
    df = query(f"""
        SELECT
          p.partner_name AS cliente, p.city, p.state,
          COUNT(o.order_number) AS qtd_pedidos,
          SUM(o.total_amount) AS faturamento
        FROM `{ORDERS}.fact_sales_order` o
        JOIN `{PROJ}.dm_partners.dim_partner` p USING (partner_code)
        WHERE o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
          AND o.order_date IS NOT NULL
        GROUP BY 1, 2, 3
        ORDER BY 5 DESC
        LIMIT 100
    """)
    if df.empty:
        return {"empty": True, "rows": []}
    rows = [{
        "cliente": str(r["cliente"]) if pd.notna(r["cliente"]) else "—",
        "city": str(r["city"]) if pd.notna(r["city"]) else "—",
        "state": str(r["state"]) if pd.notna(r["state"]) else "—",
        "qtd_pedidos": int(r["qtd_pedidos"] or 0),
        "faturamento": _num(r["faturamento"]),
    } for _, r in df.iterrows()]
    return {"empty": False, "rows": rows}


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


def rfv_vendedores(familia: str = "TODOS", periodo: str | None = None) -> list[str]:
    fam_w = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    per_w = f"AND DATE(data_referencia) = '{periodo}'" if periodo else ""
    try:
        df = query(f"""
            SELECT DISTINCT {SP_DISPLAY} AS vendedor
            FROM `{SILVER_COM}.silver_com_rfv_score`
            WHERE 1=1 {fam_w} {per_w} {GIOVANNA_RESIDUO_FILTER}
            ORDER BY 1
        """)
        return ["TODOS"] + df["vendedor"].dropna().astype(str).tolist()
    except Exception:
        return ["TODOS"]


def _rfv_where(familia, vendedor, periodo):
    fam_w = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    vend_w = f"AND {SP_DISPLAY} = '{vendedor}'" if vendedor and vendedor != "TODOS" else ""
    per_w = f"AND DATE(data_referencia) = '{periodo}'" if periodo else ""
    return f"WHERE 1=1 {fam_w} {vend_w} {per_w} {GIOVANNA_RESIDUO_FILTER}", fam_w, vend_w, per_w


def rfv(familia: str = "TODOS", vendedor: str = "TODOS", periodo: str | None = None) -> dict:
    where, fam_w, vend_w, per_w = _rfv_where(familia, vendedor, periodo)

    df_kpi = query(f"""
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
        FROM `{SILVER_COM}.silver_com_rfv_score`
        {where}
    """)
    kpi = {}
    if not df_kpi.empty:
        r = df_kpi.iloc[0]
        kpi = {
            "total_clientes": int(r["total_clientes"] or 0),
            "campeoes": int(r["campeoes"] or 0),
            "fieis": int(r["fieis"] or 0),
            "fp": int(r["fp"] or 0),
            "nao_pode_perder": int(r["nao_pode_perder"] or 0),
            "em_risco": int(r["em_risco"] or 0),
            "perdidos": int(r["perdidos"] or 0),
            "faturamento": _num(r["faturamento"]),
            "data_referencia": (pd.to_datetime(r["data_referencia"]).strftime("%d/%m/%Y")
                                if pd.notna(r["data_referencia"]) else None),
        }

    df_cells = query(f"""
        SELECT freq_bucket, rec_bucket, classificacao_2 AS segmento,
               classificacao_3 AS seg_num,
               COUNT(DISTINCT partner_name) AS clientes,
               ROUND(SUM(valor_total), 2) AS faturamento
        FROM `{SILVER_COM}.silver_com_rfv_score`
        {where}
        GROUP BY 1, 2, 3, 4
    """)
    cells = [{
        "freq_bucket": r["freq_bucket"], "rec_bucket": r["rec_bucket"],
        "segmento": str(r["segmento"]), "seg_num": int(r["seg_num"]),
        "clientes": int(r["clientes"]), "faturamento": _num(r["faturamento"]),
    } for _, r in df_cells.iterrows()]

    df_seg = query(f"""
        SELECT classificacao_3 AS seg_num,
               ANY_VALUE(classificacao_2) AS segmento,
               COUNT(DISTINCT partner_name) AS clientes,
               ROUND(SUM(valor_total), 2) AS faturamento
        FROM `{SILVER_COM}.silver_com_rfv_score`
        {where}
        GROUP BY 1 ORDER BY 1
    """)
    segments = [{
        "seg_num": int(r["seg_num"]), "segmento": str(r["segmento"]),
        "clientes": int(r["clientes"]), "faturamento": _num(r["faturamento"]),
    } for _, r in df_seg.iterrows()]

    # Painel por vendedor
    fam_painel = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    df_prfv = query(f"""
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
    """)
    df_pcrm = query(f"""
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
    """)
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

    # Alertas (dedup por nome + tipo)
    fam_alerta = f"AND rfv_familia = '{familia}'" if familia != "TODOS" else ""
    df_al = query(f"""
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
    """)
    alertas = [{
        "tipo_alerta": r["tipo_alerta"], "qtd": int(r["qtd"]),
        "valor_total": _num(r["valor_total"]),
    } for _, r in df_al.iterrows()]

    return {"kpi": kpi, "cells": cells, "segments": segments, "painel": painel, "alertas": alertas}


def rfv_segmento(seg: int, familia="TODOS", vendedor="TODOS", periodo=None) -> dict:
    where, fam_w, vend_w, per_w = _rfv_where(familia, vendedor, periodo)
    df = query(f"""
        SELECT
            partner_name AS nome_cliente,
            rfv_familia AS familia,
            {SP_DISPLAY} AS vendedor,
            FORMAT_DATE('%d/%m/%Y', ultima_compra_data) AS ultima_compra,
            recencia_dias AS dias_sem_comprar,
            frequencia AS frequencia,
            ROUND(valor_total, 2) AS valor_total
        FROM `{SILVER_COM}.silver_com_rfv_score`
        WHERE classificacao_3 = {int(seg)}
        {fam_w} {vend_w} {per_w} {GIOVANNA_RESIDUO_FILTER}
        ORDER BY valor_total DESC
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
