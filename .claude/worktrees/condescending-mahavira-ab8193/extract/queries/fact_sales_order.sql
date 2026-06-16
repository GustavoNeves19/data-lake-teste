-- fact_sales_order | COMPRAS E VENDAS | YTIPOPE='S' (sem correções)
-- fact_purchase_order | COMPRAS E VENDAS | YTIPOPE='E' (sem correções)
SELECT
    YNUMERO AS order_number,
    YNUMORC AS quote_number,
    YCODCLI AS partner_code,
    YCODEMP AS company_code,
    YCODNAT AS nature_code,
    YCODPGT AS payment_cond_code,
    YCODTRA AS carrier_code,
    YDATPED AS order_date,
    YDATENT AS delivery_date,
    YDATNOT AS invoice_date,
    YSTATUS AS order_status,
    YCONFER AS reconciliation_flag,
    YNUMNOT AS invoice_number,
    YSERNOT AS invoice_series,
    YIDENFE AS nfe_key,
    YSEUPED AS supplier_order_ref,
    YVALPRO AS product_amount,
    YVALICM AS icms_amount,
    YVALIPI AS ipi_amount,
    YVALFRE AS freight_amount,
    YVALTOT AS total_amount,
    YDATINC AS created_at_erp,
    YUSAINC AS created_by_erp
FROM [COMPRAS E VENDAS]
WHERE YTIPOPE = 'S'
  AND YDATEXC IS NULL