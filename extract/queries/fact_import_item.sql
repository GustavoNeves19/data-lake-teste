-- fact_import_item | Correção: PROCESSOS IMPORTAÇÕES ITENS PEDIDOS
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YIMPORT AS import_number,
    YNUMPED AS order_number,
    YCODITM AS item_code,
    YQTDITM AS quantity,
    YVALITM AS unit_price,
    YVALUSD AS total_usd,
    YVALBRL AS total_brl,
    YVALII  AS ii_amount,
    YVALPIS AS pis_amount,
    YVALCOF AS cofins_amount,
    YVALICM AS icms_amount,
    YVALIPI AS ipi_amount,
    YCUSBRL AS landed_cost_brl,
    YDATEXC AS excluded_at
FROM [PROCESSOS IMPORTAÇÕES ITENS PEDIDOS]