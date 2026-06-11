"""
Projeção tipada — modo "raw = coluna" (sem JSON encapsulado).

Para fontes cujos registros são tabulares e estáveis (Pipedrive, dims), o bronze
é uma tabela de colunas TIPADAS declaradas, não um envelope `payload_json`.

A entidade declara `columns: [{name, path, type, transform?}]`. O `path` navega
o registro (dot-notation) ou lê do contexto da execução com prefixo `$`
(ex: `$pipeline_id` = constante da tabela). `etl_loaded_at` é sempre adicionada.

Tipos suportados: STRING, INT64, FLOAT64, BOOL, DATE, TIMESTAMP.
Transforms: `array_join` (lista → "a,b,c"). Datas/timestamps passam como string
ISO para o BigQuery inferir.

Custom fields do Pipedrive (enum→label, monetary→_value/_currency) são achatados
no CONECTOR antes da projeção — aqui o tratamento é genérico.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd


def typed_schema(columns: list[dict]) -> list[tuple[str, str]]:
    """bq_schema: etl_loaded_at + colunas declaradas (mesma ordem do crm_raw)."""
    return [("etl_loaded_at", "TIMESTAMP")] + [(c["name"], c.get("type", "STRING")) for c in columns]


def _dig(record: dict, path: str, context: dict):
    """Resolve um valor por path: `$chave` lê do contexto; senão dot-path no registro."""
    if path.startswith("$"):
        return context.get(path[1:])
    cur = record
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _coerce(value, bq_type: str, transform: str | None):
    if value is None:
        return None
    if transform == "array_join":
        if isinstance(value, (list, tuple)):
            return ",".join(str(v) for v in value) or None
        return str(value)
    if bq_type == "INT64":
        try:
            return int(float(value))  # tolera "1608.0", 1608.0, "1608"
        except (TypeError, ValueError):
            return None
    if bq_type == "FLOAT64":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if bq_type == "BOOL":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "t"}
    # STRING / DATE / TIMESTAMP → string (BQ infere data/timestamp do ISO)
    return str(value)


def build_typed_dataframe(
    records: list[dict],
    *,
    entity_cfg: dict,
    context: dict | None = None,
) -> pd.DataFrame:
    """Projeta registros achatados em um DataFrame de colunas tipadas declaradas."""
    context = context or {}
    columns = entity_cfg["columns"]
    loaded_at = datetime.now(timezone.utc).isoformat()

    rows = []
    for record in records:
        row = {"etl_loaded_at": loaded_at}
        for col in columns:
            val = _dig(record, col.get("path", col["name"]), context)
            row[col["name"]] = _coerce(val, col.get("type", "STRING"), col.get("transform"))
        rows.append(row)

    df = pd.DataFrame(rows)

    # Dtypes anuláveis: evita que INT64/BOOL com nulos virem float64 (1608 -> "1608.0",
    # que o BigQuery rejeita no INT64). Int64/boolean serializam NA como null no JSONL.
    for col in columns:
        name, ctype = col["name"], col.get("type", "STRING")
        if name not in df.columns:
            continue
        if ctype == "INT64":
            df[name] = df[name].astype("Int64")
        elif ctype == "BOOL":
            df[name] = df[name].astype("boolean")

    return df
