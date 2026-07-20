"""
Setor Operacional e Produção.

gold_operacional não existe e a view Streamlit foi escrita contra um schema
imaginado (4 de 5 queries quebravam). Este é um port + correção de fonte (como o
SAC): SQL reescrito contra o schema real, validado por dry-run. Rótulos usam
item_name (item_description é 94% nulo); estoque usa group_name (família tem
family_code nulo na origem) e general_balance (available_balance é 100% nulo).
Tudo filtra excluded_at IS NULL.
"""

from __future__ import annotations

import math
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .bq import query, PROJECT_PROD

PROJ = PROJECT_PROD
PROD = f"{PROJ}.dm_production"
INV = f"{PROJ}.dm_inventory"
ITEMS = f"{PROJ}.dm_products"

STATUS_LABEL = {1: "Aberta", 2: "Em produção", 5: "Concluída", 8: "Cancelada"}


def _num(v, d=0.0) -> float:
    try:
        f = float(v)
        return d if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return d


def _mes(v) -> str:
    return pd.Timestamp(v).strftime("%Y-%m")


# ── Produção (OPs) ─────────────────────────────────────────────
def producao() -> dict:
    sql = {
        "pp": f"""
            SELECT DATE_TRUNC(o.order_date, MONTH) AS mes,
                   COUNT(DISTINCT o.prod_order_number) AS qtd_op,
                   SUM(pi.planned_qty) AS qtd_planejada,
                   SUM(pi.actual_qty)  AS qtd_produzida
            FROM `{PROD}.fact_production_order` o
            LEFT JOIN `{PROD}.fact_production_item` pi USING (prod_order_number)
            WHERE o.excluded_at IS NULL AND o.order_date IS NOT NULL
              AND o.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH)
            GROUP BY 1 ORDER BY 1
        """,
        "st": f"""
            SELECT o.prod_status, COUNT(*) AS qtd_op
            FROM `{PROD}.fact_production_order` o
            WHERE o.excluded_at IS NULL
            GROUP BY 1 ORDER BY 2 DESC
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    pp, st = dfs["pp"], dfs["st"]
    planejado_produzido = [{
        "mes": _mes(r["mes"]), "qtd_op": int(r["qtd_op"] or 0),
        "qtd_planejada": _num(r["qtd_planejada"]), "qtd_produzida": _num(r["qtd_produzida"]),
    } for _, r in pp.iterrows()] if not pp.empty else []

    por_status = [{
        "prod_status": int(r["prod_status"]) if pd.notna(r["prod_status"]) else -1,
        "status_label": STATUS_LABEL.get(int(r["prod_status"]) if pd.notna(r["prod_status"]) else -1,
                                         f"Status {int(r['prod_status']) if pd.notna(r['prod_status']) else '?'}"),
        "qtd_op": int(r["qtd_op"]),
    } for _, r in st.iterrows()] if not st.empty else []

    total_ops = sum(s["qtd_op"] for s in por_status)
    planejada = sum(p["qtd_planejada"] for p in planejado_produzido)
    produzida = sum(p["qtd_produzida"] for p in planejado_produzido)
    efic = produzida / planejada * 100 if planejada else 0.0
    return {
        "camada": "bronze", "empty": total_ops == 0,
        "kpis": {"total_ops": total_ops, "qtd_planejada": planejada,
                 "qtd_produzida": produzida, "eficiencia_global": efic},
        "planejado_produzido": planejado_produzido, "por_status": por_status,
    }


# ── Componentes consumidos ─────────────────────────────────────
def componentes() -> dict:
    df = query(f"""
        SELECT c.item_code, i.item_name AS item_nome,
               SUM(c.actual_qty) AS consumido, SUM(c.planned_qty) AS planejado
        FROM `{PROD}.fact_production_comp_item` c
        LEFT JOIN `{ITEMS}.dim_item` i USING (item_code)
        WHERE c.excluded_at IS NULL
        GROUP BY 1, 2 ORDER BY consumido DESC LIMIT 20
    """)
    itens = [{
        "item_code": str(r["item_code"]),
        "item_nome": str(r["item_nome"]) if pd.notna(r["item_nome"]) else "—",
        "consumido": _num(r["consumido"]), "planejado": _num(r["planejado"]),
    } for _, r in df.iterrows()] if not df.empty else []
    return {"camada": "bronze", "empty": not itens, "componentes": itens}


# ── Estoque (snapshot) ─────────────────────────────────────────
def estoque() -> dict:
    sql = {
        "itens_df": f"""
            SELECT s.item_code, i.item_name AS item_nome, g.group_name, s.general_balance AS saldo
            FROM `{INV}.snapshot_inventory_balance` s
            LEFT JOIN `{ITEMS}.dim_item`  i USING (item_code)
            LEFT JOIN `{ITEMS}.dim_group` g ON g.group_code = i.group_code
            WHERE s.excluded_at IS NULL AND s.general_balance > 0
            ORDER BY s.general_balance DESC LIMIT 300
        """,
        "agg": f"""
            SELECT COALESCE(g.group_name, 'Sem grupo') AS group_name,
                   SUM(s.general_balance) AS saldo, COUNT(*) AS itens
            FROM `{INV}.snapshot_inventory_balance` s
            LEFT JOIN `{ITEMS}.dim_item`  i USING (item_code)
            LEFT JOIN `{ITEMS}.dim_group` g ON g.group_code = i.group_code
            WHERE s.excluded_at IS NULL AND s.general_balance > 0
            GROUP BY 1 ORDER BY saldo DESC
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    itens_df, agg = dfs["itens_df"], dfs["agg"]
    itens = [{
        "item_code": str(r["item_code"]),
        "item_nome": str(r["item_nome"]) if pd.notna(r["item_nome"]) else "—",
        "group_name": str(r["group_name"]) if pd.notna(r["group_name"]) else "Sem grupo",
        "saldo": _num(r["saldo"]),
    } for _, r in itens_df.iterrows()] if not itens_df.empty else []

    por_grupo, total, n_itens = [], 0.0, 0
    if not agg.empty:
        por_grupo = [{"group_name": str(r["group_name"]), "saldo": _num(r["saldo"])} for _, r in agg.iterrows()]
        total = float(agg["saldo"].sum())
        n_itens = int(agg["itens"].sum())
    return {
        "camada": "bronze", "empty": n_itens == 0,
        "kpis": {"itens": n_itens, "total_qtd": total, "grupos": len(por_grupo)},
        "itens": itens, "por_grupo": por_grupo,
    }


# ── Movimentação de estoque ────────────────────────────────────
def movimentacao() -> dict:
    df = query(f"""
        SELECT DATE_TRUNC(m.movement_date, MONTH) AS mes,
               SUM(IF(m.operation_type = 'E', m.quantity, 0)) AS entradas,
               SUM(IF(m.operation_type = 'S', m.quantity, 0)) AS saidas
        FROM `{INV}.fact_inventory_movement` m
        WHERE m.excluded_at IS NULL AND m.movement_date IS NOT NULL
          AND m.movement_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 13 MONTH) AND CURRENT_DATE()
        GROUP BY 1 ORDER BY 1
    """)
    series = [{"mes": _mes(r["mes"]), "entradas": _num(r["entradas"]), "saidas": _num(r["saidas"])}
              for _, r in df.iterrows()] if not df.empty else []
    return {"camada": "bronze", "empty": not series, "series": series}


# ── BOM (estrutura de material) ────────────────────────────────
def bom(parent: str | None = None) -> dict:
    # `parent` vem de um selectbox; sanitiza (só código alfanumérico) contra injeção.
    parent_w = ""
    if parent:
        p = re.sub(r"[^A-Za-z0-9]", "", parent)
        if p:
            parent_w = f"AND b.parent_item_code = '{p}'"

    sql = {
        "df": f"""
            SELECT b.parent_item_code, pai.item_name AS produto_pai,
                   b.child_item_code, filho.item_name AS componente, b.quantity
            FROM `{ITEMS}.bridge_item_bom` b
            LEFT JOIN `{ITEMS}.dim_item` pai   ON pai.item_code   = b.parent_item_code
            LEFT JOIN `{ITEMS}.dim_item` filho ON filho.item_code = b.child_item_code
            WHERE b.excluded_at IS NULL AND b.link_type = 'M' {parent_w}
            ORDER BY b.parent_item_code LIMIT 2000
        """,
        "produtos": f"""
            SELECT DISTINCT b.parent_item_code
            FROM `{ITEMS}.bridge_item_bom` b
            WHERE b.excluded_at IS NULL AND b.link_type = 'M'
            ORDER BY 1 LIMIT 500
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    df, produtos = dfs["df"], dfs["produtos"]
    linhas = [{
        "parent_item_code": str(r["parent_item_code"]),
        "produto_pai": str(r["produto_pai"]) if pd.notna(r["produto_pai"]) else "—",
        "child_item_code": str(r["child_item_code"]),
        "componente": str(r["componente"]) if pd.notna(r["componente"]) else "—",
        "quantity": _num(r["quantity"]),
    } for _, r in df.iterrows()] if not df.empty else []

    lista_pais = produtos["parent_item_code"].astype(str).tolist() if not produtos.empty else []

    return {
        "camada": "bronze", "empty": not linhas,
        "kpis": {"produtos_com_bom": len(lista_pais), "relacoes": len(linhas)},
        "linhas": linhas, "produtos_pai": lista_pais,
    }
