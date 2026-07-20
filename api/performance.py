"""
Matriz de Performance — Esforço x Resultado por vendedor.

Especificação (Vinícius, WhatsApp 16/06/2026): eixo X = Esforço (CRM), eixo Y =
Resultado (CRM + Data Lake), cada indicador normalizado 0-100, 4 quadrantes:

    Futuro Talento   | Alta Performance     (resultado alto)
    Baixa Entrega     | Esforço Ineficiente  (resultado baixo)
    (esforço baixo)     (esforço alto)

Fonte dos indicadores:
- Esforço (crm_raw.activities + deals): ligações, reuniões, propostas enviadas,
  follow-ups, atividades registradas, oportunidades criadas, ciclo médio (menor
  é melhor, por isso entra invertido no score).
- Resultado (crm_raw deals + ERP fact_sales_order + Pipedrive Goals): receita
  realizada (ERP), receita contratada (deals ganhos), meta atingida %, pipeline
  gerado, conversão (win rate), ticket médio.

Escopo: só os vendedores com meta individual no Pipedrive (mesmo grupo que já
aparece no ranking da Gestão à Vista) — população consistente com o resto do
Comercial. Normalização é min-max DENTRO do grupo exibido (o melhor do mês vira
100, o pior vira 0) — não é uma escala absoluta.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd

from .bq import query, PROJECT_PROD
from .gestao_vista import _PIPE_NAME_TO_ERP, meta_vendedor, MESES_PT, NOME_SEM_SUFIXO

PROJ = PROJECT_PROD
ORDERS = f"{PROJ}.dm_orders"
CRM = f"{PROJ}.crm_raw"
NAT_JOIN = (f"JOIN `{ORDERS}.dim_operation_nature` n "
            f"ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'")

DEAL_TABLES = [
    "funil_vendas_distribuidores", "funil_vendas_farmacia",
    "recorrencia_distribuidores", "recorrencia_farmacia",
]


def _mes_bounds(mes: str | None) -> tuple[date, date, str]:
    ref = pd.Timestamp(mes).date() if mes else date.today().replace(day=1)
    ini = ref.replace(day=1)
    fim = ini.replace(month=ini.month % 12 + 1, day=1) if ini.month < 12 else date(ini.year + 1, 1, 1)
    return ini, fim, f"{MESES_PT[ini.month]}/{ini.year}"


def _norm01(vals: dict[str, float], invert: bool = False) -> dict[str, float]:
    """Min-max normaliza pra 0-100 dentro do próprio grupo. invert=True: menor valor vira score maior."""
    if not vals:
        return {}
    xs = list(vals.values())
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-9:
        return {k: 50.0 for k in vals}  # todos empatados -> neutro
    out = {}
    for k, v in vals.items():
        s = (v - lo) / (hi - lo) * 100.0
        out[k] = (100.0 - s) if invert else s
    return out


def performance_matriz(mes: str | None = None) -> dict:
    mes_ini, mes_fim, mes_label = _mes_bounds(mes)
    mes_key = f"{mes_ini.year}-{mes_ini.month:02d}"

    # As 4 queries abaixo são independentes (nenhuma usa o resultado de outra pra
    # montar o SQL) — disparam juntas em vez de sequenciais.
    union = "\n  UNION ALL\n".join(
        f"SELECT deal_id, owner_id, value, status, add_time, local_won_date, local_lost_date "
        f"FROM `{CRM}.{t}` WHERE is_deleted IS NOT TRUE" for t in DEAL_TABLES
    )
    sql = {
        # user_id (Pipedrive) -> nome_norm (ERP), só quem tem meta cadastrada.
        "users": f"SELECT user_id, name FROM `{CRM}.dim_crm_user` WHERE is_active",
        # Esforço: atividades por usuário no mês
        "ativ": f"""
            SELECT a.user_id,
                   COUNTIF(a.type = 'call' AND a.done) AS ligacoes,
                   COUNTIF(a.type = 'meeting' AND a.done) AS reunioes,
                   COUNTIF(a.type = 'envio_de_orcamento' AND a.done) AS propostas,
                   COUNTIF(a.type IN ('tentativa_de_contato', 'contato') AND a.done) AS followups,
                   COUNT(*) AS atividades_reg
            FROM `{CRM}.activities` a
            WHERE a.due_date >= '{mes_ini}' AND a.due_date < '{mes_fim}' AND a.user_id IS NOT NULL
            GROUP BY 1
        """,
        # Deals (4 pipelines unidos): criados/ganhos/perdidos no mês
        "deals": f"""
            WITH d AS ({union})
            SELECT owner_id,
                   COUNTIF(DATE(add_time) >= '{mes_ini}' AND DATE(add_time) < '{mes_fim}') AS oportunidades_criadas,
                   SUM(IF(DATE(add_time) >= '{mes_ini}' AND DATE(add_time) < '{mes_fim}', value, 0)) AS pipeline_gerado,
                   COUNTIF(status = 'won' AND local_won_date >= '{mes_ini}' AND local_won_date < '{mes_fim}') AS won_mes,
                   COUNTIF(status = 'lost' AND local_lost_date >= '{mes_ini}' AND local_lost_date < '{mes_fim}') AS lost_mes,
                   SUM(IF(status = 'won' AND local_won_date >= '{mes_ini}' AND local_won_date < '{mes_fim}', value, 0)) AS receita_contratada,
                   AVG(IF(status IN ('won', 'lost')
                          AND COALESCE(local_won_date, local_lost_date) >= '{mes_ini}'
                          AND COALESCE(local_won_date, local_lost_date) < '{mes_fim}',
                          DATE_DIFF(COALESCE(local_won_date, local_lost_date), DATE(add_time), DAY), NULL)) AS ciclo_medio_dias
            FROM d
            GROUP BY owner_id
        """,
        # ERP: faturamento + pedidos por vendedor no mês (metodologia canônica)
        "erp": f"""
            SELECT UPPER({NOME_SEM_SUFIXO}) nome_norm,
                   SUM(o.product_amount) receita_realizada, COUNT(*) pedidos
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE o.salesperson_group_code IN ('FA', 'FR', 'PC')
              AND o.invoice_date >= '{mes_ini}' AND o.invoice_date < '{mes_fim}'
              AND o.salesperson_name IS NOT NULL AND TRIM(o.salesperson_name) <> ''
            GROUP BY 1
        """,
    }
    with ThreadPoolExecutor(max_workers=len(sql)) as ex:
        futures = {k: ex.submit(query, v) for k, v in sql.items()}
        dfs = {k: f.result() for k, f in futures.items()}
    users, ativ, deals, erp = dfs["users"], dfs["ativ"], dfs["deals"], dfs["erp"]

    uid_to_erp: dict[int, str] = {}
    for _, r in users.iterrows():
        erp_nome = _PIPE_NAME_TO_ERP.get(str(r["name"]).strip().upper())
        if erp_nome:
            uid_to_erp[int(r["user_id"])] = erp_nome

    erp_map = {str(r["nome_norm"]): (float(r["receita_realizada"] or 0), int(r["pedidos"])) for _, r in erp.iterrows()}

    # ── Monta um registro cru por vendedor (nome_norm) ────────────────────
    brutos: dict[str, dict] = {}
    for nome_norm in set(_PIPE_NAME_TO_ERP.values()):
        brutos[nome_norm] = {
            "ligacoes": 0.0, "reunioes": 0.0, "propostas": 0.0, "followups": 0.0,
            "atividades_reg": 0.0, "oportunidades_criadas": 0.0, "ciclo_medio_dias": None,
            "pipeline_gerado": 0.0, "won_mes": 0, "lost_mes": 0, "receita_contratada": 0.0,
            "receita_realizada": 0.0, "pedidos": 0, "meta": None,
        }

    for _, r in ativ.iterrows():
        nome_norm = uid_to_erp.get(int(r["user_id"]))
        if not nome_norm:
            continue
        b = brutos[nome_norm]
        b["ligacoes"] += float(r["ligacoes"] or 0)
        b["reunioes"] += float(r["reunioes"] or 0)
        b["propostas"] += float(r["propostas"] or 0)
        b["followups"] += float(r["followups"] or 0)
        b["atividades_reg"] += float(r["atividades_reg"] or 0)

    for _, r in deals.iterrows():
        nome_norm = uid_to_erp.get(int(r["owner_id"])) if pd.notna(r["owner_id"]) else None
        if not nome_norm:
            continue
        b = brutos[nome_norm]
        b["oportunidades_criadas"] += float(r["oportunidades_criadas"] or 0)
        b["pipeline_gerado"] += float(r["pipeline_gerado"] or 0)
        b["won_mes"] += int(r["won_mes"] or 0)
        b["lost_mes"] += int(r["lost_mes"] or 0)
        b["receita_contratada"] += float(r["receita_contratada"] or 0)
        ciclo = r["ciclo_medio_dias"]
        if pd.notna(ciclo):
            b["ciclo_medio_dias"] = float(ciclo)

    for nome_norm in brutos:
        rec, ped = erp_map.get(nome_norm, (0.0, 0))
        brutos[nome_norm]["receita_realizada"] = rec
        brutos[nome_norm]["pedidos"] = ped
        brutos[nome_norm]["meta"] = meta_vendedor(nome_norm, mes_key)

    # Só entra na matriz quem tem meta no mês (mesma população do ranking) —
    # sem meta não dá pra calcular "% atingido", um dos 6 indicadores de resultado.
    ativos = {k: v for k, v in brutos.items() if v["meta"]}
    if not ativos:
        return {"mes": str(mes_ini), "mes_label": mes_label, "vendedores": [], "vazio": True}

    # ── Normalização 0-100 dentro do grupo exibido ────────────────────────
    def col(nome: str) -> dict[str, float]:
        return {k: v[nome] for k, v in ativos.items()}

    ciclo_vals = {k: v["ciclo_medio_dias"] for k, v in ativos.items() if v["ciclo_medio_dias"] is not None}
    n_ligacoes = _norm01(col("ligacoes"))
    n_reunioes = _norm01(col("reunioes"))
    n_propostas = _norm01(col("propostas"))
    n_followups = _norm01(col("followups"))
    n_atividades = _norm01(col("atividades_reg"))
    n_oportunidades = _norm01(col("oportunidades_criadas"))
    n_ciclo = _norm01(ciclo_vals, invert=True)  # menor ciclo = mais ágil = score maior

    n_receita_real = _norm01(col("receita_realizada"))
    n_receita_contr = _norm01(col("receita_contratada"))
    meta_pct = {k: min(v["receita_realizada"] / v["meta"], 1.5) * 100 if v["meta"] else 0.0 for k, v in ativos.items()}
    n_meta_pct = _norm01(meta_pct)
    n_pipeline = _norm01(col("pipeline_gerado"))
    conversao = {k: (v["won_mes"] / (v["won_mes"] + v["lost_mes"])) if (v["won_mes"] + v["lost_mes"]) else 0.0
                 for k, v in ativos.items()}
    n_conversao = _norm01(conversao)
    ticket = {k: (v["receita_realizada"] / v["pedidos"]) if v["pedidos"] else 0.0 for k, v in ativos.items()}
    n_ticket = _norm01(ticket)

    saida = []
    for nome_norm, b in ativos.items():
        esforco_partes = [
            n_ligacoes.get(nome_norm, 0), n_reunioes.get(nome_norm, 0), n_propostas.get(nome_norm, 0),
            n_followups.get(nome_norm, 0), n_atividades.get(nome_norm, 0), n_oportunidades.get(nome_norm, 0),
        ]
        if nome_norm in n_ciclo:
            esforco_partes.append(n_ciclo[nome_norm])
        resultado_partes = [
            n_receita_real.get(nome_norm, 0), n_receita_contr.get(nome_norm, 0), n_meta_pct.get(nome_norm, 0),
            n_pipeline.get(nome_norm, 0), n_conversao.get(nome_norm, 0), n_ticket.get(nome_norm, 0),
        ]
        esforco_score = sum(esforco_partes) / len(esforco_partes)
        resultado_score = sum(resultado_partes) / len(resultado_partes)
        saida.append({
            "vendedor": nome_norm.title(),
            "esforco_score": round(esforco_score, 1),
            "resultado_score": round(resultado_score, 1),
            "quadrante": (
                "Alta Performance" if esforco_score >= 50 and resultado_score >= 50 else
                "Futuro Talento" if esforco_score < 50 and resultado_score >= 50 else
                "Esforço Ineficiente" if esforco_score >= 50 and resultado_score < 50 else
                "Baixa Entrega"
            ),
            "detalhe": {
                "ligacoes": int(b["ligacoes"]), "reunioes": int(b["reunioes"]),
                "propostas": int(b["propostas"]), "followups": int(b["followups"]),
                "atividades_registradas": int(b["atividades_reg"]),
                "oportunidades_criadas": int(b["oportunidades_criadas"]),
                "ciclo_medio_dias": round(b["ciclo_medio_dias"], 1) if b["ciclo_medio_dias"] is not None else None,
                "receita_realizada": b["receita_realizada"], "receita_contratada": b["receita_contratada"],
                "meta": b["meta"], "meta_atingida_pct": round(meta_pct.get(nome_norm, 0.0), 1),
                "pipeline_gerado": b["pipeline_gerado"], "conversao_pct": round(conversao.get(nome_norm, 0.0) * 100, 1),
                "ticket_medio": round(ticket.get(nome_norm, 0.0), 2),
            },
        })

    saida.sort(key=lambda x: x["resultado_score"] + x["esforco_score"], reverse=True)
    return {"mes": str(mes_ini), "mes_label": mes_label, "vendedores": saida, "vazio": False}
