-- fact_tax_ledger | LIVROS FISCAIS (sem correções)
SELECT
    YNUMERO AS ledger_number,
    YNUMPED AS order_number,
    YNUMNOT AS invoice_number,
    YTIPOPE AS operation_type,
    YCODNAT AS nature_code,
    YVALPRO AS product_amount,
    YVALICM AS icms_amount,
    YVALIPI AS ipi_amount,
    YVALTOT AS total_amount
FROM [LIVROS FISCAIS]
WHERE YDATEXC IS NULL
