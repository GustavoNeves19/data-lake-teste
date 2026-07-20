"""
Pipeline bronze do conector de Documentos. Mesmo shape de
orchestration/umbler_bronze_pipeline.py: extrai -> resolve curadoria -> carrega
no cofre -> arquiva versao anterior -> upsert incremental no catalogo ->
soft-delete do que sumiu do FTP.

Ordem de execucao dentro de run():
    1. collect()                        — FTP -> memoria, com hash por arquivo
    2. upload() por arquivo              — cofre (GCS), idempotente por hash
    3. load_to_staging()                 — delta na _stg_catalog
    4. archive_history_from_staging()    — arquiva a linha PRE-mudanca em
                                            docs_raw.catalog_history (decisao da
                                            call de 13/07, ver PIPELINE_DOCUMENTOS_FTP.md)
    5. merge_from_staging()              — MERGE por file_path (INSERT/UPDATE)
    6. soft_delete_missing()             — excluded_at pro que sumiu do FTP
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import structlog

from config.documents import is_official, load_folder_map
from extract.documents import DocumentsFTPExtractor
from load.bigquery import BigQueryLoader
from load.gcs import DocumentsGCSLoader

logger = structlog.get_logger(__name__)

CATALOG_ENTITY = {
    "name": "catalog",
    "dataset": "docs_raw",
    "bq_table": "catalog",
    "bq_schema": [
        ("extract_run_id", "STRING"), ("loaded_at", "TIMESTAMP"),
        ("source_system", "STRING"), ("virtual_directory", "STRING"),
        ("file_path", "STRING"), ("file_name", "STRING"),
        ("file_extension", "STRING"), ("file_size_bytes", "INT64"),
        ("content_hash", "STRING"), ("gcs_uri", "STRING"),
        ("is_official", "BOOL"), ("requires_ocr", "BOOL"),
        ("source_modified_at", "TIMESTAMP"), ("first_seen_at", "TIMESTAMP"),
        ("excluded_at", "TIMESTAMP"),
    ],
}

# Tabela de auditoria — INSERT-only, nunca UPDATE/DELETE. Uma linha por versao
# anterior de um documento, gravada no instante em que o content_hash muda.
CATALOG_HISTORY_ENTITY = {
    "name": "catalog_history",
    "dataset": "docs_raw",
    "bq_table": "catalog_history",
    "bq_schema": CATALOG_ENTITY["bq_schema"] + [("archived_at", "TIMESTAMP")],
}


class DocumentsBronzePipeline:
    def __init__(self):
        self.extractor = DocumentsFTPExtractor()
        self.gcs = DocumentsGCSLoader()
        self.bq = BigQueryLoader()

    def run(self) -> dict:
        extract_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        folder_map = load_folder_map()  # Decisao 6 — fail-safe se ainda vazio

        remote_files = self.extractor.collect()
        remote_paths = {f.file_path for f in remote_files}

        self.bq.create_table(CATALOG_ENTITY)

        # Preserva first_seen_at atraves do MERGE (que sobrescreve toda coluna
        # fora da chave) — busca o valor ja gravado pra cada path presente
        # nesta rodada; path novo fica None e vira "agora" abaixo.
        existing_first_seen = self.bq.get_existing_values(
            CATALOG_ENTITY, key_column="file_path",
            value_column="first_seen_at", keys=remote_paths,
        )
        now = datetime.now(timezone.utc)

        rows = [
            {
                "extract_run_id": extract_run_id,
                "loaded_at": now,
                "source_system": "FTP_NEVONI",
                "virtual_directory": f.virtual_directory,
                "file_path": f.file_path,
                "file_name": f.file_name,
                "file_extension": f.file_extension,
                "file_size_bytes": f.file_size_bytes,
                "content_hash": f.content_hash,
                "gcs_uri": self.gcs.upload(f.file_path, f.content, f.content_hash),
                "is_official": is_official(f.virtual_directory, folder_map),
                "requires_ocr": None,  # calculado na Fase 2 (extracao de texto)
                "source_modified_at": f.source_modified_at,
                "first_seen_at": existing_first_seen.get(f.file_path, now),
                "excluded_at": None,
            }
            for f in remote_files
        ]

        if not rows:
            logger.warning("docs_bronze_no_files_found", extract_run_id=extract_run_id)
            excluded = self.bq.soft_delete_missing(CATALOG_ENTITY, "file_path", remote_paths)
            return {
                "extract_run_id": extract_run_id,
                "files_seen": 0,
                "rows_affected": 0,
                "archived": 0,
                "excluded": excluded,
            }

        df = pd.DataFrame(rows).drop_duplicates(subset=["file_path"], keep="first")

        # staging -> arquiva versao pre-mudanca -> MERGE. Nao usa
        # upsert_incremental() porque o arquivamento tem que rodar ENTRE a
        # staging e o MERGE (precisa comparar staging vs. final antes que o
        # MERGE sobrescreva a final).
        self.bq.load_to_staging(df, CATALOG_ENTITY)
        archived = self.bq.archive_history_from_staging(
            CATALOG_ENTITY, CATALOG_HISTORY_ENTITY,
            primary_key="file_path", version_column="content_hash",
        )
        affected = self.bq.merge_from_staging(CATALOG_ENTITY, primary_key="file_path")

        # Segunda metade do espelho (Decisao 5): soft-delete de tudo que sumiu
        # do FTP nesta rodada.
        excluded = self.bq.soft_delete_missing(CATALOG_ENTITY, "file_path", remote_paths)

        logger.info(
            "docs_bronze_pipeline_done",
            extract_run_id=extract_run_id,
            files_seen=len(remote_files),
            rows_affected=affected,
            archived=archived,
            excluded=excluded,
        )
        return {
            "extract_run_id": extract_run_id,
            "files_seen": len(remote_files),
            "rows_affected": affected,
            "archived": archived,
            "excluded": excluded,
        }
