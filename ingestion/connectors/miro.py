"""
Conector Miro — projeção ENVELOPE (payload_json).

Os boards têm 21 tipos de item heterogêneos (shape, card, sticky_note, frame,
connector, image…), cada um com `data`/`style`/`geometry` próprios — flatten
tipado seria lossy. Então o bronze guarda o payload cru por registro.

Auth: header `Authorization: Bearer <token>` (access token não-expirável).
Paginação por CURSOR (não nativa no framework) e caminhada por board vivem no
extract(). Itens/membros/tags recebem `_board_id` injetado (vira coluna board_id
no envelope, como o Umbler faz com _chat_id).
"""

from __future__ import annotations

import os

import structlog
from dotenv import load_dotenv

from ingestion.connectors.base import RestConnector

load_dotenv()
logger = structlog.get_logger(__name__)


class MiroConnector(RestConnector):
    source_system = "MIRO"

    def __init__(self):
        super().__init__(
            base_url=os.environ.get("MIRO_BASE_URL", "https://api.miro.com/v2"),
            timeout=int(os.environ.get("MIRO_TIMEOUT", "30")),
            pause_seconds=float(os.environ.get("MIRO_PAUSE_SECONDS", "0.1")),
        )
        self._token = os.environ.get("MIRO_ACCESS_TOKEN", "")
        self._boards_cache: list[dict] | None = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        if not self._token:
            raise ValueError("MIRO_ACCESS_TOKEN não configurado no .env.")
        return {"Authorization": f"Bearer {self._token}"}

    def test_connection(self) -> dict:
        data = self._get("/boards", {"limit": 1})
        return {"status": "ok", "boards_total": data.get("total") if isinstance(data, dict) else None}

    # ── Paginação por cursor ──────────────────────────────────────────────────

    def _cursor(self, path: str, params: dict | None = None) -> list[dict]:
        out: list[dict] = []
        params = dict(params or {})
        while True:
            data = self._get(path, params)
            recs = data.get("data", []) if isinstance(data, dict) else []
            out.extend(recs)
            cursor = data.get("cursor") if isinstance(data, dict) else None
            if not cursor or not recs:
                break
            params["cursor"] = cursor
            self._sleep()
        return out

    def _boards(self) -> list[dict]:
        if self._boards_cache is None:
            self._boards_cache = self._cursor("/boards", {"limit": 50})
        return self._boards_cache

    def _per_board(self, path_tpl: str) -> list[dict]:
        """Caminha todos os boards, injetando _board_id em cada registro filho."""
        out: list[dict] = []
        for b in self._boards():
            bid = b["id"]
            for rec in self._cursor(path_tpl.format(bid=bid), {"limit": 50}):
                rec["_board_id"] = bid
                out.append(rec)
        return out

    # ── extract ───────────────────────────────────────────────────────────────

    def extract(self, entity_cfg, *, parents=None, since=None) -> list[dict]:
        name = entity_cfg.get("name")
        if name == "boards":
            return self._boards()
        if name == "items":
            return self._per_board("/boards/{bid}/items")
        if name == "board_members":
            return self._per_board("/boards/{bid}/members")
        if name == "tags":
            return self._per_board("/boards/{bid}/tags")
        raise NotImplementedError(f"entidade '{name}' não suportada no conector Miro.")
