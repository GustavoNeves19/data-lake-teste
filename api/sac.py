"""
Setor SAC e Assistência Técnica.

A view original do Streamlit era especulativa (referenciava gold_sac, crm_raw.deals,
dm_calls — todos inexistentes). Aqui é um port + correção de fonte: usa as tabelas
que de fato existem no BigQuery. Não é paridade número-a-número (não há camada gold
de SAC), mas todos os números vêm de dados reais:
  - Atendimentos: crm_raw.sac_atendimento (pipeline 10) + sac_vendas (pipeline 11)
  - SLA: TMR de resolução (CRM) + 1ª resposta (umbler_raw.chats, setor SAC)
  - Chamadas: goto_raw.goto_calls (janela parcial de abril/2026)
  - Chat: umbler_raw.chats filtrando sector.name = 'SAC' (JSON raw)
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from .bq import query, PROJECT_PROD

PROJ = PROJECT_PROD
CRM = f"{PROJ}.crm_raw"
GOTO = f"{PROJ}.goto_raw"
UMBLER = f"{PROJ}.umbler_raw"

PIPELINE_ROTULO = {10: "Assistência Técnica", 11: "Venda SAC"}


def _num(v, d=0.0) -> float:
    try:
        f = float(v)
        return d if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return d


# ── Atendimentos ───────────────────────────────────────────────
def atendimentos() -> dict:
    df = query(f"""
        WITH d AS (
          SELECT status, add_time, close_time, 10 AS pl FROM `{CRM}.sac_atendimento`
          UNION ALL
          SELECT status, add_time, close_time, 11 AS pl FROM `{CRM}.sac_vendas`
        )
        SELECT FORMAT_TIMESTAMP('%Y-%m', add_time) AS mes, pl AS pipeline_id,
               COALESCE(status, 'open') AS status,
               COUNT(*) AS qtd,
               AVG(TIMESTAMP_DIFF(COALESCE(close_time, CURRENT_TIMESTAMP()), add_time, HOUR)) AS tmr_h
        FROM d WHERE add_time IS NOT NULL
        GROUP BY 1, 2, 3
    """)
    if df.empty:
        return {"camada": "crm_raw", "empty": True, "kpis": {}, "por_mes": [], "por_status": [], "por_pipeline": []}

    total = int(df["qtd"].sum())
    won = int(df[df["status"] == "won"]["qtd"].sum())
    lost = int(df[df["status"] == "lost"]["qtd"].sum())
    open_ = total - won - lost
    taxa = won / total * 100 if total else 0.0
    tmr_medio = _num((df["tmr_h"] * df["qtd"]).sum() / total) if total else 0.0

    pm = df.groupby("mes").apply(
        lambda g: pd.Series({"qtd": int(g["qtd"].sum()),
                             "tmr_horas": _num((g["tmr_h"] * g["qtd"]).sum() / g["qtd"].sum())}),
        include_groups=False).reset_index().sort_values("mes")
    por_mes = [{"mes": str(r["mes"]), "qtd": int(r["qtd"]), "tmr_horas": _num(r["tmr_horas"])} for _, r in pm.iterrows()]

    ps = df.groupby("status")["qtd"].sum().reset_index()
    por_status = [{"status": str(r["status"]), "qtd": int(r["qtd"])} for _, r in ps.iterrows()]

    pp = df.groupby("pipeline_id")["qtd"].sum().reset_index()
    por_pipeline = [{"pipeline_id": int(r["pipeline_id"]),
                     "rotulo": PIPELINE_ROTULO.get(int(r["pipeline_id"]), f"Pipeline {int(r['pipeline_id'])}"),
                     "qtd": int(r["qtd"])} for _, r in pp.iterrows()]

    return {
        "camada": "crm_raw", "empty": False,
        "kpis": {"total_atendimentos": total, "resolvidos": won,
                 "taxa_resolucao_pct": taxa, "tmr_medio_h": tmr_medio,
                 "abertos": open_},
        "por_mes": por_mes, "por_status": por_status, "por_pipeline": por_pipeline,
    }


# ── SLA / TMR ──────────────────────────────────────────────────
def sla() -> dict:
    sql = {
        "crm": f"""
            WITH d AS (
              SELECT status, add_time, close_time FROM `{CRM}.sac_atendimento`
              UNION ALL
              SELECT status, add_time, close_time FROM `{CRM}.sac_vendas`
            )
            SELECT FORMAT_TIMESTAMP('%Y-%m', add_time) AS mes,
                   COUNT(*) AS qtd,
                   AVG(TIMESTAMP_DIFF(COALESCE(close_time, CURRENT_TIMESTAMP()), add_time, HOUR)) AS tmr_horas
            FROM d WHERE add_time IS NOT NULL
            GROUP BY 1 ORDER BY 1
        """,
        # 1ª resposta via Umbler (setor SAC): firstContact -> firstMemberReply em minutos.
        "um": f"""
            WITH c AS (
              SELECT FORMAT_TIMESTAMP('%Y-%m', TIMESTAMP(JSON_VALUE(payload_json,'$.createdAtUTC'))) AS mes,
                     TIMESTAMP_DIFF(
                        TIMESTAMP(JSON_VALUE(payload_json,'$.firstMemberReplyMessage.eventAtUTC')),
                        TIMESTAMP(JSON_VALUE(payload_json,'$.firstContactMessage.eventAtUTC')), MINUTE) AS resp_min
              FROM `{UMBLER}.chats`
              WHERE JSON_VALUE(payload_json,'$.sector.name') = 'SAC'
            )
            SELECT mes, APPROX_QUANTILES(resp_min, 2)[OFFSET(1)] AS mediana_min, COUNT(*) AS qtd
            FROM c WHERE resp_min IS NOT NULL AND resp_min >= 0
            GROUP BY 1 ORDER BY 1
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        crm_f = ex.submit(query, sql["crm"])
        um_f = ex.submit(query, sql["um"])
        crm = crm_f.result()
        try:
            um = um_f.result()
        except Exception:
            um = None

    tmr_por_mes = [{"mes": str(r["mes"]), "tmr_horas": _num(r["tmr_horas"]), "qtd": int(r["qtd"])}
                   for _, r in crm.iterrows()] if not crm.empty else []
    tmr_ult = tmr_por_mes[-1]["tmr_horas"] if tmr_por_mes else 0.0
    tmr_medio = _num((crm["tmr_horas"] * crm["qtd"]).sum() / crm["qtd"].sum()) if not crm.empty and crm["qtd"].sum() else 0.0

    pr_por_mes, pr_mediana = [], None
    if um is not None:
        pr_por_mes = [{"mes": str(r["mes"]), "mediana_min": _num(r["mediana_min"]), "qtd_chats_sac": int(r["qtd"])}
                      for _, r in um.iterrows()] if not um.empty else []
        if pr_por_mes:
            pr_mediana = _num(pd.Series([p["mediana_min"] for p in pr_por_mes]).median())

    return {
        "camada_crm": "crm_raw", "camada_chat": "umbler_raw",
        "kpis": {"tmr_resolucao_ultimo_mes_h": tmr_ult, "tmr_resolucao_medio_h": tmr_medio,
                 "t_primeira_resposta_mediana_min": pr_mediana},
        "tmr_resolucao_por_mes": tmr_por_mes,
        "primeira_resposta_por_mes": pr_por_mes,
        "meta_h": 48,
    }


# ── Chamadas (GoTo) ────────────────────────────────────────────
def chamadas() -> dict:
    sql = {
        "df": f"""
            SELECT FORMAT_TIMESTAMP('%Y-%m', call_created) AS mes,
                   direction, ai_sentiment, duration_seconds
            FROM `{GOTO}.goto_calls`
            WHERE call_created IS NOT NULL
        """,
        "janela": f"""
            SELECT FORMAT_DATE('%Y-%m-%d', MIN(DATE(call_created))) AS de,
                   FORMAT_DATE('%Y-%m-%d', MAX(DATE(call_created))) AS ate
            FROM `{GOTO}.goto_calls` WHERE call_created IS NOT NULL
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    df, janela = dfs["df"], dfs["janela"]
    if df.empty:
        return {"camada": "goto_raw", "empty": True, "kpis": {}, "por_mes": [], "por_direcao": [], "por_sentimento": []}
    df["duration_seconds"] = pd.to_numeric(df["duration_seconds"], errors="coerce").fillna(0)
    total = int(len(df))
    minutos = int(df["duration_seconds"].sum() / 60)
    dur_media = minutos / total if total else 0.0

    jd = janela.iloc[0] if not janela.empty else None

    pm = df.groupby("mes").agg(qtd=("mes", "count"), minutos=("duration_seconds", lambda s: int(s.sum() / 60))).reset_index().sort_values("mes")
    por_mes = [{"mes": str(r["mes"]), "qtd": int(r["qtd"]), "minutos": int(r["minutos"])} for _, r in pm.iterrows()]
    pdir = df.groupby(df["direction"].fillna("—"))["mes"].count().reset_index(name="qtd")
    por_direcao = [{"direcao": str(r["direction"]), "qtd": int(r["qtd"])} for _, r in pdir.iterrows()]
    psent = df.groupby(df["ai_sentiment"].fillna("UNAVAILABLE"))["mes"].count().reset_index(name="qtd")
    por_sentimento = [{"sentimento": str(r["ai_sentiment"]), "qtd": int(r["qtd"])} for _, r in psent.sort_values("qtd", ascending=False).iterrows()]

    return {
        "camada": "goto_raw", "empty": False,
        "janela": {"de": (str(jd["de"]) if jd is not None else None),
                   "ate": (str(jd["ate"]) if jd is not None else None),
                   "aviso": "Telefonia geral da conta (não filtrável por SAC); carga parcial do GoTo."},
        "kpis": {"total_chamadas": total, "minutos_total": minutos, "duracao_media_min": dur_media},
        "por_mes": por_mes, "por_direcao": por_direcao, "por_sentimento": por_sentimento,
    }


# ── Chat (Umbler) ──────────────────────────────────────────────
def chat() -> dict:
    try:
        df = query(f"""
            SELECT FORMAT_TIMESTAMP('%Y-%m', TIMESTAMP(JSON_VALUE(payload_json,'$.createdAtUTC'))) AS mes,
                   COALESCE(JSON_VALUE(payload_json,'$.channel.name'), '—') AS canal,
                   CAST(JSON_VALUE(payload_json,'$.open') AS BOOL) AS aberta
            FROM `{UMBLER}.chats`
            WHERE JSON_VALUE(payload_json,'$.sector.name') = 'SAC'
        """)
    except Exception as e:  # noqa: BLE001
        return {"camada": "umbler_raw", "empty": True, "erro": str(e)[:200],
                "kpis": {}, "por_mes": [], "por_canal": []}
    if df.empty:
        return {"camada": "umbler_raw", "empty": True, "kpis": {}, "por_mes": [], "por_canal": []}

    total = int(len(df))
    canais = int(df["canal"].nunique())
    abertas = int(df["aberta"].fillna(False).sum())
    pm = df.groupby(["mes", "canal"]).size().reset_index(name="conversas").sort_values("mes")
    por_mes = [{"mes": str(r["mes"]), "canal": str(r["canal"]), "conversas": int(r["conversas"])} for _, r in pm.iterrows()]
    pc = df.groupby("canal").size().reset_index(name="conversas").sort_values("conversas", ascending=False)
    por_canal = [{"canal": str(r["canal"]), "conversas": int(r["conversas"])} for _, r in pc.iterrows()]

    return {
        "camada": "umbler_raw", "empty": False, "filtro": "sector.name = 'SAC'",
        "kpis": {"total_conversas_sac": total, "canais": canais, "abertas": abertas},
        "por_mes": por_mes, "por_canal": por_canal,
    }
