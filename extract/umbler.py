"""
Extrator Umbler Talk — Bearer token estatico.

Endpoints:
    GET /v1/channels/                              → lista de canais (sem paginacao)
    GET /v1/chats/                                 → chats (paginacao Skip/Take)
    GET /v1/chats/{chatId}/relative-messages/      → mensagens por chat (incremental)

Paginacao:
    - 'none'         → resposta unica (channels)
    - 'skip_take'    → parametros Skip e Take (chats)
    - 'nested_chats' → itera sobre cada chat_id e busca mensagens

Retry:
    Backoff exponencial para 429 e erros 5xx: 1s, 2s, 4s, 8s, 16s (max 30s).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
import structlog

from config.umbler import UMBLER_CONFIG

logger = structlog.get_logger(__name__)

_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5


class UmblerExtractor:
    """
    Extrai dados da API Umbler Talk via Bearer token.

    Pre-requisito: UMBLER_API_TOKEN no .env com token gerado na plataforma.
    """

    def __init__(self):
        self._api_token     = UMBLER_CONFIG["api_token"]
        self._organization_id = UMBLER_CONFIG["organization_id"]
        self._base_url      = UMBLER_CONFIG["base_url"].rstrip("/")
        self._timeout       = UMBLER_CONFIG["timeout"]
        self._pause_seconds = UMBLER_CONFIG["pause_seconds"]
        self._messages_from_utc = UMBLER_CONFIG["messages_from_utc"]

        if not self._api_token:
            import warnings
            warnings.warn(
                "UMBLER_API_TOKEN nao encontrado no .env. "
                "Configure antes de executar extrações.",
                stacklevel=2,
            )

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        if not self._api_token:
            raise ValueError(
                "UMBLER_API_TOKEN nao encontrado no .env. "
                "Configure antes de executar extrações."
            )
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type":  "application/json",
        }

    # ── HTTP primitivo ───────────────────────────────────────────────────────

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        """GET com retry automatico para 429/5xx."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        attempt = 0

        while True:
            try:
                response = requests.get(
                    url,
                    headers=self._auth_headers(),
                    params=params or {},
                    timeout=self._timeout,
                )

                if response.status_code in _RETRY_STATUS_CODES:
                    if attempt >= _MAX_RETRIES:
                        response.raise_for_status()
                    wait = min(2 ** attempt, 30)
                    logger.warning(
                        "umbler_retry",
                        url=url,
                        status=response.status_code,
                        attempt=attempt + 1,
                        wait_seconds=wait,
                    )
                    time.sleep(wait)
                    attempt += 1
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout:
                if attempt >= _MAX_RETRIES:
                    raise
                wait = min(2 ** attempt, 30)
                logger.warning("umbler_timeout", url=url, attempt=attempt + 1)
                time.sleep(wait)
                attempt += 1

            except requests.exceptions.HTTPError:
                raise

            except requests.exceptions.RequestException:
                if attempt >= _MAX_RETRIES:
                    raise
                wait = min(2 ** attempt, 30)
                logger.warning("umbler_request_error", url=url, attempt=attempt + 1)
                time.sleep(wait)
                attempt += 1

    # ── Extracao por modo de paginacao ───────────────────────────────────────

    def get_channels(self, entity_cfg: dict) -> list[dict]:
        """GET /v1/channels/ — retorna lista de canais sem paginacao."""
        params = {"organizationId": self._organization_id}
        data = self._get(entity_cfg["endpoint"], params)

        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # Tenta campos comuns; fallback para lista vazia
            for key in ("channels", "items", "data", "results"):
                if isinstance(data.get(key), list):
                    records = data[key]
                    break
            else:
                # Resposta e o proprio objeto sem wrapper
                records = [data] if data else []
        else:
            records = []

        logger.info("umbler_extract_channels", total=len(records))
        return records

    def get_chats(self, entity_cfg: dict) -> list[dict]:
        """GET /v1/chats/ — paginacao Skip/Take ate esgotar registros."""
        page_size = entity_cfg.get("page_size", 100)
        data_path = entity_cfg.get("data_path", "chats")
        all_records: list[dict] = []
        skip = 0
        page = 0

        while True:
            params = {
                "organizationId": self._organization_id,
                "Take": page_size,
                "Skip": skip,
            }
            data = self._get(entity_cfg["endpoint"], params)

            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = data.get(data_path) or data.get("items") or data.get("data") or []
            else:
                records = []

            if not records:
                break

            all_records.extend(records)
            page += 1
            logger.debug("umbler_chats_page", page=page, count=len(records), total=len(all_records))

            if len(records) < page_size:
                break

            skip += page_size
            if self._pause_seconds > 0:
                time.sleep(self._pause_seconds)

        logger.info("umbler_extract_chats", total=len(all_records), pages=page)
        return all_records

    def get_messages_for_chat(self, chat_id: str, from_utc: str, page_size: int = 100) -> list[dict]:
        """
        GET /v1/chats/{chatId}/relative-messages/ — mensagens de um chat especifico.
        Usa RelativeStartFromEventUTC + RelativeTakeDirection=Forward para carga incremental.
        """
        endpoint = f"/v1/chats/{chat_id}/relative-messages/"
        params = {
            "organizationId":        self._organization_id,
            "Take":                  page_size,
            "RelativeTakeDirection": "Forward",
        }
        if from_utc:
            params["RelativeStartFromEventUTC"] = from_utc

        data = self._get(endpoint, params)

        if isinstance(data, dict):
            messages = data.get("items") or data.get("messages") or data.get("data") or []
        elif isinstance(data, list):
            messages = data
        else:
            messages = []

        return messages

    def get_messages_all_chats(self, chats: list[dict], entity_cfg: dict) -> list[tuple[str, dict]]:
        """
        Itera sobre todos os chats e coleta mensagens incrementalmente.
        Retorna lista de (chat_id, message_record) para manter o chat_id acessivel
        na transformacao bronze.
        """
        from_utc = self._messages_from_utc
        page_size = entity_cfg.get("page_size", 100)
        all_pairs: list[tuple[str, dict]] = []
        total_chats = len(chats)

        if not from_utc:
            logger.warning(
                "umbler_messages_no_from_utc",
                hint="Defina UMBLER_MESSAGES_FROM_UTC no .env (ex: 2025-01-01T00:00:00Z). "
                     "Sem esse parametro nenhuma mensagem sera carregada.",
            )
            return []

        for idx, chat in enumerate(chats):
            chat_id = str(chat.get("id", ""))
            if not chat_id:
                continue

            try:
                messages = self.get_messages_for_chat(chat_id, from_utc, page_size)
                for msg in messages:
                    all_pairs.append((chat_id, msg))

                if messages:
                    logger.debug(
                        "umbler_messages_chat_ok",
                        chat_id=chat_id,
                        count=len(messages),
                        progress=f"{idx + 1}/{total_chats}",
                    )
            except Exception as e:
                logger.error("umbler_messages_chat_error", chat_id=chat_id, error=str(e))

            if self._pause_seconds > 0:
                time.sleep(self._pause_seconds)

        logger.info(
            "umbler_extract_messages",
            total_messages=len(all_pairs),
            chats_processed=total_chats,
            from_utc=from_utc,
        )
        return all_pairs

    # ── Health check ─────────────────────────────────────────────────────────

    def test_connection(self) -> dict:
        """Valida o token chamando GET /v1/members/me/."""
        data = self._get("/v1/members/me/")
        if not isinstance(data, dict):
            raise ValueError(f"Resposta inesperada de /v1/members/me/: {type(data)}")
        return {
            "status":          "ok",
            "display_name":    data.get("displayName"),
            "email":           data.get("emailAddress"),
            "account_id":      data.get("umblerAccountId"),
            "organization_id": self._organization_id,
        }
