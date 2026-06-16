-- fact_import_process | PROCESSOS IMPORTAÇÕES (sem correções)
SELECT
    YIMPORT    AS import_number,
    YNUMERODI  AS di_number,
    YDATADI    AS di_date,
    YCAMBIODI  AS di_exchange_rate,
    YARMAZENAG AS storage_cost,
    YAFRMM     AS afrmm_cost,
    YANVISA    AS anvisa_cost,
    YSISCOMEX  AS siscomex_cost,
    YFRETEINTE AS intl_freight,
    YFRETENACI AS domestic_freight,
    YTOTALFRET AS total_freight,
    YVALUSD    AS total_usd,
    YVALBRL    AS total_brl
FROM [PROCESSOS IMPORTAÇÕES]
WHERE YDATEXC IS NULL
