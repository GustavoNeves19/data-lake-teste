"""
Matcher de cidades contra lista oficial do IBGE.
Usa múltiplas técnicas em cascata para corrigir nomes corrompidos por encoding.

Estratégia de matching:
  1. Sem "?": verifica match exato na lista IBGE → retorna direto
  2. Com "?": tenta regex (substitui "?" por "." e testa contra IBGE) → determinístico
  3. Fallback fuzzy com score adaptativo ao comprimento do nome
  4. Estado conhecido → filtra lista antes do match (elimina ambiguidades)

Pré-requisito: rodar setup_reference_data.py uma vez para baixar o CSV.
Dependência: pip install thefuzz python-Levenshtein
"""

import csv
import os
import re
from functools import lru_cache

import structlog

logger = structlog.get_logger(__name__)

# Caminho do CSV gerado pelo setup
_CSV_PATH = os.path.join(os.path.dirname(__file__), "ibge_municipios.csv")

# Cache da lista de municípios
_MUNICIPIOS: list[dict] | None = None
_CITY_NAMES: list[str] | None = None
_CITY_NAMES_SET: set[str] | None = None
_CITY_BY_STATE: dict[str, list[str]] | None = None


def _load_ibge() -> None:
    """Carrega o CSV do IBGE em memória (uma vez)."""
    global _MUNICIPIOS, _CITY_NAMES, _CITY_NAMES_SET, _CITY_BY_STATE

    if _MUNICIPIOS is not None:
        return

    if not os.path.exists(_CSV_PATH):
        logger.warning(
            "ibge_csv_not_found",
            path=_CSV_PATH,
            hint="Execute: python setup_reference_data.py",
        )
        _MUNICIPIOS = []
        _CITY_NAMES = []
        _CITY_NAMES_SET = set()
        _CITY_BY_STATE = {}
        return

    _MUNICIPIOS = []
    with open(_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            _MUNICIPIOS.append(row)

    _CITY_NAMES = [m["city_name"] for m in _MUNICIPIOS]
    _CITY_NAMES_SET = set(_CITY_NAMES)

    # Indexa por estado pra matching mais rápido e preciso
    _CITY_BY_STATE = {}
    for m in _MUNICIPIOS:
        state = m["state_code"]
        if state not in _CITY_BY_STATE:
            _CITY_BY_STATE[state] = []
        _CITY_BY_STATE[state].append(m["city_name"])

    logger.info("ibge_loaded", municipios=len(_MUNICIPIOS), states=len(_CITY_BY_STATE))


def get_all_city_names() -> list[str]:
    """Retorna lista de todos os nomes de cidades IBGE."""
    _load_ibge()
    return _CITY_NAMES or []


def get_cities_by_state(state_code: str) -> list[str]:
    """Retorna cidades de um estado específico."""
    _load_ibge()
    return (_CITY_BY_STATE or {}).get(state_code.upper(), [])


def _adaptive_min_score(name: str) -> int:
    """Score mínimo ajustado pelo comprimento — nomes curtos toleram mais diferença."""
    length = len(name)
    if length <= 6:
        return 70
    elif length <= 12:
        return 80
    return 85


def _regex_matches(corrupted: str, candidates: list[str]) -> list[str]:
    """
    Converte "?" em "." (qualquer caractere único) e faz fullmatch contra candidates.
    Retorna todos os nomes que casam com o padrão estrutural.
    """
    escaped = re.escape(corrupted)
    # re.escape transforma "?" em r"\?" — substituímos por "." (qualquer char único)
    pattern_str = escaped.replace(r"\?", ".")
    try:
        pattern = re.compile(f"^{pattern_str}$")
    except re.error:
        return []
    return [c for c in candidates if pattern.match(c)]


@lru_cache(maxsize=10000)
def match_city(
    corrupted_name: str,
    state_code: str | None = None,
    min_score: int = 85,
) -> tuple[str | None, int]:
    """
    Encontra o nome correto de uma cidade corrompida contra a lista IBGE.

    Cascata de técnicas:
      1. Sem "?": verifica existência exata na lista
      2. Com "?": regex (substitui "?" por ".") — determinístico
      3. Fuzzy com score adaptativo ao comprimento
      Estado informado → candidatos filtrados por UF em todas as técnicas

    Args:
        corrupted_name: Nome como veio do ERP (ex: "BEL?M", "S?O PAULO")
        state_code: UF para restringir a busca (melhora precisão)
        min_score: Score mínimo base (usado pelo fuzzy; adaptado pelo tamanho)

    Returns:
        Tupla (nome_correto, score) ou (None, 0) se não encontrou.
        Score 100 = match exato por regex; score < 100 = match fuzzy.
    """
    from thefuzz import fuzz, process

    _load_ibge()

    if not corrupted_name or not _CITY_NAMES:
        return (None, 0)

    name = corrupted_name.strip().upper()

    # ── Técnica 1: sem "?", verifica existência exata ──────────────────────────
    if "?" not in name:
        if name in (_CITY_NAMES_SET or set()):
            return (name, 100)
        return (None, 0)

    # Monta pools de candidatos (com estado = mais preciso)
    state_candidates: list[str] = (
        get_cities_by_state(state_code.upper()) if state_code else []
    )
    all_candidates: list[str] = _CITY_NAMES or []

    # ── Técnica 2: regex — substitui "?" por "." e testa estruturalmente ───────
    for pool in ([state_candidates] if state_candidates else []) + [all_candidates]:
        if not pool:
            continue
        matches = _regex_matches(name, pool)
        if len(matches) == 1:
            return (matches[0], 100)
        if len(matches) > 1:
            # Múltiplos candidatos — fuzzy desempata
            result = process.extractOne(name, matches, scorer=fuzz.ratio)
            if result:
                return (result[0], result[1])
        # Se regex não achou nada neste pool, tenta o próximo

    # ── Técnica 3: fuzzy com score adaptativo ──────────────────────────────────
    adaptive = _adaptive_min_score(name)

    if state_candidates:
        result = process.extractOne(name, state_candidates, scorer=fuzz.ratio)
        if result and result[1] >= adaptive:
            return (result[0], result[1])

    result = process.extractOne(name, all_candidates, scorer=fuzz.ratio)
    if result and result[1] >= adaptive:
        return (result[0], result[1])

    return (None, 0)


def build_city_fix_cache(
    corrupted_cities: list[str],
    state_codes: list[str | None] | None = None,
    min_score: int = 85,
) -> dict[str, str]:
    """
    Processa uma lista de cidades corrompidas e retorna dicionário de correções.
    Ideal para uso em batch antes de aplicar no DataFrame.

    Args:
        corrupted_cities: Lista de nomes corrompidos únicos
        state_codes: Lista paralela de UFs (opcional, melhora match)
        min_score: Score mínimo base para o fuzzy

    Returns:
        Dict {nome_corrompido: nome_correto} — apenas os que encontrou match.
    """
    _load_ibge()

    if not _CITY_NAMES:
        logger.warning("ibge_not_available_for_cache")
        return {}

    fixes: dict[str, str] = {}
    unmatched: list[str] = []
    by_regex = 0
    by_fuzzy = 0

    for i, city in enumerate(corrupted_cities):
        if not city or "?" not in str(city):
            continue

        state = state_codes[i] if state_codes and i < len(state_codes) else None
        corrected, score = match_city(city, state_code=state, min_score=min_score)

        if corrected:
            fixes[city] = corrected
            if score == 100:
                by_regex += 1
            else:
                by_fuzzy += 1
        else:
            unmatched.append(city)

    logger.info(
        "city_cache_built",
        total_input=len(corrupted_cities),
        matched=len(fixes),
        unmatched=len(unmatched),
        by_regex=by_regex,
        by_fuzzy=by_fuzzy,
    )

    if unmatched:
        logger.warning("cities_unmatched", count=len(unmatched), samples=unmatched[:15])

    return fixes
