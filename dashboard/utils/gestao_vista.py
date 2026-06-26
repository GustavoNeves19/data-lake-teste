# -*- coding: utf-8 -*-
"""Fundação do Painel de Gestão à Vista (reunião 12/06/2026).

Centraliza o que NÃO vem do BigQuery: o calendário de dias úteis e as metas
(equipe + por vendedor). As metas são PROVISÓRIAS até o Alves mandar as oficiais
de junho no WhatsApp (segunda-feira) — trocar só os números em METAS_*.

Regras de cálculo fechadas na reunião:
  - projeção_esperada = (meta / dias_úteis_mês) * dia_útil_corrente
  - venda_necessaria_dia = (meta - realizado) / dias_úteis_restantes
  - dias quebrados por DIAS ÚTEIS = seg-sex MENOS feriados (Alves confirmou 25/06/2026).
"""
from __future__ import annotations

from datetime import date
import numpy as np

# ── Feriados que afetam dias úteis (PI / Teresina) ───────────────
# Junho/2026: Alves confirmou 2 feriados => 20 dias úteis (22 dias de semana − 2).
#   04/06 Corpus Christi · ⚠️ o 2º feriado precisa ser confirmado com o Alves.
# Manter como lista por ano para o cálculo seguir correto nos próximos meses.
FERIADOS: list[date] = [
    date(2026, 5, 1),    # Dia do Trabalho
    date(2026, 6, 4),    # Corpus Christi
    date(2026, 6, 24),   # São João — feriado em Teresina/PI (confirmar c/ Alves)
]

# ── Metas PROVISÓRIAS (trocar pelos números oficiais do Alves) ───
# Fonte oficial: insights do Pipedrive (Alves preenche todo mês). Plano B: ERP.
META_EQUIPE: dict[str, float] = {
    # Geral agora INCLUI o Marketplace (decisão Alves, call 23/06: "pra meta tem que ter").
    # 1.568.000 é a meta geral que o Alves citou na call (provisória, igual as demais —
    # trocar pelos números oficiais de junho). O realizado do Geral também passa a somar
    # o Marketplace (EC + vendas sem grupo). Nas visões por canal, o Marketplace fica fora.
    "GERAL":      1_568_000.0,
    "HOSPITALAR": 900_000.0,
    "FARMACIA":   100_000.0,
}
# vendedor (nome normalizado UPPER do ERP) -> meta individual por mês ("YYYY-MM")
# Fonte: Pipedrive Goals API v1 (Alves preenche). Trocar quando vierem as oficiais.
METAS_VENDEDOR: dict[str, dict[str, float]] = {
    "GUILHERME DE AQUINO MARQUES": {"2026-05": 458898, "2026-06": 407394},
    "KAUA RODRIGUES":              {"2026-05": 313000, "2026-06": 310000},
    "RICHARD LUCAS":               {"2026-05": 76000,  "2026-06": 83335},
    "CAUA RIBEIRO":                {"2026-05": 58639,  "2026-06": 69509},
    "KAUAN RAMOS":                 {"2026-05": 54196,  "2026-06": 55487},
    "GEOVANA GOMES":               {"2026-05": 57333,  "2026-06": 16125},
}

PROVISORIO = True  # vira False quando as metas oficiais entrarem


def dias_uteis_mes(ref: date) -> int:
    """Total de dias úteis (seg–sex menos feriados) no mês de `ref`."""
    inicio = ref.replace(day=1)
    fim = (inicio.replace(month=inicio.month % 12 + 1, day=1)
           if inicio.month < 12 else date(inicio.year + 1, 1, 1))
    fer = [d for d in FERIADOS if inicio <= d < fim]
    return int(np.busday_count(inicio, fim, holidays=fer))


def dia_util_corrente(ref: date) -> int:
    """Qual dia útil do mês é `ref` (1-based). Se `ref` cair em fim de semana/
    feriado, conta os dias úteis já decorridos até ele inclusive."""
    inicio = ref.replace(day=1)
    fer = [d for d in FERIADOS if inicio <= d <= ref]
    # busday_count é [início, fim) — soma 1 dia pra incluir o próprio `ref` se for útil
    return int(np.busday_count(inicio, ref, holidays=fer)) + (
        1 if np.is_busday(ref, holidays=[d for d in FERIADOS]) else 0
    )


def dias_uteis_restantes(ref: date) -> int:
    """Dias úteis que ainda faltam no mês CONTANDO o próprio dia `ref` (decisão do
    Alves 26/06: hoje ainda é dia útil, então entra na conta). Mínimo 1."""
    total = dias_uteis_mes(ref)
    # dia_util_corrente já inclui hoje; o +1 devolve o "hoje" como dia restante.
    return max(total - dia_util_corrente(ref) + 1, 1)


def projecao_esperada(meta: float, ref: date) -> float:
    """Onde a equipe DEVERIA estar hoje para bater a meta no fim do mês."""
    return meta / dias_uteis_mes(ref) * dia_util_corrente(ref)


def venda_necessaria_dia(meta: float, realizado: float, ref: date) -> float:
    """Quanto precisa vender por dia útil restante para fechar a meta."""
    falta = max(meta - realizado, 0.0)
    return falta / dias_uteis_restantes(ref)


# ── Engenharia reversa — POR USUÁRIO (reunião 23/06) ──────────────────────────
# Decisões: (Alves) quebrar a reversa por VENDEDOR, não por família; (Diego) NÃO
# hardcodar o agrupamento — quem é de qual família vem do ERP (YGRUVEN do
# dim_salesperson), o código só consulta. Por isso aqui ficam SÓ as taxas de
# conversão + ticket (da planilha "Engenharia reversa.xlsx" do Alves). A META vem
# do Pipedrive (METAS_VENDEDOR) e o GRUPO vem do ERP (resolvido na view).
# Funil reverso: vendas = meta/ticket → fechamentos = vendas/tx_fech → negociações
#   = fech/tx_neg → orçamentos = neg/tx_orc → conexões = orç/tx_con → contatos/mês
#   = conexões/tx_cont → contatos/dia = /dias_úteis. Nomes = UPPER do ERP.
TAXAS_CONVERSAO: dict[str, dict] = {
    "RICHARD LUCAS":               {"ticket": 876.14,  "tx_fech": 0.83, "tx_neg": 0.92, "tx_orc": 0.27, "tx_con": 0.75, "tx_cont": 0.54},
    "KAUA RODRIGUES":              {"ticket": 3616.23, "tx_fech": 0.65, "tx_neg": 0.74, "tx_orc": 0.50, "tx_con": 0.96, "tx_cont": 0.72},
    "GUILHERME DE AQUINO MARQUES": {"ticket": 6248.33, "tx_fech": 1.00, "tx_neg": 0.95, "tx_orc": 0.70, "tx_con": 0.77, "tx_cont": 0.36},
    "CAUA RIBEIRO":                {"ticket": 859.80,  "tx_fech": 0.92, "tx_neg": 1.00, "tx_orc": 0.38, "tx_con": 0.31, "tx_cont": 0.46},
    "GEOVANA GOMES":               {"ticket": 739.20,  "tx_fech": 0.92, "tx_neg": 0.87, "tx_orc": 0.38, "tx_con": 0.98, "tx_cont": 0.36},
}

FAMILIA_LABEL = {"FA": "Hospitalar", "FR": "Farmácia", "PC": "SAC"}


def taxas_aproximadas_hospitalar() -> dict:
    """Kauan Ramos ainda não está na planilha do Alves. Até ele cadastrar, aproximo
    as taxas + ticket pela MÉDIA do Hospitalar (Guilherme + Kauã + Richard)."""
    base = [TAXAS_CONVERSAO[v] for v in
            ("GUILHERME DE AQUINO MARQUES", "KAUA RODRIGUES", "RICHARD LUCAS")]
    chaves = ("ticket", "tx_fech", "tx_neg", "tx_orc", "tx_con", "tx_cont")
    return {k: round(sum(b[k] for b in base) / len(base), 4) for k in chaves}


def eng_reversa_funil(meta: float, taxas: dict, dias_uteis: int = 22) -> dict:
    """Funil reverso de UM vendedor: meta (Pipe) + ticket + 5 taxas (planilha Alves)."""
    t = taxas or {}
    vendas = meta / t["ticket"] if t.get("ticket") else 0.0
    fech = vendas / t["tx_fech"] if t.get("tx_fech") else 0.0
    neg  = fech   / t["tx_neg"]  if t.get("tx_neg")  else 0.0
    orc  = neg    / t["tx_orc"]  if t.get("tx_orc")  else 0.0
    con  = orc    / t["tx_con"]  if t.get("tx_con")  else 0.0
    cont = con    / t["tx_cont"] if t.get("tx_cont") else 0.0
    return {"meta": meta, "vendas": vendas, "fechamentos": fech, "negociacoes": neg,
            "orcamentos": orc, "conexoes": con, "contatos_mes": cont,
            "contatos_dia": cont / dias_uteis if dias_uteis else 0.0}
