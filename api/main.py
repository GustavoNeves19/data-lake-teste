"""
API Comercial — FastAPI sobre o BigQuery Nevoni.

Expõe como JSON os mesmos dados da página Comercial do Streamlit, para o
frontend React consumir. Rodar local:

    py -3 -m uvicorn api.main:app --reload --port 8000

(executar da raiz do projeto, para o pacote `api` ser importável)
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import queries as q

app = FastAPI(title="Nevoni Comercial API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery: {e}") from e


@app.get("/api/health")
def health():
    return {"ok": True}


# ── Vendas ────────────────────────────────────────────────────
@app.get("/api/comercial/meses")
def meses():
    return _guard(q.meses_disponiveis)


@app.get("/api/comercial/vendas")
def vendas(mes: str = Query(..., description="YYYY-MM-DD (1º dia do mês)")):
    return _guard(q.vendas, mes)


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


@app.get("/api/comercial/rfv/vendedores")
def rfv_vendedores(familia: str = "TODOS", periodo: str | None = None):
    return _guard(q.rfv_vendedores, familia, periodo)


@app.get("/api/comercial/rfv")
def rfv(familia: str = "TODOS", vendedor: str = "TODOS", periodo: str | None = None):
    return _guard(q.rfv, familia, vendedor, periodo)


@app.get("/api/comercial/rfv/segmento")
def rfv_segmento(seg: int, familia: str = "TODOS", vendedor: str = "TODOS", periodo: str | None = None):
    return _guard(q.rfv_segmento, seg, familia, vendedor, periodo)


@app.get("/api/comercial/rfv/alerta")
def rfv_alerta(tipo: str, familia: str = "TODOS"):
    return _guard(q.rfv_alerta, tipo, familia)
