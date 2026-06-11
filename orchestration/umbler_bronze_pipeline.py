"""
Pipeline ETL da camada bronze da Umbler Talk.
Extrai payloads crus da API Umbler e persiste no BigQuery com metadados de ingestao.
Entidades configuradas em config/umbler_endpoints.json — sem hardcode.

Ordem de execucao:
    1. channels  — full reload (WRITE_TRUNCATE)
    2. chats     — full reload paginado (WRITE_TRUNCATE)
    3. messages  — append incremental por eventAtUTC (WRITE_APPEND)

messages depende do resultado de chats (precisa dos chat_ids), por isso e
processado em separado apos o loop principal de entidades simples.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from config.umbler import UMBLER_CONFIG, load_umbler_bronze_entities
from extract.umbler import UmblerExtractor
from load.bigquery import BigQueryLoader
from transform.umbler_bronze_transformations import (
    build_umbler_bronze_dataframe,
    build_umbler_messages_dataframe,
)

logger = structlog.get_logger(__name__)

_WRITE_MODE_MAP = {
    "truncate": "WRITE_TRUNCATE",
    "append":   "WRITE_APPEND",
}


@dataclass
class UmblerEntityResult:
    entity: str
    status: str
    rows_extracted: int = 0
    rows_loaded: int = 0
    seconds: float = 0.0
    error: str = ""


@dataclass
class UmblerBronzePipelineResult:
    started_at: str = ""
    finished_at: str = ""
    total_seconds: float = 0.0
    entities_ok: int = 0
    entities_error: int = 0
    entities_skipped: int = 0
    total_rows: int = 0
    details: list[UmblerEntityResult] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "started_at":        self.started_at,
            "finished_at":       self.finished_at,
            "duration_seconds":  round(self.total_seconds, 1),
            "entities_ok":       self.entities_ok,
            "entities_error":    self.entities_error,
            "entities_skipped":  self.entities_skipped,
            "total_rows_loaded": self.total_rows,
        }


class UmblerBronzePipeline:
    """
    Pipeline bronze da Umbler Talk.

    Le entidades de config/umbler_endpoints.json (enabled=true),
    extrai via UmblerExtractor, transforma para DataFrame bronze e
    carrega no BigQuery.

    messages e tratado separadamente pois depende dos chat_ids de chats.
    """

    def __init__(self):
        self.extractor    = UmblerExtractor()
        self.loader       = BigQueryLoader()
        self.organization_id = UMBLER_CONFIG["organization_id"]

    def _load_entities(self) -> dict[str, dict]:
        return load_umbler_bronze_entities()

    def _process_channels(
        self, entity_cfg: dict, extract_run_id: str
    ) -> UmblerEntityResult:
        start = time.time()
        name = "channels"
        try:
            records = self.extractor.get_channels(entity_cfg)
            if not records:
                logger.warning("umbler_bronze_channels_empty")
                return UmblerEntityResult(entity=name, status="skipped", seconds=round(time.time() - start, 2))

            df = build_umbler_bronze_dataframe(
                records=records,
                entity_name=name,
                entity_cfg=entity_cfg,
                extract_run_id=extract_run_id,
                organization_id=self.organization_id,
            )
            entity = {"name": name, **entity_cfg}
            write_mode = _WRITE_MODE_MAP.get(entity_cfg.get("write_mode", "truncate"), "WRITE_TRUNCATE")
            self.loader.create_table(entity)
            rows_loaded = self.loader.load_dataframe(df, entity, write_mode=write_mode)
            elapsed = round(time.time() - start, 2)
            logger.info("umbler_bronze_channels_ok", rows=rows_loaded, seconds=elapsed)
            return UmblerEntityResult(
                entity=name, status="ok",
                rows_extracted=len(records), rows_loaded=rows_loaded, seconds=elapsed,
            )
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            logger.error("umbler_bronze_channels_error", error=str(e), seconds=elapsed)
            return UmblerEntityResult(entity=name, status="error", seconds=elapsed, error=str(e))

    def _process_chats(
        self, entity_cfg: dict, extract_run_id: str
    ) -> tuple[UmblerEntityResult, list[dict]]:
        """Retorna o resultado E a lista de chats para uso no step de messages."""
        start = time.time()
        name = "chats"
        try:
            records = self.extractor.get_chats(entity_cfg)
            if not records:
                logger.warning("umbler_bronze_chats_empty")
                return (
                    UmblerEntityResult(entity=name, status="skipped", seconds=round(time.time() - start, 2)),
                    [],
                )

            df = build_umbler_bronze_dataframe(
                records=records,
                entity_name=name,
                entity_cfg=entity_cfg,
                extract_run_id=extract_run_id,
                organization_id=self.organization_id,
            )
            entity = {"name": name, **entity_cfg}
            write_mode = _WRITE_MODE_MAP.get(entity_cfg.get("write_mode", "truncate"), "WRITE_TRUNCATE")
            self.loader.create_table(entity)
            rows_loaded = self.loader.load_dataframe(df, entity, write_mode=write_mode)
            elapsed = round(time.time() - start, 2)
            logger.info("umbler_bronze_chats_ok", rows=rows_loaded, seconds=elapsed)
            return (
                UmblerEntityResult(
                    entity=name, status="ok",
                    rows_extracted=len(records), rows_loaded=rows_loaded, seconds=elapsed,
                ),
                records,
            )
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            logger.error("umbler_bronze_chats_error", error=str(e), seconds=elapsed)
            return (
                UmblerEntityResult(entity=name, status="error", seconds=elapsed, error=str(e)),
                [],
            )

    def _process_messages(
        self, entity_cfg: dict, chats: list[dict], extract_run_id: str
    ) -> UmblerEntityResult:
        start = time.time()
        name = "messages"
        try:
            pairs = self.extractor.get_messages_all_chats(chats, entity_cfg)
            if not pairs:
                logger.warning(
                    "umbler_bronze_messages_empty",
                    hint="Verifique UMBLER_MESSAGES_FROM_UTC no .env",
                )
                return UmblerEntityResult(entity=name, status="skipped", seconds=round(time.time() - start, 2))

            df = build_umbler_messages_dataframe(
                chat_message_pairs=pairs,
                entity_cfg=entity_cfg,
                extract_run_id=extract_run_id,
                organization_id=self.organization_id,
            )
            entity = {"name": name, **entity_cfg}
            write_mode = _WRITE_MODE_MAP.get(entity_cfg.get("write_mode", "append"), "WRITE_APPEND")
            self.loader.create_table(entity)
            rows_loaded = self.loader.load_dataframe(df, entity, write_mode=write_mode)
            elapsed = round(time.time() - start, 2)
            logger.info("umbler_bronze_messages_ok", rows=rows_loaded, seconds=elapsed)
            return UmblerEntityResult(
                entity=name, status="ok",
                rows_extracted=len(pairs), rows_loaded=rows_loaded, seconds=elapsed,
            )
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            logger.error("umbler_bronze_messages_error", error=str(e), seconds=elapsed)
            return UmblerEntityResult(entity=name, status="error", seconds=elapsed, error=str(e))

    def _process_generic(
        self, name: str, entity_cfg: dict, extract_run_id: str
    ) -> UmblerEntityResult:
        """Handler generico para entidades skip_take e none (contacts, tags, sectors)."""
        start = time.time()
        try:
            pagination = entity_cfg.get("pagination_mode", "none")
            if pagination == "skip_take":
                records = self.extractor.get_chats(entity_cfg)
            else:
                records = self.extractor.get_channels(entity_cfg)

            if not records:
                logger.warning("umbler_bronze_generic_empty", entity=name)
                return UmblerEntityResult(entity=name, status="skipped", seconds=round(time.time() - start, 2))

            df = build_umbler_bronze_dataframe(
                records=records,
                entity_name=name,
                entity_cfg=entity_cfg,
                extract_run_id=extract_run_id,
                organization_id=self.organization_id,
            )
            entity = {"name": name, **entity_cfg}
            write_mode = _WRITE_MODE_MAP.get(entity_cfg.get("write_mode", "truncate"), "WRITE_TRUNCATE")
            self.loader.create_table(entity)
            rows_loaded = self.loader.load_dataframe(df, entity, write_mode=write_mode)
            elapsed = round(time.time() - start, 2)
            logger.info("umbler_bronze_generic_ok", entity=name, rows=rows_loaded, seconds=elapsed)
            return UmblerEntityResult(
                entity=name, status="ok",
                rows_extracted=len(records), rows_loaded=rows_loaded, seconds=elapsed,
            )
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            logger.error("umbler_bronze_generic_error", entity=name, error=str(e), seconds=elapsed)
            return UmblerEntityResult(entity=name, status="error", seconds=elapsed, error=str(e))

    def run_full(
        self, entities_filter: list[str] | None = None
    ) -> UmblerBronzePipelineResult:
        """
        Executa a ingestao bronze completa da Umbler.
        Ordem: channels → chats → contacts → tags → sectors → messages
        """
        pipeline_start = time.time()
        extract_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        result = UmblerBronzePipelineResult(started_at=datetime.now(timezone.utc).isoformat())
        entities = self._load_entities()
        chats_records: list[dict] = []

        _SPECIAL = {"channels", "chats", "messages"}

        def _should_run(name: str) -> bool:
            return entities_filter is None or name in entities_filter

        def _register(r: UmblerEntityResult) -> None:
            result.details.append(r)
            if r.status == "ok":
                result.entities_ok += 1
                result.total_rows += r.rows_loaded
            elif r.status == "error":
                result.entities_error += 1
            else:
                result.entities_skipped += 1

        try:
            logger.info(
                "umbler_bronze_pipeline_start",
                total_entities=len(entities),
                extract_run_id=extract_run_id,
                organization_id=self.organization_id,
            )

            if "channels" in entities and _should_run("channels"):
                _register(self._process_channels(entities["channels"], extract_run_id))

            if "chats" in entities and _should_run("chats"):
                r, chats_records = self._process_chats(entities["chats"], extract_run_id)
                _register(r)

            # Entidades genericas (contacts, tags, sectors, etc.)
            for name, cfg in entities.items():
                if name not in _SPECIAL and _should_run(name):
                    _register(self._process_generic(name, cfg, extract_run_id))

            if "messages" in entities and _should_run("messages"):
                if not chats_records and "chats" in entities:
                    logger.info("umbler_bronze_fetching_chats_for_messages")
                    chats_records = self.extractor.get_chats(entities["chats"])

                _register(self._process_messages(entities["messages"], chats_records, extract_run_id))

        finally:
            self.loader.disconnect()

        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.total_seconds = round(time.time() - pipeline_start, 2)
        logger.info("umbler_bronze_pipeline_done", **result.summary())
        return result

    def validate_all(self) -> list[dict]:
        """Valida contagem de linhas de todas as entidades Umbler bronze no BigQuery."""
        entities = self._load_entities()
        self.loader.connect()
        results = []
        for name, cfg in entities.items():
            entity = {"name": name, **cfg}
            count = self.loader.get_row_count(entity)
            results.append({
                "entity":   name,
                "bq_table": f"{cfg['dataset']}.{cfg['bq_table']}",
                "rows":     count,
            })
        self.loader.disconnect()
        return results

    def test_connection(self) -> dict:
        """Testa autenticacao Bearer com GET /v1/members/me/."""
        return self.extractor.test_connection()

    def list_entities(self) -> list[dict]:
        """Lista entidades habilitadas em umbler_endpoints.json."""
        return [
            {
                "name":             name,
                "endpoint":         cfg.get("endpoint"),
                "pagination_mode":  cfg.get("pagination_mode"),
                "write_mode":       cfg.get("write_mode"),
                "bq_table":         f"{cfg.get('dataset')}.{cfg.get('bq_table')}",
            }
            for name, cfg in self._load_entities().items()
        ]
