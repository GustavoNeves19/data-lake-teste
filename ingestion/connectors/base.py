"""
Contrato de conector + base REST.

A diferença entre fontes mora AQUI e só aqui. Tudo a jusante (envelope bronze,
carga, watermark, freshness) é compartilhado pelo runner.

    SourceConnector  — contrato mínimo: test_connection() + extract().
    RestConnector    — base p/ APIs HTTP: GET com retry/backoff e paginação
                       genérica (none | skip_take | page). Auth e parâmetros
                       específicos da fonte são pontos de extensão (métodos
                       sobrescrevíveis), nunca hardcode no loop.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests
import structlog

logger = structlog.get_logger(__name__)

# Falhas transitórias que merecem retry com backoff: rate-limit (429) e 5xx.
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
# Auth/autorização: erro de credencial não melhora com retry — falha rápido.
_FAIL_FAST_STATUS_CODES = {401, 403}


class SourceConnector(ABC):
    """Contrato que todo conector de fonte implementa."""

    #: rótulo da fonte gravado em bronze.source_system (UMBLER, PIPEDRIVE, ...)
    source_system: str = ""

    @abstractmethod
    def test_connection(self) -> dict:
        """Valida credenciais/conectividade. Levanta em caso de falha."""

    @abstractmethod
    def extract(
        self,
        entity_cfg: dict,
        *,
        parents: list[dict] | None = None,
        since: str | None = None,
    ) -> list[dict]:
        """
        Extrai os registros crus de uma entidade.

        Args:
            entity_cfg: config normalizada da entidade (ver registry).
            parents:    registros da entidade-pai (para paginação aninhada).
            since:      watermark incremental (ISO 8601 UTC) ou None p/ carga cheia.
        """

    def context(self) -> dict:
        """Constantes da fonte expostas como colunas extras (ex: organization_id)."""
        return {}


class RestConnector(SourceConnector):
    """
    Base para fontes REST. Subclasses definem auth e parâmetros da fonte
    sobrescrevendo `_auth_headers`, `_auth_params` e `_base_params`.
    """

    # Nomes dos parâmetros de paginação — sobrescrevíveis por fonte.
    skip_param = "Skip"
    take_param = "Take"
    page_param = "page"
    per_page_param = "per_page"

    def __init__(
        self,
        *,
        base_url: str,
        timeout: int = 30,
        pause_seconds: float = 0.3,
        max_retries: int = 3,
        backoff_base: float = 2.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._pause_seconds = pause_seconds
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    def _backoff_seconds(self, attempt: int) -> float:
        """Backoff exponencial: 2, 4, 8, ... segundos (attempt começa em 0)."""
        return self._backoff_base * (2 ** attempt)

    # ── Pontos de extensão por fonte ─────────────────────────────────────────

    def _auth_headers(self) -> dict:
        return {}

    def _auth_params(self) -> dict:
        return {}

    def _base_params(self, entity_cfg: dict) -> dict:
        """Parâmetros fixos por requisição da fonte (ex: organizationId)."""
        return {}

    # ── HTTP primitivo com retry/backoff ─────────────────────────────────────

    def _get(self, path: str, params: dict | None = None):
        # path pode ser relativo (junta ao base_url) ou URL absoluta (multi-base: v1/v2)
        url = path if path.startswith("http") else f"{self._base_url}/{path.lstrip('/')}"
        headers = self._auth_headers()
        merged = {**self._auth_params(), **(params or {})}

        # attempt 0..max_retries → até (max_retries + 1) chamadas no total.
        # Com max_retries=3 e backoff_base=2: dorme 2s, 4s, 8s entre as tentativas.
        attempt = 0
        while True:
            try:
                resp = requests.get(url, headers=headers, params=merged, timeout=self._timeout)

                # Auth/autorização: não adianta repetir — propaga o erro imediatamente.
                if resp.status_code in _FAIL_FAST_STATUS_CODES:
                    logger.error("rest_auth_failed", url=url, status=resp.status_code)
                    resp.raise_for_status()

                # Transitório (429 / 5xx): retry com backoff até esgotar as tentativas.
                if resp.status_code in _RETRY_STATUS_CODES:
                    if attempt >= self._max_retries:
                        logger.error("rest_retry_exhausted", url=url,
                                     status=resp.status_code, attempts=attempt + 1)
                        resp.raise_for_status()
                    wait = self._backoff_seconds(attempt)
                    logger.warning("rest_retry", url=url, status=resp.status_code,
                                   attempt=attempt + 1, wait_seconds=wait)
                    time.sleep(wait)
                    attempt += 1
                    continue

                # Demais 4xx (e qualquer outro status de erro) → falha rápido, sem retry.
                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.HTTPError:
                # Erros de status já foram classificados acima — não fazemos retry aqui.
                raise
            except requests.exceptions.RequestException as exc:
                # Falha de rede transitória: timeout, connection error, DNS, etc.
                if attempt >= self._max_retries:
                    logger.error("rest_request_error_exhausted", url=url,
                                 attempts=attempt + 1, error=str(exc))
                    raise
                wait = self._backoff_seconds(attempt)
                logger.warning("rest_request_error", url=url, attempt=attempt + 1,
                               wait_seconds=wait, error=str(exc))
                time.sleep(wait)
                attempt += 1

    @staticmethod
    def _records_from_response(data, data_path: str) -> list[dict]:
        """Extrai a lista de registros da resposta, tolerante a formatos comuns."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if data_path and isinstance(data.get(data_path), list):
                return data[data_path]
            for key in ("items", "data", "results"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data] if data else []
        return []

    def _sleep(self) -> None:
        if self._pause_seconds > 0:
            time.sleep(self._pause_seconds)

    # ── Estratégias de paginação ─────────────────────────────────────────────

    def _fetch_none(self, entity_cfg: dict) -> list[dict]:
        data = self._get(entity_cfg["endpoint"], self._base_params(entity_cfg))
        return self._records_from_response(data, entity_cfg.get("data_path", ""))

    def _fetch_skip_take(self, entity_cfg: dict) -> list[dict]:
        page_size = entity_cfg.get("page_size", 100)
        data_path = entity_cfg.get("data_path", "items")
        out: list[dict] = []
        skip, page = 0, 0
        while True:
            params = {**self._base_params(entity_cfg), self.take_param: page_size, self.skip_param: skip}
            data = self._get(entity_cfg["endpoint"], params)
            records = self._records_from_response(data, data_path)
            if not records:
                break
            out.extend(records)
            page += 1
            logger.debug("rest_skip_take_page", entity=entity_cfg["name"], page=page, total=len(out))
            if len(records) < page_size:
                break
            skip += page_size
            self._sleep()
        return out

    def _fetch_page(self, entity_cfg: dict) -> list[dict]:
        page_size = entity_cfg.get("page_size", 100)
        data_path = entity_cfg.get("data_path", "data")
        out: list[dict] = []
        page = 1
        while True:
            params = {**self._base_params(entity_cfg), self.per_page_param: page_size, self.page_param: page}
            data = self._get(entity_cfg["endpoint"], params)
            records = self._records_from_response(data, data_path)
            if not records:
                break
            out.extend(records)
            if len(records) < page_size:
                break
            page += 1
            self._sleep()
        return out

    # ── Dispatch ─────────────────────────────────────────────────────────────

    def extract(self, entity_cfg, *, parents=None, since=None) -> list[dict]:
        mode = entity_cfg.get("pagination_mode", "none")
        if mode == "none":
            return self._fetch_none(entity_cfg)
        if mode == "skip_take":
            return self._fetch_skip_take(entity_cfg)
        if mode == "page":
            return self._fetch_page(entity_cfg)
        raise NotImplementedError(
            f"pagination_mode '{mode}' exige override de extract() no conector "
            f"(entidade '{entity_cfg.get('name')}')."
        )
