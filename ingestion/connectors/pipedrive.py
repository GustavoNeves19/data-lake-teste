"""
Conector Pipedrive (CRM) — projeção TIPADA (raw = coluna, sem JSON encapsulado).

Auth: header `x-api-token`. Deals via API v2 (campos padrão batem 1:1 com o
crm_raw, inclusive local_*_date prontos). Dims/dealFields via v1.

Custom fields: cada deal v2 traz `custom_fields` keyed por hash. O conector lê
`/dealFields` (hash→nome→tipo→opções) e ACHATA cada deal:
  enum/set  → label (resolvido via options)
  monetary  → 2 colunas: cf_<slug>_value (FLOAT64) + cf_<slug>_currency (STRING)
  date/varchar/text/double → valor direto
A coluna alvo é `cf_` + slug ASCII do nome do campo (ex: "CNPJ / CPF" → cf_cnpj__cpf).

O slug e o mapa de tipos vivem AQUI (fonte única); o gerador de config
(scripts/gen_pipedrive_source.py) importa daqui para escrever a config.
"""

from __future__ import annotations

import os
import re
import unicodedata

import structlog
from dotenv import load_dotenv

from ingestion.connectors.base import RestConnector

load_dotenv()
logger = structlog.get_logger(__name__)


# ── Slug + tipos (fonte única, usada também pelo gerador) ─────────────────────

def cf_slug(name: str) -> str:
    """'CNPJ / CPF' → 'cnpj__cpf'. ASCII, lower, remove ?/(), espaço→_ (1:1)."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = re.sub(r"[/?()%.,;:!]", "", s)
    s = re.sub(r"[\s\-]", "_", s)
    s = re.sub(r"_+", lambda m: m.group(0), s)  # preserva runs (cnpj__cpf)
    return s


# Pipedrive field_type → tipo BigQuery (monetary é tratado à parte com split).
_FIELD_TYPE_MAP = {
    "varchar": "STRING", "varchar_auto": "STRING", "text": "STRING",
    "enum": "STRING", "set": "STRING", "phone": "STRING", "address": "STRING",
    "date": "DATE", "double": "FLOAT64", "monetary": "FLOAT64",
}


def cf_columns_for_field(field: dict) -> list[dict]:
    """
    Dada a definição de um custom field do /dealFields, retorna a(s) coluna(s)
    tipada(s) que ele gera. `_cf` carrega metadados de flatten p/ o conector.
    """
    name = field.get("name", "")
    key = field["key"]
    ftype = field.get("field_type", "varchar")
    slug = cf_slug(name)
    options = {str(o["id"]): o["label"] for o in (field.get("options") or [])}

    if ftype == "monetary":
        return [
            {"name": f"cf_{slug}_value", "type": "FLOAT64",
             "_cf": {"hash": key, "ftype": ftype, "part": "value"}},
            {"name": f"cf_{slug}_currency", "type": "STRING",
             "_cf": {"hash": key, "ftype": ftype, "part": "currency"}},
        ]
    return [{
        "name": f"cf_{slug}", "type": _FIELD_TYPE_MAP.get(ftype, "STRING"),
        "_cf": {"hash": key, "ftype": ftype, "options": options},
    }]


# ── Colunas padrão do deal (v2) → schema do crm_raw ──────────────────────────
# (path no registro v2; pipeline_id da tabela é injetado como _table_pipeline_id)

STANDARD_DEAL_COLUMNS: list[dict] = [
    {"name": "pipeline_id",        "path": "_table_pipeline_id", "type": "INT64"},
    {"name": "deal_id",            "path": "id",              "type": "INT64"},
    {"name": "title",              "path": "title",           "type": "STRING"},
    {"name": "creator_user_id",    "path": "creator_user_id", "type": "INT64"},
    {"name": "value",              "path": "value",           "type": "FLOAT64"},
    {"name": "currency",           "path": "currency",        "type": "STRING"},
    {"name": "person_id",          "path": "person_id",       "type": "INT64"},
    {"name": "org_id",             "path": "org_id",          "type": "INT64"},
    {"name": "stage_id",           "path": "stage_id",        "type": "INT64"},
    {"name": "status",             "path": "status",          "type": "STRING"},
    {"name": "probability",        "path": "probability",     "type": "FLOAT64"},
    {"name": "lost_reason",        "path": "lost_reason",     "type": "STRING"},
    {"name": "visible_to",         "path": "visible_to",      "type": "STRING"},
    {"name": "close_time",         "path": "close_time",      "type": "TIMESTAMP"},
    {"name": "pipeline_id_deal",   "path": "pipeline_id",     "type": "INT64"},
    {"name": "won_time",           "path": "won_time",        "type": "TIMESTAMP"},
    {"name": "lost_time",          "path": "lost_time",       "type": "TIMESTAMP"},
    {"name": "stage_change_time",  "path": "stage_change_time", "type": "TIMESTAMP"},
    {"name": "local_won_date",     "path": "local_won_date",  "type": "DATE"},
    {"name": "local_lost_date",    "path": "local_lost_date", "type": "DATE"},
    {"name": "local_close_date",   "path": "local_close_date", "type": "DATE"},
    {"name": "expected_close_date", "path": "expected_close_date", "type": "DATE"},
    {"name": "owner_id",           "path": "owner_id",        "type": "INT64"},
    {"name": "label_ids",          "path": "label_ids",       "type": "STRING", "transform": "array_join"},
    {"name": "is_deleted",         "path": "is_deleted",      "type": "BOOL"},
    {"name": "origin",             "path": "origin",          "type": "STRING"},
    {"name": "origin_id",          "path": "origin_id",       "type": "STRING"},
    {"name": "channel",            "path": "channel",         "type": "STRING"},
    {"name": "channel_id",         "path": "channel_id",      "type": "STRING"},
    {"name": "acv",                "path": "acv",             "type": "FLOAT64"},
    {"name": "arr",                "path": "arr",             "type": "FLOAT64"},
    {"name": "mrr",                "path": "mrr",             "type": "FLOAT64"},
    {"name": "is_archived",        "path": "is_archived",     "type": "BOOL"},
    {"name": "archive_time",       "path": "archive_time",    "type": "TIMESTAMP"},
    {"name": "add_time",           "path": "add_time",        "type": "TIMESTAMP"},
    {"name": "update_time",        "path": "update_time",     "type": "TIMESTAMP"},
]


def _norm_id(value):
    """owner_id/person_id às vezes vêm como objeto {id, ...} (v1) ou int (v2)."""
    if isinstance(value, dict):
        return value.get("id") or value.get("value")
    return value


class PipedriveConnector(RestConnector):
    source_system = "PIPEDRIVE"

    def __init__(self):
        token = os.environ.get("PIPEDRIVE_API_TOKEN", "")
        raw = os.environ.get("PIPEDRIVE_BASE_URL", "https://api.pipedrive.com/api/v2")
        self._v2 = raw if "/api/v2" in raw else raw.rstrip("/") + "/api/v2"
        self._v1 = self._v2.replace("/api/v2", "/api/v1")
        super().__init__(
            base_url=self._v2,
            timeout=int(os.environ.get("PIPEDRIVE_TIMEOUT", "30")),
            pause_seconds=float(os.environ.get("PIPEDRIVE_PAUSE_SECONDS", "0.2")),
        )
        self._token = token
        self._fields_cache: dict | None = None

    def _auth_headers(self) -> dict:
        if not self._token:
            raise ValueError("PIPEDRIVE_API_TOKEN não configurado no .env.")
        return {"x-api-token": self._token}

    def test_connection(self) -> dict:
        data = self._get(self._v1 + "/users", {"limit": 1})
        users = data.get("data") or []
        return {"status": "ok", "api": "v1+v2", "sample_user": users[0].get("name") if users else None}

    # ── dealFields (hash → flatten meta) ─────────────────────────────────────

    def deal_fields(self) -> list[dict]:
        """Lista crua de custom fields (key 40-hex) do /dealFields v1 (cacheada)."""
        if self._fields_cache is None:
            data = self._get(self._v1 + "/dealFields", {"limit": 500})
            self._fields_cache = [f for f in (data.get("data") or [])
                                  if len(str(f.get("key", ""))) == 40]
        return self._fields_cache

    def _flatten_map(self) -> dict[str, dict]:
        """hash → metadados de flatten (a partir das colunas geradas)."""
        out: dict[str, list[dict]] = {}
        for field in self.deal_fields():
            for col in cf_columns_for_field(field):
                out.setdefault(col["_cf"]["hash"], []).append({"name": col["name"], **col["_cf"]})
        return out

    # ── Paginação ────────────────────────────────────────────────────────────

    def _paginate_v2(self, path: str, params: dict) -> list[dict]:
        out, cursor = [], None
        while True:
            p = {**params, "limit": 500}
            if cursor:
                p["cursor"] = cursor
            data = self._get(self._v2 + path, p)
            out.extend(data.get("data") or [])
            cursor = (data.get("additional_data") or {}).get("next_cursor")
            if not cursor:
                break
            self._sleep()
        return out

    def _paginate_v1(self, path: str, params: dict) -> list[dict]:
        out, start = [], 0
        while True:
            data = self._get(self._v1 + path, {**params, "limit": 500, "start": start})
            out.extend(data.get("data") or [])
            pg = (data.get("additional_data") or {}).get("pagination") or {}
            if not pg.get("more_items_in_collection"):
                break
            start = pg.get("next_start", start + 500)
            self._sleep()
        return out

    # ── Flatten de custom fields de um deal ──────────────────────────────────

    def _flatten_deal(self, deal: dict, flat_map: dict, table_pipeline_id: int) -> dict:
        rec = dict(deal)
        rec["_table_pipeline_id"] = table_pipeline_id
        rec["owner_id"] = _norm_id(deal.get("owner_id"))
        rec["person_id"] = _norm_id(deal.get("person_id"))
        rec["org_id"] = _norm_id(deal.get("org_id"))
        rec["creator_user_id"] = _norm_id(deal.get("creator_user_id"))

        cfs = deal.get("custom_fields") or {}
        for h, targets in flat_map.items():
            raw = cfs.get(h)
            for t in targets:
                rec[t["name"]] = _resolve_cf(raw, t)
        return rec

    # ── extract ──────────────────────────────────────────────────────────────

    def extract(self, entity_cfg, *, parents=None, since=None) -> list[dict]:
        kind = entity_cfg.get("kind")
        if kind == "deals":
            pid = entity_cfg["pipeline_id"]
            deals = self._paginate_v2("/deals", {"pipeline_id": pid})
            flat_map = self._flatten_map()
            return [self._flatten_deal(d, flat_map, pid) for d in deals]
        if kind == "stages":
            return self._paginate_v1("/stages", {})
        if kind == "users":
            return (self._get(self._v1 + "/users", {"limit": 500}).get("data") or [])
        if kind == "organizations":
            return [_norm_org(o) for o in self._paginate_v1("/organizations", {})]
        if kind == "persons":
            return [_norm_person(p) for p in self._paginate_v1("/persons", {})]
        raise NotImplementedError(f"kind '{kind}' não suportado (entidade {entity_cfg.get('name')}).")


# ── Resolução de valor de custom field ───────────────────────────────────────

def _resolve_cf(raw, target: dict):
    if raw is None:
        return None
    ftype = target.get("ftype")
    if ftype == "enum":
        return target.get("options", {}).get(str(raw), raw)
    if ftype == "set":
        ids = raw if isinstance(raw, list) else [raw]
        opts = target.get("options", {})
        return ",".join(opts.get(str(i), str(i)) for i in ids) or None
    if ftype == "monetary":
        if isinstance(raw, dict):
            return raw.get("value") if target.get("part") == "value" else raw.get("currency")
        return raw if target.get("part") == "value" else None
    return raw


def _norm_org(o: dict) -> dict:
    return {"id": o.get("id"), "name": o.get("name"), "address": o.get("address"),
            "owner_id": _norm_id(o.get("owner_id")),
            "active_flag": o.get("active_flag")}


def _norm_person(p: dict) -> dict:
    emails = p.get("email") or []
    phones = p.get("phone") or []
    email = emails[0].get("value") if isinstance(emails, list) and emails and isinstance(emails[0], dict) else None
    phone = phones[0].get("value") if isinstance(phones, list) and phones and isinstance(phones[0], dict) else None
    org = p.get("org_id")
    return {"id": p.get("id"), "name": p.get("name"), "phone": phone, "email": email,
            "org_id": org.get("value") if isinstance(org, dict) else _norm_id(org),
            "owner_id": _norm_id(p.get("owner_id")), "active_flag": p.get("active_flag")}
