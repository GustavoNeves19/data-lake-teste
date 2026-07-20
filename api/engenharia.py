"""
Setor Engenharia e P&D.

Sem camada gold; fonte real = dm_products (catálogo de SKUs, BOM multi-nível,
seriais). Correções vs a view Streamlit (que tinha bugs de coluna): rótulo por
item_name (item_description é lixo '<Not implemented>'); família indisponível
(family_code 100% nulo na origem) então mix por grupo; filtra excluded_at IS NULL
(a view não filtrava). Roadmap P&D é placeholder (Miro/ClickUp não modelados).
"""

from __future__ import annotations

import math
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .bq import query, PROJECT_PROD

PROJ = PROJECT_PROD
ITEMS = f"{PROJ}.dm_products"

LINK_LABEL = {"M": "Matéria-prima", "A": "Acessório"}


def _num(v, d=0.0) -> float:
    try:
        f = float(v)
        return d if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return d


def _code(v: str | None) -> str:
    """Sanitiza um código de item (só alfanumérico) contra injeção."""
    return re.sub(r"[^A-Za-z0-9]", "", v or "")


def _like(v: str | None) -> str:
    """Sanitiza um termo de busca para LIKE (remove aspas/;/backtick)."""
    return re.sub(r"['`;\\]", "", (v or "")).strip()


# ── Catálogo ───────────────────────────────────────────────────
def catalogo() -> dict:
    sql = {
        "kpi": f"""
            SELECT COUNT(*) AS total_skus,
                   COUNTIF(i.is_active) AS ativos,
                   COUNT(DISTINCT g.group_name) AS grupos
            FROM `{ITEMS}.dim_item` i
            LEFT JOIN `{ITEMS}.dim_group` g ON g.group_code = i.group_code
            WHERE i.excluded_at IS NULL
        """,
        "mix": f"""
            SELECT COALESCE(g.group_name, 'Sem Grupo') AS group_name, COUNT(*) AS qtd
            FROM `{ITEMS}.dim_item` i
            LEFT JOIN `{ITEMS}.dim_group` g ON g.group_code = i.group_code
            WHERE i.excluded_at IS NULL
            GROUP BY group_name ORDER BY qtd DESC LIMIT 10
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    kpi, mix = dfs["kpi"], dfs["mix"]
    k = kpi.iloc[0] if not kpi.empty else None
    mix_grupo = [{"group_name": str(r["group_name"]), "qtd": int(r["qtd"])} for _, r in mix.iterrows()] if not mix.empty else []
    return {
        "kpis": {
            "total_skus": int(k["total_skus"]) if k is not None else 0,
            "ativos": int(k["ativos"]) if k is not None else 0,
            "familias": None,  # family_code 100% nulo na origem
            "grupos": int(k["grupos"]) if k is not None else 0,
        },
        "mix_grupo": mix_grupo,
        "familias_disponivel": False,
        "avisos": [
            "family_code não populado no ETL; ranking por família indisponível.",
            "group_code cobre ~27% do catálogo (resto cai em 'Sem Grupo').",
        ],
    }


def catalogo_itens(q: str | None = None, page: int = 1, page_size: int = 50) -> dict:
    q_safe = _like(q)
    try:
        page = max(1, int(page))
        page_size = min(200, max(1, int(page_size)))
    except (TypeError, ValueError):
        page, page_size = 1, 50
    offset = (page - 1) * page_size
    where_q = ""
    if q_safe:
        where_q = (f"AND (LOWER(i.item_code) LIKE LOWER('%{q_safe}%') "
                   f"OR LOWER(i.item_name) LIKE LOWER('%{q_safe}%'))")

    sql = {
        "tot": f"""
            SELECT COUNT(*) AS n FROM `{ITEMS}.dim_item` i
            WHERE i.excluded_at IS NULL {where_q}
        """,
        "df": f"""
            SELECT i.item_code, i.item_name, g.group_name, i.unit_code,
                   i.net_weight, i.gross_weight, i.is_active
            FROM `{ITEMS}.dim_item` i
            LEFT JOIN `{ITEMS}.dim_group` g ON g.group_code = i.group_code
            WHERE i.excluded_at IS NULL {where_q}
            ORDER BY i.item_code LIMIT {page_size} OFFSET {offset}
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    tot, df = dfs["tot"], dfs["df"]
    total = int(tot.iloc[0]["n"]) if not tot.empty else 0
    itens = [{
        "item_code": str(r["item_code"]),
        "item_name": str(r["item_name"]) if pd.notna(r["item_name"]) else "—",
        "group_name": str(r["group_name"]) if pd.notna(r["group_name"]) else "Sem Grupo",
        "unit_code": (int(r["unit_code"]) if pd.notna(r["unit_code"]) else None),
        "net_weight": _num(r["net_weight"]), "gross_weight": _num(r["gross_weight"]),
        "is_active": bool(r["is_active"]) if pd.notna(r["is_active"]) else False,
    } for _, r in df.iterrows()] if not df.empty else []
    return {"total": total, "page": page, "page_size": page_size, "itens": itens}


# ── BOM ────────────────────────────────────────────────────────
def bom(item_code: str | None = None) -> dict:
    ic = _code(item_code)
    where_ic = f"AND b.parent_item_code = '{ic}'" if ic else ""
    sql = {
        "kpi": f"""
            SELECT COUNT(DISTINCT parent_item_code) AS produtos_com_bom, COUNT(*) AS relacoes_bom
            FROM `{ITEMS}.bridge_item_bom` WHERE excluded_at IS NULL
        """,
        "prods": f"""
            SELECT DISTINCT parent_item_code FROM `{ITEMS}.bridge_item_bom`
            WHERE excluded_at IS NULL ORDER BY 1 LIMIT 500
        """,
        "df": f"""
            SELECT b.parent_item_code, pi.item_name AS produto_pai,
                   b.child_item_code, ci.item_name AS componente, b.quantity, b.link_type
            FROM `{ITEMS}.bridge_item_bom` b
            LEFT JOIN `{ITEMS}.dim_item` pi ON pi.item_code = b.parent_item_code
            LEFT JOIN `{ITEMS}.dim_item` ci ON ci.item_code = b.child_item_code
            WHERE b.excluded_at IS NULL {where_ic}
            ORDER BY b.parent_item_code, b.child_item_code LIMIT 2000
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    kpi, prods, df = dfs["kpi"], dfs["prods"], dfs["df"]
    k = kpi.iloc[0] if not kpi.empty else None
    produtos = prods["parent_item_code"].astype(str).tolist() if not prods.empty else []
    linhas = [{
        "parent_item_code": str(r["parent_item_code"]),
        "produto_pai": str(r["produto_pai"]) if pd.notna(r["produto_pai"]) else "—",
        "child_item_code": str(r["child_item_code"]),
        "componente": str(r["componente"]) if pd.notna(r["componente"]) else "—",
        "quantity": _num(r["quantity"]),
        "link_type": str(r["link_type"]) if pd.notna(r["link_type"]) else "M",
        "link_label": LINK_LABEL.get(str(r["link_type"]) if pd.notna(r["link_type"]) else "M", "—"),
    } for _, r in df.iterrows()] if not df.empty else []

    return {
        "kpis": {"produtos_com_bom": int(k["produtos_com_bom"]) if k is not None else 0,
                 "relacoes_bom": int(k["relacoes_bom"]) if k is not None else 0},
        "produtos": produtos, "linhas": linhas,
    }


def bom_explosao(item_code: str) -> dict:
    ic = _code(item_code)
    if not ic:
        return {"item_code": None, "niveis": []}
    df = query(f"""
        WITH RECURSIVE tree AS (
          SELECT parent_item_code, child_item_code, quantity, 1 AS nivel,
                 CAST(child_item_code AS STRING) AS path
          FROM `{ITEMS}.bridge_item_bom`
          WHERE excluded_at IS NULL AND parent_item_code = '{ic}'
          UNION ALL
          SELECT b.parent_item_code, b.child_item_code, t.quantity * b.quantity, t.nivel + 1,
                 CONCAT(t.path, ' > ', b.child_item_code)
          FROM tree t
          JOIN `{ITEMS}.bridge_item_bom` b
            ON b.parent_item_code = t.child_item_code AND b.excluded_at IS NULL
          WHERE t.nivel < 10
        )
        SELECT t.nivel, t.child_item_code, ci.item_name AS componente, t.quantity, t.path
        FROM tree t
        LEFT JOIN `{ITEMS}.dim_item` ci ON ci.item_code = t.child_item_code
        ORDER BY t.path LIMIT 2000
    """)
    niveis = [{
        "nivel": int(r["nivel"]), "child_item_code": str(r["child_item_code"]),
        "componente": str(r["componente"]) if pd.notna(r["componente"]) else "—",
        "quantity": _num(r["quantity"]), "path": str(r["path"]),
    } for _, r in df.iterrows()] if not df.empty else []
    return {"item_code": ic, "niveis": niveis}


# ── Seriais ────────────────────────────────────────────────────
def seriais(item_code: str | None = None) -> dict:
    ic = _code(item_code)
    where_ic = f"AND s.item_code = '{ic}'" if ic else ""
    df = query(f"""
        SELECT s.item_code, it.item_name,
               COUNT(*) AS total_seriais,
               COUNTIF(s.is_in_use = 'X') AS em_uso,
               COUNT(DISTINCT s.batch_number) AS lotes
        FROM `{ITEMS}.fact_serial_number` s
        LEFT JOIN `{ITEMS}.dim_item` it ON it.item_code = s.item_code
        WHERE s.excluded_at IS NULL {where_ic}
        GROUP BY s.item_code, it.item_name
        ORDER BY total_seriais DESC LIMIT 100
    """)
    itens = [{
        "item_code": str(r["item_code"]),
        "item_name": str(r["item_name"]) if pd.notna(r["item_name"]) else "—",
        "total_seriais": int(r["total_seriais"]), "em_uso": int(r["em_uso"] or 0),
        "lotes": int(r["lotes"] or 0),
    } for _, r in df.iterrows()] if not df.empty else []
    return {"itens": itens}


# ── Roadmap P&D (placeholder) ──────────────────────────────────
def roadmap() -> dict:
    return {
        "status": "placeholder",
        "titulo": "Integração Miro + ClickUp pendente",
        "mensagem": ("Fluxogramas de P&D no Miro e tarefas no ClickUp serão integrados "
                     "nesta visão quando modelados por fase e lead-time."),
        "kpis_planejados": [
            "Produtos em desenvolvimento (ClickUp, status por fase)",
            "Lead time médio de desenvolvimento (ideia até produção)",
            "Fichas técnicas homologadas vs pendentes",
            "Alterações de BOM por período",
            "Produtos com serial ativo vs descontinuados",
        ],
        "fontes_a_integrar": ["Miro", "ClickUp"],
    }
