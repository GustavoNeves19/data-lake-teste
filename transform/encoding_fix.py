"""
Correção de encoding corrompido no ERP — Orquestrador.

3 camadas de correção:
  Camada 1 — Referência autoritativa (IBGE): cidades via fuzzy matching
  Camada 2 — Dicionários de domínio: termos técnicos e empresariais
  Camada 3 — Log de não resolvidos: pra revisão manual periódica

Uso:
    from transform.encoding_fix import fix_encoding_issues
    df = fix_encoding_issues(df, city_column="city", state_column="state")
"""

import pandas as pd
import structlog

from transform.mappings import DOMAIN_ENCODING_PATTERNS

logger = structlog.get_logger(__name__)

# Flag pra saber se o IBGE está disponível
_IBGE_AVAILABLE = False
try:
    from transform.reference_data.city_matcher import build_city_fix_cache, match_city
    _IBGE_AVAILABLE = True
except ImportError:
    logger.warning("ibge_matcher_unavailable", hint="pip install thefuzz python-Levenshtein")


def _fix_cities(
    df: pd.DataFrame,
    city_column: str,
    state_column: str | None = None,
    min_score: int = 85,
) -> tuple[pd.DataFrame, int]:
    """
    Camada 1: Corrige nomes de cidades via fuzzy match contra IBGE.

    Retorna (df_corrigido, total_de_correções).
    """
    if not _IBGE_AVAILABLE:
        return df, 0

    if city_column not in df.columns:
        return df, 0

    # Pega só os valores únicos com "?" pra não fazer fuzzy match repetido
    mask = df[city_column].str.contains("?", na=False, regex=False)
    if not mask.any():
        return df, 0

    corrupted_cities = df.loc[mask, city_column].unique().tolist()

    # Se tem coluna de estado, usa pra melhorar o match
    state_codes = None
    if state_column and state_column in df.columns:
        # Monta lista paralela de estados pra cada cidade corrupta
        city_state_map = (
            df.loc[mask, [city_column, state_column]]
            .drop_duplicates(subset=[city_column])
            .set_index(city_column)[state_column]
            .to_dict()
        )
        state_codes = [city_state_map.get(c) for c in corrupted_cities]

    # Constrói cache de correções
    fixes = build_city_fix_cache(corrupted_cities, state_codes, min_score=min_score)

    if not fixes:
        return df, 0

    # Aplica correções
    df = df.copy()
    fixed_count = 0
    for wrong, right in fixes.items():
        count = (df[city_column] == wrong).sum()
        if count > 0:
            df[city_column] = df[city_column].replace(wrong, right)
            fixed_count += count

    logger.info("cities_fixed_ibge", column=city_column, corrections=fixed_count, unique_patterns=len(fixes))
    return df, fixed_count


def _fix_domain_terms(
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> tuple[pd.DataFrame, int]:
    """
    Camada 2: Aplica dicionários de domínio (produtos, empresas, termos comuns).

    Retorna (df_corrigido, total_de_correções).
    """
    df = df.copy()

    if columns is None:
        columns = df.select_dtypes(include=["object", "string"]).columns.tolist()

    fixed_count = 0
    for col in columns:
        if col not in df.columns:
            continue

        # Só processa se tem "?" na coluna
        has_question = df[col].str.contains("?", na=False, regex=False)
        if not has_question.any():
            continue

        for wrong, right in DOMAIN_ENCODING_PATTERNS.items():
            mask = df[col].str.contains(wrong, na=False, regex=False)
            count = mask.sum()
            if count > 0:
                df[col] = df[col].str.replace(wrong, right, regex=False)
                fixed_count += count

    if fixed_count > 0:
        logger.info("domain_terms_fixed", corrections=fixed_count)

    return df, fixed_count


def _log_unfixed(
    df: pd.DataFrame,
    columns: list[str] | None = None,
) -> int:
    """
    Camada 3: Loga valores que ainda têm "?" após as camadas 1 e 2.
    Estes precisam de revisão manual — adicionar nos dicionários de mappings/.

    Retorna quantidade de valores únicos não resolvidos.
    """
    if columns is None:
        columns = df.select_dtypes(include=["object", "string"]).columns.tolist()

    unfixed = {}
    for col in columns:
        if col not in df.columns:
            continue

        still_has = df[col].str.contains("?", na=False, regex=False)
        if still_has.any():
            samples = df.loc[still_has, col].unique()[:15].tolist()
            unfixed[col] = {"count": int(still_has.sum()), "samples": samples}

    total_unfixed = sum(v["count"] for v in unfixed.values())

    if unfixed:
        logger.warning(
            "encoding_still_unfixed",
            total_values=total_unfixed,
            columns=list(unfixed.keys()),
            details=unfixed,
        )

    return total_unfixed


def fix_encoding_issues(
    df: pd.DataFrame,
    city_column: str | None = None,
    state_column: str | None = None,
    skip_columns: list[str] | None = None,
    min_city_score: int = 85,
) -> pd.DataFrame:
    """
    Corrige encoding corrompido em todas as colunas string do DataFrame.

    Executa 3 camadas em sequência:
      1. Cidades (fuzzy match IBGE) — se city_column for informado
      2. Termos de domínio (dicionários manuais)
      3. Log de não resolvidos (pra revisão)

    Args:
        df: DataFrame com dados do ERP
        city_column: Nome da coluna de cidade (ex: "city"). None = pula camada 1
        state_column: Coluna de UF pra ajudar o match de cidade. Opcional
        skip_columns: Colunas pra ignorar (ex: colunas de código)
        min_city_score: Score mínimo pra match de cidade (0-100)

    Returns:
        DataFrame com encoding corrigido.
    """
    total_fixed = 0

    # Verifica se tem algo pra corrigir
    string_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    if skip_columns:
        string_cols = [c for c in string_cols if c not in skip_columns]

    # Defensivo: garante que a coluna realmente contém só str/NaN
    # (pyodbc às vezes devolve object com mixed types de LEFT JOINs)
    def _is_str_col(col):
        s = df[col].dropna()
        return s.empty or s.map(lambda x: isinstance(x, str)).all()

    string_cols = [c for c in string_cols if _is_str_col(c)]

    has_any_question = any(
        df[col].str.contains("?", na=False, regex=False).any()
        for col in string_cols
        if col in df.columns
    )

    if not has_any_question:
        logger.debug("encoding_no_issues_found")
        return df

    # Camada 1: Cidades (IBGE)
    if city_column:
        df, city_fixes = _fix_cities(df, city_column, state_column, min_city_score)
        total_fixed += city_fixes

    # Camada 2: Termos de domínio
    df, domain_fixes = _fix_domain_terms(df, columns=string_cols)
    total_fixed += domain_fixes

    # Camada 3: Log do que sobrou
    unfixed = _log_unfixed(df, columns=string_cols)

    logger.info(
        "encoding_fix_complete",
        total_fixed=total_fixed,
        total_unfixed=unfixed,
    )

    return df
