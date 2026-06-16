# -*- coding: utf-8 -*-
"""Fundação do Painel de Gestão à Vista (reunião 12/06/2026).

Centraliza o que NÃO vem do BigQuery: o calendário de dias úteis e as metas
(equipe + por vendedor). As metas são PROVISÓRIAS até o Alves mandar as oficiais
de junho no WhatsApp (segunda-feira) — trocar só os números em METAS_*.

Regras de cálculo fechadas na reunião:
  - projeção_esperada = (meta / dias_úteis_mês) * dia_útil_corrente
  - venda_necessaria_dia = (meta - realizado) / dias_úteis_restantes
  - dias quebrados por DIAS ÚTEIS (não por 30); feriados contam.
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
    "GERAL":      1_018_000.0,   # Marketplace fora · Geral = Hospitalar + Farmácia (soma das metas individuais)
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
    """Dias úteis que ainda faltam no mês A PARTIR de `ref` (exclui o próprio dia
    já contado como decorrido). Mínimo 1 para não dividir por zero."""
    total = dias_uteis_mes(ref)
    return max(total - dia_util_corrente(ref), 1)


def projecao_esperada(meta: float, ref: date) -> float:
    """Onde a equipe DEVERIA estar hoje para bater a meta no fim do mês."""
    return meta / dias_uteis_mes(ref) * dia_util_corrente(ref)


def venda_necessaria_dia(meta: float, realizado: float, ref: date) -> float:
    """Quanto precisa vender por dia útil restante para fechar a meta."""
    falta = max(meta - realizado, 0.0)
    return falta / dias_uteis_restantes(ref)


# ── Engenharia reversa — parâmetros do Alves (planilha "Engenharia reversa.xlsx", 16/06) ──
# Por vendedor: meta, ticket médio (3 meses) e as 5 taxas de conversão do funil.
# Funil reverso: vendas = meta/ticket → fechamentos = vendas/tx_fech → negociações = fech/tx_neg
#   → orçamentos = neg/tx_orc → conexões = orç/tx_con → contatos/mês = conexões/tx_cont → /dia = /22.
ENG_REVERSA: dict[str, dict] = {
    "RICHARD LUCAS":               {"meta": 45951.40,  "ticket": 876.14,  "tx_fech": 0.83, "tx_neg": 0.92, "tx_orc": 0.27, "tx_con": 0.75, "tx_cont": 0.54},
    "KAUA RODRIGUES":              {"meta": 262620.90, "ticket": 3616.23, "tx_fech": 0.65, "tx_neg": 0.74, "tx_orc": 0.50, "tx_con": 0.96, "tx_cont": 0.72},
    "GUILHERME DE AQUINO MARQUES": {"meta": 333209.90, "ticket": 6248.33, "tx_fech": 1.00, "tx_neg": 0.95, "tx_orc": 0.70, "tx_con": 0.77, "tx_cont": 0.36},
    "CAUA RIBEIRO":                {"meta": 32236.65,  "ticket": 859.80,  "tx_fech": 0.92, "tx_neg": 1.00, "tx_orc": 0.38, "tx_con": 0.31, "tx_cont": 0.46},
    "GEOVANA GOMES":               {"meta": 57815.43,  "ticket": 739.20,  "tx_fech": 0.92, "tx_neg": 0.87, "tx_orc": 0.38, "tx_con": 0.98, "tx_cont": 0.36},
}
ENG_CANAL: dict[str, list[str]] = {
    "HOSPITALAR": ["GUILHERME DE AQUINO MARQUES", "KAUA RODRIGUES", "RICHARD LUCAS"],
    "FARMACIA":   ["CAUA RIBEIRO"],
}


def eng_reversa_funil(p: dict, dias_uteis: int = 22) -> dict:
    """Funil reverso do Alves a partir de meta + ticket + 5 taxas de conversão."""
    vendas = p["meta"] / p["ticket"] if p.get("ticket") else 0.0
    fech = vendas / p["tx_fech"] if p.get("tx_fech") else 0.0
    neg  = fech   / p["tx_neg"]  if p.get("tx_neg")  else 0.0
    orc  = neg    / p["tx_orc"]  if p.get("tx_orc")  else 0.0
    con  = orc    / p["tx_con"]  if p.get("tx_con")  else 0.0
    cont = con    / p["tx_cont"] if p.get("tx_cont") else 0.0
    return {"meta": p["meta"], "vendas": vendas, "fechamentos": fech, "negociacoes": neg,
            "orcamentos": orc, "conexoes": con, "contatos_mes": cont,
            "contatos_dia": cont / dias_uteis if dias_uteis else 0.0}


def eng_reversa_canal(canal_key: str, dias_uteis: int = 22) -> dict:
    """Soma o funil reverso dos vendedores de um canal (Hospitalar/Farmácia)."""
    agg = {k: 0.0 for k in ("meta", "vendas", "fechamentos", "negociacoes",
                            "orcamentos", "conexoes", "contatos_mes", "contatos_dia")}
    for v in ENG_CANAL.get(canal_key, []):
        p = ENG_REVERSA.get(v)
        if not p:
            continue
        f = eng_reversa_funil(p, dias_uteis)
        for k in agg:
            agg[k] += f[k]
    return agg
