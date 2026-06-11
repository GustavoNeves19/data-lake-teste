"""
Conector Umbler Talk — conector de REFERÊNCIA do framework.

Auth: Bearer token estático. Parâmetro de fonte: organizationId.
Paginação especial: `nested_chats` (messages = itera chats e busca mensagens
por chat via /v1/chats/{chatId}/relative-messages/).
"""

from __future__ import annotations

import structlog

from config.umbler import UMBLER_CONFIG
from ingestion.connectors.base import RestConnector

logger = structlog.get_logger(__name__)


class UmblerConnector(RestConnector):
    source_system = "UMBLER"

    def __init__(self):
        super().__init__(
            base_url=UMBLER_CONFIG["base_url"],
            timeout=UMBLER_CONFIG["timeout"],
            pause_seconds=UMBLER_CONFIG["pause_seconds"],
        )
        self._api_token = UMBLER_CONFIG["api_token"]
        self._organization_id = UMBLER_CONFIG["organization_id"]
        self._messages_from_utc = UMBLER_CONFIG.get("messages_from_utc", "")

    # ── Auth + parâmetros da fonte ───────────────────────────────────────────

    def _auth_headers(self) -> dict:
        if not self._api_token:
            raise ValueError("UMBLER_API_TOKEN não configurado no .env.")
        return {"Authorization": f"Bearer {self._api_token}", "Content-Type": "application/json"}

    def _base_params(self, entity_cfg: dict) -> dict:
        return {"organizationId": self._organization_id}

    def context(self) -> dict:
        return {"organization_id": self._organization_id}

    def test_connection(self) -> dict:
        data = self._get("/v1/members/me/")
        if not isinstance(data, dict):
            raise ValueError(f"Resposta inesperada de /v1/members/me/: {type(data)}")
        return {
            "status":          "ok",
            "display_name":    data.get("displayName"),
            "email":           data.get("emailAddress"),
            "organization_id": self._organization_id,
        }

    # ── Override: paginação aninhada de messages ─────────────────────────────

    def extract(self, entity_cfg, *, parents=None, since=None) -> list[dict]:
        if entity_cfg.get("pagination_mode") == "nested_chats":
            return self._extract_messages(entity_cfg, parents=parents, since=since)
        return super().extract(entity_cfg, parents=parents, since=since)

    def _extract_messages(self, entity_cfg, *, parents, since) -> list[dict]:
        from_utc = since or self._messages_from_utc
        if not from_utc:
            logger.warning(
                "umbler_messages_no_cursor",
                hint="Defina UMBLER_MESSAGES_FROM_UTC no .env (ex: 2023-01-01T00:00:00Z).",
            )
            return []

        chats = parents or []
        page_size = entity_cfg.get("page_size", 100)
        data_path = entity_cfg.get("data_path", "messages")
        endpoint_tpl = entity_cfg["endpoint"]
        out: list[dict] = []

        for idx, chat in enumerate(chats):
            chat_id = str(chat.get("id", ""))
            if not chat_id:
                continue
            endpoint = endpoint_tpl.replace("{chatId}", chat_id)
            params = {
                **self._base_params(entity_cfg),
                self.take_param: page_size,
                "RelativeTakeDirection": "Forward",
                "RelativeStartFromEventUTC": from_utc,
            }
            try:
                data = self._get(endpoint, params)
                messages = self._records_from_response(data, data_path)
                for msg in messages:
                    msg["_chat_id"] = chat_id   # vira coluna extra chat_id no bronze
                    out.append(msg)
                if messages:
                    logger.debug("umbler_messages_chat", chat_id=chat_id,
                                 count=len(messages), progress=f"{idx + 1}/{len(chats)}")
            except Exception as e:  # noqa: BLE001 — um chat ruim não derruba a entidade
                logger.error("umbler_messages_chat_error", chat_id=chat_id, error=str(e))
            self._sleep()

        logger.info("umbler_messages_extracted", total=len(out), chats=len(chats), from_utc=from_utc)
        return out
