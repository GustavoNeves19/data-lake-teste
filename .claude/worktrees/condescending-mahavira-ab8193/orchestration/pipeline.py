

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from config.settings import ENTITIES, DOMAIN_LOAD_ORDER, get_entities_by_domain, get_all_entities_ordered
from extract.sqlserver import SQLServerExtractor
from transform.transformations import transform_entity
from load.bigquery import BigQueryLoader

logger = structlog.get_logger(__name__)

# ── Memória do processo (opcional — requer psutil) ────────
try:
    import psutil as _psutil
    import os as _os
    _process = _psutil.Process(_os.getpid())

    def _mem_mb() -> float:
        return round(_process.memory_info().rss / 1024 / 1024, 1)
except ImportError:
    def _mem_mb() -> float:  # type: ignore[misc]
        return -1.0


@dataclass
class EntityResult:
    """Resultado do processamento de uma entidade."""
    entity: str
    domain: str
    status: str              # "ok" | "error" | "skipped"
    rows_extracted: int = 0
    rows_loaded: int = 0
    seconds: float = 0.0
    rows_per_sec: float = 0.0
    error: str = ""


@dataclass
class PipelineResult:
    """Resultado completo da execução do pipeline."""
    started_at: str = ""
    finished_at: str = ""
    total_seconds: float = 0.0
    entities_ok: int = 0
    entities_error: int = 0
    entities_skipped: int = 0
    total_rows: int = 0
    details: list[EntityResult] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round(self.total_seconds, 1),
            "entities_ok": self.entities_ok,
            "entities_error": self.entities_error,
            "entities_skipped": self.entities_skipped,
            "total_rows_loaded": self.total_rows,
        }


class ETLPipeline:
    """
    Pipeline ETL completo: SQL Server (ERP) → BigQuery (DW).
    Processa 36 entidades em 8 domínios na ordem correta de dependências.
    """

    def __init__(self):
        self.extractor = SQLServerExtractor()
        self.loader = BigQueryLoader()

    # ── Processar uma entidade ───────────────────────────

    def _process_entity(self, entity: dict) -> EntityResult:
        """Executa E → T → L para uma entidade com logging de memória e throughput."""
        name = entity["name"]
        domain = entity["domain"]
        start = time.time()

        logger.info("entity_start", entity=name, domain=domain, mem_mb=_mem_mb())

        try:
            # ── EXTRACT ──────────────────────────────────
            mem_pre_extract = _mem_mb()
            extract_start = time.time()

            df = self.extractor.extract_entity(name, entity["query_file"])

            mem_post_extract = _mem_mb()
            logger.info(
                "phase_extract_done",
                entity=name,
                rows=len(df),
                seconds=round(time.time() - extract_start, 2),
                mem_mb=mem_post_extract,
                mem_delta_mb=round(mem_post_extract - mem_pre_extract, 1),
            )

            if df.empty:
                logger.warning("entity_empty", entity=name)
                return EntityResult(
                    entity=name, domain=domain, status="skipped",
                    seconds=round(time.time() - start, 2),
                )

            rows_extracted = len(df)

            # ── TRANSFORM ────────────────────────────────
            mem_pre_transform = _mem_mb()
            transform_start = time.time()

            df = transform_entity(df, name, entity)

            mem_post_transform = _mem_mb()
            logger.info(
                "phase_transform_done",
                entity=name,
                rows=len(df),
                seconds=round(time.time() - transform_start, 2),
                mem_mb=mem_post_transform,
                mem_delta_mb=round(mem_post_transform - mem_pre_transform, 1),
            )

            # ── LOAD ─────────────────────────────────────
            mem_pre_load = _mem_mb()
            load_start = time.time()

            self.loader.create_table(entity)
            rows_loaded = self.loader.load_dataframe(df, entity)

            mem_post_load = _mem_mb()
            logger.info(
                "phase_load_done",
                entity=name,
                rows=rows_loaded,
                seconds=round(time.time() - load_start, 2),
                mem_mb=mem_post_load,
                mem_delta_mb=round(mem_post_load - mem_pre_load, 1),
            )

            elapsed = round(time.time() - start, 2)
            rows_per_sec = round(rows_extracted / elapsed) if elapsed > 0 else 0.0

            logger.info(
                "entity_ok",
                entity=name,
                rows_extracted=rows_extracted,
                rows_loaded=rows_loaded,
                seconds=elapsed,
                rows_per_sec=rows_per_sec,
            )

            return EntityResult(
                entity=name, domain=domain, status="ok",
                rows_extracted=rows_extracted,
                rows_loaded=rows_loaded,
                seconds=elapsed,
                rows_per_sec=rows_per_sec,
            )

        except Exception as e:
            elapsed = round(time.time() - start, 2)
            logger.error("entity_error", entity=name, error=str(e), seconds=elapsed)
            return EntityResult(
                entity=name, domain=domain, status="error",
                seconds=elapsed, error=str(e),
            )

    # ── Processar um domínio ─────────────────────────────

    def run_domain(self, domain: str) -> list[EntityResult]:
        """Processa todas as entidades de um domínio."""
        entities = get_entities_by_domain(domain)
        if not entities:
            logger.warning("domain_empty", domain=domain)
            return []

        logger.info("domain_start", domain=domain, entities=len(entities))
        results = []

        for entity in entities:
            result = self._process_entity(entity)
            results.append(result)

        ok = sum(1 for r in results if r.status == "ok")
        errors = sum(1 for r in results if r.status == "error")
        logger.info("domain_done", domain=domain, ok=ok, errors=errors)

        return results

    # ── Executar pipeline completo ───────────────────────

    def run_full(
        self,
        domains: list[str] | None = None,
        entities_filter: list[str] | None = None,
    ) -> PipelineResult:
        """
        Executa o pipeline completo.
        Args:
            domains:         Lista de domínios a processar (None = todos)
            entities_filter: Lista de entidades específicas (None = todas)
        Returns:
            PipelineResult com detalhes de cada entidade.
        """
        pipeline_start = time.time()
        result = PipelineResult(
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        target_domains = domains or DOMAIN_LOAD_ORDER

        try:
            # Abre conexões
            self.extractor.connect()

            for domain in target_domains:
                if domain not in DOMAIN_LOAD_ORDER:
                    logger.warning("domain_unknown", domain=domain)
                    continue

                entities = get_entities_by_domain(domain)

                # Filtra entidades específicas se solicitado
                if entities_filter:
                    entities = [e for e in entities if e["name"] in entities_filter]

                for entity in entities:
                    if not entity.get("enabled", True):
                        logger.info("entity_disabled", entity=entity["name"])
                        continue
                    entity_result = self._process_entity(entity)
                    result.details.append(entity_result)

                    if entity_result.status == "ok":
                        result.entities_ok += 1
                        result.total_rows += entity_result.rows_loaded
                    elif entity_result.status == "error":
                        result.entities_error += 1
                    else:
                        result.entities_skipped += 1

        except Exception as e:
            logger.critical("pipeline_fatal_error", error=str(e))
            raise

        finally:
            self.extractor.disconnect()
            self.loader.disconnect()

        result.finished_at = datetime.now(timezone.utc).isoformat()
        result.total_seconds = round(time.time() - pipeline_start, 2)

        logger.info("pipeline_done", **result.summary())

        # ── Ranking das entidades mais lentas ─────────────
        ok_results = [r for r in result.details if r.status == "ok"]
        if ok_results:
            ranking = sorted(ok_results, key=lambda r: r.seconds, reverse=True)
            logger.info(
                "pipeline_slowest_entities",
                ranking=[
                    {
                        "rank": i + 1,
                        "entity": r.entity,
                        "seconds": r.seconds,
                        "rows": r.rows_loaded,
                        "rows_per_sec": r.rows_per_sec,
                    }
                    for i, r in enumerate(ranking[:10])
                ],
            )

        return result

    # ── Validação pós-carga ──────────────────────────────

    def validate_all(self) -> list[dict]:
        """Valida contagem de linhas de todas as entidades."""
        self.loader.connect()
        results = []
        for entity in get_all_entities_ordered():
            name = entity["name"]
            count = self.loader.get_row_count(entity)
            results.append({
                "entity": name,
                "domain": entity["domain"],
                "bq_table": self.loader._get_table_id(entity),
                "rows": count,
            })
        self.loader.disconnect()
        return results
