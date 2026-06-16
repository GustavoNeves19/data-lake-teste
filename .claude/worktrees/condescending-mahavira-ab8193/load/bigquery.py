"""
Módulo de carga — Google BigQuery.
Cria tabelas (se não existem) e carrega DataFrames.
Usa dataset por domínio (Opção B): dm_partners, dm_products, etc.
"""

import io
import math
import time

import pandas as pd
import structlog
from google.cloud import bigquery
from google.api_core.exceptions import NotFound, Conflict

from config.settings import BQ_PROJECT, DOMAIN_DATASET_MAP, BATCH_SIZE

logger = structlog.get_logger(__name__)

# ── Mapeamento tipo settings → tipo BigQuery ─────────────
_TYPE_MAP = {
    "INT64":     bigquery.enums.SqlTypeNames.INT64,
    "STRING":    bigquery.enums.SqlTypeNames.STRING,
    "NUMERIC":   bigquery.enums.SqlTypeNames.NUMERIC,
    "FLOAT64":   bigquery.enums.SqlTypeNames.FLOAT64,
    "BOOL":      bigquery.enums.SqlTypeNames.BOOL,
    "DATE":      bigquery.enums.SqlTypeNames.DATE,
    "TIMESTAMP": bigquery.enums.SqlTypeNames.TIMESTAMP,
}

_MAX_CHUNK_RETRIES = 3


class BigQueryLoader:
    """Carrega dados no BigQuery usando dataset por domínio."""

    def __init__(self):
        self._client = None

    # ── Conexão ──────────────────────────────────────────

    def connect(self) -> None:
        if self._client:
            return
        self._client = bigquery.Client(project=BQ_PROJECT)
        logger.info("bq_connected", project=BQ_PROJECT)

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.info("bq_disconnected")

    # ── Table ID por domínio ─────────────────────────────

    @staticmethod
    def _get_table_id(entity_config: dict) -> str:
        """
        Monta o table_id completo: projeto.dataset_do_dominio.tabela
        Ex: vanguardia-prod-466114.dm_partners.dim_company
        """
        domain = entity_config["domain"]
        dataset = DOMAIN_DATASET_MAP[domain]
        table_name = entity_config["bq_table"]
        return f"{BQ_PROJECT}.{dataset}.{table_name}"

    # ── Schema ───────────────────────────────────────────

    @staticmethod
    def _build_schema(bq_schema: list[tuple]) -> list[bigquery.SchemaField]:
        fields = []
        for col_name, col_type in bq_schema:
            bq_type = _TYPE_MAP.get(col_type, bigquery.enums.SqlTypeNames.STRING)
            mode = "REQUIRED" if col_name.startswith("sk_") or col_name == "loaded_at" else "NULLABLE"
            fields.append(bigquery.SchemaField(col_name, bq_type, mode=mode))
        return fields

    # ── Criar tabela (se não existir) ────────────────────

    def create_table(self, entity_config: dict) -> str:
        """
        Cria tabela no BigQuery se não existir.
        Retorna o table_id completo.
        """
        self.connect()
        table_id = self._get_table_id(entity_config)

        # Verifica se já existe
        try:
            self._client.get_table(table_id)
            logger.info("table_exists", table=table_id)
            return table_id
        except NotFound:
            pass  # Não existe, vai criar

        schema = self._build_schema(entity_config["bq_schema"])
        table = bigquery.Table(table_id, schema=schema)

        # Descrição
        domain = entity_config.get("domain", "")
        etype = entity_config.get("entity_type", "")
        table.description = f"[{domain}] {etype} — Pipeline ETL automático"

        try:
            self._client.create_table(table)
            logger.info("table_created", table=table_id)
        except Conflict:
            logger.info("table_exists_race", table=table_id)
        except Exception as e:
            logger.error("table_create_error", table=table_id, error=str(e))
            raise

        return table_id

    def create_all_tables(self, entities: list[dict]) -> dict[str, str]:
        """Cria todas as tabelas que não existem. Retorna {entity_name: table_id}."""
        self.connect()
        table_map = {}
        created = 0
        existed = 0

        for entity in entities:
            name = entity["name"]
            table_id = self._get_table_id(entity)

            try:
                self._client.get_table(table_id)
                existed += 1
            except NotFound:
                self.create_table(entity)
                created += 1

            table_map[name] = table_id

        logger.info(
            "all_tables_ready",
            total=len(table_map),
            created=created,
            already_existed=existed,
        )
        return table_map

    # ── Preparação do DataFrame ───────────────────────────

    def _prepare_df_for_load(
        self,
        df: pd.DataFrame,
        schema: list[bigquery.SchemaField],
    ) -> pd.DataFrame:
        """
        Filtra colunas pelo schema, limpa null bytes e normaliza nulos.
        Retorna cópia do DataFrame pronta para serialização JSONL.
        """
        schema_cols = [f.name for f in schema]
        df_cols = [c for c in schema_cols if c in df.columns]
        df_out = df[df_cols].copy()

        # Limpa null bytes e normaliza nulos em todas as colunas string-like
        # (object = tipo padrão, string = pd.StringDtype)
        str_cols = df_out.select_dtypes(include=["object", "string"]).columns
        for col in str_cols:
            df_out[col] = (
                df_out[col]
                .astype(str)
                .str.replace("\x00", "", regex=False)
                .replace({"nan": None, "None": None, "NaN": None, "<NA>": None})
            )

        # Converte timestamps para string ISO (JSONL não serializa datetime nativo)
        for col in df_out.columns:
            if hasattr(df_out[col], "dt"):
                df_out[col] = df_out[col].astype(str).replace({"NaT": None, "nat": None})

        return df_out

    # ── Envio de chunk individual com retry ───────────────

    def _send_chunk(
        self,
        chunk: pd.DataFrame,
        table_id: str,
        schema: list[bigquery.SchemaField],
        write_disposition: str,
        chunk_num: int,
        total_chunks: int,
        rows_sent_before: int,
        total_rows: int,
    ) -> None:
        """
        Envia um chunk para o BigQuery com retry automático.
        Loga progresso e throughput por chunk.
        """
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=write_disposition,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )

        last_error: Exception | None = None
        for attempt in range(1, _MAX_CHUNK_RETRIES + 1):
            try:
                chunk_start = time.time()

                jsonl_buffer = io.BytesIO()
                chunk.to_json(jsonl_buffer, orient="records", lines=True, force_ascii=False)
                jsonl_buffer.seek(0)

                job = self._client.load_table_from_file(
                    jsonl_buffer,
                    table_id,
                    job_config=job_config,
                )
                job.result()

                elapsed = time.time() - chunk_start
                rows_now = rows_sent_before + len(chunk)
                throughput = round(len(chunk) / elapsed) if elapsed > 0 else 0

                logger.info(
                    "chunk_sent",
                    table=table_id,
                    chunk=f"{chunk_num}/{total_chunks}",
                    rows_in_chunk=len(chunk),
                    rows_progress=f"{rows_now}/{total_rows}",
                    seconds=round(elapsed, 2),
                    rows_per_sec=throughput,
                )
                return  # sucesso

            except Exception as e:
                last_error = e
                if attempt < _MAX_CHUNK_RETRIES:
                    logger.warning(
                        "chunk_retry",
                        table=table_id,
                        chunk=chunk_num,
                        attempt=attempt,
                        error=str(e),
                    )
                else:
                    logger.error(
                        "chunk_failed",
                        table=table_id,
                        chunk=chunk_num,
                        attempts=_MAX_CHUNK_RETRIES,
                        error=str(e),
                    )

        raise RuntimeError(
            f"Chunk {chunk_num}/{total_chunks} falhou após {_MAX_CHUNK_RETRIES} tentativas"
        ) from last_error

    # ── Carga ────────────────────────────────────────────

    def load_dataframe(
        self,
        df: pd.DataFrame,
        entity_config: dict,
        write_mode: str = "WRITE_TRUNCATE",
    ) -> int:
        """
        Carrega DataFrame no BigQuery em chunks configuráveis (BATCH_SIZE).
        Primeiro chunk usa write_mode; chunks subsequentes usam WRITE_APPEND.
        """
        self.connect()
        table_id = self._get_table_id(entity_config)

        if df.empty:
            logger.warning("load_skipped_empty", table=table_id)
            return 0

        schema = self._build_schema(entity_config["bq_schema"])
        df_to_load = self._prepare_df_for_load(df, schema)

        total_rows = len(df_to_load)
        total_chunks = math.ceil(total_rows / BATCH_SIZE)

        logger.info(
            "load_start",
            table=table_id,
            total_rows=total_rows,
            chunk_size=BATCH_SIZE,
            total_chunks=total_chunks,
        )

        load_start = time.time()
        rows_sent = 0

        for chunk_num, offset in enumerate(range(0, total_rows, BATCH_SIZE), start=1):
            chunk = df_to_load.iloc[offset: offset + BATCH_SIZE]
            write_disp = write_mode if chunk_num == 1 else "WRITE_APPEND"

            self._send_chunk(
                chunk=chunk,
                table_id=table_id,
                schema=schema,
                write_disposition=write_disp,
                chunk_num=chunk_num,
                total_chunks=total_chunks,
                rows_sent_before=rows_sent,
                total_rows=total_rows,
            )
            rows_sent += len(chunk)

        total_elapsed = round(time.time() - load_start, 2)
        total_throughput = round(rows_sent / total_elapsed) if total_elapsed > 0 else 0

        logger.info(
            "load_ok",
            table=table_id,
            rows=rows_sent,
            chunks=total_chunks,
            seconds=total_elapsed,
            rows_per_sec=total_throughput,
        )
        return rows_sent

    # ── Validação ────────────────────────────────────────

    def get_row_count(self, entity_config: dict) -> int:
        """Conta linhas de uma tabela usando o config da entidade."""
        self.connect()
        table_id = self._get_table_id(entity_config)
        try:
            table = self._client.get_table(table_id)
            return table.num_rows
        except NotFound:
            return -1

    def validate_load(self, entity_name: str, expected_rows: int, entity_config: dict) -> dict:
        actual = self.get_row_count(entity_config)
        match = actual == expected_rows
        result = {
            "entity": entity_name,
            "table": self._get_table_id(entity_config),
            "expected": expected_rows,
            "actual": actual,
            "match": match,
        }
        if match:
            logger.info("validation_ok", **result)
        else:
            logger.warning("validation_mismatch", **result)
        return result

    # ── Context Manager ──────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
