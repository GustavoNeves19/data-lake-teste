"""
API Comercial — FastAPI sobre o BigQuery Nevoni.

Expõe como JSON os mesmos dados da página Comercial do Streamlit, para o
frontend React consumir. Rodar local:

    py -3 -m uvicorn api.main:app --reload --port 8000

(executar da raiz do projeto, para o pacote `api` ser importável)
"""

import logging
import os

from fastapi import FastAPI, Query, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import queries as q
from . import gestao_vista as gv
from . import calendario as cal
from . import visao_geral as vg
from . import financeiro as fin
from . import sac as sac_mod
from . import operacional as op_mod
from . import engenharia as eng_mod
from . import oraculo as ora
from . import performance as perf
from .db import init_db, SessionLocal, engine
from .auth import (
    User,
    backfill_user_access_allowlists,
    bootstrap_admin,
    ensure_user_schema,
    get_current_user,
    renomear_victor_carbonero,
    router as auth_router,
    usuario_pode_acessar_pagina,
    usuario_pode_acessar_recurso,
)
from .admin import router as admin_router
from .metas import router as metas_router
from .price import router as price_router
from .security import decode_token
from .access_catalog import API_PAGE_ACCESS, API_RESOURCE_ACCESS

_log = logging.getLogger("nevoni.api")

app = FastAPI(title="Nevoni 360 API", version="1.1")

# Origens liberadas: localhost no dev; em produção, definir CORS_ORIGINS
# (lista separada por vírgula) com o domínio do front. Sem quebrar o dev.
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Bootstrap: cria tabelas e admin master no primeiro boot ──
@app.on_event("startup")
def _startup() -> None:
    try:
        init_db()
        ensure_user_schema(engine)
        db = SessionLocal()
        try:
            bootstrap_admin(db)
            backfill_user_access_allowlists(db)
            renomear_victor_carbonero(db)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        # Não derruba a API se Postgres estiver fora; login não funcionará
        # até o banco voltar, mas endpoints públicos seguem respondendo.
        _log.warning("bootstrap falhou (Postgres indisponível?): %s", e)


# ── Middleware de autenticação (defesa em profundidade) ──────
# Toda rota /api/* exige cookie de sessão, exceto os endpoints públicos.
# As rotas continuam usando Depends(get_current_user) para obter o user;
# aqui só barramos requisições sem cookie antes mesmo de chegar na rota.
_PUBLIC_API_PATHS = {"/api/health", "/api/auth/login", "/api/oraculo/ready"}

def _pagina_por_api(path: str) -> str | None:
    for prefix, pagina in API_PAGE_ACCESS:
        if path == prefix or path.startswith(f"{prefix}/"):
            return pagina
    return None


def _recurso_por_api(path: str) -> str | None:
    for prefix, recurso in API_RESOURCE_ACCESS:
        if path == prefix or path.startswith(f"{prefix}/"):
            return recurso
    return None


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in _PUBLIC_API_PATHS:
        token = request.cookies.get("nevoni_session")
        if not token:
            return JSONResponse(status_code=401, content={"detail": "não autenticado"})
        payload = None
        try:
            payload = decode_token(token)
        except Exception:  # noqa: BLE001
            return JSONResponse(status_code=401, content={"detail": "não autenticado"})
        pagina = _pagina_por_api(path)
        if pagina:
            try:
                user_id = int(payload.get("sub")) if payload else None
            except (TypeError, ValueError):
                user_id = None
            if user_id is None:
                return JSONResponse(status_code=401, content={"detail": "não autenticado"})
            db = SessionLocal()
            try:
                user = db.get(User, user_id)
                if user is None or not user.is_active:
                    return JSONResponse(status_code=401, content={"detail": "não autenticado"})
                if not usuario_pode_acessar_pagina(user, pagina):
                    return JSONResponse(status_code=403, content={"detail": "acesso negado"})
                recurso = _recurso_por_api(path)
                if recurso and not usuario_pode_acessar_recurso(user, recurso):
                    return JSONResponse(status_code=403, content={"detail": "acesso negado"})
            finally:
                db.close()
    return await call_next(request)


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery: {e}") from e


@app.get("/api/health")
def health():
    return {"ok": True}


# ── Visão Geral (Monitor de Cargas) ──────────────────────────
@app.get("/api/visao-geral")
def visao_geral():
    return _guard(vg.visao_geral)


# ── Financeiro ────────────────────────────────────────────────
@app.get("/api/financeiro/kpis")
def financeiro_kpis(regime: str = "CAIXA", ini: str | None = None, fim: str | None = None):
    return _guard(fin.kpis, regime, ini, fim)


@app.get("/api/financeiro/dre")
def financeiro_dre(regime: str = "CAIXA", ini: str | None = None, fim: str | None = None,
                   mes: str | None = None):
    return _guard(fin.dre, regime, ini, fim, mes)


@app.get("/api/financeiro/contas-receber")
def financeiro_cr():
    return _guard(fin.contas_receber)


@app.get("/api/financeiro/contas-pagar")
def financeiro_cp():
    return _guard(fin.contas_pagar)


@app.get("/api/financeiro/liquidacoes")
def financeiro_liq():
    return _guard(fin.liquidacoes)


@app.get("/api/financeiro/fluxo-caixa")
def financeiro_fluxo():
    return _guard(fin.fluxo_caixa)


# ── SAC e Assistência Técnica ─────────────────────────────────
@app.get("/api/sac/atendimentos")
def sac_atendimentos():
    return _guard(sac_mod.atendimentos)


@app.get("/api/sac/sla")
def sac_sla():
    return _guard(sac_mod.sla)


@app.get("/api/sac/chamadas")
def sac_chamadas():
    return _guard(sac_mod.chamadas)


@app.get("/api/sac/chat")
def sac_chat():
    return _guard(sac_mod.chat)


# ── Operacional e Produção ────────────────────────────────────
@app.get("/api/operacional/producao")
def operacional_producao():
    return _guard(op_mod.producao)


@app.get("/api/operacional/componentes")
def operacional_componentes():
    return _guard(op_mod.componentes)


@app.get("/api/operacional/estoque")
def operacional_estoque():
    return _guard(op_mod.estoque)


@app.get("/api/operacional/movimentacao")
def operacional_movimentacao():
    return _guard(op_mod.movimentacao)


@app.get("/api/operacional/bom")
def operacional_bom(parent: str | None = None):
    return _guard(op_mod.bom, parent)


# ── Engenharia e P&D ──────────────────────────────────────────
@app.get("/api/engenharia/catalogo")
def engenharia_catalogo():
    return _guard(eng_mod.catalogo)


@app.get("/api/engenharia/catalogo/itens")
def engenharia_catalogo_itens(q: str | None = None, page: int = 1, page_size: int = 50):
    return _guard(eng_mod.catalogo_itens, q, page, page_size)


@app.get("/api/engenharia/bom")
def engenharia_bom(item_code: str | None = None):
    return _guard(eng_mod.bom, item_code)


@app.get("/api/engenharia/bom/explosao")
def engenharia_bom_explosao(item_code: str):
    return _guard(eng_mod.bom_explosao, item_code)


@app.get("/api/engenharia/seriais")
def engenharia_seriais(item_code: str | None = None):
    return _guard(eng_mod.seriais, item_code)


@app.get("/api/engenharia/roadmap")
def engenharia_roadmap():
    return eng_mod.roadmap()


# ── Oráculo (IA) ──────────────────────────────────────────────
class OraculoReq(BaseModel):
    message: str
    history: list[dict] | None = None


@app.get("/api/oraculo/ready")
def oraculo_ready():
    return {"ready": ora.ready()}


@app.post("/api/oraculo/chat")
def oraculo_chat(req: OraculoReq):
    return _guard(ora.oraculo_chat, req.message, req.history)


# ── Vendas ────────────────────────────────────────────────────
@app.get("/api/comercial/meses")
def meses():
    return _guard(q.meses_disponiveis)


@app.get("/api/comercial/vendas")
def vendas(mes: str = Query(..., description="YYYY-MM-DD (1º dia do mês)"),
           incluir_marketplace: bool = True):
    return _guard(q.vendas, mes, incluir_marketplace)


@app.get("/api/comercial/vendas/periodo")
def vendas_periodo(de: str = Query(..., description="YYYY-MM-DD"),
                   ate: str = Query(..., description="YYYY-MM-DD")):
    return _guard(q.vendas_periodo, de, ate)


# ── Gestão à Vista ────────────────────────────────────────────
@app.get("/api/comercial/gestao-vista/meses")
def gestao_vista_meses():
    return _guard(gv.gestao_vista_meses)


@app.get("/api/comercial/gestao-vista")
def gestao_vista(view: str = "Geral", mes: str | None = None, vendedor: str | None = None,
                 user: User = Depends(get_current_user)):
    # Valores em R$ por vendedor só pra gestor comercial (Vinícius/Alves); os demais
    # recebem o payload já mascarado (só % e status). Reforço no backend.
    ver_valores = bool(user.is_admin or user.pode_editar_metas)
    return _guard(gv.gestao_vista, view, mes, vendedor, ver_valores)


@app.get("/api/comercial/gestao-vista/atividades")
def gv_atividades(de: str, ate: str):
    return _guard(gv.atividades_periodo, de, ate)


@app.get("/api/comercial/performance")
def performance_matriz(mes: str | None = None, user: User = Depends(get_current_user)):
    # Matriz esforço×resultado é só nível gestão (decisão 09/07). Reforço no backend:
    # mesmo que o front exponha a rota, o vendedor recebe 403 e nunca os dados.
    if not (user.is_admin or user.pode_editar_metas):
        raise HTTPException(status_code=403, detail="acesso restrito à gestão comercial")
    return _guard(perf.performance_matriz, mes)


# ── Calendário de Vendas + Faturamento Mensal ────────────────
@app.get("/api/comercial/calendario")
def calendario(mes: str | None = None):
    return _guard(cal.calendario, mes)


@app.get("/api/comercial/faturamento-anual")
def faturamento_anual():
    return _guard(cal.faturamento_anual)


# ── Compras / Orçamentos / Ranking ───────────────────────────
@app.get("/api/comercial/compras")
def compras():
    return _guard(q.compras)


@app.get("/api/comercial/orcamentos")
def orcamentos():
    return _guard(q.orcamentos)


@app.get("/api/comercial/ranking")
def ranking():
    return _guard(q.ranking)


# ── CRM ───────────────────────────────────────────────────────
@app.get("/api/comercial/crm/pipelines")
def crm_pipelines():
    return q.crm_pipelines()


@app.get("/api/comercial/crm")
def crm(pipeline: str = "TODOS"):
    return _guard(q.crm, pipeline)


# ── RFV ───────────────────────────────────────────────────────
@app.get("/api/comercial/qa")
def qa():
    return _guard(q.qa_status)


@app.get("/api/comercial/rfv/periodos")
def rfv_periodos():
    return _guard(q.rfv_periodos)


@app.get("/api/comercial/rfv/carteiras")
def rfv_carteiras(familia: str = "TODOS", periodo: str | None = None):
    return _guard(q.rfv_carteiras, familia, periodo)


@app.get("/api/comercial/rfv")
def rfv(familia: str = "TODOS", carteira: str = "TODOS", periodo: str | None = None):
    return _guard(q.rfv, familia, carteira, periodo)


@app.get("/api/comercial/rfv/segmento")
def rfv_segmento(seg: int, familia: str = "TODOS", carteira: str = "TODOS", periodo: str | None = None):
    return _guard(q.rfv_segmento, seg, familia, carteira, periodo)


@app.get("/api/comercial/rfv/alerta")
def rfv_alerta(tipo: str, familia: str = "TODOS"):
    return _guard(q.rfv_alerta, tipo, familia)


# ── Auth / Admin / Metas ──────────────────────────────────────
# Registrados ANTES do serving estático (catch-all da SPA) para as rotas
# /api/auth, /api/admin e /api/comercial/metas-equipe terem precedência.
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(metas_router)
app.include_router(price_router)


# ── Frontend estático (deploy container único) ────────────────
# DEVE ser o último bloco: o FastAPI serve o build do React na mesma origem
# (sem CORS). As rotas /api acima têm precedência; qualquer outra rota cai no
# index.html (fallback SPA do react-router). Em dev, sem WEB_DIST, não sobe e o
# front roda pelo Vite via proxy.
_WEB_DIST = os.getenv(
    "WEB_DIST",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "dist"),
)
if os.path.isdir(_WEB_DIST):
    _assets = os.path.join(_WEB_DIST, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}")
    def _spa(full_path: str):
        candidate = os.path.join(_WEB_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_WEB_DIST, "index.html"))
