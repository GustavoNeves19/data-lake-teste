"""
State store de ingestão — `ops.ingestion_runs`.

Log append-only de toda execução por entidade. Serve a dois propósitos:
  1. Freshness  — "até quando cada fonte tem dado" vira um SELECT (não uma
                  varredura manual de MAX por tabela).
  2. Watermark  — cursor incremental: a próxima carga lê o último max_event_at
                  bem-sucedido e extrai só o que veio depois.

Idempotente: cria dataset + tabela se não existirem. Falha em gravar o log NÃO
derruba a ingestão (observabilidade não é caminho crítico) — o runner trata.
"""

from __future__ import annotations

import os

import structlog
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

from config.settings import BQ_PROJECT, BQ_LOCATION

logger = structlog.get_logger(__name__)

OPS_DATASET = os.getenv("OPS_DATASET", "ops")
RUNS_TABLE = "ingestion_runs"

_SCHEMA = [
    bigquery.SchemaField("run_id",         "STRING"),
    bigquery.SchemaField("source",         "STRING"),
    bigquery.SchemaField("entity",         "STRING"),
    bigquery.SchemaField("dataset",        "STRING"),
    bigquery.SchemaField("bq_table",       "STRING"),
    bigquery.SchemaField("status",         "STRING"),   # ok | error | skipped
    bigquery.SchemaField("rows_extracted", "INT64"),
    bigquery.SchemaField("rows_loaded",    "INT64"),
    bigquery.SchemaField("max_event_at",   "TIMESTAMP"),
    bigquery.SchemaField("started_at",     "TIMESTAMP"),
    bigquery.SchemaField("finished_at",    "TIMESTAMP"),
    bigquery.SchemaField("seconds",        "FLOAT64"),
    bigquery.SchemaField("error",          "STRING"),
]


class IngestionState:
    def __init__(self, client: bigquery.Client | None = None):
        self._client = client or bigquery.Client(project=BQ_PROJECT)
        self._table_id = f"{BQ_PROJECT}.{OPS_DATASET}.{RUNS_TABLE}"
        self._ready = False

    # ── Bootstrap idempotente ────────────────────────────────────────────────

    def ensure(self) -> None:
        if self._ready:
            return
        ds_id = f"{BQ_PROJECT}.{OPS_DATASET}"
        try:
            self._client.get_dataset(ds_id)
        except NotFound:
            ds = bigquery.Dataset(ds_id)
            ds.location = BQ_LOCATION
            ds.description = "Metadados operacionais do Data Lake (ingestão, freshness)."
            self._client.create_dataset(ds, exists_ok=True)
            logger.info("ops_dataset_created", dataset=ds_id)
        try:
            self._client.get_table(self._table_id)
        except NotFound:
            table = bigquery.Table(self._table_id, schema=_SCHEMA)
            table.description = "Log append-only de execuções de ingestão (freshness + watermark)."
            self._client.create_table(table, exists_ok=True)
            logger.info("ops_table_created", table=self._table_id)
        self._ready = True

    # ── Escrita ──────────────────────────────────────────────────────────────

    def record(self, run: dict) -> None:
        """Acrescenta uma linha de execução. Tolerante a falha (loga e segue)."""
        try:
            self.ensure()
            job = self._client.load_table_from_json(
                [run],
                self._table_id,
                job_config=bigquery.LoadJobConfig(
                    schema=_SCHEMA, write_disposition="WRITE_APPEND"
                ),
            )
            job.result()
        except Exception as e:  # noqa: BLE001
            logger.warning("ingestion_state_write_failed", entity=run.get("entity"), error=str(e))

    # ── Leitura ──────────────────────────────────────────────────────────────

    def read_watermark(self, source: str, entity: str) -> str | None:
        """Último max_event_at carregado com sucesso para a entidade (ou None)."""
        try:
            self.ensure()
            q = f"""
                SELECT max_event_at
                FROM `{self._table_id}`
                WHERE source = @source AND entity = @entity
                  AND status = 'ok' AND max_event_at IS NOT NULL
                ORDER BY finished_at DESC
                LIMIT 1
            """
            cfg = bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("source", "STRING", source),
                bigquery.ScalarQueryParameter("entity", "STRING", entity),
            ])
            rows = list(self._client.query(q, job_config=cfg).result())
            if rows and rows[0].max_event_at is not None:
                return rows[0].max_event_at.isoformat()
        except Exception as e:  # noqa: BLE001
            logger.warning("ingestion_state_read_failed", entity=entity, error=str(e))
        return None

    def freshness(self) -> list[dict]:
        """Última execução por (source, entity) — base do painel Saúde das Fontes."""
        self.ensure()
        q = f"""
            SELECT * EXCEPT(rn) FROM (
              SELECT *, ROW_NUMBER() OVER (
                       PARTITION BY source, entity ORDER BY finished_at DESC
                     ) rn
              FROM `{self._table_id}`
            ) WHERE rn = 1
            ORDER BY source, entity
        """
        return [dict(r) for r in self._client.query(q).result()]
