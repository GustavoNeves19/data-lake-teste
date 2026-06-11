-- fact_sales_order | COMPRAS E VENDAS | YTIPOPE='S' (sem correções)
-- fact_purchase_order | COMPRAS E VENDAS | YTIPOPE='E' (sem correções)
--
-- NOTA (mai/2026):
--   • YCODVEN  = canal de venda (000003=NSR direto, 92=ML, AM=Amazon, SH=Shopee, LI=Loja Integrada,
--                OL=Olist, 90=CNova, 91=Magalu, AME=Americanas, 000054=Site-Loja, codes REDE = redes farmacia)
--   • YCODVEN2 = codigo individual do vendedor (pessoa fisica) → JOIN com ATENDENTES p/ nome
--   • a.YGRUVEN = grupo do vendedor (FR=Farmácia, FA=Hospitalar/Farmer, PC=SAC/Peças).
--                Decisão reunião 27/05/2026 com Frederico/DC-Info: filtro RFV deve ser por
--                grupo, não por lista de vendedores ativos (que ignora inativos do período).
SELECT
    cv.YNUMERO AS order_number,
    cv.YNUMORC AS quote_number,
    cv.YCODCLI AS partner_code,
    cv.YCODEMP AS company_code,
    cv.YCODNAT AS nature_code,
    cv.YCODPGT AS payment_cond_code,
    cv.YCODTRA AS carrier_code,
    cv.YCODVEN  AS channel_code,
    cv.YCODVEN2 AS salesperson_code,
    a.YNOMVEN  AS salesperson_name,
    NULLIF(a.YGRUVEN, '') AS salesperson_group_code,
    ach.YNOMVEN AS channel_name,
    cv.YDATPED AS order_date,
    cv.YDATENT AS delivery_date,
    cv.YDATNOT AS invoice_date,
    cv.YSTATUS AS order_status,
    cv.YCONFER AS reconciliation_flag,
    cv.YNUMNOT AS invoice_number,
    cv.YSERNOT AS invoice_series,
    cv.YIDENFE AS nfe_key,
    cv.YSEUPED AS supplier_order_ref,
    cv.YVALPRO AS product_amount,
    cv.YVALICM AS icms_amount,
    cv.YVALIPI AS ipi_amount,
    cv.YVALFRE AS freight_amount,
    cv.YVALTOT AS total_amount,
    cv.YDATINC AS created_at_erp,
    COALESCE(cv.YDATALT, cv.YDATINC) AS updated_at_erp,
    cv.YUSAINC AS created_by_erp,
    cv.YDATEXC AS excluded_at
FROM [COMPRAS E VENDAS] cv
LEFT JOIN [ATENDENTES] a   ON a.YCODVEN   = cv.YCODVEN2
LEFT JOIN [ATENDENTES] ach ON ach.YCODVEN = cv.YCODVEN
WHERE cv.YTIPOPE = 'S'              -- partição de domínio (vendas). Filtro YDATEXC vive no silver.