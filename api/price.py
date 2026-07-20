"""
Painel PRICE — lucro líquido / margem por produto × canal.

Nasce da reunião 07/07/2026. Cruza duas camadas do BigQuery (dataset gold_price):
  • gold_price_margem   — FATOS do ERP (faturamento, quantidade, ICMS, IPI, custo
                          médio ponderado por venda — validado via SSMS 14/07/2026).
  • param_price_custos  — camada MANUAL editável pelos 4 admins: override de custo
                          quando o ERP não calculou pra aquele item×canal×mês, e os
                          componentes que o ERP ainda não expõe (% Ads / comissão /
                          IRPJ-CSLL / crédito ICMS-IPI / outras).

A margem é calculada AQUI (Python) — fonte única da fórmula — para que a edição
de um custo reflita imediatamente: a gold de fatos fica em cache de 1h, mas a
param é lida SEM cache a cada request. Ver docs/PAINEL_PRICE.md.

Acesso: require_admin (só admin — sem flag dedicado, ver docs/PAINEL_PRICE.md).
Escrita gravada em BigQuery via MERGE (mesmo padrão de dashboard/utils/metas_store.py).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import bigquery
from pydantic import BaseModel, Field, field_validator

from .auth import require_admin
from .bq import get_client, query, PROJECT_PROD

DATASET = f"{PROJECT_PROD}.gold_price"
T_MARGEM = f"{DATASET}.gold_price_margem"
T_MARGEM_UF = f"{DATASET}.gold_price_margem_uf"
T_PARAM = f"{DATASET}.param_price_custos"

# Campos manuais editáveis (custo unitário em R$ + percentuais sobre faturamento).
_PARAM_FLOATS = (
    "custo_peca", "pct_ads", "pct_comissao",
    "pct_irpj_csll", "pct_irpj", "pct_csll", "pct_pis", "pct_cofins",
    "pct_credito_icms_ipi", "pct_credito_icms", "pct_credito_ipi",
    "mao_obra_unit", "pct_custo_fixo", "pct_outras",
)

_MES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


def _num(v, default=0.0) -> float:
    """float JSON-safe (NaN/None/inf -> default)."""
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _ensure_param_table() -> None:
    """Cria param_price_custos se ainda não existir (DDL idêntico ao build gold)."""
    get_client().query(f"""
        CREATE TABLE IF NOT EXISTS `{T_PARAM}` (
          item_code            STRING  NOT NULL,
          canal                STRING  NOT NULL,
          mes                  DATE    NOT NULL,
          custo_peca           FLOAT64,
          pct_ads              FLOAT64,
          pct_comissao         FLOAT64,
          pct_irpj_csll        FLOAT64,
          pct_irpj             FLOAT64,
          pct_csll             FLOAT64,
          pct_pis              FLOAT64,
          pct_cofins           FLOAT64,
          pct_credito_icms_ipi FLOAT64,
          pct_credito_icms     FLOAT64,
          pct_credito_ipi      FLOAT64,
          mao_obra_unit        FLOAT64,
          pct_custo_fixo       FLOAT64,
          pct_outras           FLOAT64,
          updated_by           STRING,
          updated_at           TIMESTAMP
        )
    """).result()
    for col in (
        "pct_irpj", "pct_csll", "pct_pis", "pct_cofins",
        "pct_credito_icms", "pct_credito_ipi", "mao_obra_unit", "pct_custo_fixo",
    ):
        get_client().query(f"ALTER TABLE `{T_PARAM}` ADD COLUMN IF NOT EXISTS {col} FLOAT64").result()


def meses() -> list[dict]:
    """Meses disponíveis na gold de fatos (mais recente primeiro)."""
    df = query(f"SELECT DISTINCT mes FROM `{T_MARGEM}` ORDER BY mes DESC")
    out = []
    for m in pd.to_datetime(df["mes"]).dt.date.tolist():
        out.append({"value": str(m), "label": f"{_MES_PT[m.month]}/{m.year}"})
    return out


def _param_do_mes(mes_iso: str) -> pd.DataFrame:
    """Lê a param do mês SEM cache (edições refletem na hora). Vazio se ausente."""
    try:
        return get_client().query(
            f"SELECT * FROM `{T_PARAM}` WHERE mes = DATE('{mes_iso}')"
        ).to_dataframe()
    except Exception:
        return pd.DataFrame()


def _linha_margem(fatos: dict, p: dict) -> dict:
    """Margem de uma linha (produto×canal) — FONTE ÚNICA da fórmula.

    Espelhada no front (web/src/pages/Price.tsx → calcMargem) só para o preview
    ao vivo enquanto o usuário digita; o número persistido/oficial é este.

    Fórmula PROVISÓRIA (validar com Diego):
      custo_pecas    = custo_unitário × quantidade
      mao_obra       = mão_obra_unitária × quantidade
      imposto_nota   = ICMS + IPI − créditos(%·faturamento)        (piso 0)
      despesas       = (Ads% + comissão% + outras% + custo_fixo%) · faturamento
      imposto_lucro  = (PIS% + COFINS% + IRPJ% + CSLL%) · faturamento
      margem         = faturamento − custo_peças − mão_obra − imposto_nota − despesas − imposto_lucro
    """
    fat = _num(fatos.get("faturamento"))
    qtd = _num(fatos.get("quantidade"))
    icms = _num(fatos.get("imposto_icms"))
    ipi = _num(fatos.get("imposto_ipi"))

    # Prioridade invertida 16/07: o ERP (YVALITMVIN) e fonte de verdade quando
    # existe. O manual so serve pra preencher o gap dos itens que o ERP ainda
    # nao calculou — nao deve mais sobrescrever um valor real do ERP.
    custo_erp = fatos.get("custo_peca_erp")
    custo_erp_num = _num(custo_erp) if custo_erp is not None else None
    custo_unit = custo_erp_num if custo_erp_num is not None else _num(p.get("custo_peca"))
    custo_pecas = custo_unit * qtd

    credito_icms = fat * _num(p.get("pct_credito_icms"), _num(p.get("pct_credito_icms_ipi"))) / 100.0
    credito_ipi = fat * _num(p.get("pct_credito_ipi")) / 100.0
    credito = credito_icms + credito_ipi
    imposto_nota = max(icms + ipi - credito, 0.0)
    despesa_ads = fat * _num(p.get("pct_ads")) / 100.0
    despesa_comissao = fat * _num(p.get("pct_comissao")) / 100.0
    despesa_outras = fat * _num(p.get("pct_outras")) / 100.0
    despesa_custo_fixo = fat * _num(p.get("pct_custo_fixo")) / 100.0
    mao_obra = _num(p.get("mao_obra_unit")) * qtd

    legacy_irpj_csll = _num(p.get("pct_irpj_csll"))
    pct_irpj = _num(p.get("pct_irpj"), legacy_irpj_csll)
    pct_csll = _num(p.get("pct_csll"))
    imposto_pis = fat * _num(p.get("pct_pis")) / 100.0
    imposto_cofins = fat * _num(p.get("pct_cofins")) / 100.0
    imposto_irpj = fat * pct_irpj / 100.0
    imposto_csll = fat * pct_csll / 100.0
    imposto_lucro = imposto_pis + imposto_cofins + imposto_irpj + imposto_csll

    custo_total = (custo_pecas + mao_obra + imposto_nota + despesa_ads
                   + despesa_comissao + despesa_outras + despesa_custo_fixo
                   + imposto_lucro)
    margem = fat - custo_total
    margem_pct = (margem / fat * 100.0) if fat else None

    return {
        "item_code": fatos.get("item_code"),
        "item_name": fatos.get("item_name"),
        "canal": fatos.get("canal"),
        "n_pedidos": int(_num(fatos.get("n_pedidos"))),
        "quantidade": qtd,
        "faturamento": fat,
        "ticket_medio": _num(fatos.get("ticket_medio"), (fat / qtd if qtd else 0.0)),
        "imposto_icms": icms,
        "imposto_ipi": ipi,
        "custo_pecas": custo_pecas,
        "mao_obra": mao_obra,
        "imposto_nota": imposto_nota,
        "despesas": despesa_ads + despesa_comissao + despesa_outras + despesa_custo_fixo,
        "imposto_lucro": imposto_lucro,
        "custo_total": custo_total,
        "margem": margem,
        "margem_pct": margem_pct,
        # ecoa os campos manuais pro front pré-preencher os inputs
        "custo_peca": custo_unit,
        "custo_manual": p.get("custo_peca") is not None,
        # true quando o ERP ja tem o custo (YVALITMVIN) — front trava o input
        # nesse caso, edicao manual so serve pro gap onde o ERP ainda nao tem.
        "custo_travado_erp": custo_erp_num is not None,
        "pct_ads": _num(p.get("pct_ads")),
        "pct_comissao": _num(p.get("pct_comissao")),
        "pct_irpj_csll": legacy_irpj_csll,
        "pct_irpj": pct_irpj,
        "pct_csll": pct_csll,
        "pct_pis": _num(p.get("pct_pis")),
        "pct_cofins": _num(p.get("pct_cofins")),
        "pct_credito_icms_ipi": _num(p.get("pct_credito_icms_ipi")),
        "pct_credito_icms": _num(p.get("pct_credito_icms"), _num(p.get("pct_credito_icms_ipi"))),
        "pct_credito_ipi": _num(p.get("pct_credito_ipi")),
        "mao_obra_unit": _num(p.get("mao_obra_unit")),
        "pct_custo_fixo": _num(p.get("pct_custo_fixo")),
        "pct_outras": _num(p.get("pct_outras")),
    }


def margem(mes: str) -> dict:
    """Linhas produto×canal + totais do mês, com a margem já calculada."""
    mes_ref = pd.Timestamp(mes).date().replace(day=1)
    # fatos (com cache 1h) e pdf (sempre sem cache, edição reflete na hora) só
    # dependem de mes_ref — independentes entre si, disparam juntas.
    with ThreadPoolExecutor(max_workers=2) as ex:
        fatos_f = ex.submit(query, f"""
            SELECT * FROM `{T_MARGEM}` WHERE mes = DATE('{mes_ref}')
            ORDER BY canal ASC, faturamento DESC
        """)
        pdf_f = ex.submit(_param_do_mes, str(mes_ref))
        fatos = fatos_f.result()
        pdf = pdf_f.result()

    if fatos.empty:
        return {"mes": str(mes_ref), "empty": True, "rows": [], "totais": {}}

    pmap: dict[tuple, dict] = {}
    if not pdf.empty:
        for _, r in pdf.iterrows():
            pmap[(r["item_code"], r["canal"])] = r.to_dict()

    rows = []
    for _, f in fatos.iterrows():
        fd = f.to_dict()
        p = pmap.get((fd.get("item_code"), fd.get("canal")), {})
        rows.append(_linha_margem(fd, p))

    tot_fat = sum(r["faturamento"] for r in rows)
    tot_margem = sum(r["margem"] for r in rows)
    return {
        "mes": str(mes_ref),
        "empty": False,
        "rows": rows,
        "totais": {
            "faturamento": tot_fat,
            "margem": tot_margem,
            "margem_pct": (tot_margem / tot_fat * 100.0) if tot_fat else None,
            "n_itens": len(rows),
        },
    }


def margem_uf(mes: str, item_code: str, canal: str) -> dict:
    """Detalhe UF de uma linha produto×canal, mantendo a mesma fórmula da margem."""
    mes_ref = pd.Timestamp(mes).date().replace(day=1)
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("mes", "DATE", mes_ref),
        bigquery.ScalarQueryParameter("item", "STRING", item_code),
        bigquery.ScalarQueryParameter("canal", "STRING", canal),
    ])

    with ThreadPoolExecutor(max_workers=2) as ex:
        fatos_f = ex.submit(
            lambda: get_client().query(f"""
                SELECT * FROM `{T_MARGEM_UF}`
                WHERE mes = @mes AND item_code = @item AND canal = @canal
                ORDER BY faturamento DESC
            """, job_config=cfg).to_dataframe()
        )
        pdf_f = ex.submit(_param_do_mes, str(mes_ref))
        fatos = fatos_f.result()
        pdf = pdf_f.result()

    if fatos.empty:
        return {"mes": str(mes_ref), "item_code": item_code, "canal": canal, "rows": []}

    p: dict = {}
    if not pdf.empty:
        match = pdf[(pdf["item_code"] == item_code) & (pdf["canal"] == canal)]
        if not match.empty:
            p = match.iloc[0].to_dict()

    rows = []
    for _, f in fatos.iterrows():
        fd = f.to_dict()
        linha = _linha_margem(fd, p)
        linha["uf"] = fd.get("uf") or "UF nao informada"
        rows.append(linha)

    return {"mes": str(mes_ref), "item_code": item_code, "canal": canal, "rows": rows}


class CustoIn(BaseModel):
    """Payload do PUT /api/price/custo. Campos None = limpar (grava NULL)."""

    item_code: str = Field(..., min_length=1)
    canal: str = Field(..., min_length=1)
    mes: str
    custo_peca: float | None = None
    pct_ads: float | None = None
    pct_comissao: float | None = None
    pct_irpj_csll: float | None = None
    pct_irpj: float | None = None
    pct_csll: float | None = None
    pct_pis: float | None = None
    pct_cofins: float | None = None
    pct_credito_icms_ipi: float | None = None
    pct_credito_icms: float | None = None
    pct_credito_ipi: float | None = None
    mao_obra_unit: float | None = None
    pct_custo_fixo: float | None = None
    pct_outras: float | None = None

    @field_validator("mes")
    @classmethod
    def _mes(cls, v: str) -> str:
        try:
            return date.fromisoformat(v).replace(day=1).isoformat()
        except (TypeError, ValueError) as e:
            raise ValueError("mes deve ser YYYY-MM-DD.") from e


def set_custo(payload: CustoIn, updated_by: str) -> None:
    """Upsert (MERGE) dos campos manuais de custo para (item × canal × mes)."""
    _ensure_param_table()
    params = [
        bigquery.ScalarQueryParameter("item", "STRING", payload.item_code),
        bigquery.ScalarQueryParameter("canal", "STRING", payload.canal),
        bigquery.ScalarQueryParameter("mes", "DATE", date.fromisoformat(payload.mes)),
        bigquery.ScalarQueryParameter("by", "STRING", updated_by),
    ]
    for f in _PARAM_FLOATS:
        params.append(bigquery.ScalarQueryParameter(f, "FLOAT64", getattr(payload, f)))
    cfg = bigquery.QueryJobConfig(query_parameters=params)

    sel = ", ".join(f"@{f} AS {f}" for f in _PARAM_FLOATS)
    set_clause = ", ".join(f"{f} = S.{f}" for f in _PARAM_FLOATS)
    cols = ", ".join(_PARAM_FLOATS)
    src_cols = ", ".join(f"S.{f}" for f in _PARAM_FLOATS)
    get_client().query(f"""
        MERGE `{T_PARAM}` T
        USING (SELECT @item AS item_code, @canal AS canal, @mes AS mes,
                      @by AS updated_by, {sel}) S
          ON T.item_code = S.item_code AND T.canal = S.canal AND T.mes = S.mes
        WHEN MATCHED THEN UPDATE SET
          {set_clause}, updated_by = S.updated_by, updated_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN
          INSERT (item_code, canal, mes, {cols}, updated_by, updated_at)
          VALUES (S.item_code, S.canal, S.mes, {src_cols}, S.updated_by, CURRENT_TIMESTAMP())
    """, job_config=cfg).result()


# ── Router ──────────────────────────────────────────────────────
router = APIRouter(prefix="/api/price", tags=["price"])


@router.get("/meses")
def price_meses(_user=Depends(require_admin)):
    try:
        return meses()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery: {e}") from e


@router.get("")
def price_margem(mes: str = Query(..., description="YYYY-MM-DD (1º dia do mês)"),
                 _user=Depends(require_admin)):
    try:
        return margem(mes)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery: {e}") from e


@router.get("/uf")
def price_margem_uf(
    mes: str = Query(..., description="YYYY-MM-DD (1º dia do mês)"),
    item_code: str = Query(...),
    canal: str = Query(...),
    _user=Depends(require_admin),
):
    try:
        return margem_uf(mes, item_code, canal)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery: {e}") from e


@router.put("/custo")
def price_set_custo(payload: CustoIn, user=Depends(require_admin)):
    email = getattr(user, "email", None) or ""
    if not email:
        raise HTTPException(status_code=401, detail="Sessão inválida.")
    try:
        set_custo(payload, email)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"BigQuery: {e}") from e
    return {"ok": True}
