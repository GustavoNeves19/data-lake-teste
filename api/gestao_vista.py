"""
Gestão à Vista — porta fiel de dashboard/utils/gestao_vista.py + gestao_vista_view.py.

Tela que abre a reunião de liderança: meta x realizado (gauge), ranking mensal e
diário (com carry-over), venda necessária por dia, pipelines CRM, engenharia
reversa do funil e atividades. Todo número vem do BigQuery com a metodologia
canônica (financial_flag<>'N', invoice_date, product_amount); a meta é provisória
(constantes do Alves/Pipedrive, pois não há tabela de meta materializada no BQ).
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd
import requests

from .bq import query, PROJECT_PROD
from .metas import meta_do_mes
from .db import SessionLocal

PROJ = PROJECT_PROD
ORDERS = f"{PROJ}.dm_orders"
CRM = f"{PROJ}.crm_raw"
NAT_JOIN = (f"JOIN `{ORDERS}.dim_operation_nature` n "
            f"ON n.nature_code = o.nature_code AND n.financial_flag <> 'N'")

# Alguns vendedores têm variante de nome no ERP com sufixo entre parênteses por
# canal (ex: "GEOVANA GOMES (SAC)", "KAUA RODRIGUES (FARMACIA)") — mesma pessoa,
# cadastro duplicado. Sem remover o sufixo, o SQL trata como vendedor diferente:
# o faturamento some do ranking (nome não bate com a meta do Pipedrive) e a
# pessoa aparece com meta batida sem o real dela. Usar em todo GROUP BY por nome.
NOME_SEM_SUFIXO = r"TRIM(REGEXP_REPLACE(TRIM(o.salesperson_name), r'\s*\([^)]*\)\s*$', ''))"

MESES_PT = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

VIEWS = {
    "Geral":      ("GERAL",      "o.salesperson_group_code IN ('FA','FR','PC')"),
    "Hospitalar": ("HOSPITALAR", "o.salesperson_group_code = 'FA'"),
    "Farmácia":   ("FARMACIA",   "o.salesperson_group_code = 'FR'"),
}

# ── Metas / taxas (provisórias — planilha do Alves / Pipedrive) ─────────
FERIADOS: list[date] = [
    date(2026, 5, 1),    # Dia do Trabalho
    date(2026, 6, 4),    # Corpus Christi
    date(2026, 6, 24),   # São João (Teresina/PI)
    date(2026, 7, 10),   # Revolução Constitucionalista (SP, 09/07) — folga movida p/ 10 (Nevoni)
]

META_EQUIPE: dict[str, float] = {
    "GERAL": 1_568_000.0,
    "HOSPITALAR": 900_000.0,
    "FARMACIA": 100_000.0,
}

# Snapshot manual (fallback) — só usado se o Pipedrive não responder. A fonte viva
# é meta_vendedor() abaixo, que lê os Goals do Pipedrive.
METAS_VENDEDOR: dict[str, dict[str, float]] = {
    "GUILHERME DE AQUINO MARQUES": {"2026-05": 458898, "2026-06": 407394},
    "KAUA RODRIGUES":              {"2026-05": 313000, "2026-06": 310000},
    "RICHARD LUCAS":               {"2026-05": 76000,  "2026-06": 83335},
    "CAUA RIBEIRO":                {"2026-05": 58639,  "2026-06": 69509},
    "KAUAN RAMOS":                 {"2026-05": 54196,  "2026-06": 55487},
    "GEOVANA GOMES":               {"2026-05": 57333,  "2026-06": 16125},
}

# ── Metas individuais AO VIVO do Pipedrive (Goals API) ─────────────────
# Fonte real: o Alves cadastra a meta de cada vendedor todo mês nos Goals/Insights
# do Pipedrive. Puxamos direto de /goals/find (com cache), pro mês que estiver na
# tela — em vez do snapshot manual, que travava no último mês copiado à mão.
PIPEDRIVE_GOALS_TTL = 1800  # 30 min: meta muda ~1x/mês, não precisa bater a cada request

# Pipedrive usa nome curto; o ranking do ERP usa UPPER(salesperson_name). Mapa fixo.
_PIPE_NAME_TO_ERP: dict[str, str] = {
    "GUILHERME":       "GUILHERME DE AQUINO MARQUES",
    "KAUÃ RODRIGUES":  "KAUA RODRIGUES",
    "RICHARD SILVA":   "RICHARD LUCAS",
    "CAUÃ RIBEIRO":    "CAUA RIBEIRO",
    "KAUAN RAMOS":     "KAUAN RAMOS",
    "GEOVANA GOMES":   "GEOVANA GOMES",
}

_goals_cache: dict = {"ts": 0.0, "data": {}}


def _pipedrive_metas_todas() -> dict[str, dict[str, float]]:
    """{erp_nome_norm: {'2026-07': target, ...}} lido ao vivo do Pipedrive (cache 30min).

    Degrada gracioso: sem token, API fora do ar ou formato mudou -> devolve o último
    cache bom (ou {}), e o chamador cai no snapshot METAS_VENDEDOR. Nunca quebra o painel.
    """
    now = time.time()
    if _goals_cache["data"] and (now - _goals_cache["ts"]) < PIPEDRIVE_GOALS_TTL:
        return _goals_cache["data"]

    token = os.getenv("PIPEDRIVE_API_TOKEN", "").strip()
    if not token:
        return _goals_cache["data"]
    base = "https://api.pipedrive.com/v1"  # Goals só existe na v1
    try:
        ru = requests.get(f"{base}/users", params={"api_token": token}, timeout=15)
        users = {u["id"]: u.get("name") for u in (ru.json().get("data") or [])}
        rg = requests.get(f"{base}/goals/find", params={"api_token": token}, timeout=15)
        goals = (rg.json().get("data") or {}).get("goals") or []
    except Exception:
        return _goals_cache["data"]

    out: dict[str, dict[str, float]] = {}
    for g in goals:
        if not g.get("is_active"):
            continue
        if (g.get("type") or {}).get("name") != "deals_won":
            continue
        seas = g.get("seasonality") or {}
        if seas.get("tracking_metric") != "sum":   # 'sum' = R$; senão é contagem de deals
            continue
        assignee = g.get("assignee") or {}
        if assignee.get("type") == "company":
            continue  # meta de equipe vem do Postgres, não daqui
        pipe_nome = (users.get(assignee.get("id")) or "").strip().upper()
        erp_nome = _PIPE_NAME_TO_ERP.get(pipe_nome)
        if not erp_nome:
            continue
        for iv in seas.get("intervals") or []:
            mes = (iv.get("start") or "")[:7]
            if iv.get("target"):
                out.setdefault(erp_nome, {})[mes] = float(iv["target"])

    if out:
        _goals_cache["ts"] = now
        _goals_cache["data"] = out
    return out or _goals_cache["data"]


def meta_vendedor(nome_norm: str, mes_key: str) -> float | None:
    """Meta individual do vendedor no mês: Pipedrive (vivo) -> snapshot manual -> None."""
    viva = _pipedrive_metas_todas().get(nome_norm, {}).get(mes_key)
    if viva:
        return float(viva)
    snap = METAS_VENDEDOR.get(nome_norm, {}).get(mes_key)
    return float(snap) if snap else None


PROVISORIO = True

TAXAS_CONVERSAO: dict[str, dict] = {
    "RICHARD LUCAS":               {"ticket": 876.14,  "tx_fech": 0.83, "tx_neg": 0.92, "tx_orc": 0.27, "tx_con": 0.75, "tx_cont": 0.54},
    "KAUA RODRIGUES":              {"ticket": 3616.23, "tx_fech": 0.65, "tx_neg": 0.74, "tx_orc": 0.50, "tx_con": 0.96, "tx_cont": 0.72},
    "GUILHERME DE AQUINO MARQUES": {"ticket": 6248.33, "tx_fech": 1.00, "tx_neg": 0.95, "tx_orc": 0.70, "tx_con": 0.77, "tx_cont": 0.36},
    "CAUA RIBEIRO":                {"ticket": 859.80,  "tx_fech": 0.92, "tx_neg": 1.00, "tx_orc": 0.38, "tx_con": 0.31, "tx_cont": 0.46},
    "GEOVANA GOMES":               {"ticket": 739.20,  "tx_fech": 0.92, "tx_neg": 0.87, "tx_orc": 0.38, "tx_con": 0.98, "tx_cont": 0.36},
}

FAMILIA_LABEL = {"FA": "Hospitalar", "FR": "Farmácia", "PC": "SAC"}

PIPE_HOSP = ["funil_vendas_distribuidores", "recorrencia_distribuidores"]
PIPE_FARMA = ["funil_vendas_farmacia", "recorrencia_farmacia"]
STAGES_HOSP = ["Orçamento", "Negociação", "Fechamento"]
STAGES_FARMA = ["Negociação", "Fechamento"]

TIPO_ATIV = {
    "call": "Chamada", "meeting": "Reunião", "task": "Tarefa", "deadline": "Prazo",
    "email": "E-mail", "lunch": "Almoço", "tentativa_de_contato": "Tentativa de contato",
    "contato": "Contato", "elaboracao_de_orcamento": "Elaboração de orçamento",
    "envio_de_orcamento": "Envio de orçamento", "aceite_do_cliente": "Aceite do cliente",
    "quebra_de_objecoes": "Quebra de objeções", "mensagem_de_despedida": "Mensagem de despedida",
    "checklist_de_qualificacao": "Checklist qualificação", "ligacao_atendida": "Ligação atendida",
    "nao_atendida": "Não atendida", "whatsapp_chat": "Whatsapp", "anexar_documentos": "Anexar docs",
    "validar_documentacao": "Validar documentação",
}


# ── matemática de dias úteis (seg–sex menos feriados) ──────────────────
def dias_uteis_mes(ref: date) -> int:
    inicio = ref.replace(day=1)
    fim = (inicio.replace(month=inicio.month % 12 + 1, day=1)
           if inicio.month < 12 else date(inicio.year + 1, 1, 1))
    fer = [d for d in FERIADOS if inicio <= d < fim]
    return int(np.busday_count(inicio, fim, holidays=fer))


def dia_util_corrente(ref: date) -> int:
    inicio = ref.replace(day=1)
    fer = [d for d in FERIADOS if inicio <= d <= ref]
    return int(np.busday_count(inicio, ref, holidays=fer)) + (
        1 if np.is_busday(ref, holidays=list(FERIADOS)) else 0
    )


def dias_uteis_restantes(ref: date) -> int:
    total = dias_uteis_mes(ref)
    return max(total - dia_util_corrente(ref) + 1, 1)


def projecao_esperada(meta: float, ref: date) -> float:
    return meta / dias_uteis_mes(ref) * dia_util_corrente(ref)


def venda_necessaria_dia(meta: float, realizado: float, ref: date) -> float:
    falta = max(meta - realizado, 0.0)
    return falta / dias_uteis_restantes(ref)


def taxas_aproximadas_hospitalar() -> dict:
    base = [TAXAS_CONVERSAO[v] for v in
            ("GUILHERME DE AQUINO MARQUES", "KAUA RODRIGUES", "RICHARD LUCAS")]
    chaves = ("ticket", "tx_fech", "tx_neg", "tx_orc", "tx_con", "tx_cont")
    return {k: round(sum(b[k] for b in base) / len(base), 4) for k in chaves}


def eng_reversa_funil(meta: float, taxas: dict, dias_uteis: int = 22) -> dict:
    t = taxas or {}
    vendas = meta / t["ticket"] if t.get("ticket") else 0.0
    fech = vendas / t["tx_fech"] if t.get("tx_fech") else 0.0
    neg = fech / t["tx_neg"] if t.get("tx_neg") else 0.0
    orc = neg / t["tx_orc"] if t.get("tx_orc") else 0.0
    con = orc / t["tx_con"] if t.get("tx_con") else 0.0
    cont = con / t["tx_cont"] if t.get("tx_cont") else 0.0
    return {"meta": meta, "vendas": vendas, "fechamentos": fech, "negociacoes": neg,
            "orcamentos": orc, "conexoes": con, "contatos_mes": cont,
            "contatos_dia": cont / dias_uteis if dias_uteis else 0.0}


def _f(v, d=0.0) -> float:
    try:
        f = float(v)
        return d if (f != f) else f  # NaN-safe
    except (TypeError, ValueError):
        return d


# ── pipelines CRM (degrada gracioso) ───────────────────────────────────
def _pipeline_stats(tables: list[str], allowed: list[str]) -> dict:
    union = "\n  UNION ALL\n".join(
        f"SELECT deal_id, value, status, stage_id FROM `{CRM}.{t}` WHERE is_deleted IS NOT TRUE"
        for t in tables
    )
    allowed_sql = ", ".join(f"'{s}'" for s in allowed)
    sql = {
        "df": f"""
            WITH d AS ({union})
            SELECT s.stage_name AS nome, SUM(CAST(d.value AS FLOAT64)) AS val, COUNT(*) AS n
            FROM d JOIN `{CRM}.dim_crm_stage` s ON s.stage_id = d.stage_id
            WHERE d.status = 'open' AND s.stage_name IN ({allowed_sql})
            GROUP BY 1
        """,
        "wr": f"""
            WITH d AS ({union})
            SELECT COUNTIF(status='won') AS won, COUNTIF(status='lost') AS lost,
                   SUM(IF(status='won', CAST(value AS FLOAT64), 0)) AS val_won
            FROM d
        """,
    }
    try:
        with ThreadPoolExecutor(max_workers=len(sql)) as ex:
            futures = {k: ex.submit(query, v) for k, v in sql.items()}
            dfs = {k: f.result() for k, f in futures.items()}
        df, wr = dfs["df"], dfs["wr"]
    except Exception:
        return {"stages": [], "pipe_open": 0.0, "win_rate": None, "ticket_won": None}

    por_nome = {str(r["nome"]): (_f(r["val"]), int(r["n"])) for _, r in df.iterrows()}
    stages = [{"nome": s, "valor": por_nome.get(s, (0.0, 0))[0],
               "n": por_nome.get(s, (0.0, 0))[1]} for s in allowed]  # ordem completa
    pipe_open = sum(s["valor"] for s in stages)
    won = int(wr.iloc[0]["won"]) if not wr.empty else 0
    lost = int(wr.iloc[0]["lost"]) if not wr.empty else 0
    val_won = _f(wr.iloc[0]["val_won"]) if not wr.empty else 0.0
    win_rate = won / (won + lost) if (won + lost) else None
    ticket_won = val_won / won if won else None
    return {"stages": stages, "pipe_open": pipe_open,
            "win_rate": win_rate, "ticket_won": ticket_won}


def _eng_familia(grupo_cod: str, mes_key: str, du_total: int, grupo_de: dict,
                  apenas_nome_norm: str | None = None,
                  crm_ganho: dict | None = None) -> dict:
    """Funil da família (ou de 1 vendedor se apenas_nome_norm for passado).

    Itera sobre TODOS os vendedores ativos do grupo (grupo_de), não mais só os que
    estão no snapshot manual METAS_VENDEDOR — e usa meta_vendedor() (Pipedrive vivo,
    cai no snapshot se faltar), então cobre qualquer mês, não só Maio/Junho.

    "Meta do grupo" ao vivo (pedido Alves 13/07): o funil necessário é calculado
    sobre o REMANESCENTE (meta individual - já vendido no CRM no mês), não a meta
    cheia. Conforme o vendedor vende, o funil necessário pra bater o resto do mês
    encolhe. Usa o ganho no CRM (mesma fonte do ranking, decisão 09/07), não o
    faturado do ERP — "vendeu" é negócio ganho, faturamento é outra etapa.
    """
    membros = []
    aprox_any = False
    for nome_norm, grp in grupo_de.items():
        if grp != grupo_cod:
            continue
        if apenas_nome_norm and nome_norm != apenas_nome_norm:
            continue
        meta_ind = meta_vendedor(nome_norm, mes_key)
        if not meta_ind:
            continue
        ja_vendido = (crm_ganho or {}).get(nome_norm, {}).get("ganho_mes", 0.0)
        meta_restante = max(float(meta_ind) - ja_vendido, 0.0)
        taxas = TAXAS_CONVERSAO.get(nome_norm)
        aprox = taxas is None
        if aprox:
            taxas = taxas_aproximadas_hospitalar()
            aprox_any = True
        membros.append(eng_reversa_funil(meta_restante, taxas, du_total))
    if not membros:
        return {"vazio": True}
    meta_tot = sum(u["meta"] for u in membros)
    vendas = sum(u["vendas"] for u in membros)
    orc = sum(u["orcamentos"] for u in membros)
    cont_mes = sum(u["contatos_mes"] for u in membros)
    cont_dia = sum(u["contatos_dia"] for u in membros)
    ticket = meta_tot / vendas if vendas else 0.0
    tx_v = vendas / orc if orc else 0.0
    tx_o = orc / cont_mes if cont_mes else 0.0
    base = cont_mes or 1.0
    # Ordem do resultado pra origem: Vendas -> Oportunidades -> Contatos
    # (lê como "pra bater a meta preciso de N vendas, que exigem M oport., que exigem K contatos").
    etapas = [
        {"cor": "#AAA093", "label": "Vendas", "valor": round(vendas),
         "caption": f"{tx_v*100:.0f}% das oport.", "largura": max(vendas / base * 100, 22)},
        {"cor": "#8C8176", "label": "Oportunidades", "valor": round(orc),
         "caption": f"{tx_o*100:.0f}% dos contatos", "largura": max(orc / base * 100, 34)},
        {"cor": "#6F655C", "label": "Contatos", "valor": round(cont_mes),
         "caption": f"{round(cont_dia)}/dia", "largura": 100.0},
    ]
    return {"vazio": False, "meta_tot": meta_tot, "ticket": ticket,
            "etapas": etapas, "aprox": aprox_any}


# ── atividades (degrada gracioso) ──────────────────────────────────────
# "Concluídas" conta pela data em que a atividade foi MARCADA COMO FEITA
# (marked_as_done_time) — igual ao "marcado como feito" do Pipedrive, que é o
# número que o Alves compara. Fallback pra due_date se o timestamp vier nulo.
# (Já "atrasadas" segue o due_date: atrasado = venceu e não foi concluído.)
ATIV_CONCL_DATE = "COALESCE(DATE(a.marked_as_done_time), a.due_date)"


def _atividades_tipo(mes_ini: str, mes_fim: str) -> list[dict] | None:
    try:
        df = query(f"""
            SELECT a.type AS tipo,
                   COUNTIF(a.done AND {ATIV_CONCL_DATE} >= '{mes_ini}' AND {ATIV_CONCL_DATE} < '{mes_fim}') AS concl,
                   COUNTIF(NOT a.done AND a.due_date < CURRENT_DATE()) AS atras
            FROM `{CRM}.activities` a
            LEFT JOIN `{CRM}.dim_crm_user` u ON u.user_id = a.user_id
            WHERE a.user_id IS NOT NULL
            GROUP BY 1 HAVING concl > 0 OR atras > 0
            ORDER BY concl DESC LIMIT 8
        """)
    except Exception:
        return None
    return [{"tipo": TIPO_ATIV.get(str(r["tipo"]), str(r["tipo"])),
             "concl": int(r["concl"]), "atras": int(r["atras"])} for _, r in df.iterrows()]


def _atividades_vendedor(mes_ini: str, mes_fim: str) -> list[dict] | None:
    try:
        df = query(f"""
            SELECT u.name AS vend,
                   COUNTIF(a.done AND {ATIV_CONCL_DATE} >= '{mes_ini}' AND {ATIV_CONCL_DATE} < '{mes_fim}') AS concl,
                   COUNTIF(NOT a.done AND a.due_date < CURRENT_DATE()) AS atras
            FROM `{CRM}.activities` a
            JOIN `{CRM}.dim_crm_user` u ON u.user_id = a.user_id
            WHERE u.is_active
              AND UPPER(u.name) NOT LIKE 'KARINA%'
              AND UPPER(u.name) NOT LIKE 'VICTOR%' AND UPPER(u.name) NOT LIKE 'CLARICE%'
              AND UPPER(u.name) NOT LIKE 'VINICIUS%' AND UPPER(u.name) NOT LIKE 'VINÍCIUS%'
            GROUP BY 1 HAVING concl > 0 OR atras > 0
            ORDER BY concl DESC LIMIT 8
        """)
    except Exception:
        return None
    return [{"vendedor": str(r["vend"]), "concl": int(r["concl"]), "atras": int(r["atras"])}
            for _, r in df.iterrows()]


# ── API ────────────────────────────────────────────────────────────────
def _crm_ganho_por_vendedor(mes_ini: str, mes_fim: str, ref: str) -> dict:
    """{nome_norm_ERP: {'ganho_mes': R$, 'ganho_hoje': R$}} — negócios GANHOS no CRM
    (deals won no Pipedrive), por vendedor, no mês e no dia de referência.

    É o "outro número" que o ranking mostra ao lado do faturamento do ERP (opção
    combinada 09/07): o ERP segue sendo a base do %, e o CRM aparece do lado pra
    bater com o que o vendedor vê no Pipe. Degrada gracioso (retorna {} se falhar)."""
    union = "\n  UNION ALL\n".join(
        f"SELECT owner_id, value, status, local_won_date FROM `{CRM}.{t}` WHERE is_deleted IS NOT TRUE"
        for t in ["funil_vendas_distribuidores", "funil_vendas_farmacia",
                  "recorrencia_distribuidores", "recorrencia_farmacia",
                  "sac_vendas", "sac_atendimento"]
        # sac_vendas/sac_atendimento faltavam aqui (bug 13/07): a Geovana (SAC) tem
        # negócio ganho nesses dois funis, e o ganho_crm dela saía subcontado
        # (19,9% em vez de ~57%). Confirmado com o Alves: usar os funis do SAC também.
    )
    # users e df são independentes (nenhum usa o resultado do outro pra montar o SQL);
    # rodam juntos. Mantém o mesmo tratamento de erro de antes: users sem guarda (se
    # falhar, propaga), df com try/except (degrada pra {}).
    with ThreadPoolExecutor(max_workers=2) as ex:
        users_f = ex.submit(query, f"SELECT user_id, name FROM `{CRM}.dim_crm_user` WHERE is_active")
        df_f = ex.submit(query, f"""
            WITH d AS ({union})
            SELECT owner_id,
                   SUM(IF(status='won' AND local_won_date >= '{mes_ini}' AND local_won_date < '{mes_fim}', value, 0)) ganho_mes,
                   SUM(IF(status='won' AND local_won_date = '{ref}', value, 0)) ganho_hoje
            FROM d WHERE owner_id IS NOT NULL GROUP BY owner_id
        """)
        users = users_f.result()
        try:
            df = df_f.result()
        except Exception:
            return {}
    uid_to_erp = {}
    for _, r in users.iterrows():
        erp = _PIPE_NAME_TO_ERP.get(str(r["name"]).strip().upper())
        if erp:
            uid_to_erp[int(r["user_id"])] = erp
    out: dict = {}
    for _, r in df.iterrows():
        nn = uid_to_erp.get(int(r["owner_id"])) if pd.notna(r["owner_id"]) else None
        if not nn:
            continue
        cur = out.setdefault(nn, {"ganho_mes": 0.0, "ganho_hoje": 0.0})
        cur["ganho_mes"] += _f(r["ganho_mes"])
        cur["ganho_hoje"] += _f(r["ganho_hoje"])
    return out


def atividades_periodo(de: str, ate: str) -> dict:
    """Atividades por tipo/vendedor num intervalo de datas livre — desacoplado do
    mês da Gestão à Vista, pro filtro dedicado (Hoje/Semana/Mês/período custom)
    que Alves pediu (07/07 pt.3): antes só dava pra ver o mês inteiro.

    de/ate são INCLUSIVOS (ex: de=ate=hoje == só hoje); _atividades_tipo/
    _atividades_vendedor esperam fim EXCLUSIVO, por isso soma 1 dia no fim aqui.
    """
    ate_exclusivo = str(date.fromisoformat(ate) + timedelta(days=1))
    with ThreadPoolExecutor(max_workers=2) as ex:
        tipo_f = ex.submit(_atividades_tipo, de, ate_exclusivo)
        vend_f = ex.submit(_atividades_vendedor, de, ate_exclusivo)
        return {"atividades_tipo": tipo_f.result(), "atividades_vendedor": vend_f.result()}


def gestao_vista_meses() -> list[dict]:
    df = query(f"""
        SELECT DISTINCT DATE_TRUNC(o.invoice_date, MONTH) m
        FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
        WHERE o.invoice_date >= '2026-01-01' AND o.invoice_date IS NOT NULL
        ORDER BY m DESC
    """)
    out = []
    for m in pd.to_datetime(df["m"]).dt.date.tolist():
        out.append({"value": str(m), "label": f"{MESES_PT[m.month]}/{m.year}"})
    return out


def meta_atual(view_key: str, mes_ini: date) -> float:
    """Lê meta do Postgres (metas_equipe); se ausente ou erro, cai no fallback."""
    db = SessionLocal()
    try:
        m = meta_do_mes(db, mes_ini, view_key)
        if m is not None:
            return float(m)
    except Exception:
        pass
    finally:
        db.close()
    return META_EQUIPE.get(view_key, 0.0)


def _mascara_valores(d: dict) -> dict:
    """Zera os valores em R$ POR VENDEDOR pra quem não é gestor comercial (só %
    e status ficam). Card 1 (meta da equipe) fica intacto — valor pra todos.
    Defense-in-depth: mesmo inspecionando a API, o não-gestor não recebe os R$."""
    for r in d.get("ranking_mensal", []):
        r["realizado"] = 0.0; r["meta"] = 0.0; r["ganho_crm"] = 0.0
    for r in d.get("ranking_diario", []):
        r["vendido_hoje"] = 0.0; r["meta_diaria"] = 0.0
        r["falta_hoje"] = 0.0; r["ganho_crm_hoje"] = 0.0
    for r in d.get("venda_necessaria_dia", []):
        r["venda_dia"] = 0.0
    for r in d.get("vendedores", []):
        r["realizado"] = 0.0
        r["meta"] = None if r.get("meta") is None else 0.0
    return d


def gestao_vista(view: str = "Geral", mes: str | None = None, vendedor: str | None = None,
                  ver_valores: bool = True) -> dict:
    if view not in VIEWS:
        view = "Geral"
    view_key, group_filter = VIEWS[view]
    vendedor_norm = vendedor.strip().upper() if vendedor else None

    meses = gestao_vista_meses()
    mes_sel = pd.Timestamp(mes).date() if mes else (
        pd.Timestamp(meses[0]["value"]).date() if meses else date.today().replace(day=1))
    mes_ini = mes_sel.replace(day=1)
    mes_fim = (mes_ini.replace(month=mes_ini.month % 12 + 1, day=1)
               if mes_ini.month < 12 else date(mes_ini.year + 1, 1, 1))
    hoje = date.today()
    ref = hoje if (hoje.year == mes_ini.year and hoje.month == mes_ini.month) \
        else date.fromordinal(mes_fim.toordinal() - 1)
    mes_key = f"{mes_ini.year}-{mes_ini.month:02d}"
    du_total = dias_uteis_mes(ref)
    du_corr = dia_util_corrente(ref)
    du_rest = dias_uteis_restantes(ref)

    # A-D + pipelines + atividades: nenhuma depende do resultado de outra (só de
    # mes_ini/mes_fim/ref, já resolvidos acima) — dispara tudo num lote só, em vez
    # de 9 idas sequenciais ao BigQuery/Pipedrive.
    with ThreadPoolExecutor(max_workers=9) as ex:
        fa_f = ex.submit(query, f"""
            SELECT SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE {group_filter}
              AND o.invoice_date >= '{mes_ini}' AND o.invoice_date < '{mes_fim}'
        """)
        fb_f = ex.submit(query, f"""
            SELECT CASE WHEN o.salesperson_group_code IN ('FA','FR','PC')
                        THEN o.salesperson_group_code ELSE 'MKT' END g,
                   SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE (o.salesperson_group_code IN ('FA','FR','PC','EC') OR o.salesperson_group_code IS NULL)
              AND o.invoice_date >= '{mes_ini}' AND o.invoice_date < '{mes_fim}'
            GROUP BY 1
        """)
        rk_f = ex.submit(query, f"""
            SELECT INITCAP(LOWER({NOME_SEM_SUFIXO})) nome,
                   UPPER({NOME_SEM_SUFIXO}) nome_norm,
                   SUM(o.product_amount) v
            FROM `{ORDERS}.fact_sales_order` o {NAT_JOIN}
            WHERE {group_filter}
              AND o.invoice_date >= '{mes_ini}' AND o.invoice_date < '{mes_fim}'
              AND o.salesperson_name IS NOT NULL AND TRIM(o.salesperson_name) <> ''
              AND UPPER(o.salesperson_name) NOT LIKE 'KARINA%'
            GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10
        """)
        # "ganho no CRM" (Pipedrive deals won) por vendedor — no mês (ao lado do
        # faturado do ERP no ranking mensal) e no dia (base do ranking diário estrito).
        crm_ganho_f = ex.submit(_crm_ganho_por_vendedor, str(mes_ini), str(mes_fim), str(ref))
        # D) mapa vendedor→família (eng reversa)
        gd_f = ex.submit(query, f"""
            SELECT salesperson_name nome, salesperson_group_code g
            FROM `{ORDERS}.dim_salesperson`
            WHERE is_active AND salesperson_group_code IN ('FA','FR','PC')
            QUALIFY ROW_NUMBER() OVER (PARTITION BY salesperson_name
                ORDER BY CASE salesperson_group_code
                    WHEN 'FA' THEN 1 WHEN 'FR' THEN 2 ELSE 3 END) = 1
        """)
        pipe_hosp_f = ex.submit(_pipeline_stats, PIPE_HOSP, STAGES_HOSP)
        pipe_farma_f = ex.submit(_pipeline_stats, PIPE_FARMA, STAGES_FARMA)
        ativ_tipo_f = ex.submit(_atividades_tipo, str(mes_ini), str(mes_fim))
        ativ_vend_f = ex.submit(_atividades_vendedor, str(mes_ini), str(mes_fim))

        fa, fb, rk = fa_f.result(), fb_f.result(), rk_f.result()
        crm_ganho = crm_ganho_f.result()
        try:
            gd = gd_f.result()
            grupo_de = {str(r["nome"]).upper().strip(): str(r["g"]) for _, r in gd.iterrows()}
        except Exception:
            grupo_de = {}
        pipeline_hosp = pipe_hosp_f.result()
        pipeline_farma = pipe_farma_f.result()
        atividades_tipo = ativ_tipo_f.result()
        atividades_vendedor = ativ_vend_f.result()

    faturado_mes = _f(fa.iloc[0]["v"]) if not fa.empty else 0.0
    fat_grp = {str(r["g"]): _f(r["v"]) for _, r in fb.iterrows()}
    if view_key == "GERAL":
        faturado_mes += fat_grp.get("MKT", 0.0)

    meta = meta_atual(view_key, mes_ini)
    pct_meta = faturado_mes / meta if meta else 0.0
    falta = max(meta - faturado_mes, 0.0)

    ranking_mensal, ranking_diario, venda_dia = [], [], []
    vendedores_lista = []  # TODOS (com realizado); meta/pct só quando há meta no Pipedrive
    for _, r in rk.iterrows():
        nome = str(r["nome"])
        nome_norm = str(r["nome_norm"])
        v = _f(r["v"])
        meta_ind = meta_vendedor(nome_norm, mes_key)
        vendedores_lista.append({
            "vendedor": nome, "realizado": v,
            "meta": float(meta_ind) if meta_ind else None,
            "pct": (v / float(meta_ind)) if meta_ind else None,
        })
        # Ranking mensal/diário: TODOS aparecem (pedido Alves 16/07 — Eduardo não
        # tem meta de faturamento, mas precisa aparecer com o valor real dele em
        # ambos). Quem não tem meta entra com meta/pct nulos, sem % de atingimento
        # (não dá pra medir atingimento sem meta) — só o realizado/vendido fica visível.
        cg = crm_ganho.get(nome_norm, {"ganho_mes": 0.0, "ganho_hoje": 0.0})
        meta_ind_f = float(meta_ind) if meta_ind else None
        ranking_mensal.append({"vendedor": nome, "realizado": v, "meta": meta_ind_f,
                               "pct": (v / meta_ind_f) if meta_ind_f else None,
                               "ganho_crm": cg["ganho_mes"],
                               "pct_crm": (cg["ganho_mes"] / meta_ind_f) if meta_ind_f else None})
        # Ranking diário = ESTRITO por dia (ajuste 07/07 pt.2): compara o que o
        # vendedor VENDEU HOJE contra a meta diária fixa (mensal ÷ dias úteis).
        # Não olha o acumulado do mês — quem não vendeu hoje aparece atrasado,
        # mesmo que já tenha batido a meta do mês em dias anteriores.
        # Fonte = CRM (deals ganhos no Pipe), NÃO o faturado do ERP (decisão
        # 09/07, Vinícius): o ERP só conta nota emitida e mostra número mentiroso
        # pro vendedor que já vendeu mas ainda não faturou. No dia importa a venda.
        meta_diaria = (meta_ind_f / du_total) if (meta_ind_f and du_total) else None
        vendido_hoje = cg["ganho_hoje"]
        falta_hoje = max(meta_diaria - vendido_hoje, 0.0) if meta_diaria is not None else None
        bateu_hoje = (vendido_hoje >= meta_diaria) if meta_diaria else None
        ranking_diario.append({
            "vendedor": nome, "vendido_hoje": vendido_hoje, "meta_diaria": meta_diaria,
            "falta_hoje": falta_hoje, "bateu_hoje": bateu_hoje,
            "pct_hoje": (vendido_hoje / meta_diaria) if meta_diaria else None,
            "ganho_crm_hoje": cg["ganho_hoje"],
        })
        if meta_ind:
            meta_ind = float(meta_ind)
            # Venda necessária por dia exige meta (é (meta - realizado) / dias
            # restantes) — sem meta não há "necessário", fica de fora mesmo.
            vdia = venda_necessaria_dia(meta_ind, v, ref)
            venda_dia.append({"vendedor": nome, "venda_dia": vdia, "batida": v >= meta_ind})
    vendedores_lista.sort(key=lambda x: x["realizado"], reverse=True)
    # Quem tem % vem primeiro (ordenado por atingimento); sem meta vai pro fim,
    # ordenado por realizado (pct None não compara com float em Python).
    ranking_mensal.sort(key=lambda x: (x["pct"] is not None, x["pct"] or 0, x["realizado"]), reverse=True)
    # Melhor atingimento de hoje primeiro, pior por último (pedido 07/07 pt.2).
    ranking_diario.sort(key=lambda x: (x["pct_hoje"] is not None, x["pct_hoje"] or 0), reverse=True)
    venda_dia.sort(key=lambda x: x["venda_dia"], reverse=True)

    out = {
        "view": view, "view_key": view_key,
        "mes": str(mes_ini), "mes_label": f"{MESES_PT[mes_ini.month]}/{mes_ini.year}",
        "provisorio": PROVISORIO,
        "meta": meta, "faturado_mes": faturado_mes, "pct_meta": pct_meta, "falta": falta,
        "du_total": du_total, "du_corr": du_corr, "du_rest": du_rest,
        "canais": {
            "FA": fat_grp.get("FA", 0.0), "FR": fat_grp.get("FR", 0.0),
            "PC": fat_grp.get("PC", 0.0),
            "MKT": fat_grp.get("MKT", 0.0) if view_key == "GERAL" else None,
        },
        "ranking_mensal": ranking_mensal,
        "ranking_diario": ranking_diario,
        "venda_necessaria_dia": venda_dia,
        "vendedores": vendedores_lista,
        "pipeline_hosp": pipeline_hosp,
        "pipeline_farma": pipeline_farma,
        "eng_reversa_hosp": _eng_familia("FA", mes_key, du_total, grupo_de, vendedor_norm, crm_ganho),
        "eng_reversa_farma": _eng_familia("FR", mes_key, du_total, grupo_de, vendedor_norm, crm_ganho),
        "atividades_tipo": atividades_tipo,
        "atividades_vendedor": atividades_vendedor,
        "meses": meses,
    }
    # Reforço de acesso: não-gestor não recebe os valores em R$ por vendedor.
    return out if ver_valores else _mascara_valores(out)
