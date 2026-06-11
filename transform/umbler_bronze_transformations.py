"""
Transformacoes da camada bronze da Umbler Talk.
Preserva o payload cru em JSON string e adiciona metadados de ingestao.
Compativel com UMBLER_BRONZE_SCHEMA e UMBLER_MESSAGES_SCHEMA em config/umbler.py.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd


def _coerce_str(value) -> str | None:
    if value is None:
        return None
    return str(value)


def _coerce_timestamp(value) -> str | None:
    """Normaliza strings ISO 8601 para formato compativel com BigQuery TIMESTAMP."""
    if not value:
        return None
    try:
        # Tenta parse direto — retorna como string ISO para o BQ inferir
        if isinstance(value, str):
            # Remove sufixo Z se presente e re-adiciona para garantir UTC
            return value.rstrip("Z") + "Z" if value else None
        return None
    except Exception:
        return None


def _json_dumps(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)


def build_umbler_bronze_dataframe(
    records: list[dict],
    entity_name: str,
    entity_cfg: dict,
    extract_run_id: str,
    organization_id: str,
) -> pd.DataFrame:
    """
    Constroi DataFrame bronze para channels e chats.
    Schema: UMBLER_BRONZE_SCHEMA (sem chat_id).
    """
    loaded_at = datetime.now(timezone.utc).isoformat()
    record_id_path  = entity_cfg.get("record_id_path", "id")
    event_at_path   = entity_cfg.get("event_at_path", "eventAtUTC")
    source_endpoint = entity_cfg.get("endpoint", entity_name)

    rows = []
    for record in records:
        rows.append({
            "extract_run_id":  extract_run_id,
            "etl_loaded_at":   loaded_at,
            "source_system":   "UMBLER",
            "organization_id": organization_id,
            "entity_name":     entity_name,
            "source_endpoint": source_endpoint,
            "record_id":       _coerce_str(record.get(record_id_path)),
            "record_event_at": _coerce_timestamp(record.get(event_at_path)) if event_at_path else None,
            "payload_json":    _json_dumps(record),
        })

    return pd.DataFrame(rows)


def _strip_message_pii(message: dict) -> dict:
    """
    Remove campos de conteudo pessoal para conformidade LGPD.

    Removido:
        - content       : texto integral da mensagem (dado pessoal do cliente)
        - file.url      : URL pre-assinada de acesso ao arquivo de midia

    Mantido (metadado operacional):
        - messageType, source, messageState, eventAtUTC, createdAtUTC
        - file.contentType, file.originalName, file.originalSizeBytes
        - sentByOrganizationMember, isPrivate, chat.id, etc.
    """
    record = dict(message)
    record.pop("content", None)
    if isinstance(record.get("file"), dict):
        record["file"] = {k: v for k, v in record["file"].items() if k != "url"}
    return record


def build_umbler_messages_dataframe(
    chat_message_pairs: list[tuple[str, dict]],
    entity_cfg: dict,
    extract_run_id: str,
    organization_id: str,
) -> pd.DataFrame:
    """
    Constroi DataFrame bronze para messages.
    Schema: UMBLER_MESSAGES_SCHEMA (inclui chat_id).

    Campos de conteudo pessoal (content, file.url) sao removidos antes
    da serializacao para conformidade LGPD — decisao registrada em
    UMBLER_ARCHITECTURE.md.
    """
    loaded_at = datetime.now(timezone.utc).isoformat()
    record_id_path  = entity_cfg.get("record_id_path", "id")
    event_at_path   = entity_cfg.get("event_at_path", "eventAtUTC")
    source_endpoint = entity_cfg.get("endpoint", "messages")

    rows = []
    for chat_id, message in chat_message_pairs:
        clean_message = _strip_message_pii(message)
        rows.append({
            "extract_run_id":  extract_run_id,
            "etl_loaded_at":   loaded_at,
            "source_system":   "UMBLER",
            "organization_id": organization_id,
            "chat_id":         chat_id,
            "entity_name":     "messages",
            "source_endpoint": source_endpoint,
            "record_id":       _coerce_str(message.get(record_id_path)),
            "record_event_at": _coerce_timestamp(message.get(event_at_path)) if event_at_path else None,
            "payload_json":    _json_dumps(clean_message),
        })

    return pd.DataFrame(rows)
