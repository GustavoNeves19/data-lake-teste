"""
Módulo de transformação.
Conversões de tipo, surrogate keys, colunas de auditoria e limpeza de dados.
Baseado no schema dimensional v5.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import structlog

from transform.encoding_fix import fix_encoding_issues
from transform.encoding_config import get_encoding_config

logger = structlog.get_logger(__name__)


# ══════════════════════════════════════════════════════════
# SURROGATE KEYS
# ══════════════════════════════════════════════════════════

def add_surrogate_key(df: pd.DataFrame, sk_column: str) -> pd.DataFrame:
    """Insere surrogate key auto-incremento (1, 2, 3...) como primeira coluna."""
    df = df.copy()
    df.insert(0, sk_column, range(1, len(df) + 1))
    return df


# ══════════════════════════════════════════════════════════
# AUDITORIA
# ══════════════════════════════════════════════════════════

def add_audit_columns(df: pd.DataFrame, include_updated: bool = False) -> pd.DataFrame:
    """Adiciona loaded_at (e opcionalmente updated_at) com timestamp UTC."""
    df = df.copy()
    now = datetime.now(timezone.utc)
    df["loaded_at"] = now
    if include_updated:
        df["updated_at"] = now
    return df


# ══════════════════════════════════════════════════════════
# CONVERSÕES DE TIPO
# ══════════════════════════════════════════════════════════

def cast_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Converte colunas para DATE, inválidos → NaT."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


def cast_timestamps(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Converte colunas para TIMESTAMP UTC, inválidos → NaT."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


def cast_numerics(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Converte colunas para float64, não numéricos → NaN."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return df


def cast_integers(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Converte colunas para Int64 nullable (pd.Int64Dtype)."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(pd.Int64Dtype())
    return df


def cast_booleans(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Converte colunas para boolean."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype(bool)
    return df


def cast_strings(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Converte para pd.StringDtype, strip + vazio → pd.NA."""
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(pd.StringDtype())
                .str.strip()
                .replace({"": pd.NA, "None": pd.NA, "nan": pd.NA, "NaN": pd.NA})
            )
    return df


# LIMPEZA

def clean_strings(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa todas as colunas string: strip + vazio → None + remove null bytes."""
    df = df.copy()
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace("\x00", "", regex=False)  # ← remove null bytes
            .str.strip()
            .replace({"": None, "None": None, "nan": None, "NaN": None})
        )
    return df


def remove_duplicates(
    df: pd.DataFrame, subset: list[str] | None = None
) -> pd.DataFrame:
    """Remove duplicatas, mantém primeira ocorrência."""
    before = len(df)
    df = df.drop_duplicates(subset=subset, keep="first")
    removed = before - len(df)
    if removed > 0:
        logger.warning("duplicates_removed", count=removed, subset=subset)
    return df


# ══════════════════════════════════════════════════════════
# SNAPSHOT — lógica especial para snapshot_inventory_balance
# ══════════════════════════════════════════════════════════

def add_snapshot_date(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona snapshot_date = data atual (foto diária do saldo)."""
    df = df.copy()
    df["snapshot_date"] = datetime.now(timezone.utc).date()
    return df


# ══════════════════════════════════════════════════════════
# CLASSIFICAÇÃO DE TIPOS A PARTIR DO BQ_SCHEMA
# ══════════════════════════════════════════════════════════

def _classify_columns(bq_schema: list[tuple]) -> dict[str, list[str]]:
    """
    Classifica colunas do bq_schema por tipo de conversão.
    Ignora colunas sk_ e auditoria (geradas no pipeline).
    """
    skip_prefixes = ("sk_",)
    skip_names = {"loaded_at", "updated_at", "snapshot_date"}

    groups: dict[str, list[str]] = {
        "dates": [],
        "timestamps": [],
        "numerics": [],
        "integers": [],
        "booleans": [],
        "strings": [],
    }

    for col_name, col_type in bq_schema:
        if col_name in skip_names or col_name.startswith(skip_prefixes):
            continue

        match col_type:
            case "DATE":
                groups["dates"].append(col_name)
            case "TIMESTAMP":
                groups["timestamps"].append(col_name)
            case "NUMERIC":
                groups["numerics"].append(col_name)
            case "INT64":
                groups["integers"].append(col_name)
            case "BOOL":
                groups["booleans"].append(col_name)
            case "STRING":
                groups["strings"].append(col_name)

    return groups


# ══════════════════════════════════════════════════════════
# TRANSFORMAÇÃO PRINCIPAL
# ══════════════════════════════════════════════════════════

def transform_entity(
    df: pd.DataFrame,
    entity_name: str,
    entity_config: dict,
) -> pd.DataFrame:
    """
    Aplica todas as transformações para uma entidade:
      1. Limpeza de strings
      2. Remoção de duplicatas
      3. Snapshot date (se SNAPSHOT)
      4. Conversões de tipo (inferidas do bq_schema)
      5. Surrogate key
      6. Colunas de auditoria (loaded_at, updated_at)

    Args:
        df:            DataFrame extraído do ERP
        entity_name:   Nome (ex: 'dim_company')
        entity_config: Dict da entidade vindo de ENTITIES no settings.py

    Returns:
        DataFrame transformado e pronto para BigQuery.
    """
    bq_schema = entity_config["bq_schema"]
    sk_column = entity_config.get("sk_column")
    entity_type = entity_config.get("entity_type", "")

    start_rows = len(df)
    logger.info("transform_start", entity=entity_name, rows=start_rows)


    # Fix encoding (validação de caracters invalidos)
    enc_config = get_encoding_config(entity_name)
    df = fix_encoding_issues(
        df,
        city_column=enc_config.get("city_column"),
        state_column=enc_config.get("state_column"),
        skip_columns=enc_config.get("skip_columns"),
    )
    
    # 1. Limpeza geral
    df = clean_strings(df)
    df = remove_duplicates(df)

    # 2. Snapshot date (apenas para SNAPSHOT)
    if entity_type == "SNAPSHOT":
        df = add_snapshot_date(df)

    # 3. Conversões de tipo baseadas no schema
    types = _classify_columns(bq_schema)
    if types["strings"]:
        df = cast_strings(df, types["strings"])
    if types["integers"]:
        df = cast_integers(df, types["integers"])
    if types["numerics"]:
        df = cast_numerics(df, types["numerics"])
    if types["booleans"]:
        df = cast_booleans(df, types["booleans"])
    if types["dates"]:
        df = cast_dates(df, types["dates"])
    if types["timestamps"]:
        df = cast_timestamps(df, types["timestamps"])

    # 4. Surrogate key
    if sk_column:
        df = add_surrogate_key(df, sk_column)

    # 5. Auditoria
    has_updated = any(col == "updated_at" for col, _ in bq_schema)
    df = add_audit_columns(df, include_updated=has_updated)

    logger.info(
        "transform_ok",
        entity=entity_name,
        rows_in=start_rows,
        rows_out=len(df),
    )
    return df
