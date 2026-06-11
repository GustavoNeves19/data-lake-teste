"""
Runner genérico de ingestão — source-agnostic.

Para cada entidade da fonte: extract → bronze → load → state.
Resolve dependências (ex: messages depende de chats) e cursor incremental
(watermark lido de ops.ingestion_runs). Substitui os orquestradores
específicos por fonte (ERP e Umbler tinham cópias quase idênticas).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd
import structlog

from ingestion.registry import load_source
from ingestion.connectors import get_connector
from ingestion.bronze import build_bronze_dataframe
from ingestion.typed import build_typed_dataframe
from ingestion.state import IngestionState
from load.bigquery import BigQueryLoader

logger = structlog.get_logger(__name__)

_WRITE_MODE_MAP = {"truncate": "WRITE_TRUNCATE", "append": "WRITE_APPEND"}


@dataclass
class EntityResult:
    entity: str
    status: str                 # ok | error | skipped
    rows_extracted: int = 0
    rows_loaded: int = 0
    seconds: float = 0.0
    max_event_at: str | None = None
    error: str = ""


@dataclass
class SourceResult:
    source: str
    run_id: str
    started_at: str = ""
    finished_at: str = ""
    total_seconds: float = 0.0
    details: list[EntityResult] = field(default_factory=list)

    @property
    def ok(self) -> int:      return sum(1 for d in self.details if d.status == "ok")
    @property
    def errors(self) -> int:  return sum(1 for d in self.details if d.status == "error")
    @property
    def skipped(self) -> int: return sum(1 for d in self.details if d.status == "skipped")
    @property
    def total_rows(self) -> int: return sum(d.rows_loaded for d in self.details)


def _max_event_at(df: pd.DataFrame, entity_cfg: dict) -> str | None:
    # Coluna de recência: watermark declarado (tipado) ou record_event_at (envelope).
    col = entity_cfg.get("watermark") or "record_event_at"
    if col not in df.columns:
        return None
    s = df[col].dropna()
    return str(s.max()) if not s.empty else None  # ISO-8601 → ordem lexical = cronológica


class IngestionRunner:
    def __init__(self):
        self.loader = BigQueryLoader()
        self.state = IngestionState()

    def run_source(
        self,
        source_name: str,
        *,
        entities_filter: list[str] | None = None,
        full: bool = False,
    ) -> SourceResult:
        src = load_source(source_name)
        connector = get_connector(src.connector)
        context = connector.context()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        result = SourceResult(source=src.source, run_id=run_id,
                              started_at=datetime.now(timezone.utc).isoformat())
        targets = entities_filter or list(src.entities.keys())
        extracted_cache: dict[str, list[dict]] = {}

        logger.info("ingestion_source_start", source=src.source, run_id=run_id,
                    entities=targets, full=full)

        try:
            for name in targets:
                if name not in src.entities:
                    logger.warning("ingestion_entity_unknown", source=src.source, entity=name)
                    continue
                result.details.append(
                    self._process_entity(src, connector, context, src.entities[name],
                                         run_id, full, extracted_cache)
                )
        finally:
            self.loader.disconnect()

        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.total_seconds = round(
            (datetime.fromisoformat(result.finished_at) -
             datetime.fromisoformat(result.started_at)).total_seconds(), 2)
        logger.info("ingestion_source_done", source=src.source, ok=result.ok,
                    errors=result.errors, skipped=result.skipped, rows=result.total_rows)
        return result

    def _parents_for(self, src, connector, entity_cfg, cache) -> list[dict] | None:
        """Extrai (e cacheia) a entidade-pai quando a paginação é aninhada."""
        parent_name = entity_cfg.get("depends_on")
        if not parent_name:
            return None
        if parent_name not in cache:
            logger.info("ingestion_extract_parent", parent=parent_name,
                        child=entity_cfg["name"])
            cache[parent_name] = connector.extract(src.entities[parent_name])
        return cache[parent_name]

    def _process_entity(self, src, connector, context, entity_cfg,
                        run_id, full, cache) -> EntityResult:
        name = entity_cfg["name"]
        start = time.time()
        started_at = datetime.now(timezone.utc).isoformat()

        def _state(status, rows_ext=0, rows_load=0, max_ev=None, error=""):
            self.state.record({
                "run_id": run_id, "source": src.source, "entity": name,
                "dataset": entity_cfg["dataset"], "bq_table": entity_cfg["bq_table"],
                "status": status, "rows_extracted": rows_ext, "rows_loaded": rows_load,
                "max_event_at": max_ev, "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "seconds": round(time.time() - start, 2), "error": error[:1000],
            })

        try:
            # Watermark incremental: ops.ingestion_runs OU, na 1ª vez, MAX(coluna)
            # da própria tabela alvo (seed a partir do que já existe).
            since = None
            wm_col = entity_cfg.get("watermark")
            if not full and entity_cfg.get("write_mode") == "append" and wm_col:
                since = self.state.read_watermark(src.source, name)
                if since is None:
                    since = self.loader.get_max(entity_cfg, wm_col)
                    if since is not None:
                        logger.info("watermark_seed_from_table", entity=name, column=wm_col, since=str(since))

            parents = self._parents_for(src, connector, entity_cfg, cache)
            records = cache.get(name)
            if records is None:
                records = connector.extract(entity_cfg, parents=parents, since=since)
                cache[name] = records

            if not records:
                logger.warning("ingestion_entity_empty", entity=name)
                _state("skipped")
                return EntityResult(entity=name, status="skipped",
                                    seconds=round(time.time() - start, 2))

            if entity_cfg.get("projection") == "typed":
                df = build_typed_dataframe(records, entity_cfg=entity_cfg,
                                           context={**context, "run_id": run_id})
            else:
                df = build_bronze_dataframe(records, entity_cfg=entity_cfg, run_id=run_id,
                                            source_system=src.source, context=context)
            max_ev = _max_event_at(df, entity_cfg)
            write_mode = _WRITE_MODE_MAP.get(entity_cfg.get("write_mode", "truncate"), "WRITE_TRUNCATE")

            self.loader.create_table(entity_cfg)
            # Idempotência: apaga a janela re-extraída antes do append incremental.
            if write_mode == "WRITE_APPEND" and entity_cfg.get("idempotent") and wm_col and since is not None:
                self.loader.delete_window(entity_cfg, wm_col, since)
            rows_loaded = self.loader.load_dataframe(df, entity_cfg, write_mode=write_mode)

            elapsed = round(time.time() - start, 2)
            logger.info("ingestion_entity_ok", entity=name, rows=rows_loaded,
                        seconds=elapsed, max_event_at=max_ev)
            _state("ok", rows_ext=len(records), rows_load=rows_loaded, max_ev=max_ev)
            return EntityResult(entity=name, status="ok", rows_extracted=len(records),
                                rows_loaded=rows_loaded, seconds=elapsed, max_event_at=max_ev)

        except Exception as e:  # noqa: BLE001
            elapsed = round(time.time() - start, 2)
            logger.error("ingestion_entity_error", entity=name, error=str(e), seconds=elapsed)
            _state("error", error=str(e))
            return EntityResult(entity=name, status="error", seconds=elapsed, error=str(e))
