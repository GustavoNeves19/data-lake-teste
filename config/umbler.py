"""
Configuracao isolada da fonte Umbler Talk.
Autenticacao via Bearer token (estatico, sem OAuth2).
Endpoints configurados em umbler_endpoints.json — sem hardcode no codigo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ENDPOINTS_FILE = BASE_DIR / "config" / "umbler_endpoints.json"

# ── Credenciais e opcoes de conexao ──────────────────────────────────────────
UMBLER_CONFIG = {
    "api_token":       os.getenv("UMBLER_API_TOKEN", ""),
    "organization_id": os.getenv("UMBLER_ORGANIZATION_ID", ""),
    "base_url":        os.getenv("UMBLER_BASE_URL", "https://app-utalk.umbler.com/api"),
    "timeout":         int(os.getenv("UMBLER_TIMEOUT", "30")),
    "pause_seconds":   float(os.getenv("UMBLER_PAUSE_SECONDS", "0.3")),
    # Cursor incremental para messages — ISO 8601 UTC
    # Na primeira execucao defina para a data historica desejada (ex: 2025-01-01T00:00:00Z)
    "messages_from_utc": os.getenv("UMBLER_MESSAGES_FROM_UTC", ""),
}

# ── Dataset BigQuery destino ──────────────────────────────────────────────────
UMBLER_BRONZE_DATASET = os.getenv("UMBLER_BQ_DATASET", "umbler_raw")

# ── Schema base da camada bronze ─────────────────────────────────────────────
# Campos de metadados de ingestao + payload cru JSON.
# Colunas extras por entidade sao adicionadas no schema especifico abaixo.
UMBLER_BRONZE_SCHEMA_BASE = [
    ("extract_run_id",  "STRING"),
    ("etl_loaded_at",   "TIMESTAMP"),
    ("source_system",   "STRING"),
    ("organization_id", "STRING"),
    ("entity_name",     "STRING"),
    ("source_endpoint", "STRING"),
    ("record_id",       "STRING"),
    ("record_event_at", "TIMESTAMP"),
    ("payload_json",    "STRING"),
]

# Schema para channels e chats (schema base sem colunas extras)
UMBLER_BRONZE_SCHEMA = UMBLER_BRONZE_SCHEMA_BASE

# Schema para messages — inclui chat_id para navegacao eficiente
UMBLER_MESSAGES_SCHEMA = [
    ("extract_run_id",  "STRING"),
    ("etl_loaded_at",   "TIMESTAMP"),
    ("source_system",   "STRING"),
    ("organization_id", "STRING"),
    ("chat_id",         "STRING"),
    ("entity_name",     "STRING"),
    ("source_endpoint", "STRING"),
    ("record_id",       "STRING"),
    ("record_event_at", "TIMESTAMP"),
    ("payload_json",    "STRING"),
]


def get_umbler_endpoints_file(config_path: str | Path | None = None) -> Path:
    if config_path is not None:
        return Path(config_path)
    env_path = os.getenv("UMBLER_ENDPOINTS_FILE")
    if env_path:
        return Path(env_path)
    return DEFAULT_ENDPOINTS_FILE


def load_umbler_endpoint_payload(config_path: str | Path | None = None) -> dict:
    path = get_umbler_endpoints_file(config_path)
    if not path.exists():
        return {"entities": []}
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"Arquivo de endpoints invalido (esperado objeto JSON): {path}")
    return payload


def load_umbler_bronze_entities(config_path: str | Path | None = None) -> dict[str, dict]:
    """
    Converte umbler_endpoints.json em registry de entidades habilitadas.
    Apenas entidades com 'enabled': true sao incluidas.
    """
    payload = load_umbler_endpoint_payload(config_path)
    entities: dict[str, dict] = {}

    for item in payload.get("entities", []):
        if not isinstance(item, dict):
            raise ValueError("Cada entidade Umbler deve ser um objeto JSON")

        if not item.get("enabled", True):
            continue

        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError("Cada entidade Umbler habilitada precisa de um 'name'")

        endpoint = str(item.get("endpoint", "")).strip()
        bq_schema = UMBLER_MESSAGES_SCHEMA if name == "messages" else UMBLER_BRONZE_SCHEMA

        entities[name] = {
            "source":           "UMBLER",
            "entity_type":      "RAW",
            "dataset":          item.get("dataset", UMBLER_BRONZE_DATASET),
            "bq_table":         item.get("bq_table", name),
            "write_mode":       item.get("write_mode", "truncate"),
            "endpoint":         endpoint,
            "pagination_mode":  item.get("pagination_mode", "none"),
            "page_size":        int(item.get("page_size", 100)),
            "record_id_path":   item.get("record_id_path", "id"),
            "event_at_path":    item.get("event_at_path", "eventAtUTC"),
            "data_path":        item.get("data_path", ""),
            "bq_schema":        bq_schema,
        }

    return entities


def get_umbler_bronze_entity_table_id(
    entity_name: str,
    config_path: str | Path | None = None,
) -> str:
    from config.settings import BQ_PROJECT
    entities = load_umbler_bronze_entities(config_path)
    cfg = entities[entity_name]
    return f"{BQ_PROJECT}.{cfg['dataset']}.{cfg['bq_table']}"
