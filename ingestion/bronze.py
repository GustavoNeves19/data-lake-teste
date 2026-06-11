"""
Envelope bronze padronizado — comum a TODAS as fontes API.

Toda tabela `*_raw` segue o mesmo formato: metadados de ingestão + payload cru
em JSON. Isso torna silver/gold uniformes independente da fonte.

Colunas:
    extract_run_id    STRING     id da execução (mesmo p/ todas as entidades da run)
    etl_loaded_at     TIMESTAMP  quando o registro entrou no BQ (UTC)
    source_system     STRING     UMBLER | PIPEDRIVE | GMAIL | GOTO
    <colunas extras>             ex: organization_id (contexto), chat_id (por registro)
    entity_name       STRING     channels | chats | messages | ...
    source_endpoint   STRING     caminho da API que originou o registro
    record_id         STRING     id natural do registro na fonte
    record_event_at   TIMESTAMP  carimbo de negócio (eventAtUTC, update_time, ...)
    payload_json      STRING     payload cru serializado (com PII removida se aplicável)

As "colunas extras" são declaradas na config da fonte/entidade e resolvidas a
partir do `context` (constantes da fonte) ou do próprio registro (por chave).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

# Colunas universais antes/depois das colunas extras da fonte.
_LEAD_SCHEMA: list[tuple[str, str]] = [
    ("extract_run_id", "STRING"),
    ("etl_loaded_at",  "TIMESTAMP"),
    ("source_system",  "STRING"),
]
_TAIL_SCHEMA: list[tuple[str, str]] = [
    ("entity_name",     "STRING"),
    ("source_endpoint", "STRING"),
    ("record_id",       "STRING"),
    ("record_event_at", "TIMESTAMP"),
    ("payload_json",    "STRING"),
]


def bronze_schema(extra_columns: list[dict] | None) -> list[tuple[str, str]]:
    """Monta o bq_schema do envelope bronze, inserindo colunas extras no meio."""
    extras = [(c["name"], c.get("type", "STRING")) for c in (extra_columns or [])]
    return _LEAD_SCHEMA + extras + _TAIL_SCHEMA


def _coerce_str(value) -> str | None:
    return None if value is None else str(value)


def _coerce_timestamp(value) -> str | None:
    """Normaliza ISO 8601 para algo que o BigQuery infira como TIMESTAMP UTC."""
    if not value or not isinstance(value, str):
        return None
    return value.rstrip("Z") + "Z"


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)


def _resolve_extra(col: dict, record: dict, context: dict):
    """Resolve o valor de uma coluna extra a partir do contexto ou do registro."""
    scope = col.get("scope", "context")
    key = col.get("key", col["name"])
    if scope == "record":
        return _coerce_str(record.get(key))
    return _coerce_str(context.get(key))


def _apply_pii(record: dict, pii: dict | None) -> dict:
    """
    Remove campos pessoais ANTES de serializar o payload (conformidade LGPD).
    Declarado por entidade na config JSON:
        "pii": {"drop": ["content"], "drop_in": {"file": ["url"]}}
    `drop`     remove chaves de topo; `drop_in` remove subchaves de um objeto.
    """
    if not pii:
        return record
    rec = dict(record)
    for field in pii.get("drop", []):
        rec.pop(field, None)
    for parent, subkeys in pii.get("drop_in", {}).items():
        if isinstance(rec.get(parent), dict):
            rec[parent] = {k: v for k, v in rec[parent].items() if k not in subkeys}
    return rec


def build_bronze_dataframe(
    records: list[dict],
    *,
    entity_cfg: dict,
    run_id: str,
    source_system: str,
    context: dict | None = None,
) -> pd.DataFrame:
    """
    Constrói o DataFrame bronze para uma entidade, de forma source-agnostic.

    Args:
        records:        lista de registros crus (dicts) já extraídos da fonte.
        entity_cfg:     config da entidade (name, endpoint, record_id_path,
                        event_at_path, extra_columns, pii_strip).
        run_id:         id da execução (extract_run_id).
        source_system:  rótulo da fonte (UMBLER, PIPEDRIVE, ...).
        context:        valores constantes da fonte (ex: organization_id).
    """
    context = context or {}
    loaded_at = datetime.now(timezone.utc).isoformat()

    entity_name     = entity_cfg["name"]
    source_endpoint = entity_cfg.get("endpoint", entity_name)
    record_id_path  = entity_cfg.get("record_id_path", "id")
    event_at_path   = entity_cfg.get("event_at_path", "")
    extra_columns   = entity_cfg.get("extra_columns", [])
    pii             = entity_cfg.get("pii")  # dict declarativo | None

    rows = []
    for record in records:
        row = {
            "extract_run_id": run_id,
            "etl_loaded_at":  loaded_at,
            "source_system":  source_system,
        }
        for col in extra_columns:
            row[col["name"]] = _resolve_extra(col, record, context)

        payload = _apply_pii(record, pii)
        row.update({
            "entity_name":     entity_name,
            "source_endpoint": source_endpoint,
            "record_id":       _coerce_str(record.get(record_id_path)),
            "record_event_at": _coerce_timestamp(record.get(event_at_path)) if event_at_path else None,
            "payload_json":    _json_dumps(payload),
        })
        rows.append(row)

    return pd.DataFrame(rows)
