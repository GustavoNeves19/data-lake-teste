"""
Visão Geral — Monitor de Cargas do Data Lake (porta de dashboard/views/visao_geral.py).

Painel de OPERAÇÃO: até quando cada fonte está fresca, a cadência programada de
carga e o histórico das execuções. Frescor vem da Metadata API do BigQuery
(get_table().modified, custo zero, não escaneia bytes); o histórico vem de
ops.ingestion_runs. BRT = offset fixo -3h (São Paulo sem DST).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import pandas as pd

from .bq import get_client, query, PROJECT_PROD

PROJECT = PROJECT_PROD

# (rótulo, table_id, threshold saudável em minutos)
FONTES = [
    ("ERP · Vendas e pedidos", f"{PROJECT}.dm_orders.fact_sales_order", 240),
    ("CRM · Pipedrive", f"{PROJECT}.crm_raw.activities", 90),
    ("Silver · RFV", f"{PROJECT}.silver_comercial.silver_com_rfv_score", 360),
    ("Gold · Cliente 360", f"{PROJECT}.gold_comercial.gold_com_cliente_360", 360),
    ("ERP · Clientes", f"{PROJECT}.dm_partners.dim_partner", 1440),
    ("ERP · Produtos / SKUs", f"{PROJECT}.dm_products.dim_item", 1440),
]

HEADER_SOURCES = ["ERP (SQL Server)", "CRM (Pipedrive)", "GoTo Connect",
                  "Umbler", "Gmail", "Miro", "ClickUp"]


def _idade_txt(mins: int) -> str:
    if mins < 60:
        return f"há {mins} min"
    h, m = divmod(mins, 60)
    if h < 24:
        return f"há {h}h{m:02d}"
    d, h = divmod(h, 24)
    return f"há {d}d{h:02d}h"


def _estado_cor(mins: int, thr: int):
    if mins <= thr:
        return "verde", "#10B981"
    if mins <= thr * 2:
        return "ambar", "#D97706"
    return "vermelho", "#DC2626"


def _proxima(agora_brt: datetime):
    erp_times = [(6, 20), (9, 20), (12, 20), (15, 20), (17, 20)]
    nxt = None
    for h, m in erp_times:
        t = agora_brt.replace(hour=h, minute=m, second=0, microsecond=0)
        if t > agora_brt:
            nxt = t
            break
    if nxt is None:
        nxt = (agora_brt + timedelta(days=1)).replace(hour=6, minute=20, second=0, microsecond=0)
    if agora_brt.minute < 20:
        crm = agora_brt.replace(minute=20, second=0, microsecond=0)
    else:
        crm = (agora_brt + timedelta(hours=1)).replace(minute=20, second=0, microsecond=0)
    return nxt.strftime("%H:%M"), crm.strftime("%H:%M")


def _frescor_uma_fonte(cl, now_utc, rotulo: str, tid: str, thr: int) -> dict:
    try:
        m = cl.get_table(tid).modified
    except Exception:
        m = None
    if m is None:
        return {
            "rotulo": rotulo, "table_id": tid, "modified_utc": None,
            "modified_brt": "—", "idade_min": None, "idade_txt": "sem leitura",
            "threshold_min": thr, "estado": "sem_leitura", "cor": "#C9C9D4",
        }
    mins = int((now_utc - m).total_seconds() // 60)
    brt = (m - timedelta(hours=3)).strftime("%d/%m · %H:%M")
    estado, cor = _estado_cor(mins, thr)
    return {
        "rotulo": rotulo, "table_id": tid, "modified_utc": m.isoformat(),
        "modified_brt": brt, "idade_min": mins, "idade_txt": _idade_txt(mins),
        "threshold_min": thr, "estado": estado, "cor": cor,
    }


def visao_geral() -> dict:
    now_utc = datetime.now(timezone.utc)
    cl = get_client()

    # Bloco B — frescor via metadata (get_table().modified), custo zero. 6 chamadas
    # independentes (uma tabela cada) -> dispara todas juntas, preserva a ordem de FONTES.
    with ThreadPoolExecutor(max_workers=len(FONTES)) as ex:
        futures = [ex.submit(_frescor_uma_fonte, cl, now_utc, rotulo, tid, thr)
                   for rotulo, tid, thr in FONTES]
        frescor = [f.result() for f in futures]

    # Bloco C — cadência programada.
    agora_brt = now_utc - timedelta(hours=3)
    prox_erp, prox_crm = _proxima(agora_brt)
    cadencia = {
        "cards": [
            {"titulo": "Sincronização do ERP", "valor": "5× ao dia",
             "sub": "06:20 · 09:20 · 12:20 · 15:20 · 17:20 BRT"},
            {"titulo": "CRM (Pipedrive)", "valor": "De hora em hora",
             "sub": "nas horas comerciais (:20)"},
            {"titulo": "Carga completa", "valor": "1× madrugada",
             "sub": "03:20 BRT · todos os domínios"},
            {"titulo": "Próxima sincronização ERP", "valor": f"{prox_erp} BRT",
             "sub": f"próximo CRM às {prox_crm}"},
        ],
        "proxima_erp": prox_erp, "proxima_crm": prox_crm,
        "nota": ("O ERP do Fred sobe 06/09/12/15/17 BRT; a gente dispara 15min depois, "
                 "pra carga dele terminar. Entre as sincronizações, só o CRM sobe "
                 "(a Gestão à Vista lê o CRM direto)."),
    }

    # Blocos D & E — histórico de execuções (ops.ingestion_runs). Independentes uma
    # da outra -> disparam juntas. Cada uma degrada gracioso no próprio try/except.
    erros = {"runs_resumo": None, "runs_detalhe": None}
    sql_runs = {
        "resumo": f"""
            SELECT source AS fonte,
                   FORMAT_DATETIME('%d/%m %H:%M', DATETIME(MAX(finished_at), 'America/Sao_Paulo')) AS ultima_carga,
                   TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(finished_at), MINUTE) AS idade_min,
                   COUNTIF(DATE(DATETIME(finished_at, 'America/Sao_Paulo')) = CURRENT_DATE('America/Sao_Paulo')) AS cargas_hoje
            FROM `{PROJECT}.ops.ingestion_runs`
            GROUP BY source ORDER BY MAX(finished_at) DESC
        """,
        "detalhe": f"""
            SELECT FORMAT_DATETIME('%d/%m %H:%M:%S', DATETIME(finished_at, 'America/Sao_Paulo')) AS quando,
                   source AS fonte, entity AS entidade, status,
                   rows_loaded AS linhas, ROUND(seconds, 1) AS segundos
            FROM `{PROJECT}.ops.ingestion_runs`
            ORDER BY finished_at DESC LIMIT 20
        """,
    }
    with ThreadPoolExecutor(max_workers=2) as ex:
        resumo_f = ex.submit(query, sql_runs["resumo"])
        detalhe_f = ex.submit(query, sql_runs["detalhe"])

        runs_resumo = []
        try:
            df = resumo_f.result()
            for _, r in df.iterrows():
                mi = int(r["idade_min"]) if pd.notna(r["idade_min"]) else 0
                runs_resumo.append({
                    "fonte": str(r["fonte"]), "ultima_carga": str(r["ultima_carga"]),
                    "idade_min": mi, "idade_txt": _idade_txt(mi),
                    "cargas_hoje": int(r["cargas_hoje"] or 0),
                })
        except Exception as e:  # noqa: BLE001
            erros["runs_resumo"] = str(e)[:200]

        runs_detalhe = []
        try:
            df = detalhe_f.result()
            for _, r in df.iterrows():
                runs_detalhe.append({
                    "quando": str(r["quando"]), "fonte": str(r["fonte"]),
                    "entidade": str(r["entidade"]) if pd.notna(r["entidade"]) else "—",
                    "status": str(r["status"]) if pd.notna(r["status"]) else "—",
                    "linhas": int(r["linhas"]) if pd.notna(r["linhas"]) else 0,
                    "segundos": float(r["segundos"]) if pd.notna(r["segundos"]) else 0.0,
                })
        except Exception as e:  # noqa: BLE001
            erros["runs_detalhe"] = str(e)[:200]

    return {
        "header": {
            "title": "Monitor de Cargas — Data Lake",
            "subtitle": "Frescor de cada fonte, cadência programada e histórico das execuções",
            "sources": [{"name": n, "active": True} for n in HEADER_SOURCES],
            "project": PROJECT,
        },
        "frescor": frescor,
        "cadencia": cadencia,
        "runs_resumo": runs_resumo,
        "runs_detalhe": runs_detalhe,
        "footer": "Nevoni Data Lake · Monitor de Cargas · sapient-metrics-492914-m7",
        "erros": erros,
    }
