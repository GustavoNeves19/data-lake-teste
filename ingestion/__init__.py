"""
Framework de ingestão multi-fonte — "1 framework, N conectores".

A diferença entre fontes mora apenas no conector (`extract()`); tudo a jusante
— envelope bronze padronizado, carga no BigQuery, watermark e freshness — é
compartilhado. Fontes API (Umbler, Pipedrive, Gmail, GoTo) são declaradas em
`config/sources/<source>.json` e plugadas via `ingestion.connectors`.

Uso:
    py -3 -m ingestion ingest   --source umbler [--entity channels] [--full]
    py -3 -m ingestion test     --source umbler
    py -3 -m ingestion list     --source umbler
    py -3 -m ingestion freshness
"""
