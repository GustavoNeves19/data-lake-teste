"""
Módulo de carga — Google BigQuery.
Cria tabelas (se não existem) e carrega DataFrames.
Usa dataset por domínio (Opção B): dm_partners, dm_products, etc.
"""

import datetime as dt
import io
import math
import time

import pandas as pd
import structlog
from google.cloud import bigquery
from google.api_core.exceptions import NotFound, Conflict

from config.settings import BQ_PROJECT, DOMAIN_DATASET_MAP, BATCH_SIZE, BQ_LOCATION

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
        Monta o table_id completo: projeto.dataset.tabela

        Resolução do dataset (multi-fonte):
          1. `entity_config["dataset"]` explícito  → fontes API (Umbler, Pipedrive, ...)
          2. `DOMAIN_DATASET_MAP[domain]`          → ERP (compatibilidade)

        Ex ERP:    sapient-metrics-492914-m7.dm_partners.dim_company
        Ex Umbler: sapient-metrics-492914-m7.umbler_raw.channels
        """
        dataset = entity_config.get("dataset")
        if not dataset:
            dataset = DOMAIN_DATASET_MAP[entity_config["domain"]]
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
            isna = df_out[col].isna()
            df_out[col] = (
                df_out[col]
                .astype(str)
                .str.replace("\x00", "", regex=False)
                .replace({"nan": None, "None": None, "NaN": None, "<NA>": None,
                          "NaT": None, "nat": None})
            )
            df_out.loc[isna, col] = None

        # Converte timestamps para string ISO (JSONL não serializa datetime nativo)
        for col in df_out.columns:
            if hasattr(df_out[col], "dt"):
                isna = df_out[col].isna()
                df_out[col] = df_out[col].astype(str)
                df_out.loc[isna, col] = None
                df_out[col] = df_out[col].replace({"NaT": None, "nat": None, "None": None})

        # NUMERIC: o float64 do pandas gera artefato de ponto flutuante na serialização
        # JSON (ex: 659294.68 -> 659294.6800000001), que estoura a escala de 9 casas do
        # NUMERIC e o BQ rejeita o chunk inteiro. Converte pra string formatada — o BQ
        # parseia NUMERIC de string sem perder precisão nem criar artefato.
        numeric_cols = [
            f.name for f in schema
            if f.field_type == "NUMERIC" and f.name in df_out.columns
        ]
        for col in numeric_cols:
            s = pd.to_numeric(df_out[col], errors="coerce")
            df_out[col] = s.map(
                lambda v: format(v, ".6f").rstrip("0").rstrip(".") if pd.notna(v) else None
            )

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

    def get_max(self, entity_config: dict, column: str):
        """MAX(column) da tabela — seed de watermark incremental. None se vazia/inexistente."""
        self.connect()
        table_id = self._get_table_id(entity_config)
        try:
            self._client.get_table(table_id)
        except NotFound:
            return None
        q = f"SELECT MAX(`{column}`) AS mx FROM `{table_id}`"
        rows = list(self._client.query(q).result())
        return rows[0].mx if rows else None

    def delete_window(self, entity_config: dict, column: str, since) -> int:
        """
        Apaga as linhas com `column` >= since antes de um append incremental.
        A janela re-extraída (conector busca a partir de since) substitui a
        anterior — idempotência exata por timestamp, sem duplicar nem perder.
        Retorna nº de linhas afetadas. No-op se a tabela não existe.
        """
        self.connect()
        table_id = self._get_table_id(entity_config)
        try:
            self._client.get_table(table_id)
        except NotFound:
            return 0
        cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("since", "TIMESTAMP", since),
        ])
        q = f"DELETE FROM `{table_id}` WHERE `{column}` >= @since"
        job = self._client.query(q, job_config=cfg)
        job.result()
        affected = job.num_dml_affected_rows or 0
        logger.info("delete_window", table=table_id, column=column, since=str(since), deleted=affected)
        return affected

    # ── Carga incremental — staging + MERGE (upsert idempotente) ──────────
    # O caminho incremental: em vez de re-subir a tabela inteira (load_dataframe
    # WRITE_TRUNCATE), sobe só o delta numa staging e faz MERGE pela chave. O MERGE
    # cobre os 3 casos do CDC numa passada: linha nova (INSERT), valor alterado
    # (UPDATE) e cancelamento via excluded_at (UPDATE = soft-delete). Idempotente:
    # re-trazer o overlap reaplica o mesmo valor pela chave, nunca duplica.

    @staticmethod
    def _staging_config(entity_config: dict) -> dict:
        """Config espelho apontando pra staging descartável _stg_<tabela> (mesmo
        dataset, mesmo schema da final)."""
        return {**entity_config, "bq_table": "_stg_" + entity_config["bq_table"]}

    def load_to_staging(self, df: pd.DataFrame, entity_config: dict) -> tuple[str, int]:
        """Sobe o delta na staging _stg_<tabela> com WRITE_TRUNCATE. Reusa
        create_table + load_dataframe. Retorna (staging_table_id, linhas)."""
        stg_cfg = self._staging_config(entity_config)
        self.create_table(stg_cfg)
        rows = self.load_dataframe(df, stg_cfg, write_mode="WRITE_TRUNCATE")
        return self._get_table_id(stg_cfg), rows

    def merge_from_staging(
        self,
        entity_config: dict,
        primary_key: "list[str] | str",
        columns: "list[str] | None" = None,
    ) -> int:
        """MERGE (upsert) da staging pra final, pela chave primária. WHEN MATCHED
        reaplica todas as colunas fora da chave (cobre edição e cancelamento via
        excluded_at); WHEN NOT MATCHED insere. Retorna linhas afetadas."""
        self.connect()
        final_id = self._get_table_id(entity_config)
        stg_id = self._get_table_id(self._staging_config(entity_config))

        pk = [primary_key] if isinstance(primary_key, str) else list(primary_key)
        cols = columns or [c for c, _ in entity_config["bq_schema"]]
        upd = [c for c in cols if c not in pk]
        if not upd:
            raise ValueError(f"merge_from_staging: nada a atualizar fora da chave {pk}")

        on = " AND ".join(f"T.`{k}` = S.`{k}`" for k in pk)
        set_clause = ", ".join(f"`{c}` = S.`{c}`" for c in upd)
        ins_cols = ", ".join(f"`{c}`" for c in cols)
        ins_vals = ", ".join(f"S.`{c}`" for c in cols)
        sql = (
            f"MERGE `{final_id}` T USING `{stg_id}` S ON {on}\n"
            f"WHEN MATCHED THEN UPDATE SET {set_clause}\n"
            f"WHEN NOT MATCHED THEN INSERT ({ins_cols}) VALUES ({ins_vals})"
        )
        job = self._client.query(sql)
        job.result()
        affected = job.num_dml_affected_rows or 0
        logger.info("merge_ok", table=final_id, staging=stg_id, key=pk, affected=affected)
        return affected

    def upsert_incremental(
        self,
        df: pd.DataFrame,
        entity_config: dict,
        primary_key: "list[str] | str",
    ) -> int:
        """Caminho incremental completo: staging + MERGE numa chamada. Contraparte
        do load_dataframe (WRITE_TRUNCATE = full-reload)."""
        if df.empty:
            logger.warning("upsert_skipped_empty", table=self._get_table_id(entity_config))
            return 0
        # sk ÚNICO no delta antes do MERGE: o BQ aborta ("must match at most one source
        # row") se a staging tiver sk repetido. Fan-out de JOIN (ex.: ATENDENTES com
        # YCODVEN duplicado) geraria sk repetido; colapsa pro primeiro e loga (visível).
        subset = primary_key if isinstance(primary_key, list) else [primary_key]
        n0 = len(df)
        df = df.drop_duplicates(subset=subset, keep="first")
        if len(df) < n0:
            logger.warning("upsert_dedup_staging", table=self._get_table_id(entity_config),
                           removed=n0 - len(df), key=subset)
        self.load_to_staging(df, entity_config)
        return self.merge_from_staging(entity_config, primary_key)

    # ── Historico de versao (auditoria pre-MERGE) ──────────────────────────
    # Duvida levantada pelo Fred na call de 13/07 (docs/PIPELINE_DOCUMENTOS_FTP.md):
    # quando um documento e reprocessado com hash novo, o registro antigo vira
    # uma linha de auditoria em vez de simplesmente desaparecer no UPDATE.
    # Mesma logica do ops.watermark_control: tabela auxiliar separada da
    # entidade principal, nao um redesenho da chave primaria dela.

    def archive_history_from_staging(
        self,
        entity_config: dict,
        history_entity_config: dict,
        primary_key: str,
        version_column: str,
    ) -> int:
        """Roda ENTRE load_to_staging() e merge_from_staging(): compara a
        staging (delta que esta prestes a sobrescrever a final) com a linha
        atual da final por `primary_key`, e arquiva (INSERT-only, nunca
        UPDATE/DELETE) toda linha cujo `version_column` (ex.: content_hash)
        vai mudar. Se a final ainda nao existir ou a staging nao trouxer
        divergencia, e no-op — nao e erro, so nao ha o que arquivar ainda."""
        self.connect()
        final_id = self._get_table_id(entity_config)
        stg_id = self._get_table_id(self._staging_config(entity_config))
        hist_id = self.create_table(history_entity_config)

        final_cols = [c for c, _ in entity_config["bq_schema"]]
        select_cols = ", ".join(f"T.`{c}`" for c in final_cols)
        query = f"""
            INSERT INTO `{hist_id}` ({", ".join(f"`{c}`" for c in final_cols)}, archived_at)
            SELECT {select_cols}, CURRENT_TIMESTAMP()
            FROM `{final_id}` T
            JOIN `{stg_id}` S ON T.`{primary_key}` = S.`{primary_key}`
            WHERE T.`{version_column}` != S.`{version_column}`
        """
        try:
            job = self._client.query(query)
            job.result()
        except NotFound:
            # Tabela final ainda nao existe (primeira carga) — nada a arquivar.
            logger.info("archive_history_skip_first_load", table=final_id)
            return 0
        archived = job.num_dml_affected_rows or 0
        logger.info("archive_history_done", table=hist_id, archived=archived)
        return archived

    def soft_delete_missing(
        self,
        entity_config: dict,
        primary_key: str,
        present_keys: set[str],
    ) -> int:
        """Marca excluded_at para toda linha cuja `primary_key` nao esta em
        `present_keys` — nunca DELETE fisico. Contraparte do espelho:
        upsert_incremental cobre INSERT/UPDATE, este metodo cobre a exclusao
        logica. Usado pelo conector de Documentos (Decisao 5 do
        PIPELINE_DOCUMENTOS_FTP.md) — generalizavel pra qualquer conector
        "espelho" futuro."""
        self.connect()
        table_id = self._get_table_id(entity_config)
        query = f"""
            UPDATE `{table_id}`
            SET excluded_at = CURRENT_TIMESTAMP()
            WHERE excluded_at IS NULL
              AND `{primary_key}` NOT IN UNNEST(@present_keys)
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("present_keys", "STRING", list(present_keys)),
        ])
        job = self._client.query(query, job_config=job_config)
        job.result()
        affected = job.num_dml_affected_rows or 0
        logger.info("soft_delete_missing", table=table_id, key=primary_key, affected=affected)
        return affected

    def get_existing_values(
        self,
        entity_config: dict,
        key_column: str,
        value_column: str,
        keys: set[str],
    ) -> dict:
        """Busca `value_column` atual pra cada `key_column` dentre `keys`, na
        tabela final. Usado quando o pipeline precisa preservar uma coluna que
        o MERGE generico de merge_from_staging sobrescreveria — ex.:
        first_seen_at do catalogo de Documentos, que nao pode ser resetado a
        cada atualizacao de hash (MERGE nao faz COALESCE por coluna)."""
        self.connect()
        table_id = self._get_table_id(entity_config)
        query = f"""
            SELECT `{key_column}` AS k, `{value_column}` AS v
            FROM `{table_id}`
            WHERE `{key_column}` IN UNNEST(@keys)
        """
        job_config = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("keys", "STRING", list(keys)),
        ])
        try:
            rows = list(self._client.query(query, job_config=job_config).result())
        except NotFound:
            return {}
        return {r.k: r.v for r in rows}

    # ── Watermark control (carga incremental) ─────────────────────────────
    # ops.watermark_control guarda, por entidade, a maior data já carregada. A
    # próxima carga incremental lê a partir dela (menos o overlap). Atualizada SÓ
    # após a carga dar certo, recalculando MAX direto da tabela final.

    def _watermark_table_id(self) -> str:
        return f"{BQ_PROJECT}.ops.watermark_control"

    def ensure_watermark_table(self) -> None:
        """Cria ops.watermark_control (e o dataset ops) se não existirem."""
        self.connect()
        ds_id = f"{BQ_PROJECT}.ops"
        try:
            self._client.get_dataset(ds_id)
        except NotFound:
            ds = bigquery.Dataset(ds_id)
            ds.location = BQ_LOCATION
            self._client.create_dataset(ds, exists_ok=True)
        tid = self._watermark_table_id()
        try:
            self._client.get_table(tid)
        except NotFound:
            schema = [
                bigquery.SchemaField("entity", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("watermark_column", "STRING"),
                bigquery.SchemaField("last_watermark_value", "TIMESTAMP"),
                bigquery.SchemaField("last_run_at", "TIMESTAMP"),
                bigquery.SchemaField("last_row_count", "INT64"),
                bigquery.SchemaField("load_mode", "STRING"),
            ]
            self._client.create_table(bigquery.Table(tid, schema=schema), exists_ok=True)
            logger.info("watermark_table_created", table=tid)

    def get_watermark(self, entity_name: str):
        """Último watermark gravado pra entidade. None se nunca carregou (= backfill)."""
        self.connect()
        self.ensure_watermark_table()
        q = f"SELECT last_watermark_value AS v FROM `{self._watermark_table_id()}` WHERE entity = @e"
        cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("e", "STRING", entity_name)])
        rows = list(self._client.query(q, job_config=cfg).result())
        return rows[0].v if rows else None

    def set_watermark(self, entity_config: dict, watermark_column: str):
        """Recalcula MAX(watermark_column) da tabela FINAL e grava (upsert) em
        ops.watermark_control. Chamar SÓ após a carga dar certo, pra não travar a
        marca num valor parcial. Retorna o novo watermark."""
        self.connect()
        self.ensure_watermark_table()
        mx = self.get_max(entity_config, watermark_column)
        # get_max devolve datetime.date pra coluna DATE (ex.: invoice_date); o parametro
        # TIMESTAMP do BQ nao serializa date puro (TypeError). Promove a datetime UTC
        # (meia-noite); o overlap em dias absorve qualquer desvio de borda.
        if isinstance(mx, dt.date) and not isinstance(mx, dt.datetime):
            mx = dt.datetime(mx.year, mx.month, mx.day, tzinfo=dt.timezone.utc)
        cnt = self.get_row_count(entity_config)
        q = f"""MERGE `{self._watermark_table_id()}` T
        USING (SELECT @e AS entity, @c AS watermark_column, @v AS last_watermark_value,
                      CURRENT_TIMESTAMP() AS last_run_at, @n AS last_row_count, @m AS load_mode) S
        ON T.entity = S.entity
        WHEN MATCHED THEN UPDATE SET watermark_column = S.watermark_column,
            last_watermark_value = S.last_watermark_value, last_run_at = S.last_run_at,
            last_row_count = S.last_row_count, load_mode = S.load_mode
        WHEN NOT MATCHED THEN INSERT ROW"""
        cfg = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("e", "STRING", entity_config["name"]),
            bigquery.ScalarQueryParameter("c", "STRING", watermark_column),
            bigquery.ScalarQueryParameter("v", "TIMESTAMP", mx),
            bigquery.ScalarQueryParameter("n", "INT64", cnt),
            bigquery.ScalarQueryParameter("m", "STRING", entity_config.get("load_mode", "")),
        ])
        self._client.query(q, job_config=cfg).result()
        logger.info("watermark_set", entity=entity_config["name"], value=str(mx), rows=cnt)
        return mx

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
