-- fact_tax_ledger | LIVROS FISCAIS (sem correções)
-- Bronze pura: filtro YDATEXC vive no silver.
SELECT
    YNUMERO AS ledger_number,
    YNUMPED AS order_number,
    YNUMNOT AS invoice_number,
    YTIPOPE AS operation_type,
    YCODNAT AS nature_code,
    YVALPRO AS product_amount,
    YVALICM AS icms_amount,
    YVALIPI AS ipi_amount,
    YVALTOT AS total_amount,
    YDATEXC AS excluded_at
FROM [LIVROS FISCAIS]
