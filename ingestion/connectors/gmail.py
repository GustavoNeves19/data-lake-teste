"""
Conector Gmail — service account com domain-wide delegation, projeção TIPADA.

Impersona N caixas (GMAIL_ACCOUNTS) e extrai via REST da Gmail API v1:
  messages → list incremental (q=after:<data>) + get full por mensagem,
             headers achatados em colunas tipadas (subject, from/to/cc...),
             internalDate (epoch ms) → TIMESTAMP, attachments contados.
  labels   → list + get (contadores por label).

Volume alto (287k+ msgs) → messages é INCREMENTAL por internal_date; full
reload seria 1 GET por mensagem (inviável). O seed do watermark vem do
MAX(internal_date) da própria tabela (ver runner) quando ops ainda não tem.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import structlog
from dotenv import load_dotenv
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from ingestion.connectors.base import RestConnector

load_dotenv()
logger = structlog.get_logger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def _epoch_ms_to_iso(value) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _count_attachments(payload: dict) -> int:
    n = 0
    def walk(p):
        nonlocal n
        if p.get("filename") and (p.get("body") or {}).get("attachmentId"):
            n += 1
        for sub in p.get("parts") or []:
            walk(sub)
    walk(payload or {})
    return n


class GmailConnector(RestConnector):
    source_system = "GMAIL"

    def __init__(self):
        super().__init__(
            base_url=_API,
            timeout=int(os.environ.get("GMAIL_TIMEOUT", "30")),
            pause_seconds=float(os.environ.get("GMAIL_PAUSE_SECONDS", "0.02")),
        )
        self._sa_file = os.environ["GMAIL_SERVICE_ACCOUNT_FILE"]
        self._accounts = [a.strip() for a in os.environ.get("GMAIL_ACCOUNTS", "").split(",") if a.strip()]
        self._base_query = os.environ.get("GMAIL_QUERY", "").strip()
        self._page_size = int(os.environ.get("GMAIL_PAGE_SIZE", "500"))
        self._creds: dict = {}

    # ── Auth por conta (impersonação) ────────────────────────────────────────

    def _token(self, account: str) -> str:
        creds = self._creds.get(account)
        if creds is None:
            creds = service_account.Credentials.from_service_account_file(
                self._sa_file, scopes=_SCOPES, subject=account)
            self._creds[account] = creds
        if not creds.valid:
            creds.refresh(Request())
        return creds.token

    def _auth_headers(self) -> dict:
        # Definido por requisição em _get_account; base não tem conta única.
        return {}

    def _get_account(self, account: str, path: str, params: dict | None = None):
        import requests, time
        url = path if path.startswith("http") else f"{_API}/{path.lstrip('/')}"
        attempt = 0
        while True:
            try:
                token = self._token(account)  # re-auth se o token expirou numa pausa longa
                resp = requests.get(url, headers={"Authorization": f"Bearer {token}"},
                                    params=params or {}, timeout=self._timeout)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    if attempt >= self._max_retries:
                        resp.raise_for_status()
                    time.sleep(min(2 ** attempt, 30)); attempt += 1; continue
                resp.raise_for_status()
                return resp.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                # blip de rede/DNS: backoff e tenta de novo (não derruba a carga toda)
                if attempt >= self._max_retries:
                    raise
                time.sleep(min(2 ** attempt, 30)); attempt += 1

    def test_connection(self) -> dict:
        acct = self._accounts[0]
        prof = self._get_account(acct, "/profile")
        return {"status": "ok", "account": prof.get("emailAddress"),
                "messages_total": prof.get("messagesTotal"), "accounts": len(self._accounts)}

    # ── Extração ─────────────────────────────────────────────────────────────

    def extract(self, entity_cfg, *, parents=None, since=None) -> list[dict]:
        kind = entity_cfg.get("kind")
        if kind == "messages":
            return self._extract_messages(entity_cfg, since)
        if kind == "labels":
            return self._extract_labels(entity_cfg)
        raise NotImplementedError(f"kind '{kind}' não suportado (Gmail).")

    def _build_query(self, since) -> str:
        parts = []
        if since:
            # Gmail after: aceita epoch com precisão de segundo. -1s p/ incluir o
            # próprio watermark (a janela [since, ...] é apagada e re-inserida pelo
            # delete_window, garantindo idempotência sem timezone nem dups).
            d = since if isinstance(since, datetime) else datetime.fromisoformat(str(since).replace("Z", "+00:00"))
            parts.append(f"after:{int(d.timestamp()) - 1}")
        if self._base_query:
            parts.append(self._base_query)
        return " ".join(parts)

    def _extract_messages(self, entity_cfg, since) -> list[dict]:
        query = self._build_query(since)
        out: list[dict] = []
        for account in self._accounts:
            ids = self._list_message_ids(account, query)
            logger.info("gmail_list_done", account=account, query=query, ids=len(ids))
            consec_fail, total_fail = 0, 0
            for i, mid in enumerate(ids):
                try:
                    msg = self._get_account(account, f"/messages/{mid}", {"format": "full"})
                    out.append(self._flatten_message(msg, account))
                    consec_fail = 0
                except Exception as e:  # noqa: BLE001 — get isolado falhou (já passou pelo retry)
                    consec_fail += 1; total_fail += 1
                    logger.error("gmail_get_error", account=account, mid=mid, error=str(e)[:160])
                    # Circuit breaker: falha SISTÊMICA (rede caiu) → aborta a entidade
                    # inteira para o runner NÃO carregar dados parciais (delete-window
                    # apagaria a janela e re-inseriria incompleto).
                    if consec_fail >= 15:
                        raise RuntimeError(
                            f"Gmail abortado: {consec_fail} falhas consecutivas em {account} "
                            f"(rede instável). Nada será carregado — rode de novo quando estabilizar."
                        )
                if self._pause_seconds and i % 10 == 0:
                    self._sleep()
            if total_fail:
                logger.warning("gmail_account_partial", account=account, failed=total_fail, total=len(ids))
        return out

    def _list_message_ids(self, account: str, query: str) -> list[str]:
        ids, page_token = [], None
        while True:
            params = {"maxResults": self._page_size}
            if query:
                params["q"] = query
            if page_token:
                params["pageToken"] = page_token
            data = self._get_account(account, "/messages", params)
            ids.extend(m["id"] for m in data.get("messages", []) or [])
            page_token = data.get("nextPageToken")
            if not page_token:
                break
            self._sleep()
        return ids

    def _flatten_message(self, msg: dict, account: str) -> dict:
        payload = msg.get("payload") or {}
        hdrs = {h["name"].lower(): h["value"] for h in payload.get("headers", []) or []}
        att = _count_attachments(payload)
        return {
            "id":            msg.get("id"),
            "threadId":      msg.get("threadId"),
            "historyId":     msg.get("historyId"),
            "internal_date": _epoch_ms_to_iso(msg.get("internalDate")),
            "sizeEstimate":  msg.get("sizeEstimate"),
            "snippet":       msg.get("snippet"),
            "labelIds":      msg.get("labelIds"),
            "subject":       hdrs.get("subject"),
            "from":          hdrs.get("from"),
            "to":            hdrs.get("to"),
            "cc":            hdrs.get("cc"),
            "bcc":           hdrs.get("bcc"),
            "reply_to":      hdrs.get("reply-to"),
            "in_reply_to":   hdrs.get("in-reply-to"),
            "email_date":    hdrs.get("date"),
            "email_message_id": hdrs.get("message-id"),
            "mime_type":     payload.get("mimeType"),
            "has_attachments": att > 0,
            "attachment_count": att,
            "source_account": account,
        }

    def _extract_labels(self, entity_cfg) -> list[dict]:
        out = []
        for account in self._accounts:
            data = self._get_account(account, "/labels")
            for lab in data.get("labels", []) or []:
                detail = self._get_account(account, f"/labels/{lab['id']}")
                out.append({**detail, "source_account": account})
        return out
