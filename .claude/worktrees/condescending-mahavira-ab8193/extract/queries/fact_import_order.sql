-- fact_import_order | Correção: PROCESSOS IMPORTAÇÕES PEDIDOS
SELECT
    YIMPORT AS import_number,
    YNUMPED AS order_number,
    YNOMCLI AS supplier_name,
    YVALUSD AS total_usd,
    YVALBRL AS total_brl,
    YVALII  AS ii_amount,
    YVALPIS AS pis_amount,
    YVALCOF AS cofins_amount,
    YVALICM AS icms_amount,
    YVALIPI AS ipi_amount
FROM [PROCESSOS IMPORTAÇÕES PEDIDOS]
WHERE YDATEXC IS NULL