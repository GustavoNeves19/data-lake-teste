# -*- coding: utf-8 -*-
"""Metas mensais da EQUIPE editáveis pela liderança (Vinícius + Ops), no BigQuery.

Decisão reunião 26/06: o Vinícius edita a meta mensal direto no painel (a mesma
que ele atualiza todo mês), em vez de só ler do Pipedrive. As metas INDIVIDUAIS
seguem vindo do Pipedrive (gestao_vista.METAS_VENDEDOR) — aqui é só a meta da
equipe/grupo (a do gauge e da projeção).

Tabela : silver_comercial.param_com_meta_equipe_mensal
Grão   : view_key (GERAL|HOSPITALAR|FARMACIA) × mes (1º dia do mês).
Leitura: cai no default de gestao_vista.META_EQUIPE quando o mês não tem valor
         gravado — sem regressão se a tabela ainda nem existir.
Edição : gateada em auth.meta_editor_* (st.secrets[meta_editor]); grava updated_by.
"""
from __future__ import annotations

from datetime import date

import streamlit as st
from google.cloud import bigquery

from dashboard.utils.bq_client import get_client, PROJECT_PROD
from dashboard.utils import gestao_vista as gv

TABLE = f"{PROJECT_PROD}.silver_comercial.param_com_meta_equipe_mensal"


def _ensure_table() -> None:
    """Cria a tabela se ainda não existir (idempotente). silver_comercial já existe."""
    get_client().query(f"""
        CREATE TABLE IF NOT EXISTS `{TABLE}` (
          view_key   STRING    NOT NULL,
          mes        DATE      NOT NULL,
          meta       FLOAT64   NOT NULL,
          updated_by STRING,
          updated_at TIMESTAMP
        )
    """).result()


@st.cache_data(ttl=300, show_spinner=False)
def _metas_do_mes(mes_iso: str) -> dict:
    """{view_key: meta} gravadas para o mês. Cacheado (5min) e bustado no set_meta.
    Se a tabela não existir ainda, devolve {} → o chamador usa o default."""
    try:
        df = get_client().query(
            f"SELECT view_key, meta FROM `{TABLE}` WHERE mes = DATE('{mes_iso}')"
        ).to_dataframe()
        return {r["view_key"]: float(r["meta"]) for _, r in df.iterrows()}
    except Exception:
        return {}


def meta_do_mes(view_key: str, mes: date) -> float:
    """Meta da view no mês: valor gravado pela liderança OU o default do código."""
    val = _metas_do_mes(mes.replace(day=1).isoformat()).get(view_key)
    return float(val) if val is not None else float(gv.META_EQUIPE.get(view_key, 0.0))


def meta_armazenada(view_key: str, mes: date):
    """Meta GRAVADA para o mês (None se nunca foi definida). Diferente de meta_do_mes,
    que cai no default: aqui dá pra saber se o número é real daquele mês ou só o
    fallback — meses passados não devem exibir meta/projeção fabricada com o default."""
    val = _metas_do_mes(mes.replace(day=1).isoformat()).get(view_key)
    return float(val) if val is not None else None


def set_meta(view_key: str, mes: date, valor: float, updated_by: str) -> None:
    """Grava (upsert) a meta da view para o mês e busta o cache de leitura."""
    _ensure_table()
    mes1 = mes.replace(day=1)
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("vk", "STRING",  view_key),
        bigquery.ScalarQueryParameter("m",  "DATE",    mes1),
        bigquery.ScalarQueryParameter("v",  "FLOAT64", float(valor)),
        bigquery.ScalarQueryParameter("by", "STRING",  updated_by),
    ])
    get_client().query(f"""
        MERGE `{TABLE}` T
        USING (SELECT @vk AS view_key, @m AS mes, @v AS meta, @by AS updated_by) S
          ON T.view_key = S.view_key AND T.mes = S.mes
        WHEN MATCHED THEN
          UPDATE SET meta = S.meta, updated_by = S.updated_by, updated_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN
          INSERT (view_key, mes, meta, updated_by, updated_at)
          VALUES (S.view_key, S.mes, S.meta, S.updated_by, CURRENT_TIMESTAMP())
    """, job_config=cfg).result()
    _metas_do_mes.clear()
