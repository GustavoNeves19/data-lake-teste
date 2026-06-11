"""
Registry unificado de fontes API.

Cada fonte é declarada em `config/sources/<source>.json` — sem hardcode no
código. Adicionar uma fonte nova = um JSON + um conector; zero mudança no
runner/loader/state.

Estrutura do JSON:
{
  "source": "UMBLER",
  "dataset": "umbler_raw",
  "connector": "umbler",
  "auth": "bearer_static",
  "context_columns": [ {"name": "organization_id", "type": "STRING"} ],
  "entities": [
    {
      "name": "channels", "endpoint": "/v1/channels/", "bq_table": "channels",
      "write_mode": "truncate", "pagination_mode": "none",
      "record_id_path": "id", "event_at_path": "",
      "record_columns": [...], "pii": {...}, "depends_on": "...", "watermark": "..."
    }
  ]
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ingestion.bronze import bronze_schema
from ingestion.typed import typed_schema

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_DIR = BASE_DIR / "config" / "sources"


@dataclass
class SourceConfig:
    source: str                  # rótulo (UMBLER)
    dataset: str                 # dataset bronze padrão (umbler_raw)
    connector: str               # nome do conector em ingestion.connectors
    auth: str                    # estratégia de auth (bearer_static, ...)
    entities: dict[str, dict]    # name -> entity cfg já normalizada
    raw: dict                    # JSON original (acesso a chaves específicas da fonte)


def source_path(name: str) -> Path:
    return SOURCES_DIR / f"{name}.json"


def list_sources() -> list[str]:
    if not SOURCES_DIR.exists():
        return []
    return sorted(p.stem for p in SOURCES_DIR.glob("*.json"))


def load_source(name: str) -> SourceConfig:
    """Lê e normaliza a config de uma fonte. Levanta se não existir."""
    path = source_path(name)
    if not path.exists():
        disponiveis = ", ".join(list_sources()) or "(nenhuma)"
        raise FileNotFoundError(
            f"Fonte '{name}' não encontrada em {SOURCES_DIR}. Disponíveis: {disponiveis}"
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config de fonte inválida (esperado objeto JSON): {path}")

    source    = payload["source"]
    dataset   = payload["dataset"]
    connector = payload.get("connector", name)
    auth      = payload.get("auth", "")
    context_columns = payload.get("context_columns", [])

    entities: dict[str, dict] = {}
    for item in payload.get("entities", []):
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        ename = str(item.get("name", "")).strip()
        if not ename:
            raise ValueError(f"Entidade sem 'name' em {path}")

        base = {
            "name":        ename,
            "source":      source,
            "dataset":     item.get("dataset", dataset),
            "bq_table":    item.get("bq_table", ename),
            "entity_type": "RAW",
            "write_mode":  item.get("write_mode", "truncate"),
            "projection":  item.get("projection", "envelope"),
        }

        if base["projection"] == "typed":
            # raw = coluna: tabela tipada (Pipedrive, dims). Colunas declaradas.
            columns = item.get("columns", [])
            cfg = {
                **base,
                "kind":        item.get("kind"),          # deals | stages | users | messages | ...
                "pipeline_id": item.get("pipeline_id"),   # p/ deals
                "watermark":   item.get("watermark"),     # coluna p/ incremental (ex: internal_date)
                "idempotent":  item.get("idempotent", False),  # delete-window antes do append
                "columns":     columns,
                "bq_schema":   typed_schema(columns),
            }
        else:
            # envelope bronze (Umbler e fontes de payload nested/variável).
            record_columns = item.get("record_columns", [])
            for col in context_columns:
                col.setdefault("scope", "context")
            for col in record_columns:
                col.setdefault("scope", "record")
            extra_columns = context_columns + record_columns
            cfg = {
                **base,
                "endpoint":        item.get("endpoint", ""),
                "pagination_mode": item.get("pagination_mode", "none"),
                "page_size":       int(item.get("page_size", 100)),
                "data_path":       item.get("data_path", ""),
                "record_id_path":  item.get("record_id_path", "id"),
                "event_at_path":   item.get("event_at_path", ""),
                "watermark":       item.get("watermark"),
                "depends_on":      item.get("depends_on"),
                "pii":             item.get("pii"),
                "extra_columns":   extra_columns,
                "bq_schema":       bronze_schema(extra_columns),
            }
        entities[ename] = cfg

    return SourceConfig(
        source=source, dataset=dataset, connector=connector,
        auth=auth, entities=entities, raw=payload,
    )
