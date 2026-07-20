"""
Conector ClickUp — projeção TIPADA (raw = coluna, sem JSON encapsulado).

Auth: header `Authorization: <token>` (token pessoal pk_…, SEM "Bearer").
A hierarquia team → space → folder/list → task é caminhada AQUI no extract()
(o `depends_on` genérico do runner é de um nível só). Tasks lidas com
`include_closed=true` + `subtasks=true` (regra validada no explore_clickup.py),
o que traz concluídas e subtarefas — onde mora o grosso do Controle de Qualidade.

Os caminhos das colunas (status.status, list.id, creator.username, …) são
resolvidos pelo typed.py via dot-notation, então o conector só busca e devolve
os registros crus. A única transformação é explodir `assignees[]` na ponte
task↔responsável (relação N:N).
"""

from __future__ import annotations

import os

import structlog
from dotenv import load_dotenv

from ingestion.connectors.base import RestConnector

load_dotenv()
logger = structlog.get_logger(__name__)


class ClickUpConnector(RestConnector):
    source_system = "CLICKUP"

    def __init__(self):
        super().__init__(
            base_url=os.environ.get("CLICKUP_BASE_URL", "https://api.clickup.com/api/v2"),
            timeout=int(os.environ.get("CLICKUP_TIMEOUT", "30")),
            pause_seconds=float(os.environ.get("CLICKUP_PAUSE_SECONDS", "0.05")),
        )
        self._token = os.environ.get("CLICKUP_API_TOKEN", "")
        self._team_id: str | None = None
        self._spaces_cache: list[dict] | None = None
        self._lists_cache: list[dict] | None = None
        self._tasks_cache: list[dict] | None = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict:
        if not self._token:
            raise ValueError("CLICKUP_API_TOKEN não configurado no .env.")
        return {"Authorization": self._token}

    def test_connection(self) -> dict:
        teams = self._get("/team").get("teams", [])
        t = teams[0] if teams else {}
        return {
            "status":    "ok",
            "workspace": t.get("name"),
            "team_id":   t.get("id"),
            "members":   len(t.get("members", [])),
        }

    # ── Caminhada da hierarquia (cacheada por execução) ───────────────────────

    def _team_id_(self) -> str:
        if self._team_id is None:
            teams = self._get("/team").get("teams", [])
            if not teams:
                raise ValueError("Nenhum workspace (team) visível para o token ClickUp.")
            self._team_id = str(teams[0]["id"])
        return self._team_id

    def _spaces(self) -> list[dict]:
        if self._spaces_cache is None:
            self._spaces_cache = self._get(
                f"/team/{self._team_id_()}/space", {"archived": "false"}
            ).get("spaces", [])
        return self._spaces_cache

    def _folders(self) -> list[dict]:
        out: list[dict] = []
        for sp in self._spaces():
            out.extend(self._get(f"/space/{sp['id']}/folder", {"archived": "false"}).get("folders", []))
        return out

    def _lists(self) -> list[dict]:
        """Todas as listas (de folder + folderless), garantindo space/folder embutidos."""
        if self._lists_cache is not None:
            return self._lists_cache
        out: list[dict] = []
        for sp in self._spaces():
            sid, sname = sp["id"], sp.get("name")
            for fo in self._get(f"/space/{sid}/folder", {"archived": "false"}).get("folders", []):
                for lst in fo.get("lists", []):
                    lst.setdefault("space", {"id": sid, "name": sname})
                    lst.setdefault("folder", {"id": fo["id"], "name": fo.get("name")})
                    out.append(lst)
            for lst in self._get(f"/space/{sid}/list", {"archived": "false"}).get("lists", []):
                lst.setdefault("space", {"id": sid, "name": sname})
                out.append(lst)
        self._lists_cache = out
        return out

    def _tasks(self) -> list[dict]:
        if self._tasks_cache is not None:
            return self._tasks_cache
        tasks: list[dict] = []
        lists = self._lists()
        for idx, lst in enumerate(lists):
            page = 0
            while True:
                data = self._get(
                    f"/list/{lst['id']}/task",
                    {"page": page, "archived": "false", "include_closed": "true", "subtasks": "true"},
                )
                batch = data.get("tasks", [])
                tasks.extend(batch)
                if data.get("last_page", True) or not batch:
                    break
                page += 1
                self._sleep()
            logger.debug("clickup_list_tasks", list=lst.get("name"), progress=f"{idx + 1}/{len(lists)}", total=len(tasks))
        self._tasks_cache = tasks
        return tasks

    # ── extract ───────────────────────────────────────────────────────────────

    def extract(self, entity_cfg, *, parents=None, since=None) -> list[dict]:
        kind = entity_cfg.get("kind")
        if kind == "spaces":
            return self._spaces()
        if kind == "folders":
            return self._folders()
        if kind == "lists":
            return self._lists()
        if kind == "tasks":
            return self._tasks()
        if kind == "task_assignees":
            out: list[dict] = []
            for t in self._tasks():
                tid = t.get("id")
                for a in t.get("assignees", []):
                    out.append({
                        "task_id":  tid,
                        "user_id":  a.get("id"),
                        "username": a.get("username"),
                        "email":    a.get("email"),
                    })
            return out
        raise NotImplementedError(f"kind '{kind}' não suportado (entidade {entity_cfg.get('name')}).")
